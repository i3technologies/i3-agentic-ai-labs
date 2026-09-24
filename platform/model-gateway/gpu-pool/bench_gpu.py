#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# IMP-10 — GPU vs CPU First-Token Latency Benchmark Harness
# ============================================================
# PURPOSE
#   Compare first-token latency (TTFT) of GPU-backed model aliases
#   against the recorded CPU baseline.  The harness MUST print PASS
#   before any [GAP]-tagged GPU manifest may be activated in production.
#
# WHAT IS MEASURED
#   Time-to-First-Token (TTFT) via streaming completions.
#   The benchmark sends a short, fixed-length prompt to each alias and
#   measures elapsed time until the FIRST streamed token is received.
#   This is the metric most visible to users in interactive chat.
#
# CPU BASELINES
#   Derived from observed cold-start + warm inference on the existing
#   bx2.4x16 node (Ollama CPU-only, no GPU).  Baselines are intentionally
#   conservative (+20% headroom over median observed).
#
# PASS CRITERIA
#   For each model alias, GPU TTFT must be:
#     1. < GPU_TARGET_TTFT_S[alias]      (absolute threshold)
#     2. < cpu_baseline_s * SPEEDUP_MIN  (relative improvement floor)
#   Both conditions must hold.  Any single failure blocks PASS.
#
# USAGE
#   # Run against a cluster with GPU serving deployed:
#   python3 bench_gpu.py \
#       --cpu-url http://localhost:4000 \
#       --gpu-url http://localhost:4000 \
#       --litellm-key sk-litellm-i3-XXXX
#
#   # Run CPU baseline only (before GPU is available):
#   python3 bench_gpu.py --cpu-only --cpu-url http://localhost:4000 \
#       --litellm-key sk-litellm-i3-XXXX
#
#   # Override thresholds from a JSON file:
#   python3 bench_gpu.py --thresholds custom_thresholds.json ...
#
# OUTPUT
#   Exits 0 and prints "PASS" if all checks pass.
#   Exits 1 and prints "FAIL" with a per-model table if any check fails.
#   Writes results to bench_results_<timestamp>.json for CI artefact upload.
# ============================================================

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not found. Install with: pip install httpx", file=sys.stderr)
    sys.exit(2)

# ── Production model aliases (must match litellm-config*.yaml) ──────────────
# Keys without the "-gpu" suffix are the canonical names used in application code.
ALIASES: list[str] = [
    "granite-nano",
    "embed",
    "qwen-fast",
    "coder",
    "qwen-heavy",
    "vision",
    "mistral-nemo",   # ALI-01
    "granite-heavy",  # ALI-02
]

# ── CPU baselines (seconds TTFT, warm path) ──────────────────────────────────
# These values represent observed warm-path TTFT on the bx2.4x16 CPU node.
# They are the CONTRACT baselines — do not raise them without a new CPU benchmark run.
CPU_BASELINE_TTFT_S: dict[str, float] = {
    "granite-nano": 4.0,    # Granite 3.1 2B — always warm, fast CPU
    "embed":        1.5,    # Embedding model — no generation tokens
    "qwen-fast":   18.0,    # Qwen2.5 7B — warm, 50-token prompt
    "coder":       20.0,    # Qwen2.5-Coder 7B — similar to qwen-fast
    "qwen-heavy":  45.0,    # Qwen2.5 14B — warm, 50-token prompt
    "vision":      50.0,    # LLaVA 13B — text-only path (no image)
    "mistral-nemo": 18.0,   # Alias → qwen-fast CPU baseline
    "granite-heavy": 45.0,  # Alias → qwen-heavy CPU baseline
}

# ── GPU target TTFT (seconds) — absolute ceiling ─────────────────────────────
# Derived from GPU_TIMEOUT values in litellm-config-gpu.yaml × 0.50
# (TTFT is always well below total completion time for short prompts).
GPU_TARGET_TTFT_S: dict[str, float] = {
    "granite-nano": 1.5,
    "embed":        0.5,
    "qwen-fast":    5.0,
    "coder":        5.0,
    "qwen-heavy":  12.0,
    "vision":      14.0,
    "mistral-nemo": 5.0,
    "granite-heavy": 12.0,
}

# ── Minimum speedup factor (GPU_TTFT < cpu_baseline × SPEEDUP_MIN) ───────────
SPEEDUP_MIN: float = 0.50   # GPU must be at least 2× faster than CPU baseline

# ── Benchmark prompt (short, deterministic, exercises first-token path) ──────
BENCH_PROMPT = "Respond with exactly three words."

# ── Embedding benchmark text ──────────────────────────────────────────────────
EMBED_TEXT = "The quick brown fox jumps over the lazy dog."

# ── Number of runs per alias (results are median'd) ──────────────────────────
N_RUNS = 3

# ── Per-request HTTP timeout (must be > max GPU target + margin) ──────────────
HTTP_TIMEOUT_S = 60.0


