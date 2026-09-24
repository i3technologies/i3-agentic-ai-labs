# i3 Precision Marketing Cloud (i3 PMC)
## Master Technical Implementation Guide — Senior Solutions Architect Review & Consolidated Blueprint

**Prepared for:** Philip Mulala, CEO, i3 Technologies
**Prepared by:** Solutions Architecture Review
**Classification:** Internal — Strategy & Architecture
**Version:** 2.0 (Consolidated — supersedes v0.1 Technical Build Document and v1.0 Technical Implementation Guide)
**Date:** September 2026

---

## Reviewer's Note

This document reconciles the two source artifacts you provided — the **Technical Build Document (v0.1)**, which grounds i3 PMC in a competitive/commercial rationale and a phased 12-month delivery plan, and the **Technical Implementation Guide (v1.0)**, which is architecturally richer on the Agentic AI layer but drifts from the original 4-phase roadmap into an 8-wave roadmap without reconciling headcount, dependencies, or the shared-infrastructure risk already flagged in the Build Document.

Three structural issues needed resolving before this could be called implementation-ready, and I have resolved them below:

1. **Two conflicting roadmaps existed.** The Build Document specifies 4 phases across 12 months; the Implementation Guide specifies 8 waves across 12 months with different exit criteria and no team mapping. I have merged these into **one roadmap (Section 12)** that keeps the Build Document's phase-gate discipline and folds the Implementation Guide's wave-level detail in as sub-milestones.
2. **The Agentic AI layer was described twice at different levels of maturity** (Build Doc: "three AI-native capabilities from Release 1.0"; Implementation Guide: 11 signature innovations plus a full Agent Platform). I have kept the full Agent Platform architecture — it is materially better engineering — but flagged which of the 11 innovations are realistic for **Release 1.0 (MVP)** versus **Release 2.0+**, because attempting all 11 in month one is a scope-creep risk the Build Document itself warns against in Section 12.
3. **Shared-infrastructure dependency was under-weighted.** Both source documents note i3 PMC will run on the existing 750+ VM ROKS/IBM Power estate shared with 11 other proprietary solutions and i3 Academy cohorts, and that the IBM Cloud credit balance and Red Hat subscription renewal date need re-verification. This is carried forward as **Risk #1** in Section 16, not a footnote — it is the single biggest delivery risk in this document and should be checked before Phase 0 kicks off, independent of the sales/partner activities described in the IBM Ecosystem Partner Strategy materials.

Everything else in this guide is drawn directly from your source documents, reorganized into a single build-ready reference. Where I've added architect judgment rather than restating source content, it is marked **[Architect's recommendation]**.

---

## Table of Contents

1. Executive Summary
2. Competitive Landscape & Strategic Rationale
3. Product Vision, Scope & Positioning
4. Reference Architecture — 12 Capability Domains
5. Core Data Model (Consent & Profile Core)
6. Agent Platform — First-Class Service Design
7. Core Agent Portfolio & Tool-Calling Contracts
8. Signature Agentic AI Innovations — Release Prioritization
9. Real-Time Decisioning & Next-Best-Action
10. Journey, Campaign & Omnichannel Execution
11. Integration Layer (Connect Hub)
12. Event-Driven Backbone & Microservice Topology
13. Technology Stack & API Surface
14. Security, Governance, Guardrails & Human-in-the-Loop
15. AI Cost, Evaluation, Observability & Reliability
16. Non-Functional Requirements (SLOs)
17. Consolidated Implementation Roadmap
18. Team Structure & Delivery Model
19. Commercial Packaging & Pilot Strategy
20. Production Readiness Checklist & Golden Rules
21. Risk Register
22. Appendix — Glossary & API Examples

---

## 1. Executive Summary

i3 Precision Marketing Cloud (i3 PMC) is a sovereign, Agentic AI-native Customer Engagement and Decisioning platform for regulated enterprises across Africa — banks, telecoms, insurers, utilities, government and public sector, retail, education and healthcare. It targets functional parity with **HCL Unica's** module set (Campaign, Journey, Interact, Deliver, Plan, Optimize, Discover, Link) while differentiating on three axes:

1. **Sovereign, in-region hosting** on i3's existing IBM Cloud + Red Hat OpenShift (ROKS) estate, rather than an offshore private cloud.
2. **Single consumption-based commercial model** (profiles + messages + journey executions + AI agent actions + decision calls) instead of the fragmented per-module pricing seen in Salesforce Marketing Cloud and Adobe's suite.
3. **Native Agentic AI from day one** — campaign design, next-best-action and content generation are AI-assisted by construction, not bolted on, built on i3's existing Agentic AI Lab.

i3 PMC is designed to slot in as a twelfth solution alongside i3's eleven existing proprietary ROKS solutions (GridSentinel, OTShield, MaxAR, AssetChain, OT Digital Twin, AirportOS, AquaSense, RailMind, EvalOS, Admissions AI, Research Lab Dashboard), reusing the same Kubernetes-native delivery pattern, the same shared lab infrastructure, and the same IBM/Red Hat partner relationship underwriting i3's Silver Business Partner status.

The architectural core is a **closed-loop agentic decisioning cycle**, replacing the traditional linear marketing-automation model:

```
Traditional:  Customer Data → Segment → Campaign → Message → Measure

i3 PMC:       Customer Signals → Customer Intelligence → AI Reasoning →
              Business Policy/Constraints → Next-Best-Action → Agent Planning →
              Human/Policy Approval → Execution → Customer Response →
              Outcome Measurement → Learning/Optimisation → (loop)
```

AI does not replace the enterprise platform — AI operates the platform through governed tools, data, policies and workflows. This is the non-negotiable design principle underpinning every section below.

---

## 2. Competitive Landscape & Strategic Rationale

### 2.1 Reference Platform — HCL Unica

HCL Unica (formerly IBM Unica) is the closest commercial analogue and functional baseline: Campaign, Plan, Optimize, Interact, Journey, Deliver, Discover, Link, plus a shared Platform/Offer Management/Insights backbone. It is cloud-deployable (Docker or native), positioned for regulated industries on data-governance grounds. Its 2026 refresh (**Unica+ 26.1**) merges the classic suite with an AI layer ("MaxAI") that converts natural-language prompts into campaign flowcharts. Pricing is modular, usage-based and undisclosed.

