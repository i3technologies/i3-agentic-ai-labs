# MCP Tool Contract — `chromadb_tenant_search`

**Contract version:** 1.0  
**Status:** APPROVED — replaces direct ChromaDB access by Admissions Agent; enforces collection-per-tenant isolation (U-03)  
**Hard-constraint refs:** HC-4, HC-5  
**Upstream implementation:** [`platform/ai-lab/chromadb/embedding_pipeline.py`](../../platform/ai-lab/chromadb/embedding_pipeline.py) · [`platform/pmaas/agents/campaign_agent.py:retrieve_context()`](../../platform/pmaas/agents/campaign_agent.py) · ChromaDB HTTP API at `chromadb.i3-ai-lab.svc.cluster.local:8000`

---

## 1. Purpose

Provides **tenant-scoped vector search** over ChromaDB as a first-class MCP tool, enforcing a collection-per-tenant isolation model and routing embeddings through the LiteLLM proxy (R1-02).

The Campaign Agent already calls the gateway via `chroma.search` (see [`campaign_agent.py:237`](../../platform/pmaas/agents/campaign_agent.py)). The Admissions Agent, however, has no confirmed tenant-scoping at the collection level. This tool formalises the contract for all three callers and prohibits any agent from passing a raw `CHROMA_TOKEN` or the ChromaDB host URL.

### Collection Naming Convention

Every tenant receives its own isolated collection, named:

```
<base_collection>-<tenant_id_prefix_8>
```

Example: `pmaas-manifesto-0000000a` for tenant `0000000a-0000-0000-0000-000000000001`.

The MCP Gateway resolves the qualified collection name from `(collection_alias, tenant_id)` before calling ChromaDB. Agents pass the alias only.

---

## 2. Tool Registration Block

```yaml
name: chromadb_tenant_search
version: "1.0"
risk_tier: 0          # read-only vector query; no state mutation
side_effect_class: read-only
requires_human_gate: false
tenant_scoped: true   # HC-4: collection resolved per-tenant by gateway
autonomy_level: L0    # HC-3: pure retrieval; no write path
```

---

