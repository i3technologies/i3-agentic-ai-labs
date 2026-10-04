#!/usr/bin/env python3
"""
P3-GATE-02: LiteLLM Semantic Cache Warm-Up Script
Sends 50 identical admissions FAQ questions directly to LiteLLM
(/v1/chat/completions) so the semantic cache is populated, then checks the
Prometheus cache-hit ratio metric.

Rationale for targeting LiteLLM directly (not admissions agent):
  The admissions /chat endpoint requires a Keycloak Bearer JWT that cannot be
  obtained in a headless gate runner without a human SSO flow. The Redis
  semantic cache lives inside LiteLLM — hitting it directly with the master
  key is the correct and sufficient way to warm and verify the cache.
  (The admissions agent also calls LiteLLM; any cache entries added here are
  served to the agent on the next real request.)

Usage (from repo root, after cluster auth):
  pip3 install httpx --quiet
  python3 platform/scripts/p3-gate-02-cache-warmup.py

Environment variables (all optional — sensible defaults supplied):
  LITELLM_URL          — default: https://litellm.i3technologies.co.ke
  LITELLM_MASTER_KEY   — LiteLLM master key (auto-read from cluster secret in
                         p3-run-gates.ps1); also checked as LITELLM_API_KEY
  LITELLM_MODEL        — default: granite-nano  (always-warm Tier 3 model)
  PROMETHEUS_URL       — default: https://prometheus.i3technologies.co.ke
"""

import asyncio
import json
import os
import sys

try:
    import httpx
except ImportError:
    import subprocess
    for pip_cmd in (
        ["pip3", "install", "httpx", "--quiet", "--user"],
        ["pip", "install", "httpx", "--quiet", "--user"],
        [sys.executable, "-m", "pip", "install", "httpx", "--quiet", "--user"],
    ):
        try:
            subprocess.check_call(pip_cmd, stderr=subprocess.DEVNULL)
            break
        except Exception:
            continue
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not available and could not be installed.")
        print("  Run manually: pip3 install httpx")
        sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────
# Send directly to LiteLLM (not admissions agent) so no Keycloak JWT is needed.
# Explicitly read LITELLM_URL and guard against accidentally inheriting
# ADMISSIONS_AGENT_URL or any WebSocket-based URL from the environment.
_raw_litellm_url = os.environ.get(
    "LITELLM_URL",
    "https://litellm.i3technologies.co.ke",
).rstrip("/")
# Strip /chat or /admissions path segments that would target the wrong endpoint
if "/admissions" in _raw_litellm_url or "/onboarding" in _raw_litellm_url or "/pmaas" in _raw_litellm_url:
    print(f"WARNING: LITELLM_URL looks like an agent URL ({_raw_litellm_url}) — resetting to default LiteLLM host")
    _raw_litellm_url = "https://litellm.i3technologies.co.ke"
LITELLM_URL = _raw_litellm_url
LITELLM_KEY = os.environ.get(
    "LITELLM_MASTER_KEY",
    os.environ.get("LITELLM_API_KEY", os.environ.get("LITELLM_KEY", "")),
)
LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "granite-nano")
PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL",
    "https://prometheus.i3technologies.co.ke",
)

WARMUP_QUESTION = "What are the entry requirements for the AI Engineering program?"
WARMUP_COUNT = 50
CACHE_HIT_THRESHOLD = 0.20