### 2.2 Comparative Matrix

| Platform | Category Leadership | Deployment Model | Key Limitation vs. i3 PMC Target |
|---|---|---|---|
| HCL Unica / Unica+ | Full-suite breadth; sovereignty-friendly positioning | Any cloud, Docker or on-prem | No African data-centre presence; offshore USD/EUR licensing |
| Salesforce Marketing Cloud | Real-time engagement inside Customer 360/CRM | Public multi-tenant cloud | Fragmented per-module pricing; no regional hosting |
| Adobe Campaign | Cross-channel + inherited MRM (Neolane) | Adobe cloud / on-prem | Weaker scalability/support ratings; ageing core |
| Adobe Marketo Engage | B2B lead management | Adobe cloud | Optimized for B2B, not B2C/telco/bank transactional scale |
| SAS Customer Intelligence 360 | AI decisioning, advanced modelling | SAS Viya cloud/hybrid | Analytics/CDP-centric; thin execution layer |
| Redpoint Interaction | Agile CDP, fast unification | Cloud/hybrid | Narrower MRM and batch-campaign depth |
| ActionIQ | Self-service CDP usability | Cloud | CDP-only — needs Campaign/Deliver/Interact layer |
| HubSpot Marketing Hub | Ease of use, fast time-to-value | Multi-tenant SaaS | SMB/mid-market scale only |
| MoEngage | Behaviour-triggered lifecycle messaging | Cloud | Lighter MRM and contact-optimization layers |

*Sources: Gartner Peer Insights, HCLSoftware documentation, TrustRadius, Capterra/GetApp (2026).*

### 2.3 Strategic Takeaway

No reviewed platform combines full-suite breadth, in-region sovereign hosting, a single transparent commercial model, **and** native agentic AI. That combination — not any single feature — is the commercial rationale for i3 PMC. The functional target is Unica-equivalent module coverage; the differentiation is delivery model, data residency, pricing simplicity and agentic depth.

---

## 3. Product Vision, Scope & Positioning

### 3.1 Vision

Give African enterprises a single, regionally-hosted platform to plan, target, personalize and measure customer engagement across every channel their customers actually use — SMS, WhatsApp, USSD, email, push, web, call centre, branch/POS, ATM — without customer data leaving the jurisdictions where it was collected.

### 3.2 Recommended Category Positioning

**Primary:** i3 PMC — Enterprise Agentic Customer Engagement Cloud
**Alternative commercial line:** "The Sovereign Agentic Customer Engagement Platform"

Deliberately avoid positioning as: bulk SMS platform, WhatsApp broadcaster, chatbot, campaign manager, CRM, CDP, or generic marketing-automation tool — these categories are crowded and undersell the platform. Position instead around the convergence of nine capabilities: Customer Data, Customer Intelligence, Agentic AI, Real-Time Decisioning, Journey Orchestration, Omnichannel Engagement, Enterprise Governance, Sovereign Infrastructure, Measurable Business Outcomes.

### 3.3 Module Scope — Release 1.0 Target Parity

| i3 PMC Module | Unica Equivalent | Function |
|---|---|---|
| Audience Studio | Campaign + Discover | Segmentation, targeting, suppression, multi-wave batch execution |
| Journey Orchestrator | Journey | Visual, goal-based multi-step journey builder, real-time state tracking |
| Engage (Real-Time) | Interact | Sub-second NBA and offer personalization at digital/physical touchpoints |
| Messenger | Deliver | Omnichannel dispatch: SMS, WhatsApp Business API, email, push, USSD |
| Plan & Resource Manager | Plan | Marketing calendar, budget, approval workflow, creative-asset management |
| Contact Optimizer | Optimize | Cross-channel contact-frequency and offer-arbitration engine |
| Insight Studio | Insights/Discover | Pre-built and ad-hoc performance and behavioural analytics |
| Connect Hub | Link | Low-code connector framework: CRM, core banking/billing, POS, MarTech |
| Consent & Profile Core | Platform/CDP | Unified customer profile, consent ledger, identity resolution — system of record |

### 3.4 Explicitly Out of Scope — Release 1.0

- Paid media / programmatic ad-buying integration (Release 2.0 candidate via Connect Hub)
- Native mobile SDKs for in-app messaging (Release 2.0)
- Full social-listening module (build-vs-partner evaluation, Release 2.0)
- Voice Agent, Agent Marketplace (Release 2.0/P2 per Build Priority Matrix — Section 20)

