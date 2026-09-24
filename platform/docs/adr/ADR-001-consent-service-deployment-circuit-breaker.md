# ADR-001: Consent Service Deployment and Circuit-Breaker Pattern

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, Data Protection Officer, Legal (Kenya DPA)  
**Relates to:** EXPLORE-GATE §13 Track B (B-1, B-2, B-3), P2-GATE-01  
**Supersedes:** — (no prior ADR; consent was an inline boolean field)

---

## Context

### Problem Statement

The i3 AI Platform serves multiple channels (FORD-Asili USSD, Engage email/SMS, Admissions
chatbot) that dispatch communications to Kenyan data subjects. As of the Explore phase audit
(2026-09-22), consent is tracked as a raw `consent: bool` field within each service's own domain
model:

- `platform/ford/api/main.py` — `MemberRegister.consent: bool`
- `platform/engage/web/src/app/api/campaigns/send/route.ts` — no consent gate before Brevo dispatch
- Admissions Agent — no consent gate before PII appears in LLM prompt context

This means:
1. **No central audit trail** of when consent was given, withdrawn, or what version of the privacy
   notice the subject agreed to.
2. **No right-to-erasure** flow (Kenya DPA 2019 §26, Kenya DPA 2019 §35(c)). A `DELETE /consent/{subject}` path does not exist.
3. **No circuit-breaker**: if the consent store is unavailable, services silently default to
   **sending** rather than failing closed.
4. The consent service code exists (`platform/consent/`) but has never been deployed
   (EXPLORE-GATE U-07, Severity: Critical).

### Regulatory Context

| Statute | Obligation |
|---------|-----------|
| Kenya Data Protection Act 2019 §25 | Processing requires a lawful basis; consent is one such basis |
| Kenya DPA 2019 §26 | Consent must be freely given, specific, informed, unambiguous |
| Kenya DPA 2019 §35(c) | Data subject right to withdraw consent; must be as easy as giving it |
| Kenya DPA 2019 §61 | ODPC may impose penalties up to KES 3M or 1% of annual turnover |
| IEBC Act (Cap. 7A) s.44 | Voter data is strictly purpose-limited; FORD voter registration dispatches cannot proceed without explicit consent |

---

## Decision

**Deploy the pre-written Consent Service to the `i3-consent` namespace and integrate a
fail-closed circuit-breaker into every service that dispatches PII.**

Specifically:
1. Deploy `platform/consent/main.py` as `consent-service` in namespace `i3-consent`.
2. Expose HTTP API endpoints: `POST /consent`, `GET /consent/{hash}`, `DELETE /consent/{hash}`,
   `GET /consent/{hash}/audit`.
3. Integrate a Redis-backed circuit-breaker (half-open → open on 3 consecutive failures, 30-second
   reset) in FORD API, Engage campaign send route, and Admissions Agent — all three must call the
   consent service **before** any PII dispatch.
4. The circuit-breaker MUST fail closed: if the consent service is unreachable and the circuit is
   open, the dispatch is blocked with HTTP 503, not allowed.
5. Consent is recorded as `ConsentRecord` with `tenant_id`, `subject_id_hash` (HMAC-SHA256),
   `channel`, `purpose`, `status`, `version`, and `expiry`.

---

## Alternatives Considered

### A1 — Keep consent as a boolean field per service
**Rejected.** Provides no audit trail, no versioning, no right-to-erasure path. Does not satisfy
Kenya DPA 2019 §35(c) or §61. Creates cross-service inconsistency: FORD, Engage, and Admissions
would each need separate erasure logic.

### A2 — Store consent in the existing PostgreSQL tables with RLS
**Rejected.** Would require each service to implement consent logic independently. Central audit
trail still impossible without a dedicated service. Right-to-erasure cascade across 3+ schemas is
operationally error-prone.

### A3 — Use a third-party consent management platform (e.g., OneTrust, Didomi)
**Rejected** for Phase 2. Introduces SaaS dependency, adds cost, and breaks data residency
requirement (Kenya-resident data must stay on cluster). Deferred to Phase 4 re-evaluation.

