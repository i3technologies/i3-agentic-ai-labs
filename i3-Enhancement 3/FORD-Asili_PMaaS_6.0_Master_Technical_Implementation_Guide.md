# FORD-Asili PMaaS 6.0
## Master Technical Implementation Guide — Senior Solutions Architect Review & Consolidated Blueprint

**Prepared for:** Philip Mulala, CEO, i3 Technologies
**Client:** FORD-Asili (Forum for Republican Democracy–Asili) — National Executive Committee
**Delivery partners:** i3 Technologies (lead), Kinanie Technologies (technology partner), Jambocom General Merchants (merchandise partner)
**Classification:** Confidential — Internal i3 / FORD-Asili Technical & Governance Teams
**Version:** 6.0 (Consolidated — supersedes the standalone Blockchain/i3 Engage Guide v1.0 and the PMaaS 5.0 Review)
**Date:** September 2026

> **Not legal advice.** This is a technology/business architecture review. Every statutory, ORPP, IEBC and Data Protection Act reference below is an engineering-relevant compliance driver, not a legal opinion, and must be independently confirmed by FORD-Asili's legal/compliance counsel before any election-facing component goes live.

---

## Reviewer's Note

You supplied two documents that sit at different altitudes and need reconciling before either can be called implementation-ready:

- **The Blockchain Nomination & i3 Engage Technical Implementation Guide (v1.0)** is a tight, build-ready spec for exactly two subsystems — a Hyperledger Fabric nomination ledger and an i3 Engage recruitment pipeline — traced line-by-line to ten numbered requirements (R1–R10) and dated against the real IEBC 2025–2027 election clock.
- **The PMaaS 5.0 Technical, Business & Commercialisation Review** is a much wider independent audit of the whole PMaaS concept — party OS, ward intelligence, deepfake defence, GIS, agentic AI catalogue, governance and a post-election commercial business — and it explicitly flags the *first* document's underlying claims (the ORPP endpoint contract, the 200-member rule mechanism, SHA-256-as-anonymisation) as unverified design assumptions rather than settled facts.

Three structural issues needed resolving before this could be one coherent build plan, and I have resolved them below:

1. **Scope mismatch.** The Blockchain/Engage guide is a precise nomination-ledger spec; the PMaaS 5.0 Review is a whole-platform audit. I have nested the former inside the latter's 9-plane target architecture (Section 4) so the blockchain and Engage work is positioned as the **Core Party/Civic Plane + Trust Plane**, not a competing architecture.
2. **A factual contradiction on anonymisation needed fixing, not averaging.** The Blockchain/Engage guide's Section 9.1 describes on-chain data as *"SHA-256 hash of ID + salt"* and separately calls the ledger *"tamper-evident, not confidentiality-providing on its own"* — which is actually the right caveat. But the PMaaS 5.0 Review's independent finding is stronger and more precise: **a salted SHA-256 hash of a national ID is still low-entropy and dictionary-attackable; use a keyed HMAC/token vault, not a salted hash.** I have adopted the Review's correction as the binding spec in Section 8 below and flagged the original doc's language for update.
3. **Two roadmaps, two clocks, one election.** The Blockchain/Engage guide's roadmap is dated against the real IEBC calendar (16 Mar 2027 membership-list deadline, 17 Mar–10 Apr 2027 primaries, 10 Aug 2027 general election) with phase-by-phase engineering deliverables. The PMaaS 5.0 Review's roadmap is a generic 6-phase engineering-gate model without the specific dates. I have merged these into one dated roadmap (Section 14) that keeps the real dates and adds the Review's engineering exit-gate discipline.

