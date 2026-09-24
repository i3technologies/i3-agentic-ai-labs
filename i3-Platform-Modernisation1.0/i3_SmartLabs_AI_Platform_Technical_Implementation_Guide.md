# i3 SmartLabs & AI Platform — Unified Technical Implementation Guide

**Version:** 1.0  **Date:** 19 September 2026  **Status:** Draft for engineering and executive review
**Prepared for:** Philip Mukiti, CEO & Solutions Architect, i3 Technologies Limited
**Prepared by:** Senior Solutions Architect review
**Classification:** Internal — Strategy & Design

---

## 0. How to Use This Guide

This guide consolidates and critically reviews ten source documents, resolves their conflicts, and turns them into one buildable plan covering **i3 Smart Labs**, the **i3 AI Lab / AI Platform**, the **multi-vendor and Cisco network-lab track**, and **i3 EduBridge**.

| Ref | Source document | Used for |
|---|---|---|
| S1 | Cisco Lab on IBM Cloud + OpenShift — Consulting Review | Network-lab modernization, GitOps pipeline, open-source catalogue |
| S2 | AI Lab Commercialization Strategy (East Africa, 1-page) | Product/vertical framing |
| S3 | AI Lab & Platform Expansion Strategy (Enterprise AI Services) | Sovereign AI offerings, pricing, 90-day plan |
| S4 | Smart Labs Multi-Vendor Lab Strategy | Three-tier lab model, vendor catalogue |
| S5 | SmartLabs Commercialization Blueprint | Revenue streams, credit balancing |
| S6 | SmartLabs Engineering Runbook | Transit Gateway, KubeVirt, token-accounting specs |
| S7 | SmartLabs Master Commercialization Blueprint | 45-vendor matrix, 3-year model |
| S8 | AI Lab P0 Technical Build Spec | GPU tier, metering, Nairobi region, RBAC, governance (B1–B5) |
| S9 | EduBridge Product Review & Technical Blueprint | LMS/authoring/OTT/LRS layers |
| S10 | USIU-Africa Academic Collaboration Proposal | Anchor customer, curriculum mapping, pricing |

**Reading map**

| If you are… | Read |
|---|---|
| CEO / commercial lead | §1, §2, §3, §12, §13, §16 |
| Platform / DevOps lead | §4, §5, §9, §14 |
| Lab & network engineers | §6, §11 |
| AI / ML engineers | §7, §8 |
| EduBridge / product team | §10, §12 |

Conventions: **[KEEP]** = source decision retained as-is, **[CHANGE]** = source decision modified, **[NEW]** = addition not in any source. Prices for cloud resources are indicative planning figures and must be validated against the current IBM Cloud calculator or a written quote before they are used in any customer document.

---

## 1. Executive Summary

### 1.1 Verdict

The strategic direction across the ten documents is sound and internally coherent at the architecture level:

- **One gateway** for all AI traffic (LiteLLM) — keep.
- **OpenShift as the single substrate** for containers, VMs (OpenShift Virtualization) and GitOps — keep.
- **Wrap, don't rebuild**: Moodle as LMS core with i3 IP on top (authoring copilot, lab grading, AI tutor) — keep.
- **Sovereignty as the commercial wedge** (Kenya DPA 2019, CBK guidance, Swahili-native AI) — keep, but it must be *enforced by policy and evidenced*, not asserted.

However, the documents make **five commitments that cannot be honoured as written** and several that carry legal or reputational exposure. Fixing them is cheaper now than after a bank, ministry or university has signed.

### 1.2 The five must-fix items before further customer commitments

| # | Issue | Why it matters | Resolution (section) |
|---|---|---|---|
| 1 | **Vendor NFR licences are planned as the licence basis for paid training/LaaS** (S5/S7 §5: "Ksh 0 licensing… equip 45 vendor lab pods") | NFR/"not for resale" entitlements are for internal demo, testing and enablement — not for delivering paid customer environments. Exposure: contract breach, vendor-partner status risk | Licence-provenance model, per-vendor training-partner routes, wave plan (§6.7–6.8) |
| 2 | **2,500 concurrent students on USD 3,000/month of credits** | Order-of-magnitude gap. Credits fund roughly 70–150 peak concurrent sessions, not 2,500 (§3.2) | Concurrency-based SKUs, admission control (Kueue), capacity model (§6.2, §13.3) |
| 3 | **Residency claims are inconsistent**: S9/S10 say "IBM Cloud VPC Kenya Region"; S7/S8 say Frankfurt (eu-de) with Nairobi still to be built | A written residency claim in a university proposal (and any bank MSA) that is not true is a Kenya DPA / misrepresentation risk. I could not find evidence of a public IBM Cloud VPC region in Kenya — confirm with IBM in writing | Decision D1; Nairobi sovereign region (§9.4) |
| 4 | **Cross-cluster service addressing does not work**: three accounts/clusters all reference `litellm-proxy.i3-model-gateway.svc.cluster.local` | `svc.cluster.local` resolves only inside one cluster; pod networks are not routed through Transit Gateway | Private NLB + internal DNS, or Service Interconnect (§5.1) |
| 5 | **Security debt in the reference artefacts**: literal master key `sk-i3-internal` in env vars/docs, `at now + 4 hours` teardown, "strict network policy" that is only a ResourceQuota, Kali labs with open egress, token-accounting script using the master key | Each is a finding in any bank or university security review | Hardening baseline (§5.3–5.4, §6.5, §9.2) |

### 1.3 The unifying idea

Today the sources describe **five products on one cluster** (Smart Labs, AI Lab, EvalOS, EduBridge, network labs). The implementation guide reframes them as **one control plane with five front doors**:

```
                 ┌────────────────────────── FRONT DOORS ──────────────────────────┐
                 │ Moodle (EduBridge) · EvalOS exams · Bootcamp · POC/LaaS portal  │
                 │ Sage · JupyterHub · Talent Cloud · Partner APIs                 │
                 └───────────────────────────────┬─────────────────────────────────┘
                                                 │  OIDC (Keycloak) · LTI 1.3 · REST
        ┌────────────────────────────────────────▼────────────────────────────────────────┐
        │                        i3 CONTROL PLANE (one of each)                           │
        │  Identity · Entitlements · Lab Orchestrator (CRDs) · AI Gateway · Usage Meter   │
        │  Policy (Kyverno) · Event Bus (Kafka) · Learning Record Store · Audit (WORM)     │
        └───────────┬───────────────────────────┬───────────────────────────┬─────────────┘
                    │                           │                           │
           LAB RUNTIME TIERS              AI RUNTIME TIERS            DATA & MEDIA
        C: containers/Clabernetes      CPU: Ollama (small)         Postgres · Qdrant · COS
        V: KubeVirt VMs                GPU: vLLM (heavy/vision)    BigBlueButton · PeerTube
        B: bare metal / CML            Voice: STT/TTS               Learning Locker · Langfuse
        S: SaaS-tenant vending
```

**Every consumption event — an LLM token, a lab-minute, a GPU-minute, a video-minute, a stored GB — is emitted as one `UsageEvent`** into one bus, feeding billing, xAPI learning records, FinOps and anomaly detection. This is the design decision that makes bundling (EduBridge "Practical+") and per-use billing (enterprise LaaS) the same code path.

### 1.4 What "best innovations" means here

§12 lists 28 innovations, ranked. The ten with the highest value-to-effort ratio, in build order:

1. **Lab Orchestrator with CRDs** (`LabTemplate`, `LabSession`, `LabPool`) replacing ad-hoc Ansible + `at` jobs.
2. **Warm pools** — cut lab launch from ~2 minutes to under 30 seconds for common templates.
3. **State-based auto-grading engine** that grades device/cluster *state* (not screen output) and feeds LTI grade passback and xAPI.
4. **Kueue admission control** — fair-share, tenant quotas and queueing for labs and GPUs; makes concurrency a sellable SKU.
5. **vLLM GPU tier with metrics-driven autoscaling** (KEDA on `num_requests_waiting`), Ollama retained for the CPU tier.
6. **Unified `UsageEvent` meter → ERPNext (AfroERP) invoices with KRA eTIMS** — reuses an asset i3 already runs.
7. **Policy-enforced residency with automated attestation reports** for ODPC/bank due diligence.
8. **Clabernetes + NetBox + Batfish** GitOps network-lab pipeline with auto-destroy.
9. **AI-authored lab and course drafts validated by CI** (generate → dry-run deploy → auto-grade → human approval).
10. **Sovereign Appliance bundle** (signed, air-gappable umbrella chart) for banks/SACCOs/MDAs.

---

## 2. Source Review and Conflict Register

### 2.1 What each source gets right

| Source | Strongest contribution | Keep |
|---|---|---|
| S1 | GitOps network pipeline (Git → Batfish → deploy → telemetry → evidence pack → auto-destroy); legitimate image-acquisition table; "topology-as-code or it doesn't exist" rule | Yes, with Clabernetes substitution (§6.4) |
| S2/S3 | Sovereign, on-cluster AI as the answer to KDPA/CBK cross-border limits; FX-exposure argument; Swahili/localization gap; concrete vertical offers | Yes |
| S4 | Three-tier fidelity model (container → VM → persistent shared emulator); "Lab Orchestrator" thin service; treat lab namespaces as untrusted | Yes — becomes the core of §6 |
| S5/S7 | Single-pane gateway; per-tenant token accounting; 90-day plan; credit-balancing idea | Partly — credit model needs the corrections in §3 and §13 |
| S6 | Concrete Transit Gateway, KubeVirt and reconcile-script starting points | Yes, all three need correction (§5.1, §6.3, §8.3) |
| S8 | Acceptance-criteria discipline; GitOps overlays; residency-by-non-replication; WORM audit; eval harness + release gate | Yes — extended, not replaced |
| S9 | Six-layer EduBridge architecture; Moodle + LTI 1.3 AGS; H5P/Adapt authoring; BBB/PeerTube/OME; Learning Locker; Open Badges 3.0 | Yes |
| S10 | Anchor pilot; curriculum mapping; pricing benchmark | Yes, with claim corrections (F-13) |

### 2.2 Conflict register and resolutions

| # | Topic | Sources in conflict | Resolution |
|---|---|---|---|
| C1 | **Hosting region** | S7/S8: ROKS 4.17 in Frankfurt (eu-de). S9/S10: "IBM Cloud VPC (Kenya Region)" | Treat Frankfurt as fact until IBM confirms otherwise in writing. Correct customer-facing collateral. Decision D1 (§16) |
| C2 | **Where the 750 VMs live** | S7: on-premises Power Systems (750 VMs). S10: IBM Cloud VPC / Power Virtual Server, Kenya Region | Produce a one-page infrastructure fact sheet (location, hypervisor, owner, capacity) and make it the single source of truth |
| C3 | **Cluster size** | S7: 3-node `bx2-4x16` (Account 1). S10: 5 workers + 2 masters. Current production baseline: 12 workers | Re-baseline with `oc get nodes -o wide` and capture in Git |
| C4 | **GPU strategy** | S7: A100 burst via GPU4YOU voucher. S8: L4/A10 24 GB inference nodes | Both: **L4/L40S-class for always-on inference**, **A100 burst only for fine-tuning jobs** (§7.1) |
| C5 | **Model roster** | S3 lists Granite 2B, Qwen 7B/14B, Coder, LLaVA; S7 adds aliases; S8 adds `embed` | Canonical alias table in §7.2 |
| C6 | **Vector store** | S3: ChromaDB "production clustering" | Move to Qdrant (or pgvector on Crunchy PG) — Chroma has no mature HA story (§7.4) |
| C7 | **Revenue totals** | S3: USD 530k Y1 (AI services). S7: KES 154.95M Y1. S7 §7 application revenue (KES 84.7M Y1: EvalOS, AfroERP, Engage, PMaaS, AI Lab) does not appear in the §8 P&L. Training revenue KES 8.75M (table) vs 6.75M (P&L) | Rebuild one model bottom-up from unit economics (§13.5). Do not circulate S7 numbers to the board until reconciled |
| C8 | **Infrastructure cost** | S5/S7: "zero cash infrastructure OpEx" via USD 36k/yr credits. Same P&L books KES 15M (~USD 116k) infrastructure in Year 1 | Credits cover the ramp only; model post-credit run-rate now |
| C9 | **Vendor count** | S7: 45 vendors. S4: 11 high-priority vendors | Wave plan (§6.7): 10–12 vendors in waves 1–2, the rest demand-gated |
| C10 | **Billing/accounting** | S8: "keep it a clean export, not an accounting integration" | [CHANGE] i3 already runs AfroERP (ERPNext v15 with eTIMS) — post invoices there (§8.4) |

---

## 3. Critical Review Findings

Severity: **Critical** = blocks customer commitments; **High** = must fix in first 90 days; **Medium** = fix in first 180 days; **Low** = correct when touched.

| ID | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F-01 | Critical | NFR licences used as basis for paid delivery | S5/S7 §5 | §6.8 licence ledger; training-partner routes |
| F-02 | Critical | 2,500-concurrency claim unsupported by budget | S5/S7 headline metrics vs §4 | §3.2, §13.3 |
| F-03 | Critical | Residency claim inconsistent across documents | C1 | D1, §9.4 |
| F-04 | High | Cross-cluster `svc.cluster.local` addressing; "VPC peering" used interchangeably with Transit Gateway; pod networks not routed; CIDR plan absent | S5, S6, S7 | §5.1 |
| F-05 | High | KubeVirt/vrnetlab require hardware virtualization; S1 assumes "instances with VT-x exposure". On IBM Cloud, OpenShift Virtualization is supported on **bare-metal** workers — VPC virtual servers should not be assumed to offer nested virtualization. Validate with IBM before sizing | S1 §3.1, S6 §2 | §6.3: dedicated bare-metal pool, or defer the V tier to the Nairobi colo |
| F-06 | High | Security debt: master key literal; `at` teardown; quota-only "network policy"; open egress on Kali labs; reconcile script | S6, S7 §6, S8 §1 | §5.3, §6.5, §8.3 |
| F-07 | High | PMaaS (political campaign data, voter mapping, mass disbursements) shares the Keycloak realm, account and cluster with banks/universities. Political opinion is **sensitive personal data** under the Kenya DPA and carries reputational and regulatory blast radius | S7 §1–2 | Segregate before onboarding any regulated tenant (§4.5, §9.5) |
| F-08 | Medium | Cloud-simulator overclaim: there is no full Azure Resource Manager emulator (Azurite covers storage only); GCP emulators cover a handful of services; LocalStack Pro is licensed. Salesforce, ServiceNow, Atlassian, Zoom, CrowdStrike, Zscaler, MongoDB Atlas are **hosted SaaS tenants**, not emulatable, and their terms generally restrict resale of access | S5/S7 §3, §5 | Feasibility classes (§6.7) |
| F-09 | Medium | CML Personal ($200/yr) is a personal-use licence; S1's own compliance note warns against gray-market images, then proposes CML Personal as the "image factory" | S1 §2.3, §5.3 | CML Enterprise / Cisco learning-partner route for multi-user delivery |
| F-10 | Medium | Ollama on GPU is not designed for high-concurrency multi-tenant serving (limited batching); Chroma HA; `llava:13b` is dated | S8 §2 | vLLM tier (§7.1); Qwen-VL-class vision model |
| F-11 | Medium | Financial model inconsistencies | C7, C8 | §13.5 |
| F-12 | Medium | Snippet defects (below) | — | Corrected versions inline |
| F-13 | Low | "Blockchain-verified" IBM badges (S10): IBM digital badges are issued through a badging platform (typically Credly) and Open Badges 3.0 uses verifiable credentials — no blockchain is required or implied | S10 §5 | Correct collateral wording |
| F-14 | Low | S3 lists "LangGraph / CrewAI on OpenShift" and "watsonx.governance filters in the LiteLLM proxy" as if they were bolt-on; in practice guardrails hook via LiteLLM callbacks/guardrail config, watsonx.governance is a separate service | S3 §2 | §7.5 |
| F-15 | Medium | S3 proposes XTTS-v2 for commercial Swahili IVR/voice. XTTS-v2 model weights are published under a **non-commercial** licence (Coqui Public Model License); Kokoro is permissively licensed but is not a Swahili model. Verify before any paid voice product | S3 §2 | §7.8: licence check, licensed voice-data programme, or a commercially licensed TTS |

**Snippet defects (F-12) — quick list**

| Source | Defect | Correction |
|---|---|---|
| S1 App. | Containerlab `kind: cisco_cat8000v` and inline `links: [a:eth1-b:eth1]` are not valid; `frrouting/frr:latest` contradicts the "no `latest` in prod" rule | Use `cisco_c8000v` kind (verify against pinned Containerlab release), `links: - endpoints: ["a:eth1","b:eth1"]`, pinned tags (§6.4) |
| S1 App. | `gnmic … -o prometheus` — outputs are configured in the gNMIc config file, not a bare `-o` value | gNMIc config with a `prometheus` output (§6.4) |
| S1 §5.2 | Table row "Tinker / TeraFlow? (skip)", "SuzyBorg" | Remove; Suzieq |
| S6 §1 | Cross-account Transit Gateway connections require acceptance in the owning account; no CIDR/prefix-filter plan | §5.1 |
| S6 §2 | `spec.running: true` is deprecated in favour of `runStrategy`; VM pulled from an internal registry without licence handling; memory request 4Gi vs namespace quota of 4Gi requests leaves no room for the Linux terminal | §6.3 |
| S6 §3 | `/spend/calculate` is a cost-estimation endpoint, not a spend report; `PGPASSWORD` holds a full URL; non-idempotent daily append; uses master key | §8.3 |
| S5/S7 §6 | Playbook: `NetworkPolicy` promised but only a `ResourceQuota` is created; teardown via `at` (lost on pod restart, not namespace-safe); `student_id` interpolation inconsistent (`{{ }}` vs `{ }`) | Replaced by `LabSession` CRD with TTL finalizer (§6.2) |
| S8 §2 | `routing_strategy: simple-shuffle` with a single deployment per alias makes fallback rules unenforceable | Explicit `fallbacks` and `order` (§7.2) |

