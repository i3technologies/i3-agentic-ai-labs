# i3 Sovereign Agentic Platforms
## Technical Specifications & Implementation Guide
### Unified Engineering Blueprint for Agentic, Multi-Tenant, Sovereign Platforms (East Africa Focus)

**Version:** 1.0  
**Date:** September 2026  
**Classification:** Confidential — Internal Engineering & Architecture Use  
**Owner:** Chief Technology Officer / Head of Platform Engineering  
**Prepared by:** Senior Solutions Architect & Full-Stack Engineering Review  

**Companion / Source Documents Reviewed:**
- i3 E³ Technical Implementation Guide (Ecosystem, Enablement & Execution Exchange) v1.0
- i3 Precision Marketing Cloud (i3 PMC) Master Technical Implementation Guide v2.0
- Modern Enterprise Collaboration, Cloud, Email & Agentic AI Platform — Technical Implementation Guide
- Sovereign Agentic Collaboration Platform (SACP) Full Application Blueprint v1.0

**Target Platforms & Deployment:**
- Primary: Red Hat OpenShift on IBM Cloud (ROKS) — Frankfurt (eu-de) with Nairobi / East Africa sovereign node path and customer-premises / Sovereign AI Appliance portability
- Alternative / Complementary: Self-hosted or managed sovereign clusters (Nextcloud Hub + Zimbra + Keycloak + local LLM stack) for pure collaboration workloads
- Shared principles apply across i3 E³ (Partner Ecosystem), i3 PMC (Precision Marketing / Customer Engagement), and SACP / Enterprise Collaboration suites

**Guiding Motto:** Connect. Build. Certify. Deploy. Monetize. — with full data sovereignty, progressive agent autonomy, and evidence-by-construction.

---

## 1. Purpose, Scope & How to Use This Guide

This document is the single authoritative technical specifications and implementation reference synthesising the four source artefacts. It extracts common architecture principles, binding constraints, domain models, agentic runtime patterns, trust & evidence planes, security/governance controls, roadmaps, team models and risk registers into an executable engineering contract.

Any engineer joining an i3 agentic platform programme (E³, PMC, SACP or related) should be able to read Sections 3–10, understand the shape of the system, and pick up a backlog item without a verbal briefing.

### 1.1 Scope Boundaries

| In Scope | Out of Scope |
|----------|--------------|
| Multi-tenant Work Graph / Customer 360 / Collaboration Graph, Digital Passports / Profiles, Agentic Runtime, AgentOps, evaluation harness, guardrails, progressive autonomy | Commercial pricing models, partner tier economics, pure marketing campaign creative |
| Credential Trust Network patterns (W3C VC + permissioned ledger where applicable), evidence-by-construction | Legal drafting of MoUs, Partner Charters, licence agreements |
| API surface, event contracts (CloudEvents), integration adapters (CRM, ERP, LMS, core banking, WhatsApp/SMS, M-Pesa) | Physical Sovereign AI Appliance hardware design |
| OpenShift / Kubernetes topology, GitOps, CI/CD, observability, DR, Kenya Data Protection Act (2019) / ODPC alignment | Marketing sites, brand assets, event microsites |
| Security, multi-tenancy, AI governance, cost attribution | Board-level financial forecasting |
| Collaboration core (files, mail, calendar, real-time) and Marketing Decisioning (NBA, Journeys) as alternative or complementary product lines | Foundation model training / fine-tuning from scratch |

### 1.2 Terminology Conventions

- **MUST / MUST NOT** — hard requirement. A release cannot pass its gate without it.
- **SHOULD** — strong default. Deviation requires a recorded Architecture Decision Record (ADR).
- **MAY** — optional; team discretion.
- **Work Graph / Customer Graph** — the canonical property graph of entities, relationships and evidence. It is the system of context.
- **Passport / Profile** — a signed, verifiable, machine-readable object (Partner, Engineer, Customer, Solution, Agent, Tenant).
- **Agent proposes, Policy disposes** — agents never take side-effecting actions directly; they emit intents that are authorised by policy engines and (where required) human gates.
- **Evidence by construction** — every meaningful state transition produces an immutable, hash-anchored proof as a by-product of the work itself.

### 1.3 Engineering North Star

> Every capability becomes discoverable.  
> Every opportunity / customer signal becomes actionable.  
> Every delivery / interaction becomes verifiable.  
> Every verified capability or outcome creates new commercial or operational value.  
>  
> If a feature does not add a node, an edge, an event or a proof to the Graph, question whether it belongs in the MVP.

---

## 2. Architecture Principles (Binding — All Platforms)

These principles are non-negotiable across E³, PMC and SACP. Any design choice that conflicts requires a formal ADR in `/docs/adr` (Nygard format), reviewed in the Architecture Forum.

