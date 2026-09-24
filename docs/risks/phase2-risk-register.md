# Phase 2 Risk Register

**Version:** 1.0  
**Date:** 2026-09-22  
**Scope:** Days 31–45 (Phase 2 — Domain Decoupling)  
**Owner:** Engineering Manager  
**Review cadence:** Daily stand-up; escalate any TRIGGERED risk within 24 hours  

---

## Risk Codes

Risks R1–R5 map to the five critical-path blockers identified in
[`docs/plans/master-plan.md`](../plans/master-plan.md).

---

## R1 — OpenBao Unsealed / i3/ Paths Inaccessible

| Field | Value |
|-------|-------|
| **Code** | R1 |
| **Category** | Infrastructure |
| **Probability** | Low |
| **Impact** | Critical — all Phase 2 services fail at startup (secrets not injected) |
| **Trigger** | Any Phase 2 pod fails with `Error: unable to retrieve secret from vault` or OOMKilled in vault-agent sidecar |
| **Affected steps** | P2-01, P2-02, P2-03, P2-04, P2-05, P2-06, P2-07 |

**Mitigation:**
- Pre-flight: `vault status | grep "^Sealed.*false"` — must be green before any Phase 2 deploy.
- Verify SA token binding: `kubectl exec deploy/<svc> -n <ns> -- vault token lookup`.
- Pin OpenBao version in ArgoCD app to prevent accidental upgrade-triggered seal.

**Rollback Plan:**
1. Re-unseal with all three unseal keys: `vault operator unseal <key-1>`, `<key-2>`, `<key-3>`.
2. Re-verify `i3/` KV v2 paths: `vault kv list i3/`.
3. Rollout-restart affected deployments: `kubectl rollout restart deploy/<svc> -n <ns>`.
4. If seal is caused by KMS key rotation: `vault operator rekey` — requires quorum of key holders.
5. Estimated recovery time: < 30 minutes.

**Acceptance criteria for closure:** `vault status` returns `Sealed: false` and all Phase 2 pods
reach `Running` state.

---

## R2 — Redis Unavailable

| Field | Value |
|-------|-------|
| **Code** | R2 |
| **Category** | Infrastructure |
| **Probability** | Low |
| **Impact** | High — consent TTL cache, agent session cache, and Kong rate-limit backend all fail |
| **Trigger** | `kubectl get pod -n i3-data -l app=redis` returns `CrashLoopBackOff` or `OOMKilled`; or `redis-cli ping` returns `NOAUTH` or timeout |
| **Affected steps** | P2-02 (consent TTL), P2-03 (session cache), P2-07 (rate-limit) |

**Mitigation:**
- Deploy Redis StatefulSet with PVC (data survives pod restart).
- Set `maxmemory-policy allkeys-lru` to prevent OOM eviction blocking new writes.
- Add Redis Sentinel for automatic failover if cluster budget allows.

**Rollback Plan:**
1. Consent service: circuit-breaker defaults to `allowed: false` — sends stop silently (no data corruption).
2. Agent Registry: decision log emission is fire-and-forget — agents continue operating, log entries are dropped (recoverable from OTel traces).
3. Kong rate-limiter: configure `policy: local` fallback so rate limiting continues in-memory per Kong pod.
4. Restore Redis: `kubectl rollout undo statefulset/redis -n i3-data` or restore from PVC snapshot.
5. Estimated recovery time: < 15 minutes with PVC restore.

**Acceptance criteria for closure:** `kubectl exec -n i3-data redis-0 -- redis-cli ping` returns
`PONG`; all dependent services report healthy cache connections.

---

## R3 — Keycloak JWKS Unreachable

| Field | Value |
|-------|-------|
| **Code** | R3 |
| **Category** | Identity / Security |
| **Probability** | Low |
| **Impact** | Critical — Kong JWT plugin fails; all external routes return 401/503; all authenticated traffic blocked |
| **Trigger** | Kong logs show `failed to fetch JWKS`; `curl http://keycloak.i3-auth.svc.cluster.local:8080/realms/i3/protocol/openid-connect/certs` returns non-200 |
| **Affected steps** | P2-07 (Kong API Gateway) |

**Mitigation:**
- Pin JWKS URI to cluster-internal DNS (`keycloak.i3-auth.svc.cluster.local`) — never external FQDN.
- Add a liveness probe on the Keycloak pod that checks `/realms/i3/.well-known/openid-configuration`.
- Cache JWKS in Kong with `cache_ttl: 300` — brief Keycloak restart does not break in-flight sessions.

**Rollback Plan:**
1. Immediate: disable the Kong JWT plugin on the affected route — traffic flows unauthenticated (temporary, timed).
2. Restore Keycloak: `kubectl rollout restart deploy/keycloak -n i3-auth`.
3. If Keycloak DB is corrupt: restore from Crunchy PostgreSQL PITR backup.
4. Re-enable Kong JWT plugin after Keycloak health check passes.
5. Estimated recovery time: < 20 minutes for pod restart; up to 2 hours for DB restore.

