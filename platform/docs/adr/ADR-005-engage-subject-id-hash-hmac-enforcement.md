# ADR-005: Engage `subject_id_hash` HMAC-SHA256 Enforcement

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, Security Lead, Data Protection Officer  
**Relates to:** EXPLORE-GATE §4 (SEC-07), §13 Track D (D-3), HC-6  
**Supersedes:** — (no prior ADR; hash was a TODO comment)

---

## Context

### Problem Statement

The Engage platform dispatches email and SMS campaigns to i3 customers. Each dispatch record
in the Engage database stores a `subject_id_hash` column, intended to hold a pseudonymised
identifier for the message recipient — enabling consent lookups, opt-out processing, and audit
without storing raw PII.

EXPLORE-GATE §4 (SEC-07, Severity: Medium) found:

> **`subject_id_hash` falls back to raw email** (TODO in `campaigns/send/route.ts`) — HC-6 risk.

Inspection of [`platform/engage/web/src/app/api/campaigns/send/route.ts`](platform/engage/web/src/app/api/campaigns/send/route.ts) reveals a code path where, if the HMAC computation fails or the secret is absent, the raw email address is used as the `subject_id_hash` value. This is a direct HC-6 violation:

> **HC-6**: Kenyan National IDs and phone numbers MUST use keyed HMAC-SHA256 (`MEMBER_HMAC_SECRET` in OpenBao), never raw SHA-256 or plaintext.

The same risk extends to the contacts route (`/api/contacts/route.ts`) which also stores
contact identifiers.

Consequences of the current state:
1. Raw email addresses visible in `subject_id_hash` column break pseudonymisation.
2. The consent service lookup (ADR-001) passes `subject_id_hash` to `GET /consent/{hash}` —
   if the hash is actually a raw email, the consent service table is polluted with PII in a
   column intended for pseudonyms.
3. If the `engage_db` is compromised, raw email addresses are directly exposed from the hash
   column — defeating the purpose of pseudonymisation entirely.
4. Keyed HMAC (HC-6) means the hash is only re-derivable by someone with the `MEMBER_HMAC_SECRET`
   key; raw SHA-256 or raw email provides zero key-based protection.

---

## Decision

**Enforce HMAC-SHA256 keyed with `MEMBER_HMAC_SECRET` (from OpenBao) for all
`subject_id_hash` derivations in the Engage platform. Remove the raw-email fallback entirely.**

Specifically:

### 1. Remove the raw-email fallback
The code path `subject_id_hash = email` (or any non-HMAC path) is deleted. If `MEMBER_HMAC_SECRET`
is not available at startup, the service fails its liveness probe rather than silently degrading.

### 2. Enforce HMAC at the source
```typescript
// platform/engage/web/src/lib/hash.ts  (new utility module)
import { createHmac } from "crypto";

/**
 * Derives a pseudonymous subject identifier.
 * HC-6: keyed HMAC-SHA256 — never raw SHA-256 or plaintext.
 * @param value  - raw identifier (email address or E.164 phone number)
 * @param secret - MEMBER_HMAC_SECRET from OpenBao (injected via env at startup)
 * @returns hex digest string (64 characters)
 */
export function hmacSubjectId(value: string, secret: string): string {
  if (!secret || secret.length < 32) {
    throw new Error("MEMBER_HMAC_SECRET missing or too short — cannot derive subject_id_hash");
  }
  return createHmac("sha256", secret).update(value.toLowerCase().trim()).digest("hex");
}
```

### 3. Startup secret validation
```typescript
// platform/engage/web/src/lib/secrets.ts
const MEMBER_HMAC_SECRET = process.env.MEMBER_HMAC_SECRET;
if (!MEMBER_HMAC_SECRET || MEMBER_HMAC_SECRET.length < 32) {
  console.error("FATAL: MEMBER_HMAC_SECRET not set or too short. Service cannot start.");
  process.exit(1);  // fail fast — do not start without HMAC key
}
export { MEMBER_HMAC_SECRET };
```

### 4. Apply to all `subject_id_hash` call sites
- [`platform/engage/web/src/app/api/campaigns/send/route.ts`](platform/engage/web/src/app/api/campaigns/send/route.ts)
- [`platform/engage/web/src/app/api/contacts/route.ts`](platform/engage/web/src/app/api/contacts/route.ts)
- Engage Kafka consumer (`kafka_consumers.py`): Python equivalent using `hmac.new(..., hashlib.sha256)`

### 5. Python producer/consumer equivalent
```python
# platform/engage/consumers/kafka_consumers.py and producers
import hmac, hashlib, os

def hmac_subject_id(value: str) -> str:
    secret = os.environ["MEMBER_HMAC_SECRET"]
    if len(secret) < 32:
        raise RuntimeError("MEMBER_HMAC_SECRET too short")
    return hmac.new(
        secret.encode(),
        value.lower().strip().encode(),
        hashlib.sha256
    ).hexdigest()
```

