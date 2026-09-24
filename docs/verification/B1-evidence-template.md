# B1 — GPU-Accelerated Inference Evidence Pack

> ⚠ **STATUS: INCOMPLETE — GPU NODE PROVISIONING REQUIRED**  
> The benchmark harness (`platform/model-gateway/gpu-pool/bench_gpu.py`) is **ready to run** but GPU nodes are `[GAP]` — not yet provisioned.  
> The claim "GPU-accelerated inference" **MAY NOT** be made in the present tense until this document records a signed PASS from the benchmark harness.

| Field | Value |
|-------|-------|
| **Evidence ID** | B1-evidence-_[YYYYMMDD]_ |
| **Capability Claim** | "GPU-accelerated inference" |
| **Condition to unlock** | B1 benchmark harness signed PASS |
| **Benchmark harness** | `platform/model-gateway/gpu-pool/bench_gpu.py` |
| **Auditor** | _[To be completed by platform team]_ |
| **Run date** | _[YYYY-MM-DD]_ |
| **Environment** | Production cluster — `https://api.i3technologies.co.ke` |
| **GPU node profile** | IBM Cloud `gx2-8x64x1v100` (NVIDIA V100) |
| **Classification** | Internal Engineering |

---

## Acceptance Criteria

Both conditions must hold for EVERY model alias before the claim is unlocked:

| Condition | Rule |
|-----------|------|
| **Absolute** | GPU TTFT < `GPU_TARGET_TTFT_S[alias]` (per-alias ceiling in `bench_gpu.py:95–104`) |
| **Relative** | GPU TTFT < `CPU_BASELINE_TTFT_S[alias] × 0.50` (minimum 2× speedup over CPU baseline) |

Any single alias failing either condition → harness exits 1, verdict FAIL, claim remains **LOCKED**.

---

## Pre-Requisites Checklist

Before running the benchmark:

| # | Pre-Requisite | Status |
|---|--------------|--------|
| P-01 | IBM Cloud `gx2-8x64x1v100` node provisioned (or equivalent GPU profile) | ⬜ PENDING |
| P-02 | NVIDIA GPU Operator installed via OLM in `openshift-operators` | ⬜ PENDING |
| P-03 | DCGM Exporter deployed (enables GPU utilisation KEDA trigger) | ⬜ PENDING |
| P-04 | ResourceQuota applied — cap GPU requests at 3 per namespace | ⬜ PENDING |
| P-05 | `vllm-gpu-deploy.yaml` applied (`platform/model-gateway/gpu-pool/`) | ⬜ PENDING |
| P-06 | `litellm-config-gpu.yaml` ConfigMap applied | ⬜ PENDING |
| P-07 | `keda-gpu-scaler.yaml` applied with `paused: false` | ⬜ PENDING |
| P-08 | All `-gpu` model aliases responding to LiteLLM proxy | ⬜ PENDING |

---

## Benchmark Run Instructions

```bash
# 1. Install harness dependency
pip install httpx

# 2. Run full GPU vs CPU benchmark (5 runs per alias for statistical stability)
python3 platform/model-gateway/gpu-pool/bench_gpu.py \
    --cpu-url http://litellm.i3technologies.co.ke \
    --gpu-url http://litellm.i3technologies.co.ke \
    --litellm-key "$(vault kv get -field=key i3/litellm/master-key)" \
    --n-runs 5 \
    --out docs/verification/bench_results_$(date +%Y%m%d).json

# 3. Capture full terminal output (includes per-alias table and PASS/FAIL verdict)
# 4. Copy bench_results_YYYYMMDD.json to docs/verification/
# 5. Record results in the table below
```

---

## Benchmark Results (Complete When Run)

### Per-Alias Results Table

| Alias | CPU Baseline (s) | GPU TTFT (s) | Speedup | Abs PASS (<target) | Rel PASS (<50% CPU) | Verdict |
|-------|-----------------|-------------|---------|-------------------|-------------------|---------|
| granite-nano | 4.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| embed | 1.5 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| qwen-fast | 18.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| coder | 20.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| qwen-heavy | 45.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| vision | 50.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| mistral-nemo | 18.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |
| granite-heavy | 45.0 | _[ ]_ | _[ ]× | _[ ]_ | _[ ]_ | ⬜ |

### Harness Output (Paste Full Terminal Output)

```
[Paste complete bench_gpu.py terminal output here — including the ═══ RESULTS block and VERDICT line]
```

### JSON Artefact Location

`docs/verification/bench_results_[YYYYMMDD].json`

---

## GPU Targets Reference (from `bench_gpu.py:95–104`)

| Alias | GPU Target TTFT (s) |
|-------|-------------------|
| granite-nano | 1.5 |
| embed | 0.5 |
| qwen-fast | 5.0 |
| coder | 5.0 |
| qwen-heavy | 12.0 |
| vision | 14.0 |
| mistral-nemo | 5.0 |
| granite-heavy | 12.0 |

---

## Post-PASS Activation Steps

Only execute after harness prints PASS and this document is signed:

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

# 3. Remove [GAP] annotations from all files in platform/model-gateway/gpu-pool/
# 4. Update i3-platform-atomic-execution-plan.md IMP-10 status → COMPLETE
# 5. Update this document status → PASS and complete sign-off below
```

---

## Overall Verdict

**Current status: INCOMPLETE — claim LOCKED**

To unlock: run `bench_gpu.py`, paste results above, confirm all 8 aliases PASS both conditions, complete sign-off.

---

## Sign-Off (complete when harness prints PASS for all aliases)

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Platform Architect | | | |
| Infrastructure Lead | | | |

---

*Document path: `docs/verification/B1-evidence-template.md`*  
*Rename to `B1-evidence-[YYYYMMDD].md` when completed.*  
*Template generated by Bob AI Auditor · i3 AI Platform*  
*Harness: `platform/model-gateway/gpu-pool/bench_gpu.py`*
