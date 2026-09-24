# i3 Agent Mesh Architect — Supplementary Rules

These rules apply only when the i3-mesh-architect mode is active.
They supplement the global architecture standards in `.bob/rules/02-architecture-standards.md`.

---

## CloudEvent 9-Field Envelope (Mandatory)

Every Kafka event and inter-service message MUST carry all 9 fields:

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `specversion` | string | `"1.0"` | Always exactly `"1.0"` |
| `id` | string (UUIDv7) | `"01926..."` | Use UUIDv7 for time-ordered PKs |
| `source` | URI string | `"i3/admissions-agent"` | Service identifier |
| `type` | string | `"i3.admissions.application.created"` | Reverse-DNS dot notation |
| `datacontenttype` | string | `"application/json"` | Always JSON |
| `time` | RFC3339 | `"2025-07-01T12:00:00Z"` | UTC timestamp |
| `tenantid` | UUID string | `"00000000-0000-0000-..."` | HC-4: never absent |
| `subject` | string | `"application/abc123"` | Resource path |
| `data` | object | `{ ... }` | Domain payload |

HC-4 enforcement: `tenantid` must be a valid UUID and must never be null, empty, or absent.

---

## Agent Manifest Required Fields

Every agent registered in the Agent Registry must include:

```yaml
name: <agent-name>
version: "1.0"
autonomy_level: L0   # or L1 — never L2 or L3 (HC-3)
risk_tier: low       # low | medium | high
side_effect_class: read-only  # read-only | propose | execute-gated
allowed_tools:
  - <tool-name>
cost_budget_tokens: 50000
```

HC-3: Any manifest with `autonomy_level: L2` or `L3` must be rejected and the task blocked.

---

## DDD Microservice Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Namespace | `i3-<domain>` | `i3-consent` |
| Service name | `<domain>-service` | `consent-service` |
| Kafka topic | `i3.<domain>.<entity>.<event>` | `i3.consent.record.created` |
| DB table | `<entity>_records` (snake_case) | `consent_records` |
| Python module | `platform/<service-name>/` | `platform/consent-service/` |

---

## MCP Tool Specification Requirements

Every tool registered in the MCP Tool Gateway must declare:
- `risk_tier`: `low`, `medium`, or `high`
- `side_effect_class`: `read-only`, `propose`, or `execute-gated`
- `requires_human_gate`: `true` for any `execute-gated` tool
- `tenant_scoped`: `true` for all tools that access tenant data
