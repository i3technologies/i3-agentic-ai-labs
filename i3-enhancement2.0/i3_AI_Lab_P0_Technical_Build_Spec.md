# i3 AI Lab — P0 Technical Build Specification

**Version:** 1.0 (Draft for engineering review)
**Date:** September 2026
**Scope:** GPU inference tier (B1) · Metering, quotas & billing (B2) · Nairobi region deployment (B3) · Multi-tenancy, RBAC & audit logging (B4-MVP) · Model governance pack MVP (B5-MVP)
**Out of scope (P1/P2):** fine-tuning studio, RAG-as-a-service GA, white-label Sage, agent runtime, annotation workbench.

---

## 1. Context & Current-State Assumptions

The platform runs on IBM ROKS (OpenShift) in Frankfurt:

| Layer | Current state |
|---|---|
| Compute | CPU-only worker nodes; JupyterHub profiles `Standard` / `Large` |
| Model serving | Ollama + LiteLLM proxy at `http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000`, master key `sk-i3-internal` exposed as env var `LITELLM_API_KEY` |
| Models | `granite-nano`, `qwen-fast`, `qwen-heavy`, `coder`, `vision`, `embed` (Q4_K_M CPU quants) |
| Notebook UX | JupyterHub + JupyterLab, per-user PVC, 60-min idle culler, 500 MB upload limit |
| No-code UX | Sage (Open WebUI), same SSO, RAG over uploaded docs |
| Observability | Not specified in the user guide — assumed minimal; to be established in this spec |

**Design principles for all P0 work:**
1. **No breaking change to the OpenAI-compatible surface.** Existing notebooks and Sage configs must keep working (base URL + key may rotate per workstream, with 30-day overlap).
2. **Everything behind the same gateway.** Clients never talk to Ollama directly; LiteLLM remains the single control plane for routing, keys, and metering.
3. **Every workstream ships with acceptance tests and an operations runbook.**
4. **Progressive rollout:** staging alias (`*-gpu`, `*-nbi`) first, cutover by DNS/config, not big-bang.

---

## 2. Workstream B1 — GPU Inference Tier & Model Autoscaling

### 2.1 Objective
Reduce first-token latency for `qwen-heavy`, `coder`, and `vision` from 5–30 s (CPU) to < 3 s (GPU, warm), and make model serving scale with demand instead of queueing on a fixed CPU pool.

### 2.2 Target architecture

```
                 ┌──────────────────────────── OpenShift (Frankfurt) ─┐
 JupyterHub ───► │  LiteLLM proxy (control plane, replicas ≥ 2)       │
 Sage ─────────► │     ├─ router: alias → deployment                  │
                 │     │                                              │
                 │     ├─► qwen-fast / granite-nano / embed           │
                 │     │    → ollama-cpu (existing, unchanged)        │
                 │     │                                              │
                 │     └─► qwen-heavy / coder / vision                │
                 │          → ollama-gpu (NEW, 1–2 GPU nodes)         │
                 │             ├─ KEDA scaler on queue depth          │
                 │             └─ warm-pool of pre-loaded models      │
                 └────────────────────────────────────────────────────┘
```

Key decisions:
- **Separate Ollama deployment pool for GPU** (`ollama-gpu`), keeping the CPU pool untouched. One model loaded per GPU at a time (7B–14B Q4 fits comfortably on a 24 GB card).
- **Model pre-loading via Ollama's `/api/generate` with `"keep_alive": -1`** at pod start; a `prewarm` init container pulls the quant before traffic is admitted.
- **LiteLLM routing config** maps aliases → model deployments; routing weights let us shift traffic gradually (canary).

### 2.3 Hardware sizing (start small)

| Node | Spec (indicative) | Purpose |
|---|---|---|
| GPU-1 | 1× NVIDIA L4 24 GB (or A10/A30), 8 vCPU, 64 GB RAM | `qwen-heavy` + `coder` |
| GPU-2 (optional, month 2) | same | `vision` (13B llava needs ~12–16 GB at Q4) + burst/HA |
| Node selector + taint | `gpu=true:NoSchedule` | Keep notebook pods off GPU nodes |