**Acceptance criteria for closure:** Kong logs show `JWKS fetch succeeded`; `curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $VALID_TOKEN" https://api.i3technologies.co.ke/admissions/chat` returns `200`.

---

## R4 — IBM Cloud Credit Exhaustion

| Field | Value |
|-------|-------|
| **Code** | R4 |
| **Category** | Commercial / Budget |
| **Probability** | Medium (PMC Risk #1 — flagged in Enhancement 3 PMC guide) |
| **Impact** | Critical — node scheduling failures; pods evicted; entire cluster unavailable |
| **Trigger** | IBM Cloud dashboard shows credit balance < USD 500; node `SchedulingDisabled`; pods pending with `Insufficient cpu/memory` |
| **Affected steps** | All Phase 2 steps |

**Mitigation:**
- Verify credit balance before Day 31 kick-off: IBM Cloud dashboard → Billing → Credits.
- Contact IBM TAM to extend credit if balance < USD 2,000 at Phase 2 start.
- Enable IBM Cloud spending notifications at 70% and 90% thresholds.
- Right-size Phase 2 new services: all new pods request ≤ 250m CPU, ≤ 512Mi RAM.

**Rollback Plan:**
1. Immediately pause all non-critical deployments: scale down evalos, pmaas, voice to 0 replicas.
2. Keep critical path alive: Ford API, Admissions, Consent Service, Agent Registry at 1 replica each.
3. Contact IBM TAM within 1 business hour for emergency credit extension.
4. If credit cannot be extended within 24 hours: initiate cluster backup and migration to alternative IaaS (pre-prepared runbook in `docs/ops/cluster-migration.md`).
5. Estimated recovery time: 4 hours with IBM TAM; 48 hours for full migration.

**Acceptance criteria for closure:** IBM Cloud credit balance ≥ USD 2,000; all previously-evicted pods return to `Running`.

---

## R5 — Phase 2 Exit Gate Blocked

| Field | Value |
|-------|-------|
| **Code** | R5 |
| **Category** | Delivery |
| **Probability** | Medium (any one of P2-EX-01 through P2-EX-11 can block) |
| **Impact** | High — Phase 3 Fabric staging (HC-2) is blocked; IEBC 16 March 2027 critical path at risk |
| **Trigger** | Any P2-EX criterion returns non-green after Day 42 gate check |
| **Affected steps** | P2-08 (ADRs), P2-GATE-01 through P2-GATE-10 |

**Mitigation:**
- Run gate-check skill every Friday from Day 35 onward (rolling pre-check).
- Any gate that is amber on Day 39 triggers a same-day engineering sprint to resolve before Day 42.
- P2-EX-09 (latency) and P2-EX-10 (CVE) are baselined in `docs/baselines/p1-performance-baseline.md` — no ambiguity about pass/fail.

**Rollback Plan per criterion:**

| Criterion | Rollback |
|-----------|---------|
| P2-EX-01 Consent Service down | `kubectl rollout undo deploy/consent-service -n i3-consent` |
| P2-EX-02 Agent Registry missing entries | Re-apply manifests: `kubectl apply -f platform/agent-registry/manifests/` |
| P2-EX-03 MCP Gateway down | `kubectl rollout undo deploy/mcp-gateway -n i3-agent-mesh` |
| P2-EX-04 RLS migration failure | `psql $ENGAGE_DB_URL -f platform/engage/web/migrations/rollback-002.sql` |
| P2-EX-05 Grading/Credential service down | `kubectl rollout undo deploy/grading-service -n i3-evalos` |
| P2-EX-06 Kong blocking legitimate traffic | Disable JWT plugin on affected route; restore direct OpenShift Route |
| P2-EX-07 ADRs missing | Write missing ADRs from template; merge to `main` |
| P2-EX-08 RAGAS regression | Revert last LLM prompt change; re-run RAGAS eval |
| P2-EX-09 Latency regression | Profile with OTel trace; roll back the step that introduced the regression |
| P2-EX-10 New CVE | `trivy image --severity CRITICAL,HIGH <image>`; patch Dockerfile; rebuild |
| P2-EX-11 L2/L3 manifest | `grep -r "autonomy_level: L[23]" platform/agent-registry/manifests/` → remove |

**Acceptance criteria for closure:** All P2-EX-01 through P2-EX-11 return green; `gate-check`
skill outputs `APPROVED`.

---

## HC Coverage Matrix

Every risk maps to the hard constraints it protects:

| Risk | HC-1 | HC-2 | HC-3 | HC-4 | HC-5 | HC-6 | HC-7 | HC-8 |
|------|:----:|:----:|:----:|:----:|:----:|:----:|:----:|:----:|
| R1 OpenBao | ✓ | ✓ | | ✓ | ✓ | ✓ | | |
| R2 Redis | | ✓ | | ✓ | | | | |
| R3 JWKS | | ✓ | | | | | ✓ | |
| R4 Credits | | ✓ | | | | | | |
| R5 Exit gate | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
