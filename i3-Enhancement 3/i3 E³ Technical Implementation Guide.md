# i3 E³ Technical Implementation Guide
## Ecosystem, Enablement & Execution Exchange  
**Version 1.0 — Engineering Blueprint & Implementation Reference**  
**Classification:** Confidential — Internal Engineering Use  
**Owner:** Chief Technology Officer / Head of Platform Engineering  
**Companion Documents:**  
- i3 E³ Business Strategy & Channel Execution Playbook v1.0  
- i3 E³ Technical Implementation Document v1.0  
- IBM Partner Ecosystem Portal Strategy Blueprint  
- Partner Outreach & Ecosystem Engagement Strategy  

**Target Platform:** Red Hat OpenShift on IBM Cloud (ROKS) — Frankfurt (eu-de) primary, with Nairobi sovereign node path and Sovereign AI Appliance portability.  
**Launch Milestone:** 16 October 2026 — Ecosystem Launch Event, Nairobi  

**Connect. Build. Certify. Deploy. Monetize.**

---

## 1. Purpose & How to Use This Guide

This document is the single authoritative technical implementation reference for the i3 E³ platform. It synthesises the approved strategy, architecture decisions, domain model, agentic runtime, trust plane, delivery plan and risk controls into an executable engineering contract.

Any engineer joining the programme should be able to read Sections 3–8, understand the shape of the system, and pick up a backlog item without a verbal briefing.

### 1.1 Scope Boundaries

| In Scope | Out of Scope |
|----------|--------------|
| Partner Work Graph, PartnerOS, Opportunity / Solution / Engineering / Lab / Delivery / Commercial Exchanges, Academy & Skills services | Commercial pricing, partner tier economics, channel policy (see Business Playbook) |
| i3 Agentic Runtime, agent catalogue, AgentOps, evaluation harness, guardrails | Foundation model training or fine-tuning |
| Credential Trust Network (Hyperledger Fabric + W3C Verifiable Credentials) | Legal drafting of MoUs, Partner Charter, licence agreements |
| API surface, event contracts, integration adapters (IBM, Skillsoft, CRM, LMS) | Physical Sovereign AI Appliance hardware build |
| OpenShift topology, GitOps, CI/CD, observability, DR, Kenya Data Protection Act alignment | Marketing site, event microsite, brand assets |
| Security, multi-tenancy, AI governance controls | Financial forecasting & board-level revenue modelling |

### 1.2 Terminology Conventions

- **MUST / MUST NOT** — hard requirement. A release cannot pass its gate without it.
- **SHOULD** — strong default. Deviation requires a recorded Architecture Decision Record (ADR).
- **MAY** — optional; team discretion.
- **Work Graph** — the canonical property graph of ecosystem entities and relationships. It is the system of context, not merely a database.
- **Passport** — a signed, verifiable, machine-readable profile object (Partner, Engineer, Solution, Agent).

---

## 2. Engineering North Star & Problem Framing

### 2.1 What We Are Actually Building

i3 E³ is **not** a CRM, LMS, document repository or social network. Those systems record state. E³ must **change** state:

- Partner: unknown → onboarded → activated  
- Learner: enrolled → verifiably capable  
- Lead: raw → qualified → matched → delivered  
- Engineer: available → dispatched → evidenced  

Technically this is a **graph-centred, event-sourced execution platform** with an agentic control layer on top.

> **Engineering North Star**  
> Every partner capability becomes discoverable.  
> Every opportunity becomes actionable.  
> Every delivery becomes verifiable.  
> Every verified capability creates new commercial opportunity.  
>  
> If a feature does not add a node, an edge, an event or a proof to the Work Graph, question whether it belongs in the MVP.

### 2.2 The Twelve Friction Points & Technical Resolution

