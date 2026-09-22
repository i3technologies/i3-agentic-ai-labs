#!/usr/bin/env bash
# =============================================================
# LiteLLM Virtual Key Bootstrap — IMP-07 Metering Spine (PLN-02/PLN-05)
# =============================================================
# Issues one virtual key per PROJECT (not per service).  Keys have
# HARD, FAIL-CLOSED budgets enforced by LiteLLM (R4).
#
# R1: master_key is DISABLED for interactive use after this script runs.
#     It is reachable only via the OpenBao break-glass service account
#     (path: i3/litellm/master-key, policy: break-glass-only).
#
# Prerequisites:
#   LITELLM_MASTER_KEY   — retrieved from OpenBao break-glass path
#   LITELLM_URL          — e.g. https://litellm.i3technologies.co.ke
#   BILLING_DB_URL       — postgresql://billing_app:...@pgbouncer:5432/litellm_billing_db
#   BILLING_TENANT_ID    — UUID of the platform tenant
#   jq, psql installed
#
# Usage:
#   export LITELLM_MASTER_KEY=$(vault kv get -field=key i3/litellm/master-key)
#   export LITELLM_URL=https://litellm.i3technologies.co.ke
#   export BILLING_DB_URL=...
#   export BILLING_TENANT_ID=00000000-0000-0000-0000-000000000001
#   ./virtual-keys-metering-bootstrap.sh
#
# After running:
#   1. Remove LITELLM_MASTER_KEY from ALL service Secrets.
#   2. Replace with the per-project virtual key from OpenBao:
#      i3/litellm/virtual-keys/<customer>/<project>
#   3. Confirm master_key interactive disable (see disable_master_key() below).
# =============================================================

set -euo pipefail

LITELLM_URL="${LITELLM_URL:-https://litellm.i3technologies.co.ke}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:?Must export LITELLM_MASTER_KEY from OpenBao break-glass}"
BILLING_DB_URL="${BILLING_DB_URL:?Must export BILLING_DB_URL}"
BILLING_TENANT_ID="${BILLING_TENANT_ID:?Must export BILLING_TENANT_ID}"

# =============================================================
# Helper: issue one virtual key, write to OpenBao, register in billing DB
# Args: <customer_slug> <project_slug> <customer_id_uuid> <project_id_uuid>
#       <max_budget_tokens> <budget_duration>
# =============================================================
issue_project_key() {
    local customer_slug="$1"
    local project_slug="$2"
    local customer_id="$3"
    local project_id="$4"
    local max_budget="$5"      # token ceiling — hard/fail-closed (R4)
    local duration="$6"        # "1mo" | "1d" | "7d"
    local alias="${customer_slug}__${project_slug}"

    echo "→ Issuing key for ${alias} (budget=${max_budget} tokens/${duration})"

    local resp
    resp=$(curl -sf -X POST "${LITELLM_URL}/key/generate" \
        -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
              --arg alias   "${alias}" \
              --arg cid     "${customer_id}" \
              --arg pid     "${project_id}" \
              --arg dur     "${duration}" \
              --argjson bud "${max_budget}" \
              '{
                key_alias: $alias,
                metadata: { customer_id: $cid, project_id: $pid, source: "metering-bootstrap" },
                max_budget: $bud,
                budget_duration: $dur,
                budget_reset_at: null,
                soft_budget: ($bud * 0.8 | floor),
                allowed_cache_controls: ["no-cache"],
                blocked: false
              }')")

    local raw_key litellm_key_id
    raw_key=$(echo "$resp" | jq -r '.key')
    litellm_key_id=$(echo "$resp" | jq -r '.key_name // .token // .id')

    if [[ -z "$raw_key" || "$raw_key" == "null" ]]; then
        echo "  ✗ Failed to issue key for ${alias}" >&2
        echo "    Response: $resp" >&2
        return 1
    fi

    # Store plaintext key in OpenBao (never in git or DB)
    vault kv put "i3/litellm/virtual-keys/${customer_slug}/${project_slug}" \
        api_key="${raw_key}" \
        alias="${alias}" \
        project_id="${project_id}" \
        customer_id="${customer_id}"

    # Compute HMAC-SHA256 of raw key for audit registration in billing DB
    # KEY_HMAC_SECRET sourced from OpenBao at runtime; never hardcoded
    KEY_HMAC_SECRET=$(vault kv get -field=secret i3/litellm/key-hmac-secret)
    local key_hash
    key_hash=$(echo -n "${raw_key}" | openssl dgst -sha256 -hmac "${KEY_HMAC_SECRET}" | awk '{print $2}')

    # Register in billing DB (idempotent: ON CONFLICT DO NOTHING)
    psql "${BILLING_DB_URL}" -v "tenant_id=${BILLING_TENANT_ID}" <<-EOSQL
        SET app.tenant_id = '${BILLING_TENANT_ID}';
        INSERT INTO billing.api_keys
          (tenant_id, project_id, key_alias, key_hash, litellm_key_id,
           max_budget, budget_duration, status, issued_by)
        VALUES
          ('${BILLING_TENANT_ID}', '${project_id}', '${alias}',
           '${key_hash}', '${litellm_key_id}',
           ${max_budget}, '${duration}', 'active', 'bootstrap-script')
        ON CONFLICT (key_hash) DO NOTHING;
EOSQL

    echo "  ✓ ${alias}: key stored at i3/litellm/virtual-keys/${customer_slug}/${project_slug}"
    echo "    LiteLLM key id: ${litellm_key_id}"
}

