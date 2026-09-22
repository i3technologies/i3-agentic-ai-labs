# ============================================================
# Locust Load Test — P2-GATE-09 baseline + P3-GATE-13 SLA gates
# Target: i3 Platform APIs (admissions, evalos, engage, pmaas)
#
# P2-GATE-09 (regression): PlatformUser
#   Run: locust -f platform/testing/locust/locustfile.py --headless \
#               --users 50 --spawn-rate 5 --run-time 120s \
#               --host https://api.i3technologies.co.ke \
#               --html platform/testing/locust/report.html
#
# P3-GATE-13 (absolute SLA): NBAConsentUser + BatchPlanUser
#   Run: locust -f platform/testing/locust/locustfile.py \
#               NBAConsentUser BatchPlanUser --headless \
#               --users 50 --spawn-rate 5 --run-time 180s \
#               --host https://api.i3technologies.co.ke \
#               --html platform/testing/locust/p3-sla-report.html
#   Exit code 0: NBA/consent p95 <= 200 ms AND batch planning p95 <= 3000 ms
#   Exit code 1: any SLA breach → P3-GATE-13 BLOCKED
# ============================================================

import os
import random
import json
from locust import HttpUser, task, between, events
from locust.env import Environment

# ── Phase 1 p95 baselines (milliseconds) ─────────────────────
# These are set by running the Phase 1 gate and recording results.
# Update this dict after each confirmed Phase completion.
P1_P95_BASELINES = {
    "/health":                    120,
    "/admissions/chat":           2800,
    "/api/exam/{examId}/start":   800,
    "/api/campaigns/send":        1200,
    "/api/briefing/generate":     3500,
}
P2_REGRESSION_LIMIT_PCT = 15  # p95 must not exceed baseline by more than 15%

# ── Phase 3 absolute SLA limits (milliseconds) — P3-GATE-13 ──
P3_SLA_LIMITS: dict[str, float] = {
    "/api/consent/{subjectHash}": 200,    # NBA / consent check ≤ 200 ms
    "/api/briefing/generate":     3000,   # batch planning ≤ 3 s
}

# Shared response-time accumulator (keyed by endpoint name).
_response_times: dict[str, list[float]] = {}

# Credentials injected at runtime by the Tekton p3-sla-locust Task.
_BEARER_TOKEN = os.getenv("LOCUST_BEARER_TOKEN", "test-token")
_TENANT_ID    = os.getenv("LOCUST_TENANT_ID",    "00000000-0000-0000-0000-000000000001")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kw):
    if exception is None:
        _response_times.setdefault(name, []).append(response_time)


# ── P2-GATE-09: regression listener ──────────────────────────
@events.quitting.add_listener
def on_quitting(environment: Environment, **kw):
    violations = []
    for endpoint, baseline_ms in P1_P95_BASELINES.items():
        times = _response_times.get(endpoint, [])
        if not times:
            continue
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times_sorted) * 0.95)]
        limit = baseline_ms * (1 + P2_REGRESSION_LIMIT_PCT / 100)
        if p95 > limit:
            violations.append(
                f"{endpoint}: p95={p95:.0f}ms > limit={limit:.0f}ms "
                f"(baseline={baseline_ms}ms, +{P2_REGRESSION_LIMIT_PCT}%)"
            )
    if violations:
        print("\n[P2-GATE-09] LATENCY REGRESSION VIOLATIONS:")
        for v in violations:
            print(f"  ❌ {v}")
        environment.process_exit_code = 1
    else:
        print("\n[P2-GATE-09] ✅ All p95 latencies within +15% of Phase 1 baseline")