| Business Friction | Technical Resolution | Owning Module |
|-------------------|----------------------|---------------|
| Partner discovery is manual & reputational | Property graph + hybrid semantic/structured capability search + ranked matching | Partner Graph, Match Service |
| Certification does not convert to revenue | Skill vectors linked to opportunity requirement vectors; credential events trigger re-scoring | Academy, Skills, Match |
| Opportunity fragmentation | Single Opportunity aggregate with deal-registration exclusivity, state machine & immutable audit | Opportunity Exchange |
| Specialist talent shortage | Engineer Passport index, availability calendar, constraint-solver dispatch | Engineering Exchange |
| Solutions reinvented per engagement | Versioned Solution Passport with dependency manifest, IaC bundle & PoC kit | Solution Exchange |
| Hackathon / workshop leakage | Event-to-Opportunity pipeline with automatic artefact capture & lab telemetry | Event Factory |
| Commercial attribution disputes | Contribution event ledger with configurable rules engine & settlement export | Commercial Exchange |
| Trust gap in claimed capability | Hash-anchored W3C Verifiable Credentials with sub-second QR verification | Trust & Evidence Plane |
| Agent sprawl & unsafe autonomy | Agent registry, capability manifests, risk tiers, policy engine, kill switch | Agent Exchange, AgentOps |
| Regional fragmentation | Multi-tenant country nodes federating over shared APIs & passport standards | Platform, Federation Gateway |
| Evidence burden at audit time | Append-only evidence store with provenance & one-click audit bundle | Trust & Evidence Plane |
| Learning content produces no measurable capability | Automated lab provisioning + proctored assessment + code-level evidence hashes | Lab Exchange, Assessment Engine |

### 2.3 Design Constraints We Explicitly Design Around

1. **Connectivity variance** — East African users experience intermittent bandwidth. The web client **MUST** be a PWA with offline-tolerant read paths and queued writes.
2. **Data sovereignty** — Kenyan public-sector and financial-services customers will require in-country residency. Architecture **MUST** be portable across ROKS (Frankfurt), a Nairobi node and a customer-premises appliance without code change.
3. **Small platform team** — Optimise for a modular monolith with clean internal boundaries. Split a module into a service only when independent scaling or release cadence is required.
4. **Cost envelope** — Token spend is a first-class operational metric. Every agent invocation **MUST** carry a cost budget and be attributable to a tenant and a business object.
5. **Vendor optionality** — IBM is the primary alliance, but no component may become unswappable. Model access goes through a gateway; agent interop uses open protocols.

---

## 3. Architecture Principles (Binding)

These twelve principles are non-negotiable. Any design choice that conflicts with one requires a formal ADR.

| # | Principle | Practical Meaning |
|---|-----------|-------------------|
| **P1** | Work Graph is the centre | Domain services write to the graph through the domain API. The graph is the integration point, never a side-effect. |
| **P2** | Events are the spine | Every meaningful state change emits a CloudEvent to Kafka. Read models, agents, analytics and the evidence ledger are all consumers. No synchronous cross-module chaining. |
| **P3** | Agents propose, policy disposes | An agent never takes a side-effecting action directly. It emits an intent; the policy engine authorises, blocks or escalates to a human gate. |
| **P4** | Open protocols at every seam | Tool access via MCP. Cross-agent delegation via A2A. Telemetry via OpenTelemetry. Credentials via W3C VC 2.0. Events via CloudEvents. |
| **P5** | Portability over proximity | Everything runs as OCI containers on OpenShift. No managed-service lock-in on the critical path. |
| **P6** | Evidence by construction | Evidence is produced as a by-product of doing the work. If a workflow requires a human to “upload proof”, redesign it. |
| **P7** | Multi-tenant from line one | `tenant_id` is on every row, every index, every event, every prompt context and every log line. |
| **P8** | Deterministic core, probabilistic edge | Money, permissions, credential issuance and contract state are handled by deterministic code. LLMs handle extraction, ranking, drafting and explanation. |
| **P9** | Small surface, deep contracts | Prefer few, well-typed, well-documented tools and APIs. Every tool is a security boundary. |
| **P10** | Observable by default | A feature is not done until it emits traces, metrics, cost attribution and a business KPI signal. |
| **P11** | Progressive autonomy | Every agent ships at the lowest useful autonomy level and is promoted only on evaluation evidence. Promotion is a release decision. |
| **P12** | Privacy is a design input | Personal data is minimised, classified, encrypted and off-chain. The ledger stores proofs, never people. |

**ADR Process:** All ADRs live in `/docs/adr`, follow the Nygard format, and are reviewed in the fortnightly Architecture Forum. Required for: new datastore, new framework, public API contract change, agent autonomy promotion, or any principle deviation.

---

## 4. Logical Reference Architecture

### 4.1 Eight-Layer Model

Dependencies flow strictly downward.