| # | Principle | Practical Meaning |
|---|-----------|-------------------|
| **P1** | Graph / Context is the centre | Domain services write to the canonical graph (Work Graph, Customer 360, Collaboration Graph) through the domain API. The graph is the integration and reasoning surface, never a side-effect. |
| **P2** | Events are the spine | Every meaningful state change emits a CloudEvent (or equivalent) to a durable bus (Kafka / Redpanda). Read models, agents, analytics, evidence ledger and billing are all consumers. No synchronous cross-module chaining for core flows. |
| **P3** | Agents propose, policy disposes | An agent never executes a side-effecting action directly. It emits an intent; the Policy Engine + Approval Service authorises, blocks, escalates or routes to a human gate. |
| **P4** | Open protocols at every seam | Tool access via MCP (or equivalent typed tool registry). Cross-agent delegation via A2A where applicable. Telemetry via OpenTelemetry. Credentials via W3C VC 2.0 where trust network is required. Events via CloudEvents. |
| **P5** | Portability over proximity | Everything runs as OCI containers. Same codebase MUST be deployable on ROKS (Frankfurt), Nairobi sovereign node, customer-premises appliance or pure self-hosted Kubernetes without code change. |
| **P6** | Evidence by construction | Evidence is produced as a by-product of doing the work. If a workflow requires a human to “upload proof”, redesign it. |
| **P7** | Multi-tenant from line one | `tenant_id` is on every row, every index, every event, every prompt context, every log line and every vector collection partition. |
| **P8** | Deterministic core, probabilistic edge | Money, permissions, credential issuance, contract / consent state and high-risk actions are handled by deterministic code. LLMs handle extraction, ranking, drafting, explanation and recommendation. |
| **P9** | Small surface, deep contracts | Prefer few, well-typed, well-documented tools and APIs. Every tool is a security boundary with risk tier, schema and approval requirements. |
| **P10** | Observable by default | A feature is not done until it emits traces, metrics, cost attribution (tokens / GPU / outcomes) and a business KPI signal. |
| **P11** | Progressive autonomy | Every agent ships at the lowest useful autonomy level (L0/L1) and is promoted only on evaluation evidence. Promotion is a release decision, not a configuration toggle. |
| **P12** | Privacy is a design input | Personal data is minimised, classified, encrypted and (where a ledger exists) off-chain. The ledger stores proofs, never people. Kenya DPA / ODPC compliance is confirmed by DPO before production personal-data processing. |

**Additional Platform-Specific Principles**

- **Connectivity variance (East Africa):** Web clients MUST be PWA-capable with offline-tolerant read paths and queued writes where feasible.
- **Cost envelope:** Token / GPU spend is a first-class operational metric. Every agent invocation MUST carry a cost budget and be attributable to tenant + business object.
- **Vendor optionality:** IBM / Red Hat is primary alliance where ROKS is used, but no component on the critical path may become unswappable. Model access goes through a gateway; agent interop uses open protocols.

---

## 3. Logical Reference Architecture — Eight-Layer / Capability Domain Model

Dependencies flow strictly downward. The model is shared; concrete product lines (E³ Partner Work Graph, PMC Consent & Profile Core, SACP Collaboration Graph) specialise the Domain and Experience layers.

| Layer | Responsibility | Primary Technology Choices |
|-------|----------------|----------------------------|
| **L1 Experience** | Partner / Marketer / Engineer / Customer Workspaces, Mission Control / Executive Dashboard, Academy / Portal, public verification pages, self-service admin | Next.js 15 (App Router) / React 19 / TypeScript / Tailwind / PWA service worker / WebSocket-SSE. Alternative: Nextcloud Hub UI + custom portals for pure collaboration. |
| **L2 Edge & Gateway** | TLS, WAF, rate limiting, request signing, API composition, tenant resolution, anomaly detection | OpenShift Routes / HAProxy / NGINX Ingress + ModSecurity / CrowdSec, Kong or Red Hat 3scale / API Connect, GraphQL BFF where needed |
| **L3 Identity & Access** | AuthN, federation, session, RBAC/ABAC, service & agent identity, MFA (WebAuthn preferred) | Keycloak (OIDC/SAML) + FreeIPA / OpenLDAP / Samba4, SPIFFE/SPIRE for workload identity, OPA / policy engine |
| **L4 Domain Services** | Partner / Opportunity / Solution / Talent / Academy / Lab / Event / Delivery / Commercial (E³); Consent & Profile / Campaign / Journey / Offer / Segment (PMC); Workspace / Mail / Drive / Knowledge (SACP) | Java 21 / Quarkus or Spring Boot (transactional core); Python 3.12 / FastAPI (AI-adjacent); Node.js/TypeScript selectively |
| **L5 Agentic Runtime** | Agent registry, orchestration, MCP / tool broker, A2A peer delegation, memory, policy, evaluation hooks, kill-switch | LangGraph (or equivalent), MCP servers, watsonx Orchestrate (enterprise control plane reference where IBM stack), vLLM / Ollama for local inference |
| **L6 Knowledge & Data** | Relational state, property graph, vector, search, object store, event log, analytical store | PostgreSQL 16 (RLS + Patroni HA), Apache AGE or Neo4j, Milvus / Qdrant, OpenSearch / Elasticsearch, S3-compatible (Ceph or IBM COS), Kafka / Redpanda, Iceberg where lakehouse needed |
| **L7 Trust & Evidence** | Credential issuance, hash anchoring, revocation, verification API, audit bundles, consent ledger | Hyperledger Fabric on OpenShift (permissioned ledger for hashes/issuers only) + W3C VC Data Model 2.0 / JSON-LD where Trust Network is required; otherwise immutable audit tables + object-store proofs |
| **L8 Platform & Operations** | Clusters, GitOps, CI/CD, secrets, observability, backup/DR, FinOps | ROKS / Kubernetes, ArgoCD, Tekton, Vault / KMS, OpenTelemetry, Prometheus, Grafana, Loki, Tempo |

