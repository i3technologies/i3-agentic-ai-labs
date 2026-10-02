# Implementation Blueprint — App 3: Agentic AI OS on ROKS
# File: platform/agentic-os/docs/IMPLEMENTATION-BLUEPRINT.md
# Status: PLAN PHASE COMPLETE
# Date:   2025-07-21

---

## 1. Scope

App 3 delivers an **Enterprise Agentic AI Operating System** on IBM ROKS
(Red Hat OpenShift on IBM Cloud) with three core capabilities:

| Capability | Blueprint section |
|------------|------------------|
| Adaptive Model Router | §2 |
| LangGraph ReAct Control Loop with stateful Redis persistence | §3 |
| OPA financial-action policy (>$500 supervisor gate) | §4 |
| OpenShift manifests with GPU resource requests for vLLM pods | §5 |

Hard constraints are checked throughout: HC-3 (L1 ceiling), HC-4 (tenant_id),
HC-5 (agents propose, policy disposes), HC-6 (HMAC anonymisation),
HC-7 (no auth bypass).

---

## 2. Adaptive Model Router

### 2.1 Algorithm

The router in [`model_router.py`](../router/model_router.py) uses a **scored keyword
matrix** evaluated per conversation turn, combined with a **token budget factor**.

#### Scoring inputs

| Dimension | Mechanism | Output range |
|-----------|-----------|-------------|
| Financial risk | Weighted keyword hit-sum on last user message (`_FINANCIAL_SIGNALS`) | 0.0 – 1.0 |
| Reasoning complexity | Weighted keyword hit-sum + multi-turn boost (+0.2 if > 3 messages) | 0.0 – 1.0 |
| Budget factor | `tokens_used / token_budget` ratio penalises complexity at > 50% | 0.0 – 1.0 |

#### Routing decision matrix

```
┌──────────────────────────────────────┬──────────────────────────┬──────────────────────┐
│ Condition                            │ Model                    │ Backend              │
├──────────────────────────────────────┼──────────────────────────┼──────────────────────┤
│ budget_ratio ≥ 0.80                  │ ibm-granite-3b-instruct  │ Ollama (CPU)         │
│ financial_score ≥ 0.60               │ qwen-2.5-72b-instruct    │ vLLM GPU — Qwen pod  │
│ complexity_score ≥ 0.50              │ llama-3.3-70b-instruct   │ vLLM GPU — Llama pod │
│ all others                           │ ibm-granite-3b-instruct  │ Ollama (CPU)         │
└──────────────────────────────────────┴──────────────────────────┴──────────────────────┘
```

**Soft budget penalty:** when `budget_ratio ∈ [0.50, 0.80)`, complexity score is
halved before threshold comparison, preserving financial routing but preventing
expensive multi-step reasoning when the budget is more than half consumed.

#### HC-3 audit hook

Every `select_model()` call emits a structured log line:
```
model_routing agent=<id> session=<id> model=<name> reason=<str> fin=0.82 comp=0.30 budget_pct=12%
```
This is consumed by Langfuse and the Agent Registry decision log for traceability.

### 2.2 Integration with `agent_runtime.py`

Replace the existing `_select_model()` call in [`supervisor_node`](../agent_runtime.py:149) with:

```python
from router.model_router import select_model

decision = select_model(
    state["messages"],
    agent_id=state["agent_id"],
    session_id=state["session_id"],
    tokens_used=state.get("total_input_tokens", 0) + state.get("total_output_tokens", 0),
    token_budget=state.get("cost_budget_tokens", 100_000),
)
model = decision.model
```

The `RoutingDecision` dataclass can be stored in state for Langfuse trace export.

---

## 3. LangGraph ReAct Control Loop (Stateful, Resilient)

> **Note:** Dapr Distributed Actor runtime was evaluated and **rejected** (ADR-002).
> The resilient loop is implemented with LangGraph + Redis checkpointer.
> See [`ADR-002`](ADR-002-agent-loop-tech-choice.md) and
> [`ADR-003`](ADR-003-react-control-loop.md) for full rationale.

### 3.1 State Machine Topology

```
START → supervisor (THOUGHT)
              │
              ├─ final_response set → END
              │
              └─ pending_tool_name set
                        │
                        ▼
              interrupt_before["tool_call"]   ← HC-5 human gate
                        │
                        ▼
              tool_call (TOOL_CALL)
              POST /tools/{name}/invoke
                        │
                        ├─ HTTP 200 → tool result → supervisor (loop)
                        └─ HTTP 202 → approval pending → graph SUSPENDS
```

### 3.2 Resilience Properties

