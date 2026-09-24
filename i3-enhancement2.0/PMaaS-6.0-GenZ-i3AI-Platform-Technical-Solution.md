# PMaaS 6.0 — "Sauti ya Kizazi" (Voice of a Generation)
## A Gen-Z-First Technical Enhancement of the PMaaS 5.0 Blueprint, Natively Engineered on the i3-ai Platform

**Prepared by:** i3 Technologies — GTM & Product Engineering
**Document type:** Technical Solution Enhancement (builds on the independent *PMaaS 5.0 Technical, Business & Commercialisation Review*, September 2026)
**Status:** Implementation-ready design — for internal review and client presentation
**Scope:** Political & civic engagement OS, re-platformed end-to-end onto i3's own infrastructure, with a dedicated Gen-Z engagement layer and full i3-Engage Cloud (CDP) integration

> **Positioning statement:** Every recommendation in the PMaaS 5.0 review — the Trust Plane, the AI Gateway, the C2PA media vault, the Command Hub, the ward dossier — is not a target architecture we still need to build. It is a description, almost component-for-component, of infrastructure that **already exists and is live on the i3-ai Platform**. This document closes that gap: it maps every reviewed recommendation to its native i3-ai Platform equivalent, and then adds the one dimension the original review did not address — **how a campaign actually wins the attention, trust, and turnout of an 18–29-year-old electorate that does not read manifestos, does not answer landlines, and does not trust institutions by default.**

---

## 1. Executive Summary

Kenya's 2027 electorate skews younger than any in the country's history. Gen-Z (born ~1997–2012) and young Millennials will make up the largest bloc of newly-registered and swing voters. This cohort:

- Consumes politics as **short-form vertical video**, not press releases or PDFs.
- Trusts **peers, creators, and verifiable evidence** far more than official spokespeople.
- Has been the target audience of the **#MaandamanoMovement / Gen-Z protest wave** and is highly literate in spotting inauthentic, top-down messaging.
- Is fluent in **Sheng, Swahili-English code-switching, and meme culture**, and disengages instantly from tone-deaf, overly formal campaign copy.
- Is also the demographic **most exposed to AI-generated deepfakes and disinformation** — making the Verified Media Vault a youth-trust feature, not just a legal shield.

The PMaaS 5.0 review correctly diagnosed the trust, governance, and data-architecture gaps in the original blueprint. This document takes the next step: it **re-platforms the entire solution onto the i3-ai Platform** (already running on IBM ROKS, 100% open-source AI stack) and layers on a **Gen-Z Engagement Layer** built from capabilities i3 already operates for other products — EvalOS gamification, i3-Engage CDP segmentation, the multilingual voice stack, and the multi-agent Co-worker framework.

Nothing in this document requires new vendors, new licences, or unproven technology. It requires **wiring existing i3-ai Platform namespaces together in a new configuration**, plus a genuinely new front-end experience layer designed for a generation that scrolls, not reads.

---

## 2. Platform Alignment — Mapping the PMaaS 5.0 Review Onto What i3 Already Runs

The independent review recommended a target-state architecture in good faith, without visibility into i3's existing stack. The table below shows that the "recommended" components are, almost line for line, already-provisioned i3-ai Platform services.

