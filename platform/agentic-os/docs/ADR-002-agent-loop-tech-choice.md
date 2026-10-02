# ADR-002: App 3 Agent Loops — LangGraph vs Dapr Distributed Actors

**Status:** ACCEPTED  
**Date:** 2025-07-15  
**Deciders:** Principal Solutions Architect, Lead Full-Stack Developer  
**Context:** i3 AI Platform — Pre-Plan Phase Gate for Application 3 (Agentic AI OS)

---

## Context

The Enterprise Architecture Implementation Guide proposes **Dapr** distributed actor
runtime for stateful agent loops in the Agentic AI OS. The existing i3 AI Platform
already uses **LangGraph** for stateful agent state machines in platform/engage and
platform/pmaas. This ADR evaluates whether Dapr is warranted or whether LangGraph
with Redis checkpointing is the correct choice.

---

## Decision Drivers

| # | Driver | Weight |
|---|--------|--------|
| D1 | Existing platform alignment (reduce new operator installs) | High |
| D2 | Stateful agent loop capability (pause, resume, human-in-the-loop) | High |
| D3 | HC-5 compliance (agents propose, policy disposes) | High |
| D4 | Observability integration (Langfuse trace correlation) | High |
| D5 | Operational complexity (sidecar injection, service mesh interaction) | High |
| D6 | Redis + Kafka already available | Medium |

---

## Options Considered

### Option A: LangGraph + Redis Checkpointer — CHOSEN

**Stack:** LangGraph 0.2.x + asyncpg StateStore + Redis checkpointer +
           LiteLLM for model calls + existing MCP Gateway for tool execution

**Capability mapping to guide's App 3 requirements:**

| Requirement | LangGraph capability |
|-------------|---------------------|
| Stateful agent loop (THOUGHT → TOOL_CALL → FINAL_RESPONSE) | ✅ Native graph nodes with typed state |
| Pause / resume for human-in-the-loop | ✅ `interrupt_before` / `interrupt_after` node hooks |
| Persist agent state across pod restarts | ✅ Redis checkpointer or asyncpg checkpointer |
| Streaming partial outputs to UI | ✅ LangGraph `.astream()` with SSE |
| Multi-agent coordination (supervisor → sub-agents) | ✅ LangGraph multi-agent graph pattern |
| Tool call OPA policy gate | ✅ Tool nodes can call MCP Gateway HTTP endpoint |
| Continuous Learning Flywheel trace export | ✅ LangGraph callbacks → Langfuse tracer |

**Evaluation against drivers:**

| Driver | Assessment |
|--------|-----------|
| D1 Platform alignment | ✅ Already used in platform/engage and platform/pmaas |
| D2 Stateful loops | ✅ Full support: pause, resume, branching, cycles |
| D3 HC-5 compliance | ✅ Tool nodes route through MCP Gateway; human gate via interrupt_before |
| D4 Langfuse integration | ✅ LangGraph has first-class Langfuse callback support |
| D5 Operational complexity | ✅ Pure Python library; no sidecar injection; no new operators |
| D6 Redis reuse | ✅ Uses existing Redis cluster for checkpointing |

**Risks:**
- LangGraph state is in-memory + Redis; Dapr provides stronger distributed state guarantees →
  Risk is LOW: agent sessions are ephemeral (single request/response cycle or short-lived
  multi-turn sessions); Redis cluster HA is already ensured by existing platform setup

### Option B: Dapr Distributed Actor Runtime

**Stack:** Dapr 1.13 + DaprClient + Actor SDK + Dapr State Store (Redis backend) +
           Dapr Pub/Sub (Kafka backend) + sidecar injection

**Evaluation against drivers:**

| Driver | Assessment |
|--------|-----------|
| D1 Platform alignment | ❌ Not deployed; requires new Dapr operator install + sidecar injection on all pods |
| D2 Stateful loops | ✅ Actor model provides strong stateful entity guarantees |
| D3 HC-5 compliance | ⚠️ Requires custom actor method to route tool calls through MCP Gateway |
| D4 Langfuse integration | ❌ No native Langfuse integration; requires custom OpenTelemetry bridge |
| D5 Operational complexity | ❌ Sidecar injection complicates OpenShift SCC policies; Dapr control plane adds 4 new pods |
| D6 Redis reuse | ✅ Dapr state store can use Redis backend |

**Additional Dapr-specific costs:**
- New OLM operator or Helm chart installation: Dapr control plane (4 pods)
- All pods that use Dapr actors require sidecar injection annotation
- OpenShift Security Context Constraints (SCCs) conflict with Dapr sidecar injection
  pattern — requires privileged SCC modification or custom SCC definition
- Dapr Actor SDK is less ergonomic for LLM-native ReAct loops than LangGraph's graph DSL
- No built-in streaming for partial LLM outputs (LangGraph has native `.astream()`)

**Capability gap analysis:**
Dapr's primary advantage over LangGraph is in **distributed, long-lived stateful actors**
(e.g. an actor that persists for hours/days across multiple external system events).
App 3 agent sessions are **short-lived** (single conversation turn to a few minutes).
Dapr's added complexity is not justified by this workload profile.

---

## Decision

**ACCEPTED: Option A — LangGraph + Redis Checkpointer**

**Rationale:**
1. LangGraph is already deployed and battle-tested in platform/engage and platform/pmaas.
   Zero new operators, zero new infrastructure.
2. The `interrupt_before` / `interrupt_after` pattern in LangGraph is the idiomatic
   human-in-the-loop mechanism — it maps precisely to HC-5 (agents propose, policy disposes).
3. Dapr provides stronger distributed state for long-lived actors. App 3 agent sessions
   are short-lived (seconds to minutes) — Redis checkpointing is adequate.
4. LangGraph has native Langfuse callback support. The Continuous Learning Flywheel
   (App 3) depends on Langfuse traces — LangGraph makes this zero-configuration.
5. Dapr sidecar injection creates OpenShift SCC complications that outweigh any benefit.

---

## Consequences

**Positive:**
- App 3 agent loops share the same LangGraph + Redis pattern as platform/engage
- Langfuse tracing works out of the box via LangGraph callbacks
- Human-in-the-loop (HC-5) uses LangGraph's built-in `interrupt_before` on tool nodes
- No new cluster operators; no new pod security policies

**Negative / Mitigations:**
- Long-lived agent sessions (>30 min) may require custom Redis TTL tuning →
  Mitigation: Set Redis key TTL to 4h for active agent sessions; use asyncpg
  checkpointer for sessions exceeding that window
- LangGraph does not provide Dapr-style virtual actors for cross-pod state →
  Mitigation: Agent sessions are always single-tenant and single-pod; no cross-pod
  state sharing is required in the current App 3 design

---

## Implementation Notes

Agent loop entrypoint: `platform/agentic-os/agent_runtime.py`  
LangGraph state schema: `platform/agentic-os/state.py`  
Redis checkpointer config: shared Redis cluster, key prefix `agentic-os:session:`  
MCP Gateway integration: tool nodes call `POST /tools/{tool_name}/invoke`  
Langfuse integration: `LangfuseCallbackHandler` injected at graph `.compile()` time  
vLLM integration: LiteLLM model gateway with vLLM backend for GPU models  