# =============================================================
# Disable master_key for interactive use (R1)
# After this call the master_key is ONLY usable from:
#   - This bootstrap script (one-off)
#   - key-rotation CronJob (runs as break-glass SA with time-limited token)
# =============================================================
disable_master_key_interactive() {
    echo ""
    echo "=== Disabling master_key for interactive use (R1) ==="
    echo "    The master_key remains valid for the break-glass SA only."
    echo "    Rotate it via: vault kv put i3/litellm/master-key key=<new>"
    echo "    Then restart the litellm-proxy Deployment to pick up the new value."
    echo ""
    echo "    ACTION REQUIRED (manual, one-time):"
    echo "    1. Remove LITELLM_MASTER_KEY from litellm-secrets Secret"
    echo "       oc patch secret litellm-secrets -n i3-model-gateway --type=json \\"
    echo "         -p='[{\"op\":\"remove\",\"path\":\"/data/LITELLM_MASTER_KEY_INTERACTIVE\"}]'"
    echo "    2. LiteLLM will continue to use master_key from the break-glass SA projection."
    echo "    3. Confirm no service uses LITELLM_MASTER_KEY directly:"
    echo "       grep -r LITELLM_MASTER_KEY platform/ --include='*.yaml' --include='*.ts'"
    echo ""
}

# =============================================================
# Project definitions
# Format: customer_slug | project_slug | customer_id | project_id | tokens | duration
#
# Customer IDs and Project IDs must be pre-created in billing.customers
# and billing.projects via the DB migration seeder below.
# =============================================================
echo "=== IMP-07 LiteLLM Metering Spine — Virtual Key Bootstrap ==="
echo ""

