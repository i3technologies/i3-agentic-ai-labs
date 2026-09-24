# MCP Tool Contract — `consent_gate_check`

**Contract version:** 1.0  
**Status:** APPROVED — unblocks Campaign Agent, EvalOS Zuri, PMaaS Agent channel-level consent enforcement (U-07)  
**Hard-constraint refs:** HC-4, HC-5, HC-6  
**Upstream implementation:** [`platform/engage/consumers/kafka_consumers.py:_consent_allowed()`](../../platform/engage/consumers/kafka_consumers.py) · [`platform/pmaas/agents/campaign_agent.py:_consent_allowed()`](../../platform/pmaas/agents/campaign_agent.py) · Consent Service at `i3-consent` namespace

---

## 1. Purpose

Provides a **default-deny consent gate** as a first-class MCP tool so that every agent querying whether a data subject has consented to a given channel and purpose routes through the Consent Service via the MCP Gateway rather than making direct HTTP calls.

Currently the consent check is duplicated in at least three call sites:
- [`platform/engage/consumers/kafka_consumers.py:812`](../../platform/engage/consumers/kafka_consumers.py) — direct `httpx.get`
- [`platform/pmaas/agents/campaign_agent.py:201`](../../platform/pmaas/agents/campaign_agent.py) — direct `httpx.AsyncClient.get`
- [`platform/admissions/mcp/mcp_connectors.py`](../../platform/admissions/mcp/mcp_connectors.py) — proxied via gateway but no shared schema

This tool centralises the contract. The Consent Service endpoint is **never exposed** directly to agents; only the MCP Gateway holds the service-to-service credential.

---

## 2. Tool Registration Block

```yaml
name: consent_gate_check
version: "1.0"
risk_tier: 1          # reads from a stateful service; network I/O with default-deny semantics
side_effect_class: read-only
requires_human_gate: false
tenant_scoped: true   # HC-4: every query is scoped to a single tenant_id
autonomy_level: L1    # HC-3: permitted for L1 agents
```

---

