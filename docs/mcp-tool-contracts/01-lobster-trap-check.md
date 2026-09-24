# MCP Tool Contract — `lobster_trap_check`

**Contract version:** 1.0  
**Status:** APPROVED — unblocks Campaign Agent, EvalOS Zuri, PMaaS Agent registration (U-09)  
**Hard-constraint refs:** HC-5, HC-3  
**Upstream implementation:** [`platform/tools/i3_bob_mcp_server.py:_TRAP_PATTERNS`](../../platform/tools/i3_bob_mcp_server.py) · [`onboarding-agent/src/security/lobster-trap.ts`](../../onboarding-agent/src/security/lobster-trap.ts)

---

## 1. Purpose

Provides a **stateless prompt-injection firewall** as a first-class MCP tool so that every registered agent must pass user-supplied text through the canonical 14-pattern Lobster Trap before the text is assembled into a prompt or stored as a Kafka payload.

Previously each service maintained its own local copy of the regex set, creating a parity-drift risk (logged as `P2-MED`). This tool replaces all local copies with a single authoritative call to the MCP Gateway. Callers receive a structured verdict; they MUST block on `clean: false`.

---

## 2. Tool Registration Block

```yaml
name: lobster_trap_check
version: "1.0"
risk_tier: 0          # read-only classification; no network I/O, no state mutation
side_effect_class: read-only
requires_human_gate: false
tenant_scoped: false  # pattern matching is content-only; tenant_id passed for audit only
autonomy_level: L0    # HC-3: never promoted beyond L0 for a firewall gate
```

---

## 3. Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["text", "caller_agent_id", "tenant_id", "correlation_id"],
  "additionalProperties": false,
  "properties": {
    "text": {
      "type": "string",
      "maxLength": 32768,
      "description": "Raw user-supplied string to be tested against the 14-pattern set."
    },
    "caller_agent_id": {
      "type": "string",
      "description": "Registered agent ID from the Agent Registry (e.g. pmaas-campaign-agent-v1)."
    },
    "tenant_id": {
      "type": "string",
      "format": "uuid",
      "description": "HC-4: caller tenant UUID — present in every audit event."
    },
    "correlation_id": {
      "type": "string",
      "description": "UUIDv7 from the caller's active request context."
    }
  }
}
```

---

## 4. Output Schema

### 4a. Clean input

```json
{
  "clean": true,
  "matches": [],
  "patterns_checked": 14,
  "audit_event_id": "<uuidv7>"
}
```

### 4b. Injection detected

```json
{
  "clean": false,
  "matches": [
    {
      "pattern_id": "P01 ignore_previous",
      "matched_text": "ignore all previous instructions"
    }
  ],
  "patterns_checked": 14,
  "audit_event_id": "<uuidv7>"
}
```

> **Contract obligation:** Callers MUST treat `clean: false` as a hard block. The MCP Gateway enforces this at the policy layer; a caller that proceeds after `clean: false` is rejected by HC-5 policy enforcement.

---

## 5. Authentication

| Layer | Mechanism |
|---|---|
| Agent → Gateway | Keycloak Bearer JWT (RS256) issued to the registered agent service account |
| Gateway → Tool | Internal in-process call — no additional credential required |
| Credential in OpenBao | None required (stateless regex evaluation) |

The MCP Gateway verifies the JWT, extracts `tenant_id` and `sub`, and injects them into the tool invocation log before calling the tool function.

---

## 6. Tenant Context

`tenant_id` is **not** used for data filtering (the tool is content-only) but is **mandatory** for the audit event (HC-4). The gateway rejects any invocation where `tenant_id` is absent, null, or not a valid UUID.

---

## 7. Idempotency

**Fully idempotent.** The same text string always produces the same `clean` verdict. Callers may retry without consequence.

---

## 8. Approval Requirement

**None.** `risk_tier: 0`, `side_effect_class: read-only`. No human gate, no confirmation token.

---

## 9. Audit Event Emitted on Call

Every invocation — clean or not — emits one CloudEvent to topic `i3.security.firewall.checked`:

```json
{
  "specversion": "1.0",
  "id": "<uuidv7>",
  "source": "i3/mcp-gateway/lobster-trap-check",
  "type": "i3.security.firewall.checked",
  "datacontenttype": "application/json",
  "time": "<rfc3339-utc>",
  "tenantid": "<caller-tenant-uuid>",
  "subject": "agent/<caller_agent_id>",
  "data": {
    "clean": true,
    "patterns_checked": 14,
    "match_count": 0,
    "correlation_id": "<caller-correlation-id>",
    "caller_agent_id": "<agent-id>"
  }
}
```

> `data.text` is **never** logged — only the verdict and match count. This prevents credential or PII leakage through audit logs.

---

## 10. Timeout & Retry Policy

| Parameter | Value | Rationale |
|---|---|---|
| Gateway timeout | **100 ms** | Pure in-process regex; any latency > 100 ms indicates a gateway fault |
| Client timeout | **500 ms** | Network + queue budget for the calling agent |
| Retry policy | **2 retries, 50 ms fixed backoff** | Idempotent; safe to retry |
| Circuit breaker | N/A — tool is in-process | No remote dependency to break |

---

## 11. Upstream Credential Wrapped

**None.** The 14-pattern set is compiled in-process from the canonical list in [`platform/tools/i3_bob_mcp_server.py:_TRAP_PATTERNS`](../../platform/tools/i3_bob_mcp_server.py) (lines 32–47). No external API key, database credential, or network call is required or permitted. This satisfies **Rule R2** (no raw credential exposure).

---

## 12. Pattern Parity Obligation

The MCP Gateway's runtime copy of `_TRAP_PATTERNS` MUST be kept in sync with:
- [`platform/tools/i3_bob_mcp_server.py`](../../platform/tools/i3_bob_mcp_server.py) — Python canonical source
- [`onboarding-agent/src/security/lobster-trap.ts`](../../onboarding-agent/src/security/lobster-trap.ts) — TypeScript mirror

Use the `sync-lobster-trap` skill before any pattern modification. Pattern count MUST remain at exactly **14**.

---

## 13. Callers That MUST Use This Tool Before Registration

| Agent | Registration gap | Blocking issue |
|---|---|---|
| `pmaas-campaign-agent-v1` | U-09 | Currently uses a local copy in [`platform/pmaas/agents/campaign_agent.py:131`](../../platform/pmaas/agents/campaign_agent.py) |
| `evalos-zuri-agent-v1` | U-09 | No shared firewall call confirmed |
| `engage-kafka-consumers-v1` | U-09 | No shared firewall call confirmed |

All three must replace local `_LOBSTER_TRAP_PATTERNS` lists with a call to this tool and receive `clean: true` before their agent manifests are accepted by the Agent Registry.