| Layer | Responsibility | Primary Technology |
|-------|----------------|--------------------|
| **L1 Experience** | Partner Workspace, Engineer Workspace, Customer Transformation Room, Academy, Mission Control, public verification page | Next.js 15 (App Router), React 19, TypeScript, Tailwind, PWA service worker, WebSocket/SSE |
| **L2 Edge & Gateway** | TLS, WAF, rate limiting, request signing, API composition, tenant resolution | OpenShift Routes, NGINX Ingress, Kong / IBM API Connect, GraphQL BFF |
| **L3 Identity & Access** | AuthN, federation, session, RBAC/ABAC, service & agent identity | Keycloak (OIDC/SAML), SPIFFE/SPIRE, OPA |
| **L4 Domain Services** | Partner, Opportunity, Solution, Talent, Academy, Lab, Event, Delivery, Commercial, Trust | Java 21 / Quarkus (transactional), Python 3.12 / FastAPI (AI-adjacent) |
| **L5 Agentic Runtime** | Agent registry, orchestration, MCP tool broker, A2A peer delegation, memory, policy, evaluation hooks | LangGraph, MCP servers, A2A, watsonx Orchestrate as enterprise control plane |
| **L6 Knowledge & Data** | Relational state, graph, vector, search, object store, event log, analytical store | PostgreSQL 16, Apache AGE (or Neo4j), Milvus, OpenSearch, S3-compatible, Kafka, Iceberg |
| **L7 Trust & Evidence** | Credential issuance, hash anchoring, revocation, verification API, audit bundle | Hyperledger Fabric on OpenShift, W3C VC Data Model 2.0, JSON-LD, HSM-backed keys |
| **L8 Platform & Operations** | Clusters, GitOps, CI/CD, secrets, observability, backup/DR, FinOps | ROKS, ArgoCD, Tekton, Vault, OpenTelemetry, Prometheus, Grafana, Loki, Tempo |

### 4.2 Runtime Topology (Simplified)

(Person)-[:HAS_SKILL {level, last_evidenced_at, confidence}]->(Skill)
(Person)-[:CERTIFIED_IN {credential_id, issued_at, expires_at}]->(Certification)
(Organization)-[:EMPLOYS {from, to, role}]->(Person)
(Organization)-[:DELIVERED {project_id, outcome_score, closed_at}]->(Opportunity)
(Opportunity)-[:REQUIRES {weight, mandatory}]->(Skill|Technology|Certification)
(Opportunity)-[:REGISTERED_BY {at, exclusivity_until}]->(Organization)
(Evidence)-[:ATTESTS]->(Credential|Milestone|Solution|Opportunity)
(RevenueEvent)-[:ATTRIBUTED_TO {contribution_type, weight}]->(Organization|Person)
text



### 5.4 Identity, Keys & Tenancy

- Primary keys: **UUIDv7** (time-ordered, index-friendly, safe to expose).
- Every row, node, edge, event and object-store key carries `tenant_id`.
- PostgreSQL **Row-Level Security** policies enforce isolation; the application never relies on `WHERE` clauses alone.
- Cross-tenant references use an explicit **Sharing Grant** object with scope, expiry and audit trail.
- External identifiers (IBM Partner ID, Skillsoft learner ID, national ID hash) live in a separate `identity_alias` table.

### 5.5 Core State Machines

| Aggregate | States | Key Guard Conditions |
|-----------|--------|----------------------|
| **Partner** | prospect → registered → verified → enabled → active → dormant → offboarded | verified requires KYC document hashes; enabled requires ≥1 certified engineer; active requires ≥1 registered opportunity or delivery in 90 days |
| **Opportunity** | captured → qualified → registered → matched → proposed → won/lost → delivering → delivered → renewed | registered sets 180-day exclusivity; matched requires ≥1 partner meeting all mandatory requirements |

---

## 6. Digital Passports

Four first-class passport types are issued as signed, verifiable objects:

| Passport | Contents |
|----------|----------|
| **Partner Digital Passport** | Legal identity, geography, sectors, technologies, certifications, reference projects, delivery capacity, compliance evidence, commercial status, ecosystem relationships |
| **Engineer Passport** | Verified identity, certifications, skills (self-declared vs evidenced), seniority, technologies, industries, delivery history, assessment results, availability |
| **Solution Passport** | Owner, version, architecture, dependencies, models, agents, tools, data requirements, evaluation status, security controls, deployment targets, price, support |
| **Agent Passport** | Identity, purpose, capability manifest, permitted tools, data scope, risk tier, model/runtime, evaluation, owner, version, cost envelope, approval policy, kill-switch state |

