import sys, os, time, statistics, json

CONSENT_SVC = "http://consent-service.i3-consent.svc.cluster.local:8000"
ADMISSIONS_SVC = "http://admissions-agent.i3-admissions.svc.cluster.local:8000"
TENANT_ID = "00000000-0000-0000-0000-000000000001"

import urllib.request, urllib.error, urllib.parse

def timed_get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    t0 = time.time()
    try:
        r = urllib.request.urlopen(url, timeout=8)
        ms = (time.time() - t0) * 1000
        return ms, r.status
    except urllib.error.HTTPError as e:
        ms = (time.time() - t0) * 1000
        return ms, e.code
    except Exception:
        return 10000, 0

N = 50
WARMUP = 5
print(f"P2-GATE-09: p95 latency measurement ({N} requests per endpoint, {WARMUP} warmup)")
results = {}

# Consent check (P1 baseline p95=18ms)
label = "consent_check"
params = {"channel": "email", "purpose": "marketing", "tenant_id": TENANT_ID}
# Warmup requests (discard)
for _ in range(WARMUP):
    timed_get(f"{CONSENT_SVC}/consent/abc123hashval", params)
times = [timed_get(f"{CONSENT_SVC}/consent/abc123hashval", params)[0] for _ in range(N)]
sorted_t = sorted(times)
p50 = sorted_t[N//2]; p95 = sorted_t[int(N*0.95)]; p99 = sorted_t[int(N*0.99)]
results[label] = {"p50_ms": round(p50), "p95_ms": round(p95), "p99_ms": round(p99)}
print(f"  {label:18s}: p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms  (P1 baseline p95=18ms)")

# Consent health (sanity check)
label = "consent_health"
times = [timed_get(f"{CONSENT_SVC}/health")[0] for _ in range(N)]
sorted_t = sorted(times)
p50 = sorted_t[N//2]; p95 = sorted_t[int(N*0.95)]
results[label] = {"p50_ms": round(p50), "p95_ms": round(p95)}
print(f"  {label:18s}: p50={p50:.0f}ms  p95={p95:.0f}ms")

# Admissions health
label = "admissions_health"
times = [timed_get(f"{ADMISSIONS_SVC}/health")[0] for _ in range(N)]
sorted_t = sorted(times)
p50 = sorted_t[N//2]; p95 = sorted_t[int(N*0.95)]
results[label] = {"p50_ms": round(p50), "p95_ms": round(p95)}
print(f"  {label:18s}: p50={p50:.0f}ms  p95={p95:.0f}ms")

print()

# P2-GATE-09: consent p95 must be <= 20.7ms (18ms * 1.15)
consent_p95 = results["consent_check"]["p95_ms"]
baseline_p95 = 18
limit = baseline_p95 * 1.15
gate_pass = consent_p95 <= limit

output = {
    "gate": "P2-GATE-09",
    "evaluated_at": "2026-10-04",
    "p1_baseline_consent_p95_ms": baseline_p95,
    "p2_regression_limit_pct": 15,
    "p2_limit_ms": round(limit, 1),
    "results": results,
    "consent_check_pass": gate_pass,
    "gate_passed": gate_pass,
}
print(json.dumps(output, indent=2))

if gate_pass:
    print("\nP2-GATE-09: PASS")
else:
    print(f"\nP2-GATE-09: FAIL — consent p95={consent_p95}ms > limit={limit:.1f}ms")
    sys.exit(1)