### 6. Backfill Strategy
Existing rows in `engage_db` where `subject_id_hash` appears to be a raw email (contains `@`) must
be backfilled via a one-time migration:

```sql
-- Identify affected rows (raw emails in hash column)
SELECT id, subject_id_hash FROM contacts WHERE subject_id_hash LIKE '%@%';
```

A migration script (`platform/engage/migrations/003_backfill_hmac.py`) will:
1. Read each raw-email hash value.
2. Derive `hmac_subject_id(raw_email)`.
3. Update the row.
4. Delete the raw email from the hash column.

The migration runs as a one-off Kubernetes Job before the application code change is deployed.

---

## Alternatives Considered

### A1 — Keep raw SHA-256 (no HMAC key)
**Rejected.** HC-6 explicitly forbids unkeyed SHA-256. A rainbow table attack can reverse common
email addresses from SHA-256 hashes in seconds. HMAC with a 256-bit key makes pre-image attacks
computationally infeasible.

### A2 — Use a symmetric encryption scheme (AES) instead of HMAC
**Rejected.** HMAC is the correct primitive for pseudonymisation: it is one-way (deterministic
but non-reversible without the key) and produces a fixed-length token. AES encryption would
produce a reversible ciphertext — consent lookups need deterministic matching, not reversibility.

### A3 — Use argon2 or bcrypt
**Rejected** for this use case. Argon2/bcrypt are designed for password hashing — they are
deliberately slow and non-deterministic (random salt). `subject_id_hash` must be **deterministic**
(same email → same hash) to allow consent lookups across services. HMAC-SHA256 is the correct
choice for deterministic pseudonymisation.

### A4 — Rotate the HMAC key on a schedule
**Deferred to Phase 4.** Key rotation requires a coordinated backfill across all services that
store `subject_id_hash` values. The consent service, Engage, and FORD all use the same derived
hash as a cross-service join key — rotation requires an atomic double-write window. This is an
advanced operational concern not required for Phase 2 compliance.

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| HC-6 compliance | Keyed HMAC-SHA256 is the mandated primitive — no exceptions |
| Consent service join key | `subject_id_hash` is the cross-service pseudonymous join key between Engage, FORD, Consent Service, and the admissions pipeline |
| Fail-fast startup | Service refuses to start without the HMAC key — prevents silent fallback to PII exposure |
| Determinism | Same input + same key → same hash, always. Required for consent lookup correctness. |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | `MEMBER_HMAC_SECRET` must be a minimum 256-bit (32-byte) random value stored in OpenBao at `i3/engage/hmac-secret`. It must never be committed to git or stored in Kubernetes Secrets directly. |
| SEC-2 | The `subject_id_hash` column must contain **only** 64-character hex strings after migration. A `CHECK (LENGTH(subject_id_hash) = 64 AND subject_id_hash ~ '^[0-9a-f]+$')` constraint is added to the table after backfill. |
| SEC-3 | Input normalisation: email addresses are lowercased and trimmed before HMAC to ensure the same identity produces the same hash regardless of case/whitespace variations. |
| SEC-4 | The HMAC function is not exposed via any API endpoint. `subject_id_hash` values are never returned to end-users or logged. |
| SEC-5 | If the Engage database is compromised, `subject_id_hash` values cannot be reversed to email addresses without `MEMBER_HMAC_SECRET` — which lives in OpenBao, not in the database. |

---

## Multi-Tenancy Implications

- `MEMBER_HMAC_SECRET` is a **platform-level** shared secret (same key across all tenants). This
  is an intentional design choice — the consent service uses `subject_id_hash` as a cross-tenant
  join key (e.g., a FORD voter who is also an Engage contact should have the same hash in both
  systems, enabling consent portability).
- If per-tenant HMAC keys are required in the future (to prevent cross-tenant hash correlation),
  this is a Phase 4 decision requiring consent service schema evolution.

---

## Agent-Autonomy Implications

- HC-6: The Campaign Agent (ADR-002) receives contact information as part of its input payload.
  The agent must never log or emit raw email/phone values. The MCP gateway enforces that any
  data flowing through `kafka.produce` is pre-hashed before emission.
- HC-3: No autonomy level change.

---

## Data Implications

### Database Constraint Addition (Post-Backfill)

```sql
-- platform/engage/web/migrations/004_enforce_hash_constraint.sql
ALTER TABLE contacts
  ADD CONSTRAINT chk_subject_id_hash_format
  CHECK (LENGTH(subject_id_hash) = 64 AND subject_id_hash ~ '^[0-9a-f]+$');

ALTER TABLE email_campaigns
  ADD CONSTRAINT chk_subject_id_hash_format
  CHECK (LENGTH(subject_id_hash) = 64 AND subject_id_hash ~ '^[0-9a-f]+$');
```

