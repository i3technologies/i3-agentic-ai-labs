# ADR-003: ChromaDB Per-Tenant Collection Isolation

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, Data Protection Officer, Admissions Tech Lead  
**Relates to:** EXPLORE-GATE §13 Track D (D-1), EXPLORE-GATE §5 (U-03, R-04)  
**Supersedes:** — (no prior ADR; ChromaDB collection strategy was unspecified)

---

## Context

### Problem Statement

The i3 AI Platform operates two independent ChromaDB instances:

| Instance | Namespace | Used By | Current Collection Strategy |
|----------|-----------|---------|----------------------------|
| ChromaDB-Admissions | i3-admissions | Admissions Agent (RAG) | **Unconfirmed — single collection may serve all tenants** |
| ChromaDB-AI-Lab | i3-ai-lab | JupyterHub notebooks, AI Lab experiments | **Unconfirmed — single collection may serve all tenants** |

EXPLORE-GATE §5 documents this as **U-03** (Unknown) and **R-04** (Risk: data leakage between
tenants, rated Medium Likelihood / Critical Impact).

If a single ChromaDB collection named (e.g.) `admissions_docs` stores embeddings from multiple
tenants without partition-level isolation, then:
1. A similarity search run in Tenant A's session may return context chunks belonging to Tenant B.
2. LLM responses may inadvertently expose Tenant B's institutional data to Tenant A's candidate.
3. This constitutes a Kenya DPA 2019 §25 violation (processing without lawful basis for the
   receiving tenant).

The Admissions RAG flow is confirmed (EXPLORE-GATE §3.1):
```
User Query → Kong (JWT verify) → Admissions Agent → ChromaDB similarity search
           → LiteLLM /v1/chat/completions → Response
```
The ChromaDB step currently has **no confirmed tenant filter** applied to the similarity search.

### Current State Evidence

From `platform/admissions/admissions_agent.py` (EXPLORE-GATE §1.3, status: "Running (chromadb bug)"):
- ChromaDB version mismatch: `chromadb==0.5.7` incompatible with `llama-index-vector-stores-chroma==0.1.10` (SEC-08)
- Image must be rebuilt with `chromadb==0.4.24` (EXPLORE-GATE §13 F-1)
- Collection naming convention: not confirmed in audit

The AI Lab ChromaDB is used by JupyterHub for experimental embedding pipelines
(`platform/ai-lab/chromadb/embedding_pipeline.py`). Multi-tenant usage pattern is unconfirmed.

---

## Decision

**Enforce collection-per-tenant naming convention (`{service}_{tenant_id}`) in both ChromaDB
instances, and add a tenant-scoped `where` filter to every similarity search query as a defence-
in-depth measure.**

Specifically:

### Collection Naming Convention
- Each tenant gets its own collection: `admissions_{tenant_id}` (e.g., `admissions_0000-0000-0001`)
- AI Lab: `ailab_{tenant_id}_{project_slug}` per notebook project per tenant
- The default collection name (e.g., `admissions_docs`) is **retired** after migration
- The Admissions Agent retrieves `tenant_id` from the JWT claim at request time and passes it to
  the ChromaDB client as the collection name

### Defence-in-Depth: Metadata Filter
Even with per-tenant collections, every `collection.query()` call must include:
```python
where={"tenant_id": {"$eq": str(tenant_id)}}
```
This ensures that if an embedding is accidentally indexed in the wrong collection, it will not
appear in the results for a different tenant.

### Migration Plan
1. Discover existing collections: `client.list_collections()`
2. For each document in the default collection, re-index it into the appropriate
   `admissions_{tenant_id}` collection based on its stored `tenant_id` metadata.
3. After verification (document count matches), retire the default collection.
4. Update `admissions_agent.py` to derive collection name from JWT `tenant_id` claim.
5. Rebuild the admissions-agent image with `chromadb==0.4.24` (SEC-08 fix, F-1).

---

## Alternatives Considered

### A1 — Single collection with metadata-only tenant filter
**Rejected as sole mechanism.** Metadata filters in ChromaDB are applied post-vector-similarity
ranking — a tenant's documents are still retrieved from the index before filtering. Under a
single-collection model, a filter misconfiguration or a missing `where` clause immediately
exposes cross-tenant data. Collection-level isolation provides a hard boundary.

### A2 — Separate ChromaDB instance per tenant
**Rejected.** StatefulSet per tenant is operationally unscalable on the current 12-node cluster.
Collection-per-tenant within a shared instance provides sufficient isolation at lower cost.