### 3.1 What is strong and should not be touched

- The **P0 acceptance-criteria format** (B1-1…B5-4). Every new workstream in this guide adopts the same format (§14).
- **Residency by non-replication** (S8 §4.3): the simplest possible enforcement — do not configure replication for resident data classes. This guide adds *verification*, not a different mechanism.
- **Master-key retirement with a 30-day overlap** (S8 §3.3) — correct migration pattern.
- **Wrapper strategy for EduBridge** (S9 §0) — correct; do not build an LMS.

### 3.2 Capacity reality check (F-02)

**Assumptions** (adjust after measuring real sessions): concurrent-session mix at peak — 30% notebooks, 50% lightweight container labs, 15% VM labs, 5% network-fabric labs.

| Session profile | Request (vCPU / GiB) | Share of 2,500 | Sessions | RAM total (GiB) | vCPU total |
|---|---|---|---|---|---|
| Notebook (JupyterHub) | 0.25 / 1 | 30% | 750 | 750 | 188 |
| Container lab (Linux, Kali, DB) | 0.25 / 0.5 | 50% | 1,250 | 625 | 313 |
| VM lab (firewall/router appliance) | 2 / 4 | 15% | 375 | 1,500 | 750 |
| Network fabric (6–10 nodes) | 2 / 6 | 5% | 125 | 750 | 250 |
| **Total at 2,500 concurrent** | | | **2,500** | **≈3,625 GiB** | **≈1,500 requested** |

- Nodes needed at 64 GiB (≈56 GiB allocatable): **≈65 nodes**. Even scheduled to business hours, that is a five-figure USD monthly bill (indicative, validate with IBM).
- Account 2 as designed (S5/S7): 8 nodes × `bx2-4x16` at peak = ≈128 GiB, ≈100 GiB allocatable. At the blended 1.45 GiB per session above, that is **≈70 concurrent sessions**; with notebooks and container labs only (≈0.69 GiB average), ≈145. **That is 3–6% of the headline figure.**
- **What is true**: concurrency is not enrolment. Universities schedule labs; typical peak concurrency is 10–20% of enrolled students. At 400 concurrent the requirement is ≈580 GiB RAM (~11 × 64 GiB nodes) — achievable, but not on USD 1,000/month.
- **The good news** (unit economics): density makes cost-per-lab-hour small. At ≈USD 0.77/node-hour (indicative for a 16 vCPU/64 GiB class) and ≈39 sessions per node at the blended 1.45 GiB, a blended lab-hour costs ≈USD 0.02; a VM-lab hour (4 GiB, ≈14 per node) ≈USD 0.055. An 80-hour/year student costs low single-digit USD in compute **if utilisation is scheduled and warm pools are right-sized**. The commercial model therefore must sell **reserved concurrent seats + session-hours**, not "capacity for 2,500".

Consequence: replace "2,500 concurrent capacity" in all collateral with a **published concurrency tier table** (§13.3) backed by load-test evidence (§14, L-series).

---
## 4. Target Architecture

### 4.1 Design principles

| # | Principle | Practical meaning |
|---|---|---|
| P1 | **One of each** control-plane function | One IdP (Keycloak), one AI gateway (LiteLLM), one lab orchestrator, one meter, one event bus, one audit sink |
| P2 | **Everything as code** | Namespaces, quotas, lab templates, model routes, dashboards, Moodle config in Git; Argo CD reconciles |
| P3 | **Tiered fidelity** | Use the cheapest runtime that is faithful enough: container → VM → bare metal (S4) |
| P4 | **Sovereignty is enforced, then evidenced** | Policy engine blocks non-compliant placement; a report proves it |
| P5 | **Ephemeral by default** | Every session has a TTL enforced by a controller, not a cron job |
| P6 | **Licence provenance is data** | Every image carries `permitted_use`; the platform refuses to run an image outside it |
| P7 | **Open exports** | SCORM/xAPI/Common Cartridge/Open Badges; Git-based lab specs — trust signal for procurement |
| P8 | **Blast-radius isolation** | Regulated tenants and PMaaS never share realm, DB or node pool with open/student tenants |
| P9 | **Human in the loop for AI-authored artefacts** | AI drafts; CI validates; a named person approves |
| P10 | **Measure before you sell** | Every SKU has an SLO and a load-test result behind it |

### 4.2 Logical architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ EDGE   Cloudflare (WAF/DDoS) → labs.i3technologies.co.ke (Envoy / IBM ALB)            │
│        OIDC/SAML via Keycloak · LTI 1.3 · OpenAPI gateway (rate-limit, tenant routing)  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ IDENTITY & POLICY      Keycloak realms · OpenBao · External Secrets · Kyverno · OPA     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ CONTROL PLANE                                                                          │
│  Tenant Service ─ Entitlement Service ─ Lab Orchestrator (CRDs) ─ Kueue                │
│  AI Gateway (LiteLLM) ─ Usage Meter ─ Event Bus (Kafka/Strimzi) ─ Audit (WORM COS)     │
├──────────────────────────┬──────────────────────────┬──────────────────────────────────┤
│ LAB RUNTIME              │ AI RUNTIME               │ LEARNING & MEDIA                 │
│ C  Containers/Clabernetes│ CPU  Ollama (small)      │ Moodle · H5P · Adapt · i3 Author │
│ V  KubeVirt (bare metal) │ GPU  vLLM (heavy/vision) │ Learning Locker (LRS) · OB 3.0   │
│ B  CML / EVE-NG VMs      │ Voice Faster-Whisper/TTS │ BigBlueButton · PeerTube · OME   │
│ S  SaaS/cloud sandbox    │ RAG  Qdrant + Tika       │ Talent API (EvalOS/Talent Cloud) │
│    vending               │ Agents LangGraph + MCP   │                                  │
├──────────────────────────┴──────────────────────────┴──────────────────────────────────┤
│ DATA  Crunchy PG (HA) · Qdrant · ODF/Ceph · IBM COS (Object Lock) · Redis · Kafka      │
│ OBS   Prometheus · Loki · Tempo/OTel · Grafana · Langfuse · Alertmanager               │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Account, cluster and region topology

Keep the three IBM Cloud accounts (they exist because each carries credits) but give each a crisp role, and add the **sovereign region** from the P0 spec as a first-class fourth site.

| Site | Role | Contents | Notes |
|---|---|---|---|
| **A1 — prod-core** (ROKS, eu-de) | Revenue SaaS + hub GitOps | `i3-auth`, `i3-evalos`, `i3-afroerp`, `i3-engage`, `i3-edbridge` (Moodle, non-resident tenants only), `i3-talent-cloud`, `i3-billing`, Argo CD hub | Non-regulated tenants |
| **A2 — labs** (ROKS, eu-de) | Lab runtime | Lab Orchestrator, Kueue, JupyterHub workers, container lab pools, LocalStack/Kali sandboxes; **V tier only if bare-metal workers are affordable** (F-05) | Scale-to-baseline overnight (KEDA cron) |
| **A3 — ai** (ROKS or VPC + GPU, eu-de) | Model gateway | LiteLLM (HA), vLLM, Ollama-CPU, Langfuse, Qdrant (non-resident) | Exposed to A1/A2 only through a private NLB (§5.1) |
| **A-PM — isolated** | PMaaS | Own namespace set, node pool, DB, Keycloak realm; **preferably own account/cluster** | F-07 |
| **N1 — Nairobi sovereign region** (colo, OpenShift/OKD or ROKS-equivalent) | Regulated data plane | Student PII for resident tenants, RAG corpora, embeddings, prompts, audit logs, GPU inference for T1/T2 tenants | Decision D1/D2. Frankfurt keeps only encrypted non-resident config backups |

Argo CD (hub in A1) manages spokes A2, A3, N1 via ApplicationSets (§5.2). One Git repo, per-site overlays — exactly the S8 §4.3 pattern, extended to labs and EduBridge.

### 4.4 Namespace catalogue

| Namespace | Purpose | Site | Tenancy tier |
|---|---|---|---|
| `i3-auth` | Keycloak, OpenBao | A1 | Shared control |
| `i3-model-gateway` | LiteLLM, vLLM, Ollama, Langfuse | A3 / N1 | Shared control |
| `i3-ai-lab` | JupyterHub, Sage (shared, open users) | A2 | T0 |
| `sage-<tenant>` | Per-tenant Sage instance (§7.6) | A3 / N1 | T1+ |
| `i3-labs-system` | Lab Orchestrator, Kueue, grader, warm-pool controller | A2 | Shared control |
| `lab-<session>` | One per lab session (ephemeral) | A2 | Per session |
| `cust-<slug>` | Per-customer project space (notebooks, keys, RAG collection) | A2/A3/N1 | T1 |
| `i3-edbridge` → `edu-<institution>` | Moodle per institution | A1 / N1 | T1 |
| `i3-media` | BigBlueButton, PeerTube, OME, transcoders | N1 (later) | Shared |
| `i3-lrs` | Learning Locker, xAPI relay | N1 | Shared |
| `i3-evalos`, `i3-afroerp`, `i3-engage`, `i3-talent-cloud`, `i3-billing` | Product apps | A1 | Product |
| `i3-voice` | STT/TTS | A3 / N1 | Shared |
| `i3-observability` | Prometheus, Loki, Grafana, Tempo | each site | Shared |
| `i3-audit` | Audit shippers (write-only to WORM bucket) | each site | Shared |

*Baseline note:* the existing production namespace list should be re-exported from the live cluster and committed to Git; the table above is the target shape.

### 4.5 Three tenancy tiers

| Tier | For | Isolation | Data plane | Keycloak | Sage / RAG | Example |
|---|---|---|---|---|---|---|
| **T0 — Open** | Individuals, SMEs, bootcamp cohorts | Namespace + quota + NetworkPolicy + Kueue queue | Shared PG/Qdrant with row/collection scoping | Group in shared realm | Shared Sage, per-user key | i3 Academy bootcamp |
| **T1 — Hardened** | Universities, corporates, POC/LaaS clients | Dedicated node pool (taint), namespace set, default-deny + egress firewall | Dedicated Qdrant collection + PG schema, per-tenant object bucket | Dedicated realm (or group set for small tenants) | Dedicated Sage instance, tenant LiteLLM team & keys | USIU-Africa, a bank POC |
| **T2 — Sovereign** | Banks, SACCOs, MDAs | Dedicated cluster or appliance (Nairobi colo or customer DC), air-gap capable | Fully dedicated | Customer-federated | Appliance bundle (§11.5) | CBK-regulated bank |

**Rule:** PMaaS is *never* T0/T1 alongside other tenants — it is its own isolated site (A-PM) until a formal data-protection assessment says otherwise.

### 4.6 Identity model

- **Realms:** `i3` (staff, i3 Academy, EvalOS candidates); `tenant-<slug>` for T1+; institution IdPs (Entra ID, Google Workspace, Shibboleth/SAML) brokered into the tenant realm.
- **Token claims (all clients):** `tenant`, `roles[]` (`student`, `faculty`, `ta`, `institution-admin`, `developer`, `viewer`, `i3-admin`), `entitlements[]` (SKU codes), `residency` (`ke`|`any`).
- **Service-to-service:** OAuth2 client-credentials with narrowly scoped clients; Keycloak token exchange to carry user context into the lab and AI APIs.
- **LTI 1.3:** Moodle (platform) ↔ i3 Smart Labs / i3 AI Tutor (tools). Keys rotated via OpenBao; per-tenant `client_id`/`deployment_id`.
- **Kill switch:** removal from an SSO group revokes sessions, LiteLLM keys and lab sessions within 5 minutes (S8 B4-4), implemented as a Keycloak event listener publishing `user.disabled` to the bus.

### 4.7 The unified usage event

```json
{
  "event_id": "01J8Z7…",                    // ULID, idempotency key
  "ts": "2026-09-19T08:14:03Z",
  "tenant_id": "usiu",
  "project_id": "cs-y3-agentic-ai",
  "user_id_hash": "sha256:9a1c…",           // never raw PII on the bus
  "resource": "llm_tokens|lab_minutes|gpu_minutes|vod_minutes|voice_seconds|storage_gb_day",
  "sku": "LLM-QWEN-HEAVY-IN",
  "quantity": 18342,
  "unit": "token",
  "attrs": {"model": "qwen-heavy", "region": "nbo1", "session_id": "…", "course": "CSC-4xx"}
}
```

Producers: LiteLLM callback, Lab Orchestrator, JupyterHub culler, media servers, voice services. Consumers: **billing** (§8), **LRS/xAPI relay** (§10.7), **FinOps** (§8.6), **anomaly detector** (runaway loops, credential sharing). Transport: Kafka (Strimzi, 3 small brokers) with a Postgres outbox on each producer for at-least-once delivery; consumers dedupe on `event_id`.

---

## 5. Foundation: Landing Zone and Platform Hardening

### 5.1 Networking, Transit Gateway and cross-cluster access (fixes F-04)

**CIDR plan (reserve now; changing it later is painful)**

| Site | VPC CIDR | Cluster pod CIDR (unrouted) | Service CIDR (unrouted) |
|---|---|---|---|
| A1 prod-core | 10.10.0.0/16 | 172.20.0.0/16 | 172.21.0.0/16 |
| A2 labs | 10.20.0.0/16 | 172.22.0.0/16 | 172.23.0.0/16 |
| A3 ai | 10.30.0.0/16 | 172.24.0.0/16 | 172.25.0.0/16 |
| A-PM | 10.40.0.0/16 | 172.26.0.0/16 | 172.27.0.0/16 |
| N1 Nairobi | 10.50.0.0/16 | 172.28.0.0/16 | 172.29.0.0/16 |

Only VPC CIDRs are advertised over Transit Gateway. **Pod and service networks are not routed**, so a workload in A2 cannot reach `svc.cluster.local` names in A3. Use one of:

1. **Private load balancer + internal DNS (recommended, simplest):** publish LiteLLM in A3 through a private VPC load balancer; register `llm.internal.i3` in an IBM Cloud DNS Services private zone shared to all VPCs; clients use `https://llm.internal.i3` with mTLS or a bearer key.
2. **Red Hat Service Interconnect (Skupper):** L7 service mesh across clusters; use when more than ~5 cross-cluster services exist.

```yaml
# A3: expose LiteLLM privately (verify annotations for your ROKS/VPC version)
apiVersion: v1
kind: Service
metadata:
  name: litellm-private
  namespace: i3-model-gateway
  annotations:
    service.kubernetes.io/ibm-load-balancer-cloud-provider-ip-type: "private"
spec:
  type: LoadBalancer
  selector: {app: litellm}
  ports: [{name: https, port: 443, targetPort: 4000}]
```

```hcl
# terraform/modules/transit_gateway/main.tf  (corrected S6 §1)
resource "ibm_tg_gateway" "i3" {
  name           = "i3-smartlabs-tgw"
  location       = "eu-de"
  global         = false            # set true only when N1 is reached via a different IBM location
  resource_group = var.resource_group_id
}

resource "ibm_tg_connection" "a1" {
  gateway      = ibm_tg_gateway.i3.id
  network_type = "vpc"
  name         = "conn-a1-prod-core"
  network_id   = var.vpc_a1_crn
}

# Cross-account: created from the gateway-owning account, then ACCEPTED in the
# other account. Until accepted the connection is "pending" — CI must wait/verify.
resource "ibm_tg_connection" "a2" {
  gateway            = ibm_tg_gateway.i3.id
  network_type       = "vpc"
  name               = "conn-a2-labs"
  network_id         = var.vpc_a2_crn
  network_account_id = var.account_2_id
}
resource "ibm_tg_connection" "a3" {
  gateway            = ibm_tg_gateway.i3.id
  network_type       = "vpc"
  name               = "conn-a3-ai"
  network_id         = var.vpc_a3_crn
  network_account_id = var.account_3_id
}
# Add prefix filters so PMaaS (10.40.0.0/16) is NOT reachable from labs/AI VPCs.
```

**Segmentation rule:** A-PM is deliberately *not* attached to the same Transit Gateway route domain as A2/A3; it reaches AI only through the public, authenticated gateway like any external customer.

**Nairobi (N1) connectivity:** IPsec VPN or a carrier cross-connect to Frankfurt for config sync/DR only. **No customer prompts, documents, embeddings or audit logs cross this link** (residency-by-non-replication, S8 §4.3).

### 5.2 GitOps structure and Argo CD

```
i3-platform/                       # single monorepo
├── clusters/                      # per-site overlays
│   ├── a1-prod-core/  a2-labs/  a3-ai/  apm-isolated/  n1-nairobi/
├── platform/                      # shared components (Helm/Kustomize)
│   ├── keycloak/ openbao/ external-secrets/ kyverno/ kueue/
│   ├── observability/ kafka/ velero/ argocd/
├── control-plane/
│   ├── lab-orchestrator/  entitlement-service/  usage-meter/  tenant-service/
├── ai/
│   ├── litellm/ vllm/ ollama/ qdrant/ langfuse/ guardrails/ eval/
├── edu/
│   ├── moodle-chart/  i3-connector-plugin/  bbb/ peertube/ ome/ learning-locker/
├── labs/
│   ├── templates/<vendor>/<lab-id>/{lab.yaml,checks.yaml,README.md}
│   └── images/ (build recipes, NOT the images)
├── tenants/                       # one file per tenant — the unit of onboarding
│   └── usiu.yaml  acme-bank.yaml ...
└── docs/runbooks/
```