**[Architect's recommendation]** Hold this scope line firmly. The Build Document itself calls out "feature parity with a mature 20+ year Unica suite" as a major scope-creep risk (Section 21, Risk 3). Every module or agent not listed in 3.3 should require an explicit change-control decision, not silent inclusion because "the Implementation Guide mentioned it."

---

## 4. Reference Architecture — 12 Capability Domains

The platform is organized into layered, independently deployable capability domains on a single shared control plane:

```
 1. Experience Layer          Marketer Console · Sales Workspace · Customer Service
                               Console · Analyst Dashboard · Admin · Executive AI Copilot
                                            │
 2. AI Copilot / Agent        Campaign Agent · Journey Agent · Content Agent · Data Agent
    Experience                CX Agent · Sales Agent · Analytics Agent · Optimizer Agent
                                            │
 3. Agent Orchestration       Planner · Tool Registry · Memory · Guardrails · Approval ·
                               Policy Engine · Agent State · Evaluation · Audit · Marketplace
                                            │
 4. Decisioning &             NBA · Next-Best-Offer · Propensity · Churn · CLV · Scoring ·
    Intelligence               Recommendations · Experimentation · Optimisation
                                            │
 5. Journey & Campaign        Audience Studio · Campaign Manager · Journey Engine · Offers ·
    Platform                  Content · MRM · Automation · Contact Policy
                                            │
 6. Customer Data Platform    Profile · Identity · Consent · Events · Segments · Features ·
                               Customer 360 · Interaction History · Knowledge
                                            │
 7. Omnichannel Messaging     WhatsApp · SMS · Email · USSD · Push · Web · POS · ATM ·
                               Contact Centre · Branch · (Future: Social / Ads)
                                            │
 8. Connect Hub               CRM · Core Banking · Billing · ERP · POS · eCommerce ·
                               Data Lake · DWH · APIs · Webhooks · Files · Streaming
                                            │
 9. IBM Cloud / Red Hat       Kubernetes · Kafka · PostgreSQL · Redis · Object Storage ·
    OpenShift                 Observability · IAM · Secrets · CI/CD · Security
```

**Architecture Principles**

- **Cloud-native, container-first** — every service ships as an OCI image on ROKS, consistent with i3's 11 existing solutions.
- **API-first** — every module exposes REST/GraphQL before it gets a UI, so Connect Hub and third parties integrate the same way internal modules do.
- **Event-driven core** — customer and campaign events flow through a durable event bus (Kafka) so Journey, Engage and Insight Studio share one real-time truth.
- **Composable, not monolithic** — modules are independently deployable microservice groups on a shared control plane.
- **Sovereign by default** — primary data residency in-region; multi-tenant control plane isolated per customer at namespace and encryption-key level.

### 4.1 Deployment Topology

i3 PMC deploys on the same ROKS foundation already running i3's eleven proprietary solutions, on IBM Cloud with IBM Power Systems underpinning the shared 750+ VM lab estate. Each customer tenant is provisioned as an isolated OpenShift namespace with its own encryption keys and, where a regulator requires it, its own dedicated node pool and data-residency zone. Non-production environments (dev/test/UAT) run from existing i3 Smart Labs capacity, keeping incremental infrastructure spend limited to production-grade capacity only.

---

## 5. Core Data Model (Consent & Profile Core)

The Consent & Profile Core is the single system of record every module reads from and writes to.

| Entity | Purpose | Key Attributes |
|---|---|---|
| Customer Profile | Unified, deduplicated view of a person/account across channels | Identity keys, demographic/firmographic attributes, lifecycle stage, resolved device/channel IDs |
| Consent Record | Auditable record of what a customer agreed to, by channel/purpose | Channel, purpose, status, timestamp, source, expiry/renewal date |
| Segment | Named, reusable audience definition | Rule definition or ML-scored membership, owner, refresh cadence |
| Campaign | Planned/executing marketing initiative | Objective, budget, owning team, linked segments/offers, schedule |
| Journey | Multi-step orchestrated customer experience | Entry criteria, step sequence, decision splits, goal/exit criteria |
| Offer | A proposition presentable to a customer | Eligibility rules, priority/arbitration weight, valid channels, expiry |
| Interaction Event | Timestamped record of a customer touching any channel | Channel, event type, context payload, linked campaign/journey |
| Message Template | Reusable, channel-specific content asset | Channel, localisation variant, personalization tokens, approval status |

**Extended entity set (production-scale reasoning):** Account, Party, Household, Organisation, Identity, Device, Channel, Preference, Product, Subscription, Transaction, Conversation, Prediction, Recommendation, AgentAction, Approval, Outcome.

**Identity Resolution:** Phone, Email, Customer ID, Account ID, Device ID, CRM ID, National identifier, Cookie/web identity, Loyalty ID. Deterministic matching first, then probabilistic — **never allow probabilistic matches to silently overwrite authoritative identity records.**

**Consent as Central Policy Service:** every outbound request passes through the Consent Service — eligible? channel permitted? purpose permitted? frequency permitted? campaign permitted? → ALLOW/DENY, enriched with provenance, evidence, expiry, purpose, channel, jurisdiction, lawful basis, suppression lists and regulatory policy. **Consent is enforced at the API layer before any channel dispatch — no exceptions.**

---

## 6. Agent Platform — First-Class Service Design

**[Architect's recommendation — highest-value architectural decision in this document]** Do not implement agents as ad-hoc prompts inside individual microservices. Build one formal, shared Agent Platform that every current and future AI capability reuses:

| Component | Function |
|---|---|
| Agent Registry | Versioned agent definitions — instructions, tools, models, policies, evaluation sets |
| Agent Runtime | Task lifecycle, context assembly, plan generation, tool execution, observation, replanning |
| Agent Planner | Multi-step plan generation with constraints |
| Tool Registry | Controlled, schema-validated enterprise tools with risk tiers |
| Memory Service | Working, Conversation, Semantic, Customer, Organisational and Agent memory types |
| Policy Engine | Identity, tenant, role, tool, data, business and regulatory policy evaluation |
| Approval Service | Human-in-the-loop queues with risk-based routing |
| Guardrail Service | Input / output / tool guardrails and prompt-injection defence |
| Agent Evaluation | Automated metrics, regression datasets, canary and shadow modes |
| Observability & Audit | Full provenance — who, what, when, why, model, data, tool, policy, result |
| Agent Marketplace | Internal catalogue of reusable, governed agents |

### 6.1 Agent State Machine

```
CREATED → PLANNING → WAITING_FOR_TOOL → WAITING_FOR_APPROVAL → EXECUTING →
OBSERVING → REPLANNING → COMPLETED
Terminal (non-happy-path): FAILED · CANCELLED · ESCALATED · BLOCKED
```

**The LLM must never be the sole owner of workflow state** — the workflow engine owns it. Hard limits enforced independent of the model: token budget, execution time, tool-call count, monetary impact, recursion depth.

### 6.2 Tool-Calling Contract

Every tool declares: `name`, `permissions`, `input/output schema`, `risk_level`, `requires_approval`, `audit_required`.

Representative tools: `get_customer`, `get_account`, `get_balance`, `create_ticket`, `create_campaign`, `send_message`, `schedule_message`, `update_crm`, `search_knowledge`, `request_human`.

---

## 7. Core Agent Portfolio & Tool-Calling Contracts

| Agent | Responsibility |
|---|---|
| Marketing Strategy / Campaign Agent | Natural-language brief → objective, audience, eligibility, exclusions, channels, timing, offers, budget, expected outcomes, risks, required approvals. **Produces a plan, not immediate execution.** |
| Journey Architect Agent | Builds goal-based multi-step journeys: eligibility, consent, previous-engagement checks, channel sequencing, wait timers, response branching, human hand-off |
| Content Agent | Generates WhatsApp/SMS/email/push copy, subject lines, CTAs, variants, translations. Pipeline: Generate → Brand validation → Compliance → Policy → Hallucination checks → Human approval → Publish |
| Customer Intelligence Agent | Maintains dynamic Customer 360; computes Customer State = Historical + Recent Events + Intent + Predicted Behaviour + Business Context + Consent + Policy |
| Sales Agent | Lead detection, qualification, product matching, objection handling, offer recommendation, CRM update, appointment booking, human hand-off |
| Customer Service Agent (Nuru evolution) | Answers questions, retrieves account info, checks status, explains bills, creates tickets, escalates, summarises, detects urgency — via explicit tools only |
| Experimentation Agent | Proposes A/B, multivariate, holdout, champion/challenger, channel/timing/offer/content experiments; monitors outcomes |
| Compliance / Brand Agent | Pre-launch checks — consent, prohibited content, disclosures, eligibility, frequency, jurisdiction. Output: **PASS / WARNING / BLOCK** |
| QA Agent | Detects dead-end branches, missing conditions, invalid templates, circular journeys, channel incompatibility, consent gaps |
| Data-Quality Agent | Monitors feed volume anomalies, duplicates, invalid identifiers, schema drift; opens incidents; can suppress downstream campaigns |
| Operations / SRE Agent | Diagnoses OpenShift/Kafka/PostgreSQL/Redis/LLM/provider incidents; recommends remediation; restarts low-risk components under policy |

### 7.1 Permission Model — Risk Tiers

| Tier | Examples | Default Behaviour |
|---|---|---|
| 0 — Read | Retrieve knowledge, profile, analytics | No approval |
| 1 — Low-risk action | Add tag, create draft, generate content | Configurable |
| 2 — Customer-facing | Send message, initiate journey, assign lead | Policy-dependent |
| 3 — Business-impacting | Change offer, issue discount, alter budget | **Human approval by default** |
| 4 — High-risk | Financial transaction, credit decision, irreversible account action | **AI recommendation only — never autonomous** |

---

## 8. Signature Agentic AI Innovations — Release Prioritization

The source material describes eleven high-value agentic innovations. **[Architect's recommendation]** Building all eleven in Release 1.0 contradicts the Build Document's own scope discipline (Section 3.4). They are re-sorted below by realistic release wave.

### 8.1 Release 1.0 (MVP-critical)

| # | Innovation | Summary |
|---|---|---|
| 1 | **Agentic Campaign & Journey Builder** | Natural-language brief → Campaign Strategy Agent produces a complete validated plan (objective, segment, suppressions, journey graph, content variants, channel strategy, risk flags, required approvals). Visual canvas renders it. AI generates → platform validates → human approves → execution begins. Recommend-and-approve by default. |
| 2 | **Multi-Agent Orchestration with Structured Contracts** | Specialised agents (Campaign Manager, Audience, Content, Journey, Compliance, Optimizer, Analytics, Operations) collaborate via structured tasks and Kafka events, not free-form chat. Each declares capabilities, tools, permissions, risk level, approval requirements — reproducible, auditable workflows. |
| 3 | **Next-Best-Action Engine with Explicit "Do Nothing"** | p95 < 200 ms pipeline: Event → Feature Retrieval → Eligibility → Offer Candidates → Business Rules → ML Scoring → Contact Frequency → AI Reasoning → Policy Constraints → Ranked Actions. Actions include SEND OFFER, START JOURNEY, ROUTE TO AGENT, REQUEST DOCUMENT, TRIGGER PAYMENT REMINDER, ESCALATE, and critically **DO NOTHING** — the system must be able to decide contact is inappropriate. |
| 4 | **Multilingual African AI with Cultural Context** | Language Detection → Translation/Localisation → Brand Terminology → Compliance Validator → Channel Rendering. Covers English, Kiswahili, Sheng, French, Arabic, Portuguese and local languages. Goal is compliant, high-conversion, culturally appropriate messaging — not literal translation. |
| 5 | **AI Agent Assist for Human Employees** | While a human agent handles a customer, AI retrieves context, finds policy, suggests responses, proposes case classification, surfaces NBA. Human retains final control — lowest-risk deployment pattern, and generates valuable evaluation data for later autonomy. |

### 8.2 Release 2.0 (post-MVP, once governance is proven)

| # | Innovation | Summary |
|---|---|---|
| 6 | **Autonomous Campaign Optimisation with Policy Guardrails** | Optimisation Agent observes delivery/engagement/conversion/complaints/fatigue post-launch, detects anomalies, recommends or auto-applies changes within pre-defined policy limits for low-risk campaigns. |
| 7 | **Campaign & Agent Simulation Environment (Digital Twin)** | Pre-production dry-run against a synthetic customer population (price-sensitive, high-value, dormant, complainer, digital-first, low-connectivity). Surfaces expected engagement, consent failures, fatigue risk, budget consumption, edge cases before real customers are touched. |
| 8 | **Customer Service Agent Platform (Nuru evolution)** | Nuru evolves from conversation retrieval (ChromaDB) into a full Service Agent — answers, retrieves account info, checks status, creates tickets, updates CRM, escalates, detects urgency — through explicit permissioned tools. |
| 9 | **Autonomous QA, Data-Quality & Operations Agents** | QA Agent inspects journeys for structural defects; Data-Quality Agent monitors feeds and blocks downstream campaigns on threshold breach; Ops/SRE Agent diagnoses infrastructure incidents. |
| 10 | **Knowledge Graph + Hybrid RAG 2.0** | Beyond vector search: ingestion → classification → chunking → embedding + keyword index + structured DB + graph relationships. Enterprise Knowledge Graph models Customer–Account–Product–Segment–Campaign–Agent relationships for reasoning pure embeddings can't support. |
| 11 | **Automated Flowchart QA (Enterprise Test Engine pattern)** | Automated testing of campaign flowcharts before go-live, reusing i3's existing Enterprise Test Engine blueprint line. |

### 8.3 Industry-Specific Signature Use Cases (apply once core agents are live)

| Industry | Signature Agentic Use Case |
|---|---|
| Banking | Dormant-account reactivation with consent/complaint suppression; real-time NBA at ATM/branch; payment-reminder journeys with channel fallback |
| Telecom | Churn-prevention multi-agent system (propensity + offer arbitration + contact optimiser); prepaid recharge journeys; network-issue proactive messaging |
| Insurance | Policy-renewal journeys with personalised upsell; claims-status conversational agent; risk-based next-best-product |
| Utilities | Bill-payment reminders with USSD/SMS fallback; outage proactive notification + restoration follow-up |
| Retail/eCommerce | Abandoned-cart recovery with inventory-aware offers; post-purchase cross-sell; loyalty reactivation |
| Education | Applicant conversion journeys; fee-payment reminders; alumni engagement |
| Healthcare | Appointment reminders + no-show recovery; medication adherence journeys; patient education agents (strictly governed) |
| Government / Public Sector | Citizen-service notifications; benefit eligibility journeys; complaint intake and routing agents |

---

## 9. Real-Time Decisioning & Next-Best-Action

**NBA Pipeline (target p95 < 200 ms):**

```
Customer Event → Feature Retrieval (Redis feature store) → Eligibility →
Offer Candidate Generation → Business Rules → ML Scoring → Contact Frequency →
AI Reasoning → Policy Constraints → Ranked Actions → Selected Action (incl. DO NOTHING)
```

**Contact Optimizer:** optimises message frequency, channel, time, offer, audience, sequence, campaign collision and fatigue. Example: a customer who received SMS 2 hours ago and WhatsApp yesterday has a colliding SMS campaign suppressed or rescheduled automatically.

**Experimentation Framework:** native A/B, multivariate, holdout, champion/challenger, channel/timing/offer/content experiments. Attribution models: first-touch, last-touch, linear, time-decay, position-based, experiment-based incremental lift.

---

## 10. Journey, Campaign & Omnichannel Execution

**i3 Engage** is retained and elevated as the Omnichannel Execution Fabric — **agentic AI decides; Engage executes.** Reuse from existing Engage:

- WhatsApp Business API, SMS (Africa's Talking), Email (Brevo) integrations
- Message templates, logs, delivery receipts, Kafka events
- n8n integration patterns, conversation history, human inbox
- Nuru AI conversation embeddings (ChromaDB) — migrate behind AI Gateway/Memory Service

**Additions required:**

- Provider-agnostic channel adapters (common interface: `send`, `schedule`, `cancel`, `validate`, `get_status`, `process_delivery_receipt`) covering WhatsApp, SMS, Email, Push, USSD
- Message policy engine, AI content validation, delivery optimisation, channel selection, frequency control
- Conversation intelligence, agent hand-off API, campaign attribution, deliverability intelligence

---

## 11. Integration Layer (Connect Hub)

Connect Hub is the low-code connector framework through which i3 PMC exchanges data with each customer's existing systems, mirroring Unica Link's role.

**Priority Connector Catalog:**

- CRM and core banking/billing systems (batch and event-driven sync)
- WhatsApp Business API, SMS aggregators, USSD gateways relevant to East African carriers
- Email delivery providers (SMTP relay + provider APIs) with deliverability/reputation monitoring
- POS, ATM, branch systems for real-time offer presentment via Engage
- Enterprise data warehouse/data lake for analytics hand-off and model training
- Identity and access: Keycloak/Red Hat SSO plus customer-side SAML/OIDC federation

**Integration Pattern:** all connectors built on **Red Hat Fuse (Apache Camel)** so new connectors follow a consistent development/testing/monitoring pattern rather than being bespoke per customer — directly reusing i3's existing Red Hat partner competency.

---

## 12. Event-Driven Backbone & Microservice Topology

**Kafka is the platform backbone.** Event envelope extends the existing Engage taxonomy with a CloudEvents-style structure: `event_id`, `event_type`, `event_version`, `occurred_at`, `tenant_id`, `source`, `subject`, `correlation_id`, `trace_id`, `data`.

**Key event families:** `customer.*`, `identity.*`, `consent.*`, `interaction.*`, `conversation.*`, `campaign.*`, `journey.*`, `offer.*`, `message.*`, `agent.*`, `prediction.*`, `nba.*`, `experiment.*`, `conversion.*`

**Recommended bounded-context services (start focused, do not build all on day one):**

`identity-service` · `tenant-service` · `profile-service` · `consent-service` · `segment-service` · `campaign-service` · `journey-service` · `offer-service` · `decision-service` · `optimizer-service` · `content-service` · `messenger-service` · `conversation-service` · `agent-service` · `tool-service` · `memory-service` · `knowledge-service` · `analytics-service` · `experiment-service` · `notification-service` · `connector-service` · `audit-service` · `approval-service` · `billing-service`

---

## 13. Technology Stack & API Surface

| Layer | Stack |
|---|---|
| Frontend | React + TypeScript, Next.js (or equivalent), i3 Design System, WebSockets/SSE. Apps: Marketer Console, Agent Workspace, Customer Service Console, Executive Dashboard, Admin Console, Developer Portal |
| Backend | Java/Spring Boot (enterprise domain, decisioning, orchestration, high-volume APIs); Node.js/TypeScript (AI orchestration, integrations, lightweight services); Go selectively (ultra-low-latency, high-throughput) |
| Data — system of record | PostgreSQL (profiles, campaigns, journeys, offers, consent, config, approvals, audit metadata) |
| Data — real-time | Redis (features, session/journey state, caching, rate limits, idempotency, NBA low-latency data) |
| Data — events | Kafka (events, async workflows, streaming, integration) |
| Data — search/behavioural | Elasticsearch (behavioural/event search) |
| Data — assets | Object storage (documents, campaign assets, exports, reports, model artifacts, archives) |
| Data — semantic | Vector store (semantic knowledge, RAG, conversation retrieval) |
| API surface | REST, GraphQL, Webhooks, Async events, Streaming. Key endpoints: campaign draft/approve/execute, journey publish, next-best-action, message send, agent task creation/approval, customer 360 retrieval |
| Security | Keycloak/Red Hat SSO, OIDC, OAuth 2.0, JWT, mTLS, API gateway (Kong or Red Hat 3scale), rate limiting, WAF, schema validation, tenant enforcement (derived from authenticated context, never trusted from client), RBAC + ABAC |
| Integration runtime | Red Hat Fuse / Apache Camel |
| Platform ops | ROKS on IBM Cloud, IBM Cloud Object Storage, Prometheus/Grafana, GitOps (ArgoCD/Tekton) |

---

## 14. Security, Governance, Guardrails & Human-in-the-Loop

**AI Policy Engine Flow:**

```
Agent Request → Identity → Tenant → Role → Tool Permission → Data Permission →
Business Policy → Regulatory Policy → Risk Classification → Approval Requirement → Execution
```

Every action records: **who, what, when, why, model, data, tool, policy, result.**

**Guardrails:**

- **Input** — prompt injection, malicious instructions, sensitive-data requests, unauthorised instructions
- **Output** — prohibited content, hallucination, unsupported claims, brand policy, compliance, privacy
- **Tool** — authorisation, parameters, customer scope, action risk, approval status

**Prompt-Injection Defence Hierarchy:** `System policy > Developer policy > Business policy > User instruction > Retrieved content`. Retrieved documents are treated as **data, never trusted instructions**; content provenance and trust classification are mandatory.

**Human-in-the-Loop Approval Centre:** approval card shows AI-proposed campaign, audience size, channels, expected objective, risk level, reasoning. Actions: **Approve / Reject / Edit.** Existing Nuru human-takeover and low-confidence review queues become platform-wide mechanisms.

### 14.1 The Agentic Safety Triangle

> **Every autonomous action is executable only when Business Policy ∧ Data Authorisation ∧ Security Authorisation are all simultaneously satisfied.** This is the non-negotiable production safety invariant for the entire platform.

### 14.2 Baseline Compliance Posture

- **Data residency:** primary customer data held in-region; cross-border transfer only where contractually and legally permitted
- **Regulatory alignment:** Kenya Data Protection Act (2019) as baseline, with per-country adaptation across i3's 12 country teams; GDPR-equivalent controls for EU-linked data subjects
- **Encryption:** at rest (per-tenant keys) and in transit (TLS 1.2+ minimum) across all layers
- **Tenant isolation:** dedicated OpenShift namespace per customer; dedicated node pools available for regulated customers (banks, government) on request

---

## 15. AI Cost, Evaluation, Observability & Reliability

**AI Gateway & Model Routing:** never hard-code a single LLM provider. The i3 AI Gateway handles model routing, authentication, prompt management, token accounting, logging, fallback, rate limiting, safety, cost tracking and evaluation. Route by task — intent classification → small model; translation → specialised model; campaign planning → larger reasoning model; high-volume chatbot → optimised production model.

**AI Cost Meter:** track tenant, agent, model, request, tokens, latency, tool calls, estimated cost and business outcome. Derive cost per conversation/lead/conversion/campaign/resolved ticket, plus AI-influenced revenue. Expose commercially as **AI Agent Actions** while metering tokens underneath.

**Evaluation Platform:** automated metrics — answer correctness, groundedness, retrieval precision/recall, hallucination rate, tool accuracy, policy compliance, escalation accuracy, CSAT, task completion, latency, cost. Regression datasets per agent. **Shadow mode and canary deployment (5% → 10% → 25% → 50% → 100%)** with automatic rollback on threshold breach.

**Reliability Patterns:** timeouts, retries with exponential backoff, circuit breakers, bulkheads, dead-letter queues, idempotency (`Idempotency-Key` header), outbox pattern for DB+event consistency, sagas and compensating transactions.

---

## 16. Non-Functional Requirements (SLOs)

| Category | Target |
|---|---|
| Real-time decisioning latency (Engage/NBA) | p95 < 200 ms |
| Consent decision latency | p95 < 50 ms |
| Batch campaign throughput (Audience Studio) | Multi-million-record segmentation and wave execution within an overnight batch window |
| Platform availability | 99.9%, measured monthly |
| Message delivery reconciliation | Delivery-receipt status reconciled within 5 minutes of dispatch across all channels |
| Multi-tenancy | Namespace-level isolation; no cross-tenant data visibility by default |
| Kafka lag | < 30 s |
| Disaster recovery | RPO ≤ 1 hour, RTO ≤ 4 hours for production tenants (validate via load testing) |

---

## 17. Consolidated Implementation Roadmap

**[Architect's recommendation]** This merges the Build Document's 4-phase, 12-month plan with the Implementation Guide's 8-wave detail. Wave numbers are shown in brackets for traceability.

| Phase | Timeframe | Focus | Exit Criteria |
|---|---|---|---|
| **0 — Architecture & Security Foundation** *[Wave 0]* | Weeks 1–6 (precedes Phase 1) | Reference architecture, tenant model, security/IAM, secrets, API & event standards, observability, CI/CD, data classification, AI governance | Architecture approved, threat model complete, security baseline live |
| **1 — Foundation** *[Waves 1]* | Months 1–3 | Consent & Profile Core, tenant provisioning, identity/SSO on existing ROKS estate; Audience Studio (segmentation, suppression, batch execution); Messenger (SMS/WhatsApp/email dispatch + delivery reconciliation); integrate existing i3 Engage rather than rebuild | Core CDP + messaging operational |
| **2 — Orchestration & Resource Management** *[Waves 2–3]* | Months 3–7 | Journey Orchestrator, Plan & Resource Manager; first Connect Hub connectors (CRM, core banking/billing); Journey engine visual canvas, state management, triggers, timers | Batch campaigns live → goal-based journeys live |
| **3 — AI Copilot** *[Wave 4]* | Months 6–8 | AI Gateway, prompt registry, RAG/Knowledge, Campaign Agent, Content Agent, Journey Agent, Analytics Agent — **recommend-and-approve only** | Natural-language campaign drafting live |
| **4 — Real-Time & Optimization** *[Wave 5]* | Months 7–9 | Engage (real-time NBA), Contact Optimizer; extend Connect Hub to POS/ATM/branch for real-time offer presentment; feature store, propensity models, experimentation | Real-time NBA live |
| **5 — Agentic Execution** *[Wave 6]* | Months 9–11 | Full Agent Runtime, Tool Registry, Approval Engine, Agent Memory, Guardrails, Agent Audit, Evaluation — govern the Release 2.0 innovations (Section 8.2) as they come online | Governed multi-agent execution |
| **6 — Analytics & Enterprise Production** *[Wave 7]* | Months 10–12 | Insight Studio (pre-built + ad-hoc reporting); DR, HA, performance & security testing, compliance, billing, tenant provisioning, SRE, onboarding | Production-ready; **first external pilot customer go-live** |

**MVP Scope (commercially sellable first version, per source Build Document):** Customer 360 + Consent + Audience + Campaign + Journey + WhatsApp/SMS/Email + AI Copilot + Content Agent + Campaign Agent + Basic NBA + Analytics + Human Approval. **Do not wait for every future capability before the first pilot.**

**[Architect's recommendation]** Gate Phase 5 (Agentic Execution / autonomous optimisation) explicitly behind a working Evaluation Platform (Section 15) and at least one full quarter of Tier 2/3 human-approved agent actions in production. Autonomous or auto-applied actions (Section 8.2, #6) should not go live until the Agentic Safety Triangle (Section 14.1) has demonstrable audit evidence from real Tier 0–3 traffic.

---

## 18. Team Structure & Delivery Model

| Role | Indicative Allocation |
|---|---|
| Solutions Architect (Lead) | 1, full engagement — architecture ownership, IBM/Red Hat platform decisions, customer-facing design authority |
| Enterprise Solutions Architect | 1 |
| Technical Product Manager | 1 |
| UX / Product Designer | 1–2 |
| Backend Engineers | 4–6 |
| Frontend Engineers | 2–3 |
| Data / ML Engineers | 2–4 |
| Agent Engineers | 2–3 |
| Integration Engineers | 2–3 |
| DevOps / SRE (Platform Engineer) | 2 |
| Security Engineer | 1 |
| QA / Automation | 2 |
| Data / Analytics | 1–2 |
| Business Analyst | 1–2 |
| Implementation / Product-Delivery Lead | 1 |

**Engineering team boundaries:**

- **Team A — Customer Data:** Profile, Identity, Consent, Customer 360
- **Team B — Campaign/Journey:** Audience, Campaign, Journey, Offers
- **Team C — Messaging:** Engage, Providers, Delivery, Templates
- **Team D — AI:** AI Gateway, Agents, RAG, Memory, Evaluation
- **Team E — Decisioning:** NBA, Models, Optimisation, Experimentation
- **Team F — Platform:** OpenShift, Kafka, CI/CD, Security, Observability

Delivery draws on i3's existing bench and, where useful, i3 Academy graduates as a talent pipeline for engineering roles — consistent with i3's Talent-as-a-Service model.

**Definition of Done (non-AI features):** functional, unit, integration, security and performance tests; observability; audit logging; API documentation; failure handling; rollback plan; runbook; owner; SLO; data classification; tenant isolation test.

**Additional AI Definition of Done:** evaluation dataset, prompt/version tracking, model version tracking, grounding tests, hallucination tests, safety tests, tool-authorisation tests, human override, cost monitoring.

---

## 19. Commercial Packaging & Pilot Strategy

| Tier | Includes |
|---|---|
| PMC Foundation | Profiles, Consent, Segmentation, Campaigns, Messaging, Dashboards |
| PMC Professional | + Journeys, Automation, Advanced Analytics, AI Copilot, Personalisation |
| PMC Enterprise | + Agentic AI, NBA, Customer Intelligence, Advanced Optimisation, Enterprise Connectors, Dedicated Tenancy, Advanced Governance |
| PMC Sovereign | + Dedicated infrastructure, Country-specific deployment, Dedicated keys, Private AI, Regulatory controls, Dedicated support |

**Consumption pricing philosophy:** bill on customer profiles + messages + journey executions + AI interactions/agent actions + data volume + decision calls + connectors. Avoid forcing customers to buy ten disconnected modules. AI consumption exposed commercially as **AI Agent Actions** while the platform meters tokens underneath.

**Pilot strategy:** do not attempt a multi-industry pilot first. Choose **one** high-value, measurable use case — Banking (dormant reactivation), Telecom (churn prevention), Insurance (policy renewal), Retail (abandoned-cart), Education (applicant conversion). Measure baseline vs. control vs. treatment, incremental impact, cost and customer-experience effect.

---

## 20. Production Readiness Checklist & Golden Rules

**Commercialisation Readiness Checklist**

- **Product** — Packaging, Pricing, SLA, Onboarding, Documentation
- **Engineering** — HA, DR, Security, Performance, Observability
- **AI** — AI Gateway, Model governance, Evaluation, Guardrails, Agent permissions, Human approval
- **Data** — Consent, Identity, Retention, Residency, Encryption
- **Operations** — SRE, Incident response, Runbooks, Backup/restore, Support
- **Commercial** — Contract, Billing, Usage metering, Sales enablement, Demo environment

**The Golden Rule for Production Agentic AI** — every autonomous capability must be able to answer five questions before it ships:

1. **WHAT** is the agent trying to accomplish?
2. **WHAT** data is it allowed to access?
3. **WHAT** tools is it allowed to call?
4. **WHAT** actions require human approval?
5. **HOW** do we prove afterwards what happened and why?

If those five questions cannot be answered, the agent is not production-ready.

### Build Priority Matrix (Appendix A, source)

| Capability | Priority | Phase |
|---|---|---|
| Customer 360, Consent Engine, Omnichannel Messenger, Kafka, API Gateway, Tenant Isolation, Security/IAM | P0 | Foundation |
| Audience Studio, Campaign Manager | P0 | Campaign |
| Journey Engine | P0 | Journey |
| AI Gateway, Campaign Agent, Content Agent, Knowledge/RAG, Human Approval, Agent Guardrails | P0 | AI |
| NBA, Contact Optimizer, Experimentation, Knowledge Graph, Simulation Engine, Operations Agent | P1 | Decisioning/Intelligence/Ops |
| Agent Marketplace, Voice Agent, Paid Media, Native Mobile SDK, Social Listening | P2 | Expansion |

---

## 21. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| **Shared IBM Cloud/Red Hat estate is contended** across i3 Academy, 11 other ROKS solutions and this build; current credit balance and Red Hat subscription renewal date need re-verification | Delivery delay or resource contention across Phase 4/AI resourcing especially | Re-check current IBM Cloud credit balance and Red Hat OpenShift Partner Subscription renewal timeline **before Phase 0 kicks off**; ring-fence production capacity separately from lab capacity |
| Regulated customers (banks) require in-country data residency i3's current footprint may not fully cover | Lost or delayed pilot deals | Prioritize Connect Hub and tenancy design to support dedicated node pools/in-country hosting as an explicit, sellable option — not an afterthought |
| Feature parity with a mature 20+ year Unica suite is a large surface to cover | Scope creep, missed timelines | Phase strictly to the Release 1.0 module list (Section 3.3); treat paid media, mobile SDKs, social listening and 6 of the 11 agentic innovations as explicit Release 2.0 items (Section 8.2) |
| WhatsApp Business API and SMS aggregator relationships vary by country across i3's 12 country teams | Inconsistent channel reliability at scale | Build Messenger's channel-adapter layer provider-agnostic from day one, with per-country provider configuration |
| AI-generated campaign content/decisions require human sign-off in regulated sectors | Compliance exposure if AI recommendations are auto-executed | Keep Agent Platform outputs recommend-and-approve by default in Release 1.0; gate autonomous execution behind the Agentic Safety Triangle and a proven Evaluation Platform |
| Hallucination | Bad campaign content, incorrect claims | RAG + validation + evaluation + groundedness checks |
| Unauthorised agent action | Compliance/financial exposure | Tool authorisation + risk tiers + mandatory approval for Tier 3/4 |
| Excessive agent autonomy | Runaway cost or action loops | Risk tiers + max-step/token/monetary limits; agent state machine owned by workflow engine, not the LLM |
| Prompt injection | Data leakage, policy bypass | Input/output guardrails + strict policy hierarchy (system > developer > business > user > retrieved content) |
| Data leakage | Regulatory/reputational exposure | Tenant/data policy + encryption + full audit trail |
| Model/provider failure | Service disruption | AI Gateway fallback models; provider-agnostic channel adapters |
| AI cost explosion | Margin erosion | Token budgets + AI Cost Meter + alerting |
| Agent loops | Runtime/cost blowout | Max-step controls + state machine ownership outside the LLM |
| Wrong customer identity | Misdirected offers/messages, compliance risk | Identity confidence thresholds + deterministic-first matching, never silent probabilistic overwrite |
| Incorrect offer | Customer harm, regulatory exposure | Eligibility engine + business rules + NBA policy layer |

---

## 22. Appendix

### 22.1 Glossary

| Term | Definition |
|---|---|
| CDP | Customer Data Platform — unified, addressable customer profile store |
| NBA | Next-Best-Action — real-time recommendation of the optimal offer/message for a customer |
| MRM | Marketing Resource Management — planning, budgeting and asset-management tooling |
| ROKS | Red Hat OpenShift Kubernetes Service — i3's standard container platform |
| Consent Ledger | Auditable record of customer opt-in/opt-out status by channel and purpose |
| MCU | Micro-Credential Unit (i3 Academy/ecosystem term — not part of PMC scope) |
| FDE | Forward Deployed Engineer |

### 22.2 Illustrative API Surface

**AI Campaign Draft**
```
POST /api/v1/ai/campaigns/draft
{
  "objective": "reactivate dormant customers",
  "duration_days": 30,
  "preferred_channels": ["whatsapp", "sms"],
  "constraints": {
    "exclude_open_complaints": true,
    "respect_consent": true,
    "max_contacts_per_week": 2
  }
}
```

**Next-Best-Action**
```
POST /api/v1/decision/next-best-action
{
  "customer_id": "cust_123",
  "context": { "channel": "whatsapp", "event": "product_page_viewed" }
}
```

**Agent Task**
```
POST /api/v1/agents/tasks
{
  "agent": "campaign-strategy",
  "task": "design_campaign",
  "objective": "...",
  "constraints": {}
}
```

### 22.3 Killer Workflows (source reference)

1. **AI Campaign Creation:** Natural language → Campaign Agent → Audience → Journey → Content → Compliance → Approval → Execution
2. **AI Customer Service:** WhatsApp → Nuru/Service Agent → Customer 360 → Knowledge → Tool call → Resolution → CRM
3. **AI Next-Best-Action:** Customer event → Customer 360 → Eligibility → Prediction → NBA → Policy → Channel → Engage → Outcome

### 22.4 Source Documents Consolidated

- i3 PMC Technical Build Document v0.1 (September 2026) — competitive landscape, module-to-Unica mapping, data model, 4-phase roadmap, risk register
- i3 PMC Technical Implementation Guide v1.0 (September 2026) — Agent Platform, 11 signature innovations, 8-wave roadmap, tech stack, security/governance detail
- i3 Precision Marketing Cloud — source architecture assessment document

**Not incorporated into this technical guide** (out of scope — commercial/partner strategy, not platform architecture): i3 Ecosystem Partner Expansion Strategy and i3 E³ Partner Ecosystem Blueprint (IBM/Skillsoft/certification-body alliance strategy, October 16, 2026 launch event, Credential Trust Network). These describe a separate initiative and should remain a distinct workstream from i3 PMC delivery, though both compete for the same shared IBM Cloud/Red Hat capacity flagged as Risk #1 above.

---

*End of Document — i3 Precision Marketing Cloud Master Technical Implementation Guide v2.0*
*i3 Technologies | Instrumented, Interconnected & Intelligent Technologies Limited*
*IBM Cloud + Red Hat OpenShift | Sovereign Agentic Customer Engagement Platform*
