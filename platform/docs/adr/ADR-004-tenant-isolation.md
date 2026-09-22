# ADR-004: Tenant Isolation via tenant_id UUID NOT NULL + PostgreSQL RLS

**Status:** Accepted  
**Date:** 2025-07-17  
**Author:** i3 Technologies Platform Team  
**Step Reference:** STEP-P2-05 (i3-platform-atomic-execution-plan.md)  
**Replaces:** No prior decision record; tables were single-tenant with no row-level isolation.

---

## Context

Prior to STEP-P2-05, the three primary domain databases — `engage_db`, `pmaas_db`, and
`ford_db` — had no row-level tenant partitioning. All tables were shared across any application
user with schema access, with no enforcement mechanism preventing cross-tenant data access at
the database layer.

This state violated Hard Constraint HC-4:

> **HC-4:** `tenant_id UUID NOT NULL` across every SQL DDL, RLS policy, Kafka CloudEvent
> envelope, and application query.

The specific gaps were:

| Database | Tables Affected | Gap |
|---|---|---|
| `engage_db` | `email_campaigns`, `contacts`, `contact_lists`, `inbound_messages` | No `tenant_id` column; no RLS |
| `pmaas_db` | `campaigns`, `voters`, `ward_targets` | No `tenant_id` column; no RLS |
| `ford_db` | `members_pii`, `agent_velocity` | No `tenant_id` column; no RLS |

Additionally, FORD's `members_pii` table stores identity tokens — making a cross-tenant data
leak there a potential HC-6 (HMAC anonymisation) compliance failure if a query without a
`WHERE tenant_id = ?` filter were to return rows belonging to a different tenant's members.

---

## Decision

### 1. Safe two-step migration pattern (zero-downtime)

Each migration file follows this exact pattern to avoid constraint failures on existing rows:

```sql
-- Step 1: Add column as nullable (non-blocking DDL)
ALTER TABLE <name> ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- Step 2: Backfill all existing rows to default production tenant
UPDATE <name> SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- Step 3: Enforce NOT NULL only after backfill is complete
ALTER TABLE <name> ALTER COLUMN tenant_id SET NOT NULL;
```

The default backfill UUID `00000000-0000-0000-0000-000000000001` represents the i3 Technologies
production tenant. Future multi-tenant deployments will provision distinct UUIDs per tenant via
Keycloak realm configuration.

### 2. PostgreSQL Row-Level Security on every table

RLS is enabled immediately after the NOT NULL constraint is set:

```sql
ALTER TABLE <name> ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <name>
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

The session variable `app.tenant_id` is set by the application layer before any query:

```typescript
// TypeScript / Next.js route handlers (NextAuth → Keycloak OIDC claim)
const session = await getServerSession(authOptions);
const tenantId: string = session?.user?.tenant_id ?? DEFAULT_TENANT_ID;
await client.query("SET app.tenant_id = $1", [tenantId]);
```

```python
# Python / FastAPI handlers
tenant_id = request.headers.get("X-Tenant-Id") or settings.DEFAULT_TENANT_ID
await conn.execute("SET app.tenant_id = $1", tenant_id)
```

Superusers and roles with `BYPASSRLS` (migration runner only) are implicitly exempt, which is
the standard PostgreSQL behaviour.

### 3. Migration scope

Three migration files are introduced:

| File | Database | Tables |
|---|---|---|
| `platform/engage/web/migrations/002_add_tenant_id.sql` | `engage_db` | `email_campaigns`, `contacts`, `contact_lists`, `inbound_messages` |
| `platform/pmaas/web/migrations/002_add_tenant_id.sql` | `pmaas_db` | `campaigns`, `voters`, `ward_targets` |
| `platform/ford/api/migrations/002_add_tenant_id.sql` | `ford_db` | `members_pii`, `agent_velocity` |

Each migration is idempotent (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`) and wrapped in a `BEGIN / COMMIT` transaction block. A failure
at any step rolls back the entire migration.

### 4. Composite indexes

Each RLS-guarded table gains a `(tenant_id, created_at DESC)` composite index to avoid full
table scans when the planner filters by tenant and orders by recency — the dominant query
pattern in all three applications.

### 5. No application-layer changes in this step

Route handlers (`platform/engage/web/src/app/api/campaigns/route.ts`, etc.) will be updated to
extract `tenant_id` from the JWT and invoke `SET app.tenant_id` in a follow-up task within
STEP-P2-05. The DDL migration is independent and may be applied ahead of the application update
without any regression — RLS silently activates only when `app.tenant_id` is set; connections
that do not set it will receive a Postgres error (`unrecognized configuration parameter
'app.tenant_id'` with `current_setting` strict mode, or an empty result set in lenient mode).