## 3. Input Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "query_text",
    "collection_alias",
    "tenant_id",
    "caller_agent_id",
    "correlation_id"
  ],
  "additionalProperties": false,
  "properties": {
    "query_text": {
      "type": "string",
      "maxLength": 4096,
      "description": "Natural language query string. MUST pass lobster_trap_check before this tool is called."
    },
    "collection_alias": {
      "type": "string",
      "enum": [
        "pmaas-manifesto",
        "i3-exam-corpus",
        "onboarding-docs",
        "admissions-corpus"
      ],
      "description": "Logical collection name. The gateway resolves the tenant-qualified physical collection name."
    },
    "n_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 5,
      "description": "Number of top-k documents to return."
    },
    "where_filter": {
      "type": "object",
      "description": "Optional ChromaDB `where` metadata filter. Tenant scoping is applied by the gateway and cannot be overridden here.",
      "additionalProperties": true
    },
    "tenant_id": {
      "type": "string",
      "format": "uuid",
      "description": "HC-4: Caller tenant UUID. Used to resolve the qualified collection name."
    },
    "caller_agent_id": {
      "type": "string",
      "description": "Registered agent ID from the Agent Registry."
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

### 4a. Results found

```json
{
  "documents": [
    {
      "id": "question-001",
      "content": "Domain: AI Strategy\nTopic: ...\nQuestion: ...",
      "distance": 0.142,
      "metadata": {
        "domain_name": "AI Strategy",
        "topic": "RAG pipelines"
      }
    }
  ],
  "total_found": 1,
  "collection_resolved": "i3-exam-corpus-0000000a",
  "audit_event_id": "<uuidv7>"
}
```

### 4b. No results / empty collection

```json
{
  "documents": [],
  "total_found": 0,
  "collection_resolved": "i3-exam-corpus-0000000a",
  "audit_event_id": "<uuidv7>"
}
```

### 4c. Collection not found for tenant

```json
{
  "error": "collection_not_found",
  "collection_alias": "pmaas-manifesto",
  "tenant_id": "<uuid>",
  "audit_event_id": "<uuidv7>"
}
```

> HTTP status `404`. Caller MUST NOT fall back to a cross-tenant collection.

---

## 5. Authentication

| Layer | Mechanism |
|---|---|
| Agent → Gateway | Keycloak Bearer JWT (RS256) issued to the registered agent service account |
| Gateway → ChromaDB | Bearer token from OpenBao at `i3/chromadb/gateway-token`; injected by gateway at call time using `TokenAuthClientProvider` |
| Gateway → LiteLLM (embed) | Virtual API key from OpenBao at `i3/litellm/api-key`; injected with `X-Agent-Id` header for Langfuse tracing |

The calling agent **never** receives `CHROMA_TOKEN`, the ChromaDB host URL, or the LiteLLM key. This satisfies **Rule R2**.

---

## 6. Tenant Context

The gateway enforces tenant isolation in two layers:

1. **Collection resolution:** `collection_alias` + `tenant_id` → physical collection name `<alias>-<tenant_id[:8]>`. A query against another tenant's collection is structurally impossible from the agent's perspective.
2. **Metadata filter injection:** The gateway appends `{"tenant_id": "<uuid>"}` to any `where_filter` before forwarding to ChromaDB, providing defence-in-depth if the collection naming convention is misconfigured.

---

## 7. Embedding Pipeline (How Vectors Are Produced)

Documents are ingested by the embedding pipeline Job ([`embedding_pipeline.py`](../../platform/ai-lab/chromadb/embedding_pipeline.py)):
- Embedding model: `nomic-embed-text:v1.5` via LiteLLM `embed` alias (R1-02 — no direct Ollama calls)
- Dimensions: 768
- Distance metric: cosine (`hnsw:space: cosine`)

The MCP tool generates the query embedding at search time using the same LiteLLM route, ensuring vector space consistency.

---

## 8. Idempotency

**Fully idempotent.** Vector search is a pure read. The same query always produces the same ranked result set (deterministic HNSW traversal for a frozen index). Callers may retry without consequence.

---

## 9. Approval Requirement

**None.** `risk_tier: 0`, `side_effect_class: read-only`. No confirmation token required.

---

## 10. Audit Event Emitted on Call

Every invocation emits one CloudEvent to topic `i3.rag.search.executed`:

```json
{
  "specversion": "1.0",
  "id": "<uuidv7>",
  "source": "i3/mcp-gateway/chromadb-tenant-search",
  "type": "i3.rag.search.executed",
  "datacontenttype": "application/json",
  "time": "<rfc3339-utc>",
  "tenantid": "<caller-tenant-uuid>",
  "subject": "collection/<collection_alias>",
  "data": {
    "collection_alias": "pmaas-manifesto",
    "collection_resolved": "pmaas-manifesto-0000000a",
    "n_results_requested": 5,
    "n_results_returned": 5,
    "caller_agent_id": "<agent-id>",
    "correlation_id": "<caller-correlation-id>"
  }
}
```

> `data.query_text` is **never** logged — only the result count and collection name. This prevents inadvertent PII logging through search queries.

---

## 11. Timeout & Retry Policy

| Parameter | Value | Rationale |
|---|---|---|
| Embedding call timeout | **30 s** | Matches existing LiteLLM call timeout in [`embedding_pipeline.py:99`](../../platform/ai-lab/chromadb/embedding_pipeline.py) |
| ChromaDB query timeout | **10 s** | In-cluster; cosine HNSW on 50k-doc corpus |
| Total gateway timeout | **45 s** | Embed + query + serialisation |
| Client timeout | **50 s** | Calling agent budget |
| Retry policy | **2 retries, 200 ms exponential backoff** | Idempotent read |
| Circuit breaker | **Open after 3 consecutive failures in 30 s** | Returns `error: service_unavailable`; callers proceed without RAG context (graceful degradation) |

---

## 12. Upstream Credentials Wrapped

| Secret | OpenBao path | Scope |
|---|---|---|
| ChromaDB token | `i3/chromadb/gateway-token` | Read by MCP Gateway pod only |
| LiteLLM virtual key | `i3/litellm/api-key` | Read by MCP Gateway pod only; used for embed call with `X-Agent-Id: mcp-gateway` for Langfuse tracing |
| ChromaDB host | `i3/chromadb/host` (or env var in gateway pod spec) | Not exposed to agents |

No raw credential is passed to any calling agent. This satisfies **Rule R2**.

---

## 13. Pre-call Obligation

Before calling `chromadb_tenant_search`, every agent MUST first call `lobster_trap_check` on the `query_text`. The MCP Gateway enforces this ordering via the tool dependency graph; a call to `chromadb_tenant_search` that arrives without a `correlation_id` matching a prior clean `lobster_trap_check` verdict within the same session is rejected with `HTTP 412 Precondition Failed`.

---

## 14. Callers (U-03)

| Agent | Current state | Migration required |
|---|---|---|
| `pmaas-campaign-agent-v1` | Already calls `chroma.search` via gateway ([`campaign_agent.py:237`](../../platform/pmaas/agents/campaign_agent.py)) | Rename tool to `chromadb_tenant_search`; add `tenant_id` parameter |
| `admissions-agent-v1` | Direct ChromaDB access suspected — audit required | Remove `CHROMA_TOKEN` from pod spec; replace with `chromadb_tenant_search` tool call |
| `evalos-zuri-agent-v1` | Not confirmed — audit required | Must not bypass gateway for any vector search |