Passports are rendered publicly with a verification link and can be verified offline against the published issuer key.

---

## 7. Agentic Runtime — The Portal Must Act, Not Only Answer

### 7.1 Core Agents (MVP + Near-Term)

| Agent | Responsibility |
|-------|----------------|
| **Partner Onboarding Agent** | Completeness checks, capability tagging, onboarding plans |
| **Partner Match Agent** | Matches partner / skills / capacity / sector / geography to opportunities with score breakdown & evidence citations |
| **Opportunity Qualification Agent** | Extracts need, classifies, identifies missing information |
| **Solution Architect Agent** | Candidate architecture, BOM, implementation plan, risks |
| **FDE Dispatch Agent** | Builds qualified engineering pods with costed options & trade-offs |
| **Academy Coach** | Recommends learning paths, labs, assessments |
| **Proposal Agent** | Drafts proposals, SOWs, milestones, team structures |
| **Partner Health Agent** | Detects inactivity, capability gaps, pipeline & delivery risk |
| **Revenue Attribution Agent** | Maps contribution evidence to configurable commercial rules |
| **AgentOps Agent** | Monitors quality, failures, policy blocks, cost, regression |
| **Ecosystem Strategist** | Detects sector, geographic, talent and solution gaps |

### 7.2 Progressive Autonomy Model

Every agent ships at the lowest useful autonomy level (L0 / L1) and is promoted only on evaluation evidence. Promotion is a formal release decision, not a configuration toggle.

- **L0** — Observe / recommend only  
- **L1** — Propose actions; human gate required  
- **L2** — Execute within strict policy envelope  
- **L3** — Autonomous within published cost & risk bounds  

### 7.3 Tooling & Interoperability

- **MCP** (Model Context Protocol) for tool access — every tool is typed, classified by side-effect class and risk tier.
- **A2A** (Agent2Agent) for peer delegation and capability discovery.
- IBM watsonx Orchestrate used as the enterprise control-plane reference (centralised visibility, governance, Agent Connect).
- i3 E³ owns ecosystem / business workflow governance; IBM and other approved runtimes provide agent execution and orchestration.

### 7.4 Safety & Cost Controls

- Authorisation lives **outside** the model.
- Every invocation carries a cost budget and is attributed to tenant + business object.
- Semantic caching, small-model routing and tenant caps are mandatory.
- Kill-switch is first-class and can be invoked by on-call engineer (act first, review after).

---

## 8. Trust & Evidence Plane (Credential Trust Network)

### 8.1 Design Intent

Employers, vendors and institutions currently re-verify claims independently. Fraud risk suppresses trust. The Credential Trust Network closes this regional infrastructure gap.

### 8.2 Technology Choices

- **W3C Verifiable Credentials Data Model 2.0** (JSON-LD) for the credential itself.
- **Hyperledger Fabric** on OpenShift for the permissioned ledger (hashes, issuers, timestamps, status, pointers only — never PII or documents).
- **HSM-backed issuer keys**.
- Sub-second QR verification by unauthenticated third parties (target p95 < 300 ms).
- Offline verification possible against the published issuer key.

### 8.3 Issuance Flow (T3 Human Gate)

1. Proctored assessment produces evidence artefacts.
2. Assessment Agent proposes issuance.
3. Named human approver confirms (recorded with identity).
4. W3C VC is signed and SHA-256 hash written to the credential channel on Fabric.
5. Verification endpoint returns status only (no personal data).

### 8.4 Privacy Guarantees

- Personal data lives off-chain and is encrypted.
- Ledger stores only proofs.
- Learner erasure request destroys off-chain data and key; ledger hash remains but is unlinkable; erasure certificate is issued.

---

## 9. MVP Feature Set & Acceptance Criteria (13 Capabilities)

