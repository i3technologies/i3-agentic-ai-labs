# OPA Rego — Financial Tool Execution Policy
# Package:  agentic.financial_tools
# File:     platform/agentic-os/policies/financial_tools.rego
#
# Purpose:
#   Enforce the $500 financial threshold gate for tool invocations that carry
#   a financial value (estimated_value_usd).  Evaluated by the OPA sidecar
#   co-located with the MCP Gateway pod.
#
# Invocation:
#   Called by MCP Gateway before dispatching any tool with
#   side_effect_class = "financial" | "external_write".
#
#   POST http://localhost:8181/v1/data/agentic/financial_tools
#   Body: {
#     "input": {
#       "tool_name":            "<string>",
#       "side_effect_class":    "financial" | "external_write" | ...,
#       "agent_id":             "<string>",
#       "agent_autonomy_tier":  "L0" | "L1",
#       "estimated_value_usd":  <number>,
#       "risk_tier":            <integer 0–3>,
#       "tenant_id":            "<uuid>",
#       "approval_id":          "<uuid>" | null
#     }
#   }
#
# Result document:
#   {
#     "financial_tool_allow":  true | false,
#     "requires_supervisor":   true | false,
#     "denial_reason":         "<string>" | null
#   }
#
# HC-4:  tenant_id must be present — `tenant_id_present` guards all decisions.
# HC-5:  This policy only authorises; it never executes tools.
# HC-7:  No DEV_BYPASS_AUTH path exists.
# HC-3:  Agent autonomy tier is validated; L2/L3 is always denied.

package agentic.financial_tools

# ── Defaults ──────────────────────────────────────────────────────────────────
default financial_tool_allow = false
default requires_supervisor   = false
default denial_reason         = null

# ── Constants ─────────────────────────────────────────────────────────────────
# Threshold above which human supervisor approval is mandatory (HC-5)
financial_threshold_usd := 500

# Tools that carry financial value and are subject to this policy.
# Extend this set when new financial-class tools are registered.
financial_tool_names := {
    "vpcp.ibm_sales_cloud.sync",
    "postgres.members.write",
    "odoo.crm.create",
}

# ── HC-4 Guard ────────────────────────────────────────────────────────────────
tenant_id_present {
    input.tenant_id != ""
    count(input.tenant_id) > 0
}

# ── HC-3 Guard ────────────────────────────────────────────────────────────────
# Only L0 and L1 autonomy tiers are valid.  L2/L3 are always blocked.
valid_autonomy_tier {
    input.agent_autonomy_tier == "L0"
}

valid_autonomy_tier {
    input.agent_autonomy_tier == "L1"
}

# ── Rule: requires_supervisor ─────────────────────────────────────────────────
# Supervisor approval is required when:
#   - The tool is in the financial_tool_names set, AND
#   - The estimated_value_usd meets or exceeds the $500 threshold, AND
#   - No valid approval_id has been provided yet.
#
# This rule is ADDITIVE to the existing Tier 3 gate: a tool already declared
# risk_tier=3 is always gated by the MCP Gateway; this policy adds the value-
# based gate on top for tools that may have varying risk (e.g., a $50 Odoo CRM
# create is Tier 2 auto-approved, but a $600 sync must escalate to Tier 3).
requires_supervisor {
    input.tool_name in financial_tool_names
    input.estimated_value_usd >= financial_threshold_usd
    not approval_already_granted
}

# ── Helper: approval already granted ─────────────────────────────────────────
# True when the input already carries a non-null, non-empty approval_id.
# (The MCP Gateway verifies the approval record independently via _verify_approval.)
approval_already_granted {
    input.approval_id != null
    count(input.approval_id) > 0
}

# ── Rule: financial_tool_allow ────────────────────────────────────────────────
# Allow execution when ALL of the following hold:
#   1. HC-4: tenant_id is present.
#   2. HC-3: autonomy tier is L0 or L1.
#   3. Either:
#      a. Tool is NOT in the financial set (not subject to this policy), OR
#      b. Tool IS in the financial set AND value < threshold (auto-approved), OR
#      c. Tool IS in the financial set AND value ≥ threshold AND approval granted.

# Path A: tool not in financial set — pass through (other policies apply)
financial_tool_allow {
    tenant_id_present
    valid_autonomy_tier
    not input.tool_name in financial_tool_names
}

# Path B: financial tool, value below threshold — auto-approved
financial_tool_allow {
    tenant_id_present
    valid_autonomy_tier
    input.tool_name in financial_tool_names
    input.estimated_value_usd < financial_threshold_usd
}

# Path C: financial tool, value at or above threshold, approval already granted
financial_tool_allow {
    tenant_id_present
    valid_autonomy_tier
    input.tool_name in financial_tool_names
    input.estimated_value_usd >= financial_threshold_usd
    approval_already_granted
}

# ── Rule: denial_reason ───────────────────────────────────────────────────────
# Populate denial_reason for observability / audit log when the tool is blocked.

denial_reason = reason {
    not tenant_id_present
    reason := "HC-4: tenant_id is missing or empty"
}

denial_reason = reason {
    tenant_id_present
    not valid_autonomy_tier
    reason := sprintf(
        "HC-3: autonomy_tier=%v is above L1 ceiling — rejected",
        [input.agent_autonomy_tier],
    )
}

denial_reason = reason {
    tenant_id_present
    valid_autonomy_tier
    requires_supervisor
    reason := sprintf(
        "Financial threshold exceeded: estimated_value_usd=%.2f >= %v USD — supervisor approval required (HC-5)",
        [input.estimated_value_usd, financial_threshold_usd],
    )
}
