#!/usr/bin/env python3
"""
P3-GATE-02: LiteLLM Semantic Cache Warm-Up Script
Sends 50 identical admissions FAQ questions through the admissions agent,
then checks the Grafana/Prometheus cache-hit ratio metric.

Usage (from repo root, after cluster auth):
  pip3 install httpx --quiet
  python3 platform/scripts/p3-gate-02-cache-warmup.py

External URL env vars (for Cloud Shell / outside-cluster use):
  ADMISSIONS_AGENT_URL   — default: https://api.i3technologies.co.ke/admissions
  LITELLM_URL            — default: https://api.i3technologies.co.ke/litellm
  LITELLM_MASTER_KEY     — LiteLLM master key (from OpenBao i3/litellm/api-key)
  PROMETHEUS_URL         — default: https://prometheus.i3technologies.co.ke
                           (set to http://prometheus-operated.i3-monitoring.svc.cluster.local:9090
                            when running from inside the cluster)
"""

import asyncio
import json
import os
import sys
import time

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
    import httpx

# External-facing URLs as defaults — override with in-cluster DNS when running inside the cluster
ADMISSIONS_AGENT_URL = os.environ.get(
    "ADMISSIONS_AGENT_URL",
    "https://api.i3technologies.co.ke/admissions",
)
LITELLM_URL = os.environ.get(
    "LITELLM_URL",
    "https://api.i3technologies.co.ke/litellm",
)
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", os.environ.get("LITELLM_KEY", ""))
PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL",
    "https://prometheus.i3technologies.co.ke",
)

WARMUP_QUESTION = "What are the entry requirements for the AI Engineering program?"
WARMUP_COUNT = 50
CACHE_HIT_THRESHOLD = 0.20


async def send_question(client: httpx.AsyncClient, idx: int) -> dict:
    """Send one FAQ question to the admissions agent."""
    headers = {}
    if LITELLM_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_KEY}"
    try:
        resp = await client.post(
            f"{ADMISSIONS_AGENT_URL}/chat",
            json={"message": WARMUP_QUESTION},
            headers=headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"  [{idx:02d}/{WARMUP_COUNT}] OK — reply length: {len(result.get('reply', ''))}")
        return result
    except Exception as exc:
        print(f"  [{idx:02d}/{WARMUP_COUNT}] ERROR: {exc}")
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
    print(f"    Agent:      {ADMISSIONS_AGENT_URL}")
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
        print(f"  4. Override agent URL: export ADMISSIONS_AGENT_URL=https://api.i3technologies.co.ke/admissions")
        sys.exit(1)

    print("✓ P3-GATE-02 PASS")


if __name__ == "__main__":
    asyncio.run(main())
