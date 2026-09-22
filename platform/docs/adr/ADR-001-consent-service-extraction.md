# ADR-001: Consent Service Extraction

**Status:** Accepted  
**Date:** 2025-01-01  
**Author:** i3 Technologies Platform Team  
**Step Reference:** STEP-P2-02 (i3-platform-atomic-execution-plan.md)  
**Replaces:** Inline `consent: bool` field in FORD MemberRegister model

---

## Context

Prior to Phase 2, consent was a bare `bool` field (`consent: bool = False`) on the
FORD `MemberRegister` Pydantic model. The same flag was reused across three separate
services — FORD, Engage campaign dispatch, and SIT (Societal Impact Tracker). This
design has the following deficiencies:

1. **No auditability.** There is no record of *when* consent was given, by which channel, or
   through which source system.
2. **No channel specificity.** A single flag cannot express that a subject consents to SMS-OTP
   but not marketing email.
3. **No revocation pathway.** There is no mechanism for a subject to exercise the right-to-
   erasure under the Kenya Data Protection Act 2019.
4. **No tenant isolation.** The boolean is not scoped to a tenant, violating HC-4.
5. **Replication of consent state.** Every consuming service independently duplicates the
   concept, making audits and revocations error-prone.

The Kenya Data Protection Act 2019, §25–28, requires that consent be:
- Freely given, specific, informed, and unambiguous
- Recorded and auditable on request by the data subject
- Revocable at any time with effect applied within 72 hours

---

## Decision

Extract consent into a **dedicated `consent-service`** FastAPI microservice deployed in the
`i3-consent` namespace. The service owns two tables, `consent_records` and `consent_audit`,
both protected by PostgreSQL Row-Level Security (RLS) keyed on `tenant_id`.

All services that previously read or wrote the boolean consent flag now call the consent-service
HTTP API instead.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         i3-consent namespace                        │
│                                                                      │
│   ┌───────────────────────────────────┐                             │
│   │         consent-service            │                             │
│   │  POST   /consent                   │  ← FORD /register           │
│   │  GET    /consent/{hash}            │  ← Engage /campaigns/send   │
│   │  DELETE /consent/{hash}            │  ← GDPR right-to-erasure    │
│   │  GET    /consent/{hash}/audit      │  ← Compliance officer UI    │
│   └───────────────┬───────────────────┘                             │
│                   │ asyncpg pool                                     │
│   ┌───────────────▼───────────────────┐                             │
│   │       consent_db (Postgres)        │                             │
│   │  consent_records  (RLS)            │                             │
│   │  consent_audit    (RLS)            │                             │
│   └───────────────────────────────────┘                             │
└────────────────────────────────────────────────────────────────────┘

        FORD /register                 Engage /campaigns/send
   ┌────────────────────┐         ┌──────────────────────────────┐
   │ 1. req.consent=True│         │ 1. For each contact           │
   │ 2. _ensure_consent │──GET──► │ 2. checkEmailConsent(hash)    │
   │    (Phase 2 adapter│         │ 3. Skip if !allowed           │
   │    auto-records)   │         │ 4. Send if allowed            │
   └────────────────────┘         └──────────────────────────────┘
```

### Data Model

| Table | Primary Key | Tenant Isolation | Purpose |
|---|---|---|---|
| `consent_records` | `UUID` (gen_random_uuid) | RLS on `tenant_id` | Immutable append-only ledger |
| `consent_audit` | `UUID` (gen_random_uuid) | RLS on `tenant_id` | Every grant/revoke/check/erase |

**Hard constraints honoured:**
- HC-4: `tenant_id UUID NOT NULL` on every row in both tables
- HC-6: `subject_id_hash` is always HMAC-SHA256 of the raw identifier; never raw PII
- HC-8: Consent check is architecturally separate from ballot identity (different namespaces and DBs)

---

## HTTP Contract

```
POST   /consent
  Body: ConsentCreate (subject_id_hash, channel, purpose, status, source, expiry?, version, tenant_id)
  → 201 { consent_id: UUID, recorded_at: ISO8601 }

GET    /consent/{subject_id_hash}?channel={}&purpose={}&tenant_id={}
  → 200 { allowed: bool, recorded_at?: ISO8601, expiry?: ISO8601 }
  → Default-deny: returns { allowed: false } when no active record exists

DELETE /consent/{subject_id_hash}
  Body: ConsentErasureRequest (reason, requested_by, tenant_id)
  → 200 { erasure_job_id: UUID, status: "queued" }

GET    /consent/{subject_id_hash}/audit?tenant_id={}
  → 200 { events: ConsentAuditEvent[] }
```

---

## Backward-Compatibility Strategy

The boolean `consent: bool` field in `MemberRegister` is **retained** during Phase 2.
A transition adapter in `_ensure_consent()` translates `consent=True` into an automatic
`POST /consent` with `status=granted` on first use, if no existing consent record is found.

The field is removed in **Phase 3** cleanup (STEP-P3-xx) after all callers have migrated to
explicit consent record creation.

---

## Consequences

### Positive

- Single source of truth for all consent state across FORD, Engage, and SIT
- Full audit trail satisfies DPA 2019 §§25–28 requirements
- Channel/purpose granularity: a subject can consent to OTP but opt out of marketing
- Right-to-erasure (DELETE) is a first-class operation with job-ID tracking
- RLS enforces tenant isolation at the database level — not just application code

### Negative / Trade-offs

- **Latency:** Every registration and every campaign contact dispatch now makes an HTTP call to
  consent-service. Mitigated by: in-cluster DNS (< 2ms RTT), asyncpg connection pool, and
  Redis-backed response caching (Phase 2 enhancement).
- **New SPOF:** If consent-service is unavailable, registrations are rejected. Mitigated by:
  fail-open boolean adapter during Phase 2 transition + readiness probe on the deployment.
- **Schema migration required:** `contacts` table in `engage_db` needs a `subject_id_hash TEXT`
  column to hold pre-computed HMAC values. A TODO marker is left in `route.ts` until the Phase 2
  migration is applied.

---

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Postgres trigger that populates `consent_records` from the boolean flag | Does not provide an HTTP API; blocks Phase 3 multi-service access; no channel specificity |
| Shared consent table in `engage_db` | Violates bounded-context principle; FORD and SIT cannot access engage_db without cross-namespace coupling |
| Event-sourced consent via Kafka | Adds Kafka dependency to the consent read path; consent checks must be synchronous to block dispatch |

---

## Compliance Mapping

| Requirement | Reference |
|---|---|
| Data Protection Act 2019 §25–28 | Consent must be freely given, specific, informed, and unambiguous. The consent-service ledger provides the immutable record. |
| Enhancement 3 Guide — E³ Principle P9 | Consent-first data flows: no PII dispatch without a verified consent record. |
| HC-6 (Hard Constraint) | Kenyan National IDs and phone numbers use keyed HMAC-SHA256 (`MEMBER_HMAC_SECRET`); `subject_id_hash` stores the hash, never raw PII. |
| HC-4 (Hard Constraint) | `consent_records` and `consent_audit` both carry `tenant_id UUID NOT NULL` with RLS policies. |
| i3-platform-atomic-execution-plan.md | STEP-P2-02 |

## References

- Kenya Data Protection Act 2019, §25–28 (consent requirements)
- i3-platform-atomic-execution-plan.md, STEP-P2-02
- 02-architecture-standards.md (asyncpg pool, Pydantic validation, HC-4 tenant enforcement)
- 01-hard-constraints.md (HC-4, HC-6, HC-8)