### Backfill Job Contract

```python
# platform/engage/migrations/003_backfill_hmac.py
# Inputs: ENGAGE_DB_URL, MEMBER_HMAC_SECRET from environment
# Output: Updates all rows where subject_id_hash contains '@'
# Idempotent: rows already in HMAC format (64-char hex) are skipped
# Estimated runtime: < 5 minutes for current contact volume
# Must run BEFORE application code change is deployed
```

---

## Event Implications

- Kafka `engage.email-events` and `engage.sms-events` messages contain `to_email` / `to_phone`
  in plaintext within `data` (required for Brevo API dispatch). These fields are **not** hashed.
  The `subject_id_hash` is a separate field used only for consent lookups and audit — not for
  message delivery.
- After this change, the Engage consumer sets `subject_id_hash = hmac_subject_id(to_email)` on
  every send record written to PostgreSQL.

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| Secret availability at startup | If OpenBao is unavailable at pod start, the service fails fast (exit 1). Kubernetes restarts the pod. OpenBao HA (3-pod) ensures < 30-second recovery. |
| Backfill timing | Backfill Job runs before application deploy. If backfill fails, the application deploy is blocked (pipeline gate). |
| Cross-service consistency | FORD API uses the same `MEMBER_HMAC_SECRET` for `member_token` derivation. Consent service uses the same hash for lookups. All three must share the same secret at the same time. |
| Emergency secret rotation | Key rotation requires a coordinated double-write window (Phase 4). Until then, `MEMBER_HMAC_SECRET` is treated as a long-lived platform secret. |

---

## Performance Implications

- HMAC-SHA256 computation: ~1 microsecond per call. Negligible at any expected throughput.
- Startup validation: executed once at pod start. No per-request overhead.

---

## Cost Implications

- Zero additional infrastructure cost.
- One-time developer effort: migration script, utility module, and 3 call-site updates.

---

## Rollback Strategy

1. **If backfill fails**: Deployment is blocked at the pipeline gate. No application code change
   has been deployed. Raw-email state is preserved.
2. **If application fails after deploy**: Revert the application code via ArgoCD rollback.
   The database constraint (step 4) can be dropped: `ALTER TABLE contacts DROP CONSTRAINT chk_subject_id_hash_format;`
3. **There is no rollback for the HMAC key**: Once `MEMBER_HMAC_SECRET` is set, changing it
   invalidates all existing hashes. The key is treated as immutable until Phase 4 key rotation
   is planned.

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to solution-01 through solution-08 namespaces. |
| HC-2 | Not directly applicable to IEBC timeline. |
| HC-3 | No autonomy tier change. |
| HC-4 | `subject_id_hash` is indexed by `tenant_id` — consent lookups always scoped to tenant. |
| HC-5 | MCP gateway enforces that agent Kafka produce calls pre-hash identifiers. |
| HC-6 | **This ADR's primary purpose.** `subject_id_hash` = HMAC-SHA256(`MEMBER_HMAC_SECRET`, email). No raw email. No unkeyed SHA-256. |
| HC-7 | `MEMBER_HMAC_SECRET` must never have a fallback value that bypasses the check. `process.exit(1)` on missing secret is the explicit anti-bypass control. |
| HC-8 | Not applicable. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §25 — lawful basis | Pseudonymisation via HMAC ensures only the consent service can re-link hash to identity |
| Kenya DPA 2019 §29 — pseudonymisation | HMAC-SHA256 with OpenBao-managed key satisfies pseudonymisation requirements |
| Kenya DPA 2019 §61 — ODPC penalties | Demonstrates active technical control against PII exposure in the database |
| GDPR Article 25 (by analogy) — privacy by design | HMAC enforced at the earliest possible point (before DB write, not after) |

---

## Acceptance Criteria

```
AC-1: hmacSubjectId() utility exists in platform/engage/web/src/lib/hash.ts
AC-2: Raw-email fallback path removed from campaigns/send/route.ts (grep for "subject_id_hash = email" → zero matches)
AC-3: Service refuses to start if MEMBER_HMAC_SECRET absent or < 32 chars (integration test)
AC-4: subject_id_hash values in DB are all 64-char lowercase hex strings after backfill
AC-5: DB constraint chk_subject_id_hash_format present on contacts and email_campaigns tables
AC-6: Python kafka_consumers.py uses hmac.new() for subject_id_hash derivation
AC-7: grep -rn "sha256.*email\|hashlib.sha256" platform/engage/ → zero matches (unkeyed SHA-256 gone)
AC-8: Consent service GET /consent/{hash} returns correct result using HMAC-derived hash
AC-9: MEMBER_HMAC_SECRET injected from OpenBao i3/engage/hmac-secret, not Kubernetes Secret literal
AC-10: Cross-service parity: FORD member_token derived with same MEMBER_HMAC_SECRET as Engage subject_id_hash
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