| PMaaS 5.0 Review Recommendation | i3-ai Platform Native Equivalent | Status |
|---|---|---|
| Multi-tenant, API-first, event-driven platform on Kubernetes | IBM ROKS 4.17 cluster (12 × bx2.4x16), namespace-per-product isolation | ✅ Live |
| AI Model Gateway with policy enforcement, allowlists, cost budgets | **LiteLLM Proxy** (`i3-model-gateway`) — OpenAI-compatible routing, retries, rate limits | ✅ Live |
| LLM observability, prompt/version registry, evaluation hooks | **Langfuse v2** — traces every call: latency, tokens, cost, errors, per-product dashboards | ✅ Live |
| RAG-grounded assistants answering from an approved knowledge base | **ChromaDB** vector store + `nomic-embed-text` embeddings — dedicated `pmaas-manifesto` collection | ✅ Live |
| Agent runtime with observe/reason/propose/execute boundaries | **LangGraph + LangChain** multi-agent orchestration | ✅ Live |
| Human-in-the-loop AI Co-worker with tools sidebar | **Open WebUI**, white-labelled per product — PMaaS instance is **"Dawa"** | ✅ Live |
| Workflow engine for durable, auditable approvals | n8n (event-driven automation) + Kafka event bus for audit trail | ✅ Live |
| C2PA-based media provenance / Verified Media Vault | XTTS-v2 voice-clone registry + object storage (SeaweedFS) + provenance metadata — C2PA manifest layer to be added at the object-store boundary (see §7) | 🟡 Extend |
| Standards-based IAM, MFA, tenant realms | **Keycloak** SSO — dedicated realm `pmaas`, separate from `engage`, `afroerp`, `ailab` | ✅ Live |
| Secrets/KMS, no plaintext credentials | **OpenBao** (HashiCorp Vault fork), 3-node HA | ✅ Live |
| Spatial/GIS data layer (PostGIS) for ward dossiers | PostgreSQL HA (Crunchy PGO), `pmaas_db` — PostGIS extension addable in-cluster | 🟡 Extend |
| Voice cloning with documented authorisation | **XTTS-v2** (Coqui) — 6-second zero-shot cloning, voice_id stored in OpenBao | ✅ Live |
| Multilingual speech-to-text | **faster-whisper large-v3** — English, Swahili, Kikuyu support | ✅ Live |
| GitOps, CI/CD, signed releases | **ArgoCD + Tekton Pipelines** (`i3-gitops`) | ✅ Live |
| Observability / SIEM-lite | Prometheus, Grafana, Alertmanager, Loki (`i3-monitoring`) | ✅ Live |
| Commercial tenant isolation, billing | Per-tenant Keycloak realms, LiteLLM per-tenant token metering → n8n billing webhook | ✅ Live |
| Modular monolith before microservice sprawl | Next.js 14 app per product, shared platform services — exactly the "don't build 20 microservices on day one" guidance the review gave | ✅ Already followed |

**The headline finding:** i3 is not being asked to build a Trust Plane. It already operates one, for five other products (EvalOS, AfroERP, i3-Engage, AI Lab, Onboarding). PMaaS 6.0's job is to **connect to it**, not invent it.

---

## 3. Target Architecture on the i3-ai Platform

```
                         ┌───────────────────────────────────────────────┐
                         │              i3-auth (Keycloak SSO)             │
                         │   Realms: pmaas · engage · afroerp · ailab      │
                         └───────────────────────┬───────────────────────┘
                                                  │
   CHANNELS (Gen-Z first)          EDGE / GATEWAY │        TRUST & SECRETS
   TikTok/IG/YouTube Shorts   ┌─────────────────┐ │   ┌─────────────────────┐
   WhatsApp · SMS · USSD  ──▶ │  API Gateway/WAF │◀┼──▶│  i3-security (OpenBao)│
   Web PWA · Live OTT (AMAs)  └────────┬─────────┘ │   │  voice_id · consent   │
                                       │            │   │  vault · API keys      │
                                       ▼            │   └─────────────────────┘
                          ┌─────────────────────────────────────┐
                          │            i3-pmaas namespace          │
                          │  PMaaS Web (Next.js) · pmaas_db (PG)   │
                          │  Campaign Agent (LangGraph)             │
                          │  Dawa Co-worker (Open WebUI)            │
                          │  Voice Caller / AI Caller Engine        │
                          │  War Room Dashboard (Grafana)           │
                          └───────────────┬─────────────────────────┘
                                          │  Kafka: pmaas.voter-interactions
                                          ▼
        ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
        │   i3-model-gateway     │  │      i3-voice          │  │     i3-engage          │
        │  LiteLLM · Qwen 14B/7B │  │  XTTS-v2 TTS/clone      │  │  Nuru Co-worker         │
        │  LLaVA vision · Granite│  │  faster-whisper STT     │  │  CDP · Segment Builder  │
        └──────────────────────┘  └──────────────────────┘  │  WhatsApp/SMS Gateway    │
                                                              └──────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │           i3-ai-lab namespace           │
                          │  ChromaDB (pmaas-manifesto, youth-kb)  │
                          │  EvalOS Leaderboard — reused for        │
                          │  "Youth Squad" gamification              │
                          └─────────────────────────────────────┘

  Every arrow above is a versioned API contract, logged to Langfuse and Kafka.
  No channel writes directly to pmaas_db — everything passes through the gateway.
```

**Design rule carried over from the review, now enforceable in real infra:** the review's "no external channel writes directly to the system of record" principle is implemented today by the fact that every i3-ai Platform product already sits behind Keycloak + the API gateway + LiteLLM — there is no code path that bypasses it.

---

## 4. The Gen-Z Engagement Layer (New)

This is the component the original 22-page review does not address: **how do you make a 21-year-old care, and then act?** The answer is not "more AI." It is packaging existing i3-ai Platform capability into formats a young voter already trusts.