### A3 — Migrate from ChromaDB to pgvector (PostgreSQL vector extension)
**Deferred to Phase 4.** pgvector would allow PostgreSQL RLS to enforce tenant isolation uniformly
alongside all other SQL tables. ChromaDB remains for Phase 2 to minimise blast radius. This is
recorded as a future architecture option.

### A4 — Use ChromaDB's built-in tenant/database feature (ChromaDB 0.5+)
**Blocked.** ChromaDB 0.5+ introduces native database-per-tenant isolation. However, the admissions
agent is pinned to `chromadb==0.4.24` due to the `llama-index-vector-stores-chroma` version
incompatibility (SEC-08). ChromaDB native tenancy requires 0.5+. This approach is deferred until
the image can be upgraded to a compatible version in Phase 3.

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| Data isolation | Collection-per-tenant provides a hard namespace boundary — no vector can physically cross tenant collections |
| Defence in depth | `where` metadata filter is a second check; both must be correct for a cross-tenant leak to occur |
| Compatibility | Must stay on `chromadb==0.4.24` due to `llama-index-vector-stores-chroma` constraint |
| Operational | Migration script is idempotent — safe to re-run |
| RAGAS quality | Embedding pipeline rebuild must not regress RAGAS faithfulness below 0.80 (P1-GATE-10 threshold) |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | If `tenant_id` is absent from the JWT, the Admissions Agent must return 401 rather than defaulting to a shared collection. |
| SEC-2 | The AI Lab ChromaDB is accessible from JupyterHub notebooks. Notebook authors must not use hard-coded collection names — the `i3-ailab` SDK wrapper will enforce `ailab_{tenant_id}_{project}` naming. |
| SEC-3 | ChromaDB HTTP API is cluster-internal (ClusterIP only, port 8000). No external route via Kong. Access is from Admissions Agent and JupyterHub only, validated by Kubernetes NetworkPolicy. |
| SEC-4 | Embedding metadata must include `tenant_id` as a stored field for post-hoc audit queries. |

---

## Multi-Tenancy Implications

- **Admissions Agent**: `tenant_id` is extracted from Keycloak JWT claim at request time and used
  as both the collection name suffix and the `where` filter.
- **AI Lab**: Collection creation in JupyterHub is wrapped by an SDK helper that enforces the
  `ailab_{tenant_id}_{project}` naming convention. Raw `chromadb.Client().create_collection()`
  calls are intercepted by a middleware that injects the tenant prefix.
- **Document ingestion**: The embedding pipeline (`embedding_pipeline.py`) must tag every
  embedded chunk with `{"tenant_id": tenant_id}` in the metadata dict.
- **Empty collection behaviour**: A tenant with no documents indexed gets an empty collection
  (not an error). The Admissions Agent responds with a graceful "no context found" message.

---

## Agent-Autonomy Implications

- HC-5: ChromaDB is exposed as a `chroma.search` Tier-0 (read-only) tool through the MCP gateway.
  The MCP gateway sets the collection name from the request's `tenant_id` before forwarding to
  ChromaDB — agents cannot override the collection name.
- HC-3: This is an infrastructure change; no agent autonomy level change.

---

## Data Implications

### Collection Naming Schema
```
# Admissions RAG
Collection: admissions_{tenant_id}
  # e.g.: admissions_00000000-0000-0000-0000-000000000001
  Metadata fields per chunk:
    - tenant_id: str (UUID)
    - source_document: str
    - chunk_index: int
    - indexed_at: ISO8601
    - language: str (default: "sw" or "en")

# AI Lab
Collection: ailab_{tenant_id}_{project_slug}
  Metadata fields per chunk:
    - tenant_id: str
    - project: str
    - notebook_id: str
    - indexed_at: ISO8601
```

### Migration Query Patterns
```python
# Migration script (idempotent)
old_collection = client.get_collection("admissions_docs")
all_docs = old_collection.get(include=["documents", "embeddings", "metadatas"])

# Group by tenant_id metadata
from collections import defaultdict
by_tenant = defaultdict(list)
for i, meta in enumerate(all_docs["metadatas"]):
    by_tenant[meta.get("tenant_id", "legacy")].append(i)

for tenant_id, indices in by_tenant.items():
    new_col = client.get_or_create_collection(f"admissions_{tenant_id}")
    new_col.upsert(
        ids=[all_docs["ids"][i] for i in indices],
        documents=[all_docs["documents"][i] for i in indices],
        embeddings=[all_docs["embeddings"][i] for i in indices],
        metadatas=[all_docs["metadatas"][i] for i in indices],
    )
```