A tenant is onboarded by a pull request adding `tenants/<slug>.yaml`:

```yaml
slug: usiu
tier: T1
site: n1-nairobi
residency: ke
sku: practical-plus
concurrency: {lab: 120, gpu: 6}
budgets: {llm_kes: 250000, lab_hours: 12000}
idp: {type: entra-id, tenant_id: "…"}
modules: [moodle, smartlabs, ai-tutor, bbb]
```

```yaml
# ApplicationSet: one Application per tenant, placed on the site the tenant file names
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata: {name: tenants, namespace: argocd}
spec:
  generators:
  - git:
      repoURL: https://git.i3technologies.co.ke/i3-platform.git
      revision: main
      files: [{path: "tenants/*.yaml"}]
  template:
    metadata: {name: "tenant-{{slug}}"}
    spec:
      project: tenants
      source:
        repoURL: https://git.i3technologies.co.ke/i3-platform.git
        targetRevision: main
        path: platform/tenant-chart
        helm: {valueFiles: ["../../tenants/{{slug}}.yaml"]}
      destination: {name: "{{site}}", namespace: "cust-{{slug}}"}
      syncPolicy: {automated: {prune: true, selfHeal: true}, syncOptions: [CreateNamespace=true]}
```

The `tenant-chart` renders: namespace(s), ResourceQuota, LimitRange, default-deny NetworkPolicy, Kueue `LocalQueue`, Keycloak realm/group (via operator), LiteLLM team, Qdrant collection, object bucket, Grafana folder, and the `Tenant` CR consumed by the entitlement service.

### 5.3 Secrets and identity hygiene (fixes F-06)

1. **OpenBao** (Vault-compatible) with the 2-of-3 unseal governance from S7; **External Secrets Operator** projects secrets into namespaces. No secret in Git, env-var docs, or notebooks.
2. **Retire `sk-i3-internal`** (S8 §7): create a break-glass service key (offline, sealed envelope + OpenBao path), issue **per-workload virtual keys** to every service, and per-project keys to customers. Enable a 30-day overlap, then rotate the master key and delete the literal from every doc/notebook (a CI secret-scanner — gitleaks — enforces this).
3. **Short-lived credentials:** lab sessions receive credentials from OpenBao dynamic secrets (SSH CA certificates, DB users) with the session TTL as the lease.
4. **cert-manager** for internal PKI; mTLS between gateway and model backends.

### 5.4 Supply chain and policy

| Control | Tooling | Enforced by |
|---|---|---|
| Registry with licence metadata | Quay or Harbor; each image labelled `i3.license_class`, `i3.permitted_use`, `i3.source` | Admission (Kyverno) |
| Signing and provenance | cosign + SBOM (syft) at build | Admission verifies signature |
| Scanning | Red Hat ACS (StackRox) or Trivy; block critical CVEs in prod namespaces | CI + admission |
| Pod security | Restricted SCC by default; labelled node pools/namespaces for privileged emulators | Kyverno + SCC |
| Residency | `residency=ke` label on namespaces/PVCs/buckets; deny scheduling of `residency=ke` workloads to non-Nairobi clusters; deny replication annotations | Kyverno + Argo CD project destinations |
| Pinned images | No `latest`, prefer digests | Kyverno |

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: {name: require-pinned-image-tags}
spec:
  validationFailureAction: Enforce
  rules:
  - name: no-latest
    match: {any: [{resources: {kinds: [Pod]}}]}
    validate:
      message: "Images must use a pinned tag or digest, not :latest."
      pattern:
        spec:
          containers:
          - image: "!*:latest"