@dataclass
class BenchResult:
    alias: str
    pool: str              # "cpu" or "gpu"
    ttft_s: float
    runs: list[float] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class CompareResult:
    alias: str
    cpu_ttft_s: float
    gpu_ttft_s: float
    cpu_baseline_s: float
    gpu_target_s: float
    speedup: float
    pass_absolute: bool
    pass_relative: bool
    passed: bool


def measure_ttft_chat(
    base_url: str,
    model: str,
    api_key: str,
    prompt: str,
    timeout: float,
) -> float:
    """Return TTFT in seconds for a chat/completions streaming request."""
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 5,   # We only need the first token
    }
    t0 = time.perf_counter()
    with httpx.stream(
        "POST",
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            raw = line[len("data:"):].strip()
            if raw == "[DONE]":
                break
            chunk = json.loads(raw)
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if delta.get("content"):
                # First actual token received
                return time.perf_counter() - t0
    # Fallback: entire response received without a content token (shouldn't happen)
    return time.perf_counter() - t0


def measure_ttft_embed(
    base_url: str,
    model: str,
    api_key: str,
    text: str,
    timeout: float,
) -> float:
    """Return round-trip time for an embeddings request (no streaming)."""
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "input": text}
    t0 = time.perf_counter()
    resp = httpx.post(
        f"{base_url}/embeddings",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return time.perf_counter() - t0


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def run_bench(
    base_url: str,
    alias: str,
    pool: str,
    api_key: str,
    gpu_alias_suffix: bool,
    n_runs: int,
) -> BenchResult:
    """Run N_RUNS TTFT measurements and return the median."""
    model_name = f"{alias}-gpu" if gpu_alias_suffix else alias
    runs: list[float] = []
    last_err: Optional[str] = None

    for _ in range(n_runs):
        try:
            if alias == "embed":
                t = measure_ttft_embed(base_url, model_name, api_key, EMBED_TEXT, HTTP_TIMEOUT_S)
            else:
                t = measure_ttft_chat(base_url, model_name, api_key, BENCH_PROMPT, HTTP_TIMEOUT_S)
            runs.append(t)
        except Exception as exc:
            last_err = str(exc)

    if not runs:
        return BenchResult(alias=alias, pool=pool, ttft_s=float("inf"), runs=[], error=last_err)

    median_ttft = _median(runs)
    return BenchResult(alias=alias, pool=pool, ttft_s=median_ttft, runs=runs)


def compare(
    cpu_result: BenchResult,
    gpu_result: BenchResult,
) -> CompareResult:
    cpu_b = CPU_BASELINE_TTFT_S[cpu_result.alias]
    gpu_t = GPU_TARGET_TTFT_S[gpu_result.alias]
    speedup = cpu_result.ttft_s / gpu_result.ttft_s if gpu_result.ttft_s > 0 else 0.0
    pass_absolute = gpu_result.ttft_s < gpu_t
    pass_relative = gpu_result.ttft_s < (cpu_b * SPEEDUP_MIN)
    return CompareResult(
        alias=cpu_result.alias,
        cpu_ttft_s=cpu_result.ttft_s,
        gpu_ttft_s=gpu_result.ttft_s,
        cpu_baseline_s=cpu_b,
        gpu_target_s=gpu_t,
        speedup=speedup,
        pass_absolute=pass_absolute,
        pass_relative=pass_relative,
        passed=pass_absolute and pass_relative,
    )


def _fmt_row(r: CompareResult) -> str:
    status = "PASS ✓" if r.passed else "FAIL ✗"
    abs_mark = "✓" if r.pass_absolute else "✗"
    rel_mark = "✓" if r.pass_relative else "✗"
    return (
        f"  {r.alias:<18} "
        f"CPU={r.cpu_ttft_s:>6.2f}s  "
        f"GPU={r.gpu_ttft_s:>6.2f}s  "
        f"speedup={r.speedup:>4.1f}×  "
        f"abs{abs_mark}(<{r.gpu_target_s:.0f}s)  "
        f"rel{rel_mark}(<{r.cpu_baseline_s*SPEEDUP_MIN:.1f}s)  "
        f"{status}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="IMP-10 GPU vs CPU first-token latency benchmark"
    )
    parser.add_argument(
        "--cpu-url",
        default=os.getenv("LITELLM_CPU_URL", "http://localhost:4000"),
        help="LiteLLM proxy URL (CPU Ollama backend)",
    )
    parser.add_argument(
        "--gpu-url",
        default=os.getenv("LITELLM_GPU_URL", "http://localhost:4000"),
        help="LiteLLM proxy URL (GPU Ollama backend)",
    )
    parser.add_argument(
        "--litellm-key",
        default=os.getenv("LITELLM_MASTER_KEY", ""),
        help="LiteLLM master key (or virtual key with model access)",
    )
    parser.add_argument(
        "--cpu-only",
        action="store_true",
        help="Only benchmark CPU baselines (use before GPU is available)",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=N_RUNS,
        help=f"Number of runs per alias (default: {N_RUNS})",
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help="JSON file with custom GPU_TARGET_TTFT_S overrides",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON file path (default: bench_results_<timestamp>.json)",
    )
    args = parser.parse_args()

    if not args.litellm_key:
        print(
            "ERROR: --litellm-key or LITELLM_MASTER_KEY env var required.",
            file=sys.stderr,
        )
        return 2

    # Override thresholds from file if provided
    gpu_targets = dict(GPU_TARGET_TTFT_S)
    if args.thresholds:
        with open(args.thresholds) as f:
            gpu_targets.update(json.load(f))

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out or f"bench_results_{ts}.json"

    print(f"\n{'═'*72}")
    print("  IMP-10 — GPU First-Token Latency Benchmark Harness")
    print(f"  CPU URL : {args.cpu_url}")
    if not args.cpu_only:
        print(f"  GPU URL : {args.gpu_url}")
    print(f"  Aliases : {', '.join(ALIASES)}")
    print(f"  Runs/alias: {args.n_runs}")
    print(f"{'═'*72}\n")

    # ── Step 1: measure CPU baselines ──────────────────────────────────
    print("► Measuring CPU baselines …")
    cpu_results: dict[str, BenchResult] = {}
    for alias in ALIASES:
        r = run_bench(args.cpu_url, alias, "cpu", args.litellm_key, False, args.n_runs)
        cpu_results[alias] = r
        status = f"{r.ttft_s:.2f}s (median of {len(r.runs)})" if not r.error else f"ERROR: {r.error}"
        print(f"  {alias:<18}  CPU TTFT = {status}")

    if args.cpu_only:
        print("\n[cpu-only mode] Skipping GPU measurement.")
        print("\nCPU Baseline Summary:")
        for alias, r in cpu_results.items():
            b = CPU_BASELINE_TTFT_S[alias]
            within = "✓" if r.ttft_s <= b * 1.2 else "WARN"
            print(f"  {alias:<18}  measured={r.ttft_s:.2f}s  contract={b:.1f}s  {within}")
        result_data = {
            "mode": "cpu_only",
            "timestamp": ts,
            "aliases": {a: asdict(r) for a, r in cpu_results.items()},
        }
        with open(out_path, "w") as f:
            json.dump(result_data, f, indent=2)
        print(f"\nResults written to {out_path}")
        return 0

    # ── Step 2: measure GPU paths ───────────────────────────────────────
    print("\n► Measuring GPU paths [GAP] …")
    gpu_results: dict[str, BenchResult] = {}
    for alias in ALIASES:
        r = run_bench(args.gpu_url, alias, "gpu", args.litellm_key, True, args.n_runs)
        gpu_results[alias] = r
        status = f"{r.ttft_s:.2f}s (median of {len(r.runs)})" if not r.error else f"ERROR: {r.error}"
        print(f"  {alias:<18}  GPU TTFT = {status}")

    # ── Step 3: compare and decide ──────────────────────────────────────
    print(f"\n{'═'*72}")
    print("  RESULTS")
    print(f"{'═'*72}")
    comparisons: list[CompareResult] = []
    for alias in ALIASES:
        c = compare(cpu_results[alias], gpu_results[alias])
        comparisons.append(c)
        print(_fmt_row(c))

    # ── Step 4: final verdict ───────────────────────────────────────────
    all_passed = all(c.passed for c in comparisons)
    failed = [c.alias for c in comparisons if not c.passed]

    print(f"\n{'═'*72}")
    if all_passed:
        print("  VERDICT: PASS")
        print("  All GPU aliases meet absolute TTFT targets AND")
        print(f"  deliver ≥{1/SPEEDUP_MIN:.0f}× speedup over CPU baselines.")
        print()
        print("  ► NEXT STEPS (GPU promotion):")
        print("    1. oc set volume deployment/litellm-proxy --name=config \\")
        print("         --from-config-map=litellm-config-gpu")
        print("    2. oc annotate scaledObject/ollama-gpu-scaler \\")
        print("         'autoscaling.keda.sh/paused'=false --overwrite")
        print("    3. Set paused: false in keda-gpu-scaler.yaml and commit.")
        print("    4. Remove [GAP] annotations from gpu-node-pool.yaml and commit.")
    else:
        print("  VERDICT: FAIL [GAP REMAINS]")
        print(f"  Failed aliases: {', '.join(failed)}")
        print()
        print("  GPU manifests remain GATED.  Do NOT activate litellm-config-gpu")
        print("  or remove [GAP] annotations until this harness prints PASS.")
    print(f"{'═'*72}\n")

    # ── Step 5: write JSON artefact ─────────────────────────────────────
    result_data = {
        "mode": "gpu_vs_cpu",
        "timestamp": ts,
        "verdict": "PASS" if all_passed else "FAIL",
        "speedup_min_required": SPEEDUP_MIN,
        "comparisons": [asdict(c) for c in comparisons],
        "cpu_raw": {a: asdict(r) for a, r in cpu_results.items()},
        "gpu_raw": {a: asdict(r) for a, r in gpu_results.items()},
    }
    with open(out_path, "w") as f:
        json.dump(result_data, f, indent=2)
    print(f"Results written to {out_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
