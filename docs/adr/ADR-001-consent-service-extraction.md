# ADR-001: Consent Service Extraction

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** Backend Domain Lead, Data Platform Lead, Engineering Manager  

---

## Context

Consent enforcement for personal data processing is scattered across at least three call sites:
`platform/ford/api/main.py` (boolean `consent` field on `MemberRegister`),
`platform/engage/web/src/app/api/campaigns/send/route.ts` (no check before email dispatch), and
`platform/sit/api/main.py` (inline enrollment without purpose-scoped consent).  
This creates DPA 2019 compliance risk: purpose limitation, right-to-erasure, and audit trail are
unenforceable when consent state is stored as a boolean column with no audit history.

The Enhancement 3 PMC guide §5 mandates a central Consent Policy Service.

---

## Decision

Extract all consent state, purpose mapping, and erasure logic into a dedicated `consent-service`
FastAPI microservice deployed in the `i3-consent` namespace.  
All services that touch personal data MUST call `GET /consent/{subject_id_hash}` before dispatching
any PII-carrying message.  The default response is `{"allowed": false}` (deny by default).  
`subject_id_hash` MUST be HMAC-SHA256 of the identifier keyed with `MEMBER_HMAC_SECRET` from
OpenBao (HC-6).  Raw NIDs, phone numbers, or email addresses are never accepted.

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| Boolean `consent` column per service | No purpose scoping; no audit; duplicated schema drift |
| Shared PostgreSQL consent table (no service boundary) | Schema coupling; no rate-limit; no cache layer |
| Consent embedded in Keycloak user attributes | OIDC attribute not suited for per-channel purpose tracking; no erasure |

---

## Consequences

**Positive:**
- Single source of truth for consent across all domains.
- Append-only `consent_audit` table satisfies DPA 2019 Article 7 record-keeping requirement.
- Default-deny gate prevents accidental PII dispatch before consent is recorded.
- Redis TTL cache (300 s) keeps p99 consent check latency ≤ 10 ms.

**Negative:**
- Adds a synchronous dependency for every PII-touching operation; mitigated by circuit-breaker
  (default to deny on service timeout, so no silent data leak).
- Requires a migration adapter to translate legacy `consent: true` into a consent record during
  Phase 2 transition; adapter removed in Phase 3.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-4 | `tenant_id UUID NOT NULL` on `consent_records` and `consent_audit`; RLS policy enforced |
| HC-6 | `subject_id_hash` is HMAC-SHA256; raw identifier is never stored or transmitted |
| HC-5 | Agents call consent gate via MCP `consent_gate_check` tool — never directly |
| DPA 2019 (Kenya) | Purpose-scoped consent, timestamped audit trail, erasure queue satisfy Articles 30 & 34 |
| E³ P12 | Privacy as a design input — consent is a hard gate, not an advisory check |

---

## Sensor Gate (P2-GATE-01)

```bash
kubectl get pod -n i3-consent -l app=consent-service   # Running
curl -s -X POST http://consent-service.i3-consent.svc/consent \
  -d '{"subject_id_hash":"<64-char-hex>","channel":"sms","purpose":"otp",
       "status":"granted","source":"test",
       "tenant_id":"00000000-0000-0000-0000-000000000001","version":1}'
# Expected: HTTP 201
curl -s "http://consent-service.i3-consent.svc/consent/unknown?channel=sms&purpose=otp"
# Expected: {"allowed": false}
grep -n "consent" platform/engage/web/src/app/api/campaigns/send/route.ts
# Expected: ≥ 1 match
```