### 3.1 Runtime Topology (Simplified Graph Relationships)

```
(Person|Organization)-[:HAS_SKILL|EMPLOYS|OWNS]->(...)
(Opportunity|Campaign|Journey)-[:REQUIRES|TARGETS|USES]->(Skill|Segment|Offer|Channel)
(Evidence|Credential|Interaction)-[:ATTESTS|ATTRIBUTED_TO]->(...)
(AgentAction)-[:PROPOSED_BY|APPROVED_BY|EXECUTED_VIA]->(...)
(RevenueEvent|Outcome)-[:ATTRIBUTED_TO]->(Organization|Person|Campaign)
```

All nodes and edges carry `tenant_id`, timestamps, provenance and (where applicable) confidence / evidence references.

### 3.2 Identity, Keys & Tenancy (Universal)

- Primary keys: **UUIDv7** (time-ordered, index-friendly, safe to expose).
- Every row, node, edge, event and object-store key carries `tenant_id`.
- PostgreSQL **Row-Level Security** policies enforce isolation; the application never relies on `WHERE` clauses alone.
- Cross-tenant references use an explicit **Sharing Grant** object with scope, expiry and audit trail.
- External identifiers (IBM Partner ID, CRM ID, National ID hash, M-Pesa MSISDN, etc.) live in a separate `identity_alias` table.
- Vector collections and Kafka topics are partitioned or namespaced by tenant.
- Agent service accounts are first-class identities with least-privilege tool grants.

---

## 4. Digital Passports / Profiles (First-Class Objects)

Four (or more) first-class passport / profile types are issued as signed, verifiable objects where the Trust Plane is active:

| Passport / Profile | Typical Contents | Product Line |
|--------------------|------------------|--------------|
| **Partner Digital Passport** | Legal identity, geography, sectors, technologies, certifications, reference projects, delivery capacity, compliance evidence, commercial status | E³ |
| **Engineer / FDE Passport** | Verified identity, certifications, skills (self-declared vs evidenced), seniority, delivery history, availability | E³ |
| **Customer 360 / Consent Profile** | Unified identity keys, demographic/firmographic, lifecycle stage, consent ledger by channel/purpose, interaction history, predictions | PMC |
| **Solution / Offer Passport** | Owner, version, architecture, dependencies, models, agents, data requirements, evaluation status, security controls, deployment targets | E³ / PMC |
| **Agent Passport** | Identity, purpose, capability manifest, permitted tools, data scope, risk tier, model/runtime, evaluation suite, owner, version, cost envelope, approval policy, kill-switch state | All |
| **Tenant / Organisation Profile** | Domain mappings, quotas (users, storage, agents, tokens), security policy, residency tags, billing plan, delegated admins | All / SACP |

Passports / profiles are rendered with a verification link (and offline-verifiable against published issuer keys where W3C VC is used).

---

## 5. Agentic Runtime — First-Class Service Design

**Highest-value architectural decision (binding across all platforms):** Do not implement agents as ad-hoc prompts inside individual microservices. Build one formal, shared Agent Platform that every current and future AI capability reuses.

### 5.1 Core Components

| Component | Function |
|-----------|----------|
| Agent Registry | Versioned agent definitions — instructions, tools, models, policies, evaluation sets, risk tier |
| Agent Runtime | Task lifecycle, context assembly, plan generation, tool execution, observation, replanning |
| Agent Planner | Multi-step plan generation with constraints and cost budgets |
| Tool Registry | Controlled, schema-validated enterprise tools with risk tiers, side-effect class, approval requirements |
| Memory Service | Working, Conversation, Semantic, Customer/Organisational and Agent memory types (Qdrant / vector + structured) |
| Policy Engine | Identity, tenant, role, tool, data, business and regulatory policy evaluation |
| Approval Service | Human-in-the-loop queues with risk-based routing and audit |
| Guardrail Service | Input / output / tool guardrails and prompt-injection defence |
| Agent Evaluation | Automated metrics, regression datasets, canary and shadow modes |
| Observability & Audit | Full provenance — who, what, when, why, model, data, tool, policy, result, cost |
| Agent Marketplace (later phase) | Internal / commercial catalogue of reusable, governed agents |