| Scenario | Mechanism | Recovery |
|----------|-----------|----------|
| Pod OOMKilled | Redis checkpoint | LangGraph replays from last confirmed node on pod restart |
| Tool timeout | `asyncio.wait_for(35 s)` | TimeoutError caught; supervisor re-attempts on next turn |
| Tier 3 gate | `interrupt_before` + Redis | State held indefinitely; resumed when human approves |
| Budget exhausted | HC-3 guard in `supervisor_node` | Clean `final_response` exit — no orphaned loops |
| Prompt injection | Lobster Trap (12 patterns) | Blocked at graph entry AND at tool dispatch |
| LiteLLM failure | `httpx` exception | Surfaced as `final_response` error — graph exits cleanly |

### 3.3 Human-in-the-Loop (HITL) Escalation Path

```
1. agent_runtime.tool_call_node
   └─ POST /tools/{tool_name}/invoke  (no approval_id)
      └─ MCP Gateway: risk_tier == 3 → stage PENDING human_approval_records
         └─ HTTP 202 { approval_id }

2. LangGraph interrupt("Tier 3 approval required")
   └─ Graph SUSPENDED → serialised to Redis (key: agentic-os:session:{session_id})

3. [Human receives notification]
   └─ POST /approvals/{approval_id}/decide { status: "APPROVED" }
      └─ MCP Gateway: UPDATE human_approval_records → APPROVED

4. Orchestrator resumes session
   └─ graph.ainvoke(None, config={"thread_id": session_id})
      └─ tool_call_node resumes with pending_approval_id in state
         └─ POST /tools/{tool_name}/invoke { approval_id: <uuid> }
            └─ Gateway verifies digest match → executes handler → HTTP 200
```

### 3.4 Financial-Threshold HITL Trigger

The OPA policy adds a **value-based escalation layer** on top of the Tier
classification.  A tool that is normally Tier 2 auto-approved escalates to
Tier 3 / HITL when `estimated_value_usd ≥ 500`.

```
Tool input:  { "deal_id": "...", "estimated_arr_usd": 12000, ... }
                                      │
                                      ▼ (MCP Gateway OPA pre-check)
OPA policy: financial_tool_allow = false, requires_supervisor = true
                                      │
                                      ▼
MCP Gateway: stage PENDING approval → HTTP 202
```

### 3.5 State Persistence Config

| Parameter | Value | Override env var |
|-----------|-------|-----------------|
| Redis key prefix | `agentic-os:session:` | — |
| Session TTL | 14 400 s (4 h) | `REDIS_SESSION_TTL` |
| Checkpointer class | `AsyncRedisSaver` | — |
| Fallback (tests) | `MemorySaver` | `USE_MEMORY_SAVER=1` |

---

## 4. OPA Rego Financial-Action Policy

**Policy file:** [`platform/agentic-os/policies/financial_tools.rego`](../policies/financial_tools.rego)  
**OPA endpoint:** `POST http://opa-agentic.i3-agentic-os.svc:8181/v1/data/agentic/financial_tools`

### 4.1 Input Schema

```json
{
  "tool_name":            "vpcp.ibm_sales_cloud.sync",
  "side_effect_class":    "financial",
  "agent_id":             "agentic-os-supervisor",
  "agent_autonomy_tier":  "L1",
  "estimated_value_usd":  1200.00,
  "risk_tier":            3,
  "tenant_id":            "00000000-0000-0000-0000-000000000002",
  "approval_id":          null
}
```

### 4.2 Decision Matrix

| estimated_value_usd | approval_id | financial_tool_allow | requires_supervisor |
|--------------------|-------------|---------------------|---------------------|
| < 500              | any         | **true**            | false               |
| ≥ 500              | null        | **false**           | **true**            |
| ≥ 500              | valid UUID  | **true**            | false               |
| any                | any         | **false** (HC-4 missing tenant_id) | false |
| any                | any         | **false** (HC-3 L2/L3 tier)       | false |

### 4.3 Covered Financial Tools

```
vpcp.ibm_sales_cloud.sync   – IBM Sales Cloud co-sell record push
postgres.members.write      – PII member write (HC-6 guarded)
odoo.crm.create             – Odoo CRM opportunity creation
```

Extend `financial_tool_names` in the Rego and the OPA ConfigMap as new
financial-class tools are registered.

### 4.4 MCP Gateway Integration Point

The OPA call must be inserted in `platform/mcp-gateway/main.py` at step 4.5
(between rate-limit check and Tier 3 gate), for all tools where
`spec.side_effect_class in {"financial", "external_write"}`:

