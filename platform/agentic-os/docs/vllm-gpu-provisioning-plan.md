# vLLM GPU Node Provisioning Plan
# File: platform/agentic-os/docs/vllm-gpu-provisioning-plan.md
# Context: i3 AI Platform — Pre-Plan Phase Gate for Application 3 (Agentic AI OS)

## 1. Model Inventory & GPU Memory Requirements

| Model | Use Case | Quantization | VRAM Required | Source |
|---|---|---|---|---|
| Qwen-2.5-72B-Instruct | High-risk / financial decisions | AWQ 4-bit | ~36 GB | HuggingFace |
| Llama-3.3-70B-Instruct | Multi-step reasoning | AWQ 4-bit | ~36 GB | HuggingFace |
| IBM Granite-3B-Instruct | Simple intent / drafts | BF16 | ~6 GB | HuggingFace |
| **Total peak VRAM** | | | **~78 GB** | |

**Note:** Qwen-72B and Llama-70B are never loaded simultaneously in the default
routing config (the supervisor routes to one model per request). With speculative
decoding, Granite-3B acts as the draft model for Llama-70B — both are loaded
simultaneously, requiring ~42 GB VRAM for that pair.

---

## 2. Recommended GPU Configuration

### Option A: 2× NVIDIA A100 80GB (RECOMMENDED)
- 2 × 80 GB HBM2e = 160 GB total VRAM
- Covers all three models simultaneously (78 GB used, 82 GB headroom)
- Tensor parallel across 2 GPUs for 70B+ models (vLLM `tensor_parallel_size=2`)
- IBM Cloud: `gx3.16x80x2l40s` or `gx2.16x160.2a100` worker profile

### Option B: 2× NVIDIA L40S 48GB
- 2 × 48 GB GDDR6 = 96 GB total VRAM
- Covers 70B model on one GPU + Granite-3B on second GPU
- Qwen-72B requires tensor parallel across both L40S GPUs
- Lower cost than A100; adequate for Phase 3 workloads
- IBM Cloud: `gx3.8x40x1l40s` × 2 (one GPU per worker node, 2 worker nodes)

**DECISION: Start with Option B (2× L40S) for cost efficiency in Phase 3.**
Upgrade to Option A (A100) when concurrent 70B model demand justifies it.

---

## 3. IBM Cloud Worker Pool Configuration

```bash
# Create dedicated GPU worker pool for i3-agentic-os namespace
# (run from IBM Cloud Shell or local ibmcloud CLI)

# Option B: L40S worker pool
ibmcloud ks worker-pool create vpc-gen2 \
  --cluster ${ROKS_CLUSTER_NAME} \
  --name gpu-ai-pool \
  --flavor bx2.8x32 \           # Adjust to GPU-enabled flavor
  --size-per-zone 1 \
  --label workload=gpu-inference

# Label nodes for vLLM pod scheduling
kubectl label node <gpu-node-1> nvidia.com/gpu.present=true
kubectl label node <gpu-node-1> workload=gpu-inference

# Verify GPU operator is installed (NVIDIA GPU Operator via OLM)
kubectl get pods -n nvidia-gpu-operator
```

**IBM Cloud GPU worker profile lookup:**
```bash
ibmcloud ks flavors --zone eu-de-1 | grep gpu
```

---

## 4. vLLM Kubernetes Deployment

vLLM is deployed as a LiteLLM backend — not as a standalone service visible
to agents. Agents call LiteLLM, LiteLLM routes GPU-eligible requests to vLLM.