> **Note:** If NVIDIA supply is constrained in-country, evaluate AMD Instinct MI210/MI300X (ROCm) — Ollama supports ROCm, but validate each model quant on ROCm before committing. Decide via a 2-week bake-off; do not let hardware procurement block the metering/tenancy workstreams.

### 2.4 Build steps

1. **Cluster prep:** label/taint GPU nodes; install NVIDIA GPU Operator (or AMD equivalent); verify `nvidia-smi` from a debug pod.
2. **Deploy `ollama-gpu`:** StatefulSet, 1 replica per GPU node, `OLLAMA_KEEP_ALIVE=-1`, resource limits set to full card, node affinity per alias (heavy/coder on GPU-1, vision on GPU-2).
3. **LiteLLM config update:**

```yaml
model_list:
  - model_name: qwen-fast
    litellm_params:
      model: ollama/qwen2.5:7b-instruct-q4_K_M
      api_base: http://ollama-cpu:11434
  - model_name: qwen-heavy
    litellm_params:
      model: ollama/qwen2.5:14b-instruct-q4_K_M
      api_base: http://ollama-gpu:11434
      timeout: 120
  - model_name: coder
    litellm_params:
      model: ollama/qwen2.5-coder:7b-instruct-q4_K_M
      api_base: http://ollama-gpu:11434
  - model_name: vision
    litellm_params:
      model: ollama/llava:13b
      api_base: http://ollama-gpu2:11434
router_settings:
  routing_strategy: simple-shuffle
```

4. **Autoscaling (phase 2 of this workstream):** KEDA scaled-object on LiteLLM queue depth / GPU utilization ≥ 75% for 5 min → scale Ollama pods within node capacity; scale-to-zero is **not** enabled for GPU (cold-start is minutes) — instead, scale-to-one warm minimum.
5. **Fallback rule:** if `ollama-gpu` health-check fails, LiteLLM router falls back to the CPU deployment for the same alias with a 5× latency warning header logged. This preserves availability over speed.
6. **Observability:** Prometheus scrape of Ollama (`/api/ps`, token throughput) + LiteLLM metrics; Grafana dashboard `GPU Inference — Latency & Throughput`.

### 2.5 Acceptance criteria

| ID | Test | Pass threshold |
|---|---|---|
| B1-1 | First-token latency, `qwen-heavy`, warm | p50 < 3 s, p95 < 6 s (vs current CPU baseline recorded pre-change) |
| B1-2 | First-token latency, `coder` | p50 < 2 s |
| B1-3 | Concurrent load, 10 parallel chat requests on `qwen-heavy` | No 5xx; p95 total latency < 30 s |
| B1-4 | GPU node failure | Requests fail over to CPU pool within 60 s; no client-visible error beyond latency |
| B1-5 | Notebook compatibility | Existing guide §5.1 code sample runs unmodified against the gateway |

### 2.6 Estimate
2 engineers × 3–4 weeks (hardware lead time excluded).

---

## 3. Workstream B2 — Metering, Quotas & Billing

### 3.1 Objective
Every API call attributable to a **key → project → customer**; usage exportable to invoice; budgets enforced before spend, not after.

### 3.2 Design

LiteLLM natively supports per-key budgets/rate limits and writes spend to Postgres — we operationalize it:

```
Client ──(API key per project)──► LiteLLM ──► Postgres (spend_logs)
                                  │
                                  ├─► Key-level: max_budget, tpm/rpm limits, expires
                                  ├─► Team-level: budgets mapped to customer accounts
                                  └─► Prometheus metrics (tokens, latency, spend rate)
                                             │
Nightly job: usage_extract ──► billing schema ──► CSV/PDF invoice + customer dashboard
```

### 3.3 Schema & data flow

1. **Postgres (HA, via ROKS managed DB or CrunchyData):** LiteLLM `spend_logs` (built-in) + a small `billing` schema:
   ```sql
   customers(id, name, tier, currency DEFAULT 'KES')
   projects(id, customer_id, name, litellm_team_id)
   api_keys(id, project_id, litellm_key_hash, label, budget_kes, expires_at)
   monthly_usage(project_id, ym, tokens_in, tokens_out, tokens_embed,
                 compute_minutes, gpu_minutes, amount_kes)
   ```
