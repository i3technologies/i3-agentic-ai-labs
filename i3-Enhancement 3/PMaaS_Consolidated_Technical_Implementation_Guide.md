# PMaaS Platform — Consolidated Technical Implementation Guide

**Solutions Architecture Synthesis & Review of the PMaaS 5.0 Review, PMaaS 6.0 "Sauti ya Kizazi," and the FORD-Asili Blockchain / i3 Engage Implementation Guide**

| | |
|---|---|
| **Document class** | Confidential — Internal i3 Technical Teams |
| **Engagement** | PMaaS — FORD-Asili Digital-First Party Platform, 2027 General Election |
| **Prepared by** | Senior Solutions Architecture Review |
| **Prepared for** | i3 Technologies Delivery Leadership & FORD-Asili National Executive Committee |
| **Version** | 1.0 — Consolidated |
| **Date** | 19 September 2026 |
| **Status** | Implementation-ready — consolidates three source documents into one buildable specification |

---

## How to read this document

Three documents were supplied for this review, each written at a different altitude and none fully cross-referenced against the others:

1. **PMaaS 5.0 Review** — an independent architecture/business/commercialisation review of the original PMaaS blueprint. Strongest on *target-state architecture*, *data governance*, *AI agent safety*, and *commercial productisation*.
2. **PMaaS 6.0 "Sauti ya Kizazi"** — a Gen-Z-first enhancement mapping the PMaaS 5.0 recommendations onto i3's **already-live** infrastructure (i3-ai Platform), and adding the youth-engagement, CDP, and voice/multimodal layer the first review didn't cover.
3. **FORD-Asili Blockchain / i3 Engage Technical Implementation Guide** — the most concrete of the three: a buildable Hyperledger Fabric specification for the certified membership register, nomination rules, digital primaries, and the i3 Engage recruitment pipeline, dated against the actual IEBC 2027 election clock.

This guide's job is to **resolve the overlaps, close the gaps, and produce one coherent build spec** — not to repeat any of the three source documents. Where the three disagree or leave a gap, this document states the resolution and flags it explicitly as a **[SA DECISION]**.

Audience: solutions architects, backend/blockchain engineers, mobile/USSD engineers, AI/platform engineers, security engineers, DevOps/SRE, QA, and the i3 Engage/i3-Engage CDP product teams. Executives and NEC stakeholders should read §1–3, §11, and §16–19; engineering teams should treat §4–14 as the working spec.

---

## Table of Contents

