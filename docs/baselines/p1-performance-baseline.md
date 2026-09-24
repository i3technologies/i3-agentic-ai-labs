# Phase 1 Performance & Security Baselines

**Recorded:** Day 30 (Phase 1 exit gate green)  
**Purpose:** Provides the reference values required by P2-EX-09 (Locust latency regression gate)
and P2-EX-10 (Trivy CVE baseline) so those exit criteria are deterministically measurable.

---

## Locust p95 Latency Baselines (Phase 1 exit)

Measured on staging cluster using `locust -u 100 -r 10 --run-time 120s`.

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) | SLO |
|----------|----------|----------|----------|-----|
| `POST /api/plans` (onboarding-agent) | 1 200 | 2 800 | 4 100 | ≤ 3 000 ms p95 |
| `GET /consent/{hash}` (consent-service) | 8 | 18 | 35 | ≤ 200 ms p95 |
| `POST /chat` (admissions-agent) | 900 | 2 100 | 3 400 | ≤ 3 000 ms p95 |
| `POST /api/campaigns/send` (engage) | 320 | 740 | 1 200 | ≤ 3 000 ms p95 (Phase 2; becomes 202 async in Phase 3) |
| `POST /api/exam/{id}/start` (evalos) | 180 | 420 | 680 | ≤ 3 000 ms p95 |
| `POST /briefing/generate` (pmaas) | 1 400 | 3 100 | 5 200 | ≤ 3 000 ms p95 |

**P2-EX-09 pass condition:** No Phase 2 endpoint p95 value exceeds its Phase 1 p95 value by more
than 15%. For example: consent check Phase 1 p95 = 18 ms → Phase 2 must be ≤ 20.7 ms.

---

## Trivy CVE Baseline (Phase 1 exit)

Scanned with `trivy image --severity CRITICAL,HIGH` on all platform images at Day 30.

| Image | CRITICAL | HIGH | Notes |
|-------|----------|------|-------|
| `admissions-agent:latest` | 0 | 0 | chromadb pinned to 0.4.24 (STEP-P1-01) |
| `engage-web:latest` | 0 | 0 | — |
| `evalos-web:latest` | 0 | 0 | — |
| `pmaas-web:latest` | 0 | 1 | 1 HIGH in transitive dep — no fix available; accepted risk logged in `docs/risks/phase2-risk-register.md` |
| `onboarding-agent:latest` | 0 | 0 | — |
| `ford-api:latest` | 0 | 0 | — |
| `talent-api:latest` | 0 | 0 | — |
| `voice-tts:latest` | 0 | 0 | — |

**P2-EX-10 pass condition:** Phase 2 image scans must show **zero new** CRITICAL or HIGH findings
compared to this baseline. The 1 accepted HIGH in `pmaas-web` with no available fix does not
count as "new" for Phase 2 evaluation purposes — it is already recorded here.

---

## RAGAS Baselines (Phase 1 exit — P1-GATE-10)

| Agent | Faithfulness | Answer Relevancy |
|-------|-------------|-----------------|
| admissions-agent | 0.83 | 0.79 |
| pmaas-campaign-agent | 0.81 | 0.77 |

**P2-EX-08 pass condition:** Both agents must remain at or above these scores in Phase 2 CI.
Gate threshold is faithfulness ≥ 0.80 and relevancy ≥ 0.75 (the floor, not this exact score).

---

## How to Update This File

After each phase exit gate passes, append a new dated row to the latency and Trivy tables above
with the new measured values. Do not overwrite previous phase values — they are the audit trail.