2. **Key lifecycle:** created via LiteLLM Admin UI / API on project creation; revoked on offboarding. The legacy master key `sk-i3-internal` is **retired for client use** (see B4) but retained 30 days for migration.
3. **Pricing engine (v1, keep deliberately simple):**
   - LLM tokens: per-1M-token rates per alias (cost-plus margin), fixed quarterly.
   - Notebook compute: CPU-hours from JupyterHub culler events + pod resource-hours; GPU-hours from GPU node allocation.
   - Sage usage: attributed via the same LiteLLM keys (Sage configured to use per-workspace keys, not the master key).
4. **Nightly ETL** aggregates `spend_logs` + kube metrics into `monthly_usage`; a report job renders per-customer usage CSV and a branded PDF usage statement (invoice line items feed whatever accounting system i3 uses — keep it a clean export, not an accounting integration, in v1).
5. **Dashboard:** Grafana customer-facing view (or minimal internal admin UI) showing month-to-date spend vs budget.

### 3.4 Quotas & guardrails

- Hard budget cap per key: requests rejected with `429-style` budget-exceeded response (friendly JSON, not a stack trace).
- Soft alerts at 50%/80%/95% to project owner email/webhook.
- Per-key RPM limits to stop runaway loops (common in student notebooks).

### 3.5 Acceptance criteria

| ID | Test | Pass threshold |
|---|---|---|
| B2-1 | 100 requests on key A, 100 on key B | `spend_logs` and `monthly_usage` attribute ≥ 99% of tokens to the correct keys/projects |
| B2-2 | Key budget exhausted | Further calls rejected within 60 s of cap; alert fired at 80% |
| B2-3 | Month-end export | Per-customer CSV+PDF generated for all active customers with zero manual edits |
| B2-4 | Notebook (JupyterHub) usage | CPU-hours attributable per user within ±10% of manual estimate on a test week |
| B2-5 | Sage | Sage chat traffic metered per workspace, not pooled under master key |

### 3.6 Estimate
1–2 engineers × 2–3 weeks (parallelizable with B1).

---

## 4. Workstream B3 — Nairobi Region Deployment

### 4.1 Objective
A second deployment region in Nairobi so client data and inference are Kenya-resident — converting the sovereignty story into a verifiable, contractual claim.

### 4.2 Hosting options (decision required by week 2)

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A. ROKS (IBM Cloud) in-region** | Second ROKS cluster in an IBM Cloud SA-Nairobi-capable location or nearest Africa region with explicit data-residency commitment | Consistent tooling/ops with Frankfurt | Verify actual region availability & residency terms; cost |
| **B. Nairobi colocation / local DC (e.g., iColo, Africa Data Centres, Node Africa)** | OpenShift (or OKD) on dedicated hardware in a Nairobi DC | True in-country residency, lowest latency for EA users, strong procurement story | i3 owns hardware lifecycle; GPU sourcing locally |
| **C. Local cloud partner (e.g., regional OpenStack/KVM provider)** | Managed Kubernetes from an EA cloud provider | Middle ground | Ecosystem maturity varies |

**Recommendation:** Option B for the inference + data plane (where residency matters), keep Frankfurt as DR/control-plane backup initially. Final call is a business decision (procurement, capex) — this spec assumes Option B, with Option A as fallback if hardware lead times slip.

### 4.3 Reference architecture

```
                        ┌─ Region: Frankfurt (existing) ─        ┌─ Region: Nairobi (new) ─
                        │  JupyterHub (training)                 │  JupyterHub (EA users)
                        │  Sage                                  │  Sage
                        │  LiteLLM ──► ollama-cpu                │  LiteLLM ──► ollama-cpu
                        │     │                                    │     └──────► ollama-gpu
                        │     └────► ollama-gpu                    │  Billing DB (replica)
                        │  Billing DB (primary)                    │  Audit log store
                        │  Object storage (PVC backups)  ──async──►│  Object storage (residency copy)
                        └──────────────────────────────────────────┴─────────────────────────
 DNS: customers route by data-residency class; global fallback Frankfurt for DR only
```

