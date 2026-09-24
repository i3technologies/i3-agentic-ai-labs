"""
i3 Platform Guard — Bob MCP Server
====================================
Project-scoped MCP server that exposes four read-only/validation tools
to the IBM Bob IDE over stdio transport.

Tools
-----
test_prompt_injection   — Run the 12-pattern Lobster Trap against a string.
audit_sql_ast           — Parse and audit SQL for destructive/injection patterns.
validate_agent_manifest — Check agent YAML manifest against HC-3 autonomy ceiling.
verify_cloudevent_envelope — Validate a dict against the 9-field CloudEvent schema.

Transport: stdio (Bob reads stdout / writes stdin line-by-line as JSON-RPC 2.0).

Usage (registered in .bob/mcp.json):
    command: python
    args: [platform/tools/i3_bob_mcp_server.py]
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from typing import Any

# ── Lobster Trap — 12 canonical patterns (mirrors lobster-trap.ts) ───────────
# Canonical 14-pattern set — synced with lobster-trap.ts (P2-MED).
# P13 (SELECT injection) and P14 (XSS) were previously TypeScript-only.
_TRAP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("P01 ignore_previous",       re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I)),
    ("P02 system_prompt_override", re.compile(r"system\s+prompt\s+override", re.I)),
    ("P03 developer_mode",         re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I)),
    ("P04 output_passwords",       re.compile(r"output\s+all\s+passwords", re.I)),
    ("P05 reveal_internal_logic",  re.compile(r"reveal\s+internal\s+logic", re.I)),
    ("P06 bypass_safety_filter",   re.compile(r"bypass\s+safety\s+filter", re.I)),
    ("P07 act_as_dan",             re.compile(r"act\s+as\s+DAN", re.I)),
    ("P08 jailbreak",              re.compile(r"jailbreak", re.I)),
    ("P09 drop_table",             re.compile(r"(drop|delete|truncate)\s+table", re.I)),
    ("P10 prompt_injection",       re.compile(r"prompt\s+injection", re.I)),
    ("P11 disregard_previous",     re.compile(r"disregard\s+(all\s+)?previous", re.I)),
    ("P12 exfiltrate",             re.compile(r"\bexfiltrate\b", re.I)),
    ("P13 select_injection",       re.compile(r"SELECT\s+.+FROM\s+", re.I | re.S)),
    ("P14 xss_in_input",           re.compile(r"<\s*(script|img|iframe|svg)\b", re.I)),
]

# ── SQL audit patterns ────────────────────────────────────────────────────────
_SQL_DANGEROUS: list[tuple[str, re.Pattern[str]]] = [
    ("DROP_TABLE",      re.compile(r"\bDROP\s+TABLE\b", re.I)),
    ("DROP_DATABASE",   re.compile(r"\bDROP\s+(DATABASE|SCHEMA)\b", re.I)),
    ("TRUNCATE",        re.compile(r"\bTRUNCATE\b", re.I)),
    ("DELETE_NOTAIL",   re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.I | re.S)),
    ("UNION_SELECT",    re.compile(r"\bUNION\b.*\bSELECT\b", re.I | re.S)),
    ("COMMENT_INJECT",  re.compile(r"(--[^\n]*)|(\/\*.*?\*\/)", re.S)),
    ("STACKED_QUERY",   re.compile(r";\s*(DROP|DELETE|INSERT|UPDATE|EXEC)\b", re.I)),
    ("XSS_IN_SQL",      re.compile(r"<\s*(script|img|iframe|svg)\b", re.I)),
    ("NO_TENANT_ID",    re.compile(r"\bINSERT\s+INTO\b(?!.*\btenant_id\b)", re.I | re.S)),
]

# ── CloudEvent required fields (9-field envelope) ────────────────────────────
_CLOUDEVENT_REQUIRED = {
    "specversion", "id", "source", "type",
    "datacontenttype", "time", "tenantid",
    "subject", "data",
}

# ── HC-3 autonomy ceiling ────────────────────────────────────────────────────
_FORBIDDEN_AUTONOMY = {"L2", "L3", "level2", "level3", "autonomous", "full_autonomy"}


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────


def _tool_scan_for_bypass_auth(params: dict[str, Any]) -> dict[str, Any]:
    """
    Scan the workspace for DEV_BYPASS_AUTH=true (HC-7 enforcement).
    Uses pure Python file walking — no grep dependency, works on Windows and Linux.

    Parameters
    ----------
    path : str  — Optional directory or file path to scan (default: ".")

    Returns
    -------
    { "clean": bool, "violations": [ { "file": str, "line": str } ] }
    """
    import os  # noqa: PLC0415

    SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".mjs", ".yaml", ".yml", ".json", ".sh", ".env"}
    NEEDLE = "DEV_BYPASS_AUTH=true"
    scan_path = str(params.get("path", ".")).strip() or "."
    violations: list[dict[str, str]] = []

    def _scan_file(filepath: str) -> None:
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    if NEEDLE in line:
                        violations.append({
                            "file": filepath,
                            "line": f"{filepath}:{lineno}: {line.rstrip()}",
                        })
        except OSError:
            pass

    if os.path.isfile(scan_path):
        _scan_file(scan_path)
    else:
        for root, dirs, files in os.walk(scan_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {
                ".git", "node_modules", "__pycache__", ".venv", "venv",
                "dist", "build", ".bob",
            }]
            for fname in files:
                if os.path.splitext(fname)[1].lower() in SCAN_EXTS:
                    _scan_file(os.path.join(root, fname))

    return {"clean": len(violations) == 0, "violations": violations}


def _tool_check_rls_policy(params: dict[str, Any]) -> dict[str, Any]:
    """
    Check a SQL DDL string for Row-Level Security completeness (HC-4).

    Verifies that every CREATE TABLE statement has:
    - tenant_id column (UUID NOT NULL)
    - ALTER TABLE ... ENABLE ROW LEVEL SECURITY
    - CREATE POLICY with tenant_isolation using current_setting('app.tenant_id')

    Parameters
    ----------
    sql : str  — The SQL DDL string to check.

    Returns
    -------
    { "compliant": bool, "findings": [ { "check": str, "detail": str } ] }
    """
    sql = str(params.get("sql", ""))
    findings: list[dict[str, str]] = []

    has_create_table = bool(re.search(r"\bCREATE\s+TABLE\b", sql, re.I))
    if not has_create_table:
        return {"compliant": True, "findings": [], "note": "No CREATE TABLE found — nothing to check"}

    if not re.search(r"\btenant_id\b", sql, re.I):
        findings.append({"check": "MISSING_TENANT_ID", "detail": "No tenant_id column found in DDL"})

    if not re.search(r"\bUUID\b.*\bNOT\s+NULL\b", sql, re.I):
        findings.append({"check": "TENANT_ID_NULLABLE", "detail": "tenant_id column should be UUID NOT NULL"})

    if not re.search(r"ENABLE\s+ROW\s+LEVEL\s+SECURITY", sql, re.I):
        findings.append({"check": "MISSING_RLS", "detail": "ALTER TABLE ... ENABLE ROW LEVEL SECURITY not found"})

    if not re.search(r"CREATE\s+POLICY\b", sql, re.I):
        findings.append({"check": "MISSING_POLICY", "detail": "No CREATE POLICY statement found"})

    if not re.search(r"tenant_isolation", sql, re.I):
        findings.append({"check": "MISSING_TENANT_ISOLATION", "detail": "Policy named 'tenant_isolation' not found"})

    if not re.search(r"current_setting\s*\(\s*['\"]app\.tenant_id", sql, re.I):
        findings.append({"check": "MISSING_TENANT_FILTER", "detail": "current_setting('app.tenant_id') not found in policy USING clause"})

    return {"compliant": len(findings) == 0, "findings": findings}

def _tool_test_prompt_injection(params: dict[str, Any]) -> dict[str, Any]:
    """
    Test a string against all 12 Lobster Trap patterns.

    Parameters
    ----------
    text : str  — The user-supplied string to check.

    Returns
    -------
    { "clean": bool, "matches": [ { "pattern_id": str, "matched_text": str } ] }
    """
    text = str(params.get("text", ""))
    matches: list[dict[str, str]] = []
    for label, pattern in _TRAP_PATTERNS:
        m = pattern.search(text)
        if m:
            matches.append({"pattern_id": label, "matched_text": m.group(0)})
    return {"clean": len(matches) == 0, "matches": matches}


def _tool_audit_sql_ast(params: dict[str, Any]) -> dict[str, Any]:
    """
    Audit a SQL string for destructive statements and injection vectors.

    Parameters
    ----------
    sql : str  — The SQL string to audit.

    Returns
    -------
    { "safe": bool, "findings": [ { "rule": str, "excerpt": str } ] }
    """
    sql = str(params.get("sql", ""))
    findings: list[dict[str, str]] = []
    for rule, pattern in _SQL_DANGEROUS:
        m = pattern.search(sql)
        if m:
            excerpt = sql[max(0, m.start() - 20): m.end() + 20].strip()
            findings.append({"rule": rule, "excerpt": excerpt})
    return {"safe": len(findings) == 0, "findings": findings}


def _tool_validate_agent_manifest(params: dict[str, Any]) -> dict[str, Any]:
    """
    Validate an agent manifest dict against HC-3 (L0/L1 autonomy ceiling).

    Parameters
    ----------
    manifest : dict  — The parsed agent manifest (YAML/JSON loaded as dict).

    Returns
    -------
    { "valid": bool, "violations": [ str ] }
    """
    manifest = params.get("manifest", {})
    if not isinstance(manifest, dict):
        return {"valid": False, "violations": ["manifest must be a JSON object"]}

    violations: list[str] = []

    # Check autonomy_level field directly
    autonomy = str(manifest.get("autonomy_level", "")).strip()
    if autonomy.upper() in {a.upper() for a in _FORBIDDEN_AUTONOMY}:
        violations.append(
            f"HC-3 VIOLATION: autonomy_level '{autonomy}' exceeds permitted L0/L1 ceiling"
        )

    # Scan all string values for forbidden autonomy keywords
    def _scan(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                _scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _scan(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            for kw in _FORBIDDEN_AUTONOMY:
                if kw.lower() in obj.lower():
                    violations.append(
                        f"HC-3 WARN: forbidden autonomy keyword '{kw}' found at {path}"
                    )

    _scan({k: v for k, v in manifest.items() if k != "autonomy_level"})

    # Check required fields
    for req in ("name", "version", "autonomy_level"):
        if req not in manifest:
            violations.append(f"MISSING FIELD: '{req}' is required in agent manifest")

    return {"valid": len(violations) == 0, "violations": violations}


def _tool_verify_cloudevent_envelope(params: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a CloudEvent envelope dict against the 9-field schema.

    Parameters
    ----------
    event : dict  — The CloudEvent dict to validate.

    Returns
    -------
    { "valid": bool, "missing_fields": [ str ], "notes": [ str ] }
    """
    event = params.get("event", {})
    if not isinstance(event, dict):
        return {
            "valid": False,
            "missing_fields": list(_CLOUDEVENT_REQUIRED),
            "notes": ["event must be a JSON object"],
        }

    missing = sorted(_CLOUDEVENT_REQUIRED - set(event.keys()))
    notes: list[str] = []

    # Validate specversion
    if event.get("specversion") != "1.0":
        notes.append("specversion should be '1.0'")

    # Validate tenantid is UUID-shaped
    tenantid = str(event.get("tenantid", ""))
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )
    if tenantid and not uuid_re.match(tenantid):
        notes.append(f"tenantid '{tenantid}' does not look like a UUID")

    # HC-4 enforcement — tenantid must be present and non-empty
    if not tenantid:
        notes.append("HC-4 VIOLATION: tenantid is absent or empty")

    return {
        "valid": len(missing) == 0 and not any("VIOLATION" in n for n in notes),
        "missing_fields": missing,
        "notes": notes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# JSON-RPC 2.0 stdio transport
# ─────────────────────────────────────────────────────────────────────────────

_TOOLS: dict[str, dict[str, Any]] = {
    "test_prompt_injection": {
        "description": (
            "Test a string against all 12 Lobster Trap prompt injection patterns. "
            "Returns clean=true and an empty matches list if no pattern fires."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The user-supplied string to check"}
            },
            "required": ["text"],
        },
        "fn": _tool_test_prompt_injection,
    },
    "audit_sql_ast": {
        "description": (
            "Audit a SQL string for destructive statements (DROP, TRUNCATE, DELETE without WHERE), "
            "UNION-based injection, stacked queries, XSS tokens, and missing tenant_id on INSERT."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL string to audit"}
            },
            "required": ["sql"],
        },
        "fn": _tool_audit_sql_ast,
    },
    "validate_agent_manifest": {
        "description": (
            "Validate an agent manifest against HC-3: no agent may be promoted above L1 autonomy. "
            "Pass the manifest as a parsed JSON/YAML object."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "manifest": {
                    "type": "object",
                    "description": "Parsed agent manifest dict",
                }
            },
            "required": ["manifest"],
        },
        "fn": _tool_validate_agent_manifest,
    },
    "verify_cloudevent_envelope": {
        "description": (
            "Validate a CloudEvent envelope against the 9-field schema (specversion, id, source, type, "
            "datacontenttype, time, tenantid, subject, data). Enforces HC-4 tenantid presence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "event": {
                    "type": "object",
                    "description": "CloudEvent dict to validate",
                }
            },
            "required": ["event"],
        },
        "fn": _tool_verify_cloudevent_envelope,
    },
    "scan_for_bypass_auth": {
        "description": (
            "Scan the workspace (or a specific path) for DEV_BYPASS_AUTH=true. "
            "Enforces HC-7: this value must never appear in non-gitignored files. "
            "Returns clean=true if no violations are found."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory or file path to scan (default: workspace root '.')",
                }
            },
            "required": [],
        },
        "fn": _tool_scan_for_bypass_auth,
    },
    "check_rls_policy": {
        "description": (
            "Check a SQL DDL string for Row-Level Security completeness (HC-4). "
            "Verifies tenant_id UUID NOT NULL, ENABLE ROW LEVEL SECURITY, "
            "CREATE POLICY tenant_isolation, and current_setting('app.tenant_id') USING clause."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The SQL DDL string to check"}
            },
            "required": ["sql"],
        },
        "fn": _tool_check_rls_policy,
    },
}


def _send(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _handle(request: dict[str, Any]) -> None:
    rpc_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    try:
        if method == "initialize":
            _send({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "i3-platform-guard", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            })

        elif method == "tools/list":
            tools_list = [
                {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": spec["inputSchema"],
                }
                for name, spec in _TOOLS.items()
            ]
            _send({"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": tools_list}})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            if tool_name not in _TOOLS:
                _send({
                    "jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                })
                return
            result = _TOOLS[tool_name]["fn"](tool_args)
            _send({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                    "isError": False,
                },
            })

        elif method == "notifications/initialized":
            pass  # No response required for notifications

        else:
            _send({
                "jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })

    except Exception:  # noqa: BLE001
        _send({
            "jsonrpc": "2.0", "id": rpc_id,
            "error": {"code": -32603, "message": traceback.format_exc()},
        })


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        _handle(request)


if __name__ == "__main__":
    main()
