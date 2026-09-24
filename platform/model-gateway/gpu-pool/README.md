# IMP-10 — GPU Pool + Automatic CPU Fallback  [GAP]

> ⚠ **ALL GPU ACCELERATION CLAIMS ARE GATED.**  
> No output in this directory may be applied to production until
> `bench_gpu.py` prints **`PASS`** for every production model alias.

---

## Status

| Component | File | Status |
|-----------|------|--------|
| GPU MachineSet + ClusterPolicy + ResourceQuota | `gpu-node-pool.yaml` | **[GAP]** — not applied |
| Ollama GPU StatefulSet + Services | `vllm-gpu-deploy.yaml` | **[GAP]** — not applied |
| LiteLLM GPU routing ConfigMap | `litellm-config-gpu.yaml` | **[GAP]** — not applied |
| KEDA MachineAutoscaler + ScaledObject | `keda-gpu-scaler.yaml` | **[GAP]** — paused |
| Benchmark harness | `bench_gpu.py` | Ready to run |

---

## Architecture

```
Incoming request (any alias)
        │
        ▼
  LiteLLM Proxy
  routing_strategy: least-busy
        │
        ├── <alias>-gpu  ──► ollama-gpu:11435  (NVIDIA V100, primary)
        │                         │ timeout < GPU_TARGET_TTFT_S
        │                         │ on failure / timeout ↓
        └── <alias>       ──► ollama-service:11434  (CPU bx2.4x16, fallback)
                                  │ timeout unchanged from canonical config
                                  │ on failure → granite-nano (terminal)
```

### GPU → CPU fallback triggers
- `allowed_fails: 3` consecutive failures
- Per-model timeout exceeded (GPU timeouts are 3–4× shorter than CPU)
- `cooldown_time: 60` seconds before GPU re-tried after cooldown

---

## Pre-requisites

1. **IBM Cloud account** with `gx2-8x64x1v100` (or equivalent) profile quota
2. **NVIDIA GPU Operator** installed via OLM in `openshift-operators`
3. **DCGM Exporter** deployed (enables GPU utilisation KEDA trigger)
4. **ResourceQuota** applied to cap GPU requests at 3 per namespace

---

## Benchmark Harness

### Install

```bash
pip install httpx
```

### CPU baseline only (run before GPU nodes are available)

```bash
python3 bench_gpu.py \
    --cpu-only \
    --cpu-url http://litellm.i3technologies.co.ke \
    --litellm-key "$(vault kv get -field=key i3/litellm/master-key)"
```

### Full GPU vs CPU comparison

```bash
python3 bench_gpu.py \
    --cpu-url http://litellm.i3technologies.co.ke \
    --gpu-url http://litellm.i3technologies.co.ke \
    --litellm-key "$(vault kv get -field=key i3/litellm/master-key)" \
    --n-runs 5 \
    --out bench_results_$(date +%Y%m%d).json
```

### PASS criteria (all must hold per alias)

| Condition | Rule |
|-----------|------|
| Absolute | GPU TTFT < `GPU_TARGET_TTFT_S[alias]` |
| Relative | GPU TTFT < `CPU_BASELINE_TTFT_S[alias] × 0.50` (2× minimum speedup) |

---

## Activation (GPU Promotion — ONLY after `bench_gpu.py` PASS)

```bash
# 1. Replace LiteLLM config with GPU routing config
oc set volume deployment/litellm-proxy \
    -n i3-model-gateway \
    --add --name=config --type=configmap \
    --configmap-name=litellm-config-gpu \
    --mount-path=/app/config.yaml \
    --sub-path=config.yaml \
    --overwrite

# 2. Unpause KEDA GPU ScaledObject
oc annotate scaledObject/ollama-gpu-scaler \
    -n i3-model-gateway \
    'autoscaling.keda.sh/paused'=false --overwrite

# 3. Commit config changes (remove paused: true from keda-gpu-scaler.yaml)
# 4. Remove [GAP] annotations from all files in this directory
# 5. Update i3-platform-atomic-execution-plan.md IMP-10 status → COMPLETE
```

---

## Rollback

```bash
# Revert to CPU-only config instantly (no downtime — CPU fallback is always warm)
oc set volume deployment/litellm-proxy \
    -n i3-model-gateway \
    --add --name=config --type=configmap \
    --configmap-name=litellm-config \
    --mount-path=/app/config.yaml \
    --sub-path=config.yaml \
    --overwrite
```

---

## Hard Constraint Compliance

| HC | Compliance |
|----|-----------|
| HC-3 | GPU pool is infrastructure only — no agent autonomy change |
| HC-4 | `tenant_id` enforcement is at LiteLLM virtual-key layer — unchanged |
| HC-5 | No agent may invoke GPU endpoints directly; all calls route through LiteLLM proxy |
| HC-7 | `DEV_BYPASS_AUTH` is absent from all files in this directory |