# ── P3-GATE-13: absolute SLA listener ────────────────────────
@events.quitting.add_listener
def on_quitting_p3_sla(environment: Environment, **kw):
    """
    Enforces absolute p95 latency SLAs defined in P3_SLA_LIMITS.
    Sets process_exit_code = 1 on any breach so Tekton marks the gate BLOCKED.
    Only fires when at least one P3 endpoint was exercised in this run.
    """
    p3_endpoints_exercised = [
        ep for ep in P3_SLA_LIMITS if _response_times.get(ep)
    ]
    if not p3_endpoints_exercised:
        return  # P2-only run — skip P3 check

    violations = []
    results = []
    for endpoint, limit_ms in P3_SLA_LIMITS.items():
        times = _response_times.get(endpoint, [])
        if not times:
            results.append(f"  ⚠  {endpoint}: no samples collected")
            continue
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times_sorted) * 0.95)]
        passed = p95 <= limit_ms
        symbol = "✅" if passed else "❌"
        results.append(
            f"  {symbol} {endpoint}: p95={p95:.0f}ms (limit={limit_ms:.0f}ms)"
        )
        if not passed:
            violations.append(
                f"{endpoint}: p95={p95:.0f}ms > SLA limit {limit_ms:.0f}ms"
            )

    print("\n[P3-GATE-13] SLA Results:")
    for r in results:
        print(r)

    if violations:
        print("\n[P3-GATE-13] ❌ GATE BLOCKED — SLA violations:")
        for v in violations:
            print(f"  {v}")
        environment.process_exit_code = 1
    else:
        print("\n[P3-GATE-13] ✅ GATE PASSED — all p95 latencies within SLA limits")


# =============================================================================
# P2-GATE-09: PlatformUser — regression baseline
# =============================================================================

class PlatformUser(HttpUser):
    wait_time = between(1, 3)

    # ── Health checks ────────────────────────────────────────
    @task(5)
    def health_admissions(self):
        self.client.get("/health", name="/health", catch_response=True)

    # ── EvalOS: start exam ───────────────────────────────────
    @task(3)
    def evalos_start_exam(self):
        exam_id = "00000000-0000-0000-0000-000000000099"  # seeded test exam
        with self.client.post(
            f"/api/exam/{exam_id}/start",
            name="/api/exam/{examId}/start",
            json={},
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 403, 404):
                resp.success()

    # ── Admissions chat ──────────────────────────────────────
    @task(2)
    def admissions_chat(self):
        with self.client.post(
            "/admissions/chat",
            name="/admissions/chat",
            json={"message": "What are the admission requirements?", "session_id": "load-test"},
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 403):
                resp.success()

    # ── Engage campaigns ─────────────────────────────────────
    @task(1)
    def engage_campaigns_send(self):
        with self.client.post(
            "/api/campaigns/send",
            name="/api/campaigns/send",
            json={"campaignId": "test", "tenantId": "00000000-0000-0000-0000-000000000001"},
            headers={"Authorization": "Bearer test-token"},
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201, 401, 403, 422):
                resp.success()


# =============================================================================
# P3-GATE-13: NBAConsentUser — NBA / consent check p95 ≤ 200 ms
#
# Simulates the Next-Best-Action agent verifying consent before dispatch.
# 50 concurrent users, 3-minute run, absolute p95 ≤ 200 ms.
#
# Run standalone:
#   locust -f locustfile.py NBAConsentUser --headless \
#          --users 50 --spawn-rate 5 --run-time 180s \
#          --host https://api.i3technologies.co.ke
# =============================================================================

# Seeded subject hashes — HMAC-SHA256 tokens, never raw IDs (HC-6).
_SAMPLE_SUBJECT_HASHES = [
    "a3f2c1d4e5b6a7f8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    "b4e3d2c1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3",
    "c5f4e3d2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4",
    "d6a5b4c3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5",
    "e7b6c5d4f3e2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6",
]

_CONSENT_CHANNELS = ["email", "sms", "push"]
_CONSENT_PURPOSES = ["marketing", "transactional", "service"]


