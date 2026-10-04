#!/usr/bin/env python3
"""
P3-GATE-02: LiteLLM Semantic Cache Warm-Up Script
Sends 50 identical admissions FAQ questions through the admissions agent,
then checks the Grafana/Prometheus cache-hit ratio metric.

Usage:
  python platform/scripts/p3-gate-02-cache-warmup.py

Env vars:
  ADMISSIONS_AGENT_URL   — default: http://admissions-agent.i3-admissions.svc.cluster.local:8000
  LITELLM_URL            — default: http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000
  LITELLM_MASTER_KEY     — LiteLLM master key (from OpenBao i3/litellm/api-key)
  PROMETHEUS_URL         — default: http://prometheus-operated.i3-monitoring.svc.cluster.local:9090
"""

import asyncio
import json
import os
import sys
import time

import httpx

ADMISSIONS_AGENT_URL = os.environ.get(
    "ADMISSIONS_AGENT_URL",
    "http://admissions-agent.i3-admissions.svc.cluster.local:8000",
)
LITELLM_URL = os.environ.get(
    "LITELLM_URL",
    "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000",
)
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")
PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL",
    "http://prometheus-operated.i3-monitoring.svc.cluster.local:9090",
)

# The canonical FAQ question — repeated 50 times to warm the semantic cache.
# The similarity_threshold is 0.95 in litellm-config-oss.yaml; identical queries
# hit the cache 100% of the time once the first response is stored.
WARMUP_QUESTION = "What are the entry requirements for the AI Engineering program?"
WARMUP_COUNT = 50
CACHE_HIT_THRESHOLD = 0.20  # P3-GATE-02: ≥ 20%


async def send_question(client: httpx.AsyncClient, idx: int) -> dict:
    """Send one FAQ question to the admissions agent."""
    try:
        resp = await client.post(
            f"{ADMISSIONS_AGENT_URL}/chat",
            json={"message": WARMUP_QUESTION},
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
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
    """
    Query Prometheus for the LiteLLM semantic cache hit ratio.
    Metric: litellm_cache_hit_ratio or derived from litellm_cache_hits_total /
            (litellm_cache_hits_total + litellm_cache_misses_total).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Try the direct ratio gauge first (LiteLLM >= 1.35)
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
    print("WARNING: Could not query Prometheus — returning 0.0")
    return 0.0


async def main():
    print(f"=== P3-GATE-02: LiteLLM Cache Warm-Up ({WARMUP_COUNT} requests) ===")
    print(f"    Agent:      {ADMISSIONS_AGENT_URL}")
    print(f"    Prometheus: {PROMETHEUS_URL}")
    print(f"    Question:   {WARMUP_QUESTION[:60]}...")
    print()

    # Send 50 questions, 5 at a time (concurrency = 5 to avoid saturating CPU ollama)
    async with httpx.AsyncClient() as client:
        for batch_start in range(0, WARMUP_COUNT, 5):
            batch = range(batch_start + 1, min(batch_start + 6, WARMUP_COUNT + 1))
            tasks = [send_question(client, i) for i in batch]
            await asyncio.gather(*tasks)
            if batch_start + 5 < WARMUP_COUNT:
                await asyncio.sleep(1)  # brief pause between batches

    print()
    print("=== Checking cache hit ratio (waiting 10s for Prometheus scrape) ===")
    await asyncio.sleep(10)

    hit_rate = await query_cache_hit_rate()
    pass_fail = "PASS" if hit_rate >= CACHE_HIT_THRESHOLD else "FAIL"

    result = {
        "gate": "P3-GATE-02",
        "warmup_queries_sent": WARMUP_COUNT,
        "cache_hit_ratio": round(hit_rate, 4),
        "threshold": CACHE_HIT_THRESHOLD,
        "pass": hit_rate >= CACHE_HIT_THRESHOLD,
    }

    print(json.dumps(result, indent=2))
    print()
    print(f"P3-GATE-02: {pass_fail} — cache hit ratio = {hit_rate:.2%} (target ≥ {CACHE_HIT_THRESHOLD:.0%})")

    if not result["pass"]:
        print()
        print("TROUBLESHOOTING:")
        print("  1. Confirm cache block in litellm-config-oss.yaml is under litellm_settings:")
        print("     grep -A8 'cache:' platform/model-gateway/litellm/litellm-config-oss.yaml")
        print("  2. Check Redis connectivity:")
        print("     kubectl exec -n i3-model-gateway deploy/litellm-proxy -- redis-cli -h redis.i3-model-gateway.svc.cluster.local ping")
        print("  3. Check LiteLLM logs for cache errors:")
        print("     kubectl logs -n i3-model-gateway deploy/litellm-proxy | grep -i cache | tail -20")
        sys.exit(1)

    print("✓ P3-GATE-02 PASS")


if __name__ == "__main__":
    asyncio.run(main())