### A4 — Deploy consent service fail-open (allow dispatch if consent service unavailable)
**Rejected.** Fail-open violates Kenya DPA 2019 §25 (requires lawful basis to exist before
processing). If consent cannot be confirmed, dispatch must not occur. A 503 to the user is
acceptable; an unconfirmed PII dispatch is not.

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| Availability | Redis-backed circuit-breaker ensures a consent service blip does not degrade the entire platform — it only blocks new dispatches until the circuit resets |
| Performance | Redis consent-check cache with 5-minute TTL reduces per-request latency overhead from ~15ms to ~2ms for cached lookups |
| Correctness | Single source of truth for consent state — no more per-service boolean drift |
| Observability | All consent checks, grants, and revocations emit OTel spans tagged with `tenant_id`, `channel`, `purpose`, and `subject_id_hash` |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | `subject_id_hash` MUST be HMAC-SHA256 keyed with `MEMBER_HMAC_SECRET` from OpenBao (HC-6). Raw email or national ID must never appear in the consent table. |
| SEC-2 | The `DELETE /consent/{hash}` erasure endpoint requires `Authorization: Bearer` with a Keycloak role of `consent:admin` — it is not publicly callable. |
| SEC-3 | Consent audit log is append-only (no UPDATE/DELETE on `consent_audit`). Enforced via PostgreSQL table-level privilege: the consent service role has INSERT + SELECT only on `consent_audit`. |
| SEC-4 | The consent service is cluster-internal only (ClusterIP, no NodePort/LoadBalancer). External access is via Kong API Gateway with JWT validation. |

---

## Multi-Tenancy Implications

- `consent_records.tenant_id UUID NOT NULL` — HC-4 compliant.
- PostgreSQL Row-Level Security policy enforces `tenant_id = current_setting('app.tenant_id')` on all reads and writes.
- A data subject's consent hash for tenant A is invisible to queries running in tenant B context.
- The `GET /consent/{hash}?channel=&purpose=` query sets `app.tenant_id` from the caller's JWT before executing.

---

## Agent-Autonomy Implications

- HC-5: No agent may dispatch customer-facing PII without first receiving `{ allowed: true }` from the
  consent service via the MCP gateway. The MCP tool spec for `kafka.produce` (Tier 2) and
  `brevo.send` (Tier 2) will gate on consent check as a precondition — this is enforced in the
  MCP gateway tool handler, not in agent code.
- HC-3: Agents remain at L1 autonomy; the consent gate is an automated policy enforcement point,
  not an agent decision.

---

## Data Implications

### DDL (from STEP-P2-02 execution plan)