| # | Capability | Key Acceptance Criteria |
|---|------------|-------------------------|
| 1 | Partner registration & Digital Passport | Self-register → verified without staff DB edit; Passport renders publicly with verification link |
| 2 | Engineer / FDE Passport | Verified skills with evidence references; self-declared vs verified visually distinct |
| 3 | Academy & certification status | Enrolment → progress tracking → credential-eligible event |
| 4 | Opportunity registration | 180-day exclusivity enforced; duplicate registration blocked with clear message |
| 5 | Partner & engineer matching | Ranked shortlist < 3 s p95; score breakdown + evidence citations; zero mandatory-requirement violations |
| 6 | FDE request & dispatch | 2–3 costed pod options with trade-offs; soft hold expires after 48 h |
| 7 | Solution catalogue | Versioned, with dependencies, deployment targets, SBOM; discoverable by capability search |
| 8 | Lab booking & provisioning | Provisioned ≤ 5 min; hard TTL; auto-teardown; cost metered to tenant |
| 9 | AI Partner Copilot | Natural-language question answered with graph-grounded, cited response |
| 10 | Work Graph foundation | Entities & relationships projected from events; full rebuild < 2 h |
| 11 | Executive Mission Control | 12 KPI tiles resolve from live platform data with zero manual assembly |
| 12 | Basic evidence & attribution | Credential issuance & milestone acceptance produce anchored evidence; contribution event recorded |
| 13 | Credential Trust Network pilot | Signed VC anchored to Fabric; QR verification by unauthenticated third party < 300 ms |

### Explicit MVP Exclusions

| Excluded | Earliest Phase |
|----------|----------------|
| Agent marketplace & monetisation | Phase 4 (months 9–12) |
| Full attribution & settlement engine | Phase 3 |
| Multi-country tenant federation | Phase 4 |
| Automated IBM Partner Plus synchronisation | Phase 2 (assisted export first) |
| Native mobile applications | Post year-one |
| Consortium multi-organisation Fabric governance | Phase 3 |
| Fine-tuned domain models | On evidence only |

---

## 10. Delivery Plan & Team

### 10.1 Twelve-Month Roadmap

| Phase | Window | Engineering Deliverables | Exit Gate |
|-------|--------|--------------------------|-----------|
| **Phase 0 — Foundation** | Weeks 1–4 | Cluster + GitOps, IAM + tenancy, event backbone, schema registry, observability, CI, ADR process, Partner & Opportunity aggregates | Partner can register end-to-end in staging; traces & metrics visible; security baseline clean |
| **Phase 1 — MVP Core** | Weeks 5–12 | Work Graph projection, Passports, Academy + Lab Exchange, Opportunity Exchange, Match + Qualification agents, Trust pilot, Mission Control v1 | All 13 MVP acceptance criteria pass on staging with controlled partner cohort |
| **Phase 2 — Launch Hardening** | Weeks 13–16 | Performance, accessibility, adversarial testing, DR rehearsal, verification API at scale, event-day readiness, launch cohort onboarding | Production live; 16 October demo rehearsed 3× end-to-end without intervention |
| **Phase 3 — Depth** | Months 5–8 | Solution & Engineering Exchange depth, Proposal & Architect agents, Curriculum Mapping, collaboration rooms, contribution ledger, first CRM / IBM connectors | Three paid PoCs converted through the platform; agent estate governed under AgentOps |
| **Phase 4 — Scale** | Months 9–12 | Agent Exchange, full AgentOps, attribution & settlement, country-node federation, public APIs, billing | Second country node on same codebase; marketplace transacting |

### 10.2 First 90-Day Sprint Plan

| Sprint | Weeks | Primary Objective | Demoable Outcome |
|--------|-------|-------------------|------------------|
| S1 | 1–2 | Platform baseline & tenancy | Hello-world service via GitOps with tenant-scoped auth + end-to-end trace |
| S2 | 3–4 | Partner aggregate & registration | Partner registers and appears in the graph |
| S3 | 5–6 | Passports & evidence store | Partner & Engineer Passports render with evidence references |
| S4 | 7–8 | Opportunity aggregate, registration & exclusivity | Deal registration correctly blocks a duplicate |
| S5 | 9–10 | Agentic runtime, MCP broker, Match Agent | Ranked shortlist with citations against real historical data |
| S6 | 11–12 | Academy, labs, assessment, credential issuance & anchoring | Credential issued and verified by QR |
| S7 | 13–14 | Qualification Agent, Copilot, Mission Control | Emailed RFP becomes a scored draft opportunity |
| S8 | 15–16 | Hardening, performance, adversarial, DR, launch rehearsal | Full launch demo runs without intervention |