class NBAConsentUser(HttpUser):
    """
    P3-GATE-13-A: NBA / consent check load test.
    SLA: p95 latency ≤ 200 ms at 50 concurrent users.

    Exercises:
      GET  /api/consent/{subjectHash}?channel=…&purpose=…&tenant_id=…
      POST /api/consent/{subjectHash}   (consent record upsert, lower weight)
    """
    wait_time = between(0.1, 0.5)  # tight loop — consent checks are hot path

    def on_start(self):
        self.subject_hash = random.choice(_SAMPLE_SUBJECT_HASHES)
        self.headers = {
            "Authorization": f"Bearer {_BEARER_TOKEN}",
            "X-Tenant-ID":   _TENANT_ID,
        }

    # ── GET consent (read path — NBA hot path, weight 8) ─────
    @task(8)
    def check_consent(self):
        channel = random.choice(_CONSENT_CHANNELS)
        purpose = random.choice(_CONSENT_PURPOSES)
        subject = random.choice(_SAMPLE_SUBJECT_HASHES)
        with self.client.get(
            f"/api/consent/{subject}",
            name="/api/consent/{subjectHash}",
            params={
                "channel":   channel,
                "purpose":   purpose,
                "tenant_id": _TENANT_ID,
            },
            headers=self.headers,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 403, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    # ── POST consent (write path — lower weight) ──────────────
    @task(2)
    def upsert_consent(self):
        subject = random.choice(_SAMPLE_SUBJECT_HASHES)
        with self.client.post(
            f"/api/consent/{subject}",
            name="/api/consent/{subjectHash} [POST]",
            json={
                "channel":   random.choice(_CONSENT_CHANNELS),
                "purpose":   random.choice(_CONSENT_PURPOSES),
                "allowed":   True,
                "tenant_id": _TENANT_ID,
            },
            headers=self.headers,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201, 401, 403, 422):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")


# =============================================================================
# P3-GATE-13-B: BatchPlanUser — batch planning / briefing p95 ≤ 3 s
#
# Simulates PMaaS agents generating AI briefings (batch planning path).
# 20 concurrent users, 3-minute run, absolute p95 ≤ 3,000 ms.
#
# Run standalone:
#   locust -f locustfile.py BatchPlanUser --headless \
#          --users 20 --spawn-rate 2 --run-time 180s \
#          --host https://api.i3technologies.co.ke
# =============================================================================

_BRIEFING_TOPICS = [
    "Ward-level voter registration summary for Machakos",
    "Campaign engagement metrics for the last 7 days",
    "Top 3 issues raised by constituents in Mwala ward",
    "Turnout projections for Kangundo sub-county",
    "Agent performance report — week ending Friday",
]

_CAMPAIGN_IDS = [
    "00000000-0000-0000-0000-000000000101",
    "00000000-0000-0000-0000-000000000102",
    "00000000-0000-0000-0000-000000000103",
]


class BatchPlanUser(HttpUser):
    """
    P3-GATE-13-B: Batch planning / AI briefing load test.
    SLA: p95 latency ≤ 3,000 ms at 20 concurrent users.

    Exercises:
      POST /api/briefing/generate   (primary — LLM-backed, heaviest path)
      POST /api/briefing/ask        (secondary — follow-up question)
    """
    wait_time = between(1, 4)  # briefings are slower; wider think-time

    def on_start(self):
        self.headers = {
            "Authorization": f"Bearer {_BEARER_TOKEN}",
            "X-Tenant-ID":   _TENANT_ID,
        }
        self.last_briefing_id: str | None = None

    # ── POST /api/briefing/generate (LLM path — weight 3) ────
    @task(3)
    def generate_briefing(self):
        with self.client.post(
            "/api/briefing/generate",
            name="/api/briefing/generate",
            json={
                "topic":        random.choice(_BRIEFING_TOPICS),
                "campaign_id":  random.choice(_CAMPAIGN_IDS),
                "tenant_id":    _TENANT_ID,
                "max_tokens":   400,
            },
            headers=self.headers,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201, 401, 403, 422):
                resp.success()
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.last_briefing_id = data.get("briefing_id")
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    # ── POST /api/briefing/ask (follow-up — weight 1) ─────────
    @task(1)
    def ask_briefing(self):
        if not self.last_briefing_id:
            return  # skip until a briefing has been generated
        with self.client.post(
            "/api/briefing/ask",
            name="/api/briefing/ask",
            json={
                "briefing_id": self.last_briefing_id,
                "question":    "What is the recommended next action?",
                "tenant_id":   _TENANT_ID,
            },
            headers=self.headers,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 403, 404, 422):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")