### 5.2 Agent State Machine (Canonical)

```
CREATED → PLANNING → WAITING_FOR_TOOL → WAITING_FOR_APPROVAL → EXECUTING →
OBSERVING → REPLANNING → COMPLETED
Terminal (non-happy-path): FAILED · CANCELLED · ESCALATED · BLOCKED
```

**The LLM must never be the sole owner of workflow state** — the workflow engine owns it. Hard limits are enforced independent of the model: token budget, execution time, tool-call count, monetary impact, recursion depth.

### 5.3 Progressive Autonomy Model

| Level | Behaviour | Promotion Gate |
|-------|-----------|----------------|
| **L0** | Observe / recommend only | Evaluation suite + golden sets |
| **L1** | Propose actions; human gate required | Production traffic under human approval + quality metrics |
| **L2** | Execute within strict policy envelope | Demonstrable audit evidence of Safety Triangle satisfaction |
| **L3** | Autonomous within published cost & risk bounds | Formal release decision + continuous evaluation |

Promotion is a release decision, not a configuration toggle. Every agent ships at the lowest useful level.

### 5.4 Tool-Calling Contract

Every tool declares at minimum:

- `name`, `permissions`, `input/output schema` (JSON Schema)
- `risk_level` (0–4)
- `requires_approval` (boolean or policy expression)
- `audit_required`, `side_effect_class`, `cost_estimate`

Representative tools (product-specific): `get_customer`, `get_partner`, `create_campaign`, `send_message`, `register_opportunity`, `provision_lab`, `ocr_document`, `request_human`, `issue_credential`, `m_pesa_stk_push`, etc.

### 5.5 Safety & Cost Controls (Mandatory)

- Authorisation lives **outside** the model.
- Every invocation carries a cost budget and is attributed to tenant + business object.
- Semantic caching, small-model routing and tenant caps are mandatory.
- Kill-switch is first-class and can be invoked by on-call engineer (act first, review after).
- Prompt-injection defence hierarchy: System policy > Developer policy > Business policy > User instruction > Retrieved content. Retrieved documents are treated as **data, never trusted instructions**.

### 5.6 The Agentic Safety Triangle (Production Invariant)

> Every autonomous action is executable only when **Business Policy ∧ Data Authorisation ∧ Security Authorisation** are all simultaneously satisfied. This is the non-negotiable production safety invariant.

---

## 6. Core Product Line Specialisations

### 6.1 i3 E³ — Ecosystem, Enablement & Execution Exchange

**Purpose:** Graph-centred, event-sourced partner ecosystem execution platform.

**Key Aggregates & State Machines:**
- Partner: prospect → registered → verified → enabled → active → dormant → offboarded
- Opportunity: captured → qualified → registered → matched → proposed → won/lost → delivering → delivered → renewed (180-day exclusivity on registration)

**Core Agents (MVP):** Partner Onboarding, Partner Match, Opportunity Qualification, Solution Architect, FDE Dispatch, Academy Coach, Proposal, Partner Health, Revenue Attribution, AgentOps, Ecosystem Strategist.

**MVP Capabilities (13):** Partner registration & Passport, Engineer Passport, Academy & certification, Opportunity registration with exclusivity, Matching (< 3 s p95 ranked shortlist), FDE dispatch, Solution catalogue, Lab booking & provisioning (≤ 5 min), AI Partner Copilot, Work Graph foundation, Executive Mission Control (12 live KPIs), Basic evidence & attribution, Credential Trust Network pilot (QR verification < 300 ms).

**Trust Plane:** Hyperledger Fabric + W3C VC 2.0; hashes only on-chain; sub-second public verification; offline verification against issuer key; learner erasure leaves unlinkable hash + certificate.

### 6.2 i3 PMC — Precision Marketing Cloud

**Purpose:** Sovereign, Agentic AI-native Customer Engagement and Decisioning platform targeting Unica-equivalent module coverage with in-region residency and single consumption commercial model.

**Key Modules (Release 1.0):** Audience Studio, Journey Orchestrator, Engage (Real-Time NBA), Messenger (WhatsApp / SMS / Email / USSD / Push), Plan & Resource Manager, Contact Optimizer, Insight Studio, Connect Hub, Consent & Profile Core.

**NBA Pipeline (target p95 < 200 ms):**  
Customer Event → Feature Retrieval (Redis) → Eligibility → Offer Candidates → Business Rules → ML Scoring → Contact Frequency → AI Reasoning → Policy Constraints → Ranked Actions (including explicit **DO NOTHING**).