Key points:
- **Model artifact replication:** nightly sync of Ollama model blobs (or pull-from-registry per region) — models themselves are not customer data; the *residency* claim applies to prompts, documents, embeddings, and logs.
- **Control plane:** keep one LiteLLM config repo (GitOps); per-region overlays differ only in endpoints and storage classes.
- **Failover:** manual in v1 (documented runbook, RTO 4 h). Automated DNS failover is P1.
- **Backup/DR:** Frankfurt retains an encrypted replica of Nairobi *configuration and non-resident* data only; **no customer prompts/documents leave Nairobi** — this is the contractual promise, enforced by simply not configuring replication for those buckets/PVCs.

### 4.4 Build steps
1. Provision cluster + storage classes (block + object), GPU node per B1.
2. GitOps deploy: same Helm/Kustomize as Frankfurt with region overlay.
3. Data plane: per-tenant PVCs, object buckets with residency tags; verify ODPC-relevant controls (encryption at rest, access logging).
4. Billing: Nairobi region writes to regional billing replica; Frankfurt remains billing-of-record until Nairobi GA.
5. Cutover plan per customer class: pilot tenants → EA enterprise tenants → training workloads (may stay Frankfurt if users are global).

### 4.5 Acceptance criteria

| ID | Test | Pass threshold |
|---|---|---|
| B3-1 | Residency audit | All customer prompts, uploads, embeddings, and audit logs verified Nairobi-only (no Frankfurt replica for these classes) |
| B3-2 | Latency | EA user round-trip to Nairobi gateway p95 < round-trip to Frankfurt by ≥ 60% |
| B3-3 | DR runbook | Simulated Nairobi outage → Frankfurt standby procedures executed per runbook within RTO 4 h (drill, not production failover) |
| B3-4 | Same client experience | Guide §5.1 sample runs unchanged in Nairobi with region-specific base URL |

### 4.6 Estimate
2 engineers × 4–6 weeks + procurement lead; can overlap B1/B2 (same manifests).

---

## 5. Workstream B4-MVP — Multi-Tenancy, RBAC & Audit Logging

### 5.1 Objective
Enterprise tenants get project spaces with role-based access, per-project keys, and tamper-evident audit trails — the minimum a bank/procurement officer needs to see.

### 5.2 Design (MVP scope — full B4 continues in P1)

- **Tenancy model:** OpenShift namespaces per enterprise customer (`cust-<slug>`); JupyterHub uses `kubespawner` to place user pods in the customer namespace via SSO group claims (Keycloak groups: `i3-users`, `cust-acme`, …).
- **RBAC:** three roles per customer namespace — `admin` (manage keys/users), `developer` (notebooks + API keys), `viewer` (dashboards). Mapped from SSO groups; no separate user database.
- **Keys:** per-project LiteLLM keys (B2) bound to the customer; master key disabled for interactive use and scoped to a break-glass service account only.
- **Audit logging:**
  - **API audit:** LiteLLM request log enriched with `project_id`, model, token counts, latency — shipped to an append-only object-store bucket (WORM policy, 7-year retention class configurable per contract).
  - **Platform audit:** OpenShift API audit events for customer namespaces forwarded to the same store.
  - Retention: hot 90 days, cold archive per contract.

### 5.3 Acceptance criteria

| ID | Test | Pass threshold |
|---|---|---|
| B4-1 | SSO group mapping | User in `cust-acme` group spawns notebook in `cust-acme` ns; cannot list `cust-beta` resources |
| B4-2 | Key isolation | Key from project A rejected when used against project B's constrained endpoints; master key refuses interactive chat calls |
| B4-3 | Audit completeness | Sample of 1,000 requests: 100% have project attribution; tamper-evidence verified (object lock) |
| B4-4 | Offboarding | User removed from SSO group loses access within 5 min incl. revoked sessions/keys |

### 5.4 Estimate
1–2 engineers × 2–3 weeks.

---

## 6. Workstream B5-MVP — Model Governance Pack (Minimum Viable)

### 6.1 Objective
Enough governance to (a) sign off client deployments and (b) satisfy a bank's risk review: a repeatable evaluation harness, basic PII guardrails, and published model cards.

### 6.2 Components