To avoid empty result sets during the transition window, `current_setting('app.tenant_id', true)`
(with the `missing_ok` flag) can be substituted; the migration uses the strict form to enforce
correct application behaviour at query time.

---

## Consequences

### Positive

- **HC-4 compliance**: all nine affected tables now carry `tenant_id UUID NOT NULL`.
- **Database-layer enforcement**: data isolation is enforced by PostgreSQL, not application
  code alone. A misconfigured route handler that forgets to filter by `tenant_id` will receive
  only the rows belonging to the authenticated tenant's session, not all rows.
- **FORD PII protection**: `members_pii` RLS prevents cross-tenant identity token exposure
  even if the application layer is compromised (defence in depth for HC-6).
- **Zero-downtime migration**: the ADD COLUMN → backfill → SET NOT NULL pattern avoids table
  locks on large tables and is safe to run against a live Crunchy Postgres instance.
- **Idempotent DDL**: `IF NOT EXISTS` guards mean re-running the migration file is safe (useful
  for cluster rebuilds and CI seed scripts).

### Negative / Trade-offs

- **`app.tenant_id` must be set before every query**: any connection pool that borrows a
  connection without setting `app.tenant_id` will fail. This requires discipline in the
  application layer, particularly in background jobs and Kafka consumers.
- **Superuser sessions bypass RLS**: migration runner and DBA sessions have `BYPASSRLS`.
  Access to these credentials is restricted to OpenBao-vaulted roles (see HC-1, STEP-P1-01).
- **Backfill assigns single default tenant**: existing data in `pmaas_db` (voter records,
  campaign data for the Ford-Asili 2027 pilot) will be assigned to the default tenant UUID.
  Future multi-candidate deployments must re-assign rows via a separate data migration before
  enabling per-tenant isolation in production.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Application-only tenant filtering (`WHERE tenant_id = ?` in every query) | Not enforced at DB layer; a single missing WHERE clause leaks all rows; fails HC-4 intent |
| Separate schema per tenant (Postgres schema namespacing) | High operational overhead; incompatible with existing Crunchy Postgres connection pooler (PgBouncer) in transaction-pool mode |
| Separate database per tenant | Cost-prohibitive at current scale; adds connection-pool complexity; deferred to future scale event |
| Table partitioning by `tenant_id` | Overkill at current data volume; adds DDL complexity; RLS achieves equivalent logical isolation |

---

## Compliance Mapping

| Requirement | Reference |
|---|---|
| HC-4 (Hard Constraint) | `tenant_id UUID NOT NULL` is required on every SQL table, RLS policy, Kafka CloudEvent envelope, and application query. This ADR delivers the Engage and PMaaS implementation. |
| Data Protection Act 2019 §29–34 | Personal data must be processed only for the purpose it was collected; per-tenant RLS prevents cross-tenant data access at the database layer. |
| Enhancement 3 Guide — E³ Principle P7 | Tenant isolation must be enforced at the data layer, not only the API layer. |
| i3-platform-atomic-execution-plan.md | STEP-P2-05 |

---

## Sensor Checks (from STEP-P2-05)

| Check ID | Command | Expected |
|---|---|---|
| SC-P2-05-a | `psql $ENGAGE_DB_URL -c "\d email_campaigns" \| grep tenant_id` | `tenant_id \| uuid \| not null` |
| SC-P2-05-b | `psql $ENGAGE_DB_URL -c "SELECT relrowsecurity FROM pg_class WHERE relname='email_campaigns';"` | `t` |
| SC-P2-05-c | Set `app.tenant_id` to tenant-A, insert row, switch to tenant-B, `SELECT *` | 0 rows returned |
| SC-P2-05-d | `curl -s -H "Authorization: Bearer $TOKEN" https://engage.i3technologies.co.ke/api/campaigns` | HTTP 200, same campaign list |

---

## Related Documents

- `i3-platform-atomic-execution-plan.md` — STEP-P2-05
- `platform/engage/web/migrations/002_add_tenant_id.sql`
- `platform/pmaas/web/migrations/002_add_tenant_id.sql`
- `platform/ford/api/migrations/002_add_tenant_id.sql`
- Hard Constraints: HC-4, HC-6, HC-8 (`.bob/workspace-rules/01-hard-constraints.md`)
- `ADR-003-mcp-tool-gateway.md` — prerequisite step (STEP-P2-04)