**Core Agents (Release 1.0):** Campaign Strategy, Journey Architect, Content, Customer Intelligence, Compliance / Brand, QA, Data-Quality (later autonomous Ops). All recommend-and-approve by default.

**Consent is enforced at the API layer before any channel dispatch — no exceptions.**

### 6.3 SACP / Enterprise Collaboration Platform

**Purpose:** Greenfield multi-tenant collaboration + autonomous operations suite for East African organisations (self-hosted or managed sovereign cloud).

**Core Applications:**
- SACP Workspace (unified portal)
- SACP Mail (Zimbra-powered + agentic inbox, M-Pesa receipt understanding)
- SACP Drive & Knowledge (Nextcloud-based + agent-writable spaces + knowledge graph)
- SACP Agents Console (visual multi-agent designer + templates)
- SACP Agentic PDF Studio (OCR → classification → multi-agent evaluation → actionable output)
- SACP Admin & Tenant Console (quotas, M-Pesa billing, ODPC readiness)

**Flagship Agents:** Academic Tutor, Institutional Ops, Meeting Synthesizer, Smart Tender Auditor, Self-Evaluating Worksheet, Contract Compliance, Cyber Defense.

**Stack Highlights:** Nextcloud Hub, Zimbra, Keycloak, PostgreSQL HA, Ceph/S3, vLLM/Ollama, LangGraph, Qdrant, PaddleOCR / pdfplumber, HAProxy + WAF.

---

## 7. Event-Driven Backbone & Microservice Topology

Kafka (or Redpanda) is the platform backbone. Event envelope follows CloudEvents style:

```
event_id, event_type, event_version, occurred_at, tenant_id, source, subject,
correlation_id, trace_id, data
```

**Key event families (extend per product):**  
`customer.*`, `identity.*`, `consent.*`, `interaction.*`, `partner.*`, `opportunity.*`, `campaign.*`, `journey.*`, `offer.*`, `message.*`, `agent.*`, `prediction.*`, `nba.*`, `credential.*`, `document.*`, `security.*`, `billing.*`

**Bounded-context services (start focused; split only on evidence of independent scaling need):**  
identity-service, tenant-service, profile-service / partner-service, consent-service, segment-service, campaign-service / opportunity-service, journey-service, offer-service, decision-service, messenger-service, agent-service, tool-service, memory-service, knowledge-service, analytics-service, audit-service, approval-service, billing-service, connector-service, document-service (PDF/OCR), etc.

Prefer a modular monolith with clean internal boundaries for the initial 14–20 FTE squad; extract services only when independent release cadence or scaling is proven necessary.

---

## 8. Technology Stack Summary

| Layer | Preferred Stack |
|-------|-----------------|
| Frontend | Next.js 15 + React 19 + TypeScript + Tailwind + PWA; or Nextcloud UI + custom portals |
| Backend Domain | Java 21 / Quarkus or Spring Boot; Python 3.12 / FastAPI for AI-adjacent |
| AI Orchestration | LangGraph + MCP tool servers; watsonx Orchestrate as enterprise reference where IBM |
| Local Inference | vLLM / Ollama (sovereign / offline path) |
| Vector / RAG | Qdrant or Milvus + local embeddings (e.g. bge-large family) |
| Relational | PostgreSQL 16 + RLS + Patroni HA |
| Graph | Apache AGE (PostgreSQL) or Neo4j |
| Cache / Features | Redis |
| Events | Kafka / Redpanda |
| Object Storage | Ceph or IBM Cloud Object Storage (S3-compatible) |
| Search | OpenSearch / Elasticsearch |
| Identity | Keycloak + LDAP/FreeIPA |
| Secrets | HashiCorp Vault or cloud KMS / HSM |
| Observability | OpenTelemetry → Prometheus / Grafana / Loki / Tempo |
| CI/CD / GitOps | ArgoCD + Tekton (or GitHub Actions / GitLab CI equivalent) |
| Ingress / Security Edge | HAProxy / NGINX + WAF (ModSecurity), Kong / 3scale |
| OCR / Document | PaddleOCR + pdfplumber + layout models |
| Integration Runtime | Red Hat Fuse / Apache Camel (preferred for Connect Hub) or custom adapters |

---

## 9. Security, Privacy, Governance & Compliance

### 9.1 Multi-Tenancy & Isolation

- Namespace-level isolation on OpenShift / Kubernetes.
- RLS + partitioned vector collections + purpose-bound access.
- Cross-tenant leakage is a **P1** incident.
- Dedicated node pools and encryption keys available for regulated tenants (banks, government).

### 9.2 AI Governance Controls

- Input / output / tool guardrails.
- Prompt-injection hierarchy and provenance tagging.
- No privilege inheritance from retrieved content.
- Adversarial evaluation suite gates every agent autonomy promotion.
- Full agent action audit trail retained for compliance.

### 9.3 Data Protection

