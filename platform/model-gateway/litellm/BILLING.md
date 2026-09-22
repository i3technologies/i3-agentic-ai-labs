# LiteLLM Metering Spine — Billing Team Reference

> **IMP-07 / PLN-02/PLN-05** — Last updated: September 2026  
> Namespace: `i3-model-gateway` · Database: `litellm_billing_db`

---

## Overview

Every request to the i3 AI platform model gateway is metered against a
**per-project virtual key** with a hard, fail-closed token budget.  When a
project exceeds its monthly allocation the gateway returns **HTTP 429** and
refuses further calls until the budget resets or is raised.  There is no
fallback path to an un-metered endpoint (Rule R4).

The master key used to administer virtual keys is **disabled for interactive
use** and is reachable only through the `litellm-break-glass-sa` Kubernetes
service account, which is backed by a time-limited OpenBao token with the
`break-glass-only` policy (Rule R1).

---

## Database Schema

All tables are in the `billing` schema of `litellm_billing_db`.  Every table
carries `tenant_id UUID NOT NULL` and Row-Level Security so that queries from
one tenant cannot read another tenant's rows (HC-4).

| Table | Purpose |
|---|---|
| `billing.customers` | One row per paying/metered entity |
| `billing.projects` | Sub-units of a customer; each gets its own API key |
| `billing.api_keys` | Virtual key registry — stores HMAC-SHA256(raw_key), never plaintext |
| `billing.monthly_usage` | Rolled-up token consumption per project per calendar month |
| `billing.key_rotation_log` | Immutable audit trail of every key rotation |

### Applying the migration

```bash
# Run against PGBouncer as i3admin
psql "$PGBOUNCER_URL" -f platform/migrations/005_litellm_metering_spine.sql
```

---

## Virtual Key Lifecycle

### Initial bootstrap (run once per environment)

```bash
export LITELLM_MASTER_KEY=$(vault kv get -field=key i3/litellm/master-key)
export LITELLM_URL=https://litellm.i3technologies.co.ke
export BILLING_DB_URL=$(vault kv get -field=url i3/litellm/billing-db-url)
export BILLING_TENANT_ID=00000000-0000-0000-0000-000000000001

bash platform/model-gateway/litellm/virtual-keys-metering-bootstrap.sh
```

This script:
1. Seeds `billing.customers` and `billing.projects`.
2. Issues one virtual key per project via `POST /key/generate`.
3. Stores each plaintext key in OpenBao at `i3/litellm/virtual-keys/<customer>/<project>`.
4. Stores the HMAC-SHA256 fingerprint in `billing.api_keys`.
5. Prints instructions to disable the master key for interactive use.

### Adding a new customer / project

1. Insert rows into `billing.customers` and `billing.projects` (set
   `tenant_id`, `monthly_token_hard_limit`).
2. Call `POST /key/generate` — or re-run the bootstrap script with the new
   entries only.
3. Store the key in OpenBao and update the service Secret.

### Monthly key rotation (automated)

The `litellm-key-rotation` CronJob runs at **02:00 UTC on the 1st of every
month**.  It:
- Issues a replacement key for every `active` key in `billing.api_keys`.
- Writes the new key to OpenBao (atomic overwrite).
- Revokes the old key via `DELETE /key/delete`.
- Writes an immutable row to `billing.key_rotation_log`.

Services pick up the new key on their next pod restart, or immediately if
they fetch from OpenBao on each request.

**If rotation fails for any key**, the CronJob exits with code 1 and
Kubernetes marks the Job as failed.  This triggers a PagerDuty alert via
the standard `job_failed` PrometheusRule.

---

## Nightly Usage ETL

The `litellm-metering-etl` CronJob runs at **00:05 UTC daily**.  It:

1. Queries `LiteLLM_SpendLogs` and `LiteLLM_ErrorLogs` for the prior
   calendar month.
2. Aggregates by project: prompt tokens, completion tokens, total tokens,
   request count, over-quota hits (HTTP 429 count).