### 10.3 Team Composition (MVP — 14 FTE)

| Role | FTE | Responsibilities |
|------|-----|------------------|
| Engineering Manager / Delivery Lead | 1 | Backlog, sprint cadence, dependency management, stakeholder reporting |
| Solutions Architect | 1 | ADRs, module boundaries, integration contracts, technical arbitration |
| Backend Engineers | 3 | Domain modules, APIs, event producers/consumers, migrations |
| AI / Agent Engineers | 2 | Agent manifests, orchestration, MCP tools, prompts, evaluation suites |
| Frontend Engineers | 2 | Workspaces, Mission Control, PWA, accessibility |
| Data Engineer | 1 | Graph projection, vector & search pipelines, lakehouse, lineage |
| Platform / SRE | 1 | Clusters, GitOps, observability, DR, on-call |
| Security Engineer | 0.5 | Threat model, IAM, supply chain, adversarial testing, DPA controls |
| QA / Test Engineer | 1 | Test strategy, journey automation, agent regression, release sign-off |
| Product Owner (from Ecosystems) | 0.5 | Acceptance, prioritisation, partner cohort liaison |

### 10.4 Key RACI Decisions

| Decision | Responsible | Accountable | Consulted | Informed |
|----------|-------------|-------------|-----------|----------|
| Architecture changes & ADRs | Solutions Architect | CTO | Engineering leads, Security | Whole team |
| Agent autonomy promotion | AI Engineer | CTO | Security, Operations Manager, QA | Board (quarterly) |
| Release to production | Engineering Manager | CTO | QA, SRE, Security | Ecosystems Manager |
| Data classification & retention | Security Engineer | Data Protection Officer | Legal, CTO | All staff |
| Scope change to MVP | Product Owner | Ecosystems Manager / CTO | Engineering Manager | Board |
| Credential issuance policy | Academy Lead | CTO | Legal, partner institutions | Learners, employers |
| Emergency agent halt | On-call engineer | CTO | — (act first) | Board if customer-impacting |

---

## 11. Security, Privacy & AI Governance Highlights

- **Multi-tenancy**: RLS + partitioned vector collections + purpose-bound access. Cross-tenant leakage is a P1.
- **Prompt injection**: Authorisation outside the model; provenance tagging; no privilege inheritance; adversarial suite gates every promotion.
- **Kenya Data Protection Act**: Confirmed by DPO and external counsel before any production processing of personal data.
- **Supply chain**: SBOM for every solution; signed container images; dependency & CVE posture reviewed monthly.
- **AgentOps**: Quality, cost, policy blocks, regression and kill-switch metrics published and reviewed weekly.
- **Evidence by construction**: No retrospective “upload proof” workflows.

---

## 12. Technical Risk Register (Selected High-Impact Items)

| ID | Risk | L | I | Mitigation | Owner |
|----|------|---|----|------------|-------|
| TR-01 | Scope sprawl — platform attempts all thirteen exchanges at once | H | H | Hard MVP boundary; scope changes require Ecosystems Manager + CTO approval | Engineering Manager |
| TR-02 | Agent output quality insufficient for partner-facing use at launch | M | H | Deterministic scoring + model explains only; L0/L1 autonomy at launch; golden sets before agents; human gates on everything partner-visible | CTO |
| TR-03 | Model / inference cost outruns revenue | M | H | Cost envelopes, tenant caps, semantic caching, small-model routing, cost-per-outcome reported monthly | CTO |
| TR-04 | Cross-tenant data leakage | L | VH | RLS, partitioned collections, per-release leakage suite, immediate P1 path | Security Engineer |
| TR-08 | Prompt injection through customer documents causes unintended action | M | H | Authorisation outside model; provenance tagging; no privilege inheritance; adversarial suite | Security Engineer |
| TR-11 | Launch-date pressure causes security or evaluation gates to be waived | M | VH | Gates are release-blocking by policy; only CTO may waive in writing with remediation date; waivers reported to board | CTO |
| TR-13 | Connectivity conditions degrade launch demonstration | M | M | Offline-capable verification; local-network rehearsal; pre-seeded data; three full rehearsals | Platform Lead |

Full register is reviewed monthly; any H/H or VH risk is reported to the board with named mitigation owner and review date.