- Kenya Data Protection Act 2019 / ODPC as baseline; per-country adaptation across East Africa.
- Data classification (Public / Internal / Confidential / Restricted / Highly Restricted).
- Encryption at rest (per-tenant keys) and in transit (TLS 1.3 preferred).
- Personal data minimised and off-chain where ledger exists.
- Erasure workflows that leave unlinkable proofs + certificates where required.
- DPO confirmation required before any production personal-data processing.

### 9.4 Email & Channel Security (Collaboration / Messaging)

- SPF + DKIM + DMARC (`p=reject` by default where possible).
- MTA-STS, TLS-RPT, reputation monitoring, attachment sandboxing, phishing analysis.
- Consent / frequency / purpose checks before every outbound dispatch.

### 9.5 Supply Chain & DevSecOps

- SBOM for every solution / container image.
- Signed images, dependency & CVE posture reviewed monthly.
- Pipeline: SAST → dependency scan → secret scan → container scan → unit/integration → AI evaluation → staging → security approval → production.
- No direct manual production deployments except controlled break-glass.

---

## 10. Non-Functional Requirements (Illustrative SLOs)

| Category | Target |
|----------|--------|
| Real-time decisioning / NBA latency | p95 < 200 ms |
| Consent decision latency | p95 < 50 ms |
| Partner / engineer matching (E³) | Ranked shortlist p95 < 3 s |
| Lab provisioning (E³) | ≤ 5 min; hard TTL; auto-teardown |
| Credential QR verification | p95 < 300 ms (unauthenticated) |
| Platform availability (critical services) | 99.9 % – 99.99 % (measure from dependencies) |
| Kafka lag | < 30 s |
| Message delivery reconciliation | Within 5 min of dispatch |
| Disaster Recovery | RPO ≤ 1 h, RTO ≤ 4 h for production tenants (validate by test) |
| Agent task success rate (production) | ≥ 93 % (product-specific) |

Final contractual SLAs must be derived from measured capacity and DR architecture.

---

## 11. Consolidated Implementation Roadmap (12-Month Horizon)

Roadmaps from source documents have been reconciled into phase-gate discipline. Product-specific waves sit inside the common phases.

| Phase | Window | Focus | Exit Gate (Common) |
|-------|--------|-------|--------------------|
| **0 — Foundation** | Weeks 1–6 | Cluster / GitOps, IAM + tenancy, event backbone, schema registry, observability, CI, ADR process, security baseline, threat model | Architecture approved; Hello-world service with tenant-scoped auth + end-to-end trace; security baseline clean |
| **1 — Core Domain + Graph** | Months 1–3 | Consent / Profile / Partner aggregates, Work Graph / Customer 360 projection, basic Passports, Messaging / Mail foundation, Audience / Opportunity registration | Core CDP / Partner registration + messaging operational; multi-tenancy proven |
| **2 — Orchestration & Agents (L0/L1)** | Months 3–7 | Journey / Opportunity matching, first Connect Hub connectors, AI Gateway, Campaign / Match / Content agents (recommend-and-approve), Agent Platform skeleton, evaluation harness | Natural-language drafting / matching live under human gate; evaluation platform operational |
| **3 — Real-Time, Labs & Trust** | Months 6–9 | NBA / Engage, Lab provisioning, Credential Trust Network pilot (where applicable), Contact Optimizer, deeper AgentOps | Real-time paths live; credential verification pilot; AgentOps metrics published |
| **4 — Depth & Governance** | Months 9–12 | Full Agent Runtime (L2 candidates), Solution / Engineering depth, attribution / settlement foundations, country-node federation path, Insight / Mission Control maturity, commercial packaging readiness | First external pilot(s) live; second country node path proven on same codebase; autonomous actions gated behind Safety Triangle evidence |

**MVP Scope Rule (binding):** Treat the explicit MVP / Release 1.0 acceptance criteria of each product line as the only release gate for the corresponding launch milestone. Do not allow Phase 3/4 capability to leak into the launch demo.

**Launch Milestone Reference:** 16 October 2026 — Ecosystem Launch Event, Nairobi (E³). Other product lines follow their own pilot cadence.

---

## 12. Team Composition & Delivery Model (MVP Reference)

| Role | Indicative FTE (MVP Squad) | Responsibilities |
|------|----------------------------|------------------|
| Engineering Manager / Delivery Lead | 1 | Backlog, sprint cadence, dependency management, stakeholder reporting |
| Solutions Architect | 1 | ADRs, module boundaries, integration contracts, technical arbitration |
| Backend Engineers | 3–6 | Domain modules, APIs, event producers/consumers, migrations |
| AI / Agent Engineers | 2–3 | Agent manifests, orchestration, MCP tools, prompts, evaluation suites |
| Frontend Engineers | 2–3 | Workspaces, Mission Control / Dashboards, PWA, accessibility |
| Data Engineer | 1–2 | Graph projection, vector & search pipelines, lakehouse, lineage |
| Platform / SRE | 1–2 | Clusters, GitOps, observability, DR, on-call |
| Security Engineer | 0.5–1 | Threat model, IAM, supply chain, adversarial testing, DPA controls |
| QA / Test Engineer | 1–2 | Test strategy, journey automation, agent regression, release sign-off |
| Product Owner / Technical PM | 0.5–1 | Acceptance, prioritisation, cohort / pilot liaison |