### 4.1 "Dawa Kijana" — a Gen-Z Persona for the Existing Dawa Co-worker

Dawa (the PMaaS Campaign Strategist co-worker, running on `qwen-heavy` via LiteLLM) already exists. For youth channels it gets a **second system prompt profile**, not a second product:

| Attribute | Default Dawa (candidate/staff facing) | Dawa Kijana (voter/youth facing) |
|---|---|---|
| Tone | Formal campaign-strategist register | Sheng/English code-switch, WhatsApp-native brevity |
| Channel | Command Hub, staff dashboard | WhatsApp, Instagram DM automation, TikTok comment triage |
| Grounding | Full manifesto + internal strategy corpus | Public manifesto + FAQ corpus only (`pmaas-manifesto`, youth-safe subset) |
| Autonomy | Draft + propose (staff approves) | Answer FAQs directly; escalate anything persuasive, financial, or sensitive to a human |
| Model | `qwen-heavy` | `qwen-fast` (low latency for chat-speed replies) |

This uses the same LiteLLM routing and Langfuse tracing already in production — it is a configuration change, not new infrastructure.

### 4.2 Short-Form Content Factory (extends the existing Content Agent)

The platform's **Content Agent** already generates "5 social media post variants (Twitter/X, Facebook, TikTok) in candidate's voice." For Gen-Z this is extended with:

