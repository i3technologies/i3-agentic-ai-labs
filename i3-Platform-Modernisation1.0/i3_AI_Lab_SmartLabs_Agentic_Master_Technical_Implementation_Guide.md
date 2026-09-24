# i3 AI Lab, SmartLabs & Agentic Platform
## Master Technical Implementation Guide — Senior Solutions Architect Review & Consolidated Blueprint

**Prepared for:** Philip Mulala (Philip Mukiti), CEO, i3 Technologies Ltd
**Classification:** Internal — Strategy & Architecture
**Version:** 1.0 (Consolidated — reconciles 11 source documents listed in Section 0)
**Date:** September 2026

---

## Reviewer's Note

You supplied eleven documents covering four overlapping product lines — the **AI Lab**, **SmartLabs**, an emerging **AfriqAI/Agentic AI unification layer**, and **i3 EduBridge** (the higher-education wrapper, live-piloting at USIU-Africa) — written by different authors at different times with different levels of engineering rigor. Before this can be called one implementation plan, four contradictions between the commercial narrative and the engineering reality need to be surfaced and resolved, not averaged together.

1. **Data-residency claim is ahead of the infrastructure that would make it true.** The **USIU-Africa proposal** (submitted March 2026) already tells a paying customer: *"IBM Cloud VPC (Kenya Region): Primary infrastructure with local data residency."* But the **AI Lab P0 Technical Build Spec** (the most detailed, engineering-grade document you supplied, dated September 2026) states plainly that the platform runs on **IBM ROKS in Frankfurt**, and that a Nairobi region is **Workstream B3 — not yet built** — its own stated purpose is *"converting the sovereignty story into a verifiable, contractual claim."* The SmartLabs blueprints independently confirm Frankfurt as the current ROKS location. **This is a live commercial-integrity risk, not a documentation inconsistency**: a university (and by extension a bank, under the same sovereignty pitch in the AI Lab commercialization docs) has been told data residency exists when the build spec says it doesn't yet. I treat B3 as the gating requirement before this claim is repeated to any new prospect, and flag it as Risk #1 in Section 15.
2. **GPU capability is marketed as live in three documents and specified as a to-be-built workstream in the fourth.** The USIU proposal advertises *"GPU-Enabled AI/ML Labs: NVIDIA A100 GPU pods for deep learning and IBM watsonx"* as present-tense infrastructure. The SmartLabs 45-vendor matrix lists NVIDIA GPU labs. But the P0 Build Spec's own current-state table says compute is **"CPU-only worker nodes"** with 5–30s first-token latency, and GPU inference is **Workstream B1 — not yet built** (hardware not yet procured, NVIDIA-vs-ROCm bake-off not yet run). The AfriqAI blueprint independently confirms the CPU-only baseline. I have treated the P0 spec as ground truth throughout this document and flagged every commercial document's GPU claims accordingly (Section 15, Risk #2).
3. **Five separate documents each model revenue for overlapping product lines, with no single P&L.** The AI Lab Commercialization Strategy projects USD 530k Year-1 revenue for "AI Services" alone. The SmartLabs Master Blueprint projects Ksh 154.95M (≈USD 1.19M) Year-1 gross revenue, of which the "AI Lab/JupyterHub" line is only Ksh 15M — a fraction of the AI Lab document's own USD 530k figure once converted. The Agentic AI Commercialization Review adds a third figure (KES 4.2B EAC TAM) on a different basis again. **These are not three businesses — they are the same AI Lab, described three times with three inconsistent revenue models.** Section 12 below proposes one reconciled model and flags this discrepancy for your finance lead rather than silently picking one number.
4. **Two SmartLabs blueprint documents are near-duplicates.** The *SmartLabs Commercialization Blueprint* and the *SmartLabs Master Commercialization Blueprint* share identical revenue tables, identical architecture diagrams, and near-identical prose — the Master version simply adds the full 45-vendor table. I have treated them as one source and used the Master version as canonical (Section 6).

Where I am reconciling rather than restating, it's marked **[Architect's recommendation]**. Where a claim in one document is contradicted by the more authoritative engineering spec, it's marked **[VERIFY / GAP]**.

---

## 0. Source Documents Consolidated

| # | Document | Role in this guide |
|---|---|---|
| 1 | AI Lab Commercialization & Expansion Strategy (Kenya/East Africa) | Commercial overview — Section 11 |
| 2 | AI Lab & Platform Expansion Strategy — Enterprise AI Services & Commercialization | Primary commercial/technical detail for AI Lab services — Section 11 |
| 3 | **i3 AI Lab — P0 Technical Build Specification** | **Ground truth for current AI Lab state and near-term build** — Section 5 |
| 4 | i3 SmartLabs — Multi-Vendor Lab Strategy on OpenShift | Network/vendor lab engineering — Section 6 |
| 5 | i3 SmartLabs Commercialization Blueprint | Superseded by #6, treated as duplicate |
| 6 | **i3 SmartLabs & AI Platform Master Commercialization Blueprint** | Canonical SmartLabs commercial + architecture doc — Section 6, 12 |
| 7 | i3 SmartLabs — Engineering Runbook | VPC peering, KubeVirt manifests, ops — Section 6.4 |
| 8 | USIU-Africa Academic Collaboration Proposal | Live commercial pilot — Section 9 |
| 9 | AfriqAI: Sovereign Pan-African Frontier Architecture & Strategy | Language sovereignty + agentic product suite — Section 7 |
| 10 | Agentic AI Commercialization & Market Review | Competitive landscape + unification strategy — Section 8 |
| 11 | i3 EduBridge Product Review & Technical Blueprint | Higher-ed wrapper product — Section 9 |

---

## Table of Contents

1. Executive Summary
2. Platform Inventory — What Actually Exists Today (Ground Truth)
3. Target-State Architecture — One Diagram for Four Product Lines
4. Identity, Multi-Tenancy & the Shared `cust-<slug>` Pattern
5. AI Lab: P0 Technical Build (Ground-Truth Engineering Spec)
6. SmartLabs: Multi-Vendor Lab Infrastructure
7. AfriqAI: Language Sovereignty & the Agentic Product Suite
8. Unified Agentic Orchestration Layer
9. i3 EduBridge & the USIU-Africa Pilot
10. Cross-Cutting Security, Governance & Compliance
11. Commercial Product Catalogue (As Proposed Across Sources)
12. Reconciled Financial Model — One P&L, Not Five
13. Consolidated Implementation Roadmap
14. Best Innovations — Prioritized Across All Sources
15. Risk Register
16. Appendix — Model Roster, Glossary, Contacts

---

## 1. Executive Summary

i3 Technologies operates a genuinely rare combination of enterprise assets for an East African systems integrator: a production Kubernetes platform (IBM ROKS), a centralized on-cluster LLM gateway (LiteLLM + Ollama, serving Granite, Qwen, LLaVA), a code-execution sandbox (EvalOS, Firecracker microVMs), a production ERP with tax/mobile-money rails (AfroERP), an omnichannel messaging platform (Engage), a 45-vendor training lab environment (SmartLabs), and a live university partnership (USIU-Africa) already selling a bundled version of these assets.

The strategic opportunity described across all eleven source documents is consistent and correct: **stop selling these as four or five separate things, and unify them behind one gateway, one identity plane, and one commercial model.** Where the documents disagree is on *how far that unification has actually progressed* — several commercial documents describe target-state capability (GPU inference, Kenya-region residency, a unified Agentic Orchestration Bus) in the present tense, while the one ground-truth engineering document (the P0 Build Spec) describes a CPU-only, Frankfurt-only, single-tenant-key platform with those capabilities scoped as **the next 90 days of work, not yet shipped.**

This guide treats the P0 Build Spec as the floor of what's real, builds the target architecture on top of it exactly as its own workstreams (B1–B5) specify, and folds the AfriqAI, Agentic AI, EduBridge and SmartLabs ambitions in as the roadmap that follows P0 — not as a parallel narrative that gets ahead of it in customer conversations.

---

## 2. Platform Inventory — What Actually Exists Today (Ground Truth)

