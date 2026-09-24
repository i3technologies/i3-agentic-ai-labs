# i3 EduBridge™
## Academic-to-Industry Practical Learning Platform
### Product Review & Detailed Technical Implementation Blueprint for Universities & Colleges

**Prepared by:** Philip Mukiti — CEO & Solutions Architect, i3 Technologies Limited
**Prepared for:** Internal Product Strategy — Higher Education Vertical
**Date:** September 2026
**Status:** Draft for engineering, academic partnerships, and commercial review

---

## 0. What This Document Is

i3 already has three proven, separately-run assets aimed at universities:

1. **i3 Academy Learning Hub** — Skillsoft/Percipio, 2,000+ courses, 16 domains, IBM/Red Hat certification tracks (used in the USIU-Africa proposal).
2. **i3 Smart Labs** — 750 live VMs on IBM Power Systems / IBM Cloud VPC (Kenya Region) + Red Hat OpenShift, 1,000+ hands-on lab scenarios, 2-minute provisioning, 99.9% SLA.
3. **i3 AI Lab** — a GPU-backed, LiteLLM/Ollama-based AI platform (JupyterHub + Sage/Open WebUI) currently being hardened for multi-tenancy, metering, Nairobi-region residency, and governance (per the P0 Technical Build Spec).

These are currently **sold as adjacent offerings** bundled into bespoke academic proposals (e.g., USIU-Africa). This document reviews the opportunity to productize them into a single, coherent, licensable **EdTech platform** — `i3 EduBridge` — that any university or college in Africa can adopt, with:

- A proper **LMS core** (not just "Percipio + labs bolted onto whatever LMS the university already has").
- An **authoring layer** (i3's own tooling, or hardened open-source, so faculty and i3's curriculum team can build practical content, not just consume Skillsoft's).
- The existing **practical labs fabric** (Smart Labs) exposed as an embeddable, gradable service rather than a separate portal.
- The existing **AI Lab** repositioned as the platform's AI tutor, assessment copilot, and content-authoring accelerant.
- A new **OTT / virtual delivery layer** for lecture capture, live classes, and a Netflix-style on-demand course video library — something none of the current three assets provide today.

This is a **build-on-what-exists** strategy: nothing here proposes replacing i3 Smart Labs or the AI Lab. It proposes wrapping them in an LMS + authoring + video layer so the whole thing can be sold, provisioned, and billed as **one product** to a Vice-Chancellor or Dean, rather than as three vendor relationships.

---

## 1. The Problem (Confirmed by the USIU-Africa Engagement)

The USIU-Africa proposal already documents the core gap i3 is solving:

| What CS/tech students learn in lecture | What employers need on day 1 |
|---|---|
| Data structures & algorithms, programming theory | IBM Cloud / Red Hat OpenShift deployment |
| Database design concepts | Agentic AI: IBM watsonx, LangChain, RAG |
| Software engineering principles | CI/CD: Jenkins, GitLab, Terraform |
| Networking fundamentals, OS theory | Enterprise cybersecurity operations (SOC) |
| AI/ML mathematical foundations | Kubernetes/Docker orchestration, MLOps |

What's missing from the *current* pitch is the **delivery mechanism** universities actually run their academic year on: a gradebook, an LMS faculty already know, a way to record and stream lectures, and a way to author and version practical content — not just consume a third-party catalogue. That's the product gap `i3 EduBridge` fills.

---

## 2. Product Architecture — Six Layers

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          i3 EduBridge Platform                            │
│                                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │ 1. LMS CORE │  │ 2. AUTHORING │  │ 3. PRACTICAL   │  │ 4. AI LAYER   │  │
│  │  (Moodle+)  │◄─┤   STUDIO     │─►│   LABS FABRIC  │◄─┤ (i3 AI Lab)   │  │
│  │             │  │  (i3 Author) │  │ (i3 Smart Labs)│  │               │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  └───────┬───────┘  │
│         │                │                  │                    │        │
│  ┌──────▼────────────────▼──────────────────▼────────────────────▼─────┐  │
│  │            5. OTT / VIRTUAL DELIVERY (live + on-demand video)        │  │
│  └──────────────────────────────┬─────────────────────────────────────┘  │
│                                  │                                         │
│  ┌───────────────────────────────▼──────────────────────────────────────┐ │
│  │        6. CREDENTIALING, ANALYTICS & TALENT-PLATFORM LAYER            │ │
│  │   (IBM Digital Badges, xAPI/LRS, employer network, placement API)    │ │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  Cross-cutting: SSO (Keycloak) · Multi-tenancy (per-institution namespace)│
│  · Kenya DPA 2019 residency (Nairobi region) · Audit logging (WORM)      │
└───────────────────────────────────────────────────────────────────────────┘
```

Each layer below is scoped as **build vs. buy vs. extend**, since that decision drives cost, time-to-market, and defensibility.

---

## 3. Layer 1 — LMS Core

### 3.1 Decision: Extend open-source, don't build from scratch

Building a new LMS is a multi-year distraction from i3's actual differentiators (labs, AI, IBM/Red Hat content, sovereignty). The LMS should be a **hardened, white-labeled open-source core** that i3 owns the deployment, integration, and hosting of — not a from-scratch product.

| LMS | License | Strength for this use case | Weakness |
|---|---|---|---|
| **Moodle** (recommended core) | GPLv3 | Largest plugin ecosystem, native LTI 1.3/Advantage, mature gradebook, competency frameworks, huge Africa/education install base (familiar to faculty), strong REST/web-service API for headless use | UI feels dated without theming investment |
| Open edX | AGPLv3 | Excellent for MOOC-style self-paced content, strong video-first pedagogy (Studio + micro-frontends) | Heavier ops footprint (many microservices), less familiar to African university IT teams |
| Canvas LMS (open-source core) | AGPLv3 | Clean UX, strong mobile apps | Commercial cloud version dominates mindshare; self-hosting is less common, smaller ecosystem of Africa-specific integrators |
| Sakai / Chamilo | Various OSS | Lower TCO for small colleges | Smaller plugin ecosystems, weaker LTI Advantage support |

**Recommendation:** **Moodle**, self-hosted on i3 Smart Labs' existing OpenShift/IBM Cloud VPC infrastructure, multi-tenant via one Moodle instance per institution namespace (mirrors the multi-tenancy model already specified for the AI Lab in workstream B4 — same `cust-<slug>` namespace pattern, same Keycloak SSO groups).

### 3.2 What i3 builds on top of Moodle (the actual IP)

- **i3 Theme & Brand Shell** — white-label per institution (university branding, i3 co-brand watermark), consistent with the "co-brand with IBM" positioning already used with USIU.
- **i3 Connector Plugin (Moodle plugin, PHP)** — a single plugin package providing:
  - LTI 1.3 Deep Linking into i3 Smart Labs (launch a lab directly from a Moodle activity, return a grade via LTI AGS).
  - LTI Deep Linking into i3 Academy/Percipio courses (so Skillsoft content shows up as native Moodle activities, not an external portal link).
  - A "Launch AI Tutor" block that opens a scoped Sage/AI Lab chat session pre-loaded with the course's RAG corpus (see Layer 4).
  - An OTT video block (Layer 5) for embedding lecture recordings and live-class links directly in the course page.
- **Competency & Certification Mapping** — Moodle's native Competency Frameworks API mapped to IBM/Red Hat/Anthropic certification tracks (reusing the certification taxonomy i3 already maintains for the Graduate Trainee Bootcamp — IBM watsonx Orchestrate AI Engineer Associate, Anthropic Claude Certified Architect, RHCSA, etc.).

### 3.3 Identity & multi-tenancy

- **Keycloak** as the single SSO/IdP across Moodle, Smart Labs, Sage, and Percipio SSO handoff — one login per student for the entire stack.
- One Keycloak **realm per institution** (or per-institution group set within a shared realm for smaller colleges), mirroring the `i3-users` / `cust-<slug>` group model already defined for AI Lab tenancy.
- Role mapping: `student`, `faculty`, `ta`, `institution-admin`, `i3-admin` — propagated to Moodle roles, Smart Labs RBAC tiers, and AI Lab project scopes from the same group claim.

---

## 4. Layer 2 — Authoring Studio ("i3 Author")

This is the layer that currently **does not exist** in the USIU proposal — faculty and i3's curriculum team have no dedicated tool for building practical, lab-linked, AI-assisted courseware. It's the highest-leverage build.

### 4.1 Build approach: open-source authoring core + i3's AI generation layer on top

| Component | Choice | Why |
|---|---|---|
| Interactive content authoring | **H5P** (open-source, GPLv2), self-hosted via the H5P Moodle plugin or standalone H5P Hub | Industry-standard interactive content (branching scenarios, drag-drop, interactive video, quizzes) with xAPI output out of the box |
| Long-form/branching scenario authoring | **Adapt Learning Framework** (open-source) for responsive, story-driven modules — used for the CAISY-style simulation scenarios (cybersecurity incident response, client presentations) referenced in the USIU proposal | Free alternative to commercial tools (Articulate/Captivate) with full source control, versionable in Git |
| Lab scenario authoring | **i3 Lab Scenario Builder** (new, thin custom layer) — a YAML/Git-based spec (VM image + starter files + grading script + hints) that compiles to a Smart Labs lab definition | Keeps lab content versioned in Git alongside the courseware, not locked in a proprietary lab vendor format |
| AI-assisted authoring ("i3 Author Copilot") | **Custom, built on the i3 AI Lab's LiteLLM gateway + RAG Studio** | Faculty upload a syllabus, textbook chapter, or slide deck; the copilot (using `qwen-heavy`/`coder` aliases from the existing model roster) drafts quiz items, a branching scenario outline, and a matching lab scenario skeleton — cutting authoring time dramatically |

### 4.2 i3 Author Copilot — technical flow

```
Faculty uploads source material (PDF/PPTX/DOCX)
        │
        ▼
Document AI / RAG ingestion (Apache Tika + LangChain/LlamaIndex chunking
      → ChromaDB, per-course collection)          [reuses AI Lab RAG Studio]
        │
        ▼
LiteLLM call to `coder` / `qwen-heavy` alias with a structured-output prompt
        │
        ├──► Draft quiz bank (H5P-compatible JSON/xAPI)
        ├──► Draft branching scenario outline (Adapt-compatible JSON)
        └──► Draft lab scenario spec (YAML: base image, tasks, grading script)
        │
        ▼
Faculty reviews/edits in i3 Author UI → publishes → Moodle course + Smart Labs
       lab definition + H5P package are versioned together in one course package
```

This is the single most defensible piece of IP in the whole platform: everything else (Moodle, H5P, Smart Labs, LiteLLM) is either open-source or already built by i3 — the Copilot orchestration layer that ties authoring, RAG, and lab generation together is new and proprietary.

### 4.3 Content packaging & interoperability

- Export/import via **SCORM 1.2/2004** and **xAPI (Tin Can)** so content is portable and not locked to i3 infrastructure — a genuine trust signal for university procurement committees who fear vendor lock-in.
- **Common Cartridge / LTI Resource** packaging so a course built in i3 Author can also run inside a university's existing Canvas/Blackboard if they don't fully migrate to the Moodle core (a pragmatic hybrid-adoption path).

---

## 5. Layer 3 — Practical Labs Fabric (i3 Smart Labs, exposed as a service)

No new infrastructure is proposed here — this layer **already exists and works** (750 VMs, IBM Power Systems, Red Hat OpenShift, 1,000+ lab scenarios, 2-minute provisioning, 99.9% SLA, GPU pods for AI/ML). The product work is making it **embeddable and gradable from inside a course**, rather than a separate portal students have to context-switch into.

### 5.1 What needs to be built (thin integration layer, not new infra)

- **Lab-as-a-Service API** — a REST/GraphQL wrapper over the existing Smart Labs provisioning system exposing: `launch_lab(scenario_id, user_id, course_context)`, `get_session_status()`, `get_grading_result()`.
- **LTI 1.3 Deep Linking + Assignment & Grade Services (AGS)** — so a Moodle activity can launch a specific lab scenario and receive a numeric grade back automatically (session completion, task checklist, or auto-graded script output).
- **Session recording metadata → xAPI statements** — every lab session emits `(actor, verb, object, result)` xAPI statements ("Jane attempted lab cybersecurity-soc-101, completed 4/5 tasks, duration 42 min") into the platform's Learning Record Store (Layer 6), not just a raw session log.

### 5.2 Curriculum mapping (already defined, reused as-is)

The existing 4-year Year 1–4 lab mapping from the USIU proposal becomes the **default lab catalogue template** shipped with `i3 EduBridge` for any Computer Science / IT programme, customizable per institution:

| Year | Smart Labs focus | New: auto-linked Moodle activity type |
|---|---|---|
| 1 | Linux Admin, AWS Cloud Basics, Python/Jupyter | "Practical Lab" activity, auto-graded checklist |
| 2 | Full-Stack Dev, PostgreSQL/MongoDB, Docker | "Practical Lab" + peer-reviewed code submission |
| 3 | AI/ML GPU labs, Cybersecurity SOC, OpenShift | "Practical Lab" + AI-graded rubric (via AI Layer) |
| 4 / Capstone | IBM Power Systems, watsonx Studio, multi-agent LangChain | "Capstone Project" workflow with enterprise-brief intake form |

---

## 6. Layer 4 — AI Layer (repositioning the i3 AI Lab as a teaching product)

The i3 AI Lab's P0 build (GPU inference tier, metering/billing, Nairobi residency, multi-tenancy/RBAC, model governance pack) is being engineered as **general-purpose enterprise AI infrastructure**. For `i3 EduBridge`, that same infrastructure is the AI Tutor and Faculty Copilot engine — the same LiteLLM gateway, the same model roster, the same governance pack, reused, not duplicated.

| AI Lab capability (already speced) | EduBridge product feature |
|---|---|
| LiteLLM gateway + `qwen-fast`/`qwen-heavy`/`coder`/`vision`/`embed` aliases | Backend for AI Tutor chat, code-review copilot, and the i3 Author Copilot |
| GPU inference tier (ollama-gpu, KEDA autoscaling) | Low-latency AI Tutor responses during peak lecture/lab hours |
| RAG Studio / ChromaDB per-tenant collections | Course-scoped AI Tutor — answers grounded in *that course's* syllabus, slides, and textbook, not generic internet knowledge |
| Swahili/Sheng evaluation suite (B5) | AI Tutor and voice features natively support Kenyan Swahili and code-switching — a genuine differentiator vs. Coursera/edX/ChatGPT-in-education tools |
| PII pre-filter / NeMo-style guardrails | Protects student data (names, ID numbers, contact info) from leaking into model logs or being echoed back inappropriately |
| Metering & per-key budgets (B2) | Per-institution and per-student AI usage quotas — prevents runaway costs, enables tiered pricing (see §10) |
| Multi-tenancy/RBAC + audit logging (B4) | Each institution's AI Tutor conversations, RAG corpora, and usage logs are isolated and auditable — required for a bank-grade or ministry-grade procurement review, equally relevant to a university data-protection office |
| Model governance pack / model cards (B5) | Published "AI Tutor model card" per course subject area — capability, known limitations, intended use — for academic integrity and accreditation-body scrutiny |

### 6.1 New feature: AI Teaching Assistant for faculty

- Auto-drafts rubric-based feedback on code/lab submissions (using the `coder` alias against the student's lab session output).
- Flags at-risk students from engagement/xAPI signal patterns (late lab starts, repeated failed grading attempts) — surfaced to faculty dashboards, **not** used for any automated academic-standing decision (kept as an advisory signal only, consistent with responsible-AI governance).
- Generates weekly cohort progress summaries for department heads, replacing manual Percipio dashboard exports.

### 6.2 New feature: Agentic AI curriculum sandbox

Reuses the Agent Builder capability (LangGraph/CrewAI) described in the platform commercialization strategy, exposed to students as a **teaching tool, not just an enterprise feature**: Year 3/4 students build and run their own multi-agent workflows inside an isolated Smart Labs GPU sandbox as coursework — directly matching Pillar 3 of the USIU proposal (Foundations of Agentic AI → Capstone).

---

## 7. Layer 5 — OTT / Virtual & On-Demand Delivery (new build)

This is the second genuinely new layer. Universities need lecture capture, live virtual classes, and an on-demand video library — none of which the current three assets provide.

### 7.1 Requirements specific to the East Africa context

- **Low-bandwidth resilience** — adaptive bitrate down to 240p, aggressive segment caching, and an explicit "data-saver" mode, since many students access content on mobile data.
- **Data sovereignty** — video storage and streaming origin inside the Nairobi region (same residency posture as the AI Lab's B3 workstream), not a US/EU CDN by default.
- **Offline-friendly** — downloadable lecture packages for intermittent-connectivity students (common outside Nairobi's core).
- **Live + on-demand in one system** — synchronous classes and asynchronous catch-up video need to live in the same catalogue, not two separate tools.

### 7.2 Recommended stack (open-source first, avoids per-seat licensing at scale)

| Function | Recommended component | Notes |
|---|---|---|
| Live virtual classroom (synchronous) | **BigBlueButton** (open-source, LGPL) | Native Moodle LTI integration (`mod_bigbluebluttonbn`), recording auto-published to the OTT library below, breakout rooms for lab-support sessions |
| Live low-latency streaming (large lectures, guest speakers, roadshow-style events) | **OvenMediaEngine** (open-source, low-latency WebRTC/LLHLS) | Sub-second-to-few-second latency for large-audience broadcast use cases beyond BBB's group-call model |
| VOD library / course video repository ("Netflix for courses") | **PeerTube** (open-source, ActivePub federation optional — disable federation for a private institutional deployment) | Self-hosted, adaptive HLS transcoding, playlists = course modules, i3-branded front end |
| Transcoding pipeline | **FFmpeg**-based worker pool on the existing OpenShift cluster, GPU-accelerated encode where GPU capacity allows (shares infra with the AI Lab's GPU nodes during off-peak hours) | Multi-bitrate HLS ladder: 240p/360p/480p/720p/1080p |
| DRM (optional, for premium/licensed third-party content only) | **Widevine/FairPlay via Shaka Packager**, applied selectively — not on i3/faculty-authored open content | Needed only if licensing commercial publisher video content through the platform later |
| Captioning / accessibility | **Whisper-based auto-captioning** using the existing Faster-Whisper STT component already speced for the Kenyan Swahili Voice AI workstream | Auto-captions in English and Swahili; accessibility compliance (a common accreditation requirement) |
| CDN / edge delivery | Regional edge cache in front of the Nairobi origin (evaluate a local/regional CDN partner or self-managed edge nodes on partner ISPs) | Avoids routing East African student traffic through Europe/US, improving both latency and DPA-aligned data-flow posture |

### 7.3 Integration into the LMS

- Every BigBlueButton/PeerTube asset is a native Moodle activity (via LTI or the respective plugins), appears in the gradebook (attendance/watch-completion tracked via xAPI), and is discoverable through the same course page as labs and AI Tutor blocks — **one course page, not three portals.**

---

## 8. Layer 6 — Credentialing, Analytics & Talent Platform

- **Learning Record Store (LRS):** **Learning Locker** (open-source, xAPI-native) ingests every activity — Moodle completions, H5P interactions, lab session results, OTT watch-time, AI Tutor engagement — into one queryable event store. This is what makes the "IBM Digital Badge" and "student progress dashboard" promises in the USIU proposal *actually real-time* rather than manually compiled.
- **Digital badges:** IBM/Red Hat/Anthropic micro-credentials issued via **Open Badges 3.0** (verifiable, LinkedIn-postable), triggered automatically from LRS completion events — no manual badge-issuing workflow.
- **Talent platform API:** exposes an anonymized/opt-in competency + badge + capstone-outcome profile per graduating student to i3's employer network (the "University-as-a-Talent-Platform" innovation from the USIU proposal), turned from a slide-deck promise into an actual API contract with i3's placement team.

---

## 9. Cross-Cutting Technical Concerns

| Concern | Approach |
|---|---|
| **Data residency (Kenya DPA 2019)** | All student PII, video content, RAG corpora, and audit logs hosted in the Nairobi region per the AI Lab's B3 workstream; Frankfurt (or another DR region) holds only encrypted, non-resident configuration backups |
| **Multi-tenancy** | One OpenShift namespace per institution (`cust-<university-slug>`), consistent naming/RBAC pattern shared with the AI Lab's B4 workstream — the same platform team operates both |
| **Identity** | Single Keycloak deployment federating institution SSO (many universities already run Shibboleth/SAML or Google Workspace/Microsoft 365 — Keycloak brokers these into one OIDC identity for Moodle/Smart Labs/AI Lab/OTT) |
| **Audit logging** | Append-only, WORM-policy object storage for API, platform, and content-access audit trails (reusing the B4 audit design), essential for both DPA compliance and academic-integrity investigations |
| **Observability** | Prometheus + Grafana across Moodle app servers, BigBlueButton/PeerTube media servers, LiteLLM gateway, and Smart Labs provisioning — one SLI dashboard set for the whole product, not three separate ones |
| **GitOps** | All infrastructure-as-code (Moodle Helm charts, BBB/PeerTube manifests, LiteLLM config, course-content packages) in one repo with per-institution overlays, mirroring the AI Lab's existing GitOps discipline |

---

## 10. Commercialization Model (extends the USIU pricing logic to a repeatable SaaS product)

The USIU-Africa proposal's pricing (free pilot semester → USD 150/student/year) is a strong anchor. `i3 EduBridge` generalizes it into tiers so it's sellable beyond one bespoke deal:

| Tier | Includes | Indicative price |
|---|---|---|
| **Foundation** | Moodle core + i3 theme, Percipio catalogue access, standard Smart Labs catalogue (no GPU labs), no AI Tutor | USD 60–80 / student / year |
| **Practical+** (matches the USIU pilot scope) | Foundation + full Smart Labs (incl. GPU AI/ML labs) + AI Tutor (metered) + OTT live/VOD delivery | USD 150 / student / year |
| **Institution-Wide / Multi-Faculty** | Practical+ across multiple departments, i3 Author licensed for faculty content creation, dedicated account manager, custom lab-scenario development | Custom / volume pricing |
| **Regional Alliance** | The "East Africa University Technology Alliance" model — shared infrastructure, cross-institution content exchange, joint IBM/Red Hat branding | Consortium pricing, negotiated per member |

**Free pilot pattern retained** (one semester, full-feature, no cost) as the standard sales motion for every new institution — proven to work with USIU-Africa and low-risk enough for a Dean to approve without a procurement cycle.

---

## 11. Competitive Landscape (why this is defensible)

| Competitor / adjacent product | What they offer | Where i3 EduBridge wins |
|---|---|---|
| **Coursera for Campus / edX for Business** | Course catalogue + certificates | No local labs, no data-sovereign hosting, no Swahili-native AI, USD pricing that's expensive at African-university budget scale |
| **Instructure Canvas + a labs vendor (e.g., Skillable/CloudLabs)** | Good LMS + generic cloud sandboxes | Two separate vendor relationships and bills; sandboxes are generic, not IBM Power Systems/OpenShift-specific; no AI Lab or OTT layer bundled |
| **Google Cloud Skills Boost / AWS Educate** | Free/cheap cloud labs | Locks curriculum into one hyperscaler's ecosystem; no local data residency; no LMS/gradebook integration; no faculty authoring tools |
| **Generic AI chatbot tools (ChatGPT Edu, etc.)** | General AI tutoring | Not grounded in the specific course's RAG corpus, no lab integration, weaker Swahili/code-switching support, no institutional data governance/audit trail |

i3's actual moat is the **combination**: IBM/Red Hat enterprise infrastructure + Kenya-resident sovereign AI + Swahili-native voice/NLP + a real VM lab fabric + a bundled LMS/authoring/OTT layer, sold as one relationship at a price point tuned for African university budgets.

---

## 12. Phased Delivery Plan

| Phase | Timeline | Deliverable |
|---|---|---|
| **P0 — Foundation** | Months 1–3 | Moodle core deployed multi-tenant; SSO via Keycloak; LTI links to existing Smart Labs and Percipio (no new authoring or OTT yet) — this alone is enough to run the USIU pilot on a proper LMS instead of ad-hoc portal links |
| **P1 — AI + Authoring** | Months 4–7 | i3 Author (H5P/Adapt + AI Copilot) launched; AI Tutor (RAG-grounded, per-course) launched; Lab-as-a-Service API with LTI AGS auto-grading live |
| **P2 — OTT & Talent Platform** | Months 8–12 | BigBlueButton + PeerTube live/VOD stack deployed; Learning Locker LRS live; Open Badges 3.0 issuance automated; talent-platform API opened to i3's employer network |
| **P3 — Regional Alliance** | Year 2 | Second and third university onboarded on the same shared, multi-tenant infrastructure; East Africa University Technology Alliance formalized |

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Faculty resistance to a new LMS if the university already runs Canvas/Blackboard | Ship SCORM/xAPI/Common Cartridge export so i3-authored content runs inside their existing LMS during a transition period; don't force a hard Moodle migration on day one |
| OTT self-hosting operational burden (media servers are ops-heavy) | Start with BigBlueButton only (P0/P1) — it's the lowest-ops-burden component and already LTI-native for Moodle; defer PeerTube VOD library to P2 once the platform team has bandwidth |
| AI Tutor cost/latency at scale during exam-period usage spikes | Reuses the AI Lab's existing KEDA autoscaling and per-key budget guardrails (B1/B2) — the metering discipline already being built for enterprise clients directly protects the education product's margins |
| Data-protection office pushback on AI processing of student data | Reuses the AI Lab's PII pre-filter and audit-logging design (B4/B5) — the same governance pack built for bank-grade enterprise clients is the right answer for a university's Data Protection Officer |
| Vendor lock-in perception during procurement | Every layer (Moodle, H5P, BigBlueButton, PeerTube, Learning Locker, Open Badges) is open-source and exportable — the pitch to a procurement committee is "own your data, own your content, i3 hosts and integrates it for you" |

---

## 14. Recommendation

Build `i3 EduBridge` as the **wrapper product** around the three existing assets, in the phased order above, using the USIU-Africa engagement as the **live P0 pilot** rather than starting a separate proof-of-concept from zero. Concretely, for USIU specifically:

1. Stand up a single-institution Moodle instance now (P0), LTI-linked to the existing Smart Labs and Percipio access already being provisioned for the pilot.
2. Fold BigBlueButton in for the Agentic AI Faculty Workshop and any live sessions during the pilot semester — a quick, low-risk way to demonstrate the OTT layer's value before it's fully built out.
3. Treat the AI Tutor as a P1 feature to announce **during** the pilot (not before it) — it becomes the differentiator that converts the free pilot into the paid Year 1 agreement.
4. Everything built for USIU becomes the reusable template for the next university, and the "East Africa University Technology Alliance" vision moves from a proposal paragraph to an actual shared-tenancy architecture.