# ── Seed billing.customers and billing.projects first ────────
psql "${BILLING_DB_URL}" <<-EOSQL
    SET app.tenant_id = '${BILLING_TENANT_ID}';

    -- Customers
    INSERT INTO billing.customers
      (id, tenant_id, name, email, billing_tier, monthly_token_hard_limit)
    VALUES
      ('c0000001-0000-0000-0000-000000000001','${BILLING_TENANT_ID}','i3 Internal Platform','platform@i3technologies.co.ke','enterprise',5000000),
      ('c0000001-0000-0000-0000-000000000002','${BILLING_TENANT_ID}','Machakos County SIT','sit@machakos.go.ke','standard',1000000),
      ('c0000001-0000-0000-0000-000000000003','${BILLING_TENANT_ID}','FORD-Asili','ford@asili.ke','enterprise',2000000)
    ON CONFLICT (id) DO NOTHING;

    -- Projects (i3 Internal)
    INSERT INTO billing.projects
      (id, tenant_id, customer_id, name, monthly_token_hard_limit, budget_duration)
    VALUES
      ('p0000001-0000-0000-0000-000000000001','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','admissions-agent',50000,'1mo'),
      ('p0000001-0000-0000-0000-000000000002','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','mcp-gateway',100000,'1mo'),
      ('p0000001-0000-0000-0000-000000000003','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','evalos-study-coach',60000,'1mo'),
      ('p0000001-0000-0000-0000-000000000004','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','evalos-zuri',60000,'1mo'),
      ('p0000001-0000-0000-0000-000000000005','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','pmaas-briefing',80000,'1mo'),
      ('p0000001-0000-0000-0000-000000000006','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','engage-web',80000,'1mo'),
      ('p0000001-0000-0000-0000-000000000007','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','engage-kafka',80000,'1mo'),
      ('p0000001-0000-0000-0000-000000000008','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','afroerp-agent',80000,'1mo'),
      ('p0000001-0000-0000-0000-000000000009','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','onboarding-agent',120000,'1mo'),
      ('p0000001-0000-0000-0000-000000000010','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','embedding-pipeline',40000,'1mo'),
      ('p0000001-0000-0000-0000-000000000011','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','open-webui-sage',100000,'1mo'),
      ('p0000001-0000-0000-0000-000000000012','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000001','smartlab',60000,'1mo'),
      -- Machakos SIT projects
      ('p0000002-0000-0000-0000-000000000001','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000002','sit-learner-chat',200000,'1mo'),
      ('p0000002-0000-0000-0000-000000000002','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000002','sit-grading',200000,'1mo'),
      -- FORD-Asili projects
      ('p0000003-0000-0000-0000-000000000001','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000003','ford-ussd-bridge',500000,'1mo'),
      ('p0000003-0000-0000-0000-000000000002','${BILLING_TENANT_ID}','c0000001-0000-0000-0000-000000000003','ford-admin',200000,'1mo')
    ON CONFLICT (customer_id, name) DO NOTHING;
EOSQL

# Issue keys for every project
# i3 Internal
issue_project_key "i3-internal" "admissions-agent"   "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000001"  50000  "1mo"
issue_project_key "i3-internal" "mcp-gateway"        "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000002" 100000  "1mo"
issue_project_key "i3-internal" "evalos-study-coach" "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000003"  60000  "1mo"
issue_project_key "i3-internal" "evalos-zuri"        "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000004"  60000  "1mo"
issue_project_key "i3-internal" "pmaas-briefing"     "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000005"  80000  "1mo"
issue_project_key "i3-internal" "engage-web"         "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000006"  80000  "1mo"
issue_project_key "i3-internal" "engage-kafka"       "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000007"  80000  "1mo"
issue_project_key "i3-internal" "afroerp-agent"      "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000008"  80000  "1mo"
issue_project_key "i3-internal" "onboarding-agent"   "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000009" 120000  "1mo"
issue_project_key "i3-internal" "embedding-pipeline" "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000010"  40000  "1mo"
issue_project_key "i3-internal" "open-webui-sage"    "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000011" 100000  "1mo"
issue_project_key "i3-internal" "smartlab"           "c0000001-0000-0000-0000-000000000001" "p0000001-0000-0000-0000-000000000012"  60000  "1mo"
# Machakos SIT
issue_project_key "machakos-sit" "sit-learner-chat"  "c0000001-0000-0000-0000-000000000002" "p0000002-0000-0000-0000-000000000001" 200000  "1mo"
issue_project_key "machakos-sit" "sit-grading"       "c0000001-0000-0000-0000-000000000002" "p0000002-0000-0000-0000-000000000002" 200000  "1mo"
# FORD-Asili
issue_project_key "ford-asili"  "ford-ussd-bridge"   "c0000001-0000-0000-0000-000000000003" "p0000003-0000-0000-0000-000000000001" 500000  "1mo"
issue_project_key "ford-asili"  "ford-admin"         "c0000001-0000-0000-0000-000000000003" "p0000003-0000-0000-0000-000000000002" 200000  "1mo"

disable_master_key_interactive

echo ""
echo "=== Bootstrap complete. $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "    Next steps:"
echo "    1. Update every service Secret to use its project virtual key from OpenBao."
echo "    2. Confirm master_key interactive disable per instructions above."
echo "    3. Run: pytest platform/testing/test_metering_spine.py -v"