Where a design assumption in either source still needs external legal or ORPP confirmation, it is marked **[VERIFY]**. Where I am adding architect judgment beyond what either source states, it is marked **[Architect's recommendation]**.

---

## Table of Contents

1. Executive Summary
2. What This Programme Actually Is — Reconciling Scope
3. Requirements Traceability (R1–R10)
4. Target-State Architecture — The Nine Planes
5. Blockchain Network Design (Hyperledger Fabric)
6. Identity, Authentication & Ballot Secrecy
7. i3 Engage Recruitment Drive Integration
8. Data Architecture, Zoning & Data Protection Act Compliance
9. Digital Primaries — End-to-End Design
10. Agentic AI: Full Agent Catalogue & Governance
11. Anti-Deepfake & Verified Media System
12. Ward Intelligence, GIS & Research Architecture
13. Infrastructure, Security & DevSecOps
14. Consolidated Implementation Roadmap (IEBC Clock)
15. Delivery Team & RACI
16. Commercialisation Strategy (Post-Election)
17. Best New Innovations — Prioritized
18. Governance, Legal & Regulatory Design
19. Risk Register (Consolidated Top Risks)
20. Testing, Security Audit & Certification Plan
21. KPI, SLO & Acceptance Framework
22. Production Readiness Checklist & Decision Gates
23. Appendix — Chaincode Reference, Glossary, Sources

---

## 1. Executive Summary

FORD-Asili's 2027 strategy requires running Kenya's largest simultaneous party nomination exercise — up to 1,881 seats, a modelled 1.45 million new members, digital primaries across 1,450 wards — against a hard 16 March 2027 IEBC membership-list deadline, on infrastructure cheap enough to run without Political Parties Fund income and simple enough to work on feature phones in low-connectivity wards.

The recommended architecture combines:

- A **permissioned Hyperledger Fabric ledger** for membership, nomination and primary-result events, replacing an ordinary relational "system of truth" with something FORD-Asili, ORPP and rival aspirants can independently verify.
- **Identity/ballot-secrecy separation** — turnout is fully auditable; individual vote choice is not.
- A **USSD/SMS bridge** (`*509#`-class) so rural, feature-phone members can register and vote without a smartphone or data bundle.
- **i3 Engage as the sole recruitment channel**, turning each of up to 1,881 candidates into an instrumented, rate-limited, consent-checked lead pipeline that writes only de-duplicated, verified members into the ledger — the direct engineering answer to the "1.45 million fake members" risk both source documents independently flag.
- A wider **9-plane platform** (Section 4) that positions the blockchain/Engage subsystem as the trust-critical core of a larger party operating system — collaboration engine, ward intelligence, deepfake defence, AI governance and a post-election commercial business — without letting any of those wider ambitions compromise the narrow, auditable, legally defensible nomination system that has to work first.

**Bottom line for delivery teams:** ship a minimum viable ledger + USSD registration + Engage recruitment pipeline within the 90-day window ending January 2027, ahead of the 16 March 2027 deadline. Digital primaries — the single highest-severity component in both source reviews — get **two full independent pilots** before the 17 March–10 April 2027 primaries window. Nothing in this build should require a rural voter to own a smartphone, and nothing in the wider platform ambition should be allowed to delay the trust-critical core.

---

## 2. What This Programme Actually Is — Reconciling Scope

| Layer | Source document | What it actually specifies |
|---|---|---|
| Trust-critical core (must work, legally contestable) | Blockchain/i3 Engage Guide v1.0 | Hyperledger Fabric nomination ledger, USSD registration, i3 Engage recruitment pipeline, digital primaries — R1–R10, dated to the real IEBC clock |
| Whole-platform ambition (strategic, longer runway) | PMaaS 5.0 Review | Party Collaboration Engine, ward intelligence/GIS, deepfake defence, agentic AI catalogue, commercialisation as a multi-tenant SaaS business, governance framework |

**[Architect's recommendation]** Treat these as two delivery tracks with a hard dependency in one direction only: the trust-critical core (Section 5–9 below) must ship on the IEBC clock regardless of what happens to the wider platform ambition. The wider platform (collaboration, ward intelligence, deepfake defence, commercialisation) can and should continue in parallel, but **no wider-platform feature should ever gain write access to the nomination ledger, the membership register, or the ballot-secrecy broker.** This is the same boundary both source documents independently insist on (R10 in the Blockchain guide; the "Commercial Data Diode" and party/commercial firewall in the PMaaS 5.0 Review) — it is restated here as the single most important architectural rule in this document.

---

## 3. Requirements Traceability (R1–R10)

Carried forward unchanged from the Blockchain/Engage guide — every engineering requirement traces to a specific OSINT/compliance finding so architecture and legal reviewers can verify nothing was invented outside the brief.

| # | Requirement | Source driver | System owner |
|---|---|---|---|
| R1 | Certified, de-duplicated membership register usable as the IEBC-submissible list | Political Parties Act; certified-register requirement | Blockchain + Membership CRM |
| R2 | Nomination rules encode free-MCA / Gen-Z waivers and existing NEC fee schedule without contradiction | NEC Aug-2026 fee notice vs. free-nomination proposal | Nomination Chaincode |
| R3 | 1,000 verified new members per ward (tiered 400–1,000 by ward type) tracked per candidate | Membership-duty design correction | Chaincode counters + i3 Engage |
| R4 | Refundable integrity deposit (KSh 2,000–5,000), waivable for PWD/indigent | Anti-frivolous-candidacy control | Daraja escrow + Chaincode |
| R5 | Digital primary with independent audit trail, ballot secrecy, and dispute workflow | Election-management-system framing, not "just an app" | Voting Chaincode + HSM |
| R6 | USSD/feature-phone access (`*509#`-class channel) | Rural connectivity constraint | USSD Gateway |
| R7 | Data Protection Act 2019 consent, minimisation, breach-proofing | Membership-register leak risk | Consent Service + Encryption |
| R8 | Independent security audit / penetration test before go-live | Digital-primary compromise risk (HIGH severity, both reviews) | Security & QA |
| R9 | 16 March 2027 membership list; 17 Mar–10 Apr 2027 primaries window | IEBC 2025–2027 Election Operation Plan | Programme / Delivery |
| R10 | Ward-level accountability dossier does not touch the nomination ledger | Separation of powers: campaign content vs. electoral system integrity | Architecture boundary |

**[VERIFY]** R2 (exact 200-member/fee-waiver mechanism) — the PMaaS 5.0 Review independently confirms this needs legal/party-constitution validation before being encoded as chaincode logic; do not hard-code it as a generic statutory rule (Section 18).

---

## 4. Target-State Architecture — The Nine Planes

**[Architect's recommendation]** This adopts the PMaaS 5.0 Review's "PMaaS 6.0 direction" nine-plane model as the outer architecture, and places every component from the Blockchain/Engage guide into its correct plane. This is the single reference diagram for the whole programme.

```
1. Trust Plane            Identity · Consent · Provenance · Audit · Policy-as-Code ·
                           Cryptographic Receipts · HSM/KMS
                                        │
2. Core Party/Civic Plane Membership · Nomination · Candidate · Digital Primaries ·
   (= Blockchain/Engage   Collaboration · Grievances · Finance/Escrow · Governance
    guide's scope)                     │
3. Communication Plane    USSD (*509#) · SMS · WhatsApp · Voice · Email · OTT —
                           all through consent-aware adapters, terminating at one
                           API gateway (no channel bypasses verification)
                                        │
4. Intelligence Plane     GIS · Ward Digital Twins · Public-source research ·
                           Scorecards · Evidence Graphs  [hard-isolated from R10]
                                        │
5. AI Plane               Model Gateway · RAG · Agents (Section 10) · Evaluation ·
                           Red-teaming · Multilingual QA · Cost controls
                                        │
6. Media Integrity Plane  C2PA Vault · Forensic Analysis · Verification Workflow ·
                           Correction System
                                        │
7. Commercial Plane       Isolated tenants · Product catalogue · Billing · CRM ·
                           Managed services  [hard-isolated from Planes 1–2]
                                        │
8. Reliability Plane      OpenShift/Kubernetes (ROKS) · GitOps · CI/CD ·
                           Observability · SIEM · DR · SRE
                                        │
9. Governance Plane       DPO · AI Governance Desk · Legal Desk · Security ·
                           Procurement firewall · Independent audit
```

**Architecture rule (both sources agree, restated as one rule):** no external channel writes directly to the system of record. Every channel terminates at an API gateway, passes identity/consent/rate-limit checks, and enters a domain service through a versioned contract. Every consequential workflow — a membership registration, a nomination certification, a ballot cast, an AI-generated public message — emits an immutable audit event.

### 4.1 Layer-to-plane mapping for the blockchain/Engage subsystem

| Blockchain/Engage guide layer | Maps to plane |
|---|---|
| Channel layer (web, mobile, USSD, WhatsApp) | Plane 3 — Communication |
| API & identity layer (gateway, Identity & Consent Service, Ballot-Secrecy Broker) | Plane 1 — Trust |
| Application services (Membership, Nomination, Primary Election, Fee/Escrow, Dedup, Dispute) | Plane 2 — Core Party/Civic |
| Ledger layer (Fabric chaincode, ordering service, peers) | Plane 1 + Plane 2 (ledger of record) |
| Off-chain data layer (encrypted PII, documents, analytics) | Plane 1 (identity vault) / Plane 4 (aggregate only) |
| Integration layer (Engage, Daraja, Qwen 14B, ORPP/IEBC export) | Cross-cutting — Plane 3 + Plane 5 |
| Platform & ops (ROKS, HSM/KMS, observability, DR) | Plane 8 — Reliability |

---

## 5. Blockchain Network Design (Hyperledger Fabric)

### 5.1 Why Hyperledger Fabric, not a public chain

- **Permissioned membership (MSP/CA)** matches the requirement for named, accountable validators — FORD-Asili's National Elections Board, i3 as technology operator, and an optional ORPP/independent-audit peer.
- **Channel / private-data-collection features** let ballot content be shared only among the peers that need it for tallying, while turnout events remain visible to all peers for audit — the mechanical basis of identity/ballot-secrecy separation (Section 6).
- **No token/cryptocurrency requirement, no public gas fees, no probabilistic finality** — Fabric transactions are final once endorsed and ordered, which matters for a legally contestable nomination result.
- **Runs natively on Red Hat OpenShift**, which i3 already operates on IBM Cloud (ROKS) for AI Lab workloads — reusing existing platform skills, monitoring and support contracts.

### 5.2 Network topology

| Organisation (MSP) | Role | Nodes operated | Notes |
|---|---|---|---|
| i3Tech-MSP | Technology operator / majority validator | 2× peer, 1× ordering-service member (Raft), CA | Runs on ROKS; on-call SRE ownership |
| FORDAsili-MSP | Party / National Elections Board | 1× peer, 1× ordering-service member, CA | Independent key custody — **NEC holds its own signing keys, never i3** |
| ORPP-Observer-MSP (optional, Phase 2) | Independent compliance observer | 1× read-only peer | Endorsement-exempt observer; strengthens legal defensibility of results |

- **Ordering service:** Raft consensus across i3Tech-MSP and FORDAsili-MSP orderers — crash-fault tolerant; no single organisation can unilaterally order transactions.
- **Channels:** a `membership` channel, a `nominations` channel (both i3Tech-MSP + FORDAsili-MSP), and a per-election-cycle `primaries-2027` channel using private data collections scoped per constituency to bound ledger size and blast radius.
- **Certificate Authorities** issue enrolment certificates to application services, not directly to end users; end users authenticate to the Identity Service, which acts on their behalf via service-account identities scoped by role.

### 5.3 Chaincode inventory

| Chaincode | Key functions | State written |
|---|---|---|
| MembershipRegistry | RegisterMember, VerifyMember, FlagDuplicate, RenewMembership, GetMemberStatus | Hashed national-ID reference, ward, status, consent timestamp |
| Nomination | OpenNominationWindow, SubmitCandidacy, ApplyWaiver(GenZ/MCA), RecordFeePayment, RecordMemberDutyProgress, CertifyEligibility, CloseNominationWindow | Candidate ID, seat, fee/waiver status, member-duty counter, eligibility flag, certification hash |
| Escrow | CollectDeposit, ReleaseDeposit, ForfeitDeposit, WaiveDeposit(PWD/indigent) | Deposit status keyed to candidate ID and Daraja transaction reference |
| PrimaryVoting | OpenBallot, CastEncryptedBallot, CloseBallot, RecordTurnoutEvent | Turnout event per verified voter (public); encrypted ballot content (private data collection) |
| ResultTally | Tally, PublishSignedResult, OpenDisputeWindow, RecordDisputeEvidence, ResolveDispute | Aggregated, signed result summaries; dispute case references and evidence hashes |

> **MUST — ballot secrecy control.** `CastEncryptedBallot` writes only a turnout event (member voted: yes/no, timestamped, publicly auditable) to the public channel state. The candidate choice is written only into a private data collection accessible to the tally peers, encrypted client-side before submission, and never linked to the voter's identity in any queryable index.

---

## 6. Identity, Authentication & Ballot Secrecy

### 6.1 Identity verification pipeline

1. Candidate/agent submits a new member via web, mobile, USSD, or an i3 Engage-driven WhatsApp/SMS flow — capturing full name, national ID number, phone number, ward, and explicit consent under the Data Protection Act 2019.
2. Identity Service validates ID-number and phone format, then calls the Dedup/Verification Service, which checks the encrypted PII store for existing matches **across the whole national register, not just within one ward.**
3. No duplicate → record created `pending`, OTP sent, confirmed → `MembershipRegistry.RegisterMember` writes the tokenised reference and status `verified` to the ledger.
4. Duplicate or suspicious bulk-registration pattern (same device/agent registering many members in a short window, sequential ID numbers, repeated phone prefixes) → status `flagged`, routed to the National Elections Board review queue — **never silently rejected or silently accepted.**

### 6.2 Authentication tiers

| Actor | Channel | Authentication |
|---|---|---|
| Ordinary member | USSD / SMS / WhatsApp | Phone-number possession (OTP) + national-ID match; no password |
| Ordinary member | Web/mobile app | Phone OTP + optional PIN for repeat sessions |
| Candidate | Candidate portal | Phone OTP + email verification + document upload; elevated KYC before nomination certification |
| Recruitment agent / candidate's team | i3 Engage campaign console | SSO via i3 identity provider + role-scoped API token; MFA mandatory |
| National Elections Board reviewer | Admin console | SSO + hardware-token MFA; all actions logged to an immutable audit channel |
| i3 platform engineer | Fabric CA / OpenShift console | Hardware-token MFA; break-glass access requires two-person authorisation and is itself logged on-chain |

### 6.3 Why never rely on a phone number alone

Both source documents independently flag phone-only authentication as legally insufficient. Mitigations: (1) national-ID cross-check against the certified register at registration time; (2) SIM-swap risk mitigated by binding a member's OTP-verified phone to a re-verification step if the number changes after registration; (3) any phone-number change for an already-active member requires a secondary verification path (in-person agent confirmation or video-KYC in Phase 2), never a bare SMS reset.

---

## 7. i3 Engage Recruitment Drive Integration

### 7.1 Why i3 Engage sits in front of the membership register

The single biggest technical risk both source reviews flag independently is **register inflation** — candidates chasing a 1,000-member (tiered 400–1,000) quota have every incentive to submit low-quality, duplicate, or coerced sign-ups. i3 Engage is the **only** channel through which bulk recruitment happens, so every recruitment interaction is instrumented, rate-limited, and consent-checked before it ever reaches `MembershipRegistry`.

### 7.2 Recruitment workflow

1. Candidate onboarded in the Candidate Portal; issued an i3 Engage campaign workspace scoped to their ward (or constituency, for MP-level races).
2. **Dawa** (the existing PMaaS AI co-worker) drafts ward-specific recruitment scripts for SMS, WhatsApp and voice-assisted USSD prompts; **a human campaign owner reviews and approves scripts before send — no AI-generated message reaches a voter unreviewed.**
3. i3 Engage runs the outreach sequence and captures consent-to-join responses as structured leads.
4. Each lead is pushed via the i3 Engage → Membership Service webhook into the identity verification pipeline (Section 6.1) — **Engage never writes directly to the ledger.**
5. **Rate limiting:** per-agent/per-candidate velocity cap (default 150 verified registrations/day/agent) throttles submission spikes into human review rather than silently accepting them.
6. The candidate's live member-duty counter is exposed back into their i3 Engage dashboard — turning recruitment into a gamified, real-time progress view rather than a black box.

### 7.3 Technical integration points

| Integration point | Direction | Payload / mechanism |
|---|---|---|
| Campaign creation API | PMaaS → i3 Engage | Ward, candidate ID, approved script variants, target headcount, campaign window |
| Lead capture webhook | i3 Engage → Membership Service | Name, phone, national ID (where captured), ward, consent flag, agent ID, timestamp |
| Consent double-opt-in | i3 Engage ↔ member | WhatsApp/SMS confirmation with explicit opt-in link before lead is marked consented |
| Progress feed | Membership Service → i3 Engage dashboard | Verified-member count, flagged count, duplicate-rejection count per candidate |
| Dedup signal | Dedup/Verification Service → i3 Engage | Suppresses re-targeting of already-registered numbers |
| Script content | Dawa AI → i3 Engage (via human approval queue) | Draft ward-specific copy; never auto-published |

### 7.4 Compliance guardrails specific to Engage

- Every outbound message includes a clear opt-out/STOP instruction; opt-outs propagate immediately.
- Membership must **never** be represented as tied to a promise of public benefit (CDF, bursary, jobs) in script content — enforced by a keyword/policy linter in the script-approval queue, not left to reviewer memory.
- Engage campaign data retention follows the platform-wide retention schedule (Section 8); raw outreach logs are purged after the statutory retention period while consented, verified member records persist in the register.

---

## 8. Data Architecture, Zoning & Data Protection Act Compliance

**[Architect's recommendation — binding correction from the PMaaS 5.0 Review]** The Blockchain/Engage guide's Section 9.1 specifies on-chain identity as a "SHA-256 hash of ID + salt." **This is not adequate anonymisation.** National ID numbers are low-entropy; a salted hash of a low-entropy value is still dictionary-attackable at scale. Replace this with:

> **Binding spec:** on-chain identity references MUST use a **keyed HMAC (or equivalent keyed pseudonymisation) token**, with the signing key held in the same HSM/KMS infrastructure already specified for Fabric organisation keys (Section 5, 9.2 of the Blockchain guide). The key-to-identity mapping is stored only in the segregated identity vault, never derivable from the on-chain token alone, and never exposed to analytics or commercial-plane consumers.

### 8.1 Three-zone data model (PMaaS 5.0 Review, applied to this build)

| Data class | Examples | Storage | Access | Retention |
|---|---|---|---|---|
| **Zone A — Identity vault** | National ID, phone, legal name, consent evidence | Encrypted off-chain PII store; HMAC token service | Identity Service + authorised DPO/compliance roles only | Shortest period necessary per retention schedule |
| **Zone B — Operational party data** | Membership status, join/resign events, ward, candidate declarations, nomination evidence | PostgreSQL / Fabric ledger (tokenised references) | Party operations by role | Retain while active + statutory election-record period |
| **Zone C — Aggregate intelligence** | Ward issue counts, service scorecards, news trends | Warehouse/OpenSearch | Operational dashboards; public subset | Aggregate, non-identifying |
| Media | Audio/video/images + C2PA manifests | Object storage + provenance registry | Content studio, verification desk | Versioned; preserved for disputes |
| Commercial client data | Brand campaigns, customer lists, content assets | **Separate tenant/data plane** | Client + commercial team only | Client contract terms |

### 8.2 What lives where (blockchain-specific detail)

| Data class | Storage location | Protection |
|---|---|---|
| National ID, full name, raw phone | Encrypted off-chain PII store (not on ledger) | AES-256 at rest, field-level encryption, Identity Service access only |
| Identity reference | On-chain (MembershipRegistry state) | **Keyed HMAC token** (corrected from salted SHA-256); tamper-evident, not confidentiality-providing on its own |
| Candidate documents | Encrypted document store, referenced by hash on-chain | Access-controlled; hash proves non-tampering without exposing the document |
| Ballot choice (encrypted) | Private data collection, tally-peer scoped | Client-side encryption; decryptable only within the tally process |
| Turnout events | Public channel state | Publicly auditable; contains no vote content |
| Engage outreach logs | i3 Engage data store | Purged per retention schedule; consented leads promoted, raw logs not retained indefinitely |
| Ward accountability dossier data | Separate analytics store — architecturally isolated from the nomination ledger | Public-source data; kept out of the electoral system per R10 |

### 8.3 Consent ledger (PMaaS 5.0 Review requirement, applied here)

Store: purpose, notice version, timestamp, channel, language, affirmative action, lawful basis, withdrawal event, processor/controller role, policy version in force. A consent record is immutable as an event; current consent state is materialised for fast checks.

### 8.4 Key management

- All Fabric organisation signing keys generated and stored in an **HSM** — FORD-Asili's NEC keys are never held by i3 staff; i3 provisions the HSM partition and access ceremony, but **custody of NEC key material is FORD-Asili's.**
- Client-side ballot encryption keys (tally-peer public key) rotated per election cycle, published in advance for independent verification.
- Break-glass administrative access to production Fabric peers requires **two-person authorisation** and is itself recorded as an audit-channel transaction.

### 8.5 Data Protection Act 2019 controls

- **Lawful basis:** explicit, opt-in consent captured at registration and at every i3 Engage touch-point; consent is itself a timestamped, revocable record.
- **Data minimisation:** only tokenised identifiers and status flags go on-chain; raw PII stays in the encrypted off-chain store, never replicated to Fabric peers.
- **Purpose limitation:** membership data collected for party registration MUST NOT be repurposed for the ward accountability dossier or campaign-messaging beyond party administration without a fresh consent basis.
- **Breach response:** documented incident-response runbook (Section 13.3) with mandatory notification timelines; encrypted-at-rest design limits blast radius even in a partial breach.
- A **Data Protection Officer** function (party-side, i3 as processor) is designated before the membership drive begins at scale.

---

## 9. Digital Primaries — End-to-End Design

### 9.1 Primary-day sequence

1. NEC opens the ballot for a given ward/seat via `PrimaryVoting.OpenBallot`, referencing a Merkle-rooted extract of `MembershipRegistry` state as of the certification date.
2. Eligible voter authenticates (Section 6.2) and receives a one-time ballot token bound to their verified member ID but cryptographically unlinkable to their eventual candidate choice.
3. Voter casts a ballot; client encrypts the candidate choice with the tally peers' public key before submission. `CastEncryptedBallot` writes (a) a public turnout event and (b) the encrypted choice into the private data collection.
4. At close, `ResultTally.Tally` runs only on designated tally peers, decrypts within that trusted execution context, aggregates, and calls `PublishSignedResult` — a signed, publicly verifiable result summary (turnout, per-candidate totals, rejected-ballot count) written to the public channel.
5. A dispute window (default 72 hours) opens automatically; `OpenDisputeWindow` and `RecordDisputeEvidence` let any candidate or NEC member submit evidence, hashed and time-stamped on-chain even though underlying documents live off-chain.

### 9.2 Offline / connectivity contingency

- USSD voting sessions are **stateful and resumable** at the gateway — a dropped session does not invalidate a partially-completed ballot.
- For confirmed connectivity failure on primary day, a pre-agreed **paper/manual fallback ballot** is reconciled into the ledger post-hoc via a manual `RecordOfflineBallot` transaction requiring two-person sign-off, with paper ballots retained as physical evidence.
- All Fabric peers replicate synchronously within the Raft ordering group; a single data-centre outage does not halt the network provided a majority of orderers remain reachable.

### 9.3 Pilot requirements before go-live

Digital primaries are the single highest-severity risk in both source reviews (Blockchain guide: T2/T3 "Very high"; PMaaS 5.0 Review: "Critical," top of the Top-20 register). **i3 MUST run two independent, full-scope pilots:**

- **Pilot 1** (target: December 2026, 2 wards) — functional and usability validation, including USSD flow with real feature phones on multiple network operators.
- **Pilot 2** (target: February 2027, 5–10 wards across ≥3 counties) — load, security, and dispute-workflow validation, including a **simulated DDoS** and a **simulated insider-rigging attempt**, run by the independent security auditor (Section 20).

---

## 10. Agentic AI: Full Agent Catalogue & Governance

**[Architect's recommendation]** The two source documents describe overlapping but non-identical agent sets — the Blockchain guide only mentions Dawa (script drafting); the PMaaS 5.0 Review specifies a much fuller catalogue. Merged and governed under one model here.

### 10.1 Unified agent catalogue

| Agent | Allowed autonomy | Never autonomous | Evaluation metric |
|---|---|---|---|
| **Registration/Dedupe** | Validate format; identify likely duplicates; request missing fields | Final rejection where ambiguous; legal membership decisions | Precision/recall of duplicate flags; false-rejection rate |
| **Content Factory (Dawa)** | Draft recruitment/content and translations | Publish without approval | Factuality; language QA; approval-rejection rate |
| **Call Centre** | Answer approved FAQs; create cases | Money/legal/sensitive decisions | Containment; escalation accuracy; hallucination rate |
| **Ward Intelligence** | Collect/summarise public sources; compute aggregates | Individual persuasion profile or covert monitoring | Source coverage; citation accuracy; false-claim rate |
| **Deepfake** | Score media and assemble evidence | Declare guilt solely from model score | Precision/recall; analyst confirmation rate |
| **Compliance** | Detect missing controls and deadline drift | Autonomously waive legal controls | Finding precision; time-to-remediation |
| **Finance** | Match invoices and flag variance | Release funds | Reconciliation accuracy; exception detection |
| **Minutes** | Draft minutes and action items | Finalise official minutes without chair confirmation | Edit distance; missed action rate |

### 10.2 AI Model Gateway (single control point)

Every model sits behind one internal gateway enforcing: model allowlists, data-classification rules, prompt templates, max token/cost budgets, redaction, tool permissions, output schemas, provenance, evaluation hooks and kill switches. The existing on-cluster **Qwen 14B** (AI Campaign Briefing module) and **Dawa** both route through this gateway — no direct model access from application code.

### 10.3 RAG & agent memory

Candidate/party assistants answer from a versioned knowledge base of approved policies, nomination rules, FAQs and official documents — retrieval tenant- and role-scoped. **Do not give agents unrestricted persistent memory** — use task-scoped state plus a controlled knowledge store; sensitive information never becomes "memory" merely because an agent saw it.

### 10.4 Governance baseline

NIST's AI RMF frames trustworthy AI as a lifecycle risk-management problem, aligning with both source documents' emphasis on human-in-the-loop checkpoints, logging and weekly review. Kenya's National AI Strategy 2025–2030 is the applicable national-policy context. **[VERIFY]** current AI-inventory/risk-tier registration requirements against the strategy before go-live.

---

## 11. Anti-Deepfake & Verified Media System

**[Architect's recommendation, from the PMaaS 5.0 Review]** Redesign the "Verified Media Vault" as an evidence system with four **independent** signals, avoiding the common mistake of treating one detector score as truth.

| Signal | Implementation | Output |
|---|---|---|
| Provenance | C2PA manifest, signer identity, asset hash, ingredients and edits | Authenticity/provenance evidence |
| Forensics | Audio spectral features, face/voice consistency, compression artefacts, model ensemble | Risk score + evidence snippets |
| Source verification | Compare against official vault, publication timestamps, known official channels | Source-of-record match |
| Human review | Two-person review for high-impact incidents | Confirmed / unconfirmed / insufficient evidence |

**Incident state machine:** `NEW → TRIAGED → FORENSIC_REVIEW → HUMAN_CONFIRMATION → RESPONSE_DRAFT → APPROVED → PUBLISHED → ARCHIVED`. Every transition is signed or attributable.

**Response packet** should contain: what was detected, what is known, what is not known, a link/QR to the verified original, the C2PA credential, time of verification, reviewer ID, and a correction if earlier information was wrong. Avoid amplifying false content unnecessarily.

**Voice cloning** (referenced in the wider PMaaS blueprint's vernacular voice ambitions) is a **restricted capability**: prefer generic synthetic voices for routine content; identity-linked cloning only with explicit documented authorisation, visible/audible disclosure, key rotation and revocation. A consented reference sample never becomes a general-purpose biometric database.

---

## 12. Ward Intelligence, GIS & Research Architecture

Converts fragmented public information into structured, local operational knowledge — must remain **aggregate and source-disciplined**, and architecturally isolated from the nomination ledger per R10 (Section 3).

**Recommended GIS stack:** PostgreSQL/PostGIS for authoritative spatial relationships; MapLibre/OpenLayers for web maps; vector tiles; a boundary version registry; a data-quality service recording source, date, licence, geometry validity and update status.

| Dataset | Use | Quality control | Privacy boundary |
|---|---|---|---|
| Administrative boundaries | County/constituency/ward mapping | Version and checksum every release | No personal data |
| Public infrastructure | Service scorecards, project tracking | Source/date/confidence fields | Aggregate only |
| County budget/CIDP | Budget/implementation dashboards | Parser + manual exception queue | No individual profiling |
| Public news | Issue/news digest | Source allowlist + duplicate detection | Public content only |
| Public social posts | Aggregate trend signals | API/licensing + sampling + provenance | No individual persuasion profile |
| Survey research | Issue/opinion research | Sampling plan + weighting + consent | Aggregate-level storage where possible |

**Innovation — Ward Digital Twin:** each ward has a living operational object (boundary, service indicators, public issues, programme activities, content calendar, training status, infrastructure evidence) — a governance object, **not a profile of the people living there.**

**Innovation — evidence graph:** links every scorecard item to source documents, photos, geospatial evidence, dates and review status — a defensible chain from raw evidence → extracted fact → aggregate indicator → published statement.

**Research engine:** USSD/CATI/CAPI with weighting, kept strictly **separate from party membership records**. Never use inferred or historical political affiliation as an individual-level weighting feature.

---

## 13. Infrastructure, Security & DevSecOps

### 13.1 Platform stack

| Component | Technology | Notes |
|---|---|---|
| Container platform | Red Hat OpenShift on IBM Cloud (ROKS) | Reuses i3's existing ROKS AI Lab footprint |
| Blockchain runtime | Hyperledger Fabric 2.5 LTS | Peers/orderers as OpenShift StatefulSets; Fabric Operator for lifecycle |
| API layer | Node.js/Express behind API Gateway | Rate limiting, request validation, OAuth2/OIDC |
| Identity provider | Keycloak (Red Hat SSO) or IBM App ID | SSO for internal/agent/NEC users; OTP service for members |
| USSD gateway | Africa's Talking / Safaricom USSD aggregator | Reuses existing `*509#`-class channel |
| Messaging | i3 Engage platform, WhatsApp Business API | Recruitment and notification channel |
| Encrypted PII store | IBM Cloud Databases (Postgres) + field-level encryption / IBM Key Protect | Off-chain sensitive data |
| Document store | IBM Cloud Object Storage (encrypted buckets) | Candidate documents, evidence artefacts |
| Observability | Prometheus/Grafana + IBM Cloud Log Analysis; OpenTelemetry traces/metrics/logs | Ledger health, endorsement latency, chaincode error rates |
| CI/CD | OpenShift Pipelines (Tekton) + GitOps (ArgoCD) | Mandatory peer review on chaincode and service deployment |

### 13.2 Environments & scalability targets

- Dev → Test → Staging (pilot) → Production, each on separate OpenShift namespaces/clusters with separate Fabric channels; **no shared keys across environments.**
- Staging mirrors production sizing and network conditions (including simulated low-bandwidth USSD sessions) and is the environment for both mandatory pilots (Section 9.3).

| Metric | Target |
|---|---|
| Concurrent USSD sessions (peak, primary day) | ≥ 5,000 nationally |
| Membership registrations processed | ≥ 50,000/day sustained during the recruitment drive |
| Ballot transactions per ward, primary day | Worst case ~15,000 votes/ward within a 12-hour window |
| Ledger write latency (endorsement to commit) | < 2 s at P95 under peak load |
| Platform availability, primaries window | ≥ 99.9%, multi-zone IBM Cloud region |
| Core platform uptime (general) | ≥ 99.9% monthly for critical services |
| API p95 latency | < 500 ms for standard reads; heavy jobs asynchronous |

### 13.3 Security controls (DevSecOps baseline, from the PMaaS 5.0 Review)

| Control | Production requirement |
|---|---|
| Zero trust | Every service authenticates; no implicit trust inside the cluster |
| Privileged access | MFA + step-up authentication + just-in-time elevation + session logging |
| Secrets | KMS/HSM-backed secret management; no secrets in Git or container images |
| Encryption | TLS 1.3 where supported; AES-256-class at rest; key rotation |
| Supply chain | SBOM, signed images, dependency scanning, release provenance |
| Application security | OWASP ASVS-based verification; SAST/DAST/API testing; threat modelling |
| Resilience | Multi-zone deployment; tested backups; defined RPO/RTO; quarterly restore tests |
| AI security | Prompt-injection defence, tool allowlists, DLP, model-output validation |

**Security innovation — cryptographic action receipts:** every high-impact workflow generates a signed receipt containing actor, role, input evidence hash, policy version, model/version if AI-assisted, approval chain and resulting state — a portable audit package for disputes and audits.

---

## 14. Consolidated Implementation Roadmap (IEBC Clock)

**[Architect's recommendation]** This keeps the Blockchain/Engage guide's real dates and folds in the PMaaS 5.0 Review's engineering exit-gate discipline.

| Phase | Window | Engineering deliverables | Exit gate |
|---|---|---|---|
| **0 — Foundations & Governance** | Now – 15 Oct 2026 | Fabric network stood up on ROKS; MSPs/CAs provisioned; NEC HSM key ceremony; nomination-rules config schema agreed with legal; DPIA; data inventory; threat model | Architecture Review Board approval |
| **1 — Rules-to-Code** | By 30 Oct 2026 | Nomination chaincode encodes certified rules (fee schedule, waivers, deposit); ORPP certification sign-off obtained **before** this date | Legal sign-off on encoded rules |
| **2 — Platform MVP** | Nov 2026 – Jan 2027 | Membership registry live; USSD registration live; i3 Engage recruitment integration live in 5 pilot counties; candidate portal with live member-duty counter; Command Hub operational | Pilot with synthetic/test data passed |
| **3 — Mass Recruitment Support** | Dec 2026 – 16 Mar 2027 | Platform scaled to all 47 counties / 1,450 wards; dedup and anomaly-detection tuned under real load; membership list frozen and certified | Membership list certified for 16 Mar deadline |
| **4 — Digital Primaries** | Pilot 1: Dec 2026 · Pilot 2: Feb 2027 · Live: 17 Mar–10 Apr 2027 | Voting chaincode hardened, security-audited, piloted twice; dispute workflow operational; AI gateway, RAG, agents, media vault, C2PA, forensic pipeline live | AI red-team + human-approval certification; SRE readiness + election continuity drill |
| **5 — General Election Support** | 29 May – 10 Aug 2027 | Candidate registration exports to IEBC; platform moves to steady-state monitoring; ledger retained as permanent audit record | 24/7 operational command through election day |
| **6 — Post-Election** | Aug 2027 onward | Governance mode, archive, data retention/closure, platform hardening; commercial tenant layer activation (Section 16) | Independent audit + product transition |

**Critical path (both sources agree):** data governance → identity → workflow/audit → integrations → communications → AI → GIS → commercial multi-tenancy. **Do not reverse this order** — building AI agents or the wider platform ambition before the permission and audit substrate is finished creates rework and risk on the one component that cannot slip: the certified membership list.

---

## 15. Delivery Team & RACI

| Workstream | i3 Solutions Architect | i3 Blockchain Eng. | i3 Engage Team | i3 Security | FORD-Asili NEC |
|---|---|---|---|---|---|
| Network & chaincode design | A | R | C | C | I |
| Nomination-rules encoding | R | C | I | I | **A** |
| i3 Engage recruitment integration | C | I | R | C | I |
| USSD/mobile channel | C | R | I | C | I |
| HSM / key custody ceremony | C | R | I | A | **R** |
| Independent security audit coordination | C | I | I | A | I |
| Digital-primary pilots | A | R | I | R | R |
| Go-live certification sign-off | C | C | I | R | **A** |

R = Responsible, A = Accountable, C = Consulted, I = Informed. **FORD-Asili NEC accountability on rules-encoding, HSM custody, and go-live sign-off is deliberate** — these are governance decisions, not purely technical ones. i3 builds and recommends; the party owns and certifies its own election-management rules.

**Recommended core team (from the wider PMaaS 5.0 Review, scaled to this programme's needs):** Solutions Architect (lead, full engagement), Blockchain/backend engineers, Frontend engineer(s), Data/ML engineer, Integration engineer, DevOps/Platform engineer, Security engineer, QA/Test engineer, Product/Delivery lead — drawing on i3's existing bench and, where useful, i3 Academy graduates as a talent pipeline.

---

## 16. Commercialisation Strategy (Post-Election)

**[Architect's recommendation]** This section applies only to Phase 6 (Section 14) and only to the non-political technology built for this programme — never to party or member data (Section 8, Section 2's hard boundary).

The commercial thesis: build a difficult-to-replicate operational platform for a major election programme, then reuse the **non-political technology** — software, managed operations, content infrastructure, provenance technology, research tooling, workflow automation — in enterprise, civic, media and communications markets. **The asset for sale is never voter/member profiles.**

| Business line | Product | Buyer | Pricing model | Moat |
|---|---|---|---|---|
| Vernacular Communications Cloud | Campaign/content orchestration in African languages | FMCG, agritech, fintech, telco, NGOs | Platform + usage + managed service | Language workflows + distribution integrations |
| Brand Integrity Shield | C2PA vault + monitoring + incident response | Brands, executives, media orgs | Monthly retainer + incident tier | Provenance + evidence workflow |
| Civic/Community OS | Ward/community dashboards, grievances, scorecards | NGOs, foundations, programmes | Annual licence + implementation | GIS + evidence graph + offline channels |
| Research Cloud | USSD/CATI/CAPI + analysis workflow | Research firms, universities, NGOs | Per study + platform subscription | Multi-channel field infrastructure |
| AI Governance Desk | AI policy, evaluation, red-team, audit | Mid-market/enterprise | Retainer | Operational governance, consulting-only |
| Localized Content Factory | Rapid multi-language creative production | SMEs and agencies | Per campaign/package | Workflow automation + language assets |
| Managed Collaboration | Sovereign/self-hosted collaboration and workflow | Institutions and networks | Per tenant + support | Data ownership + custom workflow |

**Commercial entity separation:** a separate commercial operating unit with separate contracts, data stores, IAM realms/tenants, billing, support and security policies. **A party customer must never become the data source for another commercial client.** The party platform is a reference implementation; its data is never a product.

**Illustrative three-year revenue scenarios (KES millions, planning framework only — not a forecast):**

| Scenario | Year 1 | Year 2 | Year 3 | 3-year total |
|---|---|---|---|---|
| Conservative | 28 | 58 | 92 | 178 |
| Base planning case | 45 | 95 | 165 | 305 |
| Upside | 65 | 145 | 260 | 470 |

Base-case gross margin progresses 55% → 65% → 72% as revenue shifts from implementation-heavy to recurring software/managed-service. **Track:** ARR, gross margin by service line, cost-to-serve per tenant, AI inference cost per workflow, communications cost per delivered message/session, support tickets per 1,000 users, CAC, payback period, net revenue retention, implementation-to-recurring conversion.

---

## 17. Best New Innovations — Prioritized

Consolidated from both source documents into one priority list.

| Innovation | What it adds | Why it matters | Priority |
|---|---|---|---|
| Trust Fabric | Every important record has provenance, actor, policy and evidence | Turns the platform into an auditable institution | P0 |
| Keyed-HMAC identity tokens (not salted hash) | Correctly anonymised on-chain identity references | Closes the dictionary-attack gap in the original spec (Section 8) | P0 |
| Policy-as-Code | DPA/AI/publication rules executable by gateways/workflows | Prevents policy drift | P0 |
| AI Model Gateway | One controlled entry point for all models (Qwen 14B, Dawa, others) | Controls cost, data leakage and model sprawl | P0 |
| Ballot-Secrecy Broker | Application-layer component issuing anonymised ballot tokens | Breaks the identity↔vote-choice link mechanically, not by policy | P0 |
| Commercial Data Diode | One-way controlled aggregate outputs from party analytics to approved public reporting | Prevents accidental commercial data leakage | P0 |
| Evidence Graph | Links claims to source evidence, media and approvals | Improves disputes, journalism and transparency | P0 |
| Ward Digital Twin | Persistent aggregate operational object per ward | Reusable civic/governance product, commercially and operationally | P1 |
| Offline-First Field Mesh | Encrypted local queue + sync for poor connectivity | Improves field reliability (complements USSD resumable sessions) | P1 |
| AI Evaluation Lab | Golden datasets, multilingual tests, adversarial prompts, regression suite | Makes AI quality measurable | P1 |
| Provenance QR | Human-readable verification QR on every official media asset | Makes C2PA useful to ordinary audiences | P1 |
| Synthetic Data Factory | Generate non-production test populations and workflow cases | Enables safe engineering without exposing member data | P1 |
| Digital Public Evidence Room | Public archive of policies, approvals, scorecards and corrections | Builds institutional trust | P1 |
| Cryptographic action receipts | Signed receipt per high-impact workflow | Portable audit package for disputes and audits | P1 |
| FinOps for AI | Cost attribution per agent/workflow/customer | Prevents AI economics from becoming invisible | P1 |
| Partner Marketplace | Certified integrators and language/content vendors | Scales delivery without losing standards | P2 |
| Pan-African Portability | Configurable country/legal adapters | Exportable IP beyond Kenya | P2 |

The original PMaaS 5.0 blueprint also proposes a Super-App, Candidate AI Co-Pilot, Resolution Ledger, Pan-African Partner Bridge, Volunteer Task Marketplace, micro-credentials, accessibility-first design, QR-first materials, a secure grievance channel and predictive resource allocation — the priority list above turns those ideas into product modules with explicit sequencing rather than a flat feature list.

---

## 18. Governance, Legal & Regulatory Design

This section identifies implementation dependencies, not legal advice. A standing **Legal & Compliance Desk and DPO function** with a written authority matrix is required before scale.

| Topic | Current source signal | Implementation implication |
|---|---|---|
| Party membership technology | Kenya's Political Parties (Membership) Regulations require technology used for recruitment to conform to prescribed requirements, with Registrar certification before deployment | **[VERIFY]** Do not launch membership technology as final until the certification/approval pathway is confirmed |
| ORPP/IPPMS integration | ORPP confirms an API module for secure system-to-system exchange and validation, but not the specific endpoint contract this build assumes | **[VERIFY]** Use a formal integration adapter; confirm schema, authentication, rate limits and reconciliation process directly with ORPP before go-live |
| Membership lists | Elections Act contains submission/certification obligations | Build a deadline engine and pre-submission reconciliation workflow |
| 200-member rule (R2) | Independent-candidate provisions contain separate supporter thresholds distinct from the blueprint's exact mechanism | **[VERIFY]** Validate against party constitution and current law before encoding as chaincode logic — do not treat as a generic statutory rule |
| Data protection | ODPC guidance applies data-protection requirements to voter registration, party membership and campaigning; processing must be lawful, fair, specified and proportionate | DPIA, DPO, consent/notice, retention, rights, processor contracts and incident response are first-class deliverables |
| Sensitive political data | Political opinion/adherence is sensitive personal data under the Kenyan registration framework | Never infer or commercialise individual political profiles; aggregate where possible |
| AI governance | Kenya's National AI Strategy 2025–2030; NIST AI RMF as an operational governance framework | AI inventory, risk tiers, evaluation, human oversight and incident register |
| Election technology | IEBC has flagged AI/new-media opportunities and risks in its 2027 election-technology planning | Keep the platform clearly separate from statutory election administration systems unless formally authorised |

**Legal-risk red lines (both sources agree):** no private-message scraping; no covert individual voter profiling; no sale of political opinion data; no automated final legal decisions; no unverified claims presented as fact; no autonomous disbursement; no biometric/voice identity expansion beyond documented purpose; **no production use of an external integration until its authority and contract are confirmed.**

---

## 19. Risk Register (Consolidated Top Risks)

| # | Risk | Severity | Mitigation (engineering-owned) |
|---|---|---|---|
| 1 | Unverified ORPP integration assumptions | Critical | Formal interface discovery, test environment, contract tests, reconciliation, human fallback |
| 2 | Wrong interpretation of the 200-member rule | Critical | Validate against party constitution, nomination rules and current law before implementation |
| 3 | Political-opinion data leakage | Critical | Data zoning (Section 8), access policy, no commercial query path, aggregate-only intelligence |
| 4 | Register inflation via bulk/duplicate recruitment | High | i3 Engage rate limiting, dedup service, human-review queue (Sections 6.1, 7.2) |
| 5 | Digital-primary manipulation (insider rigging, DDoS) | Very high | Two-person HSM key custody, independent audit peer, pre-primary pilots, signed results |
| 6 | Ballot secrecy failure (vote linked back to voter) | Very high | Private data collection + client-side encryption, independently code-reviewed |
| 7 | Data Protection Act breach of membership register | Very high | Field-level encryption, off-chain PII isolation, incident-response runbook |
| 8 | Salted-hash-as-anonymisation weakness in original spec | High | **Corrected in this document** — keyed HMAC/token vault (Section 8) |
| 9 | USSD/network outage on primary day | High | Stateful resumable sessions, paper fallback with two-person reconciliation |
| 10 | Contradiction between certified nomination rules and platform logic | High | Nomination chaincode config driven by a signed rules document reviewed by legal each cycle; no hard-coded fee logic |
| 11 | Commercial data cross-contamination | Critical | Separate tenant/data planes, automated policy tests, Commercial Data Diode |
| 12 | Insider misuse | Critical | Least privilege, dual control, audit and anomaly detection |
| 13 | AI hallucination in public content | High | RAG, source citations, schema validation, human approval, regression tests |
| 14 | Deepfake false positive | High | Multi-signal detection + human confirmation + transparent evidence |
| 15 | Voice-cloning abuse | High | Restricted keys, explicit authorisation, disclosure, revocation |
| 16 | Credential theft | Critical | MFA, phishing-resistant auth where feasible, PAM, device/session controls |
| 17 | Cloud outage | High | Multi-zone deployment, backups, tested DR, manual fallbacks |
| 18 | IEBC/ORPP timeline slippage vs. build schedule | Medium | Roadmap back-timed from statutory dates with buffer (Section 14) |
| 19 | Ward accountability dossier bleeding into the electoral system | Medium | Hard architectural separation (R10); dossier store has no write path to any chaincode |
| 20 | Key-person / operational dependency on a small i3 delivery team | Medium | Documented runbooks, cross-trained SRE pair, FORD-Asili NEC holds its own HSM key custody |
| 21 | Programme scope explosion (wider platform ambition delaying trust-critical core) | High | **[Architect's recommendation]** Product council, P0/P1/P2 roadmap, change-control board; enforce the one-way dependency in Section 2 |

---

## 20. Testing, Security Audit & Certification Plan

### 20.1 Test layers

- **Unit & chaincode tests:** every chaincode function covered by automated tests in CI; no chaincode deployed to Staging without passing coverage thresholds.
- **Integration tests:** end-to-end candidate journey (registration → recruitment → verification → nomination → voting → tally) run nightly against Staging.
- **Load tests:** simulate the scalability targets in Section 13.2, including worst-case ward turnout and simultaneous USSD sessions.
- **Chaos/failover tests:** kill individual peers/orderers during a simulated primary to confirm Raft failover does not corrupt or halt the ledger.

### 20.2 Independent security audit (MUST, before go-live)

- Engage an **independent third-party security firm** (not i3) for a full penetration test of the API layer, USSD gateway, Fabric network configuration, and key-management ceremony.
- **Independent code review of the ballot-secrecy mechanism** specifically, given its Very High severity rating.
- A **simulated insider-rigging exercise** (red-team) targeting the tally process, executed during Pilot 2.
- Findings remediated and a **written certification issued before the 17 March 2027 primaries window**; any Critical/High finding blocks go-live until resolved.

### 20.3 Incident response

A documented runbook covering: detection (observability alerts + anomaly detection on registration velocity and ballot patterns), containment (ability to pause a specific ward's primary via NEC-authorised two-person action), notification (Data Protection Act timelines), and post-incident review feeding back into the risk register.

---

## 21. KPI, SLO & Acceptance Framework

| Domain | KPI / SLO | Target philosophy |
|---|---|---|
| Availability | Core platform uptime | ≥99.9% monthly for critical services |
| API | p95 latency | <500 ms for standard reads; async for heavy jobs |
| Messaging | Delivery success | Track accepted, delivered, failed, opted-out separately |
| AI | Hallucination / factual error | Task-specific ceilings; 100% human approval for public political content |
| AI | Tool execution | 0 unauthorised tool calls; continuous audit |
| Security | Critical vulnerability remediation | Defined SLA by severity; no release with unwaived criticals |
| Privacy | Consent completeness | 100% for workflows requiring consent before processing |
| Audit | High-impact actions with receipts | 100% |
| Deepfake | Triage time | ≤15 min target; response SLA 90 min normal / 30 min peak |
| Research | Methodology traceability | 100% of published results linked to sampling/weighting metadata |
| Commercial | Gross margin | Improve as recurring platform revenue grows |
| Support | First response | Tiered by severity; 24/7 only for defined critical services during peak |

**Acceptance principle:** no module is "done" when the code works. It is done when the workflow works under normal conditions, adverse conditions, security tests, privacy tests, operational load, staff training and audit review.

---

## 22. Production Readiness Checklist & Decision Gates

**Minimum Definition of Done**

- Architecture and threat model approved.
- Data inventory and retention schedule approved by governance owner.
- All privileged users protected by MFA and least-privilege roles.
- Every high-impact workflow emits an audit receipt.
- Public AI-assisted content cannot bypass human approval.
- Commercial tenants cannot query party/member data.
- External integrations are adapter-based and contract-tested.
- C2PA credentials are verifiable; key rotation is tested.
- AI models evaluated on multilingual and adversarial test sets.
- Backup restore and disaster-recovery exercises have passed.
- Operational runbooks exist for outage, breach, deepfake incident and regulatory request.

**Decision gates for the board**

1. Approve the target architecture and trust-plane-first sequencing (Section 4).
2. Approve the legal validation workstream **before** locking election-specific rules into code (Section 18).
3. Approve the political/commercial data firewall as a non-negotiable control (Section 2, Section 8).
4. Approve a modular platform strategy instead of a large microservice build on day one.
5. Approve the AI governance charter and human-approval policy (Section 10).
6. Approve the commercial product portfolio and illustrative financial planning envelope (Section 16).
7. Approve independent security/privacy testing **before** national scale (Section 20).

---

## 23. Appendix

### 23.1 Chaincode Function Reference

| Chaincode | Function | Access role |
|---|---|---|
| MembershipRegistry | RegisterMember(memberHash, ward, consentRef) | Membership Service |
| MembershipRegistry | VerifyMember(memberID) | Verification Service, NEC reviewer |
| MembershipRegistry | FlagDuplicate(memberID, reason) | Dedup Service, NEC reviewer |
| Nomination | SubmitCandidacy(candidateID, seat, ward) | Candidate Portal |
| Nomination | ApplyWaiver(candidateID, waiverType) | Candidate Portal, NEC reviewer |
| Nomination | RecordMemberDutyProgress(candidateID, verifiedCount) | Membership Service (event-driven) |
| Nomination | CertifyEligibility(candidateID) | NEC reviewer only |
| Escrow | CollectDeposit / ReleaseDeposit / ForfeitDeposit | Fee & Escrow Service (Daraja-triggered) |
| PrimaryVoting | OpenBallot(wardID) / CloseBallot(wardID) | NEC reviewer (two-person) |
| PrimaryVoting | CastEncryptedBallot(ballotToken, encryptedChoice) | Voter session (via Ballot-Secrecy Broker) |
| ResultTally | Tally(wardID) / PublishSignedResult(wardID) | Tally peer process only |
| ResultTally | RecordDisputeEvidence(caseID, evidenceHash) | Dispute Service, any registered candidate |

### 23.2 Glossary

| Term | Definition |
|---|---|
| MSP | Membership Service Provider — Fabric's mechanism for defining an organisation's cryptographic identity |
| HSM | Hardware Security Module — tamper-resistant device for generating/storing cryptographic keys |
| ROKS | Red Hat OpenShift Kubernetes Service on IBM Cloud |
| Private data collection | Fabric feature restricting a subset of ledger data to a defined set of peers — used to keep ballot content away from non-tally peers |
| Ballot-Secrecy Broker | Application-layer component issuing an anonymised ballot token to a verified voter, breaking the link between identity verification and vote content |
| C2PA | Coalition for Content Provenance and Authenticity — cryptographically verifiable media-provenance standard |
| CDP | Customer Data Platform (commercial-plane context) |
| DPIA | Data Protection Impact Assessment |

### 23.3 Source Documents Consolidated

- **FORD-Asili PMaaS — Blockchain Nomination & i3 Engage Technical Implementation Guide, v1.0** (16 September 2026) — Hyperledger Fabric nomination ledger, i3 Engage recruitment integration, digital primaries, requirements traceability R1–R10, IEBC-clock roadmap
- **PMaaS 5.0 — Technical, Business & Commercialisation Review** (September 2026) — independent architecture review, nine-plane target state, data-zoning correction, agentic AI governance, anti-deepfake system, ward intelligence, commercialisation strategy, risk register, decision gates
- Both source documents draw on FORD-Asili OSINT assessments and the FORD_Asili_PMaaS_5.0_Final_Master_Blueprint (11 September 2026), which is treated as strategic input rather than independently re-verified in this consolidation

**External regulatory/standards sources cited in the PMaaS 5.0 Review** (carried forward for reference; re-verify currency before go-live): ORPP Annual Report FY2024/25; Kenya Elections Act 2011; Political Parties (Membership) Regulations 2021; Keycloak documentation; OpenTelemetry documentation; PostGIS; Safaricom Daraja Developer Portal; C2PA Specification 2.4; ODPC Guidance Notes for Electoral Purposes; Data Protection (Registration of Data Controllers and Data Processors) Regulations 2021; NIST AI RMF 1.0; NIST CSF 2.0; OWASP ASVS 5.0.0; Kenya AI Strategy 2025–2030; IEBC election-technology workshop notes (April 2025).

---

*End of Document — FORD-Asili PMaaS 6.0 Master Technical Implementation Guide*
*i3 Technologies Ltd | Kinanie Technologies | Jambocom General Merchants*
*Confidential — Internal i3 / FORD-Asili Technical & Governance Teams*
