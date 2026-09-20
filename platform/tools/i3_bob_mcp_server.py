#!/usr/bin/env python3
"""
i3 Platform Architectural Modernization & Safety MCP Server for IBM Bob
Exposes direct platform verification, tenant audit, and firewall tools.
"""

import os
import re
import json
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("i3-Platform-Modernization-Core")

LOBSTER_TRAP_12 = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"system\s+prompt\s+override",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"output\s+all\s+passwords",
    r"reveal\s+internal\s+logic",
    r"bypass\s+safety\s+filter",
    r"act\s+as\s+DAN",
    r"jailbreak",
    r"drop\s+table",
    r"prompt\s+injection",
    r"disregard\s+(all\s+)?previous",
    r"\bexfiltrate\b"
]

@mcp.tool()
def test_prompt_injection(prompt: str) -> str:
    """Evaluates text against the 12 canonical i3 Lobster Trap firewall rules."""
    matched = [pat for pat in LOBSTER_TRAP_12 if re.search(pat, prompt, re.IGNORECASE)]
    if matched:
        return json.dumps({"verdict": "BLOCKED", "matched_rules": matched})
    return json.dumps({"verdict": "CLEAN", "matched_rules": []})

@mcp.tool()
def audit_sql_ast(ddl_or_query: str) -> str:
    """Verifies that queries/DDL enforce tenant isolation (tenant_id) and avoid SQL injection anti-patterns."""
    findings = []
    normalized = ddl_or_query.upper()

    if "CREATE TABLE" in normalized and "TENANT_ID" not in normalized:
        findings.append("Missing tenant_id column in table definition (violates Principle P7).")

    if "CREATE TABLE" in normalized and "ROW LEVEL SECURITY" not in normalized:
        findings.append("Table created without ROW LEVEL SECURITY enabled.")

    if re.search(r"ILIKE\s+\$\{\s*LEN\(", ddl_or_query, re.IGNORECASE):
        findings.append("Fragile dynamic query indexing pattern (M-5) detected.")

    return json.dumps({
        "compliant": len(findings) == 0,
        "findings": findings
    })

@mcp.tool()
def validate_agent_manifest(manifest_content: str) -> str:
    """Validates an Agent Registry YAML manifest against Autonomy Tiers (L0-L3) and risk constraints."""
    try:
        import yaml
        data = yaml.safe_load(manifest_content)
    except Exception as e:
        return json.dumps({"valid": False, "error": f"YAML Parse Error: {str(e)}"})

    errors = []
    tier = data.get("autonomy_tier")
    if tier not in ["L0", "L1", "L2", "L3"]:
        errors.append(f"Invalid autonomy tier '{tier}'. Must be L0, L1, L2, or L3.")

    if tier in ["L0", "L1"]:
        for tool in data.get("allowed_tools", []):
            if any(side_effect in tool.lower() for side_effect in ["write", "produce", "delete", "transfer"]):
                errors.append(f"Autonomy {tier} cannot contain mutating tool '{tool}' without a human gate.")

    if "cost_budget_tokens" not in data:
        errors.append("Missing mandatory 'cost_budget_tokens' budget allocation.")

    return json.dumps({
        "valid": len(errors) == 0,
        "tier": tier,
        "errors": errors
    })

@mcp.tool()
def verify_cloudevent_envelope(event_json: str) -> str:
    """Validates that a JSON event payload satisfies the mandatory 9-field i3 CloudEvent envelope."""
    required_fields = [
        "event_id", "event_type", "event_version", "tenant_id",
        "correlation_id", "causation_id", "actor", "timestamp", "payload"
    ]
    try:
        data = json.loads(event_json)
    except Exception as e:
        return json.dumps({"valid": False, "error": "Invalid JSON format"})

    missing = [f for f in required_fields if f not in data]
    return json.dumps({
        "valid": len(missing) == 0,
        "missing_fields": missing
    })

if __name__ == "__main__":
    mcp.run()