3. Upserts into `billing.monthly_usage`.
4. Renders a JSON statement per customer and uploads to:

   ```
   s3://i3-billing/statements/<tenant_id>/<customer_id>/<YYYY-MM>.json
   ```

5. Writes `statement_path` and `etl_run_at` back to `billing.monthly_usage`.

### Retrieving a statement

```bash
# Using the MinIO CLI (mc)
mc cp minio/i3-billing/statements/<tenant_id>/<customer_id>/2026-09.json /tmp/

# Or via the AWS CLI pointed at MinIO
aws --endpoint-url http://minio.i3-data.svc.cluster.local:9000 \
    s3 cp s3://i3-billing/statements/<tenant_id>/<customer_id>/2026-09.json /tmp/
```

### Re-running the ETL for a specific month

```bash
# Trigger a one-off Job from the CronJob template
oc create job --from=cronjob/litellm-metering-etl \
    litellm-metering-etl-manual \
    -n i3-model-gateway \
    -- env ETL_YEAR_MONTH=2026-08
```

---

## Budget Enforcement Rules

| Rule | Behaviour |
|---|---|
| **R1** | `master_key` is disabled for interactive use. All gateway calls must use a project virtual key. |
| **R4** | Budgets are hard and fail-closed. Gateway returns HTTP 429 on exhaustion. No graceful degradation. |

### Raising a project's budget

```bash
# Update billing DB
psql "$BILLING_DB_URL" -c "
  SET app.tenant_id = '<tenant_id>';
  UPDATE billing.projects
  SET monthly_token_hard_limit = 200000
  WHERE name = 'evalos-study-coach'
    AND tenant_id = '<tenant_id>'::UUID;
"

# Update the LiteLLM virtual key (use break-glass SA token)
MASTER_KEY=$(vault kv get -field=key i3/litellm/master-key)
curl -X POST https://litellm.i3technologies.co.ke/key/update \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "<virtual_key>", "max_budget": 200000}'
```

---

## Monitoring & Alerting

| Metric | Source | Alert threshold |
|---|---|---|
| `litellm_spend_per_key` | Prometheus (port 4001) | > 80% of `max_budget` → Slack warning |
| `kube_job_failed` | kube-state-metrics | any failed ETL or rotation Job → PagerDuty |
| `billing_monthly_usage.over_quota_hits` | `billing.monthly_usage` | > 0 → weekly billing report |

---

## Security Notes

- **Plaintext keys never in git or DB.** Keys are stored only in OpenBao and
  in the memory of the issuing script during bootstrap.
- **HMAC-SHA256 fingerprints** (`key_hash`) are stored in `billing.api_keys`
  keyed with `KEY_HMAC_SECRET` (OpenBao path: `i3/litellm/key-hmac-secret`).
  Raw SHA-256 is not used (HC-6).
- **RLS** ensures no cross-tenant row leakage.  Always set
  `app.tenant_id` before querying billing tables.
- **Break-glass SA** (`litellm-break-glass-sa`) has the only OpenBao token
  with access to `i3/litellm/master-key`.  Its token is projected with a
  24-hour TTL and is not stored in any Secret.

---

## Running Tests

```bash
# Unit + integration tests (requires a running litellm_billing_db)
export LITELLM_BILLING_DB_URL=postgresql://billing_app:...@localhost:5432/litellm_billing_db
export BILLING_TENANT_ID=00000000-0000-0000-0000-000000000001
export KEY_HMAC_SECRET=$(vault kv get -field=secret i3/litellm/key-hmac-secret)

# Optional — enables the live over-quota gateway test (R4)
export LITELLM_URL=https://litellm.i3technologies.co.ke
export LITELLM_TEST_KEY=$(vault kv get -field=api_key i3/litellm/virtual-keys/i3-internal/mcp-gateway)

pytest platform/testing/test_metering_spine.py -v
```

Tests that require a live gateway are automatically skipped when
`LITELLM_TEST_KEY` is not set, so the full suite runs safely in CI.