```sql
CREATE TABLE consent_records (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  subject_id_hash TEXT NOT NULL,  -- HMAC-SHA256(national_id or email, MEMBER_HMAC_SECRET)
  channel         TEXT NOT NULL,  -- email | sms | whatsapp | voice | ussd
  purpose         TEXT NOT NULL,  -- marketing | otp | enrollment | survey | voter_registration
  status          TEXT NOT NULL,  -- granted | revoked | expired
  recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  source          TEXT,           -- registration_form | api | ussd | keycloak_consent_screen
  expiry          TIMESTAMPTZ,
  version         INT NOT NULL DEFAULT 1
);

CREATE TABLE consent_audit (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consent_id  UUID REFERENCES consent_records(id),
  tenant_id   UUID NOT NULL,
  event_type  TEXT NOT NULL,  -- granted | revoked | checked | erased
  actor       TEXT,
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata    JSONB
);

ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE consent_audit   ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON consent_records
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
CREATE POLICY tenant_isolation ON consent_audit
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

### Default-Deny
A `GET /consent/{hash}?channel=sms&purpose=otp` for an unknown hash returns `{ "allowed": false }`.
No exception, no 404 — silence equals denial. This is the correct interpretation of Kenya DPA 2019
§25 (no consent = no lawful basis = no processing).

---

## Event Implications

The consent service does **not** produce Kafka events in Phase 2. Consent state changes are
synchronous HTTP and persist to PostgreSQL + audit table only.

Phase 3 deferred item: emit `com.i3.consent.granted` / `com.i3.consent.revoked` CloudEvents to
`consent-events` topic with full HC-4 `tenant_id` in the CloudEvent envelope.

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| Circuit-breaker state visibility | Circuit state (open/half-open/closed) exposed via `/health/circuit` endpoint; Prometheus metric `consent_circuit_state` (0=closed, 1=open) |
| Consent service downtime | Circuit-breaker prevents dispatch cascade; alert `ConsentServiceDown` fires after 60s (Severity: Critical) |
| Right-to-erasure SLA | `DELETE /consent/{hash}` queues erasure job; job must complete within 72h per Kenya DPA 2019 §35(c); job status tracked in `consent_audit` |
| Migration from boolean consent | Phase 2 adapter: on first FORD registration with `consent=True`, a `POST /consent` is called transparently. The legacy `consent` boolean field is removed in Phase 3. |

---

## Performance Implications

| Scenario | Latency Impact |
|---------|----------------|
| Cache HIT (Redis, 5-min TTL) | +2ms per dispatch |
| Cache MISS (DB lookup) | +15ms per dispatch |
| Circuit OPEN (consent service down) | 0ms — returns immediately from breaker state |
| Consent POST (new grant) | ~10ms DB write |

Engage campaign send (batch) pre-fetches consent for all recipients before dispatch loop — O(1)
Redis lookup per recipient after first cache warm.

---

## Cost Implications

- Consent service: 1 replica, 256Mi / 250m CPU — negligible on existing cluster.
- PostgreSQL storage: `consent_records` estimated at 1,000 rows/day → ~50MB/year.
- Redis consent cache: 5-min TTL keys, ~200 bytes per entry → < 10MB steady state.

---

## Rollback Strategy

1. **Feature flag**: `CONSENT_CHECK_ENABLED=false` in each consuming service. When false, services
   bypass the consent check (legacy behaviour). This flag is a **temporary escape hatch only** —
   it must be removed after Phase 2 is stable. Leaving it enabled in production is a HC-7-class
   violation.
2. **Database rollback**: consent tables can be dropped without affecting any other service.
   Consent records are additive data only.
3. **Circuit-breaker manual override**: `redis.set("consent:circuit:override", "closed", EX=3600)`
   forces circuit closed for up to 1 hour while root cause is investigated.

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to `solution-01` through `solution-08` namespaces. |
| HC-2 | `voter_registration` is a valid `purpose` value in `consent_records`. FORD voter consent is stored and audited, supporting IEBC statutory compliance before March 2027. |
| HC-3 | Consent gate is policy enforcement, not agent decision. Agents remain L1. |
| HC-4 | `tenant_id UUID NOT NULL` on `consent_records` and `consent_audit`. RLS enforced. |
| HC-5 | Agents do not call the consent service directly — consent check is a precondition enforced by the MCP gateway for Tier-2+ tools. |
| HC-6 | `subject_id_hash` must be HMAC-SHA256 with `MEMBER_HMAC_SECRET`. Raw national_id and email must never appear in this column. |
| HC-7 | `CONSENT_CHECK_ENABLED` flag must never ship as `false` to production. |
| HC-8 | Voter registration consent (`purpose=voter_registration`) is stored in the consent service (identity layer), not in the Fabric `ballotPrivate` collection (ballot layer). Architecturally separate per HC-8. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §25 — lawful basis | Consent record required before any PII dispatch |
| Kenya DPA 2019 §26 — informed consent | `version` field tracks which privacy notice version was accepted |
| Kenya DPA 2019 §35(c) — right to withdraw | `DELETE /consent/{hash}` + 72h erasure job |
| Kenya DPA 2019 §61 — ODPC penalties | Audit trail in `consent_audit` is evidence of compliance |
| IEBC Act Cap. 7A s.44 — voter data purpose limitation | `purpose=voter_registration` channel=`ussd` is the only valid consent for FORD |
| ODPC Registration | Platform must register as a data controller; consent records are the primary evidence |

---

## Acceptance Criteria

```
AC-1: kubectl get pod -n i3-consent -l app=consent-service → Running
AC-2: POST /consent with valid payload → 201 { consent_id, recorded_at }
AC-3: GET  /consent/{unknown_hash}?channel=sms&purpose=otp → { "allowed": false }
AC-4: GET  /consent/{known_granted_hash}?channel=sms&purpose=otp → { "allowed": true }
AC-5: Engage send route calls consent service before Brevo dispatch (grep "consent" campaigns/send/route.ts → match)
AC-6: FORD API calls consent service before OTP dispatch
AC-7: Admissions Agent calls consent service before PII appears in LLM context
AC-8: Circuit-breaker opens after 3 consecutive consent service failures; 4th dispatch returns 503
AC-9: Circuit-breaker resets (half-open) after 30 seconds
AC-10: Prometheus metric consent_circuit_state present; alert ConsentServiceDown defined
AC-11: DELETE /consent/{hash} → 200 { erasure_job_id, status: "queued" }
AC-12: consent_audit table contains row for every grant, check, and revocation
AC-13: subject_id_hash column contains no raw email addresses or national_id values
AC-14: P2-GATE-01 sensor passes: consent service pod Running; all 3 consumers check consent
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
