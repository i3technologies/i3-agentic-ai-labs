# MCP Tool Contracts — i3 Agent Mesh

**Phase:** Phase 2 — PLN-04  
**Status:** All four contracts APPROVED  
**Last updated:** 2025-07

---

## Summary Table

| # | Tool | risk_tier | side_effect_class | Unblocks | Contract |
|---|------|-----------|-------------------|----------|----------|
| 1 | `lobster_trap_check` | 0 | read-only | U-09 (Campaign Agent, EvalOS Zuri, PMaaS Agent registration) | [01-lobster-trap-check.md](01-lobster-trap-check.md) |
| 2 | `consent_gate_check` | 1 | read-only | U-07 (all three channel-messaging callers) | [02-consent-gate-check.md](02-consent-gate-check.md) |
| 3 | `chromadb_tenant_search` | 0 | read-only | U-03 (Admissions Agent direct ChromaDB removal) | [03-chromadb-tenant-search.md](03-chromadb-tenant-search.md) |
| 4 | `kafka_event_publish` | 1 | reversible_write | All agents requiring Kafka writes | [04-kafka-event-publish.md](04-kafka-event-publish.md) |

---

## Dependency Order (Call Sequence)

For any agent endpoint that accepts user text and produces a Kafka event, the mandatory call sequence is:

```
1. lobster_trap_check(query_text)          → clean: true  required
2. consent_gate_check(subject_id_hash, …)  → allowed: true  required
3. chromadb_tenant_search(query_text, …)   → optional RAG context
4. kafka_event_publish(topic, data, …)     → final output
```

Steps 1 and 2 are hard gates — the MCP Gateway rejects step 4 if step 1 or 2 was not executed with a clean/allowed result in the current session.

---

## Hard-Constraint Cross-Reference

| HC | Tools enforcing it |
|---|---|
| HC-3 (L0/L1 autonomy ceiling) | `lobster_trap_check` (L0), `chromadb_tenant_search` (L0), `consent_gate_check` (L1), `kafka_event_publish` (L1) |
| HC-4 (tenant_id on every event/query) | All four tools — `tenant_id` UUID NOT NULL on every call |
| HC-5 (agents propose, policy disposes) | `kafka_event_publish` — 2-stage gate on `execute-gated` topics; all tools — no direct broker/DB/ChromaDB access |
| HC-6 (HMAC-SHA256 for NIDs/phones) | `consent_gate_check` — `subject_id_hash` is HMAC-SHA256 hex; raw identifiers rejected |

---

## Rule R2 Compliance

All four tools are designed so that **no raw credential (DB password, Kafka SASL password, ChromaDB token, HMAC secret) is ever passed to a calling agent**. The MCP Gateway exclusively holds and injects credentials retrieved from OpenBao KV v2 at pod startup.