**Engineering team boundaries (example):**  
Team A — Customer / Partner Data; Team B — Campaign / Opportunity / Journey; Team C — Messaging / Mail; Team D — AI / Agents; Team E — Decisioning / Match; Team F — Platform.

**Definition of Done (non-AI):** functional + unit + integration + security + performance tests; observability; audit logging; API documentation; failure handling; rollback plan; runbook; owner; SLO; data classification; tenant isolation test.

**Additional AI Definition of Done:** evaluation dataset, prompt/version tracking, model version tracking, grounding tests, hallucination tests, safety tests, tool-authorisation tests, human override, cost monitoring.

---

## 13. Risk Register (Selected High-Impact Items)

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|----|------|------------|--------|------------|-------|
| TR-01 | Scope sprawl across all product lines / 11+ agentic innovations | H | H | Hard MVP boundary per product; scope changes require CTO + Product Owner approval; explicit exclusion lists public | Engineering Manager |
| TR-02 | Agent output quality insufficient for partner / customer-facing use at launch | M | H | Deterministic scoring + model explains only; L0/L1 autonomy at launch; golden sets; human gates on everything visible | CTO / AI Lead |
| TR-03 | Model / inference cost outruns revenue | M | H | Cost envelopes, tenant caps, semantic caching, small-model routing, cost-per-outcome reported monthly | CTO |
| TR-04 | Cross-tenant data leakage | L | VH | RLS, partitioned collections, per-release leakage suite, immediate P1 path | Security Engineer |
| TR-05 | Shared IBM Cloud / Red Hat estate contention (Academy + 11 other solutions + new platforms) | H | H | Re-verify credit balance and Red Hat subscription renewal **before Phase 0**; ring-fence production capacity | Platform Lead |
| TR-06 | Prompt injection via customer / partner documents causes unintended action | M | H | Authorisation outside model; provenance tagging; no privilege inheritance; adversarial suite | Security Engineer |
| TR-07 | Launch-date pressure causes security or evaluation gates to be waived | M | VH | Gates are release-blocking by policy; only CTO may waive in writing with remediation date; waivers reported to board | CTO |
| TR-08 | Connectivity conditions degrade East Africa demonstrations | M | M | Offline-capable verification / PWA; local-network rehearsal; pre-seeded data; multiple full rehearsals | Platform Lead |
| TR-09 | Regulated customers require in-country residency not fully covered by current footprint | M | H | Tenancy design supports dedicated node pools / in-country hosting as explicit sellable option from day one | Solutions Architect |
| TR-10 | Feature parity pressure with mature commercial suites (Unica, global collaboration platforms) | H | H | Phase strictly to Release 1.0 / MVP lists; treat advanced autonomy, marketplaces, voice, paid media as explicit later phases | Product Owner |

Full register is reviewed monthly; any H/H or VH risk is reported to the board with named mitigation owner and review date.

---

## 14. Production Readiness Checklist & Golden Rules

### Commercialisation / Launch Readiness

- **Product** — Packaging, Pricing philosophy (consumption where applicable), SLA, Onboarding, Documentation
- **Engineering** — HA, DR, Security, Performance, Observability
- **AI** — AI Gateway, Model governance, Evaluation Platform, Guardrails, Agent permissions, Human approval flows
- **Data** — Consent / Profile, Identity resolution, Retention, Residency tags, Encryption
- **Operations** — SRE, Incident response, Runbooks, Backup/restore, Support tiers
- **Commercial** — Contract templates, Billing / metering, Sales enablement, Demo environment

### The Golden Rule for Production Agentic AI

Every autonomous capability must be able to answer five questions before it ships:

1. **WHAT** is the agent trying to accomplish?
2. **WHAT** data is it allowed to access?
3. **WHAT** tools is it allowed to call?
4. **WHAT** actions require human approval?
5. **HOW** do we prove afterwards what happened and why?

If those five questions cannot be answered, the agent is not production-ready.

---

## 15. Recommendations for Immediate Action