1. [Executive Assessment](#1-executive-assessment)
2. [What Each Source Document Contributes](#2-what-each-source-document-contributes)
3. [Consolidated Requirements Traceability](#3-consolidated-requirements-traceability)
4. [Target-State Architecture — The Nine Planes](#4-target-state-architecture--the-nine-planes)
5. [Layer-by-Layer Technology Stack (as-built on i3-ai Platform)](#5-layer-by-layer-technology-stack-as-built-on-i3-ai-platform)
6. [Blockchain System of Record — Membership, Nominations & Digital Primaries](#6-blockchain-system-of-record--membership-nominations--digital-primaries)
7. [Data Architecture, Zoning & Data Protection Act Compliance](#7-data-architecture-zoning--data-protection-act-compliance)
8. [Identity, Authentication, Consent & Ballot Secrecy](#8-identity-authentication-consent--ballot-secrecy)
9. [Agentic AI System — Gateway, Agents & Guardrails](#9-agentic-ai-system--gateway-agents--guardrails)
10. [i3 Engage Recruitment Pipeline & i3-Engage CDP Mobilisation](#10-i3-engage-recruitment-pipeline--i3-engage-cdp-mobilisation)
11. [Gen-Z Engagement Layer](#11-gen-z-engagement-layer)
12. [Anti-Deepfake & Verified Media System (C2PA)](#12-anti-deepfake--verified-media-system-c2pa)
13. [Ward Intelligence, GIS & Research Architecture](#13-ward-intelligence-gis--research-architecture)
14. [Cybersecurity, Reliability & DevSecOps](#14-cybersecurity-reliability--devsecops)
15. [Consolidated Innovation Portfolio — "Best Innovations"](#15-consolidated-innovation-portfolio--best-innovations)
16. [Commercialisation & Product Family](#16-commercialisation--product-family)
17. [Illustrative Financial Model](#17-illustrative-financial-model)
18. [Master Implementation Roadmap](#18-master-implementation-roadmap)
19. [Delivery Team & RACI](#19-delivery-team--raci)
20. [Consolidated Risk Register](#20-consolidated-risk-register)
21. [KPI / SLO / Acceptance Framework](#21-kpi--slo--acceptance-framework)
22. [Governance, Legal & Regulatory Design](#22-governance-legal--regulatory-design)
23. [Decision Gates for the Board](#23-decision-gates-for-the-board)
24. [Appendix A — Consolidated Chaincode Function Reference](#appendix-a--consolidated-chaincode-function-reference)
25. [Appendix B — Glossary](#appendix-b--glossary)
26. [Appendix C — Source Documents & Evidence Base](#appendix-c--source-documents--evidence-base)

---

## 1. Executive Assessment

Read together, the three source documents describe **one platform at three levels of resolution**: a target-state architecture (PMaaS 5.0), a mapping of that target state onto infrastructure i3 already operates plus a youth layer (PMaaS 6.0), and a concrete, dated, buildable subsystem for the highest-stakes component — certified membership and digital primaries (FORD-Asili Guide).

**The core finding of this consolidated review: the platform is buildable, and most of it is not net-new engineering.** The trust-plane components the PMaaS 5.0 review called for as a target state — AI gateway, model observability, RAG, agent orchestration, human-in-the-loop co-worker, workflow engine, IAM, secrets management, GitOps, observability — are confirmed **live today** on the i3-ai Platform (ROKS/IBM Cloud, open-source stack). The one genuinely new engineering programme is the **permissioned Hyperledger Fabric ledger** for membership, nominations, and digital primaries, which the FORD-Asili guide specifies in enough detail to build directly.

Four corrections carry across all three documents and must be treated as **non-negotiable at architecture sign-off**:

1. **Hashing is not anonymisation.** A raw SHA-256 hash of a National ID is dictionary-attackable. Both the PMaaS 5.0 review and the FORD-Asili guide converge on the same fix: a keyed HMAC/token vault (KMS/HSM-backed) with the identifier-derived token never exposed to analytics or commercial tenants.
2. **Identity verification and ballot/vote secrecy must be architecturally separate systems**, not merely policy-separated. The FORD-Asili guide operationalises this exactly: turnout events are public and auditable; encrypted ballot *content* lives only in a Fabric private data collection scoped to tally peers.
3. **No individual political-opinion profiling, ever** — carried as a hard rule through the ward dossier (PMaaS 5.0), the i3-Engage CDP youth segments (PMaaS 6.0), and the ward-accountability-dossier/ledger separation (FORD-Asili, requirement R10). This is architecturally enforced via a **Commercial/Political Data Diode**, not a contractual promise.
4. **Every external integration (ORPP/IPPMS, IEBC export, the exact 200-member / membership-duty rule, the fee schedule) is a placeholder until independently confirmed against the authorised interface and the party's certified nomination rules.** Do not hard-code unverified legal or endpoint assumptions into chaincode or workflow logic.

**Bottom line:** build the trust architecture and the ledger first, in that order, before scaling AI agents, Gen-Z channels, or commercial productisation on top. The differentiator is not "more AI" — it is a platform where every membership event, AI action, nomination decision, ballot, media credential, and commercial transaction is attributable, auditable, and reversible where appropriate.

---

## 2. What Each Source Document Contributes

| Source | Primary contribution | Primary gap it leaves | How this guide resolves it |
|---|---|---|---|
| **PMaaS 5.0 Review** | Target-state 9-plane architecture; three-zone data model; agent-safety table; C2PA-as-provenance-not-detector framing; commercial SKU family; legal/regulatory dependency table | Written without visibility into i3's actual infrastructure — recommends things as "to build" that already exist; no concrete ledger design; no youth layer | §4–5 re-anchor the 9 planes onto live i3-ai Platform services (per PMaaS 6.0); §6 supplies the ledger design (per FORD-Asili guide) |
| **PMaaS 6.0 "Sauti ya Kizazi"** | Confirms which target-state components are already live; adds the Gen-Z engagement layer, i3-Engage CDP integration, voice/multimodal stack, age-gating guardrails | Does not address the blockchain/nomination/primary subsystem at all; commercial model is i3-Engage-centric, not FORD-Asili-specific | §6 and §16–17 fold in the FORD-Asili blockchain/nomination economics and roadmap alongside the Gen-Z commercial add-ons |
| **FORD-Asili Guide** | The only source with a dated, numbered, buildable spec: Fabric network topology, chaincode inventory, identity/ballot-secrecy mechanism, i3 Engage integration points, DPA controls, infra bill of materials, risk register, RACI, roadmap pinned to the IEBC clock | Does not reference the Gen-Z layer, i3-Engage CDP, C2PA/deepfake system, or ward intelligence/GIS at all — reads as a standalone subsystem | §9–13 wire the ledger into the AI, Gen-Z, media-integrity, and intelligence planes it was written independently of |

**[SA DECISION]** These three documents are **complementary layers of one build**, not competing designs. This guide treats the FORD-Asili blockchain subsystem as the **system of record for membership, nominations, fees, and primaries**; the i3-ai Platform (PMaaS 6.0) as the **application, AI, and engagement runtime**; and the PMaaS 5.0 review's 9-plane model as the **organising architecture** that both plug into.

---

## 3. Consolidated Requirements Traceability

| # | Requirement | Source driver | Owning subsystem |
|---|---|---|---|
| R1 | Certified, de-duplicated membership register, IEBC-submissible | Political Parties Act; certified-register requirement | Blockchain Membership chaincode + off-chain PII store |
| R2 | Nomination rules encode fee schedule and any waivers without contradicting NEC's certified rules | NEC fee notice vs. any waiver proposal — legal validation required before encoding | Nomination chaincode, config driven by a **signed rules document**, never hard-coded |
| R3 | Per-ward/tiered new-member duty tracked per candidate | Membership-duty design correction | Nomination chaincode counters + i3 Engage recruitment pipeline |
| R4 | Refundable integrity deposit, waivable per certified criteria | Anti-frivolous-candidacy control | Daraja escrow + Escrow chaincode |
| R5 | Digital primary with independent audit trail, ballot secrecy, dispute workflow | Election-management-system framing | PrimaryVoting + ResultTally chaincode; HSM key custody |
| R6 | USSD/feature-phone access | Rural connectivity constraint | USSD Gateway, stateful/resumable sessions |
| R7 | Data Protection Act 2019 consent, minimisation, breach-proofing | Membership-register leak risk | Consent Service + field-level encryption |
| R8 | Independent security audit / penetration test before go-live | Digital-primary compromise risk (Very High severity) | Security & QA, third-party firm, not i3 |
| R9 | Delivery pinned to the IEBC 2025–2027 Election Operation Plan dates | Statutory deadlines | Programme / Delivery |
| R10 | Ward-accountability/intelligence dossier data has **no write path** to the nomination ledger | Separation of electoral-system integrity from campaign content | Architecture boundary — Commercial/Political Data Diode |
| R11 | AI agents default to read/draft/route; no autonomous publication of political content or persuasive youth messaging | Agent-safety table, PMaaS 5.0 review | AI Gateway + policy engine + human-approval workflow state |
| R12 | Gen-Z/youth channels apply the *same* approval-gate and audit-receipt architecture as staff channels — informality of channel is not a reduced-governance zone | PMaaS 6.0 Gen-Z guardrails | n8n workflow state + Kafka audit trail, channel-agnostic |
| R13 | Age-eligibility (18+) enforced as a technical gate at the identity layer, not a policy note; under-18 users routed to a strictly non-partisan civic-education track | PMaaS 6.0 §7 | Keycloak identity layer + WhatsApp opt-in flow |
| R14 | Media provenance (C2PA) implemented as an evidence signal, never marketed as a truth detector | PMaaS 5.0 review + C2PA 2.4 spec | Verified Media Vault — provenance + forensics + source-verification + human review |
| R15 | Commercial tenants technically cannot query party/member data | PMaaS 5.0 commercial firewall | Separate tenant Keycloak realms + data-plane isolation |

---

## 4. Target-State Architecture — The Nine Planes

The PMaaS 5.0 review's nine-plane model remains the correct organising frame. This section re-anchors each plane to its **actual, confirmed implementation** — either already live on the i3-ai Platform, or newly specified by the blockchain subsystem.

| # | Plane | What it owns | Implementation status |
|---|---|---|---|
| 1 | **Trust Plane** | Identity, consent, provenance, audit, policy-as-code, cryptographic receipts | ✅ Live (Keycloak, OpenBao, Kafka audit channel) + 🔧 New (Fabric ledger as the tamper-evident record for membership/nomination/vote events) |
| 2 | **Core Party/Civic Plane** | Membership, candidate, nominations, collaboration, grievances, finance, governance | 🔧 New — Membership/Nomination/Escrow chaincode + application services (§6) |
| 3 | **Communication Plane** | USSD, SMS, WhatsApp, voice, email, OTT, TikTok/IG/YouTube Shorts | ✅ Live (i3 Engage, OTT stack) + existing *509#-class USSD channel reused |
| 4 | **Intelligence Plane** | GIS, ward digital twins, public-source research, scorecards, evidence graphs | ✅ Live infra (PostgreSQL/PostGIS addable in-cluster) — **architecturally isolated from the ledger (R10)** |
| 5 | **AI Plane** | Model gateway, RAG, agents, evaluation, red-teaming, multilingual QA, cost controls | ✅ Live (LiteLLM, Langfuse, ChromaDB, LangGraph, Open WebUI) |
| 6 | **Media Integrity Plane** | C2PA vault, forensic analysis, verification workflow, correction system | ⚠️ Partial — voice-clone registry and object storage live; C2PA manifest layer to be added at the object-store boundary |
| 7 | **Commercial Plane** | Isolated tenants, product catalogue, billing, CRM, managed services | ✅ Live pattern (per-tenant Keycloak realms, LiteLLM metering → n8n billing) |
| 8 | **Reliability Plane** | Kubernetes/OpenShift, GitOps, CI/CD, observability, SIEM, DR, SRE | ✅ Live (ROKS, ArgoCD, Tekton, Prometheus/Grafana/Loki) |
| 9 | **Governance Plane** | DPO, AI Governance Desk, Legal Desk, security, procurement firewall, independent audit | ⚠️ Organisational function to stand up — not infrastructure; owned by FORD-Asili NEC with i3 as processor |

**[SA DECISION]** The ledger (Fabric) is placed **inside the Trust Plane**, not as a tenth plane, because its entire purpose is to make Plane 2's events (membership, nomination, votes) tamper-evident and independently verifiable — exactly the Trust Plane's mandate.

---

## 5. Layer-by-Layer Technology Stack (as-built on i3-ai Platform)

This table merges the PMaaS 5.0 "recommended implementation" column, the PMaaS 6.0 "already-live i3-ai Platform equivalent" column, and the FORD-Asili infrastructure bill of materials into one buildable stack.

| Layer | Technology | Status | Key controls |
|---|---|---|---|
| Container platform | Red Hat OpenShift on IBM Cloud (ROKS), namespace-per-product isolation | ✅ Live | Multi-zone; reuses existing ROKS/Red Hat partner skills and support contracts |
| Blockchain runtime | Hyperledger Fabric 2.5 LTS — peers/orderers as OpenShift StatefulSets, Fabric Operator for lifecycle | 🔧 New | Permissioned MSP/CA per organisation; Raft ordering (crash-fault tolerant) |
| AI Model Gateway | LiteLLM Proxy (`i3-model-gateway`) — OpenAI-compatible routing, retries, rate limits, per-tenant token metering | ✅ Live | Model allowlists, budgets, kill switches |
| LLM observability | Langfuse v2 — traces every call: latency, tokens, cost, errors, per-product dashboards | ✅ Live | Prompt/version registry; evaluation hooks |
| RAG / vector store | ChromaDB + nomic-embed-text embeddings; dedicated `pmaas-manifesto` collection | ✅ Live | Tenant- and role-scoped retrieval |
| Agent orchestration | LangGraph + LangChain multi-agent framework | ✅ Live | Observe/reason/propose/execute boundary enforced per agent |
| Human-in-the-loop co-worker | Open WebUI, white-labelled per product — PMaaS instance is **"Dawa"** | ✅ Live | Tools sidebar; every consequential action requires named human approval |
| Workflow / approval engine | n8n (event-driven automation) + Kafka event bus | ✅ Live | Durable, auditable approval state machine |
| Identity provider | Keycloak SSO — dedicated `pmaas` realm, separate from `engage`, `afroerp`, `ailab` | ✅ Live | MFA for staff; step-up auth for high-risk actions; RBAC + ABAC |
| Secrets / KMS | OpenBao (HashiCorp Vault fork), 3-node HA | ✅ Live | No plaintext credentials; HSM partition for Fabric MSP signing keys |
| Relational / spatial DB | PostgreSQL HA (Crunchy PGO), `pmaas_db`; PostGIS extension addable in-cluster | ✅ Live / ⚠️ extend | Encryption at rest; row/tenant isolation |
| Object storage | SeaweedFS | ✅ Live | Candidate documents, media, voice-clone registry, evidence artefacts |
| Voice — STT | faster-whisper large-v3 (English, Swahili, Kikuyu) | ✅ Live | Live captioning, voice-note transcription |
| Voice — TTS/clone | XTTS-v2 (Coqui), 6-second zero-shot cloning, `voice_id` in OpenBao | ✅ Live | Mandatory disclosure; restricted to authorised, documented use |
| Vision | LLaVA:13B | ✅ Live | Meme/thumbnail brand-safety and fact-grounding review before publish |
| Live streaming | OvenMediaEngine + SeaweedFS + nginx-HLS | ✅ Live | Candidate/surrogate AMAs; auto-cut into short-form clips |
| USSD gateway | Africa's Talking / Safaricom USSD aggregator, reusing the existing `*509#`-class channel | ✅ Live | Stateful, resumable sessions |
| Messaging | WhatsApp Business Cloud API, SMS gateway (Africa's Talking / SMPP), i3 Engage | ✅ Live | Opt-out/STOP on every message; consent double-opt-in |
| Payments | M-Pesa Daraja API, Paystack in-message links | ✅ Live | Nomination fees, refundable deposits, small-ticket donations, volunteer reimbursements |
| GitOps / CI/CD | ArgoCD + Tekton Pipelines | ✅ Live | Signed releases; chaincode and service deployment require peer review |
| Observability | Prometheus, Grafana, Alertmanager, Loki | ✅ Live | Ledger health, endorsement latency, chaincode error rates, cost telemetry |
| Commercial tenancy | Per-tenant Keycloak realms; LiteLLM per-tenant token metering → n8n billing webhook | ✅ Live | Hard tenant isolation; no party-data reuse |

**[SA DECISION]** The stack column marked ✅ Live means **no procurement, licensing, or platform-standup lead time** — engineering effort is configuration and integration, not infrastructure build. Effort and risk concentrate almost entirely in the 🔧 New row (Fabric) and the ⚠️ Partial/extend rows (PostGIS, C2PA manifest layer).

---

## 6. Blockchain System of Record — Membership, Nominations & Digital Primaries

This section is the FORD-Asili guide's specification, retained in full because it is the most implementation-ready component across all three source documents and the one genuinely new engineering programme.

### 6.1 Architecture principles

- **Permissioned, not public.** Validator and ordering nodes are operated by named, accountable organisations only — i3 Technologies, FORD-Asili's National Elections Board (NEC), and optionally an independent ORPP/observer node. This is an election-management system, not a cryptocurrency network.
- **Identity/ballot separation.** The system that authenticates a member is architecturally separate from the system that records a ballot choice — turnout is fully auditable while individual votes remain secret where secrecy is required.
- **Channel-agnostic front door.** Web, mobile, USSD, and WhatsApp/i3 Engage all terminate at the same API gateway and identity layer — no channel gets a shortcut around verification.
- **Everything material is on-chain; everything sensitive is off-chain.** PII lives in an encrypted off-chain store; the ledger holds only hashes, status flags, and event references, per Data Protection Act minimisation.
- **Human review beats automation for consequential decisions.** Deduplication, waiver eligibility, and dispute resolution surface flagged cases to human reviewers (NEC) rather than auto-deciding.

### 6.2 Why Hyperledger Fabric, not a public chain

- Permissioned membership (MSP/CA) matches the requirement for named, accountable validators.
- Channel and private-data-collection features let ballot content be shared only among tally peers while turnout events stay visible to all peers for audit.
- No token/cryptocurrency requirement, no gas fees, no probabilistic finality — Fabric transactions are final once endorsed and ordered, which matters for a legally contestable nomination result.
- Runs natively on Red Hat OpenShift, which i3 already operates on IBM Cloud (ROKS) — reusing existing platform skills, monitoring, and support contracts.

### 6.3 Network topology

| Organisation (MSP) | Role | Nodes operated | Notes |
|---|---|---|---|
| `i3Tech-MSP` | Technology operator / majority validator | 2× peer, 1× ordering-service member (Raft), CA | Runs on ROKS; on-call SRE ownership |
| `FORDAsili-MSP` | Party / National Elections Board | 1× peer, 1× ordering-service member, CA | Independent key custody — NEC holds its own signing keys, never i3 |
| `ORPP-Observer-MSP` (optional, Phase 2) | Independent compliance observer | 1× read-only peer | Read-only, endorsement-exempt; strengthens legal defensibility of results |

**Channels:** a `membership` channel (i3Tech-MSP, FORDAsili-MSP), a `nominations` channel (same members), and a per-election-cycle `primaries-2027` channel using private data collections scoped per constituency, to bound ledger size and blast radius. Certificate Authorities issue enrolment certificates to application services, not directly to end users; end users authenticate to the Identity Service, which acts on their behalf via role-scoped service-account identities (member, candidate, agent, NEC-reviewer).

### 6.4 Chaincode (smart contract) inventory

| Chaincode | Key functions | State written |
|---|---|---|
| **MembershipRegistry** | `RegisterMember`, `VerifyMember`, `FlagDuplicate`, `RenewMembership`, `GetMemberStatus` | Hashed national-ID reference, ward, status (pending/verified/flagged/active), consent timestamp |
| **Nomination** | `OpenNominationWindow`, `SubmitCandidacy`, `ApplyWaiver`, `RecordFeePayment`, `RecordMemberDutyProgress`, `CertifyEligibility`, `CloseNominationWindow` | Candidate ID, seat, fee/waiver status, member-duty counter, eligibility flag, certification hash |
| **Escrow** | `CollectDeposit`, `ReleaseDeposit`, `ForfeitDeposit`, `WaiveDeposit` (per certified criteria) | Deposit status keyed to candidate ID and Daraja transaction reference |
| **PrimaryVoting** | `OpenBallot`, `CastEncryptedBallot`, `CloseBallot`, `RecordTurnoutEvent` | Turnout event per verified voter (public); encrypted ballot content (private data collection, tally-peer scoped only) |
| **ResultTally** | `Tally`, `PublishSignedResult`, `OpenDisputeWindow`, `RecordDisputeEvidence`, `ResolveDispute` | Aggregated, signed result summaries; dispute case references and evidence hashes |

### 6.5 Layered application architecture

| Layer | Components | Responsibility |
|---|---|---|
| Channel layer | PMaaS web app, PMaaS mobile app, USSD gateway, WhatsApp/SMS via i3 Engage | Member/candidate/agent-facing entry points |
| API & identity layer | API Gateway, Identity & Consent Service, MFA/OTP service, **Ballot-Secrecy Broker** | AuthN/AuthZ, consent capture, session control, vote-anonymisation handoff |
| Application services | Membership Service, Candidate/Nomination Service, Primary Election Service, Fee & Escrow Service, Dedup/Verification Service, Dispute Service | Business logic; orchestrate chaincode calls and off-chain stores |
| Ledger layer (Fabric) | Membership/Nomination/Voting/Result-Tally chaincode, ordering service, peer nodes | Tamper-evident system of record; consensus and immutability |
| Off-chain data layer | Encrypted PII store, document store, analytics warehouse (read replicas) | Sensitive data, large binary attachments, reporting |
| Integration layer | i3 Engage connector, Daraja connector, AI-brief connector (LiteLLM/Qwen), ORPP/IEBC export connector | External and cross-module integrations |
| Platform & ops | ROKS, HSM/KMS, observability stack, backup/DR | Runtime, key management, monitoring, resilience |

### 6.6 Digital primaries — end-to-end sequence

1. NEC opens the ballot for a ward/seat via `PrimaryVoting.OpenBallot`, referencing the certified voter roll snapshot (a Merkle-rooted extract of `MembershipRegistry` state as of the certification date).
2. Eligible voter authenticates and receives a one-time ballot token bound to their verified member ID but cryptographically unlinkable to their eventual candidate choice.
3. Voter casts a ballot; the client encrypts the candidate choice with the tally peers' public key before submission. `CastEncryptedBallot` writes (a) a public turnout event and (b) the encrypted choice into the private data collection.
4. At close, `ResultTally.Tally` runs only on designated tally peers, decrypts within that trusted execution context, aggregates, and calls `PublishSignedResult` — a signed, publicly verifiable result summary (turnout, per-candidate totals, rejected-ballot count).
5. A dispute window (default 72 hours) opens automatically; `OpenDisputeWindow` and `RecordDisputeEvidence` let any candidate or NEC member submit evidence, hashed and time-stamped on-chain even though underlying documents live in the off-chain document store.

**Offline / connectivity contingency:** USSD sessions are stateful and resumable at the gateway. Wards with confirmed connectivity failure on primary day fall back to a pre-agreed paper/manual ballot, reconciled into the ledger post-hoc via `RecordOfflineBallot` requiring two-person sign-off, with paper ballots retained as physical evidence. Fabric peers replicate synchronously within the Raft ordering group; a single data-centre outage does not halt the network provided a majority of orderers remain reachable.

### 6.7 Mandatory pilots before go-live

Digital primaries are the single highest-severity technical risk in the programme. **MUST** run two independent, full-scope pilots before the primaries window:

- **Pilot 1** (target: December 2026, 2 wards) — functional and usability validation, including USSD flow with real feature phones on multiple network operators.
- **Pilot 2** (target: February 2027, 5–10 wards across ≥3 counties) — load, security, and dispute-workflow validation, including a simulated DDoS and a simulated insider-rigging attempt, run by the independent security auditor (§14).

### 6.8 i3 Engage recruitment integration — why it sits in front of the register

The single biggest technical risk flagged across the source OSINT assessments is **register inflation**: candidates chasing a member-duty quota have every incentive to submit low-quality, duplicate, or coerced sign-ups. i3 Engage is positioned as the **only** channel through which bulk recruitment happens, so every recruitment interaction is instrumented, rate-limited, and consent-checked before it ever reaches `MembershipRegistry`. Full recruitment workflow and integration points are detailed in §10.

---

## 7. Data Architecture, Zoning & Data Protection Act Compliance

### 7.1 Three-zone data model (PMaaS 5.0) mapped onto on-chain/off-chain split (FORD-Asili)

| Zone | Contents | Storage | Access | On-chain / off-chain |
|---|---|---|---|---|
| **A — Identity vault** | National ID, full legal name, raw phone number, consent evidence | Encrypted off-chain PII store (IBM Cloud Databases / Postgres, field-level encryption; IBM Key Protect) | Identity Service + authorised DPO/compliance roles only | **Off-chain** |
| **B — Operational party data** | Membership status, ward, candidate declarations, nomination evidence, fee/escrow status | On-chain (chaincode state) referencing pseudonymous/hashed identifiers | Party operations by role; candidate/NEC/legal roles | **On-chain** (hashed reference only) |
| **C — Aggregate intelligence** | Ward/county statistics, service scorecards, news trends | Warehouse/OpenSearch/PostGIS | Operational dashboards; public subset | **Off-chain, architecturally isolated from the ledger (R10)** |
| **Commercial client data** | Brand campaigns, customer lists, content assets | Separate tenant/data plane | Client + commercial team only | Off-chain, separate tenant realm |

**Critical correction carried from the PMaaS 5.0 review and confirmed in the FORD-Asili guide:** replace raw SHA-256 of the National ID with a **tokenisation service using a KMS/HSM-protected secret and a keyed HMAC** (or equivalent keyed pseudonym). Store the mapping in a segregated vault. Never expose the identifier-derived token to analytics vendors or commercial tenants.

### 7.2 What lives where (concrete data classes)

| Data class | Storage location | Protection |
|---|---|---|
| National ID, full name, raw phone | Encrypted off-chain PII store | AES-256 at rest, field-level encryption, Identity Service access only |
| Hashed ID reference, membership status, ward | On-chain (`MembershipRegistry`) | Keyed HMAC + salt; ledger is tamper-evident, not confidentiality-providing on its own |
| Candidate documents (ID copies, clearance certs) | Encrypted document store, referenced by hash on-chain | Access-controlled; hash proves non-tampering without exposing the document |
| Ballot choice (encrypted) | Private data collection, tally-peer scoped | Client-side encryption; decryptable only within the tally process |
| Turnout events | Public channel state | Publicly auditable; contains no vote content |
| Engage outreach logs | i3 Engage data store | Purged per retention schedule; consented leads promoted to Membership Service, raw logs not retained indefinitely |
| Ward accountability/intelligence data | Separate analytics store, **no write path to the ledger** | Public-source data only; isolated per R10 |
| Commercial client data | Separate tenant/data plane | Client contract-defined retention |

### 7.3 Consent ledger

Store: purpose, notice version, timestamp, channel, language, affirmative action, lawful basis, withdrawal event, processor/controller role, and the policy version in force. A consent record is **immutable as an event**, while current consent state is materialised for fast checks. This single consent-ledger design serves both the DPA-2019 membership-registration flow (FORD-Asili guide, §9.3) and every i3-Engage youth-channel opt-in (PMaaS 6.0, §7).

### 7.4 Commercial / Political Data Diode

The party/member data environment must be **technically unable** to be queried by commercial tenants, and the ward-intelligence/accountability dossier must be **technically unable** to write to the nomination ledger. No "anonymous export" is allowed by default; aggregate outputs pass disclosure-control rules. This is enforced as an **architecture boundary**, not a contractual promise — the same principle underwrites requirement R10, the PMaaS 5.0 commercial firewall, and the PMaaS 6.0 youth-segment aggregation-only rule.

### 7.5 Data Protection Act 2019 controls

- **Lawful basis:** explicit, opt-in consent captured at registration and at every i3 Engage recruitment touch-point; consent is itself a timestamped, revocable record.
- **Data minimisation:** only hashed identifiers and status flags go on-chain; raw PII never replicated to Fabric peers.
- **Purpose limitation:** membership data collected for party registration **must not** be repurposed for the ward accountability dossier or any campaign-messaging use beyond party administration without a fresh consent basis.
- **Breach response:** documented incident-response runbook (§14.3) with mandatory notification timelines; encrypted-at-rest design limits blast radius even in a partial breach.
- **DPO function** (party-side, i3 as processor) designated before the membership drive begins at scale.

---

## 8. Identity, Authentication, Consent & Ballot Secrecy

### 8.1 Identity verification pipeline

1. Candidate/agent submits a new member via web, mobile, USSD, or an i3 Engage-driven WhatsApp/SMS flow, capturing full name, national ID number, phone number, ward, and explicit DPA-2019 consent.
2. Identity Service validates ID-number and phone format, then calls the **Dedup/Verification Service**, which checks the encrypted PII store for existing hashed-ID matches across the **whole national register**, not just within one ward.
3. If no duplicate: a member record is created with status `pending`; OTP confirms the phone; once confirmed, `MembershipRegistry.RegisterMember` writes the hashed reference and status `verified` to the ledger.
4. If a duplicate or suspicious bulk-registration pattern is detected (same device/agent registering many members in a short window, sequential ID numbers, repeated phone prefixes), the record is set to `flagged` and routed to the NEC review queue — **never silently rejected or silently accepted.**

### 8.2 Authentication tiers

| Actor | Channel | Authentication |
|---|---|---|
| Ordinary member | USSD / SMS / WhatsApp | Phone-number possession (OTP) + national-ID match; no password |
| Ordinary member | Web/mobile app | Phone OTP + optional PIN for repeat sessions |
| Candidate | Candidate portal | Phone OTP + email verification + document upload; elevated KYC before nomination certification |
| Recruitment agent / candidate's team | i3 Engage campaign console | SSO via i3 identity provider + role-scoped API token; MFA mandatory |
| NEC reviewer | Admin console | SSO + hardware-token MFA; all actions logged to an immutable audit channel |
| i3 platform engineer | Fabric CA / OpenShift console | Hardware-token MFA; break-glass access requires two-person authorisation and is itself logged on-chain |

### 8.3 Why never rely on a phone number alone

Phone-only authentication is insufficient for something with legal consequences. Mitigated three ways: (1) national-ID cross-check against the certified register at registration time; (2) SIM-swap risk mitigated by binding a member's OTP-verified phone to a re-verification step if the number changes after registration; (3) any change of registered phone number for an already-active member requires a secondary verification path (in-person agent confirmation or video-KYC in Phase 2), never a bare SMS reset.

### 8.4 Ballot-Secrecy Broker (MUST)

`CastEncryptedBallot` writes only a turnout event (member voted: yes/no, timestamped, publicly auditable) to the public channel state. The actual candidate choice is written only into a private data collection accessible to the tally peers, encrypted client-side before submission, and never linked to the voter's identity in any queryable index. This is the concrete mechanism satisfying "separate identity verification from ballot secrecy."

### 8.5 Age-eligibility gate (carried from PMaaS 6.0, applied platform-wide)

Targeting Gen-Z is not the same as targeting minors — Kenya's Elections Act sets voter eligibility at 18. Keycloak-authenticated flows and WhatsApp opt-in flows **must** capture and verify eligibility status before any persuasive or mobilisation content is served. Under-18 users are automatically routed to a strictly non-partisan civic-education track (how elections work, how to register when eligible) — never manifesto content, never mobilisation asks, never AI voice-clone messaging. This is a **hard technical boundary at the identity layer**, audited weekly, not a policy note to staff.

---

## 9. Agentic AI System — Gateway, Agents & Guardrails

### 9.1 AI Gateway

Every model sits behind **one internal gateway (LiteLLM)**. It enforces model allowlists, data-classification rules, prompt templates, maximum token/cost budgets, redaction, tool permissions, output schemas, provenance, evaluation hooks, and kill switches. All traffic traced end-to-end in Langfuse.

### 9.2 Production agent catalogue and bounded autonomy

Production agents need four bounded capabilities: **observe, reason, propose, execute** — execution constrained by tools, permissions, policy, and approval state. No agent operates with unrestricted persistent memory; use task-scoped state plus a controlled knowledge store.

| Agent | Allowed autonomy | Never autonomous | Evaluation metric |
|---|---|---|---|
| Registration/Dedupe | Validate format; identify likely duplicates; request missing fields | Final rejection where ambiguous; legal membership decisions | Precision/recall of duplicate flags; false-rejection rate |
| Content Factory | Draft content and translations, vertical-first for short-form | Publish without approval | Factuality; language QA; approval rejection rate |
| Call Centre / Dawa | Answer approved FAQs; create cases | Money/legal/sensitive decisions | Containment; escalation accuracy; hallucination rate |
| Ward Intelligence | Collect/summarise public sources; compute aggregates | Individual persuasion profile or covert monitoring | Source coverage; citation accuracy; false-claim rate |
| Deepfake | Score media and assemble evidence | Declare guilt solely from model score | Precision/recall; analyst confirmation rate |
| Compliance | Detect missing controls and deadline drift | Autonomously waive legal controls | Finding precision; time-to-remediation |
| Finance | Match invoices and flag variance | Release funds | Reconciliation accuracy; exception detection |
| Minutes | Draft minutes and action items | Finalise official minutes without chair confirmation | Edit distance; missed action rate |

### 9.3 Dawa / Dawa Kijana — one co-worker, two configuration profiles

Dawa (running on `qwen-heavy` via LiteLLM) already exists as the PMaaS campaign co-worker; for youth channels it gets a **second system-prompt profile, not a second product**:

| Attribute | Default Dawa (staff-facing) | Dawa Kijana (voter/youth-facing) |
|---|---|---|
| Tone | Formal campaign-strategist register | Sheng/English code-switch, WhatsApp-native brevity |
| Channel | Command Hub, staff dashboard | WhatsApp, Instagram DM automation, TikTok comment triage |
| Grounding | Full manifesto + internal strategy corpus | Public manifesto + FAQ corpus only (youth-safe subset) |
| Autonomy | Draft + propose (staff approves) | Answer FAQs directly; escalate anything persuasive, financial, or sensitive to a human |
| Model | `qwen-heavy` | `qwen-fast` (low latency for chat-speed replies) |

For the recruitment-specific use, Dawa also drafts ward-specific recruitment scripts for SMS/WhatsApp/voice-assisted USSD prompts — **a human campaign owner reviews and approves scripts before send; no AI-generated message reaches a voter unreviewed.**

### 9.4 RAG

Candidate and party assistants answer from a versioned knowledge base of approved policies, nomination rules, FAQs, and official documents (ChromaDB `pmaas-manifesto` collection). Every answer carries document references internally, with public-facing citations where appropriate. Retrieval is tenant- and role-scoped — the youth-facing Dawa Kijana profile is grounded only on the public/youth-safe subset.

---

## 10. i3 Engage Recruitment Pipeline & i3-Engage CDP Mobilisation

### 10.1 Recruitment workflow

1. Candidate is onboarded in the Candidate Portal and issued an i3 Engage campaign workspace scoped to their ward (or constituency, for higher-seat races).
2. Dawa drafts ward-specific recruitment scripts; a human campaign owner reviews and approves before send.
3. i3 Engage runs the outreach sequence (SMS blast, WhatsApp broadcast to opted-in numbers, or agent-assisted door-to-door capture via the Engage mobile app) and captures consent-to-join responses as structured leads.
4. Each lead is pushed via the **i3 Engage → Membership Service webhook** into the identity verification pipeline (§8.1) — **Engage never writes directly to the ledger.**
5. **Rate limiting:** the Membership Service enforces a per-agent/per-candidate velocity cap (default 150 verified registrations/day/agent), throttling sudden spikes into the human-review queue rather than silently accepting them.
6. The candidate's live member-duty counter (`Nomination.RecordMemberDutyProgress`) is exposed back into their i3 Engage dashboard, turning recruitment into a gamified, real-time progress view.

### 10.2 Technical integration points

| Integration point | Direction | Payload / mechanism |
|---|---|---|
| Campaign creation API | PMaaS → i3 Engage | Ward, candidate ID, approved script variants, target headcount, campaign window |
| Lead capture webhook | i3 Engage → Membership Service | Name, phone, national ID (where captured), ward, consent flag, agent ID, timestamp |
| Consent double-opt-in | i3 Engage ↔ member | WhatsApp/SMS confirmation message with explicit opt-in link before a lead is marked consented |
| Progress feed | Membership Service → i3 Engage dashboard | Verified-member count, flagged count, duplicate-rejection count per candidate |

### 10.3 Compliance guardrails specific to Engage

- Every outbound message includes a clear opt-out/STOP instruction; opt-outs propagate immediately to suppress further contact (DPA consent-withdrawal requirement).
- Membership must never be represented as tied to a promise of public benefit (CDF, bursary, jobs) in Engage script content — enforced by a **keyword/policy linter in the script-approval queue**, not left to reviewer memory.
- Engage campaign data retention follows the platform-wide retention schedule; raw outreach logs are purged after the statutory retention period while consented, verified member records persist in the register.

### 10.4 i3-Engage CDP — the mobilisation layer beyond recruitment

Beyond one-time recruitment, i3 already operates a full Customer Data Platform (i3-Engage Cloud) for banks, SACCOs, and insurers. PMaaS uses it directly for ongoing member/voter mobilisation rather than building a parallel CDP:

| i3-Engage capability (already live) | PMaaS use |
|---|---|
| Unified profile merged across touchpoints | Aggregate, ward-level engagement profile — **never individual political-opinion scoring** (hard boundary, §7.4) |
| Segment Builder Agent — natural language → SQL segment → preview count → one-click launch | e.g. "Registered voters aged 18–24 in Nairobi wards, reached via WhatsApp, not yet responded" — aggregate cohorts only |
| Content Generator | Brand-compliant SMS/WhatsApp/email variants, passing through the same human-approval gate |
| Send-Time Optimiser | Times civic-reminder and event-notification sends to when audiences are actually online |
| Churn/lapse Predictor (repurposed) | Flags lapsed volunteers/subscribers for a **non-partisan** re-engagement nudge — not a persuasion escalation |
| WhatsApp Business Cloud API + SMS gateway | Primary two-way channel |
| M-Pesa Daraja + Paystack in-message links | Small-ticket donation flows, volunteer stipend/reimbursement rails |

**Commercial note:** i3-Engage already has a live usage-based pricing model (platform fee + per-message + AI-token overage). Bolting PMaaS mobilisation onto it means the campaign licence fee funds incremental usage on existing infrastructure, not a second CDP build (see §17).

---

## 11. Gen-Z Engagement Layer

Kenya's 2027 electorate skews younger than any in the country's history. This cohort consumes politics as short-form vertical video rather than press releases, trusts peers and verifiable evidence over official spokespeople, is fluent in Sheng/code-switching and meme culture, and is highly exposed to — and literate about — AI-generated disinformation.

### 11.1 Short-form Content Factory (extends the existing Content Agent)

- **Vertical-first output:** script + caption + on-screen text pack sized for TikTok/Reels/Shorts, not repurposed long-form.
- **LLaVA (multimodal)** reviews thumbnail/meme drafts for brand safety and factual grounding before they leave draft state.
- **Human-approval gate stays mandatory**, enforced as a workflow state in n8n, logged to Kafka — no exception for "casual" channels.
- **Youth Ambassador Marketplace:** verified student/creator ambassadors get a branded content kit, a personal referral code, and are tracked (aggregate only, never individual persuasion profiling) via i3-Engage CDP.

### 11.2 Gamified civic literacy — reusing EvalOS, not rebuilding it

i3 already operates a full assessment/gamification engine (EvalOS: exam engine, leaderboard, Open Badges 3.0 / W3C verifiable credentials, cohort provisioning). Repurposed for youth civic engagement:

- **"Youth Squad" leaderboard** — ward-level youth volunteer teams compete on verified, non-partisan activity (voter-registration assists, civic-quiz completions, verified event attendance) — **never on persuasion metrics.**
- **Civic-literacy quiz bot on WhatsApp** — "How does nomination work?", "What is the IEBC's role?" — answered via RAG over public civic-education content only, never manifesto persuasion content.
- **Open Badges for civic participation** — a verifiable, LinkedIn-linkable credential for completing voter-education modules or verified volunteer hours; no monetary or preferential value attached, which keeps it outside campaign-finance/inducement concerns.

### 11.3 Live "Ask Me Anything" (existing OTT stack)

Candidate/surrogate AMAs streamed via the existing OvenMediaEngine pipeline; Whisper STT live-transcribes for real-time captioning; clips auto-cut and routed into the Content Factory for same-day short-form distribution.

### 11.4 Verified Media Vault as a youth trust feature, not just legal cover

Every official video/audio asset gets a scannable **Verified QR** linking to the C2PA manifest, timestamp, and original source, marketed explicitly to youth audiences: "If it doesn't have the QR, don't trust it, and tell us so we can respond." This turns the defensive innovation into an active engagement mechanic — a fact-checking-literate Gen-Z audience becomes a distributed detection network.

### 11.5 Trust, safety & age-eligibility guardrails (non-negotiable)

1. **Age gating enforced at the identity layer** (§8.5).
2. **No individual political-opinion profiling of anyone, of any age** — the Commercial/Political Data Diode (§7.4) extended to i3-Engage youth segments.
3. **Consent ledger** (OpenBao-backed) records purpose, channel, language, and withdrawal event for every youth-channel opt-in.
4. **Disclosure by default:** any AI-generated voice, video, or text delivered to a youth channel is labelled as such at first contact, reinforced by the Verified Media Vault QR.
5. **Human-in-the-loop remains mandatory** for anything persuasive, financial, or emotionally charged, regardless of how "casual" the channel feels.

---

## 12. Anti-Deepfake & Verified Media System (C2PA)

The Verified Media Vault is an **evidence system with four independent signals** — provenance, forensic analysis, source verification, human adjudication — deliberately avoiding the common mistake of treating a detector score as truth.

| Signal | Implementation | Output |
|---|---|---|
| Provenance | C2PA manifest, signer identity, asset hash, ingredients and edits | Authenticity/provenance evidence |
| Forensics | Audio spectral features, face/voice consistency, compression artefacts, model ensemble | Risk score + evidence snippets |
| Source verification | Compare against official vault, publication timestamps, known official channels | Source-of-record match |
| Human review | Two-person review for high-impact incidents | Confirmed / unconfirmed / insufficient evidence |

C2PA should be implemented as a **provenance layer**, not marketed as a perfect deepfake detector — the specification provides trust signals about origin and editing history, not proof that every underlying claim is true. **[SA DECISION]** On the i3-ai Platform, the C2PA manifest layer is the one component explicitly flagged as "to extend": it attaches at the SeaweedFS object-store boundary, alongside the existing XTTS-v2 voice-clone registry and provenance metadata.

**Incident state machine:** `NEW → TRIAGED → FORENSIC_REVIEW → HUMAN_CONFIRMATION → RESPONSE_DRAFT → APPROVED → PUBLISHED → ARCHIVED`. Every transition is signed or attributable.

**Voice cloning** is a restricted capability: prefer generic synthetic voices for routine content; use identity-linked cloning only with explicit documented authorisation, visible/audible disclosure, key rotation, and revocation. A consented reference sample never becomes a general-purpose biometric database.

---

## 13. Ward Intelligence, GIS & Research Architecture

The ward dossier converts fragmented public information into structured, local operational knowledge — with the key design constraint that it **must remain aggregate and source-disciplined**, and (per R10) has **no write path to the nomination ledger**.

**Recommended GIS stack:** PostgreSQL/PostGIS for authoritative spatial relationships; MapLibre/OpenLayers for web maps; vector tiles for performance; a boundary version registry; a data-quality service recording source, date, licence, geometry validity, and update status.

| Dataset | Use | Privacy boundary |
|---|---|---|
| Administrative boundaries | County/constituency/ward mapping | No personal data |
| Public infrastructure | Service scorecards, project tracking | Aggregate only |
| County budget/CIDP | Budget and implementation dashboards | No individual profiling |
| Public news | Issue/news digest | Public content only |
| Public social posts | Aggregate trend signals | No individual persuasion profile |
| Survey research | Issue/opinion research | Aggregate level where possible |

**Ward Digital Twin:** a living operational object per ward — boundary, service indicators, public issues, programme activities, content calendar, training status, infrastructure evidence. It is a **governance object, not a profile of the people living there.**

**Evidence graph:** links every scorecard item to source documents, photos, geospatial evidence, dates, and review status — a defensible chain from raw evidence → extracted fact → aggregate indicator → published statement.

---

## 14. Cybersecurity, Reliability & DevSecOps

Because the platform combines identity, political-party administration, payments, communications, and AI, it is treated as a **high-impact information system**.

| Control | Production requirement |
|---|---|
| Zero trust | Every service authenticates; no implicit trust inside the cluster |
| Privileged access | MFA + step-up authentication + just-in-time elevation + session logging |
| Secrets | KMS/HSM-backed (OpenBao); no secrets in Git or container images |
| Encryption | TLS 1.3 where supported; AES-256-class at rest; key rotation |
| Database | Least privilege, separate schemas/roles, row-level security, encrypted backups |
| Supply chain | SBOM, signed images, dependency scanning, provenance for releases |
| Application security | OWASP ASVS-based verification; SAST/DAST/API testing; threat modelling |
| Resilience | Multi-zone deployment; tested backups; defined RPO/RTO; quarterly restore tests |
| Observability | OpenTelemetry-equivalent traces/metrics/logs; correlation IDs across agents/workflows |
| Incident response | 24/7 severity matrix during campaign/election peak; tabletop exercises; forensic retention |
| AI security | Prompt-injection defence, tool allowlists, DLP, model-output validation |

### 14.1 Key management (blockchain-specific)

- All Fabric organisation signing keys are generated and stored in an **HSM** — NEC keys are never held by i3 staff; i3 provisions the HSM partition and access ceremony, but custody of NEC key material is FORD-Asili's.
- Client-side ballot encryption keys (public key of the tally peers) are rotated per election cycle and published in advance for independent verification.
- Break-glass administrative access to production Fabric peers requires two-person authorisation and is itself recorded as an audit-channel transaction.

### 14.2 Independent security audit (MUST, before go-live)

- Engage an independent third-party security firm (not i3) for a full penetration test of the API layer, USSD gateway, Fabric network configuration, and key-management ceremony.
- Independent code review of the ballot-secrecy mechanism specifically, given its Very High severity rating.
- A simulated insider-rigging exercise (red-team) targeting the tally process, executed during Pilot 2 (§6.7).
- Findings remediated and written certification issued before the primaries window opens; any Critical/High finding blocks go-live.

### 14.3 Incident response

A documented runbook covers: detection (observability alerts + anomaly detection on registration velocity and ballot patterns), containment (ability to pause a specific ward's primary via NEC-authorised two-person action), notification (DPA timelines), and post-incident review feeding back into the risk register (§20).

### 14.4 Cryptographic action receipts (security innovation)

For every high-impact workflow, generate a signed receipt containing actor, role, input evidence hash, policy version, model/version if AI-assisted, approval chain, and resulting state — a portable audit package for disputes and audits, applicable to both the ledger side (nominations, ballots) and the AI/content side (published messaging).

---

## 15. Consolidated Innovation Portfolio — "Best Innovations"

This table merges the PMaaS 5.0 review's P0/P1/P2 innovation list, the PMaaS 6.0 Gen-Z-specific additions, and the FORD-Asili guide's concrete mechanisms into one prioritised portfolio.

| Innovation | Source | What it adds | Priority |
|---|---|---|---|
| **Trust Fabric** | PMaaS 5.0 | Every important record has provenance, actor, policy, and evidence | P0 |
| **Ballot-Secrecy Broker** | FORD-Asili | Concrete Fabric mechanism separating turnout auditability from vote secrecy | P0 |
| **Policy-as-Code** | PMaaS 5.0 | DPA/AI/publication rules executable by gateways/workflows, incl. nomination-rules-as-signed-config (never hard-coded) | P0 |
| **AI Model Gateway** | PMaaS 5.0 / 6.0 | One controlled entry point for all models — confirmed live as LiteLLM | P0 |
| **Evidence Graph** | PMaaS 5.0 | Links claims to source evidence, media, and approvals | P0 |
| **Commercial / Political Data Diode** | PMaaS 5.0 / 6.0 / FORD-Asili (R10) | One-way, controlled aggregate outputs; hard boundary between ledger, ward-intelligence, and commercial data | P0 |
| **Cryptographic Action Receipts** | PMaaS 5.0 / FORD-Asili | Signed receipt per high-impact workflow — extends naturally from the ledger's own audit-channel pattern | P0 |
| **Dawa / Dawa Kijana dual-profile co-worker** | PMaaS 6.0 | One co-worker, two governed configuration profiles — no second product to secure | P0 |
| **Real-time member-duty counter in the recruitment dashboard** | FORD-Asili | Turns compliance tracking into a gamified, transparent candidate-facing progress view, reusing EvalOS-style UX | P1 |
| **Ward Digital Twin** | PMaaS 5.0 | Persistent aggregate operational object per ward | P1 |
| **Youth Squad Leaderboard / Open Badges civic credentials** | PMaaS 6.0 | Reuses EvalOS gamification for non-partisan youth civic engagement | P1 |
| **Verified QR / Provenance QR as an engagement mechanic** | PMaaS 5.0 (concept) → PMaaS 6.0 (activation) | Turns a defensive C2PA feature into a distributed, youth-driven fact-checking network | P1 |
| **Offline-First Field Mesh / resumable USSD sessions** | PMaaS 5.0 / FORD-Asili | Encrypted local queue + sync; stateful, resumable USSD ballot sessions for poor connectivity | P1 |
| **AI Evaluation Lab** | PMaaS 5.0 | Golden datasets, multilingual/adversarial tests, regression suite — natively supported by Langfuse | P1 |
| **Synthetic Data Factory** | PMaaS 5.0 | Non-production test populations and workflow cases — directly enables the two mandatory Fabric pilots without exposing real member data | P1 |
| **Digital Public Evidence Room** | PMaaS 5.0 | Public archive of policies, approvals, scorecards, and corrections | P1 |
| **FinOps for AI** | PMaaS 5.0 | Cost attribution per agent/workflow/customer — natively supported by LiteLLM per-tenant metering | P1 |
| **Independent ORPP-Observer Fabric peer** | FORD-Asili | Read-only, endorsement-exempt observer node — strengthens legal defensibility of results beyond a contractual promise | P1 |
| **Keyword/policy linter on Engage script approval queue** | FORD-Asili | Automated enforcement (not reviewer memory) against public-benefit-inducement language in recruitment scripts | P1 |
| **Partner Marketplace** | PMaaS 5.0 | Certified integrators and language/content vendors | P2 |
| **Pan-African Portability** | PMaaS 5.0 | Configurable country/legal adapters | P2 |
| **Youth Ambassador Marketplace** | PMaaS 6.0 | Extension of the Partner Marketplace concept for verified student/creator ambassadors, tracked in i3-Engage CDP | P2 |

---

## 16. Commercialisation & Product Family

### 16.1 Non-election product SKUs (PMaaS 5.0 productisation)

| SKU | Customer | Core modules | Commercial logic |
|---|---|---|---|
| PMaaS Core | Political/civic organisation | Collaboration, membership, workflow, audit | Annual licence + implementation |
| CivicOS | NGO/foundation/programme | GIS, grievances, scorecards, field apps | Annual SaaS + managed operations |
| Integrity Shield | Enterprise/media | Provenance vault, monitoring, incident desk | Retainer + usage |
| Vernacular Cloud | Brands/agencies | Translation, TTS, content factory, distribution | Subscription + usage |
| Research Cloud | Research/academic | USSD/CATI/CAPI, sampling, dashboards | Per study + subscription |
| AI Governance Desk | Enterprise | Inventory, evaluations, policy, red-team, audit | Recurring advisory/SaaS hybrid |

**Commercial entity separation:** a separate commercial operating unit with its own contracts, data stores, IAM realms/tenants, billing, support, and security policies — a party customer must never become the data source for another commercial client. The party platform can be a reference implementation; its data cannot be a product.

### 16.2 Election-specific licence + Gen-Z add-on (FORD-Asili / PMaaS 6.0)

| Line item | Base pricing | Gen-Z / Engage add-on |
|---|---|---|
| PMaaS Campaign Licence | Ward Councillor / MCA / MP / Governor tiers, priced by seat level | **Youth Mobilisation Pack** — Dawa Kijana config, Content Factory vertical-video templates, Youth Squad leaderboard instance |
| AI Caller minutes | Billed separately | Voice-note reply volume billed under the same meter |
| i3-Engage usage fees | Platform fee + SMS/WhatsApp usage + AI token overage | Youth segment CDP usage rolls into the same usage-based meter — no separate CDP contract needed |
| AI Lab / EvalOS reuse | N/A (internal reuse) | Licensed at marginal cost — Leaderboard/Badges infrastructure already amortised across EvalOS customers |

**[SA DECISION]** The blockchain/membership/nomination subsystem in §6 is treated as part of the base **PMaaS Campaign Licence**, not a separate SKU, because it is the system of record the licence's core value proposition depends on.

---

## 17. Illustrative Financial Model

The following is a **planning framework, not a quotation, valuation, or market forecast.** Actual pricing must be built from cloud costs, message/voice provider rates, staffing, support coverage, security requirements, taxes, and customer willingness to pay.

**Illustrative three-year revenue targets (KES millions):**

| Scenario | Year 1 | Year 2 | Year 3 | 3-year total |
|---|---|---|---|---|
| Conservative | 28 | 58 | 92 | 178 |
| Base planning case | 45 | 95 | 165 | 305 |
| Upside | 65 | 145 | 260 | 470 |

Illustrative base-case gross-margin progression is 55% → 65% → 72% as the platform shifts from implementation-heavy revenue toward recurring software and managed-service revenue. Under those assumptions, gross contribution would be approximately KES 24.8m, KES 61.8m, and KES 118.8m respectively. **These are scenario outputs, not forecasts.**

**Revenue architecture:** recurring platform licence; managed operations; usage revenue (communications, voice, storage, research, media processing); professional services; enterprise protection retainers; licensing (AI literacy curriculum, workflow modules, provenance components, white-label deployments).

**Unit economics to track:** ARR, gross margin by service line, cost-to-serve per tenant, AI inference cost per workflow, communications cost per delivered message/session, support tickets per 1,000 users, CAC, payback period, net revenue retention, implementation-to-recurring conversion.

**Credit model:** provider-funded capex amortised against service fees, candidate technology levies, and post-election revenue share — should include a hard cap, milestone acceptance, termination rights, data/IP ownership, escrow/continuity provisions, and an independent reconciliation mechanism.

---

## 18. Master Implementation Roadmap

The FORD-Asili blockchain roadmap and the i3-ai Platform's existing 5-phase rollout are threaded together below, both anchored to the actual IEBC 2025–2027 election clock.

| Phase | Window | Platform / AI deliverables | Blockchain / membership deliverables | Gen-Z overlay |
|---|---|---|---|---|
| **0 — Foundations** | Now – 15 Oct 2026 | Architecture baseline, threat model, data map, API contracts, repo/IaC | Fabric network stood up on ROKS; MSPs/CAs provisioned; NEC HSM key ceremony; nomination-rules config schema agreed with legal | — |
| **1 — Rules-to-code & AI Gateway foundation** | By 30 Oct 2026 | AI Gateway + Co-worker foundation live | Nomination chaincode encodes certified rules (fee schedule, waivers, deposit); ORPP certification sign-off obtained before this date | Dawa Kijana system-prompt profile stood up on same LiteLLM/Open WebUI deployment |
| **2 — Platform MVP** | Nov 2026 – Jan 2027 | Voice stack + PMaaS foundation | Membership registry live; USSD registration flow live; i3 Engage recruitment integration live in 5 pilot counties; candidate portal with live member-duty counter | Voice-note reply flow wired into WhatsApp; Verified-Media QR pipeline deployed on the voice-clone registry |
| **3 — Mass recruitment support** | Dec 2026 – 16 Mar 2027 | AfroERP + i3-Engage + AI Lab build | Platform scaled to all 47 counties/1,450 wards; dedup and anomaly-detection tuned under real load; membership list frozen and certified for the 16 Mar deadline | Youth segments stood up in i3-Engage CDP; EvalOS Leaderboard relabelled "Youth Squad"; first Open Badges issued |
| **4 — Digital primaries** | Pilot 1: Dec 2026; Pilot 2: Feb 2027; Live: 17 Mar – 10 Apr 2027 | Dashboards + commercialisation | Voting chaincode hardened, security-audited, piloted twice before live primaries; dispute workflow operational | Grafana youth-engagement dashboard alongside PMaaS War Room dashboard |
| **5 — General election support** | 29 May – 10 Aug 2027 | Steady-state monitoring | Candidate registration exports to IEBC; ledger retained as permanent audit record | — |
| **6 — Post-election / commercial spin-out** | Post-election | Governance mode, archive, data retention/closure, platform hardening | — | Youth Ambassador Marketplace pilot in 3 wards; OTT AMA cadence begins; independent legal review of age-gating flow before any paid promotion targets under-25 audiences |

**Critical path (unchanged from all three sources, and the single most important sequencing rule in this guide):** data governance → identity → workflow/audit → ledger/integrations → communications → AI → GIS → commercial multi-tenancy. **Do not reverse this order** — building AI agents or the Gen-Z layer before the permission and audit substrate is finished creates rework and risk. Similarly, do not scale recruitment (Phase 3) ahead of a hardened dedup/rate-limiting pipeline (Phase 2), and do not open live primaries (Phase 4) without both mandatory pilots and independent security certification complete.

---

## 19. Delivery Team & RACI

R = Responsible, A = Accountable, C = Consulted, I = Informed.

| Workstream | i3 Solutions Architect | i3 Blockchain Eng. | i3 Engage Team | i3 AI/Platform Eng. | i3 Security | FORD-Asili NEC |
|---|---|---|---|---|---|---|
| Network & chaincode design | A | R | C | I | C | I |
| Nomination-rules encoding | R | C | I | I | I | A |
| i3 Engage recruitment integration | C | I | R | I | C | I |
| USSD/mobile channel | C | R | I | I | C | I |
| AI Gateway / agent configuration | C | I | I | R | C | I |
| Gen-Z engagement layer / Dawa Kijana | C | I | R | R | I | I |
| C2PA / Verified Media Vault | C | I | I | R | C | I |
| HSM / key custody ceremony | C | R | I | I | A | R |
| Independent security audit coordination | C | I | I | I | A | I |
| Digital-primary pilots | A | R | I | I | R | R |
| Go-live certification sign-off | C | C | I | I | R | A |

FORD-Asili NEC accountability (A) on rules-encoding, HSM custody, and go-live sign-off reflects that these are **governance decisions, not purely technical ones** — i3 builds and recommends, the party owns and certifies its own election-management rules.

---

## 20. Consolidated Risk Register

Risks are consolidated across all three source documents; blockchain-specific risks retain the FORD-Asili guide's severity ratings, which are the most granular.

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Register inflation via bulk/duplicate recruitment | High | i3 Engage rate limiting, dedup service, human-review queue (§8.1, §10.1) |
| 2 | Digital-primary manipulation (insider rigging, DDoS) | **Very High** | Two-person HSM key custody, independent audit peer, pre-primary pilots, signed results (§6.7, §14) |
| 3 | Ballot secrecy failure (vote linked back to voter) | **Very High** | Private data collection + client-side encryption, independently code-reviewed (§8.4) |
| 4 | Data Protection Act breach of membership register | **Very High** | Field-level encryption, off-chain PII isolation, incident-response runbook (§7) |
| 5 | USSD/network outage on primary day | High | Stateful resumable sessions, paper fallback with two-person reconciliation (§6.6) |
| 6 | Contradiction between certified nomination rules and platform logic | High | Nomination chaincode config driven by a signed rules document reviewed by legal before each cycle; no hard-coded fee logic |
| 7 | Unverified ORPP/IPPMS integration assumptions | Critical | Formal interface discovery, test environment, contract tests, reconciliation, human fallback |
| 8 | Wrong interpretation of the membership-duty/nomination rule | Critical | Validate against party constitution, nomination rules, and current law before implementation |
| 9 | Political-opinion / individual profiling data leakage | Critical | Data zoning, Commercial/Political Data Diode, aggregate-only intelligence (§7.4) |
| 10 | AI hallucination in public content | High | RAG, source citations, schema validation, human approval, regression tests |
| 11 | Deepfake false positive | High | Multi-signal detection + human confirmation + transparent evidence |
| 12 | Voice-cloning abuse | High | Restricted keys, explicit authorisation, disclosure, revocation |
| 13 | Credential theft | Critical | MFA, phishing-resistant auth, PAM, device/session controls |
| 14 | Insider misuse | Critical | Least privilege, dual control, audit and anomaly detection |
| 15 | Commercial data cross-contamination | Critical | Separate tenant/data planes and automated policy tests |
| 16 | Age-gating bypass (under-18 reaching persuasive or mobilisation content) | High | Hard technical gate at Keycloak/WhatsApp opt-in layer, not a policy instruction; quarterly audit |
| 17 | Gamification read as vote-buying / inducement | Medium | Badges non-monetary and non-preferential by design; legal review before any physical-prize tie-in |
| 18 | Youth channels (WhatsApp/TikTok) treated as "lower-stakes" and under-governed | Medium | Same approval-gate and audit-receipt architecture applies regardless of channel informality |
| 19 | Ward accountability dossier data bleeding into the electoral system | Medium | Hard architectural separation (R10); dossier store has no write path to any chaincode |
| 20 | IEBC/ORPP timeline slippage vs. build schedule | Medium | Roadmap back-timed from statutory dates with buffer (§18) |
| 21 | Key-person / operational dependency on a small i3 delivery team | Medium | Documented runbooks, cross-trained SRE pair, FORD-Asili NEC holds its own HSM key custody independent of i3 |
| 22 | AI cost explosion | Medium | Model gateway, budgets, caching, smaller models for routine tasks |
| 23 | Vendor lock-in | Medium | Open standards, portable data, adapters, documented APIs |
| 24 | Programme scope explosion | High | Product council, P0/P1/P2 roadmap, change-control board |

---

## 21. KPI / SLO / Acceptance Framework

| Domain | KPI / SLO | Target philosophy |
|---|---|---|
| Availability | Core platform uptime | ≥99.9% monthly for critical services; multi-zone IBM Cloud region during primaries window |
| Ledger performance | Write latency (endorsement to commit) | <2 seconds at P95 under peak load |
| Scale | Concurrent USSD sessions (peak, primary day) | ≥5,000 concurrent sessions nationally |
| Scale | Membership registrations processed | ≥50,000/day sustained during the recruitment drive |
| Scale | Ballot transactions per ward | Sized to ward voter roll, worst case ~15,000 votes/ward within a 12-hour window |
| API | p95 latency | <500ms for standard read APIs; asynchronous for heavy jobs |
| AI | Hallucination / factual error | Task-specific ceilings; 100% human approval for public political content |
| AI | Unauthorised tool execution | Zero; continuous audit |
| Privacy | Consent completeness | 100% for workflows requiring consent before processing |
| Audit | High-impact actions with cryptographic receipts | 100% |
| Deepfake | Triage time | ≤15 min target; response SLA 90 min normal / 30 min peak |
| Safety | Under-18 users correctly routed to non-partisan track | 100% — zero tolerance, audited weekly |
| Research | Methodology traceability | 100% of published results linked to sampling/weighting metadata |
| Trust | % of official assets carrying a Verified QR | 100% of official media, tracked as an authenticity signal |
| Commercial | Gross margin | Improve as recurring platform revenue grows |
| Support | First response | Tiered by severity; 24/7 only for defined critical services during peak |

**Acceptance principle (unchanged from PMaaS 5.0):** no module is "done" when the code works. It is done when the workflow works under normal conditions, adverse conditions, security tests, privacy tests, operational load, staff training, and audit review.

---

## 22. Governance, Legal & Regulatory Design

This section identifies implementation dependencies; it is **not legal advice.** A standing Legal & Compliance Desk and DPO function, with a written authority matrix, is required.

| Topic | Current source signal | Implementation implication |
|---|---|---|
| Party membership technology | Kenya's Political Parties (Membership) Regulations require technology used for recruitment to conform to prescribed requirements and provide for Registrar certification before deployment | Do not launch membership technology as final until the certification/approval pathway is confirmed |
| IPPMS | ORPP reports an API module for secure system interfaces and real-time sharing/validation, but not the specific endpoint contract used in any blueprint | Use an official adapter; confirm schema, authentication, rate limits, and reconciliation process directly with ORPP |
| Membership lists | Elections Act §28/28A contains submission/certification obligations | Build a deadline engine and pre-submission reconciliation workflow |
| Data protection | ODPC guidance applies to political parties and election stakeholders; processing must be lawful, fair, specified, proportionate | DPIA, DPO, consent/notice, retention, rights, processor contracts, and incident response are first-class deliverables |
| Sensitive political data | Political opinion/adherence is treated as sensitive personal data in the Kenyan registration framework | Do not infer or commercialise individual political profiles; aggregate where possible |
| AI governance | Kenya's National AI Strategy 2025–2030; NIST AI RMF as a complementary operational governance framework | AI inventory, risk tiers, evaluation, human oversight, incident register |
| Election technology | IEBC has highlighted AI/new-media opportunities and risks in its 2027 election-technology work | Keep the platform clearly separate from statutory election administration systems unless formally authorised |
| Membership-duty / nomination rule (e.g., a "200-member" style threshold) | Needs independent legal/party-constitution validation before being encoded | Implement as a party-rule workflow driven by a **signed rules config**, never a hard-coded statutory assumption |

**Legal-risk red lines (carried unchanged across all three documents):** no private-message scraping; no covert individual voter profiling; no sale of political opinion data; no automated final legal decisions; no unverified claims presented as fact; no autonomous disbursement; no biometric/voice identity expansion beyond documented purpose; no production use of an external integration until its authority and contract are confirmed.

---

## 23. Decision Gates for the Board

1. Approve the target architecture and trust-plane-first, ledger-second sequencing (§4, §18 critical path).
2. Approve the legal validation workstream **before** locking election-specific rules (fee schedule, waivers, membership-duty thresholds) into chaincode.
3. Approve the political/commercial Data Diode as a non-negotiable architectural control (§7.4), not a contractual one.
4. Approve a modular platform strategy — reusing live i3-ai Platform services — instead of a large greenfield build (§5).
5. Approve the AI governance charter and human-approval policy, including its extension to Gen-Z/youth channels without exception (§9, §11.5).
6. Approve the commercial product portfolio and illustrative financial planning envelope (§16–17).
7. Approve independent security/privacy testing, including both mandatory Fabric pilots, before national scale (§6.7, §14.2).
8. Approve the age-eligibility technical gate and its quarterly audit cadence before any youth-channel paid promotion goes live (§11.5).

---

## Appendix A — Consolidated Chaincode Function Reference

| Chaincode | Function | Access role |
|---|---|---|
| MembershipRegistry | `RegisterMember(memberHash, ward, consentRef)` | Membership Service |
| MembershipRegistry | `VerifyMember(memberID)` | Verification Service, NEC reviewer |
| MembershipRegistry | `FlagDuplicate(memberID, reason)` | Dedup Service, NEC reviewer |
| Nomination | `SubmitCandidacy(candidateID, seat, ward)` | Candidate Portal |
| Nomination | `ApplyWaiver(candidateID, waiverType)` | Candidate Portal, NEC reviewer |
| Nomination | `RecordMemberDutyProgress(candidateID, verifiedCount)` | Membership Service (event-driven) |
| Nomination | `CertifyEligibility(candidateID)` | NEC reviewer only |
| Escrow | `CollectDeposit` / `ReleaseDeposit` / `ForfeitDeposit` | Fee & Escrow Service (Daraja-triggered) |
| PrimaryVoting | `OpenBallot(wardID)` / `CloseBallot(wardID)` | NEC reviewer (two-person) |
| PrimaryVoting | `CastEncryptedBallot(ballotToken, encryptedChoice)` | Voter session (via Ballot-Secrecy Broker) |
| ResultTally | `Tally(wardID)` / `PublishSignedResult(wardID)` | Tally peer process only |
| ResultTally | `RecordDisputeEvidence(caseID, evidenceHash)` | Dispute Service, any registered candidate |

---

## Appendix B — Glossary

- **MSP** — Membership Service Provider; Fabric's mechanism for defining an organisation's cryptographic identity.
- **HSM** — Hardware Security Module; tamper-resistant device for generating and storing cryptographic keys.
- **ROKS** — Red Hat OpenShift Kubernetes Service on IBM Cloud.
- **Private data collection** — a Fabric feature restricting a subset of ledger data to a defined set of peers, used here to keep ballot content away from non-tally peers.
- **Ballot-Secrecy Broker** — the application-layer component that issues an anonymised ballot token to a verified voter, breaking the link between identity verification and vote content.
- **C2PA** — Coalition for Content Provenance and Authenticity; defines cryptographically verifiable provenance manifests for media.
- **CDP** — Customer Data Platform; here, i3-Engage Cloud, repurposed for aggregate, non-partisan voter/member mobilisation.
- **Data Diode** — an enforced, one-way architectural boundary preventing sensitive data (political opinion, member PII) from reaching commercial or intelligence-plane systems.
- **RAG** — Retrieval-Augmented Generation; grounding an AI response in a versioned, approved knowledge base rather than model memory alone.

---

## Appendix C — Source Documents & Evidence Base

**Internal source documents synthesised in this guide:**

1. *PMaaS 5.0 — Technical, Business & Commercialisation Review*, i3 Technologies, September 2026 — independent architecture/business review of the original blueprint.
2. *PMaaS 6.0 — "Sauti ya Kizazi" (Voice of a Generation)* — Gen-Z-first technical enhancement, natively engineered on the i3-ai Platform, i3 Technologies GTM & Product Engineering.
3. *FORD-Asili PMaaS Blockchain & i3 Engage Recruitment Drive Integration — Technical Implementation Guide*, v1.0, i3 Technologies Solutions Architecture Practice, 16 September 2026.

**External regulatory/standards references carried from the source documents** (validate currency before build sign-off — several of these interfaces and rules require direct confirmation with the issuing authority, per §22):

- Office of the Registrar of Political Parties (ORPP), Annual Report FY 2024/2025
- Kenya Law, Elections Act, 2011 (consolidated text)
- Kenya Law, Political Parties (Membership) Regulations, 2021
- Office of the Data Protection Commissioner (ODPC), Guidance Notes for Electoral Purposes
- Data Protection (Registration of Data Controllers and Data Processors) Regulations, 2021
- Coalition for Content Provenance and Authenticity (C2PA), Specification 2.4
- NIST, AI Risk Management Framework (AI RMF 1.0) and Generative AI Profile
- NIST, Cybersecurity Framework (CSF) 2.0
- OWASP, Application Security Verification Standard (ASVS) 5.0.0
- Ministry of Information, Communications and the Digital Economy, Kenya AI Strategy 2025–2030
- IEBC 2025–2027 Election Operation Plan

**Evidence note:** where the source documents contain specific implementation claims not independently confirmed by public documentation — exact ORPP endpoints, authentication flows, specific election deadlines, or provider-specific pricing — this guide treats them as **design assumptions requiring confirmation**, not established facts, consistent with the evidence-handling standard set in the PMaaS 5.0 review.

---

*End of consolidated technical implementation guide.*