```yaml
# platform/agentic-os/vllm-deploy.yaml (to be created in Implement phase)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-inference
  namespace: i3-agentic-os
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-inference
  template:
    metadata:
      labels:
        app: vllm-inference
    spec:
      nodeSelector:
        workload: gpu-inference
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.6.0
          args:
            - --model
            - /models/llama-3.3-70b-awq
            - --tensor-parallel-size
            - "2"
            - --gpu-memory-utilization
            - "0.90"
            - --enable-chunked-prefill
            - --speculative-model
            - /models/ibm-granite-3b
            - --num-speculative-tokens
            - "5"
            - --served-model-name
            - llama-3.3-70b-instruct
          resources:
            limits:
              nvidia.com/gpu: "2"
              memory: 32Gi
              cpu: "8"
            requests:
              nvidia.com/gpu: "2"
              memory: 32Gi
              cpu: "4"
          volumeMounts:
            - name: model-storage
              mountPath: /models
      volumes:
        - name: model-storage
          persistentVolumeClaim:
            claimName: vllm-model-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-model-pvc
  namespace: i3-agentic-os
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ibmc-vpc-block-general-purpose
  resources:
    requests:
      storage: 200Gi          # Qwen-72B AWQ ~36GB + Llama-70B AWQ ~36GB + Granite-3B ~6GB
```

---

## 5. LiteLLM Configuration — vLLM as Backend

Add to LiteLLM model gateway config (`platform/model-gateway/litellm_config.yaml`):

```yaml
model_list:
  # Existing CPU models (unchanged)
  - model_name: qwen-fast
    litellm_params:
      model: ollama/qwen2.5:3b
      api_base: http://ollama.i3-model-gateway.svc:11434

  # New GPU-resident models via vLLM (OpenAI-compatible API)
  - model_name: llama-3.3-70b-instruct
    litellm_params:
      model: openai/llama-3.3-70b-instruct
      api_base: http://vllm-inference.i3-agentic-os.svc:8000/v1
      api_key: "not-required"             # vLLM internal — no auth needed within cluster

  - model_name: qwen-2.5-72b-instruct
    litellm_params:
      model: openai/qwen-2.5-72b-instruct
      api_base: http://vllm-qwen.i3-agentic-os.svc:8000/v1
      api_key: "not-required"

router_settings:
  # Adaptive routing: high-risk/financial → 72B; multi-step → 70B; simple → CPU
  routing_strategy: usage-based-routing
```

---

## 6. Model Download Procedure

Models are downloaded to the PVC before vLLM pod starts:

```bash
# Run as a Kubernetes Job (model-downloader-job.yaml — created in Implement phase)
# Uses HuggingFace CLI with token from OpenBao i3/agentic-os/huggingface-token

huggingface-cli download \
  meta-llama/Llama-3.3-70B-Instruct-AWQ \
  --local-dir /models/llama-3.3-70b-awq \
  --token ${HF_TOKEN}

huggingface-cli download \
  ibm-granite/granite-3.0-3b-instruct \
  --local-dir /models/ibm-granite-3b \
  --token ${HF_TOKEN}
```

OpenBao secret: `i3/agentic-os/huggingface-token`

---

## 7. Cost Estimate (IBM Cloud Frankfurt, eu-de)

| Resource | Monthly cost (approximate) |
|---|---|
| 2× L40S GPU worker nodes (gx3 profile) | ~$3,200–4,800 USD |
| 200 Gi Block Storage PVC | ~$20 USD |
| Egress for model downloads (~300 GB one-time) | ~$30 USD one-time |
| **Total Phase 3 GPU cost** | **~$3,250–4,830 USD/month** |

**ACTION REQUIRED:** Confirm IBM Cloud credit allocation covers GPU worker pool
before beginning Implement phase for App 3. GPU nodes are on the critical path.

---

## 8. HC Compliance

- **HC-3:** All agents using vLLM-backed models must be registered in Agent Registry
  with `autonomy_tier: L0` or `L1` before any vLLM inference is routed to them.
  The `agentic-os-supervisor` manifest enforces this (created in REQUIRED 6).
- **HC-4:** LiteLLM routes include `tenant_id` in the metadata headers for all calls.
- **HC-5:** vLLM is an inference backend only — it never calls external APIs directly.
  All tool invocations from agents go through the MCP Gateway.