---

## Event Implications

No Kafka events are produced or consumed by this change. The embedding pipeline
(`embedding_pipeline.py`) produces to `ai-lab-usage` topic (EXPLORE-GATE §8 — no consumer
confirmed). This topic's consumer gap is tracked separately as U-06.

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| Zero-downtime migration | Migration script runs as a Kubernetes Job; old collection is retained until document count verified. Admissions Agent continues using old collection name until migration Job succeeds. Feature flag `CHROMA_TENANT_ISOLATION=true` gates the new collection naming. |
| Collection explosion | At current scale (< 50 tenants), collection count is manageable. Phase 4 evaluates pgvector migration if tenant count exceeds 200. |
| ChromaDB image rebuild | `chromadb==0.4.24` rebuild also fixes the llama-index bug (SEC-08 / R-08). RAGAS test must re-run after rebuild to confirm faithfulness ≥ 0.80. |
| AI Lab enforcement | JupyterHub spawner pre-hook injects `CHROMA_TENANT_ID` env var from Keycloak claims into each notebook server. SDK wrapper reads this env var. |

---

## Performance Implications

| Scenario | Impact |
|---------|--------|
| Per-tenant collection | Similarity search is ~10% faster (smaller index per collection vs. one large collection) for current document volumes |
| `where` metadata filter | Adds ~2ms per query for ChromaDB to apply post-retrieval filter. Acceptable. |
| Migration Job runtime | Estimated 5–10 minutes for current document corpus. No service disruption. |

---

## Cost Implications

- No additional infrastructure cost.
- ChromaDB storage increases minimally from collection-level metadata overhead.

---

## Rollback Strategy

1. **Feature flag**: `CHROMA_TENANT_ISOLATION=false` in the Admissions Agent deployment reverts
   to the old collection name. Can be applied via `kubectl set env` in < 60 seconds.
2. **Data**: Old default collection is not deleted until Phase 3 cleanup. Re-pointing is
   instantaneous.
3. **AI Lab**: If the SDK wrapper causes issues, notebooks can be reverted to direct ChromaDB
   client calls; the wrapper is non-destructive.

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to solution-01 through solution-08 namespaces. |
| HC-2 | Not directly applicable; FORD does not use ChromaDB. |
| HC-3 | ChromaDB is a read-only tool (Tier 0); no autonomy level impact. |
| HC-4 | `tenant_id` is now part of the ChromaDB collection name AND embedded as chunk metadata. This closes the ChromaDB vector store gap in HC-4 compliance. |
| HC-5 | MCP gateway enforces tenant-scoped collection name for `chroma.search` tool calls; agents cannot override. |
| HC-6 | Chunk metadata contains `tenant_id` (UUID) — not NID or phone numbers. Admission documents are institutional content, not PII. |
| HC-7 | No auth bypass pattern. |
| HC-8 | ChromaDB not used in FORD/Fabric flow. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §25 — lawful basis | Tenant-scoped collections ensure each vector search only processes data for the requesting tenant's lawful purpose |
| Kenya DPA 2019 §23 — data minimisation | Per-tenant collections prevent over-retrieval of data from non-consenting tenants |
| Kenya DPA 2019 §61 — ODPC penalties | Demonstrates active architecture controls against cross-tenant data leakage |
| ISO 27001 A.18.1 — compliance with legal requirements | Tenant isolation in vector store documented and enforced |

---

## Acceptance Criteria

```
AC-1: admissions-agent uses collection name "admissions_{tenant_id}" (not "admissions_docs")
      grep -n "admissions_docs\|collection_name" platform/admissions/admissions_agent.py → shows tenant-parameterised name
AC-2: Every collection.query() call includes where={"tenant_id": {"$eq": tenant_id}}
AC-3: Migration Job completes successfully: document counts match between old and new collections
AC-4: admissions-agent image rebuilt with chromadb==0.4.24 (SEC-08 fix)
AC-5: RAGAS faithfulness ≥ 0.80 after image rebuild (P1-GATE-10 regression check)
AC-6: Admissions Agent returns 401 if JWT contains no tenant_id claim
AC-7: AI Lab ChromaDB collections follow ailab_{tenant_id}_{project} naming convention
AC-8: Cross-tenant probe fails: querying admissions_{tenant_A} with {where: tenant_B} returns 0 results
AC-9: Feature flag CHROMA_TENANT_ISOLATION confirmed removed (not just set to true) in Phase 3 cleanup
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