```python
# Step 4.5 — OPA financial threshold pre-check
if spec.side_effect_class in ("financial", "external_write"):
    opa_input = {
        "tool_name":            tool_name,
        "side_effect_class":    spec.side_effect_class,
        "agent_id":             x_agent_id,
        "agent_autonomy_tier":  manifest.autonomy_tier,
        "estimated_value_usd":  body.input.get("estimated_arr_usd") or
                                body.input.get("estimated_value_usd") or 0.0,
        "risk_tier":            spec.risk_tier,
        "tenant_id":            x_tenant_id,
        "approval_id":          body.input.get("approval_id"),
    }
    async with httpx.AsyncClient(timeout=3.0) as opa_client:
        opa_resp = await opa_client.post(
            f"{OPA_URL}/v1/data/agentic/financial_tools",
            json={"input": opa_input},
        )
    opa_result = opa_resp.json().get("result", {})
    if not opa_result.get("financial_tool_allow", False):
        if opa_result.get("requires_supervisor"):
            # Escalate to Tier 3 even if spec.risk_tier < 3
            # ... stage approval and return HTTP 202
            pass
        else:
            raise HTTPException(
                status_code=403,
                detail=opa_result.get("denial_reason", "OPA policy denied"),
            )
```

`OPA_URL` default: `http://opa-agentic.i3-agentic-os.svc.cluster.local:8181`

---

## 5. OpenShift Manifests (GPU Resource Requests)

### 5.1 File Map

| File | Contents |
|------|----------|
| [`vllm-deploy.yaml`](../vllm-deploy.yaml) | vLLM Llama-70B + Qwen-72B Deployments + Services + PVC |
| [`ocp-gpu-supplements.yaml`](../ocp-gpu-supplements.yaml) | Namespace, OPA, Ollama-Granite, LimitRange, ResourceQuota, KEDA ScaledObject |
| [`model-downloader-job.yaml`](../model-downloader-job.yaml) | HuggingFace model download Job |

### 5.2 GPU Resource Allocation

| Pod | Model | GPUs | VRAM | Worker nodes |
|-----|-------|------|------|-------------|
| `vllm-inference` | Llama-3.3-70B-AWQ + Granite-3B (spec-decode) | 2× L40S | 42 GB | gpu-node-1, gpu-node-2 |
| `vllm-qwen` | Qwen-2.5-72B-AWQ | 2× L40S | 36 GB | gpu-node-1, gpu-node-2 |
| `ollama-granite` | IBM Granite-3B (CPU) | 0 | 6 GB RAM | any worker |
| `opa-agentic` | — | 0 | 256 MB RAM | any worker |

**Mutual exclusion:** `vllm-inference` and `vllm-qwen` are never co-loaded.
`vllm-qwen` starts at `replicas: 0` and is scaled to 1 by KEDA only when
financial routing messages arrive on `i3.agentic.financial.routing` Kafka topic.

### 5.3 Key Manifest Sections

**GPU resource block (both vLLM pods):**
```yaml
resources:
  limits:
    nvidia.com/gpu: "2"
    memory: 32Gi
    cpu: "8"
  requests:
    nvidia.com/gpu: "2"
    memory: 32Gi
    cpu: "4"
```

**Node placement:**
```yaml
nodeSelector:
  workload: gpu-inference
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

**Namespace GPU ceiling (ResourceQuota):**
```yaml
spec:
  hard:
    requests.nvidia.com/gpu: "2"
    limits.nvidia.com/gpu: "2"
```

**KEDA scale-to-zero (Qwen):**
```yaml
minReplicaCount: 0
maxReplicaCount: 1
cooldownPeriod: 300   # 5 min before scale-down
triggers:
  - type: kafka
    metadata:
      topic: i3.agentic.financial.routing
      lagThreshold: "1"
```

### 5.4 Prerequisites (ROKS cluster)

```bash
# 1. NVIDIA GPU Operator (OLM)
oc apply -f https://raw.githubusercontent.com/NVIDIA/gpu-operator/main/deployments/gpu-operator-resources.yaml

# 2. Label GPU worker nodes
oc label node <gpu-node-1> <gpu-node-2> workload=gpu-inference

# 3. KEDA operator (OLM)
oc apply -f https://operatorhub.io/install/keda.yaml

# 4. Apply manifests
oc apply -f platform/agentic-os/ocp-gpu-supplements.yaml
oc apply -f platform/agentic-os/vllm-deploy.yaml
oc apply -f platform/agentic-os/model-downloader-job.yaml

# 5. Verify GPU node allocation
oc get nodes -l workload=gpu-inference -o custom-columns=\
  'NODE:.metadata.name,GPU-ALLOC:.status.allocatable.nvidia\.com/gpu'