---

## 13. Best-of-Breed Innovations Incorporated

1. **Work Graph as system of context** — not a side-effect database but the primary integration and reasoning surface (GraphRAG-ready).
2. **Agents propose, policy disposes** — deterministic core protects money, permissions and credentials; LLMs stay on the probabilistic edge.
3. **Progressive autonomy** — promotion is a release decision backed by evaluation evidence, not a configuration toggle.
4. **Evidence by construction** — every meaningful transition produces an immutable, hash-anchored proof as a by-product.
5. **Open protocols at every seam** — MCP, A2A, CloudEvents, W3C VC 2.0, OpenTelemetry, SPIFFE/SPIRE.
6. **Portability-first** — same codebase runs on ROKS (Frankfurt), Nairobi sovereign node and Sovereign AI Appliance.
7. **PWA + offline-tolerant design** — designed for real East African connectivity conditions.
8. **Credential Trust Network** — permissioned Fabric + W3C VC for independent, sub-second, offline-capable verification without exposing personal data.
9. **Digital Passports** — machine-readable, signed, publicly verifiable profiles for partners, engineers, solutions and agents.
10. **Cost as a first-class signal** — every agent invocation is budgeted and attributed; FinOps is continuous, not quarterly.
11. **Multi-tenant from line one** — tenancy is never retrofitted.
12. **Modular monolith with clean boundaries** — optimised for a 14-person squad; services are split only on evidence of need.

---

## 14. Recommendations for Immediate Action

1. Adopt this document as the engineering contract and the 12 Architecture Principles as binding.
2. Fund and resource the 14-FTE MVP squad for the 90–120 day window.
3. Stand up the ADR process, Architecture Forum and weekly AgentOps review in Week 1.
4. Treat the 13 MVP acceptance criteria as the only release gate for the 16 October launch.
5. Keep the explicit exclusion list public and defended — do not allow Phase 3/4 capability to leak into the launch demo.
6. Confirm Skillsoft and priority certification-body licensing in writing before any content ingestion pipeline is built.
7. Confirm Kenya Data Protection Act position with the DPO before any production personal-data processing.
8. Rehearse the launch demonstration three times end-to-end, including offline fallback, before 16 October.

---

## Appendix A — Illustrative PostgreSQL Schema Fragments

```sql
CREATE TABLE organization (
  id            UUID PRIMARY KEY,
  tenant_id     UUID NOT NULL,
  legal_name    TEXT NOT NULL,
  country_code  CHAR(2) NOT NULL,
  org_type      TEXT NOT NULL CHECK (org_type IN
    ('partner','customer','academic','vendor','tvet')),
  tier          TEXT,
  status        TEXT NOT NULL DEFAULT 'prospect',
  attributes    JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_tenant_isolation ON organization
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

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


Appendix C — Glossary (Selected)









































TermDefinitionA2AAgent2Agent protocol (Linux Foundation) for agent-to-agent delegationAgentOpsOperational discipline of evaluating, observing, governing and controlling an agent estateCloudEventsCNCF portable event envelope specificationGraphRAGRetrieval-augmented generation where the retrieval substrate is a property graphMCPModel Context Protocol — open standard for agent-to-tool accessROKSRed Hat OpenShift Kubernetes Service on IBM CloudVCW3C Verifiable Credential (Data Model 2.0)Work GraphCanonical property graph of ecosystem entities, relationships and evidence; the system of context for E³

Appendix D — Qualification & Disclaimer
This is an engineering specification and implementation guide, not a binding IBM programme commitment, regulatory determination, security certification or financial forecast. Specific IBM and Red Hat programme eligibility, licensing, availability and commercial terms must be confirmed with the relevant vendor teams before any customer commitment is made. Skillsoft and certification-body content licensing must be confirmed in writing before any ingestion pipeline processes licensed material. Data protection obligations under the Kenya Data Protection Act must be confirmed by the Data Protection Officer and external counsel before production processing of personal data. Statements about IBM product capability reflect publicly available information as at September 2026 and should be re-verified before external use.

Document Control

Prepared by: i3 Solutions Architecture & Business Consulting

Reviewed for: Engineering Review & Board Endorsement

Next Review: After Phase 1 MVP gate (target: Week 12)
Connect. Build. Certify. Deploy. Monetize.