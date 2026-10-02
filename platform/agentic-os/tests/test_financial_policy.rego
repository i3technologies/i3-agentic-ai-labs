# OPA Unit Tests — Financial Tools Policy
# File: platform/agentic-os/tests/test_financial_policy.rego
#
# Run with:  opa test platform/agentic-os/policies/ platform/agentic-os/tests/
# Requires:  opa >= 0.60.0

package agentic.financial_tools_test

import data.agentic.financial_tools

# ── Helpers ───────────────────────────────────────────────────────────────────
base_input := {
    "tool_name":            "vpcp.ibm_sales_cloud.sync",
    "side_effect_class":    "external_write",
    "agent_id":             "agentic-os-supervisor",
    "agent_autonomy_tier":  "L1",
    "estimated_value_usd":  0,
    "risk_tier":            3,
    "tenant_id":            "00000000-0000-0000-0000-000000000002",
    "approval_id":          null,
}

# ── Tests: below threshold ────────────────────────────────────────────────────

test_allow_below_threshold {
    result := financial_tools with input as object.union(base_input, {"estimated_value_usd": 499.99})
    result.financial_tool_allow == true
    result.requires_supervisor == false
}

test_allow_zero_value {
    result := financial_tools with input as object.union(base_input, {"estimated_value_usd": 0})
    result.financial_tool_allow == true
    result.requires_supervisor == false
}

test_allow_exactly_499 {
    result := financial_tools with input as object.union(base_input, {"estimated_value_usd": 499})
    result.financial_tool_allow == true
}

# ── Tests: at/above threshold, no approval ────────────────────────────────────

test_deny_at_threshold_no_approval {
    result := financial_tools with input as object.union(base_input, {"estimated_value_usd": 500})
    result.financial_tool_allow == false
    result.requires_supervisor == true
}

test_deny_above_threshold_no_approval {
    result := financial_tools with input as object.union(base_input, {"estimated_value_usd": 12000})
    result.financial_tool_allow == false
    result.requires_supervisor == true
    contains(result.denial_reason, "Financial threshold exceeded")
    contains(result.denial_reason, "supervisor approval required")
}

# ── Tests: at/above threshold, with valid approval ────────────────────────────

test_allow_above_threshold_with_approval {
    input_with_approval := object.union(base_input, {
        "estimated_value_usd": 1200,
        "approval_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    })
    result := financial_tools with input as input_with_approval
    result.financial_tool_allow == true
    result.requires_supervisor == false
}

test_allow_exactly_500_with_approval {
    input_with_approval := object.union(base_input, {
        "estimated_value_usd": 500,
        "approval_id": "11111111-2222-3333-4444-555555555555",
    })
    result := financial_tools with input as input_with_approval
    result.financial_tool_allow == true
}

# ── Tests: HC-4 tenant_id guard ───────────────────────────────────────────────

test_deny_missing_tenant_id {
    input_no_tenant := object.union(base_input, {"tenant_id": ""})
    result := financial_tools with input as input_no_tenant
    result.financial_tool_allow == false
    contains(result.denial_reason, "HC-4")
}

# ── Tests: HC-3 autonomy tier guard ──────────────────────────────────────────

test_deny_l2_autonomy_tier {
    input_l2 := object.union(base_input, {"agent_autonomy_tier": "L2"})
    result := financial_tools with input as input_l2
    result.financial_tool_allow == false
    contains(result.denial_reason, "HC-3")
}

test_deny_l3_autonomy_tier {
    input_l3 := object.union(base_input, {"agent_autonomy_tier": "L3"})
    result := financial_tools with input as input_l3
    result.financial_tool_allow == false
    contains(result.denial_reason, "HC-3")
}

test_allow_l0_autonomy_tier {
    input_l0 := object.union(base_input, {"agent_autonomy_tier": "L0", "estimated_value_usd": 10})
    result := financial_tools with input as input_l0
    result.financial_tool_allow == true
}

# ── Tests: non-financial tool (pass-through) ──────────────────────────────────

test_allow_non_financial_tool {
    non_fin_input := object.union(base_input, {
        "tool_name":            "chroma.search",
        "side_effect_class":    "read",
        "estimated_value_usd":  0,
    })
    result := financial_tools with input as non_fin_input
    result.financial_tool_allow == true
    result.requires_supervisor == false
}

test_allow_non_financial_tool_high_value {
    # A non-financial tool with a high estimated_value_usd field should still pass
    # (the policy only gates tools in financial_tool_names)
    non_fin_input := object.union(base_input, {
        "tool_name":            "litellm.chat",
        "side_effect_class":    "inference",
        "estimated_value_usd":  99999,
    })
    result := financial_tools with input as non_fin_input
    result.financial_tool_allow == true
}

# ── Tests: postgres.members.write (HC-6 PII write) ───────────────────────────

test_deny_postgres_members_write_above_threshold {
    pg_input := object.union(base_input, {
        "tool_name":            "postgres.members.write",
        "side_effect_class":    "financial",
        "estimated_value_usd":  600,
    })
    result := financial_tools with input as pg_input
    result.financial_tool_allow == false
    result.requires_supervisor == true
}