1. **Evaluation harness (`eval/` repo):**
   - Task suites per alias: summarization, Q&A faithfulness, code correctness, instruction-following — 50–100 gold items each.
   - **Swahili/Sheng suite v1:** 100 prompts covering comprehension, translation, cultural idiom; scored by rubric + human spot-checks.
   - Runner: batch against LiteLLM; outputs scored (BLEU/ROUGE where apt, LLM-judge via `qwen-heavy` for qualitative rubrics); results versioned in Git.
2. **PII pre-filter (MVP):** a LiteLLM pre-call hook using a NER model (e.g., a small presidio-style analyzer) to redact/detect emails, phone numbers (KE format), ID numbers, before logging; mode = `detect` (flag) first, `redact` after 2 weeks of false-positive tuning.
3. **Model cards:** one page per alias — capability, eval scores (incl. Swahili), latency on GPU/CPU, known limitations, intended use. Published to the customer portal.
4. **Release gate:** any model/quant change must pass the harness + produce updated model card before promotion to `prod` alias.

### 6.3 Acceptance criteria

| ID | Test | Pass threshold |
|---|---|---|
| B5-1 | Harness runs | Full suite executes via CI in < 2 h unattended; results published |
| B5-2 | Swahili pack | v1 suite scored for all six aliases with baseline report |
| B5-3 | PII detection | ≥ 90% recall on a seeded 200-document test set of KE PII patterns; FP rate documented |
| B5-4 | Release gate | Promotion of a test model blocked without passing eval (negative test) |

### 6.4 Estimate
1 ML engineer × 3 weeks (parallel with B1/B2), plus part-time reviewer for Swahili content quality.

---

## 7. Cross-Cutting: Security, GitOps & Operations

- **GitOps:** all manifests (LiteLLM config, KEDA, Grafana, namespaces) in one repo; Frankfurt + Nairobi overlays; changes via PR with the acceptance tests above as CI gates.
- **Secrets:** move `LITELLM_API_KEY` and DB credentials to a secrets manager (Vault or cloud-native equivalent); the literal `sk-i3-internal` string must disappear from docs, notebooks, and env dumps.
- **Backups:** Postgres PITR, object-store versioning for model blobs and audit buckets; quarterly restore drill.
- **Observability baseline:** Prometheus + Grafana + alertmanager; SLI dashboards: gateway availability, p50/p95 latency per alias, GPU utilization, spend rate vs budget.
- **Runbooks:** one per workstream (GPU failover, budget incident, region failover drill, audit export request).

## 8. 90-Day Delivery Plan

| Weeks | Track 1 (Infra) | Track 2 (Platform) | Track 3 (Governance) |
|---|---|---|---|
| 1–2 | GPU node procurement + bake-off (NVIDIA vs ROCm) | Billing schema + LiteLLM key model design | Eval harness skeleton + Swahili item collection |
| 3–5 | `ollama-gpu` deploy + routing + fallback; latency baseline | Per-key metering live in staging; nightly ETL v1 | Task suites v1; runner CI |
| 6–8 | KEDA autoscaling; load tests B1-3 | Quotas/alerts; invoice export pilot (2 friendly customers) | PII detect mode on staging |
| 9–12 | Nairobi region stand-up (Option B) + residency verification | B4 namespace/RBAC pilot with first enterprise tenant; master-key retirement notice | B5 release gate enforced; model cards published |

**Definition of done for the P0 program:** all acceptance criteria B1-1…B5-4 pass in staging; two paying pilot tenants live on metered keys; Nairobi residency verified by audit; governance pack v1 published.

## 9. Risks & Open Questions

| Risk / Question | Owner | Needed by |
|---|---|---|
| GPU hardware lead time in-country | Ops | Week 1 |
| ROKS vs OKD for Nairobi colo (licensing/support) | Platform lead | Week 2 |
| LiteLLM Postgres HA sizing at current RPS | DBA | Week 3 |
| Whether Sage supports per-workspace LiteLLM keys natively or needs a fork/config patch | Sage owner | Week 2 |
| ODPC legal review of audit-retention promises (7-yr WORM) | Compliance | Week 4 |
| Final KES pricing table to encode in billing engine | Commercial | Week 6 |