async def send_question(client: httpx.AsyncClient, idx: int) -> dict:
    """Send one FAQ question directly to LiteLLM /v1/chat/completions."""
    if not LITELLM_KEY:
        print(f"  [{idx:02d}/{WARMUP_COUNT}] SKIP: LITELLM_MASTER_KEY not set")
        return {}
    headers = {"Authorization": f"Bearer {LITELLM_KEY}"}
    payload = {
        "model": LITELLM_MODEL,
        "messages": [{"role": "user", "content": WARMUP_QUESTION}],
        "max_tokens": 256,
    }
    for attempt in range(3):
        try:
            resp = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=90.0,
            )
            if resp.status_code == 426:
                # 426 Upgrade Required — Kong is requiring WebSocket on this route.
                # This means LITELLM_URL is pointing at the Kong-gated /chat WebSocket
                # endpoint rather than the LiteLLM proxy REST API.
                print(
                    f"  [{idx:02d}/{WARMUP_COUNT}] ERROR 426: Kong is requiring WebSocket upgrade.\n"
                    f"    Current LITELLM_URL: {LITELLM_URL}\n"
                    f"    Fix: export LITELLM_URL=https://litellm.i3technologies.co.ke\n"
                    f"    (Do NOT use the admissions /chat WebSocket endpoint for cache warm-up)"
                )
                return {}
            if resp.status_code == 429:
                wait = 2 ** attempt
                print(f"  [{idx:02d}/{WARMUP_COUNT}] RATE_LIMITED — waiting {wait}s ...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            tokens = data.get("usage", {}).get("total_tokens", "?")
            cached = data.get("usage", {}).get("cache_read_input_tokens", 0) or \
                     ("cached" in json.dumps(data).lower())
            tag = "CACHE_HIT" if cached else "ok"
            print(f"  [{idx:02d}/{WARMUP_COUNT}] {tag} — tokens: {tokens}")
            return data
        except Exception as exc:
            print(f"  [{idx:02d}/{WARMUP_COUNT}] ERROR (attempt {attempt+1}): {exc}")
            if attempt < 2:
                await asyncio.sleep(2)
    return {}


async def query_cache_hit_rate() -> float:
    """Query Prometheus for the LiteLLM semantic cache hit ratio."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        for metric in [
            'litellm_cache_hit_ratio',
            'sum(rate(litellm_cache_hits_total[5m])) / (sum(rate(litellm_cache_hits_total[5m])) + sum(rate(litellm_cache_misses_total[5m])))',
        ]:
            try:
                resp = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query",
                    params={"query": metric},
                )
                data = resp.json()
                results = data.get("data", {}).get("result", [])
                if results:
                    val = float(results[0]["value"][1])
                    return val
            except Exception:
                continue
    print("WARNING: Could not query Prometheus — cache metric unavailable")
    print(f"  Prometheus URL: {PROMETHEUS_URL}")
    print("  To check manually: kubectl exec -n i3-monitoring deploy/prometheus -- curl localhost:9090/api/v1/query?query=litellm_cache_hit_ratio")
    return 0.0


async def main():
    print(f"=== P3-GATE-02: LiteLLM Cache Warm-Up ({WARMUP_COUNT} requests) ===")
    print(f"    LiteLLM:    {LITELLM_URL}")
    print(f"    Model:      {LITELLM_MODEL}")
    print(f"    Prometheus: {PROMETHEUS_URL}")
    print(f"    Question:   {WARMUP_QUESTION[:70]}...")
    print()

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, WARMUP_COUNT, 5):
            batch = range(batch_start + 1, min(batch_start + 6, WARMUP_COUNT + 1))
            tasks = [send_question(client, i) for i in batch]
            await asyncio.gather(*tasks)
            if batch_start + 5 < WARMUP_COUNT:
                await asyncio.sleep(1)

    print()
    print("=== Checking cache hit ratio (waiting 10s for Prometheus scrape) ===")
    await asyncio.sleep(10)

    hit_rate = await query_cache_hit_rate()
    pass_flag = hit_rate >= CACHE_HIT_THRESHOLD

    result = {
        "gate": "P3-GATE-02",
        "warmup_queries_sent": WARMUP_COUNT,
        "cache_hit_ratio": round(hit_rate, 4),
        "threshold": CACHE_HIT_THRESHOLD,
        "pass": pass_flag,
    }

    print(json.dumps(result, indent=2))
    print()
    print(f"P3-GATE-02: {'PASS' if pass_flag else 'FAIL'} — cache hit ratio = {hit_rate:.2%} (target ≥ {CACHE_HIT_THRESHOLD:.0%})")

    if not pass_flag:
        print()
        print("TROUBLESHOOTING:")
        print("  1. Confirm cache block is under litellm_settings: in litellm-config-oss.yaml")
        print("     grep -A8 'cache:' platform/model-gateway/litellm/litellm-config-oss.yaml")
        print("  2. Check Redis: kubectl exec -n i3-model-gateway deploy/litellm-proxy -- redis-cli ping")
        print("  3. Check LiteLLM logs: kubectl logs -n i3-model-gateway deploy/litellm-proxy | grep -i cache | tail -20")
        print(f"  4. Override LiteLLM URL:  export LITELLM_URL=https://litellm.i3technologies.co.ke")
        print(f"  5. Override model:        export LITELLM_MODEL=granite-nano")
        sys.exit(1)

    print("✓ P3-GATE-02 PASS")


if __name__ == "__main__":
    asyncio.run(main())
