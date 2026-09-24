#!/usr/bin/env bash
# ============================================================
# LiteLLM Virtual Key Bootstrap — AUTH-01 Remediation
# ============================================================
# Run ONCE after initial LiteLLM deployment to issue per-service
# virtual keys. Each key has a daily token budget matching the
# agent-registry manifest cost_budget_tokens value.
#
# Prerequisites:
#   - LITELLM_MASTER_KEY  export from OpenBao i3/litellm/master-key
#   - LITELLM_URL         e.g. https://litellm.i3technologies.co.ke
#   - jq installed
#
# Output: prints each virtual key; save each to OpenBao:
#   vault kv put i3/litellm/virtual-keys/<service> api_key=<value>
#
# After issuing, remove LITELLM_MASTER_KEY from all service Secrets
# and replace with the corresponding virtual key.
# ============================================================

set -euo pipefail

LITELLM_URL="${LITELLM_URL:-https://litellm.i3technologies.co.ke}"
LITELLM_MASTER_KEY="${LITELLM_MASTER_KEY:?Must set LITELLM_MASTER_KEY}"

issue_key() {
    local service="$1"
    local budget="$2"   # daily token budget (from agent-registry manifest)
    local resp
    resp=$(curl -sf -X POST "${LITELLM_URL}/key/generate" \
        -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
              \"metadata\": {\"service\": \"${service}\"},
              \"max_budget\": ${budget},
              \"budget_duration\": \"1d\",
              \"key_alias\": \"${service}\"
            }")
    local key
    key=$(echo "$resp" | jq -r '.key')
    echo "SERVICE=${service}  KEY=${key}"
    echo "  → vault kv put i3/litellm/virtual-keys/${service} api_key=${key}"
}

echo "=== Issuing LiteLLM virtual keys (AUTH-01) ==="

# budget values are in tokens (not dollars — on-premise infra).
# Derived from agent-registry/manifests/*.yaml cost_budget_tokens.
# LiteLLM treats budget as USD; set to a large number since cost=0 on-prem.
# The real enforcement is via Prometheus token-budget alerts.

issue_key "admissions-agent"   50000
issue_key "mcp-gateway"        100000
issue_key "evalos-study-coach" 30000
issue_key "evalos-zuri"        30000
issue_key "pmaas-briefing"     40000
issue_key "engage-web"         40000
issue_key "engage-kafka"       40000
issue_key "afroerp-agent"      40000
issue_key "mfumo-coworker"     40000
issue_key "onboarding-agent"   60000
issue_key "embedding-pipeline" 20000
issue_key "open-webui-sage"    50000
issue_key "smartlab"           30000

echo ""
echo "=== Done. Store each key in OpenBao and update service Secrets. ==="
echo "    See platform/model-gateway/litellm/virtual-keys-bootstrap.sh for paths."
