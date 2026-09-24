# B2 — Per-Tenant Metering & Billing Evidence Pack

> ⚠ **STATUS: INCOMPLETE — ONE FULL BILLING CYCLE REQUIRED**  
> The claim "Per-tenant metering & billing" **MAY NOT** be made in the present tense until this document records a reconciled ledger for one complete billing cycle and is signed PASS.

| Field | Value |
|-------|-------|
| **Evidence ID** | B2-evidence-_[YYYYMMDD]_ |
| **Capability Claim** | "Per-tenant metering & billing" |
| **Condition to unlock** | B2 ledger reconciled for one full billing cycle |
| **Auditor** | _[To be completed by platform team]_ |
| **Billing cycle** | _[YYYY-MM-01 to YYYY-MM-30/31]_ |
| **Environment** | Production |
| **Classification** | Internal Engineering |

---

## Acceptance Criteria

All of the following must be confirmed for at least one complete billing cycle:

| # | Criterion | Status |
|---|-----------|--------|
| MC-01 | LiteLLM virtual key usage metered per `tenant_id` (token counts recorded) | ⬜ INCOMPLETE |
| MC-02 | Per-tenant token totals match Langfuse trace aggregates for the same period | ⬜ INCOMPLETE |
| MC-03 | Invoice or ledger line generated per tenant for the billing cycle | ⬜ INCOMPLETE |
| MC-04 | Ledger reconciled: metered usage ≤ invoiced usage (no under-billing) | ⬜ INCOMPLETE |
| MC-05 | No cross-tenant token attribution (Tenant A tokens never billed to Tenant B) | ⬜ INCOMPLETE |
| MC-06 | Metering data persisted to PostgreSQL with `tenant_id UUID NOT NULL` (HC-4) | ⬜ INCOMPLETE |
| MC-07 | Usage export available in auditor-queryable format (CSV or SQL) | ⬜ INCOMPLETE |

---

## Metering Architecture Reference

The metering stack must be confirmed operational before a billing cycle run:

| Component | File | Expected Status |
|-----------|------|----------------|
| LiteLLM virtual key usage tracking | `platform/model-gateway/litellm/litellm-config-oss.yaml` | Per-key `tenant_id` tag required |
| Langfuse trace aggregation | `platform/model-gateway/langfuse/langfuse-deploy.yaml` | Running, traces ingested |
| KEDA autoscale events (for burst billing) | `platform/model-gateway/keda/keda-scaled-objects.yaml` | Scale events logged |
| PostgreSQL usage table | _[migrations path]_ | `tenant_id UUID NOT NULL`; HC-4 enforced |

---

## Billing Cycle Evidence (Complete When Available)

### MC-01 — LiteLLM Token Metering

```bash
# Extract per-tenant token usage from LiteLLM for billing cycle
curl -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  "http://litellm.i3technologies.co.ke/usage?start_date=YYYY-MM-01&end_date=YYYY-MM-30" \
  | jq '.usage_by_key[] | {tenant_id: .metadata.tenant_id, tokens: .total_tokens}'
```

**Result:** _[Paste output — per-tenant token counts]_  
**Status:** ⬜ INCOMPLETE

---

### MC-02 — Langfuse Trace Reconciliation

```bash
# Aggregate token usage from Langfuse for the billing period
# (Langfuse API or dashboard export)
# Expected: per-tenant totals match LiteLLM virtual key totals within ±2%
```

**Result:** _[Paste reconciliation table]_  
**Reconciliation delta:** _[%]_  
**Status:** ⬜ INCOMPLETE

---

### MC-03 — Invoice / Ledger Lines Generated

| Tenant ID | Tenant Name | Billing Period | Total Tokens | Compute Units | Amount (USD/KES) |
|-----------|-------------|---------------|-------------|--------------|-----------------|
| _[ ]_ | _[ ]_ | _[YYYY-MM]_ | _[ ]_ | _[ ]_ | _[ ]_ |
| _[ ]_ | _[ ]_ | _[YYYY-MM]_ | _[ ]_ | _[ ]_ | _[ ]_ |

**Status:** ⬜ INCOMPLETE

---

### MC-04 — Ledger Reconciliation (Metered vs Invoiced)

| Tenant | Metered Tokens | Invoiced Tokens | Delta | Within Tolerance? |
|--------|---------------|----------------|-------|------------------|
| _[ ]_ | _[ ]_ | _[ ]_ | _[ ]_ | ⬜ |

Tolerance: metered ≤ invoiced, or within ±1% (rounding).  
**Status:** ⬜ INCOMPLETE

---

### MC-05 — Cross-Tenant Attribution Check

```sql
-- Confirm no token usage record has tenant_id NULL or mismatched
SELECT COUNT(*)
FROM litellm_usage_log
WHERE tenant_id IS NULL
   OR tenant_id NOT IN (SELECT tenant_id FROM tenants);
-- Expected: 0 rows
```

**Result:** _[Paste count]_  
**Status:** ⬜ INCOMPLETE

---

### MC-06 — PostgreSQL HC-4 Compliance

```bash
# Confirm usage table has tenant_id NOT NULL constraint
psql $DATABASE_URL -c "\d+ litellm_usage_log" | grep tenant_id
# Expected: tenant_id | uuid | not null

# Confirm RLS policy on usage table
psql $DATABASE_URL -c "\dp litellm_usage_log"
# Expected: RLS policy using (tenant_id = current_setting('app.tenant_id')::uuid)
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### MC-07 — Auditor-Queryable Usage Export

```sql
-- Full usage export for the billing cycle (auditor query)
SELECT
  tenant_id,
  SUM(prompt_tokens)     AS total_prompt_tokens,
  SUM(completion_tokens) AS total_completion_tokens,
  SUM(total_tokens)      AS total_tokens,
  DATE_TRUNC('day', created_at) AS usage_date
FROM litellm_usage_log
WHERE created_at >= 'YYYY-MM-01'
  AND created_at <  'YYYY-MM-01'::date + INTERVAL '1 month'
GROUP BY tenant_id, usage_date
ORDER BY tenant_id, usage_date;
```

**Export produced:** ⬜ INCOMPLETE — attach CSV or reference S3 path

---

## Overall Verdict

**Current status: INCOMPLETE — claim LOCKED**

To unlock: complete one full billing cycle, fill in all seven criteria above, reconcile ledger, complete sign-off.

| Criterion | Status |
|-----------|--------|
| MC-01 LiteLLM token metering | ⬜ |
| MC-02 Langfuse trace reconciliation | ⬜ |
| MC-03 Invoice / ledger lines generated | ⬜ |
| MC-04 Ledger reconciled (metered ≤ invoiced) | ⬜ |
| MC-05 No cross-tenant attribution | ⬜ |
| MC-06 PostgreSQL HC-4 compliance | ⬜ |
| MC-07 Auditor-queryable export produced | ⬜ |

---

## Sign-Off (complete when all criteria PASS)

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Platform Architect | | | |
| Finance / Billing Lead | | | |

---

*Document path: `docs/verification/B2-evidence-template.md`*  
*Rename to `B2-evidence-[YYYYMMDD].md` when completed.*  
*Template generated by Bob AI Auditor · i3 AI Platform*  
*Claim unlocks only after one complete billing cycle is reconciled and this document is signed.*