## 3. Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "subject_id_hash",
    "channel",
    "purpose",
    "tenant_id",
    "caller_agent_id",
    "correlation_id"
  ],
  "additionalProperties": false,
  "properties": {
    "subject_id_hash": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "description": "HC-6: HMAC-SHA256 hex digest of the subject identifier, keyed with MEMBER_HMAC_SECRET from OpenBao. NEVER the raw NID or phone number."
    },
    "channel": {
      "type": "string",
      "enum": ["email", "sms", "whatsapp", "voice", "push"],
      "description": "Communication channel for which consent is being queried."
    },
    "purpose": {
      "type": "string",
      "enum": ["marketing", "transactional", "research", "data-processing"],
      "description": "Processing purpose per DPA 2019 §25 consent categories."
    },
    "tenant_id": {
      "type": "string",
      "format": "uuid",
      "description": "HC-4: Caller tenant UUID. Used for RLS query scope in the Consent Service."
    },
    "caller_agent_id": {
      "type": "string",
      "description": "Registered agent ID from the Agent Registry."
    },
    "correlation_id": {
      "type": "string",
      "description": "UUIDv7 from the caller's active request context for distributed tracing."
    }
  }
}
```

---

## 4. Output Schema

### 4a. Consent allowed

```json
{
  "allowed": true,
  "reason": "explicit_consent",
  "consent_record_id": "<uuidv7>",
  "expires_at": "2026-01-01T00:00:00Z",
  "audit_event_id": "<uuidv7>"
}
```

### 4b. Consent denied (default-deny path)

```json
{
  "allowed": false,
  "reason": "no_record_found",
  "consent_record_id": null,
  "expires_at": null,
  "audit_event_id": "<uuidv7>"
}
```

### 4c. Consent Service unreachable (circuit-breaker open)

```json
{
  "allowed": false,
  "reason": "service_unavailable",
  "consent_record_id": null,
  "expires_at": null,
  "audit_event_id": "<uuidv7>"
}
```

> **Contract obligation:** Callers MUST treat `allowed: false` as an absolute block regardless of `reason`. The MCP Gateway enforces default-deny at the policy layer; there is no override path available to agent code.

---

## 5. Authentication

| Layer | Mechanism |
|---|---|
| Agent → Gateway | Keycloak Bearer JWT (RS256) issued to the registered agent service account |
| Gateway → Consent Service | Service-to-service Keycloak client credential (`consent-gateway-sa`) — stored in OpenBao at `i3/consent/gateway-sa-secret` |
| Consent Service → Database | asyncpg pool with RLS; `SET LOCAL app.tenant_id` before every query |

The calling agent **never** receives the `consent-gateway-sa` secret or sees the Consent Service URL. This satisfies **Rule R2**.

---

## 6. Tenant Context

`tenant_id` is passed as a query parameter to the Consent Service and is used to:
1. Set `SET LOCAL app.tenant_id = $1` before every DB query (HC-4 RLS enforcement)
2. Include in the CloudEvent audit envelope (HC-4 event field)
3. Validate that the JWT's `tenant_id` claim matches the input — mismatches cause a `403 Forbidden` at the gateway layer

---

## 7. Idempotency

**Fully idempotent.** The same `(subject_id_hash, channel, purpose, tenant_id)` tuple always returns the same current consent state. Callers may retry on network error without side effects.

---

## 8. Approval Requirement

**None at call time.** `risk_tier: 1`, `side_effect_class: read-only`. No confirmation token required. The consent record creation workflow (which _sets_ consent) is governed by a separate write-path tool and requires explicit human gate.

---

## 9. Audit Event Emitted on Call

Every invocation emits one CloudEvent to topic `i3.consent.query.executed`:

```json
{
  "specversion": "1.0",
  "id": "<uuidv7>",
  "source": "i3/mcp-gateway/consent-gate-check",
  "type": "i3.consent.query.executed",
  "datacontenttype": "application/json",
  "time": "<rfc3339-utc>",
  "tenantid": "<caller-tenant-uuid>",
  "subject": "subject/<subject_id_hash>",
  "data": {
    "allowed": false,
    "channel": "email",
    "purpose": "marketing",
    "reason": "no_record_found",
    "caller_agent_id": "<agent-id>",
    "correlation_id": "<caller-correlation-id>"
  }
}
```

> `data.subject_id_hash` is included in `subject` only as a reference path; the raw subject identity is never reconstructed here.

---

## 10. Timeout & Retry Policy

| Parameter | Value | Rationale |
|---|---|---|
| Gateway timeout | **5 s** | Consent Service is in-cluster; 5 s matches current `httpx` timeout in direct callers |
| Client timeout | **6 s** | Gateway overhead budget |
| Retry policy | **2 retries, 100 ms exponential backoff (max 400 ms)** | Idempotent read; transient network jitter in the mesh |
| Circuit breaker | **Open after 3 consecutive failures in 10 s** | Returns `allowed: false / reason: service_unavailable` immediately when open — default-deny is preserved |

---

## 11. Upstream Credential Wrapped

| Secret | OpenBao path | Scope |
|---|---|---|
| Consent Service SA client secret | `i3/consent/gateway-sa-secret` | Read by MCP Gateway at startup via `vault kv get -field=secret i3/consent/gateway-sa-secret`; injected into in-cluster HTTP header |
| Consent DB password | `i3/consent/db-url` | **Only** accessible to the Consent Service pod — never surfaced to the gateway or agents |

No raw database credential is passed to any calling agent. The gateway exclusively holds `consent-gateway-sa-secret`. This satisfies **Rule R2**.

---

## 12. Callers That MUST Use This Tool (U-07)

| Agent / Consumer | Current direct call | Migration required |
|---|---|---|
| `engage-kafka-consumers-v1` | [`kafka_consumers.py:811`](../../platform/engage/consumers/kafka_consumers.py) — direct `httpx.get` | Replace with `consent_gate_check` MCP call |
| `pmaas-campaign-agent-v1` | [`campaign_agent.py:201`](../../platform/pmaas/agents/campaign_agent.py) — direct `httpx.AsyncClient.get` | Replace with `consent_gate_check` MCP call |
| `evalos-zuri-agent-v1` | Not yet confirmed — audit required | Must call `consent_gate_check` before any messaging action |

All three must remove direct `CONSENT_SERVICE_URL` environment variables from their pod specs once migrated; the URL is exclusively owned by the MCP Gateway.
