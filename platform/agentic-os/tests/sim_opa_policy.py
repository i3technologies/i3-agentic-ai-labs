"""
OPA Financial-Tools Policy Simulator
Mirrors financial_tools.rego exactly for environments where the OPA CLI is absent.
"""
import copy, sys

FINANCIAL_TOOL_NAMES = {
    "vpcp.ibm_sales_cloud.sync",
    "postgres.members.write",
    "odoo.crm.create",
}
THRESHOLD = 500


def tenant_id_present(inp):
    return bool(inp.get("tenant_id"))


def valid_autonomy_tier(inp):
    return inp.get("agent_autonomy_tier") in ("L0", "L1")


def approval_already_granted(inp):
    aid = inp.get("approval_id")
    return aid is not None and len(str(aid)) > 0


def requires_supervisor(inp):
    return (
        inp["tool_name"] in FINANCIAL_TOOL_NAMES
        and inp["estimated_value_usd"] >= THRESHOLD
        and not approval_already_granted(inp)
    )


def evaluate(inp):
    req_sup = requires_supervisor(inp)
    denial = None
    allow = False

    if not tenant_id_present(inp):
        denial = "HC-4: tenant_id is missing or empty"
    elif not valid_autonomy_tier(inp):
        tier = inp["agent_autonomy_tier"]
        denial = f"HC-3: autonomy_tier={tier} is above L1 ceiling — rejected"
    elif req_sup:
        val = inp["estimated_value_usd"]
        denial = (
            f"Financial threshold exceeded: estimated_value_usd={val:.2f} "
            f">= {THRESHOLD} USD — supervisor approval required (HC-5)"
        )
    else:
        if inp["tool_name"] not in FINANCIAL_TOOL_NAMES:
            allow = True
        elif inp["estimated_value_usd"] < THRESHOLD:
            allow = True
        elif approval_already_granted(inp):
            allow = True

    return {
        "financial_tool_allow": allow,
        "requires_supervisor": req_sup,
        "denial_reason": denial,
    }


def union(base, extra):
    r = copy.copy(base)
    r.update(extra)
    return r


BASE = {
    "tool_name": "vpcp.ibm_sales_cloud.sync",
    "side_effect_class": "external_write",
    "agent_id": "agentic-os-supervisor",
    "agent_autonomy_tier": "L1",
    "estimated_value_usd": 0,
    "risk_tier": 3,
    "tenant_id": "00000000-0000-0000-0000-000000000002",
    "approval_id": None,
}

# (name, input_dict, expected_allow, expected_requires_supervisor_or_None)
TESTS = [
    ("test_allow_below_threshold",
     union(BASE, {"estimated_value_usd": 499.99}), True, False),
    ("test_allow_zero_value",
     union(BASE, {"estimated_value_usd": 0}), True, False),
    ("test_allow_exactly_499",
     union(BASE, {"estimated_value_usd": 499}), True, None),
    ("test_deny_at_threshold_no_approval",
     union(BASE, {"estimated_value_usd": 500}), False, True),
    ("test_deny_above_threshold_no_approval",
     union(BASE, {"estimated_value_usd": 12000}), False, True),
    ("test_allow_above_threshold_with_approval",
     union(BASE, {"estimated_value_usd": 1200, "approval_id": "aaa-bbb-ccc"}), True, False),
    ("test_allow_exactly_500_with_approval",
     union(BASE, {"estimated_value_usd": 500, "approval_id": "111-222-333"}), True, None),
    ("test_deny_missing_tenant_id",
     union(BASE, {"tenant_id": ""}), False, None),
    ("test_deny_l2_autonomy_tier",
     union(BASE, {"agent_autonomy_tier": "L2"}), False, None),
    ("test_deny_l3_autonomy_tier",
     union(BASE, {"agent_autonomy_tier": "L3"}), False, None),
    ("test_allow_l0_autonomy_tier",
     union(BASE, {"agent_autonomy_tier": "L0", "estimated_value_usd": 10}), True, None),
    ("test_allow_non_financial_tool",
     union(BASE, {"tool_name": "chroma.search", "side_effect_class": "read",
                  "estimated_value_usd": 0}), True, False),
    ("test_allow_non_financial_tool_high_value",
     union(BASE, {"tool_name": "litellm.chat", "side_effect_class": "inference",
                  "estimated_value_usd": 99999}), True, None),
    ("test_deny_postgres_members_write_above_threshold",
     union(BASE, {"tool_name": "postgres.members.write",
                  "side_effect_class": "financial",
                  "estimated_value_usd": 600}), False, True),
    # === Adversarial Verification Tests ===
    # Mock banking refund $750 WITHOUT supervisor credentials → MUST be denied (HC-5)
    ("test_mock_banking_refund_750_no_credentials",
     union(BASE, {"tool_name": "vpcp.ibm_sales_cloud.sync",
                  "estimated_value_usd": 750,
                  "approval_id": None}), False, True),
    # Refund at exact threshold with null approval → denied
    ("test_banking_refund_at_threshold_null_approval",
     union(BASE, {"tool_name": "postgres.members.write",
                  "estimated_value_usd": 500,
                  "approval_id": None}), False, True),
    # L2 agent trying to call financial tool at any amount → denied (HC-3 wins)
    ("test_l2_agent_financial_tool_denied",
     union(BASE, {"agent_autonomy_tier": "L2", "estimated_value_usd": 1}), False, None),
]


def run():
    passed = failed = 0
    print("\nOPA Financial Tools Policy Simulation")
    print("=" * 65)
    for name, inp, exp_allow, exp_sup in TESTS:
        r = evaluate(inp)
        ok_allow = r["financial_tool_allow"] == exp_allow
        ok_sup = exp_sup is None or r["requires_supervisor"] == exp_sup
        if ok_allow and ok_sup:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(
                f"  FAIL  {name}: "
                f"allow={r['financial_tool_allow']} (expected {exp_allow}), "
                f"sup={r['requires_supervisor']} (expected {exp_sup}), "
                f"denial={r['denial_reason']!r}"
            )
    print("=" * 65)
    print(f"Result: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(run())