1. Adopt this document (and the 12 Architecture Principles) as the engineering contract for all i3 agentic platform workstreams.
2. Fund and resource the MVP squad(s) for the 90–120 day window of the priority product line (E³ for 16 Oct 2026 launch; others according to commercial priority).
3. Stand up the ADR process, Architecture Forum and weekly AgentOps review in Week 1 of any programme.
4. Treat the explicit MVP / Release 1.0 acceptance criteria of each product as the only release gate for its launch.
5. Keep exclusion lists public and defended — do not allow later-phase capability to leak into launch demos.
6. Confirm Skillsoft / certification-body / content licensing (E³) and channel provider relationships (WhatsApp Business API, SMS aggregators, M-Pesa) in writing before building dependent pipelines.
7. Confirm Kenya Data Protection Act position with the DPO and external counsel before any production personal-data processing.
8. Re-verify IBM Cloud credit balance and Red Hat OpenShift Partner Subscription renewal timeline **before Phase 0** of any ROKS-dependent programme.
9. Rehearse launch / pilot demonstrations three times end-to-end (including offline / low-connectivity fallback) before the target date.
10. Begin with the three highest-leverage agents for the chosen product line and prove the Safety Triangle + Evaluation Platform before expanding autonomy.

---

## Appendix A — Illustrative Schema Fragments (PostgreSQL)

```sql
-- Organisation / Tenant / Partner core
CREATE TABLE organization (
  id            UUID PRIMARY KEY,          -- UUIDv7
  tenant_id     UUID NOT NULL,
  legal_name    TEXT NOT NULL,
  country_code  CHAR(2) NOT NULL,
  org_type      TEXT NOT NULL CHECK (org_type IN
    ('partner','customer','academic','vendor','tvet','internal')),
  tier          TEXT,
  status        TEXT NOT NULL DEFAULT 'prospect',
  attributes    JSONB NOT NULL DEFAULT '{}',
  residency_tag TEXT,                      -- e.g. 'KE-only', 'EAC'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_tenant_isolation ON organization
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Opportunity (E³) or Campaign (PMC) pattern
CREATE TABLE opportunity (
  id                 UUID PRIMARY KEY,
  tenant_id          UUID NOT NULL,
  customer_org_id    UUID NOT NULL REFERENCES organization(id),
  registered_by_org  UUID REFERENCES organization(id),
  stage              TEXT NOT NULL DEFAULT 'captured',
  value_amount       NUMERIC(18,2),
  value_currency     CHAR(3),
  exclusivity_until  TIMESTAMPTZ,
  scope_fingerprint  TEXT NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX opp_exclusive_scope
  ON opportunity (customer_org_id, scope_fingerprint)
  WHERE stage IN ('registered','matched','proposed')
    AND exclusivity_until > now();

-- Agent action audit (all platforms)
CREATE TABLE agent_action (
  id              UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL,
  agent_id        TEXT NOT NULL,
  agent_version   TEXT NOT NULL,
  intent          TEXT NOT NULL,
  tools_used      JSONB,
  data_accessed   JSONB,
  decision        TEXT,                    -- ALLOW / DENY / ESCALATE / REQUIRES_APPROVAL
  risk_tier       SMALLINT,
  model_id        TEXT,
  token_cost      NUMERIC,
  approval_id     UUID,
  result          JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Appendix B — Glossary (Selected)

| Term | Definition |
|------|------------|
| A2A | Agent2Agent protocol for agent-to-agent delegation |
| AgentOps | Operational discipline of evaluating, observing, governing and controlling an agent estate |
| CloudEvents | CNCF portable event envelope specification |
| GraphRAG | Retrieval-augmented generation where the retrieval substrate is a property graph |
| MCP | Model Context Protocol — open standard for agent-to-tool access |
| NBA | Next-Best-Action |
| ROKS | Red Hat OpenShift Kubernetes Service on IBM Cloud |
| SACP | Sovereign Agentic Collaboration Platform |
| VC | W3C Verifiable Credential (Data Model 2.0) |
| Work Graph | Canonical property graph of ecosystem entities, relationships and evidence; the system of context |

## Appendix C — Qualification & Disclaimer

This is an engineering specification and implementation guide synthesised from the four source documents. It is not a binding IBM programme commitment, regulatory determination, security certification or financial forecast. Specific IBM and Red Hat programme eligibility, licensing, availability and commercial terms must be confirmed with the relevant vendor teams before any customer commitment is made. Content licensing (Skillsoft, certification bodies) and channel provider agreements must be confirmed in writing before dependent pipelines process licensed or third-party material. Data protection obligations under the Kenya Data Protection Act 2019 must be confirmed by the Data Protection Officer and external counsel before production processing of personal data. Statements about product capability reflect the source material as at September 2026 and should be re-verified before external use.

---

**Document Control**

Prepared by: Senior Solutions Architect & Full-Stack Engineering Review  
Reviewed for: Engineering Review & Board Endorsement  
Next Review: After Phase 1 MVP gate of the priority product line (target: Week 12) or major architecture change  

**Connect. Build. Certify. Deploy. Monetize.**  
*i3 Technologies | Instrumented, Interconnected & Intelligent Technologies Limited*  
*IBM Cloud + Red Hat OpenShift | Sovereign Agentic Platforms for East Africa*
