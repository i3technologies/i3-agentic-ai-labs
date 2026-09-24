# LMS & Bootcamp Content Authoring Platform — Technical Specification & Implementation Document

**Powered by Agentic AI · Delivered via OTT Channel**
**Document ID:** SPEC-AI-AUTHOR-OTT-001 · **Version:** 1.0 · **Date:** 2026-09-20
**Prepared by:** Senior Solutions Architect / Full-Stack Development Review
**Source material:** *i3 Academy Bootcamp Reading Guide.xlsx* (3,994 catalog entries · 3,593 unique titles · 7 tracks · 3 levels)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Catalog Analysis & Content Portfolio Review](#2-catalog-analysis--content-portfolio-review)
3. [Shortlisted Priority Reading List (Content Authoring Backlog)](#3-shortlisted-priority-reading-list)
4. [Solution Vision & Scope](#4-solution-vision--scope)
5. [Reference Architecture](#5-reference-architecture)
6. [Agentic AI Content Authoring Engine](#6-agentic-ai-content-authoring-engine)
7. [Multi-Format Content Production Pipeline](#7-multi-format-content-production-pipeline)
8. [LMS Integration Layer](#8-lms-integration-layer)
9. [OTT Delivery Channel](#9-ott-delivery-channel)
10. [Data Models](#10-data-models)
11. [API Specifications](#11-api-specifications)
12. [Security, Licensing & Compliance](#12-security-licensing--compliance)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Technology Stack](#14-technology-stack)
15. [Success Metrics & QA Gates](#15-success-metrics--qa-gates)
16. [Risks & Mitigations](#16-risks--mitigations)

---

## 1. Executive Summary

The i3 Academy library contains **3,994 digital titles across 7 bootcamp tracks** (Foundations / Intermediate / Advanced). This document specifies an end-to-end platform that:

1. **Authors content automatically** — an Agentic AI pipeline reads, summarizes, structures, and transforms source books into LMS-ready learning objects in **all modern delivery formats** (interactive video, micro-learning, e-books, audio/podcasts, assessments, labs, flashcards, instructor guides).
2. **Delivers content through an OTT channel** — a Netflix-class streaming experience (web, mobile, TV) for video lessons, live bootcamp sessions, and serialized learning series.
3. **Maps everything to the existing Track × Level matrix** so curriculum managers can assemble bootcamp cohort paths directly from the generated catalog.

**Key portfolio insight from the review:** the catalog is heavily weighted toward *Data, AI & Emerging Technologies* (1,510 titles, 37.8%) and *Intermediate* level (2,957 titles, 74.1%), with source formats dominated by PDF (2,533) and EPUB (1,426). This makes the collection exceptionally well-suited for LLM-based ingestion (text-dense, digitally born sources) and means the platform's **first authoring wave should target the AI/ML and Cybersecurity tracks at Intermediate level**, where both volume and market demand are highest.

---

## 2. Catalog Analysis & Content Portfolio Review

### 2.1 Track × Level Distribution (verified against source workbook)

| Track | Foundations | Intermediate | Advanced | Total | Share |
|---|---:|---:|---:|---:|---:|
| Data, AI & Emerging Technologies | 141 | 1,195 | 174 | **1,510** | 37.8% |
| Programming & Computer Science | 114 | 437 | 94 | **645** | 16.2% |
| Cybersecurity & Digital Forensics | 51 | 456 | 54 | **561** | 14.0% |
| Systems, Networks & Cloud Infrastructure | 99 | 283 | 101 | **483** | 12.1% |
| Web, Design & Digital Media | 55 | 357 | 63 | **475** | 11.9% |
| IT Foundations | 43 | 199 | 27 | **269** | 6.7% |
| Professional & Career Development | 11 | 30 | 10 | **51** | 1.3% |
| **TOTAL** | **514** | **2,957** | **523** | **3,994** | 100% |

### 2.2 Format & Recency Profile

| Dimension | Findings | Architectural Implication |
|---|---|---|
| Formats | PDF 2,533 · EPUB 1,426 · MOBI 24 · AZW3 9 | Ingestion adapters: PDF parser, EPUB parser, MOBI/AZW3 converter (Calibre-style) |
| Publication years | 2026: 1,710 · 2025: 1,406 · 2024: 750 · 2023: 89 · 2022: 26 · 2021: 13 | 93% of sources are ≤ 2 years old — low staleness risk; freshness check still enforced per source |
| Duplicate editions | 3,994 entries → 3,593 unique titles (~10% edition/format duplicates) | Deduplication agent required before authoring; ISBN-based merge |
| Top categories | AI (448) · Computer Programming (427) · Computer Security (418) · Robotics (361) · IoT (284) · Blockchain (278) · Web Dev (195) · Forensics (167) | Specialist authoring agents mapped 1:1 to the top categories |

### 2.3 Architect's Review Notes

- **Strengths:** exceptional topical currency (agentic AI, LLM engineering, RAG, Claude/ChatGPT toolchains are heavily represented), clean taxonomy (Track → Level → Category), strong publisher mix (O'Reilly, Packt, CRC, Wiley, Manning, No Starch) implying consistent structure quality for machine ingestion.
- **Gaps/risks:** (a) ~10% duplicate/format-variant records must be merged to avoid authoring duplicate content; (b) some records lack ISBN or page counts — ingestion must tolerate partial metadata; (c) licensing: source books are reference material for *authoring* original derivative content; copyright guardrails (§6.6, §12) must prevent verbatim reproduction; (d) Foundations-level coverage is thin in Cybersecurity (51) and Career Development (51 total) — flag for original content creation rather than AI-authored derivation.

---

## 3. Shortlisted Priority Reading List

> Selection criteria: track strategic value, market demand, recency (2025–2026), category coverage fit, and suitability for multi-format transformation. These form **Authoring Wave 1 (Phase 1 of the roadmap)**.

### 3.1 Data, AI & Emerging Technologies (Wave 1 primary)

| # | Title (source ref) | Level | Category | Authoring Output Priority |
|---|---|---|---|---|
| 1 | Hands-On RAG for Production (O'Reilly, 2026) | Intermediate | AI, Computer Programming | Full stack: video series + labs + assessments |
| 2 | Agentic AI for Engineers (Apress, 2026) | Advanced | AI | Capstone-grade video course + project lab |
| 3 | Build a Reasoning Model (From Scratch) (Manning MEAP, 2026) | Foundations | AI, Data Science | Interactive notebook course |
| 4 | 50 ML Projects to Understand LLMs (Packt, 2026) | Intermediate | AI | Lab-only course (hands-on first) |
| 5 | The RLHF Book (Manning MEAP, 2026) | Intermediate | AI | Video + audio (commute format) |
| 6 | Machine Learning: A Concise Introduction (Wiley, 2026) | Foundations | AI | Foundations video series |
| 7 | Practical Multi-Agent AI Systems (Wiley, 2026) | Intermediate | AI | Advanced lab track |
| 8 | Generative AI on Kubernetes (O'Reilly, 2026) | Intermediate | AI, Cloud | DevOps-flavored course |
| 9 | Quantum Machine Learning (CRC, 2026) | Intermediate | AI | Elective module (Advanced) |
| 10 | Privacy and Security for Large Language Models (O'Reilly, 2026) | Intermediate | AI, Security | Cross-track (Cybersecurity bridge) |

### 3.2 Programming & Computer Science

| # | Title | Level | Notes |
|---|---|---|---|
| 1 | Designing Data-Intensive Applications, 2nd ed. (O'Reilly, 2026) | Advanced | Flagship systems course |
| 2 | Python Automation Cookbook (Packt, 2026) | Advanced | Recipe/lab format |
| 3 | Deep Learning with Python, 3rd ed. (Manning, 2025) | Intermediate | Core DL track |
| 4 | The Rust Programming Language, 3rd ed. (No Starch, 2026) | Intermediate | Language series |
| 5 | Fundamentals of Software Architecture, 2nd ed. (O'Reilly, 2025) | Foundations | Architecture literacy for all tracks |

### 3.3 Cybersecurity & Digital Forensics

| # | Title | Level | Notes |
|---|---|---|---|
| 1 | Agentic AI for Cybersecurity (Cisco Press, 2026) | Intermediate | AI×Sec flagship |
| 2 | AI for Cybersecurity: Research and Practice (Wiley-IEEE, 2026) | Advanced | Graduate-level series |
| 3 | Practical AI Security (No Starch, 2026) | Intermediate | Hands-on labs |
| 4 | From Day Zero to Zero Day (No Starch, 2025) | Advanced | Vulnerability research track |
| 5 | Foundations of Cybersecurity, 2nd ed. (No Starch, 2026) | Foundations | Onboarding module |

### 3.4 Systems, Networks & Cloud Infrastructure

| # | Title | Level | Notes |
|---|---|---|---|
| 1 | Kubernetes in Action, 2nd ed. (Manning, 2026) | Intermediate | Core platform engineering |
| 2 | Cloud Security Fundamentals (Wiley, 2026) | Foundations | Cross-track required module |
| 3 | Mastering AWS Cloud (BPB, 2026) | Advanced | Certification-aligned |
| 4 | Data Engineering with Medallion Architecture (BPB, 2026) | Advanced | Data platform path |

### 3.5 Web, Design & Digital Media

| # | Title | Level | Notes |
|---|---|---|---|
| 1 | Designing and Prototyping Interfaces with Figma (Packt, 2026) | Intermediate | UI/UX core |
| 2 | Web Development with Django 6 (Packt, 2026) | Intermediate | Backend web path |
| 3 | React and React Native, 6th ed. (Packt, 2026) | Intermediate | Frontend path |
| 4 | The Fundamentals of UX Writing (Apress, 2026) | Foundations | Short-form micro-course |

### 3.6 IT Foundations & Professional Development

| # | Title | Level | Notes |
|---|---|---|---|
| 1 | Computing Essentials (McGraw Hill, 2026) | Foundations | IT Foundations anchor |
| 2 | Azure Fundamentals AZ-900 Study Guide (O'Reilly, 2026) | Foundations | Certification prep |
| 3 | CompTIA SecurityX CAS-005 Certification Guide (Packt, 2025) | Advanced | Cert track |
| 4 | Reskilling and Upskilling in the Age of AI (CRC, 2026) | Intermediate | Career Development anchor (thin track — priority original content) |

**Wave 1 total: ~40 source titles → ~320–400 generated learning objects (modules, videos, labs, assessments).**

---

## 4. Solution Vision & Scope

### 4.1 Vision
"Every book in the i3 library becomes a complete, multi-format, track-aligned learning experience — authored by agents, curated by humans, delivered like streaming media."

### 4.2 Scope

**In scope**
- Ingestion of PDF/EPUB/MOBI/AZW3 source titles (library-licensed)
- Agentic AI authoring of original derivative learning content in 8 output formats
- Track/Level/Curriculum mapping aligned to the existing matrix
- LMS delivery (SCORM 2004 / xAPI / LTI 1.3 / Common Cartridge)
- OTT delivery channel (web, iOS, Android, tvOS, Android TV, Roku)
- Human review workflow, editorial QA, copyright guardrails
- Analytics: learning analytics (LMS) + streaming analytics (OTT)

**Out of scope (v1)**
- Live virtual classroom (roadmap Phase 4)
- Proctored exams (integrate with third-party)
- AR/VR immersive labs (Phase 5 R&D)
- Human-authored original courses for gap areas (Wave 3)

### 4.3 Personas

| Persona | Needs |
|---|---|
| Curriculum Manager | Assemble bootcamp paths from generated catalog; approve/flag AI content |
| Instructor / SME | Review, edit, and approve agent-authored modules; record voiceovers |
| Learner (bootcamp) | Consume multi-format content; progress tracking; hands-on labs |
| Learner (OTT self-paced) | Binge-style learning series; mobile/offline; audio mode |
| Administrator | License, DRM, entitlements, analytics dashboards |

---

## 5. Reference Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        SOURCE LIBRARY (3,994 TITLES)                        │
│              PDF · EPUB · MOBI · AZW3  ──  License Registry                │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — INGESTION & NORMALIZATION                                        │
│  Adapters → Dedup Agent (ISBN merge) → Metadata Enricher → Content Store   │
│  (object storage + vector DB + relational catalog)                          │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — AGENTIC AI AUTHORING ENGINE (see §6)                             │
│  Orchestrator → Specialist Agents (Outline/Draft/Assessment/Code-Lab/       │
│  Video-Script/Audio/Pedagogy) → Critic & Fact-Check Agents → HITL Review    │
└──────────────┬───────────────────────────────────────────────┬─────────────┘
               ▼                                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────────────────┐
│  LAYER 3 — CONTENT SERVICES  │   │  LAYER 3b — FORMAT RENDERING FACTORY      │
│  Module Store · Versioning   │   │  Video render (avatars+slides) · TTS      │
│  Curriculum Mapper · Search  │   │  EPUB/HTML export · SCORM/xAPI packager  │
└──────────────┬───────────────┘   └──────────────────────┬───────────────────┘
               ▼                                            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — DELIVERY                                                         │
│  ┌─────────────────────┐        ┌───────────────────────────────────────┐  │
│  │  LMS (Moodle/Canvas) │        │  OTT PLATFORM                        │  │
│  │  SCORM/xAPI/LTI/CC   │        │  CMS → Transcoder → DRM → CDN        │  │
│  │  Gradebook, cohorts  │        │  Web · iOS · Android · TV apps       │  │
│  └─────────────────────┘        └───────────────────────────────────────┘  │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — ANALYTICS & GOVERNANCE                                           │
│  xAPI Learning Record Store · Streaming QoS analytics · Entitlements        │
│  Copyright compliance audit trail · Agent quality dashboards                │
└────────────────────────────────────────────────────────────────────────────┘
```

**Deployment model:** Cloud-native, Kubernetes-based, multi-tenant (region-pinned for data residency). Event-driven backbone (Kafka) between layers; each agent is a horizontally scalable microservice.

---

## 6. Agentic AI Content Authoring Engine

### 6.1 Agent Orchestration Design

| Agent | Role | Model class | Inputs | Outputs |
|---|---|---|---|---|
| **Librarian Agent** | Catalog hygiene: dedup by ISBN/title fuzzy-match, metadata enrichment, staleness flag | LLM + rules | Raw catalog rows | Canonical title records |
| **Curriculum Mapper Agent** | Maps each title → Track, Level, Category, prerequisites, estimated hours | LLM + taxonomy DB | Canonical record | Curriculum node |
| **Outline Architect Agent** | Builds course/module/lesson hierarchy from book TOC and pedagogy patterns | LLM (long-context) | Parsed book, curriculum node | Module blueprint (JSON) |
| **Author Agent (×7 specialists)** | Writes original lessons per category (AI/ML, Security, Programming, Cloud, Web, Data, Foundations) | LLM + RAG over source | Blueprint, source chunks | Lesson drafts (markdown/JSON) |
| **Code-Lab Agent** | Generates runnable labs, Jupyter notebooks, Docker-based exercises, solution code + tests | LLM + sandbox executor | Lesson draft | Lab package (git repo) |
| **Assessment Agent** | Quizzes, rubrics, capstone projects; Bloom's-taxonomy tagging | LLM | Lesson draft | QTI 3.0 / JSON assessments |
| **Video-Script Agent** | Turns lessons into scene-by-scene scripts with visual directions | LLM | Lesson draft | Script JSON |
| **Multimedia Producer Agent** | Slides (HTML/PPTX), avatar voiceover, TTS narration, diagrams (Mermaid/d2) | LLM + TTS + image gen | Script JSON | Render-ready assets |
| **Pedagogy Critic Agent** | Reviews against learning objectives, reading level, completeness | LLM (evaluator) | Draft module | Scorecard + revision notes |
| **Fact-Check & Citation Agent** | Verifies claims against source; flags verbatim overlap (copyright) | LLM + embeddings | Draft module | Verdict: approve / revise |
| **Compliance Agent** | Copyright similarity threshold, license check, PII scan | Rules + embeddings | Final draft | Compliance certificate |
| **Human Review UI** | SME approve/edit/reject with tracked changes | — | Flagged module | Signed-off version |

**Orchestration pattern:** Hierarchical planner (Outline Architect → parallel specialist authoring → critic loop, max 3 iterations) implemented with a workflow engine (Temporal). Each agent invocation is idempotent, versioned, and logged for full auditability.

### 6.2 Retrieval-Augmented Grounding
- Every source title is chunked, embedded, and stored in a **per-title vector namespace**; authoring agents may only cite/ground from the licensed namespace of the title being processed (prevents cross-contamination and unsourced claims).
- Long-context models ingest full TOCs and chapter structures directly; chunk-level RAG handles deep drafting.

### 6.3 Human-in-the-Loop (HITL) Gates
1. **Gate A** — Curriculum blueprint approval (Curriculum Manager)
2. **Gate B** — Lesson draft approval (SME sample-review: 20% auto-sampled, 100% for Advanced level and all assessments)
3. **Gate C** — Compliance certificate sign-off (automated + legal-spot-check)

### 6.4 Quality Scoring (auto-computed per module)
`Q = w1·factual_grounding + w2·pedagogy_alignment + w3·readability + w4·assessment_coverage + w5·format_completeness` — modules below threshold 0.80 are auto-revised before HITL.

### 6.5 Agent Infrastructure
- Model gateway (OpenAI / Anthropic / open-weight Llama-class via vLLM) with per-agent routing, fallback, and cost budgets
- Prompt registries versioned in Git; A/B evaluation harness (LM-eval style) for prompt upgrades
- GPU inference pool autoscaling; batch authoring queues (Kafka)

### 6.6 Copyright Guardrails (hard constraints)
- Max 8% n-gram overlap with source text; embeddings similarity ceiling enforced by Compliance Agent
- All output labeled as "AI-authored derivative learning material" with source attribution metadata
- No images/tables reproduced from source unless licensed; all diagrams regenerated

---

## 7. Multi-Format Content Production Pipeline

For each approved lesson, the pipeline emits **eight synchronized artifacts** from one canonical content model (CMS-JSON, §10):

| # | Format | Production method | Delivery channel |
|---|---|---|---|
| 1 | **Video lesson** (5–12 min) | Avatar presenter + auto-generated slides + code demos; rendered via headless video pipeline | OTT (HLS/DASH) + LMS embed |
| 2 | **Interactive e-book / HTML lesson** | Authored markdown → styled HTML/EPUB | LMS + OTT reading mode |
| 3 | **Audio / podcast episode** | TTS (neural voices) or SME voiceover + chapter markers | OTT audio + podcast feeds |
| 4 | **Micro-learning cards** | Key concepts → flashcards/spaced-repetition deck | Mobile app |
| 5 | **Hands-on lab** | Git repo + Jupyter notebook + Docker image + auto-grader | LMS lab runner (Kubernetes jobs) |
| 6 | **Assessment** | QTI 3.0 quizzes + auto-graded code tasks | LMS gradebook |
| 7 | **Instructor kit** | Slides (PPTX), talking points, facilitation guide | Instructor portal |
| 8 | **Live-session plan** (Phase 4) | Workshop agenda + breakout exercises | Virtual classroom |

**Rendering pipeline:** Canonical JSON → Pandoc/Jinja templates (text) · Remotion/FFmpeg headless render (video) · Azure Neural/Google TTS (audio) · Puppeteer screenshot pipeline (slides/diagrams) · SCORM/xAPI packager (LMS bundles).

---

## 8. LMS Integration Layer

- **Standards:** SCORM 2004 (4th ed.) packaging for legacy LMS, **xAPI statements to an LRS** as the primary tracking spine, LTI 1.3 for tool launch, Common Cartridge for course import, QTI 3.0 for assessments, Caliper Analytics optional.
- **Reference LMS:** Moodle 4.x (self-hosted) with custom plugins; Canvas via LTI for enterprise clients.
- **Bootcamp features:** cohort management, learning paths auto-assembled from Track×Level matrix, prerequisites enforced by Curriculum Mapper graph, competency-based progression gates, instructor dashboards.
- **API-first:** every LMS function exposed via REST/GraphQL so the OTT apps share one learner identity and progress state (single learner profile, SSO via OIDC).

---

## 9. OTT Delivery Channel

### 9.1 Media Pipeline
```
Source renders (ProRes/MP4 master) → Transcoder (H.264/H.265/AV1 ladders,
  240p→4K, per-title encoding) → DRM (Widevine + FairPlay + PlayReady)
  → Origin (object storage) → Multi-CDN (HLS LL + DASH) → Apps
```
- **Audio:** AAC 128–256k + Opus; podcast RSS feeds with dynamic ad-free entitlements
- **Offline:** encrypted downloads (DRM-licensed) on mobile/TV
- **Live (Phase 4):** WebRTC/LL-HLS live bootcamp sessions with DVR window

### 9.2 OTT Application Suite
| App | Stack | Notes |
|---|---|---|
| Web | React + Shaka Player / hls.js | PWA, offline cache |
| iOS / tvOS | Swift + AVPlayer (FairPlay) | AirPlay, downloads |
| Android / Android TV | Kotlin + ExoPlayer (Widevine) | Cast, downloads |
| Roku / Smart TV (Phase 3) | BrightScript / Tizen web | |

### 9.3 Learning UX on OTT
- "Netflix-style" rows: *Continue Learning · Your Track (e.g., Data, AI & Emerging Tech) · Foundations→Intermediate→Advanced ladders · New AI-authored releases · Assessment reviews*
- **Dual-mode playback:** Watch (video) ↔ Listen (audio) with position sync
- **In-player checks:** pause-point quiz overlays; xAPI statements fired from player for LMS progress
- **Kid/enterprise profiles:** bootcamp cohort profile vs. individual self-paced profile

### 9.4 Recommendations & Search
- Agentic recommendation service (LLM + collaborative filtering) using Track×Level taxonomy + learner behavior
- Natural-language search over full generated catalog ("build me a 6-week RAG engineering path")

---

## 10. Data Models

### 10.1 Canonical Content Model (simplified)
```json
{
  "module_id": "uuid",
  "source_title_id": 1456,
  "track": "Data, AI & Emerging Technologies",
  "level": "Intermediate",
  "categories": ["AI", "Computer Programming"],
  "learning_objectives": ["..."],
  "lessons": [{
    "lesson_id": "uuid",
    "title": "...",
    "duration_min": 10,
    "assets": {
      "video_master": "s3://.../master.mp4",
      "script": "cms://.../script.json",
      "audio": "s3://.../audio.mp3",
      "ebook_html": "cms://.../lesson.html",
      "lab_repo": "git://labs/uuid",
      "assessment_qti": "cms://.../quiz.qti",
      "micro_cards": "cms://.../deck.json",
      "instructor_kit": "cms://.../kit.zip"
    },
    "quality": { "score": 0.87, "gate": "B-approved", "reviewer": "sme@i3" },
    "compliance": { "overlap_pct": 2.1, "certificate_id": "uuid", "license": "library-derivative-v1" },
    "xapi_activity_iri": "https://lms.i3.academy/xapi/activities/..."
  }],
  "prerequisites": ["module_uuid"],
  "estimated_hours": 6.5
}
```

### 10.2 Core Entities
`SourceTitle · CanonicalTitle (deduped) · CurriculumNode · Module · Lesson · Asset · Assessment · Enrollment · Progress (xAPI) · Entitlement · AgentRun (audit) · ComplianceCertificate`

---

## 11. API Specifications (selected endpoints)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/ingestion/titles` | Register source title (PDF/EPUB upload or library ref) |
| POST | `/v1/authoring/jobs` | Kick off agentic authoring for a title `{track, level, formats[]}` |
| GET | `/v1/authoring/jobs/{id}` | Job status, agent-run trace, quality scores |
| POST | `/v1/review/gates/{gateId}/decisions` | HITL approve/revise/reject |
| GET | `/v1/catalog/modules?track=&level=&format=` | Query generated catalog |
| POST | `/v1/lms/packages` | Generate SCORM/xAPI/Common Cartridge export |
| POST | `/v1/ott/publish` | Publish module assets to OTT CMS + trigger transcode |
| GET | `/v1/learner/progress` (xAPI) | Unified progress across LMS + OTT |
| POST | `/v1/entitlements/grant` | Cohort/license entitlement to content |

**Contracts:** OpenAPI 3.1 spec; async jobs over webhooks; idempotency keys required on mutating endpoints.

---

## 12. Security, Licensing & Compliance

- **Content licensing:** source books consumed under the academy's digital-library license strictly as grounding/authoring references; all generated content carries attribution metadata; per-title license flags block authoring where derivative creation is not permitted.
- **DRM & entitlement:** multi-DRM on OTT; watermarking (forensic for video, visible for PDFs); institutional and per-seat entitlements.
- **Data protection:** learner data region-pinned; GDPR/POPIA-style consent for analytics; PII redaction agent in pipeline.
- **AI governance:** full agent-run audit logs (prompt, model version, source chunks, output hash); model-output quality dashboards; no learner PII in prompts.
- **Platform security:** OIDC SSO + RBAC (Curriculum Manager, SME, Instructor, Learner, Admin), secrets management, encrypted storage in transit/at rest, WAF + rate limiting, SOC2-aligned controls.

---

## 13. Implementation Roadmap

| Phase | Duration | Deliverables |
|---|---|---|
| **Phase 0 — Foundation** | Weeks 1–4 | Infra (K8s, Kafka, object store, vector DB), ingestion adapters for PDF/EPUB, dedup + Librarian Agent, canonical catalog DB |
| **Phase 1 — Authoring Engine MVP** | Weeks 5–12 | Orchestrator + 4 core agents (Outline, Author, Assessment, Fact-Check), HITL review UI, e-book + assessment + micro-card formats; **Wave 1 backlog (§3) piloted: 10 titles → ~100 modules** |
| **Phase 2 — Multi-Format Factory** | Weeks 13–22 | Video render pipeline, TTS audio, lab agent + sandbox runner, SCORM/xAPI packagers; full 8-format output; LMS integration (Moodle + LTI); quality threshold automation |
| **Phase 3 — OTT Launch** | Weeks 23–32 | Transcoder + DRM + CDN, Web/iOS/Android apps, recommendation + NL search, entitlement sync with LMS, pilot cohort rollout (1,000 learners) |
| **Phase 4 — Scale & Live** | Weeks 33–44 | Authoring waves 2–3 (all 7 tracks), live-session layer, Roku/TV apps, enterprise multi-tenant, full catalog coverage plan (3,994 titles staged) |
| **Phase 5 — R&D** | Ongoing | AR/VR labs, adaptive learning engine, agent-personalized tutoring companion |

**Team:** 2 architects, 4 backend, 3 full-stack/OTT, 2 ML/agent engineers, 1 DevOps, 1 security engineer, 2 curriculum SMEs (per track cluster), 1 legal/licensing advisor.

---

## 14. Technology Stack

| Layer | Choices |
|---|---|
| Agent framework | Temporal workflows + LangGraph-style agent graphs; model gateway (OpenAI/Anthropic + vLLM self-hosted) |
| Ingestion | Apache Tika, Calibre conversion, Unstructured.io, Tesseract OCR fallback |
| Storage | S3-compatible object store, PostgreSQL (catalog), pgvector/Milvus (embeddings), Redis (queues/cache) |
| Backend | Python (FastAPI) for AI services · Node.js/NestJS or Kotlin for delivery APIs · GraphQL federation |
| LMS | Moodle 4.x + custom plugins; LRS (Learning Locker / custom) |
| Video | FFmpeg, Remotion, Bunny/AWS MediaConvert-class transcoder, Shaka/ExoPlayer/AVPlayer, Widevine/FairPlay/PlayReady |
| Frontend | React (web/LMS) · React Native or native (OTT) |
| Observability | OpenTelemetry, Prometheus/Grafana, agent-run tracing UI |
| IaC | Terraform + Helm, multi-region failover |

---

## 15. Success Metrics & QA Gates

| Category | KPI | Target (Phase 3 exit) |
|---|---|---|
| Authoring throughput | Modules per week per track (8 formats) | ≥ 60 |
| Quality | Auto-Q score ≥ 0.80 pass rate | ≥ 85% first-pass |
| SME effort | Review minutes per module | ≤ 15 min (Intermediate) |
| Compliance | Overlap violations escaping pipeline | 0 |
| Learner engagement | OTT completion rate per module | ≥ 70% |
| Learning outcomes | Assessment pass rate, pre/post skill gain | ≥ 75% / +30% |
| Delivery | OTT startup time / rebuffer ratio | < 1.5 s / < 0.5% |
| Business | Cost per authored module vs. manual benchmark | ≤ 20% of manual cost |

---

## 16. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Copyright exposure from AI derivatives | Legal | Hard similarity ceilings, per-title license registry, attribution metadata, legal spot-audits (§6.6, §12) |
| Hallucinated technical content in code/labs | Learner harm | Sandboxed auto-execution of all generated labs; Fact-Check Agent; SME 100% review of Advanced content |
| Duplicate authoring from ~10% edition duplicates | Wasted compute | Librarian dedup agent (ISBN + fuzzy title) before any authoring job |
| OTT vs. LMS learner state divergence | Broken progress | xAPI as single source of truth; event-driven sync; reconciliation jobs |
| Model cost escalation at 3,994-title scale | Budget | Per-title cost budgets, small-model routing for mechanical tasks, batch inference, caching |
| Foundations-level gaps (Cybersecurity 51, Career 51) | Curriculum imbalance | Flag as *original human-authored* content (Wave 3), not AI-derived |
| Thin metadata (missing ISBN/pages) | Ingestion failures | Graceful defaults; publisher-API enrichment; manual queue |

---

## Appendix A — Wave 1 Authoring Job Template

```json
POST /v1/authoring/jobs
{
  "source_title_id": 1456,
  "target": {
    "track": "Data, AI & Emerging Technologies",
    "level": "Intermediate",
    "categories": ["AI", "Computer Programming"]
  },
  "formats": ["video","ebook","audio","micro_cards","lab","assessment","instructor_kit"],
  "quality_threshold": 0.80,
  "hitl_gates": ["A", "B", "C"],
  "publish_targets": ["lms", "ott"]
}
```

## Appendix B — Glossary

- **Agentic AI:** LLM-driven agents that plan, invoke tools, and iterate toward a goal under governance constraints
- **OTT:** Over-the-top media delivery — streaming apps independent of traditional broadcast
- **xAPI / LRS:** Experience API statements recording learning activity to a Learning Record Store
- **QTI:** Question & Test Interoperability standard for assessments
- **HITL:** Human-in-the-loop review gate
- **RAG:** Retrieval-Augmented Generation (grounding model output in licensed source chunks)

---

*End of document — SPEC-AI-AUTHOR-OTT-001 v1.0*
