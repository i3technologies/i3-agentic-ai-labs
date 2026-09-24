# ADR-004: Tenant Isolation Strategy

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** Data Platform Lead, Backend Domain Lead, Engineering Manager  

---

## Context

The `engage_db`, `pmaas_db`, and `ford_db` PostgreSQL databases do not have `tenant_id` on their
core domain tables.  `email_campaigns`, `contacts`, `contact_lists`, `campaigns`, `voters`,
`ward_targets`, `members_pii`, and `agent_velocity` are all single-tenant by accident — they were
built for a single customer and never instrumented for multi-tenancy.

E³ Principle P7 ("Multi-tenant from line one") and HC-4 (`tenant_id UUID NOT NULL` on every row,
event, and log line) require remediation before Phase 3 can add new paying tenants.

---

## Decision

Apply zero-downtime `ALTER TABLE … ADD COLUMN tenant_id UUID` migrations across all affected
tables in `engage_db`, `pmaas_db`, and `ford_db`.  Migration procedure:

1. ADD COLUMN (nullable)  
2. Backfill existing rows with the default production tenant UUID  
   `00000000-0000-0000-0000-000000000001`  
3. ALTER COLUMN SET NOT NULL  
4. Enable Row-Level Security  
5. Create `tenant_isolation` RLS policy using `current_setting('app.tenant_id')::UUID`  
6. Add composite index on `(tenant_id, created_at DESC)` for query performance  

All API route handlers must extract `tenant_id` from the Keycloak JWT claim and set
`SET app.tenant_id = $1` before every query.

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| Separate database per tenant | Operational overhead; connection pool explosion; Crunchy operator not configured for N-tenant DBs |
| Schema-per-tenant | PostgreSQL schema switching is not supported by Crunchy connection pooler without custom pooler config |
| Application-level filtering (WHERE tenant_id = ?) only | RLS provides a database-enforced guarantee; application filtering alone is a defence-in-depth gap |

---

## Consequences

**Positive:**
- RLS provides a database-enforced tenant boundary — even a buggy query cannot leak cross-tenant
  data without explicitly setting `app.tenant_id`.
- Zero-downtime migration procedure (ADD COLUMN → backfill → NOT NULL) is safe for production.
- Composite `(tenant_id, created_at DESC)` index prevents full-table scans on tenant-filtered
  queries.

**Negative:**
- All route handlers must be updated to pass `tenant_id` from JWT — 12+ files across Engage,
  PMaaS, and FORD.
- RLS requires `SET app.tenant_id` before every connection checkout; missing this causes a query
  to return zero rows (safe fail) rather than all rows (data leak), which is the correct
  failure mode.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-4 | `tenant_id UUID NOT NULL` added to every affected table; RLS enforces isolation at DB layer |
| E³ P7 | Multi-tenant from line one — all new Phase 2 tables are created with `tenant_id UUID NOT NULL` from day one |
| DPA 2019 (Kenya) | Tenant isolation prevents accidental cross-organisation data disclosure |

---

## Sensor Gate (P2-GATE-04)

```bash
psql $ENGAGE_DB_URL -c "\d email_campaigns" | grep tenant_id
# Expected: tenant_id | uuid | not null
psql $ENGAGE_DB_URL -c "SELECT relrowsecurity FROM pg_class WHERE relname='email_campaigns';"
# Expected: t
# Cross-tenant leakage test:
# SET app.tenant_id = '<tenant-A>'; INSERT INTO contacts(…) VALUES(…);
# SET app.tenant_id = '<tenant-B>'; SELECT * FROM contacts;
# Expected: 0 rows returned for tenant-B
```