**[Architect's recommendation]** This table is drawn exclusively from the P0 Build Spec's "Current-State Assumptions" (Section 1) — the only document in the set written as an engineering spec rather than a pitch — cross-checked against the SmartLabs Engineering Runbook where it independently corroborates.

| Layer | Current state (verified) | What commercial docs claim (verify before repeating) |
|---|---|---|
| Region | IBM ROKS (OpenShift), **Frankfurt** | USIU proposal, SmartLabs docs describe "Kenya Region" / "IBM Cloud VPC Kenya Region" as primary — **[VERIFY / GAP]**, see Risk #1 |
| Compute | **CPU-only** worker nodes; JupyterHub `Standard`/`Large` profiles | AI Lab docs, USIU proposal, SmartLabs matrix describe GPU pods (NVIDIA A100) as present — **[VERIFY / GAP]**, see Risk #2 |
| Model serving | Ollama + LiteLLM proxy, single master key (`sk-i3-internal`) exposed as an env var — **not yet retired** | Multiple docs describe per-tenant metering/billing as operational; P0 spec defines this as Workstream B2, not yet live |
| Models | `granite-nano`, `qwen-fast`, `qwen-heavy`, `coder`, `vision`, `embed` — Q4_K_M **CPU quants** | Consistent across all documents — this part checks out |
| Notebook UX | JupyterHub + JupyterLab, per-user PVC, 60-min idle culler, 500MB upload limit | Consistent |
| No-code UX | Sage (Open WebUI), same SSO, RAG over uploaded docs | Consistent; Sage's ability to use per-workspace (not master) keys is an **open question** (P0 Spec, Section 9 risks) |
| Multi-tenancy | **Not yet built** — namespace-per-customer (`cust-<slug>`) is Workstream B4-MVP | SmartLabs and EduBridge docs already design against this pattern as if available — reasonable to design against, **not yet safe to sell against** |
| Audit logging | **Not specified / minimal** — WORM audit store is Workstream B4-MVP | AI Lab governance docs describe audit trails as a sellable feature today |
| Observability | Not established — Prometheus/Grafana baseline is part of P0 cross-cutting work | — |
| Existing production namespaces | **10 operational namespaces** on ROKS 4.17 (per SmartLabs Master Blueprint) running EvalOS, AfroERP, Engage, PMaaS, JupyterHub/Sage | Corroborated across SmartLabs and Agentic AI docs — this is real production footprint |
| IBM Cloud accounts | 3 accounts, $3,000/quarter each ($36k/yr total), workload-partitioned (Production / SmartLabs Compute / Model Gateway+GPU) | Consistent across SmartLabs docs 6, 7, 10 |

**Bottom line:** the production applications (EvalOS, AfroERP, Engage, PMaaS) and the CPU-based AI Lab are real and running. GPU inference, Kenya-region residency, per-tenant metering/billing, multi-tenant RBAC, and audit logging are **all specified but not yet built** — they are exactly the five P0 workstreams (Section 5). Every commercial document that describes these as present-tense capability needs to be corrected before its next customer conversation.

---

## 3. Target-State Architecture — One Diagram for Four Product Lines

**[Architect's recommendation]** This merges the SmartLabs "Unified Lab Gateway," the P0 Build Spec's LiteLLM control plane, the Agentic AI Commercialization Review's orchestration bus, and EduBridge's six-layer product stack into one reference architecture. Every subsequent product (SmartLabs, AfriqAI, EduBridge) is a **consumer** of this shared core, not a separate stack.

```
                         [Internet / Enterprise WAN / Campus Network]
                                          │
                    Cloudflare WAF / DDoS Mitigation / Anycast DNS
                                          │
                 i3 Unified Edge Gateway (Envoy / IBM ALB) — labs.i3technologies.co.ke
                                          │
        ┌─────────────────────────────────┼─────────────────────────────────┐
        ▼                                 ▼                                 ▼
  IDENTITY PLANE                  AGENTIC ORCHESTRATION            LAB / PRODUCT PLANE
  Keycloak SSO (i3-auth)          & MCP GATEWAY                    ├─ SmartLabs (45-vendor
  Realm: i3 | Clients:            • Intent classification            matrix, Containerlab/
  evalos-spa, jupyterhub,           (English/Swahili/Sheng)           KubeVirt/EVE-NG)
  sage, afroerp, engage,          • ReAct planner (reason→act→      ├─ EduBridge (Moodle +
  pmaas, moodle                     observe→confirm)                 H5P + BigBlueButton)
  OpenBao Vault: secrets,         • Tool calls → AfroERP, Engage,   └─ Customer sandboxes
  ephemeral keys                    EvalOS, SmartLabs APIs             (POC/dev/prod mirror)
        │                                 │
        ▼                                 ▼
  MODEL GATEWAY (LiteLLM, single control plane — ALL clients route through here)
  ├─ ollama-cpu (existing): granite-nano, qwen-fast, embed
  ├─ ollama-gpu (P0 Workstream B1, NOT YET LIVE): qwen-heavy, coder, vision
  ├─ Per-key budgets/metering → Postgres spend_logs (P0 Workstream B2, NOT YET LIVE)
  └─ PII pre-filter / guardrails (P0 Workstream B5-MVP, NOT YET LIVE)
        │
        ▼
  DATA & PLATFORM LAYER
  PostgreSQL (Crunchy PGO HA) · ChromaDB (RAG) · Object Storage (audit WORM,
  model blobs) · Kafka/event bus (where used by PMaaS/Engage) · Prometheus/Grafana
        │
        ▼
  INFRASTRUCTURE
  IBM ROKS Frankfurt (current) ──▶ IBM ROKS / Nairobi colo (P0 Workstream B3, NOT YET LIVE)
  3× IBM Cloud accounts (Production / SmartLabs Compute / Model+GPU Gateway)
```

**Architecture rule (restated from the P0 spec, applies to every product built on top):** clients never talk to Ollama, EvalOS, AfroERP or Engage directly — every call routes through the identity plane and the model/agentic gateway, so metering, guardrails, and audit apply uniformly whether the caller is a SmartLabs student, a EduBridge AI Tutor, an AfriqAI SME Coworker, or an internal i3 operations agent.

---

## 4. Identity, Multi-Tenancy & the Shared `cust-<slug>` Pattern

**[Architect's recommendation]** Three of your documents (P0 Spec §5, EduBridge §3.3/§9, SmartLabs Runbook) independently converge on the same tenancy pattern without cross-referencing each other — worth stating once as the platform-wide standard rather than three products each re-describing it:

- **One Keycloak realm (`i3`)**, shared across all client applications (`evalos-spa`, `jupyterhub`, `sage`, `afroerp`, `engage`, `pmaas`, and — once EduBridge P0 ships — `moodle`).
- **One OpenShift namespace per enterprise/institution customer** (`cust-<slug>`), used identically by AI Lab enterprise tenants (P0 Workstream B4) and EduBridge institutions (`cust-<university-slug>`).
- **SSO group claims drive RBAC everywhere**: `i3-users` / `cust-acme` group membership determines JupyterHub pod placement, Moodle role, Smart Labs RBAC tier, and AI Lab project scope — from **one** group claim, not four separate access-control systems.
- **Per-project LiteLLM keys** (P0 Workstream B2) are the metering unit for every downstream product — SmartLabs lab sessions, EduBridge AI Tutor sessions, and AfriqAI SME Coworker usage all attribute spend to a project key, never the shared master key.

This pattern is currently **designed but only partially built** — the identity plane (Keycloak, existing) is real; the namespace-per-tenant RBAC and audit logging (B4-MVP) is not yet shipped. Every product roadmap in this document assumes B4 lands first.

---

## 5. AI Lab: P0 Technical Build (Ground-Truth Engineering Spec)

This section is carried forward from the P0 Build Spec largely unchanged — it is already the most rigorous document in the set. **All downstream products (SmartLabs GPU labs, EduBridge AI Tutor, AfriqAI SME Coworker) depend on B1–B5 shipping.**

### 5.1 Workstream B1 — GPU Inference Tier & Model Autoscaling

**Objective:** cut first-token latency for `qwen-heavy`/`coder`/`vision` from 5–30s (CPU) to <3s (GPU, warm).

- Separate `ollama-gpu` deployment pool (existing `ollama-cpu` untouched); one model per GPU (7B–14B Q4 fits a 24GB card).
- Hardware: GPU-1 (1× NVIDIA L4/A10/A30, 8vCPU/64GB) for `qwen-heavy`+`coder`; GPU-2 (month 2) for `vision`. Node taint `gpu=true:NoSchedule` keeps notebook pods off GPU nodes.
- **[VERIFY]** NVIDIA vs AMD ROCm bake-off (2 weeks) before hardware commitment — do not let procurement block B2/B4/B5, which are hardware-independent.
- LiteLLM routing config maps aliases → deployments; fallback rule: `ollama-gpu` health-check failure → route falls back to CPU pool with a 5× latency warning logged (availability over speed).
- KEDA autoscaling on queue depth/GPU utilization ≥75% for 5 min; scale-to-**one** warm minimum (not scale-to-zero — GPU cold start is minutes).
- **Acceptance:** `qwen-heavy` p50 <3s/p95 <6s warm; `coder` p50 <2s; 10 concurrent requests no 5xx, p95 <30s; GPU node failure → failover within 60s; existing notebook code runs unmodified.
- **Estimate:** 2 engineers × 3–4 weeks (excl. hardware lead time).

### 5.2 Workstream B2 — Metering, Quotas & Billing

**Objective:** every API call attributable to key → project → customer; budgets enforced before spend.

- LiteLLM's native per-key budgets/rate limits + Postgres `spend_logs`, plus a `billing` schema: `customers`, `projects`, `api_keys`, `monthly_usage` (tokens in/out/embed, compute-minutes, GPU-minutes, amount in KES).
- Master key `sk-i3-internal` **retired for client use**, retained 30 days for migration.
- Pricing engine v1: per-1M-token rates per alias (cost-plus, fixed quarterly); notebook compute from JupyterHub culler + pod resource-hours; Sage usage via per-workspace keys (not master key — **open question** whether Sage supports this natively).
- Nightly ETL → `monthly_usage` → per-customer CSV + branded PDF statement (clean export, not an accounting integration in v1).
- Guardrails: hard budget cap → friendly 429-style rejection; soft alerts at 50/80/95%; per-key RPM limits against runaway student-notebook loops.
- **Acceptance:** ≥99% token attribution accuracy; budget-exceeded calls rejected within 60s; month-end export with zero manual edits; JupyterHub CPU-hours ±10% of manual estimate; Sage metered per workspace.
- **Estimate:** 1–2 engineers × 2–3 weeks (parallelizable with B1).

### 5.3 Workstream B3 — Nairobi Region Deployment

**Objective:** a second, Kenya-resident deployment region, converting the sovereignty story from marketing claim to **verifiable, contractual claim.**

- **Recommended:** Option B — Nairobi colocation (iColo/Africa Data Centres/Node Africa) for the inference + data plane, Frankfurt as DR/control-plane backup initially. Option A (ROKS in-region, if IBM Cloud offers a genuinely Kenya-resident location) is the fallback if hardware lead times slip.
- **Contractual promise enforced architecturally, not by policy:** no customer prompts/documents/embeddings/audit logs replicate to Frankfurt — simply don't configure replication for those buckets/PVCs. Frankfurt only ever holds encrypted, non-resident **configuration** backups.
- One GitOps config repo, per-region overlays differing only in endpoints/storage classes.
- Failover: manual in v1 (documented runbook, RTO 4h); automated DNS failover is P1.
- **Acceptance:** residency audit confirms zero Frankfurt replica of customer prompts/uploads/embeddings/audit logs; EA-user latency ≥60% better than round-trip to Frankfurt; DR drill executed within RTO 4h; existing client code runs unchanged against region-specific base URL.
- **Estimate:** 2 engineers × 4–6 weeks + procurement lead time; can overlap B1/B2 (same manifests).

**[Architect's recommendation]** This workstream is the single highest-priority item in the entire program, given that Section 2's Risk #1 shows the sovereignty claim is already being made commercially before it's true. Recommend pulling B3 forward or explicitly correcting current sales collateral (USIU proposal, AI Lab commercialization decks) until it ships.

### 5.4 Workstream B4-MVP — Multi-Tenancy, RBAC & Audit Logging

**Objective:** enterprise tenants get project spaces with RBAC and tamper-evident audit trails — the minimum a bank/procurement officer or a university DPO needs to see.

- OpenShift namespace per customer (`cust-<slug>`); JupyterHub `kubespawner` places pods via SSO group claims.
- Three roles per namespace: `admin`, `developer`, `viewer` — mapped from SSO groups, no separate user database.
- Master key disabled for interactive use, scoped to a break-glass service account only.
- Audit: LiteLLM request log enriched with `project_id`/model/tokens/latency, shipped to append-only WORM object storage (7-year retention class, configurable per contract); OpenShift API audit events for customer namespaces forwarded to the same store. Hot 90 days, cold archive per contract.
- **Acceptance:** SSO group isolation verified (no cross-tenant resource listing); key isolation verified; 100% audit attribution on a 1,000-request sample with tamper-evidence (object lock); offboarding revokes access within 5 minutes.
- **Estimate:** 1–2 engineers × 2–3 weeks.

### 5.5 Workstream B5-MVP — Model Governance Pack (Minimum Viable)

**Objective:** enough governance to sign off client deployments and satisfy a bank's risk review.

- Evaluation harness (`eval/` repo): task suites per alias (summarization, Q&A faithfulness, code correctness, instruction-following, 50–100 gold items each) **plus a Swahili/Sheng suite v1** (100 prompts, comprehension/translation/idiom, rubric-scored with human spot-checks).
- PII pre-filter (MVP): LiteLLM pre-call hook, NER-based (presidio-style) redaction/detection of emails, KE-format phone numbers, ID numbers — mode `detect` first, `redact` after 2 weeks of false-positive tuning.
- Model cards: one page per alias (capability, eval scores incl. Swahili, GPU/CPU latency, limitations, intended use), published to the customer portal.
- Release gate: any model/quant change must pass the harness + produce an updated model card before promotion to `prod`.
- **Acceptance:** full harness in <2h unattended via CI; Swahili pack scored for all six aliases; PII recall ≥90% on a seeded 200-document KE-PII test set; release gate blocks an unpassed test model (negative test).
- **Estimate:** 1 ML engineer × 3 weeks, plus part-time Swahili content reviewer.

### 5.6 Cross-cutting (all workstreams)

- **GitOps:** one repo, Frankfurt + Nairobi overlays, PRs gated by the acceptance tests above.
- **Secrets:** `LITELLM_API_KEY`/DB credentials move to a secrets manager (Vault/OpenBao); the literal `sk-i3-internal` string must disappear from docs, notebooks, and env dumps.
- **Backups:** Postgres PITR, object-store versioning, quarterly restore drill.
- **Observability baseline:** Prometheus + Grafana + alertmanager; SLI dashboards for gateway availability, p50/p95 latency per alias, GPU utilization, spend-rate vs budget.

### 5.7 90-Day Delivery Plan (P0 program)

| Weeks | Track 1 (Infra) | Track 2 (Platform) | Track 3 (Governance) |
|---|---|---|---|
| 1–2 | GPU procurement + NVIDIA/ROCm bake-off | Billing schema + LiteLLM key model design | Eval harness skeleton + Swahili item collection |
| 3–5 | `ollama-gpu` deploy + routing + fallback; latency baseline | Per-key metering live in staging; nightly ETL v1 | Task suites v1; runner CI |
| 6–8 | KEDA autoscaling; load tests | Quotas/alerts; invoice export pilot (2 friendly customers) | PII detect mode on staging |
| 9–12 | Nairobi region stand-up (Option B) + residency verification | B4 namespace/RBAC pilot with first enterprise tenant; master-key retirement notice | B5 release gate enforced; model cards published |

**Definition of done for P0:** all acceptance criteria B1-1…B5-4 pass in staging; two paying pilot tenants live on metered keys; Nairobi residency verified by audit; governance pack v1 published. **Nothing in Sections 6–9 below should be sold as sovereign, GPU-accelerated, multi-tenant, or audit-ready until this line is crossed.**

---

## 6. SmartLabs: Multi-Vendor Lab Infrastructure

### 6.1 Current recommendation: hybrid three-tier lab model

From the Multi-Vendor Lab Strategy review — this supersedes the "one VM per device" mindset of the original vendor matrix:

| Tier | Technology | Use case |
|---|---|---|
| **Tier 1 — Container-native** (highest density, lowest cost) | Containerlab + cEOS, cRPD, FRR, SONiC, SR Linux | Protocol labs (BGP/OSPF/EVPN), CI/CD-validated network automation |
| **Tier 2 — Full VMs via OpenShift Virtualization (KubeVirt)** | Cisco CAT8000v/CSR1000v, Palo Alto VM-Series+Panorama, FortiGate+FortiManager, Juniper vSRX/vMX, Check Point, F5 BIG-IP, ISE, Windows | Devices needing full feature fidelity, connected via Multus CNI / User-Defined Networks |
| **Tier 3 — Persistent shared emulation** | EVE-NG Pro / CML as long-lived VMs | CCIE-scale, SD-WAN, complex multi-vendor topologies, rich GUI |

**Innovation carried forward:** a thin **Lab Orchestrator** service (Python/Go operator or web UI) accepting a high-level spec ("I need a 6-node BGP + 2 firewall lab") and deploying the right mix of containers/VMs/EVE-NG nodes automatically — this is the same "Lab-as-a-Service API" pattern EduBridge's Layer 3 later reuses (Section 9.3).

### 6.2 The 45-vendor matrix (canonical — from the Master Commercialization Blueprint)

Organized into six namespace-isolated domains: `labs-networking` (Cisco, Juniper, Aruba, Arista), `labs-security` (Fortinet, Palo Alto, Check Point, Sophos, CrowdStrike), `labs-cloud` (IBM Cloud, AWS, Azure, GCP via LocalStack/emulators), `labs-virtualization` (IBM Power, VMware, Nutanix, Red Hat), `labs-data-observability` (Oracle, Splunk, Dynatrace, Veeam, F5), plus 30+ additional lower-priority vendor pods (storage, backup, UC, ITSM, CRM). Full setup/OpEx table retained in Appendix (Section 16).

**[Architect's recommendation]** With 45 vendors listed and only a handful marked HIGH priority, sequence build-out strictly by the priority column — Cisco, Juniper, Fortinet, Palo Alto, Check Point, VMware, AWS/GCP/Azure, IBM, Red Hat first. Do not attempt all 45 concurrently; this is the same scope-discipline risk flagged in your other engagements' documents.

### 6.3 Licensing strategy — zero-cost ramp-up

- Red Hat Developer for Organizations & Partner Portal — up to 16 free RHEL instances, OpenShift dev tiers, NFR licenses for AAP/RHACM.
- IBM Partner Plus Software Access Catalog — Db2 SaaS, MQ, API Connect, watsonx Orchestrate practice licenses.
- Vendor NFR enrollment — Fortinet Engage, Palo Alto NextWave, Check Point Partner Program, VMware Partner Connect.
- Open-source core: Crunchy Data PGO, Ollama+LiteLLM, Monaco Editor, OpenBao.
- **Legal note (carried forward without dilution):** always obtain vendor images through legitimate channels (customer portal, evaluation request, DevNet). **Never distribute or store unauthorized IOS/PAN-OS/FortiOS images.**

### 6.4 Infrastructure automation & the 3-account IBM Cloud fabric

- **Transit Gateway** interconnects Account 1 (Production Core), Account 2 (SmartLabs Compute), Account 3 (Model Gateway & GPU) via Terraform (`ibm_tg_gateway`/`ibm_tg_connection`).
- **KubeVirt VM manifests** for full-fidelity appliances (e.g., FortiGate) run as `VirtualMachine` resources in student namespaces, `containerDisk` image pulled from the internal registry.
- **Ansible Automation Platform (AAP)** playbooks provision isolated namespaces + ResourceQuotas per student, deploy lab pods, and schedule automated teardown (`at now + 4 hours`) — necessary at 2,500 concurrent-student target scale.
- **Token accounting daemon** reconciles LiteLLM spend against the EvalOS Postgres billing ledger via a cron script — this is the SmartLabs-side consumer of the AI Lab's B2 metering work (Section 5.2); it cannot go live for real billing until B2 ships.

### 6.5 Scalability and phased rollout

Phase 0 (2–4 weeks): enable KubeVirt, dedicated namespaces/quotas, Containerlab on worker nodes, Git repo for topologies. Phase 1 (4–6 weeks): Tier-1 container labs live, 2–3 high-priority VMs via KubeVirt, pilot with 5–10 engineers. Phase 2 (6–10 weeks): persistent EVE-NG/CML instances, GitOps topology promotion, observability. Phase 3 (ongoing): full Lab-as-a-Service portal with TTL auto-teardown and cost reporting.

---

## 7. AfriqAI: Language Sovereignty & the Agentic Product Suite

### 7.1 The linguistic problem

Standard English-centric tokenizers fragment Swahili words into 3.5–5.2 tokens (e.g., "walituonyeshana" → 5 nonsensical fragments), inflating both latency and cost for the ~600M-speaker Kiswahili trade-language corridor across EAC/SADC/COMESA.

### 7.2 Target architecture beyond the P0 baseline

| System layer | Current i3 baseline (= P0 spec ground truth) | AfriqAI frontier target |
|---|---|---|
| Compute | ROKS Frankfurt, CPU inference, 5–30s latency | Hybrid: local Nairobi GPU nodes (L40S/H100/A100) + Frankfurt overflow — **this is P0 Workstream B1/B3, not a separate build** |
| Inference engine | Single Ollama instance behind LiteLLM | Distributed vLLM/TensorRT-LLM, FP8/AWQ, speculative decoding, dynamic multi-LoRA adapter routing |
| Code execution | EvalOS: Firecracker microVMs, ~125ms cold start, 4 profiles | EvalOS++: Redis-backed distributed scheduler, persistent workspace snapshots, MCP tool exposure for agentic REPL |
| Frontends | Sage (Open WebUI), JupyterHub — browser-only | Afriq Desktop (Tauri v2), Afriq Web PWA, Afriq Code CLI terminal agent |
| Linguistic coverage | Standard tokenizers, poor vernacular grammar, no Sheng | Custom Bantu-aware BPE tokenizer (64k vocab) + LoRA/full fine-tunes |

### 7.3 Morphological tokenizer & dialectal corpus pipeline

- **Bantu-aware BPE tokenizer:** explicit vocabulary injection for Swahili subject prefixes (ni-, u-, a-, tu-, m-, wa-), tense markers (-na-, -li-, -ta-, -me-, -nge-), object infixes and derivative extensions — claimed 2.8× token-count reduction vs. standard Llama-3/Qwen tokenizers.
- **Three-tier dialectal corpus:** Tier 1 (Kiswahili Sanifu + coastal dialects — parliamentary Hansards, BBC Swahili, Taifa Leo, legal statutes: 15B+ token high-purity pre-training corpus); Tier 2 (Dynamic Sheng — social scraping, matatu-culture corpora, weekly fine-tuning loop for lexical drift); Tier 3 (Vernaculars — Gĩkũyũ, Dholuo, Luhya, Kalenjin, Kĩkamba, Ekegusii, Maa via vernacular radio ASR, domain-specific LoRA adapters).
- **Dynamic Sheng ingestion pipeline:** social scraping → slang-drift detector (identifies new n-grams/semantic shifts) → daily synthesized DPO preference pairs → fast router model (detects Sheng/vernacular) → base model + dynamic Sheng LoRA.

**[Architect's recommendation]** This is genuinely differentiated IP and the strongest technical moat in the whole document set — but it depends entirely on P0's GPU tier (B1) shipping first. Sequence AfriqAI's Phase 1 (tokenizer, vLLM migration) to start only after B1 acceptance criteria pass, not in parallel with unproven hardware.

### 7.4 Four-tier product matrix

1. **Afriq Code & Workspace** — autonomous terminal agent / IDE extension, ReAct loop (Search→Edit→Sandbox Exec→Git Diff→Verify), tests run inside EvalOS microVMs, bilingual code comments.
2. **Afriq Coworker for SMEs** — automated M-Pesa statement parsing, KRA eTIMS filing, vernacular WhatsApp/SMS CRM, supply-chain forecasting.
3. **Afriq Omnimodal Chat** — Tauri v2 desktop app, Whisper-Swahili STT + MMS-TTS, vision diagnostics (crop disease, medical prescriptions, handwritten invoices).
4. **Afriq Box** — air-gapped sovereign appliance (2U, 2× L40S/A100, OpenShift/k3s + LiteLLM + vLLM preloaded) for banks, telcos, legal firms, defense — the ultimate expression of the B3 sovereignty claim, once B3 itself is real.

### 7.5 Security & DLP

Keycloak 24 realm federation (consistent with Section 4's shared identity plane); in-flight PII redaction (Kenyan National ID, M-Pesa transaction IDs, bank accounts) before prompts reach models — **this is the same capability as P0 Workstream B5's PII pre-filter, not a separate build.**

---

## 8. Unified Agentic Orchestration Layer

### 8.1 The core strategic insight (Agentic AI Commercialization Review)

i3 already owns four pillars most AI startups don't: sovereign inference (AI Lab), ultra-low-latency sandboxed execution (EvalOS), a local financial/ERP core with M-Pesa and eTIMS rails (AfroERP), and an omnichannel engagement engine (Engage). **The vulnerability is that these exist as separate silos** — Sage is an isolated chat interface, EvalOS an isolated exam tester, AfroERP has an isolated assistant (Mfumo), Engage has an isolated bot (Nuru). Global frontier competitors win by operating as autonomous agents with tool-calling loops *across* entire ecosystems — i3's four-pillar ownership is the raw material for the same thing, applied locally.

### 8.2 Competitive landscape (from the Agentic AI Review — retained for the board)

| Competitor class | Key players | Where they threaten | i3's moat |
|---|---|---|---|
| Global frontier giants | OpenAI, Anthropic, Google Cloud | Developer mindshare for coding/office copilot | High cost, 3.5× Swahili token inflation, zero eTIMS/Daraja rails, ODPC data-egress exposure |
| Regional telco/cloud | Safaricom (Baze AI), Microsoft ADC Nairobi, AWS Local Zones, Liquid | Bundling generic chatbots with connectivity packages | They sell raw infrastructure; lack sovereign models, sandboxes, deep ERP workflows |
| African NLP labs | Lelapa AI, Sunbird AI, Masakhane, Amini | Vernacular NLP dominance | They lack full-stack enterprise execution (ERP + SMS + code sandboxes) |
| Regional SaaS/CRM | Zoho Africa, Yellow.ai, Wati.io | WhatsApp chatbot commoditization | Most use static decision trees; none offer true autonomous agentic execution |

### 8.3 Unified architecture — the Agentic Operating Bus

This is the same gateway shown in Section 3, described here at the tool-call level:

```
i3 Agentic Orchestration & MCP Gateway
• Intent classification & fast routing (Kiswahili/Sheng/vernacular/English)
• Autonomous multi-turn planner (ReAct: Reason → Action → Observe → Confirm)
• Model router: LiteLLM proxy (granite-nano/qwen-fast/qwen-coder/llava)
         │ tool call            │ tool call            │ tool call
         ▼                      ▼                      ▼
   AfroERP Engine          Engage Platform         EvalOS Sandbox
   M-Pesa Daraja STK       Africa's Talking        Firecracker MicroVM
   KRA eTIMS invoicing     WhatsApp Meta API       Code testing & build
   Ledger & payroll        Dynamic campaigns       IaC & bash execution
```

### 8.4 Named agent upgrades (existing co-workers, made autonomous under governance)

- **Mfumo++** (AfroERP finance): autonomous M-Pesa statement reconciliation, credit-note generation, eTIMS e-invoice triggering; autonomous debt-chasing (evaluates aging invoices, drafts customized reminders via Engage). **Tool-call risk tier: 2–3 — should inherit the risk-tier/human-approval pattern already specified for the FORD-Asili and i3 PMC agent catalogues** (see cross-engagement note below).
- **Nuru++** (Engage growth): vernacular customer segmentation (Sheng/Swahili/Gĩkũyũ campaign drafting), closed-loop attribution from message response to AfroERP invoice payment.
- **Sage Code** (developer copilot): Qwen-Coder + EvalOS microVMs; reads compiler stack traces, writes patches, re-tests, opens PRs autonomously — **highest-autonomy agent in the catalogue; needs the same "never autonomous: irreversible actions" boundary applied elsewhere in your agent governance work.**

**[Architect's recommendation]** You've now specified agent risk-tiering and human-approval gating independently in at least two other engagements (the i3 PMC guide's Agent Platform, and the FORD-Asili guide's agent catalogue). Mfumo++, Nuru++ and Sage Code should adopt the **same risk-tier table** (0-Read / 1-Low-risk / 2-Customer-facing / 3-Business-impacting-human-approval-default / 4-High-risk-recommendation-only) rather than being specified a third time with different language. This is a governance consistency gap, not a technical one.

### 8.5 Phase 1 — "Eat Your Own Dog Food" internal rollout (before any external sale)

| Internal area | Target agentic workflow | Systems used |
|---|---|---|
| Bootcamp/Academy admissions | Admissions Agent scores entrance quizzes (EvalOS), provisions Keycloak SSO, sends WhatsApp welcome (Engage) | EvalOS + Keycloak Admin API + Engage + n8n |
| Client invoicing & eTIMS | Finance Coworker reads milestone completions, issues AfroERP invoice, triggers M-Pesa STK, validates KRA CU signature | AfroERP + Daraja + eTIMS + n8n |
| Student code assessment | Sage Grader runs test suites in EvalOS, analyzes errors with Qwen-Coder, posts feedback | EvalOS + LiteLLM (coder) + Directus CMS |
| Client support/SLA monitoring | Internal Ops Sentinel ingests support tickets, runs ROKS health diagnostics, creates tasks | Engage + LiteLLM + AfroERP Support Desk |

**Dog-fooding metric:** validate 80% of internal invoicing, grading, and customer messaging runs autonomously without human intervention **before** offering this externally.

---

## 9. i3 EduBridge & the USIU-Africa Pilot

### 9.1 What EduBridge actually is

Three existing i3 assets — i3 Academy (Skillsoft/Percipio), i3 Smart Labs, and the AI Lab — are currently **sold as adjacent offerings bundled into bespoke proposals** (USIU being the live example). EduBridge productizes them into one licensable platform: LMS core + authoring layer + the existing labs fabric (exposed as embeddable/gradable, not a separate portal) + the AI Lab repositioned as AI Tutor/assessment copilot + a new OTT/video delivery layer none of the three existing assets provide.

### 9.2 Six-layer architecture

```
1. LMS CORE (Moodle, self-hosted, white-labeled)
2. AUTHORING STUDIO ("i3 Author": H5P + Adapt Learning + i3 Lab Scenario Builder
   + AI-assisted authoring copilot on the AI Lab's LiteLLM gateway)
3. PRACTICAL LABS FABRIC (i3 Smart Labs — exposed via LTI 1.3 Deep Linking + AGS,
   no new infrastructure, thin integration layer only)
4. AI LAYER (i3 AI Lab, repositioned — same gateway, same model roster, same
   governance pack, reused not duplicated)
5. OTT / VIRTUAL DELIVERY (new build: BigBlueButton live + PeerTube VOD +
   Whisper auto-captioning)
6. CREDENTIALING, ANALYTICS & TALENT PLATFORM (Learning Locker LRS + Open
   Badges 3.0 + talent-platform API)

Cross-cutting: Keycloak SSO · cust-<university-slug> multi-tenancy ·
Kenya DPA 2019 residency (depends on P0 Workstream B3) · WORM audit logging
```

### 9.3 Build-vs-buy decisions

| Layer | Decision | Rationale |
|---|---|---|
| LMS | **Moodle**, self-hosted, extended (not built from scratch) | Largest plugin ecosystem, native LTI 1.3, mature gradebook, familiar to African university IT teams |
| Interactive authoring | **H5P** (open-source) | Industry-standard interactive content with xAPI output |
| Branching scenarios | **Adapt Learning Framework** (open-source) | Free alternative to Articulate/Captivate, Git-versionable |
| Lab scenario spec | **i3 Lab Scenario Builder** (new, thin) | YAML/Git-based spec compiling to a SmartLabs lab definition — keeps content out of a proprietary lab vendor format |
| Live classroom | **BigBlueButton** (open-source) | Native Moodle LTI plugin, lowest ops burden, recordings auto-publish to VOD |
| VOD library | **PeerTube** (open-source, federation disabled) | Self-hosted, adaptive HLS, i3-branded front end |
| LRS | **Learning Locker** (open-source, xAPI-native) | Makes the badge/dashboard promises in the USIU proposal *actually real-time* |
| Credentials | **Open Badges 3.0** | Verifiable, LinkedIn-postable, auto-triggered from LRS events |

**i3's actual defensible IP** in this stack is the **i3 Author Copilot** (faculty uploads source material → RAG ingestion via the AI Lab → LiteLLM drafts quiz bank + branching scenario + lab scenario skeleton in one pass) — everything else in the layer list is open-source, which is itself a selling point to procurement committees wary of vendor lock-in (SCORM/xAPI/Common Cartridge export keeps content portable).

### 9.4 The USIU-Africa pilot — reconciling the live deal against the P0 build

| USIU proposal claim | P0 Build Spec reality | Action |
|---|---|---|
| "IBM Cloud VPC (Kenya Region): Primary infrastructure with local data residency" | Current platform is Frankfurt-only; Nairobi region is Workstream B3, not shipped | **[GAP]** Correct in next USIU-facing update, or accelerate B3 ahead of Semester 1 pilot go-live |
| "GPU-Enabled AI/ML Labs: NVIDIA A100 GPU pods" | Current compute is CPU-only; GPU tier is Workstream B1, not shipped | **[GAP]** Same — either accelerate B1 or scope the pilot's AI/ML labs honestly as CPU-tier until B1 lands |
| "Student progress dashboards... real-time" | Depends on Learning Locker LRS (EduBridge P2, months 8-12) — not yet built | Pilot's dashboard promise should be scoped to what Percipio's native reporting already provides until EduBridge P1/P2 ship |
| "IBM Digital Badges... blockchain-verified... real time" | Depends on Open Badges 3.0 + LRS integration (EduBridge P2) | Same — scope near-term delivery to Percipio's existing badge mechanism |

**[Architect's recommendation]** None of this means walk back the USIU relationship — it means the **EduBridge phased plan (9.5) is the mechanism that makes the existing proposal's claims true over the pilot's 12 months**, not a separate roadmap. Treat Phase 1 (Months 1-2) of the USIU rollout as "stand up Moodle + LTI links to what already exists" — genuinely deliverable now — and be explicit internally that Pillars involving GPU labs, real-time dashboards, and residency claims ride on the AI Lab's own P0 program finishing on the same clock.

### 9.5 Phased delivery (EduBridge)

| Phase | Timeline | Deliverable |
|---|---|---|
| P0 — Foundation | Months 1–3 | Moodle multi-tenant; SSO via Keycloak; LTI links to existing SmartLabs/Percipio — enough to run the USIU pilot on a proper LMS |
| P1 — AI + Authoring | Months 4–7 | i3 Author (H5P/Adapt + AI Copilot); AI Tutor (RAG-grounded, per-course); Lab-as-a-Service API with LTI AGS auto-grading |
| P2 — OTT & Talent Platform | Months 8–12 | BigBlueButton + PeerTube; Learning Locker LRS; Open Badges 3.0 automated; talent-platform API |
| P3 — Regional Alliance | Year 2 | Second/third university onboarded on shared multi-tenant infra; East Africa University Technology Alliance formalized |

### 9.6 Commercial tiers

| Tier | Includes | Indicative price |
|---|---|---|
| Foundation | Moodle core + theme, Percipio access, standard SmartLabs (no GPU), no AI Tutor | USD 60–80/student/year |
| Practical+ (matches USIU pilot scope) | Foundation + full SmartLabs incl. GPU labs + metered AI Tutor + OTT | USD 150/student/year |
| Institution-Wide | Practical+ across departments, i3 Author licensed, dedicated account manager | Custom/volume |
| Regional Alliance | Shared infra, cross-institution content exchange, joint IBM/Red Hat branding | Consortium pricing |

---

## 10. Cross-Cutting Security, Governance & Compliance

**[Architect's recommendation]** Consolidated once from scattered mentions across AI Lab, SmartLabs, AfriqAI, and EduBridge documents — this is the platform-wide governance baseline every product line above inherits.

| Control | Requirement | Owning workstream |
|---|---|---|
| Data residency (Kenya DPA 2019, CBK Prudential Guidelines) | No cross-border transfer of sensitive customer/student data; enforced architecturally (no replication config), not by policy alone | AI Lab B3 |
| PII protection | NER-based pre-filter redacts National ID, M-Pesa transaction IDs, phone numbers before logging | AI Lab B5-MVP; reused by AfriqAI (7.5) and EduBridge (9.2 Layer 4) |
| Multi-tenant isolation | Namespace-per-customer, SSO-group-driven RBAC, no shared user database | AI Lab B4-MVP; reused by SmartLabs (Ansible-provisioned quotas) and EduBridge |
| Audit logging | WORM object storage, 7-year retention class, tamper-evident | AI Lab B4-MVP |
| Secrets management | Vault/OpenBao; retire hardcoded `sk-i3-internal` | AI Lab cross-cutting (5.6) |
| Model governance | Evaluation harness + Swahili suite + model cards + release gate | AI Lab B5-MVP |
| Vendor image legality | Only legitimate channels (customer portal, DevNet, NFR programs) — never unauthorized IOS/PAN-OS/FortiOS images | SmartLabs (6.3) |
| Agent risk-tiering | 0-Read → 4-High-risk-recommendation-only, human approval default at tier 3+ | Agentic Orchestration (8.4) — **should reuse the risk-tier model already specified in your i3 PMC and FORD-Asili engagements, not redefine it a third time** |

---

## 11. Commercial Product Catalogue (As Proposed Across Sources)

**[Architect's recommendation]** Collated from the AI Lab commercialization docs — presented as a catalogue for review, not yet reconciled into one price list (see Section 12 for why).

| Service line | Target market | Deliverable | Pricing (as proposed) |
|---|---|---|---|
| Sovereign Banking AI Appliance (private on-prem RAG) | Commercial banks, SACCOs, microfinance | Turnkey OpenShift+LiteLLM+ChromaDB inside bank's air-gapped DC, Finacle/T24 integration | Setup $25k–$60k; SLA $15k/yr |
| eTIMS & Tax Intelligence Co-Pilot | Manufacturing, wholesale, retail, audit firms | AI agent on KRA rules, auto-validates invoices/HS codes/withholding | SaaS $150–$450/mo; enterprise $8k setup |
| WhatsApp & Voice Conversational AI | Telcos, e-commerce, utilities, insurance | Two-way WhatsApp/voice agent with M-Pesa STK checkout | Setup $6k–$18k; usage $0.015/conversation |
| AI Governance, Risk & Audit Advisory | CBK/CMA-regulated firms, healthcare | Bias audits, KDPA pipeline certification, MRM docs, guardrails | Fixed $12k–$30k; retainer $2.5k/mo |
| Enterprise AI Transformation Bootcamp | Corporate IT teams, state corporations | 10-day hands-on upskilling on i3 SmartLabs | $10k–$25k/cohort (≤20 engineers) |
| Enterprise Private RAG Studio | Banks, law firms | No-code document ingestion + secure query UI | $15k setup + SLA |
| Autonomous Agent Builder & Orchestrator | Banks, logistics, insurance | LangGraph/CrewAI multi-agent workflows into AfroERP | $10k–$35k/engagement |
| Kenyan Vernacular Voice AI | Rural banking, microfinance, telcos | IVR automation, Swahili/code-switching STT/TTS | Bundled into appliance/engagement pricing |
| AI Governance/Trust Guardrail Shield | CBK-regulated banks, healthcare | NeMo Guardrails + PII filters in LiteLLM proxy | $1,200/mo add-on |
| Afriq SME Coworker | Retailers, clinics, SACCOs, law firms | eTIMS + M-Pesa + WhatsApp CRM bundle | KES 3,500–7,500/mo |
| Afriq Developer & Edu API | Startups, agencies, universities | Token metering + MicroVM execution fee | Pay-per-token + KES 0.50/sandbox run |
| Afriq Box (sovereign edge) | Government, defense, judiciary, Tier-1 banks | Turnkey hardware lease + local licensing | KES 6M–18M turnkey |
| SmartLabs — Customer & Corporate Training | Individuals, universities, enterprise teams | 45-vendor certification tracks | Ksh 25k–150k/seat |
| SmartLabs — Labs-as-a-Service | System integrators, banks, ISVs | Isolated POC/dev-test/production-mirror environments | Ksh 100k–500k/month |
| SmartLabs — Implementation Services | Enterprise network/security/cloud projects | Deployments unlocked by pre-validated lab POCs | Ksh 2.5M–7.5M/project |
| SmartLabs — Managed Services | Enterprise SLA clients | Day-2 ops, model fine-tuning, patch compliance | Ksh 2.5M–5.0M/yr retainer |
| EduBridge tiers | Universities/colleges | See Section 9.6 | USD 60–150+/student/year |

**[Architect's recommendation]** Several rows above describe **the same underlying capability sold under three names and three price structures** — e.g. "AI Governance/Trust Guardrail Shield" ($1,200/mo) and the "PII pre-filter" specified as a free/included platform feature in the P0 Build Spec (B5-MVP) are the same NeMo/presidio-style filter. Before this catalogue goes to a sales team, someone needs to decide: is PII redaction a **platform feature** (included, differentiator) or a **billable add-on**? Right now two documents answer that question differently.

---

## 12. Reconciled Financial Model — One P&L, Not Five

As flagged in the Reviewer's Note, five documents model overlapping revenue for what is largely the same underlying platform. This section does not invent a new number — it lays the five out side-by-side so your finance lead can reconcile them, and recommends the reconciliation method.

| Source document | What it models | Year 1 figure | Basis |
|---|---|---|---|
| AI Lab Commercialization Strategy (doc 2) | "AI Services Unit" — consultancy, appliances, conversational AI, governance, bootcamps | USD 530,000 | 5-line revenue table, USD-denominated |
| SmartLabs Master Commercialization Blueprint | Training, LaaS, Implementation, Managed Services + 5 platform-application lines (incl. "AI Lab/JupyterHub: Ksh 15M") | Ksh 154,950,000 (≈USD 1.19M) | KES-denominated, includes AI Lab as one of 9 lines |
| Agentic AI Commercialization Review | EAC enterprise agentic TAM | KES 4.2B (TAM, not a revenue projection) | Market-sizing figure, not comparable to the other two |
| EduBridge Blueprint | Per-student SaaS tiers (USIU-anchored) | Not yet modeled as an aggregate — per-student pricing only | Distinct product, genuinely additive once it exists |
| AfriqAI Blueprint | Developer API, SME Coworker, Sovereign Appliance, Desktop/Pro | Not modeled as Year-1 aggregate — described as "24-month roadmap" | Overlaps with AI Lab doc 2's line items (RAG, appliance, governance) under different product names |

**[Architect's recommendation]** The SmartLabs Master Blueprint's own "AI Lab/JupyterHub" revenue line (Ksh 15M ≈ USD 115k) is the only figure that's explicitly scoped as *just* the AI Lab, inside a document that also accounts for the other 9 revenue streams without double-counting. The AI Lab Commercialization Strategy's USD 530k figure, once you inspect its line items (Sovereign Banking Appliances, eTIMS Co-Pilot, Conversational AI, Governance Advisory, Bootcamps), is describing **the same AI Lab capability sold through more product SKUs** — it is not incremental revenue on top of the SmartLabs figure; it's a more granular breakdown of a overlapping opportunity. Before board presentation:

1. Pick **one** canonical revenue model (recommend the SmartLabs Master Blueprint's structure, since it's the only one that already nets multiple product lines into one P&L).
2. Fold the AI Lab Commercialization Strategy's five service-line breakdown **into** that single "AI Lab/JupyterHub" line as sub-SKUs, not as an additional USD 530k.
3. Treat AfriqAI and the Agentic Orchestration layer as **future upside on the same AI Lab line**, not a fourth business — they are technical evolutions of the same gateway (Section 3), not new revenue streams.
4. Treat EduBridge as genuinely additive (it's a distinct product, per-student, university-channel) — this is the one new P&L line in the set.

---

## 13. Consolidated Implementation Roadmap

**[Architect's recommendation]** Sequences everything above against one clock — AI Lab P0 gates almost everything else.

| Phase | Window | Deliverables |
|---|---|---|
| **0 — AI Lab P0 (gating)** | Months 1–3 | Workstreams B1–B5: GPU tier, metering/billing, Nairobi region, multi-tenancy/RBAC/audit, governance pack (Section 5.7) |
| **1 — SmartLabs Foundation (parallel)** | Months 1–3 | KubeVirt enabled, Containerlab Tier-1 labs, HIGH-priority vendor pods (Cisco/Juniper/Fortinet/Palo Alto/VMware/AWS/GCP/IBM/Red Hat), Ansible provisioning pilot |
| **2 — EduBridge P0 (parallel, USIU-anchored)** | Months 1–3 | Moodle multi-tenant, Keycloak SSO, LTI links to existing SmartLabs/Percipio — honest scope given AI Lab P0 not yet complete |
| **3 — Agentic Dog-Fooding** | Months 2–4 | Internal-only: Admissions Agent, Finance Coworker (Mfumo++), Sage Grader, Ops Sentinel — validate 80% autonomy before external sale |
| **4 — SmartLabs Shared Platforms** | Months 4–7 | Persistent EVE-NG/CML, GitOps topology promotion, MEDIUM-priority vendor pods, Lab-as-a-Service portal v1 |
| **5 — EduBridge P1 (depends on AI Lab P0 complete)** | Months 4–7 | i3 Author + AI Tutor (now legitimately RAG-grounded and metered); Lab-as-a-Service API + LTI AGS |
| **6 — AfriqAI Phase 1 (depends on B1 GPU tier)** | Months 4–6, starting after B1 acceptance | Nairobi GPU nodes, vLLM migration, Afriq-BPE tokenizer v1, EvalOS++ |
| **7 — External Agentic Commercialization** | Months 5–8, after dog-fooding metric hit | Beta pilot: 25 SMEs on Afriq Coworker / Nuru++ / Mfumo++ |
| **8 — EduBridge P2 (OTT + Talent Platform)** | Months 8–12 | BigBlueButton + PeerTube, Learning Locker LRS, Open Badges 3.0 |
| **9 — AfriqAI Phase 2–3** | Months 7–24 | Afriq Code CLI, Dynamic Sheng engine, Afriq Desktop, vernacular fine-tuning, Afriq Box commercialization |
| **10 — Regional Scale** | Year 2 | SmartLabs Lab-as-a-Service GA; EduBridge second/third university (Regional Alliance); AfriqAI continental expansion (Tanzanian/Congolese Swahili, Luganda) |

**Critical path:** AI Lab P0 (B1–B5) → everything else. No commercial claim about GPU performance, data residency, multi-tenant isolation, or audit-readiness should be repeated to a new prospect until its owning workstream passes acceptance criteria.

---

## 14. Best Innovations — Prioritized Across All Sources

| Innovation | Source | Why it matters | Priority |
|---|---|---|---|
| Single LiteLLM control plane for every product (SmartLabs, EduBridge, AfriqAI, internal agents) | P0 Spec + all downstream docs | One place to meter, guardrail, and audit — the entire platform's defensibility rests on this not being bypassed | P0 |
| Keyed per-project metering (not shared master key) | P0 Spec B2 | Makes every commercial model in Section 12 actually billable | P0 |
| Nairobi-region residency enforced by *not configuring* replication (not by policy) | P0 Spec B3 | Turns the sovereignty pitch from a claim into an architectural fact | P0 |
| Bantu-aware BPE tokenizer (2.8× compression) | AfriqAI | Directly attacks the cost/latency structural disadvantage vs. global frontier models | P0 (once B1 ships) |
| Dynamic Sheng ingestion & DPO fine-tuning loop | AfriqAI | No competitor (global or African NLP lab) is solving for 3–6-month slang drift | P1 |
| i3 Author Copilot (RAG → quiz + scenario + lab-spec in one pass) | EduBridge | The one genuinely new, proprietary piece in an otherwise open-source EdTech stack | P1 |
| Lab Orchestrator ("I need a 6-node BGP + 2 firewall lab" → auto-provisioned) | SmartLabs | Turns SmartLabs from a catalogue into a self-service product | P1 |
| Unified Agentic Operating Bus (Mfumo++/Nuru++/Sage Code sharing one MCP gateway) | Agentic AI Review | The actual moat vs. Yellow.ai/Wati.io-style static chatbot competitors | P1 |
| Reused risk-tier agent governance model (shared with i3 PMC / FORD-Asili engagements) | This review | Avoids specifying human-approval gating three different ways across the company's AI products | P1 |
| Afriq Box sovereign appliance | AfriqAI + Agentic AI Review | Highest-margin, highest-trust product for Tier-1 banks/government — but entirely dependent on B3 being real first | P2 |
| Talent-platform API (badge/competency profile → employer network) | EduBridge / USIU proposal | Turns "we have an employer network" into an actual contract, not a slide | P2 |
| Regional Alliance / Pan-African portability | EduBridge + AfriqAI + FORD-Asili guide (cross-engagement pattern) | Same country-adapter pattern this reviewer has now seen specified in three separate i3 engagements — worth building once as shared infrastructure | P2 |

---

## 15. Risk Register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **Data-residency claim already made to a live customer (USIU) ahead of B3 shipping** | Critical | Correct current collateral or accelerate B3; never repeat the "Kenya Region" claim in new proposals until residency audit (B3-1) passes |
| 2 | **GPU capability already marketed (USIU, SmartLabs matrix) as present-tense; actually CPU-only** | High | Correct collateral or accelerate B1; scope any live pilot's AI/ML labs honestly as CPU-tier until B1-1 acceptance passes |
| 3 | Five unreconciled revenue models presented to leadership/board as if independently additive | High | Adopt Section 12's reconciliation before any consolidated P&L goes to the board |
| 4 | Master API key (`sk-i3-internal`) still in client-facing use; leak = unmetered, unattributed, unlimited-budget access | Critical | B2/B4 retirement of the master key is not optional — treat as security incident risk, not just a metering gap |
| 5 | No audit trail on current production AI usage | High | B4-MVP audit logging; until then, any client conversation implying "we can show you who accessed what" is inaccurate |
| 6 | AfriqAI and Agentic layer both depend on GPU hardware not yet procured, with a NVIDIA-vs-ROCm decision still open | Medium | Do not let AfriqAI Phase 1 or Agentic external commercialization start before B1 acceptance criteria pass |
| 7 | 45-vendor lab matrix risks scope explosion (parallel to the scope-discipline risk flagged in your PMC/FORD-Asili engagements) | Medium | Sequence strictly by HIGH priority tier; do not build all 45 concurrently |
| 8 | Vendor image licensing — grey-market IOS/PAN-OS/FortiOS images | Medium | Only legitimate channels (partner portals, NFR programs, DevNet); no exceptions |
| 9 | Agent autonomy (Sage Code auto-opens PRs, Mfumo++ auto-generates credit notes) specified without an explicit risk-tier/approval gate in the source documents | High | Apply the shared risk-tier model (Section 10) before any of these ship with write access to production financial or code systems |
| 10 | Sage's ability to use per-workspace (not master) LiteLLM keys is an open question in the P0 spec itself | Medium | Resolve by Week 2 of the P0 program (per the spec's own risk table) — blocks accurate B2 metering for Sage traffic specifically |
| 11 | 7-year WORM audit retention promise needs ODPC legal review | Medium | Flagged as an open question in the P0 spec itself (Week 4) — do not commit this retention period to enterprise contracts before legal sign-off |
| 12 | Two near-duplicate SmartLabs blueprint documents in circulation | Low | Retire the shorter "Commercialization Blueprint" in favor of the "Master Commercialization Blueprint" to avoid internal version drift |

---

## 16. Appendix

### 16.1 Model Roster (consistent across all sources)

`granite-nano` (IBM Granite 3.1, 2B) · `qwen-fast` (Qwen 2.5, 7B) · `qwen-heavy` (Qwen 2.5, 14B) · `coder` (Qwen 2.5-Coder, 7B) · `vision` (LLaVA, 13B) · `embed` (Nomic Embeddings) — all currently served as Q4_K_M CPU quants via Ollama behind the LiteLLM proxy at `http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000`.

### 16.2 Glossary

| Term | Definition |
|---|---|
| ROKS | Red Hat OpenShift Kubernetes Service on IBM Cloud |
| LiteLLM | Open-source LLM API gateway/proxy — i3's single model control plane |
| EvalOS | i3's Firecracker-microVM-based code execution/assessment sandbox |
| MCP | Model Context Protocol — tool-exposure standard used for agent-to-system integration |
| KEDA | Kubernetes Event-Driven Autoscaling |
| LTI / AGS | Learning Tools Interoperability / Assignment & Grade Services — the standard connecting Moodle to external tools like SmartLabs |
| LRS | Learning Record Store — xAPI event store (Learning Locker) |
| WORM | Write-Once-Read-Many — tamper-evident audit storage |
| B1–B5 | The five P0 AI Lab workstreams: GPU tier, metering/billing, Nairobi region, multi-tenancy/RBAC/audit, model governance |

### 16.3 Full 45-Vendor Lab Matrix (reference — priority/cost columns)

HIGH priority: Cisco, Juniper, Fortinet, Check Point, Palo Alto, VMware, AWS, Google Cloud, IBM, Red Hat, Microsoft. MEDIUM: Aruba, Arista, Sophos, CrowdStrike, Zscaler, Nutanix, Oracle, NetApp, Dell, HPE, Cisco Collaboration, Splunk, NVIDIA, SAP. LOW: Kaspersky, Veeam, Veritas, Avaya, SolarWinds, Huawei, Lenovo, Pure Storage, Rubrik, Cohesity, Commvault, Salesforce, ServiceNow, Atlassian, Teradata, MongoDB, Mitel, Poly, Zoom. Full setup-cost/OpEx table (Ksh 50,000–1,000,000 setup range per vendor) retained in the source SmartLabs Master Commercialization Blueprint.

### 16.4 Contacts

Philip Mukiti — CEO & Solutions Architect, i3 Technologies Ltd · philip@i3technologies.co.ke · training@i3technologies.co.ke · +254 714 912 212 · Waumini House, Westlands, Nairobi.

---

*End of Document — i3 AI Lab, SmartLabs & Agentic Platform Master Technical Implementation Guide v1.0*
*i3 Technologies Ltd | Instrumented, Interconnected & Intelligent Technologies Limited*
*Internal — Strategy & Architecture*