- **Vertical-first output**: script + caption + on-screen text pack sized for TikTok/Reels/Shorts, not repurposed long-form.
- **LLaVA (multimodal)** reviews thumbnail/meme drafts for brand safety and factual grounding before they leave the draft state — this is the same vision model already used for "document OCR, certificate validation" elsewhere on the platform.
- **Human-approval gate** stays mandatory (per the review's non-negotiable: *"Public AI-assisted content cannot bypass human approval"*), enforced as a workflow state in n8n, logged to Kafka.
- **Youth Ambassador Marketplace**: a lightweight extension of the review's "Partner Marketplace" idea — verified student/creator ambassadors get a branded content kit generated by the Content Agent, a personal referral code, and are tracked (aggregate only — no individual persuasion profiling) via the i3-Engage CDP.

### 4.3 Gamified Civic Literacy — Reusing EvalOS, Not Rebuilding It

i3 already operates a full assessment/gamification engine for EvalOS: exam engine, leaderboard, Open Badges 3.0 (W3C verifiable credentials), cohort provisioning. Repurposed for youth civic engagement:

- **"Youth Squad" leaderboard** (EvalOS Leaderboard, relabelled): ward-level youth volunteer teams compete on verified, non-partisan activity — voter registration assists, civic-quiz completions, verified event attendance — never on persuasion metrics.
- **Civic literacy quiz bot** on WhatsApp: "How does nomination work?", "What is the IEBC's role?", built on the same question-bank/quiz architecture as EvalOS, answered via RAG over public civic-education content (never manifesto persuasion content).
- **Open Badges for civic participation**: a verifiable, LinkedIn-linkable credential for completing voter-education modules or verified volunteer hours — no monetary or preferential value attached, purely recognition, which keeps it outside campaign-finance and inducement concerns.

### 4.4 Live "Ask Me Anything" via the Existing OTT Stack

i3 already runs **OvenMediaEngine + SeaweedFS + nginx-HLS** for live streaming (`i3-ott`). Gen-Z political engagement research consistently shows unscripted, live, Q&A-format content outperforms produced ads for this demographic. This is a **relabel, not a rebuild**:

- Candidate/surrogate AMAs streamed via the existing OTT pipeline.
- Whisper STT live-transcribes for real-time captioning (accessibility + shareability).
- Clips auto-cut and routed into the Content Factory (§4.2) for same-day short-form distribution.

### 4.5 Verified Media Vault as a *Youth Trust Feature*, Not Just Legal Cover

The review frames C2PA provenance primarily as a legal/forensic safeguard. For a generation raised on deepfakes and AI slop, **visible provenance is also a brand differentiator**:

- Every official video/audio asset gets a **scannable "Verified" QR** (the review's own "Provenance QR" innovation) linking to the C2PA manifest, timestamp, and original source.
- This is marketed to youth audiences explicitly: *"If it doesn't have the QR, don't trust it, and tell us so we can respond."* This turns the review's defensive innovation into an active engagement mechanic — a Gen-Z audience that already fact-checks becomes a distributed detection network.

---

## 5. i3-Engage Cloud Integration — The CDP Backbone for Youth Mobilisation

The PMaaS 5.0 review's ward dossier and voter-outreach concepts are, functionally, a Customer Data Platform problem. i3 already operates one — **i3-Engage Cloud** — for banks, SACCOs, and insurers. PMaaS 6.0 uses it directly rather than building a parallel CDP.

| i3-Engage Capability (already live) | PMaaS 6.0 Youth Use |
|---|---|
| Unified profile merged across touchpoints (`engage_db` + Kafka streams) | Aggregate, ward-level youth engagement profile — **never individual political-opinion scoring** (hard boundary, see §7) |
| **Segment Builder Agent** — natural language → SQL segment → preview count → one-click launch | "Registered voters aged 18–24 in Nairobi wards, reached via WhatsApp, not yet responded" — aggregate cohorts only |
| **Content Generator** — campaign goal + segment → SMS/WhatsApp/email, brand-compliant | Youth-tone variants of approved messaging, still passing through the same human-approval gate |
| **Send-Time Optimiser** | Times civic-reminder and event-notification sends to when 18–24s are actually online (evening/weekend peaks) |
| **Churn Predictor** (re-purposed as *lapsed-volunteer/engagement predictor*) | Flags youth volunteers/subscribers who have gone quiet, for a **non-partisan** re-engagement nudge (event invite, civic-literacy content) — not a persuasion escalation |
| WhatsApp Business Cloud API + SMS gateway (Africa's Talking / SMPP) | Primary two-way channel for youth — cheaper, higher-reach than voice calls for this cohort |
| M-Pesa Daraja + Paystack in-message payment links | Youth-friendly small-ticket donation flows ("Tuma KES 50") and volunteer stipend/reimbursement rails |
| Nuru Co-worker | Campaign-ops staff ask Nuru in natural language: *"Draft a WhatsApp sequence for first-time voters in Kibra who haven't registered yet."* |

**Why this matters commercially:** i3-Engage already has a live usage-based pricing model (platform fee + per-message + AI-token overage). Bolting PMaaS's youth mobilisation onto it means the campaign licence fee funds *incremental usage on existing infrastructure*, not a second CDP build.

---

## 6. Voice & Multimodal Stack for Youth Channels

| Modality | Technology (already live) | Gen-Z Application |
|---|---|---|
| Voice Input (STT) | faster-whisper large-v3 | Voice-note replies in WhatsApp — Gen-Z in Kenya sends voice notes more than typed messages |
| Voice Output / Clone | XTTS-v2 | Candidate's cloned voice for **opt-in** WhatsApp voice-note replies to FAQs — always disclosed as AI-generated, never used for unsolicited persuasion calls to this cohort without consent |
| Vision | LLaVA:13B | Meme/creative-review, screenshot fact-check ("is this real?") submissions from youth via WhatsApp |
| Live | OvenMediaEngine + Whisper captions | AMAs, debate-watch-parties, real-time reaction threads |

---

## 7. Trust, Safety & Age-Eligibility — Non-Negotiable Guardrails

Targeting "Gen-Z" is not the same as targeting minors. The Kenyan Elections Act sets voter eligibility at 18. This distinction must be a **hard technical boundary**, not a policy note:

1. **Age gating enforced at the identity layer.** Keycloak-authenticated flows and WhatsApp opt-in flows must capture and verify eligibility status before any persuasive or mobilisation content is served. Under-18 users are automatically routed to a **strictly non-partisan civic-education track** (how elections work, how to register when eligible) — never manifesto content, never mobilisation asks, never AI voice-clone messaging.
2. **No individual political-opinion profiling of anyone, of any age** — carried over unchanged from the PMaaS 5.0 review's red line, enforced by the same "Commercial Data Diode" / aggregate-only architecture already specified for the ward dossier and now extended to the i3-Engage youth segments.
3. **Consent ledger** (OpenBao-backed) records purpose, channel, language, and withdrawal event for every youth-channel opt-in — same architecture the review specified, already available as an i3-ai Platform pattern.
4. **Disclosure by default**: any AI-generated voice, video, or text delivered to a youth channel is labelled as such at first contact, reinforced by the Verified Media Vault QR (§4.5).
5. **Human-in-the-loop remains mandatory** for anything persuasive, financial, or emotionally charged, regardless of how "casual" the channel (WhatsApp/TikTok) feels — the informality of the format is not a reason to relax the approval gate.

---

## 8. Roadmap — Threaded Into the Existing i3-ai Platform Phased Build

The i3-ai Platform master implementation plan already has a live 5-phase, 10-week rollout in progress. PMaaS 6.0's Gen-Z layer is added as an overlay, not a parallel timeline.

| Platform Phase (existing) | Gen-Z / Engage Overlay (new) |
|---|---|
| **Phase 1** — AI Gateway + Co-worker foundation (Wk 1–2) | Stand up Dawa Kijana system-prompt profile on the same LiteLLM/Open WebUI deployment |
| **Phase 3** — Voice stack + PMaaS foundation (Wk 3–5) | Wire voice-note reply flow into WhatsApp; deploy Verified-Media QR pipeline on top of the voice-clone registry |
| **Phase 4** — AfroERP + i3-Engage + AI Lab build (Wk 5–8) | Stand up youth segments in i3-Engage CDP; relabel EvalOS Leaderboard as "Youth Squad"; issue first Open Badges civic-literacy credentials |
| **Phase 5** — Dashboards + commercialisation (Wk 8–10) | Grafana youth-engagement dashboard (segment growth, quiz completions, AMA reach) alongside the existing PMaaS War Room dashboard |
| **New — Phase 6** (Wk 10–12) | Youth Ambassador Marketplace pilot in 3 wards; OTT AMA cadence begins; independent legal review of age-gating flow before any paid promotion targets under-25 audiences |

---

## 9. Commercial Model Extension

Layered onto i3's existing per-product pricing (not a new pricing system):

| Line item | Base (existing i3 pricing) | Gen-Z / Engage Add-on |
|---|---|---|
| PMaaS Campaign Licence | Ward Councillor KES 150K · MCA/MP KES 500K · Governor KES 2M | **Youth Mobilisation Pack**: +KES 40K–150K depending on ward count — includes Dawa Kijana config, Content Factory vertical-video templates, Youth Squad leaderboard instance |
| AI Caller minutes | Billed separately | Voice-note reply volume billed under the same meter |
| i3-Engage usage fees | KES 5K/mo platform + SMS/WhatsApp usage + AI token overage | Youth segment CDP usage rolls into the same usage-based meter — no separate CDP contract needed |
| AI Lab / EvalOS reuse | N/A (internal reuse) | Licensed at marginal cost — Leaderboard/Badges infrastructure is already amortised across EvalOS customers |

---

## 10. KPIs Specific to Youth Engagement

| Domain | Metric | Target Philosophy |
|---|---|---|
| Reach | 18–29 segment size in i3-Engage CDP, verified-eligible | Growth, not vanity follower counts |
| Content | Content Factory output → approved → published turnaround | Same-day for reactive content, per the review's approval-gate principle |
| Trust | % of official assets carrying a Verified QR scan | 100% of official media, tracked as an authenticity signal |
| Civic literacy | Quiz completions, Open Badges issued | Track engagement depth, not just impressions |
| Safety | Under-18 users correctly routed to non-partisan track | 100% — zero tolerance, audited weekly |
| Commercial | Incremental i3-Engage usage revenue attributable to youth segments | Track as a distinct cost-to-serve line for pricing refinement |

---

## 11. Risks & Mitigations (Gen-Z Specific, in Addition to the PMaaS 5.0 Review's Existing Risk Register)

| Risk | Mitigation |
|---|---|
| Age-gating bypass (under-18 reaching persuasive content) | Hard technical gate at Keycloak/WhatsApp opt-in layer, not a policy instruction to staff; quarterly audit |
| Perceived inauthenticity ("this is obviously AI-written for us") | Human review of tone before publish; real ambassador-generated content mixed with AI drafts, never AI-only |
| Over-reliance on voice cloning eroding trust if undisclosed | Mandatory disclosure + Verified QR on every AI-voice touchpoint |
| Gamification read as vote-buying/inducement | Badges are non-monetary and non-preferential by design; legal review before any physical-prize tie-in |
| Youth channels (WhatsApp/TikTok) treated as "lower stakes" and under-governed | Same approval-gate and audit-receipt architecture applies regardless of channel informality |
| CDP segment creep into individual profiling | Enforced at the Commercial Data Diode / aggregate-only query layer — technically, not just contractually |

---

## 12. Bottom Line

The PMaaS 5.0 review asked the right question — *"build the trust architecture first."* The honest answer, once you look at what i3 actually operates, is that **the trust architecture is already running** — for EvalOS, AfroERP, and i3-Engage today. PMaaS 6.0's job is narrower and more achievable than the original review assumed: **connect an existing, governed, multi-tenant AI platform to the channels and formats a young Kenyan electorate actually uses**, without ever loosening the age-eligibility, consent, and human-approval guardrails that make the platform trustworthy in the first place.