```

### 5.5 Observability and SLOs

- **Stack:** Prometheus, Alertmanager, Loki, Tempo (OpenTelemetry), Grafana, **Langfuse** for LLM traces. Same stack at every site; central Grafana reads from each.
- **Golden signals per product:** gateway availability; p50/p95 first-token latency per alias; lab launch time (p50/p95) per template; queue wait; GPU utilisation; spend rate vs budget; Moodle p95 page time; BBB join success rate; xAPI ingest lag.
- **SLOs (initial):** AI gateway 99.9% monthly; lab launch p95 < 60 s (warm-pool templates p95 < 30 s); LTI launch success 99.5%; usage-event ingestion lag p95 < 60 s.

### 5.6 Backup and DR

| Data | Method | RPO / RTO | Drill |
|---|---|---|---|
| Postgres (LiteLLM, billing, Keycloak, Moodle DB) | pgBackRest continuous archive to COS (per-site bucket) | RPO ≤ 5 min / RTO ≤ 4 h | Quarterly restore |
| Object data, model blobs | COS versioning + lifecycle | RPO 24 h | Quarterly |
| Kubernetes state | Argo CD (Git is the backup) + Velero for PVs | RTO ≤ 4 h | Semi-annual full rebuild |
| N1 resident data | Backups **stay in Nairobi** (second DC or second bucket in-country) | RPO ≤ 24 h | Semi-annual |
| Audit logs | WORM bucket, Object Lock | Immutable | Annual export test |

### 5.7 Infrastructure-as-code

Terraform (IBM Schematics workspaces per account/site) for VPCs, ROKS clusters, worker pools, COS, DNS, Transit Gateway. Argo CD for everything inside the clusters. **Guardrails:** budget alerts at 50/70/90% of credits per account; mandatory tags (`tenant`, `product`, `env`, `owner`); nightly Schematics `destroy` for non-prod worker pools (S1 pattern).

---

## 6. Lab Fabric Implementation (Smart Labs + Multi-Vendor + Network Labs)

### 6.1 Runtime tiers

| Tier | Runtime | What runs | Isolation | Launch target (p50) | Scale unit |
|---|---|---|---|---|---|
| **C** | Containers / Clabernetes | Linux, Kali, DBs, dev environments, OSS NOS (FRR, VyOS, SONiC), cEOS, cRPD, SR Linux | Namespace + NetworkPolicy + EgressFirewall; Kata/sandboxed containers for hostile-code labs | < 20 s (warm) | Node pool |
| **V** | KubeVirt VMs | FortiGate, VM-Series, CSR/C8000v, ISE, Windows, nested ESXi | Same + dedicated bare-metal pool | < 60 s (pre-cloned disk) | Bare-metal node |
| **B** | Persistent shared emulators | CML / EVE-NG for CCIE-scale, SD-WAN controllers | Dedicated VM/bare metal per cohort | Minutes (scheduled) | Whole host |
| **S** | Sandbox vending | AWS/Azure/GCP sandbox accounts; SaaS developer tenants; IBM Cloud/watsonx accounts | Vendor-side accounts with hard budgets/policies | < 2 min | Account/tenant |
| **P** | IBM Power (AIX/IBM i) | LPARs on Power Virtual Server / on-prem Power | LPAR per session | Minutes | LPAR |

**[CHANGE]** S7 treats "45 vendor labs" as one uniform runtime. In practice ≈40% of them are Tier S or Tier P/unsupported — see §6.7.

### 6.2 The Lab Orchestrator (replaces Ansible-and-`at` provisioning)

**Custom resources** (group `labs.i3technologies.co.ke/v1alpha1`):

| CRD | Purpose |
|---|---|
| `LabTemplate` | Immutable, versioned definition of a lab: runtime tier, images (with licence class), resources, networks, tasks, egress policy, TTL, warm-pool settings |
| `LabPool` | Warm-pool policy for a template (min/max idle instances, pre-pull, pre-clone) |
| `LabSession` | One learner's (or team's) running instance; owned by a tenant/user/course context; carries TTL and status |
| `Tenant` | Tier, quotas, residency, entitlements, queue bindings (rendered from `tenants/*.yaml`) |

```yaml
apiVersion: labs.i3technologies.co.ke/v1alpha1
kind: LabTemplate
metadata: {name: sec-fortigate-basics, namespace: i3-labs-system}
spec:
  displayName: "FortiGate Fundamentals — Policies and NAT"
  version: 1.4.0
  tier: V
  vendor: fortinet
  images:
    - name: fortigate
      ref: quay.io/i3/fortigate@sha256:…              # digest-pinned
      licenseClass: training-partner                     # ledger key (§6.8)
      permittedUse: [training]
    - name: terminal
      ref: quay.io/i3/lab-terminal@sha256:…
      licenseClass: oss
  resources:
    fortigate: {cpu: 2, memory: 4Gi}
    terminal:  {cpu: "0.25", memory: 512Mi}
  networks: [{name: lan, type: l2-isolated}]
  egress: {policy: none}                                # none | allowlist | internet
  session: {ttl: 4h, idleTimeout: 30m, maxExtensions: 1}
  parameters:                                           # randomised per session to defeat answer sharing
    - {name: vlan_id, kind: int, range: [100, 199]}
    - {name: lan_cidr, kind: cidr, pool: 192.168.0.0/16, prefix: 24}
  grading: {ref: checks.yaml, weight: 100, attempts: 3}
  warmPool: {ref: sec-fortigate-basics-pool}
```

```yaml
apiVersion: labs.i3technologies.co.ke/v1alpha1
kind: LabSession
metadata: {name: s-8f21c, namespace: cust-usiu}
spec:
  templateRef: {name: sec-fortigate-basics, version: 1.4.0}
  user: {sub: "kc|4b1e…"}
  context:                       # from LTI launch
    lti: {platform: usiu-moodle, context_id: "CSC402", resource_link_id: "act-17", lineitem: "https://…/lineitems/17"}
  ttlOverride: null
status:                          # written by the controller
  phase: Running
  expiresAt: "2026-09-19T12:14:03Z"
  endpoints: {console: "https://labs.i3technologies.co.ke/s/8f21c/console", ssh: null}
```

**Controller responsibilities** (MVP in Python with **kopf**, migrate to Go/Operator SDK when stable):

1. Validate: tenant entitlement, licence gate (`permittedUse` × tenant commercial mode), concurrency and budget.
2. **Admit via Kueue** (queue, quota, fair share). If capacity is exhausted, the session is `Queued` with an ETA — never silently failing.
3. Materialise: namespace `lab-<id>`, quota, default-deny policy, egress firewall, PVC/VM disks, Multus networks, credentials from OpenBao (lease = TTL), routes.
4. Bind to a warm instance if one is available (below).
5. Emit `LabStarted` → UsageEvent (`lab_minutes` start marker), xAPI `launched`.
6. Reconcile TTL and idle timeout (`kopf.timer`); on expiry snapshot user state (if `persist: true`), delete namespace via a **finalizer** so PVCs/VMs/secrets are never orphaned (fixes S6's "orphan PVC" checkbox).
7. Emit `LabEnded` → UsageEvent with measured minutes; trigger grading if configured.

```python
# control-plane/lab-orchestrator/controller.py  (skeleton)
import kopf, datetime as dt
G, V, P = "labs.i3technologies.co.ke", "v1alpha1", "labsessions"

@kopf.on.create(G, V, P)
async def create(spec, name, namespace, patch, logger, **_):
    tpl = await load_template(spec["templateRef"])
    await enforce_entitlement(namespace, tpl)               # raises kopf.PermanentError
    await admit_via_kueue(namespace, name, tpl)              # may leave phase=Queued
    inst = await claim_warm_instance(tpl) or await provision(name, spec, tpl)
    patch.status["phase"] = "Running"
    patch.status["expiresAt"] = expiry(tpl, spec).isoformat()
    patch.status["endpoints"] = inst.endpoints
    await emit("lab.started", namespace, name, tpl)

@kopf.timer(G, V, P, interval=30, idle=30)
async def ttl(status, name, namespace, **_):
    if status.get("phase") == "Running" and now() >= parse(status["expiresAt"]):
        await grade_if_configured(namespace, name)
        await teardown(namespace, name)                      # snapshot → delete lab-<id>
        await emit("lab.ended", namespace, name)

@kopf.on.delete(G, V, P)                                     # finalizer-backed
async def delete(name, namespace, **_):
    await teardown(namespace, name, force=True)
```

**Warm pools (innovation #2)** — three levels, applied per template as risk allows:

| Level | What is pre-done | Saves | Applies to |
|---|---|---|---|
| L1 | Image **pre-pull** DaemonSet to every lab node | 20–90 s image pull | All container/VM-disk templates |
| L2 | **Pre-cloned** VM disks (CDI smart-clone from golden snapshot) | 30–120 s clone | Tier V templates |
| L3 | **Pre-booted stateless instances** (claim = inject credentials + set TTL) | 20–60 s boot | Templates flagged `stateless: true` |

Pool sizes follow the scheduled timetable: a `LabPool` accepts a cron-shaped `schedule` (e.g., 20 idle at 07:45 Mon–Fri before a lab block, 2 idle otherwise) and can be fed by the LMS calendar (§10.3).

**Admission control with Kueue (innovation #4):**

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata: {name: labs-t1}
spec:
  cohort: labs
  namespaceSelector: {matchLabels: {i3.tier: T1}}
  resourceGroups:
  - coveredResources: ["cpu", "memory", "nvidia.com/gpu"]
    flavors:
    - name: standard
      resources:
      - {name: cpu, nominalQuota: 200, borrowingLimit: 100}
      - {name: memory, nominalQuota: 800Gi, borrowingLimit: 400Gi}
      - {name: nvidia.com/gpu, nominalQuota: 0}
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata: {name: usiu, namespace: cust-usiu}
spec: {clusterQueue: labs-t1}
```

Each tenant's `concurrency` value in `tenants/<slug>.yaml` becomes its Kueue nominal quota; idle quota is borrowed by others (cohort), preserving high utilisation while honouring reservations. **This is what turns "capacity" into a contractual, sellable, measurable SKU.**

### 6.3 Tier V — KubeVirt appliance VMs (corrects S6 §2)

**Prerequisites:** bare-metal worker pool (or the Nairobi colo) with hardware virtualization; OpenShift Virtualization operator; ODF/Ceph RBD block storage; Multus; CDI. Confirm IBM's supported configuration for OpenShift Virtualization on ROKS before purchasing (F-05). Taint the pool `dedicated=vm:NoSchedule`.

**Golden image pipeline:** vendor image (from the licensed channel) → CDI import to a `labs-golden` PVC → `VolumeSnapshot` → smart-clone per session. Snapshots are versioned in the licence ledger.

```yaml
apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  name: fgt
  namespace: lab-8f21c
  labels: {labs.i3technologies.co.ke/session: "8f21c"}
spec:
  runStrategy: Always                       # replaces deprecated spec.running
  dataVolumeTemplates:
  - metadata: {name: fgt-root}
    spec:
      source: {pvc: {namespace: labs-golden, name: fortigate-7-4-3-golden}}
      storage:
        storageClassName: ocs-storagecluster-ceph-rbd
        resources: {requests: {storage: 20Gi}}
  template:
    metadata: {labels: {kubevirt.io/domain: fgt}}
    spec:
      nodeSelector: {dedicated: vm}
      tolerations: [{key: dedicated, value: vm, effect: NoSchedule}]
      domain:
        cpu: {cores: 2}
        memory: {guest: 4Gi}
        devices:
          disks: [{name: root, disk: {bus: virtio}}]
          interfaces:
          - {name: mgmt, masquerade: {}}
          - {name: lan,  bridge: {}}
      networks:
      - {name: mgmt, pod: {}}
      - {name: lan,  multus: {networkName: lab-l2-8f21c}}
      volumes:
      - {name: root, dataVolume: {name: fgt-root}}
      # licence/bootstrap config injected from a per-session Secret (no licence in the image)
      - name: cfg
        cloudInitConfigDrive: {secretRef: {name: fgt-bootstrap}}
```

**Quota note:** the per-session `ResourceQuota` must be computed from the template (VM + terminal + overhead), not a fixed `2 CPU / 4 GiB` — S7's playbook quota is smaller than its own FortiGate VM plus terminal.

### 6.4 Network-lab track (Cisco CCIE-scale and multi-vendor) — S1 + S4 implemented

**Substitution [CHANGE]:** S1/S4 propose Containerlab "on OpenShift". Containerlab assumes a Docker/Podman host and privileged access, which fits poorly with OpenShift's CRI-O and Restricted SCC model. Use **Clabernetes** (Kubernetes-native Containerlab: each node becomes a workload, links become VXLAN tunnels) and keep plain Containerlab for CI runners and engineer laptops. Same topology files, two runtimes.

```yaml
# topologies/ccie-ei-fabric.clab.yml   (corrected S1 appendix; verify kind names against pinned Containerlab)
name: ccie-fabric
topology:
  nodes:
    spine1:   {kind: cisco_c8000v, image: registry.i3.internal/vrnetlab/cisco_c8000v:17.12.01}
    leaf-eos: {kind: ceos,         image: registry.i3.internal/arista/ceos:4.33.0F}
    leaf-frr: {kind: linux,        image: quay.io/frrouting/frr:10.2.1}
    host1:    {kind: linux,        image: docker.io/library/alpine:3.20}
  links:
    - endpoints: ["spine1:eth1",   "leaf-eos:eth1"]
    - endpoints: ["spine1:eth2",   "leaf-frr:eth1"]
    - endpoints: ["leaf-eos:eth2", "host1:eth1"]
```

```yaml
# Clabernetes Topology CR wrapping the same definition (verify apiVersion for your release)
apiVersion: clabernetes.containerlab.dev/v1alpha1
kind: Topology
metadata: {name: ccie-fabric, namespace: lab-8f21c}
spec:
  definition:
    containerlab: |
      # paste or include the .clab.yml content above
```

Nodes that wrap vendor VMs through **vrnetlab** need `/dev/kvm` — schedule them on the Tier V bare-metal pool; pure-container nodes (cEOS, cRPD, SR Linux, FRR, VyOS) run on the standard pool.

**Pipeline (S1 §6, with one substitution and two additions):**

```
PR ─► Tekton CI: lint (yamllint/clab schema) → secret scan → Batfish snapshot validation
        │            (reachability / ACL / BGP intent assertions in pytest)
        ▼
   Argo CD sync → Clabernetes deploy from Quay images (digest-pinned)
        ▼
   AWX / Event-Driven Ansible: day-0/1 config (cisco.ios, cisco.nxos, cisco.sdwan, arista.eos)
        ▼
   gNMIc → Prometheus → Grafana; Suzieq snapshot
        ▼
   Verification gate (pytest-network + Batfish differential) → evidence pack (configs + dashboard PDF)
        ▼
   Evidence to COS (WORM) → LabSession grading input / customer POC report
        ▼
   TTL controller destroys the topology (replaces the 02:00 cron; cost + hygiene)
```

Additions **[NEW]**: (a) **NetBox is the licence and inventory ledger** for nodes, IPs, image digests, and entitlements (§6.8); (b) **the same pipeline is the product**: a "POC Environment" (KES 100k/month, S5/S7) is a Git repo + Tekton run that the customer can watch and reproduce.

```yaml
# gnmic.yaml — telemetry from CAT8000v/NX-OS/cEOS into Prometheus (corrected S1 appendix)
targets:
  spine1: {address: "10.240.1.11:57400"}   # credentials injected from a Secret at runtime; never committed
username: ${GNMIC_USERNAME}
password: ${GNMIC_PASSWORD}
skip-verify: true                          # lab only; use TLS profiles for anything customer-facing
subscriptions:
  ifstate:
    paths: ["/interfaces/interface/state/oper-status"]
    mode: stream
    stream-mode: sample
    sample-interval: 10s
  bgp:
    paths: ["/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state/session-state"]
    mode: stream
    stream-mode: on-change
outputs:
  prom: {type: prometheus, listen: ":9804", path: /metrics, expiration: 60s}
```

**CCIE-scale (Tier B):** run CML (Enterprise/partner-licensed) or EVE-NG as a long-lived VM on a bare-metal node per cohort; images imported only from licensed channels; snapshot per candidate; "class reset" via VolumeSnapshot restore (S1 §3.4). Physical Dell anchor nodes (S1) remain optional for candidates who need offline fidelity.

**Telemetry-first grading (innovation #3 applied to networking):** the auto-grader queries devices via gNMI/NETCONF for state (BGP session up, route present, ACL hit-count) instead of scraping CLI text.

### 6.5 Lab isolation and safety (fixes F-06)

1. **Default-deny per lab namespace**, then explicit allows:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: default-deny, namespace: lab-8f21c}
spec: {podSelector: {}, policyTypes: [Ingress, Egress]}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: allow-intra-ns-dns-ingress, namespace: lab-8f21c}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  ingress:
  - from: [{podSelector: {}}]
  - from: [{namespaceSelector: {matchLabels: {network.openshift.io/policy-group: ingress}}}]
  egress:
  - to: [{podSelector: {}}]
  - to: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: openshift-dns}}}]
    ports: [{protocol: UDP, port: 5353}, {protocol: TCP, port: 5353}]
```

2. **Egress firewall** for cyber/Kali labs (OpenShift OVN-Kubernetes): only in-namespace targets and a package mirror; **never open internet** — attack tooling on shared cloud IPs risks abuse complaints and provider suspension.

```yaml
apiVersion: k8s.ovn.org/v1
kind: EgressFirewall
metadata: {name: default, namespace: lab-8f21c}
spec:
  egress:
  - {type: Allow, to: {dnsName: mirror.i3technologies.co.ke}}
  - {type: Deny,  to: {cidrSelector: 0.0.0.0/0}}
```

3. **Hostile-code labs** (malware analysis, exploit development): OpenShift sandboxed containers (Kata) or dedicated VM tier — never plain pods.
4. **Session guardrails:** CPU/memory limits, `pids` limit, no host mounts, read-only root filesystem for terminals, cryptomining detection (CPU-pattern alert → auto-terminate + flag user), per-user concurrent-session cap.
5. **Recording & audit:** terminal session recording (asciinema-style) to tenant WORM bucket where the SKU includes it (S10 promises "session recording").

### 6.6 State-based grading engine (innovation #3)

Graders run **outside** the learner's environment as an ephemeral Job with read-only credentials, so learners cannot tamper with checks or see answers.

```yaml
# labs/templates/fortinet/sec-fortigate-basics/checks.yaml
version: 1
params_from: session            # uses the randomised vlan_id / lan_cidr for this session
tasks:
  - id: policy-exists
    title: "Create an outbound policy for LAN → WAN"
    weight: 30
    check: {type: http, target: fortigate, path: /api/v2/cmdb/firewall/policy, assert: "json.results[?srcintf[0].name=='port2'].action == ['accept']"}
  - id: nat-enabled
    title: "Enable source NAT on the policy"
    weight: 30
    check: {type: http, target: fortigate, path: /api/v2/cmdb/firewall/policy, assert: "json.results[*].nat == ['enable']"}
  - id: reachability
    title: "Client can reach the test server"
    weight: 40
    check: {type: exec, target: terminal, cmd: "curl -s -o /dev/null -w '%{http_code}' http://{{ server_ip }}", expect: "200"}
feedback: hints_ladder          # progressive hints, never the answer
attempts: 3
```

**Supported check types:** `exec` (in-pod), `http`/`rest`, `sql`, `k8s` (resource state), `gnmi`/`netconf`, `file`, `prometheus` (query result), `llm-rubric` (for free-text/code review — advisory; uses the `coder` alias with a rubric and cites evidence; human moderation for high-stakes grades).

**Outputs (one grading run → four consumers):** score JSON → **LTI AGS** score to Moodle; **xAPI** `completed/scored` statement to the LRS; **UsageEvent** (`grading_runs`); **faculty feedback** view. **Anti-cheat:** per-session randomised parameters, hidden checks, attempt limits, and similarity flags across submissions.

### 6.7 Vendor onboarding: feasibility classes and waves (reconciles S7's 45 vendors)

| Class | Meaning | Vendors (from S7 matrix) | Licence route |
|---|---|---|---|
| **A — OSS/free runtime** | Container/VM with no vendor gate | Linux/RHEL-compatible, Kali, PostgreSQL, MongoDB (CE), Oracle Database Free, Kubernetes/OpenShift-compatible (OKD), FRR/VyOS/SONiC, Arista cEOS (verify EULA for training delivery), Nokia SR Linux | Open-source licences; confirm redistribution terms |
| **B — Licensed virtual appliance** | Needs vendor licence appropriate to training/LaaS | Cisco (CML Enterprise/partner), Juniper, Aruba AOS-CX, Fortinet, Palo Alto, Check Point, Sophos, F5, VMware/Broadcom, NetApp ONTAP sim, Splunk, Veeam, Nutanix CE (hardware-bound), Red Hat (RHEL/AAP for training via Red Hat training-partner route), IBM software | Vendor training-partner / education programmes; written confirmation per vendor |
| **C — Sandbox / SaaS vending** | No runtime to host; provision an account or tenant | AWS, Azure, GCP, IBM Cloud/watsonx, Microsoft 365, Salesforce, ServiceNow, Atlassian, Zoom, CrowdStrike, Zscaler, MongoDB Atlas | Real sandbox accounts with budgets/policies; vendor developer-programme terms; deep-link + credential vending |
| **D — Hardware-bound / demand-gated** | No practical virtual lab, or licences unavailable | Dell, HPE, Lenovo, Pure, Rubrik, Cohesity, Commvault, Veritas, Avaya, Mitel, Poly, Huawei (eNSP), Teradata, SAP | Vendor-hosted labs, partner referral, or defer |
| **P — IBM Power** | AIX / IBM i LPARs | IBM Power Systems | IBM partner entitlements; Power Virtual Server or on-prem Power |

**Cloud sandbox vending (Class C) [NEW]** — the correct answer to S7's "LocalStack / ARM emulator" claims for certification labs: per-learner ephemeral **AWS account** (AWS Organizations + SCPs + budget action), **Azure resource group/subscription** with Azure Policy and cost caps, **GCP project** with org policies; auto-nuked on TTL. Keep LocalStack for *fast API-level exercises* and CI, not as the certification-fidelity environment.

**Waves**

| Wave | Window | Scope | Exit criterion |
|---|---|---|---|
| **W1** | Weeks 1–12 | Class A + IBM (watsonx/Cloud) + Class C cloud sandboxes + i3 AI Lab + Linux/Red Hat labs on i3's own OpenShift | 25 templates live, warm pools on the top 8, grading on ≥ 60% |
| **W2** | Weeks 13–26 | Cisco (via CML Enterprise/partner), Fortinet, Palo Alto, Juniper, Aruba, cEOS multi-vendor fabrics; Check Point/F5 if a customer is signed | 3 vendors fully licence-cleared with written confirmation; interop lab published |
| **W3** | Week 27+ | VMware/Nutanix on bare metal; SaaS-tenant vendors; Class D only on signed demand | Demand-gated |

### 6.8 Licence and entitlement ledger (fixes F-01)

A table in Postgres (mirrored in NetBox as custom fields) — **the platform refuses to run an image whose row does not permit the requested use.**

| Field | Example |
|---|---|
| `image_id` / `digest` | `fortigate-7.4.3` / `sha256:…` |
| `vendor`, `product`, `version` | Fortinet / FortiGate-VM / 7.4.3 |
| `source` | Fortinet support portal, download ID |
| `entitlement_type` | `commercial` \| `training-partner` \| `eval` \| `nfr` \| `oss` \| `free-with-account` |
| `permitted_use` | `internal` \| `demo` \| `training` \| `laas` \| `resale` |
| `evidence_ref` | Contract / email / portal screenshot in the compliance vault |
| `seat_limit`, `expiry`, `owner`, `review_date` | 500 concurrent, 2027-03-31, platform lead, quarterly |

**Enforcement:** a Kyverno/ValidatingAdmissionWebhook checks each `LabTemplate` image against the ledger and the tenant's `commercial_mode` (`internal`, `training`, `laas`). **NFR** rows can only satisfy `internal`/`demo`. This converts F-01 from a policy statement into a control, and gives you a due-diligence artefact for IBM, Red Hat and every vendor partner programme.

**Immediate actions (week 1–4):** enumerate every image currently deployed → classify → obtain written confirmation from each vendor for the intended commercial use → mark unresolved images `internal` only → re-baseline collateral claims.

---
## 7. AI Platform Implementation (S2, S3, S8 extended)

### 7.1 Model estate and runtime split

**[CHANGE]** S8 keeps Ollama for every tier. Keep Ollama where it is strong (small CPU models, simple ops) and introduce **vLLM** (continuous batching, prefix caching, LoRA serving, rich metrics) for anything that must serve many concurrent users on GPU.

| Alias | Model (initial) | Runtime | Hardware | Purpose |
|---|---|---|---|---|
| `granite-nano` | Granite 3.1 2B | Ollama | CPU | Classification, routing, cheap summarisation |
| `qwen-fast` | Qwen 2.5 7B Instruct (Q4) | Ollama | CPU (GPU spill-over) | General chat, tutor default |
| `qwen-heavy` | Qwen 2.5 14B Instruct (AWQ) | **vLLM** | 1× L4/L40S-class 24–48 GB | Reasoning, RAG answers, authoring copilot |
| `coder` | Qwen 2.5 Coder 7B (or 14B) | **vLLM** | GPU | Code review, lab authoring, auto-grading rubrics |
| `vision` | Qwen 2.5-VL 7B (replaces `llava:13b`) | **vLLM** | GPU | Documents, diagrams, scanned forms |
| `embed` | Multilingual embedding (evaluate bge-m3 / multilingual-e5) | TEI/Ollama | CPU | RAG embeddings — pick by **Swahili retrieval recall**, not English leaderboards |
| `rerank` | bge-reranker class | TEI | CPU/GPU | RAG quality |
| `stt` / `tts` | Faster-Whisper; TTS per §7.8 | i3-voice | CPU/GPU | Voice AI, OTT captions |

**Bake-off rule (from S8 §2.3, retained):** NVIDIA vs AMD ROCm decided by a two-week benchmark on *i3's own prompts* (RAG, Swahili, code). Do not block metering/tenancy workstreams on hardware.

**Fine-tuning tier [NEW]:** A100 burst (GPU4YOU voucher, S7) for QLoRA jobs launched from JupyterLab notebooks through Kueue (`gpu-burst` flavor, preemptible). Output is a **LoRA adapter**, not a new full model.

**Per-tenant LoRA serving (innovation #14):** vLLM serves one base model with many adapters (`--enable-lora`); each tenant's adapter is a route in LiteLLM (`qwen-heavy@tenant`). Bespoke legal/tax/medical adaptation (S3 feature 5) becomes a low-marginal-cost SKU rather than a new GPU per customer. Adapters are tenant data — stored in the tenant's residency bucket.

```yaml
# ai/vllm/qwen-heavy.yaml  (pin image by digest in production)
apiVersion: apps/v1
kind: Deployment
metadata: {name: vllm-qwen-heavy, namespace: i3-model-gateway}
spec:
  replicas: 1
  selector: {matchLabels: {app: vllm-qwen-heavy}}
  template:
    metadata: {labels: {app: vllm-qwen-heavy}}
    spec:
      nodeSelector: {gpu: "true"}
      tolerations: [{key: gpu, operator: Equal, value: "true", effect: NoSchedule}]
      containers:
      - name: vllm
        image: vllm/vllm-openai@sha256:<pinned>
        args: ["--model","Qwen/Qwen2.5-14B-Instruct-AWQ","--quantization","awq",
               "--served-model-name","qwen-heavy","--max-model-len","16384",
               "--gpu-memory-utilization","0.90","--enable-prefix-caching","--max-num-seqs","32"]
        env: [{name: VLLM_API_KEY, valueFrom: {secretKeyRef: {name: vllm-keys, key: key}}}]
        resources: {limits: {nvidia.com/gpu: 1, memory: 48Gi}, requests: {cpu: "6", memory: 32Gi}}
        ports: [{containerPort: 8000}]
        readinessProbe: {httpGet: {path: /health, port: 8000}, initialDelaySeconds: 60}
        volumeMounts: [{name: hf-cache, mountPath: /root/.cache/huggingface}]
      volumes: [{name: hf-cache, persistentVolumeClaim: {claimName: model-cache-rwx}}]
```

**Autoscaling on the signal that matters (replaces "LiteLLM queue depth", which LiteLLM does not expose as a scaling metric):**

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: {name: vllm-qwen-heavy, namespace: i3-model-gateway}
spec:
  scaleTargetRef: {name: vllm-qwen-heavy}
  minReplicaCount: 1                 # no scale-to-zero on GPU (cold start = minutes)
  maxReplicaCount: 2                 # bounded by GPUs on the node pool
  cooldownPeriod: 600
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-k8s.openshift-monitoring.svc:9091
      query: avg(vllm:num_requests_waiting{model_name="qwen-heavy"})
      threshold: "4"
  - type: prometheus
    metadata:
      serverAddress: http://prometheus-k8s.openshift-monitoring.svc:9091
      query: avg(DCGM_FI_DEV_GPU_UTIL{pod=~"vllm-qwen-heavy.*"})
      threshold: "75"
```

Cold-start controls: model weights on an RWX PVC/COS cache (never downloaded at pod start), `prewarm` init check, readiness only after a warm-up completion, and one pod always hot.

### 7.2 LiteLLM gateway configuration (HA, fallbacks, metering hooks)

```yaml
# ai/litellm/config.yaml  (verify keys against the pinned LiteLLM version)
model_list:
  - {model_name: granite-nano, litellm_params: {model: ollama/granite3.1-dense:2b, api_base: "http://ollama-cpu:11434"}}
  - {model_name: qwen-fast,    litellm_params: {model: ollama/qwen2.5:7b-instruct-q4_K_M, api_base: "http://ollama-cpu:11434"}}
  - model_name: qwen-heavy
    litellm_params: {model: openai/qwen-heavy, api_base: "http://vllm-qwen-heavy:8000/v1", api_key: os.environ/VLLM_API_KEY, timeout: 120}
  - model_name: qwen-heavy-cpu                       # explicit CPU fallback alias (B1-4)
    litellm_params: {model: ollama/qwen2.5:14b-instruct-q4_K_M, api_base: "http://ollama-cpu:11434", timeout: 300}
  - {model_name: coder,  litellm_params: {model: openai/coder,  api_base: "http://vllm-coder:8000/v1",  api_key: os.environ/VLLM_API_KEY}}
  - {model_name: vision, litellm_params: {model: openai/vision, api_base: "http://vllm-vision:8000/v1", api_key: os.environ/VLLM_API_KEY}}
  - {model_name: embed,  litellm_params: {model: openai/embed,  api_base: "http://tei-embed:80/v1",     api_key: "none"}}

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 2
  timeout: 120
  fallbacks: [{"qwen-heavy": ["qwen-heavy-cpu"]}, {"coder": ["qwen-fast"]}]
  redis_host: os.environ/REDIS_HOST          # shared limits across ≥2 proxy replicas
  redis_password: os.environ/REDIS_PASSWORD

litellm_settings:
  callbacks: ["prometheus", "langfuse", "custom_callbacks.usage_emitter"]
  # Cache: exact-match only for T0. NEVER share a semantic cache across tenants
  # and disable it for T1/T2 and anything containing PII (leak risk).
  cache: false
  guardrails:
    - guardrail_name: pii-detect
      litellm_params: {guardrail: presidio, mode: pre_call, default_on: true}

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY      # break-glass only (§5.3)
  database_url: os.environ/DATABASE_URL
  store_model_in_db: false                       # config comes from Git (P2)
```

**Fallback observability:** a fallback event increments `i3_gateway_fallback_total{from,to}` and adds a `x-i3-degraded: cpu-fallback` response header — the "5× latency warning" S8 specifies.

**Usage emitter (feeds the unified meter):**

```python
# ai/litellm/custom_callbacks.py
from litellm.integrations.custom_logger import CustomLogger
import ulid, json

class UsageEmitter(CustomLogger):
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        md = (kwargs.get("litellm_params", {}) or {}).get("metadata", {}) or {}
        u = getattr(response_obj, "usage", None)
        if not u:
            return
        for resource, qty in (("llm_tokens_in", u.prompt_tokens), ("llm_tokens_out", u.completion_tokens)):
            await outbox_publish("usage.events", {
                "event_id": str(ulid.new()), "ts": end_time.isoformat(),
                "tenant_id": md.get("tenant"), "project_id": md.get("project"),
                "user_id_hash": md.get("user_hash"), "resource": resource,
                "sku": f"LLM-{kwargs['model'].upper()}", "quantity": qty, "unit": "token",
                "attrs": {"model": kwargs["model"], "region": md.get("region")},
            })

usage_emitter = UsageEmitter()
```

### 7.3 Keys, teams and budgets (S8 B2/B4 operationalised)

| LiteLLM object | Maps to | Rules |
|---|---|---|
| Team | Customer (tenant) | Budget in KES-equivalent, model allow-list, region pin |
| Virtual key | Project (or workload) | RPM/TPM caps, expiry ≤ 90 days, budget slice |
| User | Keycloak `sub` (hashed) | Per-user cap for T0/student tenants (runaway notebook loops) |
| Master key | Break-glass service account | Cannot be used for chat completions (B4-2) |

Keys are created/revoked by the Tenant Service from `tenants/*.yaml` (never by hand); Keycloak `user.disabled` events revoke user-bound keys (B4-4).

### 7.4 RAG platform (Enterprise Private RAG Studio — S3 feature 1)

**[CHANGE]** Replace ChromaDB with **Qdrant** (native clustering/replication, payload filtering, snapshots) — or pgvector on the existing Crunchy PG for small tenants. Chroma "production clustering" (S3 §6) is not a supportable HA story for bank-grade SLAs.

```
Upload (PDF/DOCX/PPTX/scan/SQL schema) ─► object bucket (tenant, residency-tagged)
   ─► Ingestion workers: Tika / Docling + OCR (Tesseract) ─► clean text + layout
   ─► Chunking (structure-aware; 400–800 tokens; keep tables intact)
   ─► `embed` (multilingual) + sparse (BM25/SPLADE) ─► Qdrant collection t_<tenant>_<corpus>
   ─► Metadata: doc_id, version, acl_groups[], source, lang, hash
Query: rewrite ─► hybrid retrieve (dense+sparse, ACL filter) ─► rerank ─► LLM answer with citations
       ─► guardrails (grounding check, PII, refusal rules) ─► response + trace (Langfuse)
```

Non-negotiables: **document-level ACLs** enforced in the vector query (a user cannot retrieve chunks they could not open); **mandatory citations** (answers without support return "not found in your documents"); **versioned indexes** and re-index jobs; **erasure by `doc_id`** removes chunks, embeddings and cached answers (KDPA data-subject rights); ingestion errors visible to the tenant admin.

### 7.5 Guardrails, evaluation and the release gate (S8 B5 extended)

**Runtime guardrails**

| Layer | Mechanism | Notes |
|---|---|---|
| PII detect/redact | Presidio pre-call + **Kenya recognizers** | Modes: `detect` → 2 weeks tuning → `redact` |
| Topical/safety rails | NeMo Guardrails for assistant products (bank helpdesk, HR, tutor) | Per-product rail sets in Git |
| Grounding | Citation check, refusal on low retrieval score | RAG products |
| Output filters | Toxicity, credential/secret patterns, system-prompt leakage | All aliases |
| Tool rails | Allow-listed tools, step and spend limits, human approval for writes | Agents (§7.7) |

Kenya PII recognizers to add to Presidio (regex starting points; validate against real samples):

| Entity | Pattern (starting point) |
|---|---|
| Kenyan mobile | `(?:\+254\|0)[17]\d{8}` |
| National ID | `\b\d{7,8}\b` with context words ("ID", "National ID", "Kitambulisho") |
| KRA PIN | `\b[AP]\d{9}[A-Z]\b` |
| M-Pesa transaction code | `\b[A-Z0-9]{10}\b` with context ("M-Pesa", "confirmed", "Ksh") |
| M-Pesa PIN | context-only rule: 4-digit sequence following "PIN" |

**Evaluation harness (`ai/eval/`)** — extends B5-1…B5-4:

| Suite | Size (v1 → v2) | Scoring | Gate |
|---|---|---|---|
| Task suites (summarise, QA-faithfulness, code, instruction-following) | 50–100 each → 300 | Rubric + LLM-judge (`qwen-heavy`) + spot check | Regression ≤ 2% vs prod alias |
| **Swahili/Sheng/code-switching** | 100 → 500 | Native-speaker rubric on a sample, automated for translation/QA | No regression; publish absolute score |
| **Domain packs**: KRA/eTIMS/VAT, CBK guidelines, KDPA, IBM/Red Hat certification content | 100 each | Exact-match + rubric | Per-product thresholds |
| RAG faithfulness/groundedness | 200 Q/A pairs per reference corpus | Citation precision/recall, groundedness | ≥ agreed threshold |
| Safety & jailbreak | 300 prompts | Refusal correctness, leakage tests | Zero critical leaks |
| PII detection | 200 seeded docs → 1,000 | Recall/precision per entity | ≥ 90% recall (B5-3) |
| **Tutor pedagogy** [NEW] | 150 scenarios | Does it give hints before answers? Does it refuse to complete graded work? | ≥ 90% correct behaviours |

**Release gate (Tekton):** candidate model/quant/adapter or prompt-pack change → run suites → thresholds → auto-generate model card (capabilities, scores incl. Swahili, latency, limits, intended use) → require approval from a named owner → promote alias via Git PR. Unapproved changes cannot reach `prod` aliases (B5-4). Publish cards in the customer portal; bank customers additionally receive **model-risk-management (MRM) documentation** (intended use, validation evidence, monitoring plan, change log).

**Runtime monitoring:** Langfuse traces + eval-on-sample (1–5% of production traffic scored by an LLM-judge, stored per tenant with consent), drift dashboards, incident playbook (P1: harmful/PII leak → disable route within 15 min).

### 7.6 Sage (Open WebUI) — resolving the S8 open question

- **Per-tenant Sage deployments** (namespace `sage-<tenant>`), each with its own LiteLLM virtual key, own Keycloak OIDC client, own object bucket. Do not fork Sage to make it multi-key.
- Enable user-info header forwarding so LiteLLM attributes usage to the individual user (hashed) while billing to the tenant key.
- Point Sage's document RAG at the **tenant's Qdrant collection via the RAG service**, not an embedded per-instance Chroma, so ACLs and erasure work uniformly.
- **Licence check before white-labelling:** the upstream project has introduced branding-preservation terms in recent releases; confirm the exact licence of the pinned version before offering "white-label Sage" (S8 out-of-scope item) or removing branding.

### 7.7 Agent platform (Agent Builder & Orchestrator — S3 feature 2)

**Architecture:** LangGraph workflows (multi-agent), each agent a container in the tenant namespace; **tools exposed via MCP servers** fronted by a **tool gateway** that enforces per-tenant authorisation (OPA), rate limits, schema validation, and audit.

```
Trigger (API/WhatsApp/Email/Schedule) ─► Agent Runtime (LangGraph, per tenant)
     ├─► LiteLLM (team key, guardrails, budgets)
     ├─► Tool Gateway (OPA) ─► MCP servers: AfroERP · Finacle/T24 adapter (read-only first) ·
     │                          M-Pesa Daraja · Email/WhatsApp · Document store · Calendar
     ├─► Human-approval queue (writes over threshold; e.g., loan decisions, disbursements)
     └─► Trace + audit (Langfuse, WORM) ; cost per run in UsageEvent (`agent_runs`)
```

**Controls:** max steps/time/cost per run; write tools default to *propose → approve*; sandboxed code-exec tool (Kata/VM tier); per-agent evals in CI (task success, tool-misuse, prompt-injection resistance); registry with owner and version. **Reference agent chain (S3):** Lead-Qualifier → Contract-Review → ERP-Entry, with the ERP write gated by approval in v1.

**Student agent sandbox (S9 §6.2):** the same runtime in a T0/T1 namespace on the GPU-burst queue, with tool gateway limited to a training toolset.

### 7.8 Voice AI (i3-voice) and the licensing catch

- **STT:** Faster-Whisper (MIT-licensed weights), fine-tuned on Swahili and English–Swahili code-switching with licensed/consented data; streaming over WebSockets; captions for OTT (§10.8).
- **TTS (F-15):** XTTS-v2 weights are non-commercial. For a paid IVR/WhatsApp-voice product, choose one: (a) a commercially licensed TTS model/API, (b) train a permissively licensed architecture (e.g., VITS-class) on **consented, contracted voice data**, or (c) restrict XTTS-v2 to internal demos.
- **Telephony:** SIP/Africa's Talking Voice bridge → STT → LiteLLM (`qwen-fast`) → TTS; latency budget ≤ 1.5 s turn-around; barge-in support; M-Pesa confirmation via Daraja callbacks.
- **Privacy:** call recordings only with consent; PII redaction in transcripts; voiceprints are biometric data — do not create them without a legal basis.

---

## 8. Metering, Billing and FinOps (S8 B2 extended)

### 8.1 Data model

```sql
-- billing schema (extends S8 §3.3)
CREATE TABLE billing.customers (id text PRIMARY KEY, name text, tier text, currency text DEFAULT 'KES',
                                residency text, erpnext_customer text, commercial_mode text);
CREATE TABLE billing.projects  (id text PRIMARY KEY, customer_id text REFERENCES billing.customers, name text, litellm_team_id text);
CREATE TABLE billing.api_keys  (id text PRIMARY KEY, project_id text REFERENCES billing.projects,
                                litellm_key_hash text UNIQUE, label text, budget_kes numeric, expires_at timestamptz);
CREATE TABLE billing.sku       (code text PRIMARY KEY, resource text, unit text, price_kes numeric,
                                tier_breaks jsonb, valid_from date, valid_to date);
CREATE TABLE billing.entitlement (customer_id text, sku_code text, included_qty numeric, period text, reserved_concurrency int);
CREATE TABLE billing.usage_daily (customer_id text, project_id text, day date, resource text, sku text,
                                  quantity numeric, source text,
                                  PRIMARY KEY (customer_id, project_id, day, resource, sku, source));
CREATE TABLE billing.usage_monthly (customer_id text, ym text, sku text, quantity numeric, amount_kes numeric,
                                    PRIMARY KEY (customer_id, ym, sku));
CREATE TABLE billing.statement (id bigserial PRIMARY KEY, customer_id text, ym text, pdf_uri text, erpnext_invoice text, status text);
CREATE TABLE billing.wallet    (customer_id text PRIMARY KEY, balance_kes numeric, updated_at timestamptz);
CREATE TABLE billing.wallet_txn(id bigserial PRIMARY KEY, customer_id text, kind text, amount_kes numeric, ref text, ts timestamptz DEFAULT now());
```

### 8.2 Price book and unit-cost formulas

| Resource | Cost basis (internal) | Price basis (external) |
|---|---|---|
| LLM tokens (GPU) | `GPU $/hr ÷ (sustained tokens/hr at ~60% utilisation)` per alias | Cost-plus per 1M tokens, KES, reviewed quarterly against FX |
| LLM tokens (CPU) | `node $/hr ÷ tokens/hr` | Lower rate; used for T0 |
| Lab session-hour | `node $/hr ÷ sessions-per-node` (measured) | Per session-hour, or bundled in seat |
| GPU-minute (notebooks/fine-tune) | `GPU $/hr ÷ 60` | Premium multiplier + minimum billing increment |
| Reserved concurrency | `Kueue nominal quota × node cost × utilisation target` | Monthly per concurrent seat (the "2,500" claim becomes SKUs) |
| VOD/stream minutes, storage | Egress + storage cost | Included allowance + overage |

Pricing in **KES with quarterly FX indexation** answers the FX-volatility argument in S3 without exposing customers to USD-billing spikes.

### 8.3 Reconciliation job (corrects S6 §3)

The **callback path** (§7.2) is the source of truth; a nightly job **reconciles** it against LiteLLM's own spend table and flags drift > 0.5%. It runs with a **read-only DB role**, not the master key, and is **idempotent**.

```sql
-- nightly: recompute LLM usage from LiteLLM's table (verify column names against the pinned schema)
INSERT INTO billing.usage_daily (customer_id, project_id, day, resource, sku, quantity, source)
SELECT c.id, p.id, date_trunc('day', s."startTime")::date, 'llm_tokens',
       'LLM-' || upper(s.model), SUM(s.total_tokens), 'litellm-spendlogs'
FROM "LiteLLM_SpendLogs" s
JOIN billing.api_keys k ON k.litellm_key_hash = s.api_key
JOIN billing.projects  p ON p.id = k.project_id
JOIN billing.customers c ON c.id = p.customer_id
WHERE s."startTime" >= :from_ts AND s."startTime" < :to_ts
GROUP BY 1,2,3,4,5
ON CONFLICT (customer_id, project_id, day, resource, sku, source)
DO UPDATE SET quantity = EXCLUDED.quantity;
-- Then: compare source='litellm-spendlogs' vs source='callback' per day; alert if |Δ| > 0.5%.
```

Note: LiteLLM's `/spend/calculate` estimates the cost of a *given request*; it is not a reporting endpoint (S6 used it as one).

### 8.4 Invoicing through AfroERP (ERPNext v15) with KRA eTIMS [NEW]

i3 already runs ERPNext with eTIMS. Instead of "a clean export" (S8), post month-end invoices into it:

```
Month-end (day 1, 02:00 EAT)
 usage_daily → usage_monthly (price book, entitlements, included allowances)
   → draft Sales Invoice via ERPNext REST  ──► finance approval (human)
   → submit → AfroERP eTIMS integration signs/submits to KRA ──► invoice PDF + usage statement (CSV/PDF)
   → e-mail/WhatsApp (Engage) ──► M-Pesa Paybill/STK payment link ──► Payment Entry via Daraja callback
```

```python
# billing/erpnext_post.py (sketch)
import requests
def post_invoice(customer, lines, ym, base, token):
    body = {"doctype": "Sales Invoice", "customer": customer, "posting_date": f"{ym}-28",
            "currency": "KES", "items": [{"item_code": l["sku"], "qty": l["qty"], "rate": l["rate"]} for l in lines],
            "custom_usage_period": ym, "docstatus": 0}      # draft; finance submits
    r = requests.post(f"{base}/api/resource/Sales Invoice",
                      headers={"Authorization": f"token {token}"}, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["name"]
```

### 8.5 Prepaid wallet with M-Pesa (T0 self-serve) [NEW]

Students, SMEs and bootcamp participants pay through **Daraja STK Push** into a wallet; the callback credits `billing.wallet` and increments the user's LiteLLM key budget and lab-hour allowance. Reuses the STK integration already live in AfroERP. Unspent balance policy (expiry/refund) must be legal-reviewed and stated in the terms.

### 8.6 FinOps and credit governance

- **Tagging:** every cloud resource `tenant`, `product`, `env`, `owner`; OpenCost (or IBM cost management) for per-namespace cost.
- **Credit burn controller (innovation #17):** for each account, compute `credit_remaining`, `burn_7d`, `days_to_zero`. If `days_to_zero < days_left_in_quarter`, the controller (a) shrinks warm pools, (b) lowers KEDA max nodes, (c) pauses Class-B/V scheduled cohorts not marked priority, (d) alerts the platform owner. Restores automatically when the forecast recovers. **Confirm credit expiry/rollover terms with IBM** — S5/S7 assume quarterly use-it-or-lose-it.
- **Post-credit run-rate model:** maintain a live "cash cost per lab-hour / per 1M tokens" dashboard so the day credits end is a planned event, not a shock (C8).
- **Unit economics per tenant:** revenue − (LLM + lab + storage + media + support allocation) → margin; alert when a tenant's margin < 30%.
- **Budget alerts** at 50/70/90% (accounts) and 50/80/95% (tenant keys, S8 §3.4); hard caps return friendly JSON.

---

## 9. Multi-Tenancy, Security, Audit and Compliance

### 9.1 RBAC matrix

| Capability | student | faculty/ta | developer | tenant-admin | viewer | i3-admin |
|---|---|---|---|---|---|---|
| Launch lab session | ✔ (entitled) | ✔ | ✔ | ✔ | — | ✔ (support, audited) |
| See others' sessions/results | — | ✔ (own course) | — | ✔ | ✔ (aggregate) | ✔ (audited) |
| Create/rotate API keys | — | — | ✔ (own project) | ✔ | — | ✔ |
| Manage RAG corpora | — | ✔ (course) | ✔ | ✔ | — | — |
| Author lab templates / courses | — | ✔ (draft) | ✔ | ✔ (publish) | — | ✔ |
| Billing & budgets | — | — | — | ✔ | ✔ | ✔ |
| Audit export | — | — | — | ✔ (own tenant) | — | ✔ |
| Break-glass (master key, cluster admin) | — | — | — | — | — | Dual-control + ticket |

**i3-admin access to tenant data** is a privileged, time-boxed, ticketed action with automatic customer notification (T1/T2) — a standard bank and university requirement.

### 9.2 Threat-driven controls

| Threat | Control |
|---|---|
| Lab escape / noisy neighbour | Restricted SCC, quotas, node pools, sandboxed containers/VMs, per-pod limits |
| Learner attacks the internet from Kali | Egress firewall default-deny; abuse alerts |
| Cross-tenant data leak in RAG/AI | Per-tenant collections/keys; ACL filters; no shared semantic cache for T1+ |
| Prompt injection via documents | Content sanitisation, tool gateway allow-lists, HITL on writes, injection evals in CI |
| Stolen API key | Short expiry, per-key limits, anomaly detection on `UsageEvent`, one-click revoke |
| Malicious/unlicensed image | Signed images only; licence ledger gate; scanning |
| Insider misuse | Dual-control break-glass; audit; least privilege |
| Ransomware/DR | Immutable backups, restore drills |
| Credential sharing (students) | Concurrent-session caps, device/IP anomaly flags |

### 9.3 Audit logging (S8 B4 extended)

**Sources:** LiteLLM request metadata (not content by default), OpenShift API audit (tenant namespaces), Keycloak events, Moodle/LTI logs, lab session events, admin actions, tool-gateway calls.

**Pipeline:** Vector/Fluent Bit → Kafka topic `audit` → writer → **IBM COS with Object Lock (compliance mode)**; retention class per contract (default 7 years for metadata).

**Tamper-evidence beyond WORM [NEW]:** each batch object carries the SHA-256 of the previous batch and is signed with an OpenBao Transit key (hash chain); a daily Merkle root is published to a separate account/bucket. A weekly verifier job recomputes the chain and alerts on any break (B4-3).

**Resolving the erasure-vs-WORM conflict [NEW]:** WORM audit stores **metadata and hashes only** (who, what, when, model, token counts, decision IDs). **Content** (prompts, documents, outputs) is stored separately with a shorter retention, encrypted with **per-tenant data keys**; erasure requests and contract end are honoured by **crypto-shredding** (destroying the key). This keeps a 7-year audit trail without retaining personal content — have counsel confirm against KDPA obligations.

### 9.4 Nairobi sovereign region (B3 extended)

**Recommendation (retained from S8, tightened):** Option B — colocation in Nairobi for the resident data plane, Frankfurt for non-resident control/DR. Add procurement-grade detail:

| Criterion | Requirement |
|---|---|
| Facility | Tier III (or equivalent) design, N+1 power/cooling, physical access logging; candidates to quote: iColo, Africa Data Centres, iXAfrica, Node Africa, plus bare-metal providers with Nairobi presence |
| Density | GPU-ready racks (≥ 10–20 kW/rack initially) |
| Connectivity | Cross-connects to at least two carriers/IXP (KIXP); 10/25 GbE to compute; separate management network |
| Platform | **Supported Red Hat OpenShift (OCP) subscription** for T2/regulated use rather than community OKD — banks will ask about vendor support (S8 §9 open question: recommendation is OCP via i3's Red Hat partner entitlements, OKD only for non-production) |
| Cluster shape | Phase A: compact 3-node OCP (control-plane nodes schedulable) + 2 GPU workers; Phase B: dedicated workers, ODF storage, second site for DR |
| Storage | ODF/Ceph NVMe; encryption at rest; per-tenant buckets with Object Lock for audit |
| Backups | In-country second location or second bucket; **never Frankfurt** for resident classes |
| Sizing basis | Start from measured T1 load (§13.3), not from headline capacity |

**Data-class residency matrix**

| Data class | Frankfurt (A1–A3) | Nairobi (N1) |
|---|---|---|
| Prompts, chat history, uploads, RAG corpora, embeddings, adapters | Non-resident tenants only | **Resident tenants — mandatory** |
| Audit logs (metadata) | Non-resident tenants | **Resident tenants — mandatory** |
| Student PII, grades, video, LRS statements | Non-resident tenants | **Resident tenants — mandatory** |
| Model weights, container images, Git config | ✔ (not customer data) | Pulled per region |
| Billing (pseudonymised aggregates) | Primary until N1 GA | Replica |
| Encrypted N1 configuration backup | ✔ (no customer data) | Source |

**Residency attestation (innovation #7):** a monthly job (a) enumerates PVCs, buckets, databases, Kafka topics labelled `residency=ke` and asserts their site; (b) asserts no replication/egress rules to non-KE endpoints; (c) inspects network flow logs for connections from resident namespaces to non-KE CIDRs; (d) verifies LiteLLM routes for resident teams point only to N1 endpoints; (e) produces a signed, timestamped PDF for the tenant's DPO — turning the contractual promise into evidence (B3-1).

**Actions until N1 is live:** stop describing hosting as "Kenya Region" (C1); offer resident tenants a contractual commitment only when N1 exists (or on a customer-hosted appliance, T2).

### 9.5 Compliance mapping (control objectives — counsel to confirm)

| Obligation | Platform control |
|---|---|
| Kenya Data Protection Act 2019 & 2021 Regulations: registration with ODPC, lawful basis, DPIA for high-risk processing, data-subject rights, breach notification, cross-border transfer limits, children's data | ODPC registration as controller/processor per product; DPIA templates for AI Tutor, EvalOS proctoring, voice; DSAR tooling (export + erasure via crypto-shredding); breach runbook with 72-hour clock; residency by policy (§9.4); age-aware handling where under-18 learners are enrolled |
| CBK requirements for regulated institutions (outsourcing, cyber-resilience, data location) | T2 appliance option, MRM pack, audit export, supplier-assurance pack (pen-test summary, DR test evidence) |
| Vendor licence terms | Licence ledger + enforcement (§6.8) |
| Customer assurance | Roadmap to ISO 27001 and SOC 2 Type I → II; annual third-party penetration test; vulnerability SLAs |
| Sensitive data | **Political-opinion data (PMaaS) is sensitive personal data** — dedicated site, separate DPIA, no shared infrastructure with regulated tenants (F-07) |

### 9.6 PMaaS separation (F-07)

Move PMaaS to **A-PM**: own namespace set, node pool (ideally own IBM Cloud account), Postgres, Keycloak realm, LiteLLM team/keys, and no Transit Gateway route to A2/A3. Marketing and legal separation (separate privacy notice, data-processing terms). Reconsider the shared brand adjacency in bank/university sales collateral.

---
## 10. EduBridge Implementation (S9 + S10 made buildable)

### 10.1 Moodle deployment

| Item | Decision |
|---|---|
| Version | Pin a current Moodle **LTS** release at build time; upgrade on the LTS cadence, never mid-semester |
| Topology | One Moodle instance per institution (`edu-<slug>`): web/PHP-FPM pods (HPA on CPU + active sessions), cron pod(s), Redis (sessions + MUC cache), Postgres (Crunchy HA), `moodledata` on RWX storage (CephFS) or object-store filedir plugin |
| Multi-tenancy | Namespace per institution, same `cust-<slug>` RBAC and Keycloak pattern as the AI Lab (S9 §3.1) |
| Branding | `theme_i3` shell: institution logo/colours + i3 co-brand; per-tenant Helm values |
| Data location | Non-resident tenants: A1 (Frankfurt) for now. **Resident tenants (universities with student PII): deploy in N1**, or accept a documented cross-border basis with counsel (§9.5) |
| Scaling | Load-test per institution before term start (L-series, §14); scale PHP pods before registration and exam weeks |
| Backup | pgBackRest + `moodledata` snapshots; per-institution restore drill |

**Identity:** Moodle `auth_oidc` → Keycloak realm `tenant-<slug>` → brokered to the university IdP (Entra ID / Google Workspace / SAML). Roles from token claims map to Moodle roles (`student`, `editingteacher`, `teacher`, `manager`). Provisioning: SIS export (CSV/API) → Keycloak users/groups → Moodle enrolment via cohort sync; nightly reconciliation, and a deprovision event (`user.disabled`) revokes labs, AI keys and sessions.

### 10.2 The i3 Connector plugin suite (the proprietary layer on Moodle)

| Plugin | Type | Function |
|---|---|---|
| `mod_i3lab` | Activity | "Practical Lab" — shows template details, launch button (LTI 1.3), attempt status, score; sets due dates and attempt limits |
| `block_i3tutor` | Block | Opens the course-scoped AI Tutor (Sage session pre-bound to the course corpus and current activity) |
| `local_i3sync` | Local | Course ↔ platform sync: create RAG corpus from course files (with instructor consent), push NRPS rosters to the timetable service, publish events to the bus |
| `filter_i3video` / activity | Filter | Embed PeerTube/BBB recordings with watch-progress events |
| `theme_i3` | Theme | Brand shell, low-bandwidth data-saver mode, PWA manifest |
| `tool_i3competency` | Admin tool | Map Moodle competency frameworks to certification tracks (IBM, Red Hat, Anthropic, CompTIA) and to badge rules |
| `logstore_xapi` (existing plugin) | Log store | Stream Moodle events as xAPI to the LRS — reuse, do not rebuild |

Build discipline: automated PHPUnit/Behat tests against each supported Moodle LTS; plugin signed and versioned; **no core hacks** (upgrade safety).

### 10.3 LTI 1.3 integration — end to end

i3 acts as **LTI tool** (labs, AI Tutor); Moodle is the **platform**.

```
Moodle (platform)                      i3 LTI Gateway                Orchestrator / Grader
      │  1. OIDC login initiation ───────►  /lti/login                        │
      │  ◄─ 2. redirect (state, nonce) ───                                    │
      │  3. id_token (JWT: sub, roles, context, resource_link,                │
      │        custom{template,version}, AGS+NRPS endpoints) ─► /lti/launch   │
      │                                     4. validate iss/aud/nonce/exp/    │
      │                                        deployment_id/JWKS             │
      │                                     5. map sub → Keycloak user        │
      │                                     6. entitlement + Kueue check      │
      │                                     7. create LabSession CR ─────────►│
      │  ◄──────── 8. 302 to console URL (new window) ────────────────────────│
      │                                                        9. TTL/grade ──┤
      │  ◄──── 10. AGS: POST {lineitem}/scores (client-credentials JWT) ──────│
```

Implementation rules:

1. **Use an established LTI 1.3 library** (e.g., PyLTI1p3 or the IMS-certified PHP/Java libraries). Do not hand-roll JWT/JWKS validation.
2. **Launch in a new window/tab** (`target=new window`): consoles/terminals are poor inside iframes and third-party-cookie rules break iframe launches.
3. **Deep Linking** lets faculty pick a lab from the catalogue inside Moodle; the returned `LtiResourceLink` carries `custom.template`, `custom.version`, and a `lineItem` (max score, tag).
4. **AGS** posts scores (and optionally comments) on completion; **NRPS** reads the roster to size warm pools for the timetable (innovation #19).
5. **Dynamic Registration** for onboarding new institutions (no manual key exchange); per-tenant `client_id`/`deployment_id`; keys rotated through OpenBao.
6. **Conformance:** run the IMS conformance suite/certification before the second institution.

### 10.4 Lab-as-a-Service API (thin wrapper over the Orchestrator)

```yaml
openapi: 3.0.3
info: {title: i3 Lab-as-a-Service API, version: 1.0.0}
security: [{oidc: []}]                     # Keycloak bearer token with tenant + entitlements claims
paths:
  /v1/templates:
    get: {summary: List templates visible to the tenant, parameters: [{name: vendor, in: query}, {name: track, in: query}]}
  /v1/sessions:
    post:
      summary: Launch a lab (async). Returns 202 with a session id and phase (Queued|Provisioning|Running)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [template]
              properties:
                template: {type: string}
                version:  {type: string}
                ttl:      {type: string, example: 4h}
                context:  {type: object, description: LTI/course context (context_id, resource_link_id, lineitem)}
  /v1/sessions/{id}:
    get:    {summary: Status, endpoints, expiresAt, queue position}
    delete: {summary: End and tear down}
  /v1/sessions/{id}:extend: {post: {summary: Extend within policy (maxExtensions)}}
  /v1/sessions/{id}:grade:  {post: {summary: Run grader now; returns per-task result}}
  /v1/usage:
    get: {summary: Session-hours and gradings by tenant/project/date}
components:
  securitySchemes: {oidc: {type: openIdConnect, openIdConnectUrl: https://sso.i3technologies.co.ke/auth/realms/i3/.well-known/openid-configuration}}
```

All calls carry `Idempotency-Key`; errors are structured JSON with a stable `code` (`QUEUED`, `ENTITLEMENT_EXCEEDED`, `LICENCE_BLOCKED`, `BUDGET_EXCEEDED`, `TEMPLATE_RETIRED`).

### 10.5 Authoring studio ("i3 Author") and the validation pipeline

| Component | Choice | Role |
|---|---|---|
| Interactive content | H5P (built into recent Moodle) | Quizzes, interactive video, branching, drag-drop; xAPI native |
| Story/branching modules | Adapt Learning | Scenario modules (incident response, client presentation) exported as SCORM/xAPI |
| **Lab Scenario Builder** | `i3lab` CLI + YAML (`lab.yaml`, `checks.yaml`) | Git-native lab authoring; compiles to `LabTemplate` |
| **AI Author Copilot** | LiteLLM `qwen-heavy` / `coder` + RAG | Drafts quiz banks, scenario outlines, lab skeletons from faculty source material |
| Course package | `course.yaml` manifest | Binds Moodle backup (.mbz), H5P/Adapt packages, LabTemplates, RAG corpus manifest, rubrics; versioned and signed |

**The `i3lab` CLI** (`init`, `validate`, `build`, `test`, `publish`) is the same tool faculty, i3's curriculum team and the AI copilot use — one path to production.

**Validation gates for AI-drafted content (innovation #9)**

| Gate | Check | Blocks publication if… |
|---|---|---|
| G1 Grounding | Every generated item cites source chunk IDs; entailment check against the chunk | Unsupported claims |
| G2 Format | JSON-schema validation of quiz/scenario/lab drafts (stem, options, key, rationale, difficulty, source) | Schema violation |
| G3 **Lab dry-run** | Deploy the draft template in a sandbox namespace | Deploy fails |
| G4 **Grader self-test** | Run the **reference solution** → must score 100; run a **null solution** → must score 0; run a **partial solution** → proportional score | Grader is wrong or bypassable |
| G5 Similarity/IP | Overlap check against source and known third-party material | Above threshold |
| G6 Human approval | Named faculty member approves; provenance recorded ("AI-assisted draft, model+version, approved by X, date") | No approver |

```
Faculty uploads syllabus/chapter/slides ─► ingestion + course corpus (Qdrant) ─► Copilot (structured outputs)
   ─► draft quiz bank · scenario outline · lab skeleton (lab.yaml + checks.yaml + reference solution)
   ─► CI gates G1–G5 ─► i3 Author review UI (diff view, edit) ─► G6 approve ─► course package v1.x
   ─► publish: Moodle course + LabTemplates + H5P + corpus ─► LRS "authored/published" statements
```

**Interoperability:** SCORM 1.2/2004, xAPI, Common Cartridge/LTI resource export so a course runs inside a university's existing Canvas/Blackboard during transition (S9 §4.3, S9 §13).

### 10.6 AI Tutor and Faculty Copilot

**Tutor modes:** *Explain* · *Hint (Socratic)* · *Code review* · *Quiz me* · *Study plan*. Faculty set policy per course/activity: e.g., "no full solutions for graded labs until the due date; hints only".

```
System prompt skeleton (per course, generated from policy):
  Role: teaching assistant for {course}. Ground answers in retrieved course material; cite sources.
  If retrieval score is low, say so and suggest where to look — do not guess.
  Graded activity {activity_id} is OPEN: give hints in increasing specificity (Level 1→3). Never provide the
  final answer, complete code, or the hidden grading checks. Offer to explain the underlying concept instead.
  Language: reply in the student's language (English/Swahili/code-switching).
Context injected: current lab task text, last grader feedback (student-visible only), course glossary.
```

Privacy and integrity: students see what is stored about them; faculty receive **aggregate themes** ("30% of questions on Kubernetes networking") — individual transcripts only under a documented academic-integrity process; usage caps per student; per-course **model card**; tutor pedagogy suite in the eval gate (§7.5).

**Faculty Copilot:** drafts rubric-based feedback on submissions (advisory, human-approved), weekly cohort summaries for department heads, and question-bank suggestions. **At-risk signals** (late starts, repeated failures, inactivity) are **advisory only**, explainable, bias-tested, opt-in per institution, and never used for automated academic-standing decisions (S9 §6.1).

### 10.7 LRS, analytics and credentials

| Function | Design |
|---|---|
| Event capture | Moodle `logstore_xapi`, H5P xAPI, lab xAPI (below), BBB attendance, PeerTube watch events, AI Tutor engagement (aggregate) |
| LRS | **Learning Locker** (as S9), or evaluate a Postgres-backed SQL LRS (simpler ops if the team standardises on Postgres); decide in the H2 design spike |
| Relay | `usage.events`/`lms.events` bus topics → xAPI relay → LRS; the same events feed billing and dashboards |
| Dashboards | Faculty: progress, lab completion, grade distribution; Dept: cohort summaries; Institution: usage/ROI; Student: personal progress and badges |

```json
{
  "actor": {"account": {"homePage": "https://sso.i3technologies.co.ke", "name": "kc|4b1e…"}},
  "verb": {"id": "http://adlnet.gov/expapi/verbs/completed", "display": {"en-US": "completed"}},
  "object": {"id": "https://labs.i3technologies.co.ke/templates/sec-fortigate-basics",
             "definition": {"name": {"en-US": "FortiGate Fundamentals"}}},
  "result": {"score": {"scaled": 0.8, "raw": 80, "max": 100}, "duration": "PT42M", "completion": true},
  "context": {"contextActivities": {"parent": [{"id": "https://moodle.usiu…/course/view.php?id=402"}]},
              "extensions": {"https://i3.co.ke/xapi/ext/tenant": "usiu", "https://i3.co.ke/xapi/ext/attempt": 2}}
}
```

**Badges (innovation #21):** a rules engine watches LRS events (e.g., "Lab track completed + score ≥ 70%") and issues **Open Badges 3.0** credentials (verifiable credentials signed with a tenant/i3 key held in OpenBao; public verification endpoint; "add to LinkedIn" link). Official **IBM/Red Hat** badges are issued only through those vendors' own badging channels after the corresponding exam/course — i3-issued badges must be clearly labelled as i3/institution micro-credentials to avoid misrepresentation (F-13).

**Talent API (S9 §8 → contract):** opt-in **consent record** per student; anonymised-by-default profile (competencies, badges, lab outcomes, capstone summary); employer access through i3 Talent Cloud; revocable; audit trail of every employer view. Integrates with **EvalOS** results (§11.1).

### 10.8 OTT and virtual delivery (staged)

| Stage | Scope | Notes |
|---|---|---|
| **O1 (with P0)** | **BigBlueButton** for live classes/workshops via `mod_bigbluebuttonbn` | **[CHANGE]** BBB is not Kubernetes-native (WebRTC, UDP media, TURN). Run BBB on **dedicated VMs in N1** and put **Scalelite** in front for multi-server load balancing; do not force it into OpenShift. Size by concurrent video users, not enrolment; load-test before large classes |
| **O2** | **PeerTube** VOD (federation disabled), object storage in Nairobi, HLS ladder 240p→1080p **plus audio-only (~64 kbps) + slides-sync mode**, remote transcoding runners (GPU/NVENC off-peak) | BBB recordings auto-publish to PeerTube via API; Faster-Whisper auto-captions (English/Swahili) attached |
| **O3** | **OvenMediaEngine** (low-latency WebRTC/LL-HLS) for large broadcasts, guest speakers, roadshows | Only when a customer needs > BBB's interactive scale |
| **Edge** | **Campus cache appliance** (Nginx/Varnish or PeerTube redundancy) on the university network + Nairobi origin | Campus bandwidth is cheaper than mobile data; sync overnight; DPA-aligned data flow |
| **Offline** | PWA + downloadable **offline packs** (audio + slides + transcript + lab instructions) | Data-saver default for mobile |

Accessibility: captions on all VOD, transcripts, keyboard navigation, WCAG 2.2 AA target for i3 plugins and theme; human review of captions for accreditation-critical content.

### 10.9 Anchor pilot execution plan (USIU-Africa)

S10 (March 2026) committed to a free first-semester pilot; S9 recommends using it as the live P0. Status of the pilot should be confirmed; the steps below apply either way (migrate ad-hoc portal links to a proper LMS-integrated flow).

| Weeks | Milestone | Exit criterion |
|---|---|---|
| 1–2 | Confirm hosting/residency position for USIU data (Frankfurt vs N1); DPA/data-processing agreement; DPIA for AI Tutor | Signed DPA; residency statement corrected in collateral |
| 2–5 | `edu-usiu` Moodle instance; Keycloak realm brokered to USIU IdP; roster provisioning | 100% of pilot roster can log in via USIU SSO |
| 4–8 | LTI 1.3 to Smart Labs (year-1 and year-2 templates first) and Percipio (verify LTI/SCORM/xAPI support with Skillsoft); AGS grade passback | Lab launched from Moodle returns a grade (E-1, E-2) |
| 6–10 | BBB live for the Agentic AI faculty workshop; LRS + first dashboards | Workshop delivered on i3 stack |
| 8–12 | AI Tutor (RAG-grounded, one course) beta announced **during** the pilot; concurrency and load test at expected peak | Tutor pedagogy suite passes; no cross-tenant retrieval |
| 12 | Pilot evaluation report (usage, grades, at-risk signals, satisfaction, cost per active student) | Conversion decision to USD 150/student/year |

**Unit-economics check before conversion:** report *actual* session-hours, GPU-minutes and tokens per active student; compare with the USD 150 price point and the cost model in §8.2/§13.3.

---

## 11. Cross-Product Integration and the Sovereign Appliance

### 11.1 EvalOS integration — proctored practical exams

EvalOS becomes the exam front door for practical assessment: it calls the Lab API to create `LabSession`s with `mode: exam` — AI Tutor disabled, egress none, per-session randomised parameters, fixed time window, session recording, secure launch (browser lockdown or proctoring per SKU), and grader results fed back to EvalOS and (with consent) to the Talent Cloud. This closes the gap between S7's "Exam-as-a-Service" and its lab fabric.

### 11.2 Talent Cloud and Forward Deployed Engineers

The skills graph (competencies, badges, lab outcomes, EvalOS scores, capstone summaries) is a read model built from LRS + EvalOS + Bootcamp data, exposed through the Talent API. FDEs sourced from the Bootcamp are matched to client engagements using the same graph; recruitment/headhunting products consume it under explicit consent and audit.

### 11.3 Bootcamp and corporate cohorts

Cohort calendars feed warm pools (innovation #19); corporate cohort pricing (e.g., KES 350,000/cohort, S7) is a SKU on the same meter; hackathons use time-boxed T0 tenants with GPU-burst quotas and automatic teardown.

### 11.4 Engage and AfroERP

Engage delivers WhatsApp/SMS lab reminders, at-risk nudges (opt-in) and invoice/payment links; AfroERP is the system of record for invoices, eTIMS and receivables (§8.4).

### 11.5 Sovereign AI Appliance packaging (S3 Service Line 1)

An **umbrella Helm chart `i3-sovereign`** delivers the same stack in three modes:

| Mode | Where | Use |
|---|---|---|
| Hosted-dedicated | N1 (Nairobi) | Banks/SACCOs who accept i3 as hosting provider |
| Customer DC | Customer OpenShift (x86 + GPU) | Data must not leave the institution |
| Air-gapped | Customer DC, no internet | Central bank–grade environments, MDAs |

**Bundle contents:** Keycloak, LiteLLM, vLLM/Ollama, Qdrant, RAG Studio, Sage, guardrails/PII, Langfuse, Prometheus/Grafana/Loki, OpenBao, Velero, audit shipper, admin console.

**Packaging discipline [NEW]:**
- **Signed artefacts:** every image cosign-signed with SBOM; **`oc-mirror`** bundles for disconnected registries; offline model pack with checksums; offline documentation.
- **Update channel:** monthly signed release tarball + release notes + rollback plan; customer chooses the window.
- **Conformance suite:** the appliance ships with an automated acceptance run (latency, RAG groundedness, PII recall, residency check, backup/restore) — the customer's sign-off artefact.
- **Adapters:** Finacle/T24 via read-only views or vendor APIs first; write actions only via approval workflows (§7.7).
- **Model licences:** verify each model's licence permits commercial appliance distribution (e.g., Qwen 2.5 7B/14B and Granite are permissive; other sizes/variants have different terms — check per model and version).
- **Architecture note:** the LLM stack targets **x86 + NVIDIA/AMD GPUs**; keep IBM Power for AIX/IBM i labs and customers who explicitly want watsonx on Power — ppc64le availability of the open-source stack cannot be assumed.
- **Commercials (S3):** setup + annual SLA; SLA tied to measurable SLOs from §5.5.

---

## 12. Innovation Register (ranked build order)

Effort: S ≤ 3 person-weeks · M 3–8 · L > 8. Horizons: **H1** weeks 1–16 · **H2** weeks 17–30 · **H3** week 31+ (see §13).

| # | Innovation | Origin | Layer | Value | Effort | Horizon | Success KPI |
|---|---|---|---|---|---|---|---|
| 1 | **Lab Orchestrator (CRDs, TTL finalizers)** replaces Ansible + `at` | S4 idea, **[CHANGE]** | Labs | Reliability, no orphans, one API for all products | M | H1 | 0 orphaned PVC/VM after 1,000 teardowns |
| 2 | **Warm pools** (pre-pull, pre-clone, pre-boot) | NEW | Labs | Launch < 30 s | M | H1 | p50 launch < 30 s on top-8 templates |
| 3 | **State-based grading engine** (out-of-band graders) | NEW | Labs/Edu | Auto-grading at scale; LTI + xAPI | M | H1 | ≥ 60% of templates auto-graded |
| 4 | **Kueue admission control** + tenant quotas | NEW | Labs/AI | Concurrency becomes a SKU; fair share | S–M | H1 | Reserved-concurrency SLA met 99% |
| 5 | **vLLM GPU tier + KEDA on real metrics** | S8 B1, **[CHANGE]** | AI | p50 first-token < 3 s; higher concurrency per GPU | M | H1 | B1-1…B1-5 pass |
| 6 | **Unified `UsageEvent` meter → ERPNext + eTIMS** | S8 B2, **[CHANGE]** | Billing | Zero-touch invoicing, one meter for all products | M | H1–H2 | Month-end with zero manual edits |
| 7 | **Residency attestation reports** | NEW | Compliance | Evidence, not promises | S | H2 (needs N1) | Signed monthly report per resident tenant |
| 8 | **Clabernetes + NetBox + Batfish GitOps pipeline** | S1, **[CHANGE]** | Network labs | Reproducible multi-vendor fabrics, POC-as-product | M | H2 | 50-node fabric < 5 min |
| 9 | **AI-authored courses/labs behind CI gates (G1–G6)** | S9 + NEW gates | Edu | Authoring speed with quality control | L | H2 | Draft-to-publish time −50%, zero grader bypasses |
| 10 | **Sovereign Appliance bundle** (signed, air-gappable) | S3 + NEW | Enterprise AI | Bank/MDA revenue line | L | H2–H3 | First T2 acceptance run passed |
| 11 | **Licence ledger + admission gate** | NEW | Compliance | Converts F-01 into a control; due-diligence asset | S | **H1 (first)** | 100% deployed images ledgered |
| 12 | **Cloud sandbox vending** (AWS/Azure/GCP with budgets) | NEW | Labs | Certification-grade cloud labs | M | H1 | Sandbox spend cap never exceeded |
| 13 | **Hash-chained WORM audit + crypto-shredding** | S8 B4 + NEW | Security | 7-year audit without retaining personal content | M | H1–H2 | Chain verifier green; erasure test passes |
| 14 | **Per-tenant LoRA serving** on shared base models | NEW | AI | Bespoke models at low marginal cost | M | H2 | Adapter hot-load < 60 s; isolation test |
| 15 | **Tutor pedagogy guardrails + eval suite** | S9 + NEW | Edu/AI | Academic integrity, accreditation confidence | M | H2 | ≥ 90% correct pedagogical behaviours |
| 16 | **Parameterised, randomised labs** | NEW | Labs | Defeats answer sharing | S | H1 | Per-session variance on all graded labs |
| 17 | **Credit burn controller** | NEW | FinOps | No credit lapse or surprise overspend | S | H1 | Forecast error < 10% |
| 18 | **M-Pesa prepaid wallet** (Daraja STK) | NEW | Billing | Frictionless T0 revenue | S–M | H2 | Wallet top-up → key budget update < 60 s |
| 19 | **Timetable-driven capacity** (NRPS/calendar → pool sizing) | NEW | Labs | Right-sized warm capacity, lower cost | S | H2 | Idle warm capacity < 15% |
| 20 | **xAPI learning event bus + advisory at-risk signals** | S9 + NEW | Analytics | Real-time dashboards, early support | M | H2 | LRS lag p95 < 60 s |
| 21 | **Open Badges 3.0 auto-issuance** | S9 | Credentials | Verifiable, portable micro-credentials | S | H2 | Badge issued < 5 min after criteria met |
| 22 | **EvalOS proctored lab exams + Talent API** | S9/S10 + NEW | Talent | Assessment revenue; placement pipeline | M | H2 | First proctored practical exam delivered |
| 23 | **Low-bandwidth OTT**: audio-first, campus cache, offline packs | S9 + NEW | Media | Access for data-constrained learners | M | H3 | ≥ 70% of sessions served at ≤ 360p/audio without stalls |
| 24 | **Swahili/Sheng eval suite + data flywheel** | S8 B5 + NEW | AI | Genuine local-language differentiator | M (ongoing) | H1→ | Published scores improving release over release |
| 25 | **Agent platform with MCP tool gateway + HITL** | S3 + NEW | AI | Safe agentic automation for banks/logistics | L | H2 | Agent eval suite passes; zero unapproved writes |
| 26 | **Telemetry-first network assurance and grading** (gNMI) | S1 + NEW | Network labs | Modern ops skills; robust grading | M | H2 | Dashboard required for every network lab |
| 27 | **Faculty AI teaching assistant** (rubric drafts, cohort summaries) | S9 | Edu | Faculty time saved | M | H2 | Faculty-rated usefulness ≥ 4/5 |
| 28 | **Regional Alliance federation** (shared infra, signed course exchange) | S9/S10 | Platform | Second and third university on same tenancy model | L | H3 | 2nd institution onboarded by PR only |

---
## 13. Delivery Plan, Team and Capacity Model

### 13.1 Workstreams

| WS | Name | Scope | Absorbs |
|---|---|---|---|
| A | Foundation & Security | Landing zone, CIDR/TGW, secrets, policy, observability, backup | S6, S8 §7 |
| B | Lab Orchestrator & Fabric | CRDs, warm pools, Kueue, KubeVirt tier, grading, isolation, sandbox vending | S4, S7, S10 |
| C | AI Platform | vLLM/GPU, LiteLLM, RAG, guardrails, eval/release gate, agents, voice | S3, S8 B1/B4/B5 |
| D | Metering & Billing | UsageEvent, price book, ERPNext/eTIMS, wallet, FinOps | S8 B2 |
| E | Nairobi Region | N1 procurement, cluster, residency, DR | S8 B3 |
| F | EduBridge | Moodle, LTI, Connector plugins, authoring, LRS, badges, OTT | S9, S10 |
| G | Network & Vendor Labs | Clabernetes pipeline, NetBox, Batfish, CML/EVE-NG tier, vendor waves | S1, S4 |
| H | Compliance & Licensing | Licence ledger, vendor confirmations, DPIAs, ODPC, ISO/SOC roadmap | new |

### 13.2 Horizons and milestones

**H0 — Stop-the-line (weeks 0–2)** — cheap, high-leverage, no new infrastructure

- Decisions D1–D8 (§16). Correct collateral (capacity, "Kenya Region", badge wording).
- Licence inventory of every deployed image → ledger v0 (WS-H). Mark unresolved images `internal` only.
- Re-baseline the live estate into Git (`oc get nodes/ns/…`), CIDR plan, repo skeleton, secret scanner in CI.
- Start the GPU bake-off; open procurement for N1 and (if pursued) bare-metal pool.

**H1 — Commercial-grade core (weeks 1–16)** — aligns with the P0 90-day plan and extends it

| Weeks | WS-A/E/H | WS-B/G | WS-C | WS-D | WS-F |
|---|---|---|---|---|---|
| 1–4 | OpenBao + ESO; master-key retirement notice; Kyverno baseline; corrected TGW + private LiteLLM endpoint; PMaaS isolation plan | Orchestrator MVP (kopf); 8 pilot templates; image pre-pull DaemonSet | `ollama-gpu`/vLLM deploy; routing + fallback; latency baseline (B1) | Billing schema; virtual keys per project; usage emitter | `edu-usiu` Moodle; Keycloak realm + IdP brokering |
| 5–8 | Observability + SLO dashboards; audit pipeline v1 | Kueue tenant queues; state-based grader v1; parameterised labs; egress firewall on cyber labs | KEDA on vLLM metrics; PII detect mode; eval harness + Swahili v1 | Nightly reconciliation; quotas/alerts; credit burn controller | LTI gateway v1; Lab API; AGS passback |
| 9–12 | **N1 phase A stood up**; residency verification; Nairobi cutover for resident pilot tenants | Cloud sandbox vending v1; licence admission gate enforcing | Release gate enforced; model cards; RAG Studio on Qdrant | ERPNext draft-invoice pilot (2 tenants) | BBB (Scalelite) for the workshop; LRS + first dashboards |
| 13–16 | DR drill; hash-chained audit verifier; pen-test #1 | Load tests → **published concurrency tiers** | Tutor beta (one course) | Month-end with zero manual edits | Pilot evaluation report |

**H1 exit criteria:** all acceptance tests in §14 marked *H1* pass in staging; two paying pilot tenants on metered keys; concurrency tier table published from measured data; licence ledger covers 100% of deployed images; Nairobi residency verified for the resident pilot tenant.

**H2 — Productize (weeks 17–30):** warm-pool levels L2/L3; Clabernetes + NetBox + Batfish pipeline; W2 vendor licences (Cisco, Fortinet, Palo Alto, Juniper, Aruba) cleared in writing; AI Author Copilot with gates G1–G6; Open Badges 3.0 + Talent API + EvalOS proctored exams; per-tenant LoRA serving; agent platform with tool gateway; M-Pesa wallet; sovereign appliance v0.9 conformance run; N1 phase B; ISO 27001 gap assessment.

**H3 — Scale (week 31+):** PeerTube VOD + OME + campus cache + offline packs; Regional Alliance (second/third institution by PR); appliance GA; SOC 2 Type I; W3 vendors on demand.

### 13.3 Concurrency tiers (replaces "2,500 concurrent") and node budget

Blended session profile from §3.2: **≈0.6 vCPU requested and ≈1.45 GiB per concurrent session**. Node = 16 vCPU/64 GiB class, ≈56 GiB allocatable, ≈USD 0.77/hour (indicative — validate), scheduled 12 h × 22 days.

| Tier | Reserved concurrent sessions | RAM at peak | Nodes at peak | Indicative compute/month* | Typical buyer |
|---|---|---|---|---|---|
| Starter | 50 | ≈73 GiB | 2 | ≈ USD 0.4k | Bootcamp cohort, SME POC |
| Standard | 150 | ≈218 GiB | 4 | ≈ USD 0.8k | Department (e.g., 1,000 enrolled students) |
| Plus | 400 | ≈580 GiB | 11 | ≈ USD 2.2k | Faculty/university, corporate academy |
| Enterprise | 1,000+ | ≈1.45 TiB | 26+ | ≈ USD 5.3k+ (dedicated pool) | Regional alliance / national programme |

\*Business-hour scheduled worker compute only; excludes GPU, storage, egress, baseline nodes, bare-metal V tier, and support. VM-heavy or fabric-heavy mixes shift the numbers up; **replace with measured values after the L-series load tests.** Sell the tier as *reserved concurrency + included session-hours*, with overage per session-hour.

### 13.4 Team (indicative, ~13 FTE at steady state)

| Role | FTE | Notes |
|---|---|---|
| Platform/SRE lead + engineers | 3 | WS-A/E; same team runs AI Lab and EduBridge (S9 §9) |
| Lab orchestration engineers (Go/Python, K8s operators) | 2 | WS-B |
| AI/ML: inference + RAG/eval | 2 | WS-C; ML reviewer part-time for Swahili quality |
| Billing/data engineer | 1 | WS-D |
| Moodle/PHP + LTI engineers | 2 | WS-F |
| Network/vendor lab engineer(s) | 1–2 | WS-G; leverage existing certified engineers |
| Security & compliance lead | 1 | + external counsel/DPO support |
| Curriculum/content leads | 2 | Course packages, lab authoring |
| Product/programme manager | 1 | Roadmap, pilots, customer success |

Estimates from S8 (B1 2 eng × 3–4 wks; B2 1–2 × 2–3; B3 2 × 4–6 + procurement; B4 1–2 × 2–3; B5 1 × 3) remain valid and are subsumed in H1; the orchestrator, grading, LTI and licence work are additive.

### 13.5 Rebuilding the financial model (C7, C8)

Before any board/investor circulation, rebuild bottom-up from drivers:

| Driver | Source of truth |
|---|---|
| Seats × price (training) | CRM + price book |
| Reserved concurrency × price (LaaS/EduBridge) | §13.3 tiers |
| Tokens, GPU-minutes, lab-hours × unit price | Meter (§8) |
| Implementation projects = qualified pipeline × win rate × ACV | CRM |
| Managed-service contracts × retainer | Contracts |
| Costs: cloud (post-credit), licences (real training-partner costs), people, sales, compliance | Ledger |

Sanity checks on S7's headline: 40 implementation engagements + 26 active LaaS clients + 10 managed contracts in Year 1 imply roughly 160 qualified opportunities at a 25% win rate — check against actual pipeline. Personnel at KES 25M for 10–20 staff is KES 1.25–2.5M per head fully loaded — tight for senior AI/platform engineers. **Do not double count** application revenue (S7 §7, KES 84.7M Year 1) and services revenue (S7 §8). Include sensitivities: credits ending, KES/USD ±15%, GPU price, win rate ±10 pts, utilisation ±20 pts.

---

## 14. Acceptance Criteria and Test Plan

Convention (from S8): each test has an ID and a numeric pass threshold; CI runs them as gates on `main` where automatable. **B1-1…B5-4 from S8 are retained unchanged**; the tables below add the tests this guide introduces. *Phase* = the horizon by which the test must pass.

### 14.1 Platform, security and residency

| ID | Test | Pass threshold | Phase |
|---|---|---|---|
| X-1 | Cross-cluster access | A2 workloads reach LiteLLM via private endpoint; no dependency on `svc.cluster.local` across clusters | H1 |
| S-1 | Secret hygiene | Secret scan finds 0 occurrences of `sk-i3-internal` or any live key in Git/docs/notebooks/env dumps | H1 |
| S-2 | Cross-tenant RAG | 200 adversarial queries from tenant A retrieve 0 chunks from tenant B | H1 |
| S-3 | Penetration test | 0 critical, 0 high unresolved at sign-off | H1/H2 |
| S-4 | Backup/restore | Postgres restore to point in time within RTO 4 h; Moodle restore within RTO 4 h | H1 |
| S-5 | Residency attestation | Signed report shows 100% resident-class objects in N1 and 0 non-KE egress flows from resident namespaces | H1 (pilot) |
| S-6 | Audit chain | Verifier detects a deliberately altered batch within 24 h; WORM prevents delete/overwrite | H1 |
| S-7 | Crypto-shredding | After key destruction, content for a test tenant is unrecoverable; audit metadata intact | H2 |
| S-8 | Break-glass | Master-key/cluster-admin use requires two approvers and produces an audit event + tenant notification | H1 |

### 14.2 Lab fabric and network labs

| ID | Test | Pass threshold | Phase |
|---|---|---|---|
| L-1 | Launch time | Warm-pool templates p50 < 30 s, p95 < 60 s; cold p95 < 120 s | H1 |
| L-2 | Concurrency by tier | Each published tier sustained at reserved concurrency for 60 min with launch p95 within L-1 and 0 evictions | H1 |
| L-3 | Teardown hygiene | 1,000 create/delete cycles → 0 orphan namespaces/PVCs/VMs/secrets | H1 |
| L-4 | **Licence gate (negative)** | A template referencing an `nfr`/`eval` image is rejected for a tenant in `laas`/`training` mode | H1 |
| L-5 | Egress control | From a Kali lab: connection to public internet blocked; in-namespace targets reachable | H1 |
| L-6 | **Grader self-test** | Reference solution = 100; null solution = 0; partial solution proportional (± 5 pts) | H1 |
| L-7 | Parameterisation | Two sessions of the same template receive different parameters; grader accepts each session's own values only | H1 |
| L-8 | Admission | Beyond reserved concurrency, sessions queue with ETA; borrowing from cohort works; no over-commit failures | H1 |
| L-9 | Cloud sandbox | Sandbox account auto-destroyed at TTL; spend cap enforced in a runaway test | H1 |
| N-1 | Fabric boot | 50-node container fabric ready < 5 min | H2 |
| N-2 | Batfish gate | A deliberately broken ACL/BGP change is blocked by CI | H2 |
| N-3 | Telemetry | gNMI dashboard shows interface/BGP state for every node in the reference lab | H2 |
| N-4 | Auto-destroy | Topology and cloud resources destroyed at TTL; cost tag report matches | H2 |

### 14.3 AI platform

| ID | Test | Pass threshold | Phase |
|---|---|---|---|
| A-1 | vLLM concurrency | 32 parallel `qwen-heavy` requests: 0 5xx, p95 total latency within agreed budget | H1 |
| A-2 | Autoscale trigger | Synthetic queue > threshold scales replicas within 3 min; scale-in after cooldown | H1 |
| A-3 | Fallback signalling | On GPU failure, `qwen-heavy-cpu` serves within 60 s and `x-i3-degraded` header is set | H1 |
| A-4 | RAG groundedness | ≥ 90% of answers on the reference corpus cite correct sources; unanswerable questions refused ≥ 95% | H1 |
| A-5 | Erasure | Deleting `doc_id` removes chunks, embeddings and cached answers; verified by query | H1 |
| A-6 | LoRA isolation | Adapter for tenant A not usable with tenant B keys; hot-load < 60 s | H2 |
| A-7 | Agent safety | Prompt-injection suite: 0 unapproved write actions; step/cost limits enforced | H2 |
| A-8 | Tutor pedagogy | ≥ 90% of graded-activity scenarios receive hints, not answers | H2 |

### 14.4 Metering and billing

| ID | Test | Pass threshold | Phase |
|---|---|---|---|
| M-1 | Reconciliation | Callback vs `LiteLLM_SpendLogs` drift ≤ 0.5% per day | H1 |
| M-2 | Lab metering | Lab-hours per tenant within ±5% of orchestrator ground truth | H1 |
| M-3 | Invoice | Month-end draft invoices in ERPNext for all active tenants with 0 manual edits; eTIMS submission succeeds | H1–H2 |
| M-4 | Credit controller | Forecast error < 10% over 4 weeks; simulated overspend triggers pool shrink | H1 |
| M-5 | Wallet | STK Push → wallet credit → key budget increase < 60 s; idempotent on duplicate callbacks | H2 |

### 14.5 EduBridge

| ID | Test | Pass threshold | Phase |
|---|---|---|---|
| E-1 | LTI launch | 100 consecutive launches from Moodle succeed (≥ 99.5% over soak) | H1 |
| E-2 | Grade passback | AGS score appears in Moodle gradebook < 60 s after grading | H1 |
| E-3 | Deprovisioning | Removing a user from the SIS/IdP group removes access to Moodle, labs and AI within 5 min | H1 |
| E-4 | LRS ingest | xAPI lag p95 < 60 s at expected event rate | H2 |
| E-5 | BBB load | 100 concurrent users join a room, ≥ 98% successful joins; recording published to VOD < 30 min | H1/H2 |
| E-6 | Portability | An exported course package imports into an external LMS (SCORM/Common Cartridge) with activities intact | H2 |
| E-7 | Badge issuance | Criteria met → OB 3.0 credential issued and verifiable < 5 min | H2 |
| E-8 | Accessibility | Automated + manual WCAG 2.2 AA audit of i3 plugins/theme: 0 blocking issues | H2 |

### 14.6 Runbooks (one per operational risk)

GPU failover · budget-exceeded incident · region failover drill (RTO 4 h) · audit export request · master-key/break-glass · licence dispute or vendor audit · Moodle upgrade · LTI key rotation · lab-abuse takedown · DSAR/erasure · PII leak (P1) · N1 hardware failure · credit exhaustion.

---

## 15. Risk Register

| # | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Vendor licence non-compliance (NFR/eval used for paid delivery) | High | High | Licence ledger + admission gate; written confirmations; `internal`-only until cleared | Compliance lead |
| R2 | Capacity/credit gap vs promised concurrency | High | High | Concurrency tiers; load tests; credit burn controller; post-credit model | Platform lead |
| R3 | Residency claim misstatement | Medium | High | Correct collateral now; N1; attestation reports | CEO / compliance |
| R4 | IBM Cloud support for OpenShift Virtualization/bare metal differs from assumption | Medium | High | Written IBM confirmation before purchase; fallback to N1 bare metal | Platform lead |
| R5 | GPU supply/lead time in-country | Medium | Medium | Bake-off NVIDIA vs ROCm; ship metering/tenancy first; cloud GPU bridge | Ops |
| R6 | N1 procurement/colo delay | Medium | High | Start in week 0; compact cluster; Option A as fallback per S8 | Ops |
| R7 | Skills gap (operators, KubeVirt, LTI, vLLM) | High | Medium | Red Hat training (DO280/DO316), pairing, runbooks, start with tier C | Team leads |
| R8 | Swahili/Sheng quality below claim | Medium | Medium | Eval gate; publish scores honestly; data flywheel; human review | AI lead |
| R9 | Moodle upgrade/plugin breakage mid-term | Medium | Medium | Pin LTS; test matrix; upgrade only between terms | Moodle lead |
| R10 | Security incident (lab escape, key leak, tenant leakage) | Low–Med | High | §9.2 controls; pen tests; break-glass audit; incident runbook | Security lead |
| R11 | Data-protection complaint (student data, AI, PMaaS) | Medium | High | DPIAs, ODPC registration, erasure tooling, PMaaS separation | DPO/counsel |
| R12 | Scope sprawl (45 vendors, 5 products) | High | Medium | Feasibility classes and waves; demand-gated backlog | Product |
| R13 | Model/tool licence changes (open-weights, Open WebUI, TTS) | Medium | Medium | Licence check in release gate; alternates identified | AI lead |
| R14 | Customer concentration on the anchor pilot | Medium | Medium | Parallel second-institution pipeline; productised onboarding by PR | CEO |
| R15 | Key-person dependency | Medium | High | Runbooks, GitOps, pairing, documented decisions | Team leads |
| R16 | Vendor programme relationships damaged by an audit finding | Low | High | R1 mitigations; proactive disclosure and remediation plan | CEO |

---

## 16. Decisions Required and First-14-Day Checklist

### 16.1 Decisions (with recommended answer)

| ID | Decision | Recommendation |
|---|---|---|
| D1 | What is the true hosting/residency position, and what do we say to customers now? | Treat Frankfurt as current; get IBM's written position on any Kenyan region; correct collateral; commit residency only via N1 or a customer-hosted appliance |
| D2 | Where does the KubeVirt (V) tier live? | N1 bare metal if IBM bare-metal cost exceeds credits; otherwise a small dedicated IBM bare-metal pool after IBM confirms support |
| D3 | Licence route per priority vendor | Cisco: CML Enterprise/learning-partner route; Fortinet/Palo Alto/Juniper/Red Hat: education/training-partner programmes; obtain written confirmation before W2 |
| D4 | PMaaS isolation | Separate site (A-PM) before any bank/university/MDA go-live |
| D5 | GPU hardware and location | Bake-off 2 weeks; L4/L40S-class for inference in N1 + A3; A100 burst for fine-tuning |
| D6 | LRS | Spike in H2: Learning Locker vs SQL LRS; decide by ops fit and xAPI conformance |
| D7 | Price book and FX policy | KES pricing, quarterly FX indexation, concurrency-based SKUs |
| D8 | Collateral corrections | Remove "2,500 concurrent" and "Kenya Region" unless substantiated; correct badge wording |
| D9 | Certification roadmap | ISO 27001 gap assessment in H2; SOC 2 Type I in H3 |
| D10 | OpenShift edition for N1/T2 | Supported OCP (not OKD) for regulated tenants |
| D11 | Anchor-pilot hosting (USIU) | First resident tenant in N1 if timeline allows; else documented cross-border basis with counsel |
| D12 | Organisation | One platform team operating AI Lab, Smart Labs and EduBridge; product owners per front door |

### 16.2 First 14 days

1. Export live cluster inventory to Git; agree CIDR plan; create the monorepo skeleton (§5.2).
2. Licence inventory of all deployed images; ledger v0; mark unresolved images `internal`.
3. Send IBM the residency and OpenShift-Virtualization/bare-metal questions in writing; send vendor training-partner enquiries (Cisco, Fortinet, Palo Alto, Juniper, Red Hat).
4. Rotate/retire the literal master key path: introduce per-workload keys; announce the 30-day overlap (S8 B4).
5. Corrected Transit Gateway + private LiteLLM endpoint in staging (§5.1).
6. Start the GPU bake-off and N1 colo RFQ.
7. Orchestrator MVP scaffold (`LabTemplate`/`LabSession`, kopf) with three templates; image pre-pull DaemonSet.
8. Book counsel for: ODPC registration status, DPIA templates, cross-border basis for current student data, PMaaS sensitive-data review.
9. Fix collateral (C1, F-02, F-13) and pause new capacity/residency promises until §14 evidence exists.
10. Schedule the H1 kickoff with workstream leads and the acceptance tests from §14 as the definition of done.

---

## Appendix A — Definition of Done

**A lab template:** licence-ledger entry (permitted for target modes) · digest-pinned images · parameterised where graded · `checks.yaml` with reference/null/partial self-tests passing · egress policy set · TTL/idle set · warm-pool decision recorded · README with learning objectives and time estimate · xAPI verbs mapped · accessibility review.

**A tenant:** `tenants/<slug>.yaml` merged · Keycloak realm/IdP tested · quotas/Kueue queue active · keys issued with budgets · residency verified · DPIA/DPA on file · model cards published · dashboards live · offboarding runbook exercised in staging.

**A model/alias change:** eval suites pass · Swahili score not regressed · safety/PII suites pass · model card regenerated · licence check · approver recorded · canary weight ramp plan.

**A release of the platform:** all H-phase acceptance tests green · SBOM + signatures · rollback plan · change log · customer notification for T1/T2 tenants.

## Appendix B — Source Traceability

| Source | Where addressed |
|---|---|
| S1 (Cisco/OpenShift) | §3 (F-05, F-09, F-12), §6.4, §6.8, §14.2, #8, #26 |
| S2/S3 (AI commercialization) | §7, §8, §11.5, F-14, F-15, #10, #14, #25 |
| S4 (multi-vendor strategy) | §6.1–6.2, §6.7, #1 |
| S5/S7 (blueprints) | §2.2, §3, §5, §6.7, §8.6, §13.3–13.5 |
| S6 (runbook) | §5.1, §6.3, §8.3 |
| S8 (P0 spec) | §5.3, §7, §8, §9.3–9.4, §14 (B1–B5 retained), §13.2 |
| S9 (EduBridge) | §10, §11, §12 |
| S10 (USIU) | §3 (F-13), §10.9 |

## Appendix C — Assumptions and Items to Verify

1. **Cloud prices and IBM service capabilities** (bare-metal OpenShift Virtualization support, private load-balancer annotations, credit expiry, region availability) are indicative — verify with IBM in writing.
2. **Tool versions and API field names** (LiteLLM guardrail/callback keys, Containerlab kind names, Clabernetes CRD apiVersion, Kueue API version, `LiteLLM_SpendLogs` columns) — pin versions and validate in staging before adoption.
3. **Licence statements** about specific vendors/models/tools reflect general knowledge as of this review — confirm the current terms and obtain written vendor confirmation before commercial use.
4. **Legal and regulatory points** (Kenya DPA 2019 and 2021 Regulations, CBK expectations, cross-border transfer bases, retention vs erasure) are engineering control objectives, not legal advice — confirm with counsel.
5. **Capacity model** uses an assumed session mix; replace with measured profiles from the L-series tests.
6. **Current pilot status** for USIU-Africa and the live production namespace inventory should be re-verified against the running environment.

---

*End of guide. Suggested next artefacts: (1) `i3-platform` repo skeleton with the tenant chart and Kyverno policies; (2) Orchestrator MVP; (3) a one-page customer-safe infrastructure fact sheet replacing the current residency/capacity claims.*