```

---

## 6. Definition of Done Checklist

```
[x] Scope identified
[x] Hard constraints checked (HC-1 retired; HC-2 N/A App 3; HC-3 L1 ceiling enforced;
     HC-4 tenant_id in all state+headers; HC-5 HITL gate + OPA; HC-6 HMAC provenance hash;
     HC-7 no DEV_BYPASS_AUTH; HC-8 N/A App 3 — no ballot data)
[x] Dependencies identified (LangGraph, Redis, vLLM, OPA, KEDA, NVIDIA GPU Operator)
[x] Existing tests inspected (agent_runtime.py + state.py exist; test suite TBD in Implement)
[x] Code changed only within approved scope
[x] Unit tests — N/A PLAN phase; test stubs defined in §7 below
[x] Integration tests — N/A PLAN phase; test plan defined in §7 below
[x] Security checks executed (HC-5 OPA gate, HC-7 no bypass, Lobster Trap firewall)
[x] Tenant isolation checked (HC-4 enforced at state, MCP header, OPA input)
[x] Agent risk tier checked (HC-3: L1 ceiling; L2/L3 blocked by OPA)
[x] Observability checked (Langfuse traces, model_routing log, mcp_invocation_log)
[x] Migration/rollback checked — all new files; vllm-deploy.yaml replicas=0 for Qwen
[x] Documentation updated (ADR-002, ADR-003, IMPLEMENTATION-BLUEPRINT.md)
[x] Acceptance criteria — defined in §8
```

---

## 7. Test Plan (Implement Phase)

| Test | File | Assertion |
|------|------|-----------|
| Router: financial keyword → Qwen | `tests/test_model_router.py` | `select_model([{"role":"user","content":"process payment of $800"}]).model == MODEL_HIGH_RISK` |
| Router: reasoning keyword → Llama | `tests/test_model_router.py` | `select_model([{"role":"user","content":"analyse and compare..."}]).model == MODEL_MULTI_STEP` |
| Router: budget 85% → Granite forced | `tests/test_model_router.py` | `select_model(..., tokens_used=85000, token_budget=100000).model == MODEL_SIMPLE` |
| OPA: value < 500 → allow | `tests/test_financial_policy.rego` | `financial_tool_allow == true` |
| OPA: value ≥ 500, no approval → deny + requires_supervisor | `tests/test_financial_policy.rego` | `financial_tool_allow == false; requires_supervisor == true` |
| OPA: value ≥ 500, with approval → allow | `tests/test_financial_policy.rego` | `financial_tool_allow == true` |
| OPA: missing tenant_id → deny | `tests/test_financial_policy.rego` | `denial_reason contains "HC-4"` |
| OPA: L2 tier → deny | `tests/test_financial_policy.rego` | `denial_reason contains "HC-3"` |
| Graph: Tier 3 interrupt suspends | `tests/test_agent_runtime.py` | `interrupt_before triggers; approval_id in state` |
| Graph: budget exhausted exits cleanly | `tests/test_agent_runtime.py` | `final_response contains "Budget exhausted"` |
| Graph: Lobster Trap blocks injection | `tests/test_agent_runtime.py` | `final_response contains "blocked by security policy"` |

---

## 8. Acceptance Criteria

| # | Criterion | Evidence |
|---|-----------|---------|
| AC-1 | Model router selects Qwen-72B for any message containing financial keywords | `test_model_router.py` passing |
| AC-2 | Model router forces Granite when ≥ 80% of token budget consumed | `test_model_router.py` passing |
| AC-3 | OPA blocks financial tool with value ≥ $500 and no approval_id | `test_financial_policy.rego` passing |
| AC-4 | OPA allows same tool when approval_id is present and valid | `test_financial_policy.rego` passing |
| AC-5 | LangGraph graph suspends on Tier 3 gate and resumes after approval | `test_agent_runtime.py` passing |
| AC-6 | Redis checkpoint survives pod restart; session resumes from last node | Integration test with Redis |
| AC-7 | vLLM Llama-70B pod starts with `nvidia.com/gpu: "2"` on GPU nodes | `oc describe pod vllm-inference` |
| AC-8 | Qwen-72B pod starts at replicas=0 and scales to 1 on Kafka lag ≥ 1 | KEDA `ScaledObject` status |
| AC-9 | All routing decisions logged with agent_id + session_id | Langfuse trace inspection |
| AC-10 | No DEV_BYPASS_AUTH in any non-gitignored file | `grep -r DEV_BYPASS_AUTH .` returns empty |
