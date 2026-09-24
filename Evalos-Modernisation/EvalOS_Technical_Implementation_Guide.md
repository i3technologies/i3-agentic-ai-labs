# EvalOS Technical Implementation Guide
### AI-Native Skills Verification, Certification Intelligence & Workforce Readiness Platform

| Field | Value |
|---|---|
| **Document ID** | ARCH-EVALOS-2026-V2 (Consolidated) |
| **Prepared as** | Senior Solutions Architect / Full-Stack Technical Blueprint |
| **Prepared for** | i3 Technologies Limited — EvalOS Platform Engineering |
| **Sources synthesized** | Global Professional Exam & Assessment Platforms Report · EvalOS Technical Implementation Document (ARCH-EVALOS-2026-V1) · Senior Principal Architect Blueprint (Capability Layers) · EvalOS User Guide v2 |
| **Scope** | High-Stakes Certification · Technical/Coding Assessment · Psychometrics · Agentic AI · Practical Labs · Credentials |
| **Status** | Implementation-Ready Architecture |

---

## 1. Executive Summary

EvalOS today delivers timed MCQ exams, a Study Coach, AI Interview practice, a Coding Lab (Monaco + Qwen Coder), digital PDF certificates, and prerequisite gating on Keycloak SSO. That is a solid v1 assessment tool — but it is **not yet** a defensible platform. It lacks VUE-grade identity/integrity controls, adaptive testing, practical lab evidence at scale, multi-agent evaluation, and a skills graph that threads assessment → learning → certification → admissions → employment into one continuous loop.

This guide fuses the strongest, provable capabilities of three mature market categories with the current state of the art in **Agentic AI** into a single implementation-ready architecture:

1. **High-Stakes Certification & Licensure Networks** — Pearson VUE, Prometric, PSI, Kryterion, Meazure Learning (ProctorU + Yardstick), Certiport
2. **Technical & Developer Screening Platforms** — HackerRank, Codility, CoderPad, HackerEarth, TestDome, Coderbyte, Glider AI, WeCP
3. **Psychometric & Enterprise Talent Measurement** — SHL, Talent Q (Korn Ferry), Mercer Mettl
4. **Agentic AI State of the Art (2025–2026)** — multi-agent evaluation swarms, adaptive scenario generation, tool-using and self-critiquing agents, privacy-preserving integrity scoring, and AI-native "can you engineer with AI" assessment.

**Strategic Positioning**

> EvalOS is not another HackerRank clone. It is i3's **AI-Native Skills Verification Infrastructure** — the operating system that measures what a candidate knows, observes what they can actually do inside real cloud laboratories, diagnoses what they need to learn, issues verifiable credentials, and feeds that evidence to admissions, certification bodies, and employers.

**The Loop EvalOS Owns**

```
ASSESS → PRACTICE → SIMULATE → CERTIFY → VERIFY → EMPLOY → UPSKILL
```

Competitors can copy an editor or a proctoring widget. They cannot easily replicate a closed evidentiary loop that gets smarter with every evaluation.

---

## 2. Market Synthesis — Best Features to Adopt, by Category

### 2.1 High-Stakes Certification & Licensure Networks (Pearson VUE Peer Group)

| Capability | Source Platforms | Priority |
|---|---|---|
| Multi-factor identity verification (photo ID + live selfie + liveness + mid-exam re-checks) | Pearson VUE, Prometric, Kryterion | **P0** |
| Digital identity wallets & passkey-based re-authentication | Emerging across the category | **P2** |
| Secure/locked browser + kiosk mode, clipboard & screen-capture controls, secondary-monitor detection | Pearson VUE, Meazure Learning | **P0** |
| AI + human-assisted remote proctoring (flag-then-review, not auto-fail) | Meazure (ProctorU), Kryterion | **P1** |
| Psychometric validity — Item Response Theory (IRT), item calibration, SOC 2 Type II | Prometric, PSI | **P1** |
| Large rotating item banks with automated form assembly | All major providers | **P0** |
| Verifiable, revocable digital credentials | Certiport, Pearson VUE | **P1** |
| Data residency & regulatory compliance by region | All | **P0** |
| Foundational/entry-tier credential tracks (digital literacy, vendor fundamentals) | Certiport | **P2** |

### 2.2 Technical & Developer Screening Platforms (HackerRank Peer Group)

| Capability | Source Platforms | Priority |
|---|---|---|
| Multi-language / multi-framework execution (50–80+ languages) | HackerRank, TestDome, Coderbyte | **P0** |
| Realistic multi-file / take-home projects with Docker & Git | Coderbyte, Glider AI | **P0** |
| Live collaborative IDE / pair-programming interviews | CoderPad, HackerEarth | **P2** |
| Automated unit/integration/security test runners with hidden test suites | All | **P0** |
| AI-assisted code review, hints, and feedback | Glider AI, WeCP | **P0** |
| Custom skill-matrix / test-creation engines | WeCP | **P1** |
| Hackathon / innovation-contest formats for sourcing | HackerEarth | **P2** |
| Work-sample evidence testing across languages | TestDome | **P1** |
| Bias-reduction & algorithmic-fairness tooling in scoring | Codility | **P1** |
| Skill graphs / competency mapping | Composite of category | **P1** |
| Plagiarism / code-similarity detection (AST + semantic) | HackerRank, Codility | **P1** |
| API-first design with ATS/LMS integrations (Workday, Greenhouse, Canvas, Moodle) | All enterprise platforms | **P0** |
| Candidate-experience features — autosave, pause/resume, constructive feedback | Coderbyte, category best practice | **P0** |

### 2.3 Psychometric, Aptitude & Enterprise Testing

| Capability | Source Platforms | Priority |
|---|---|---|
| Computer-adaptive testing (CAT / IRT-driven item selection) | Talent Q, SHL | **P1** |
| Multi-dimensional scoring — cognitive + behavioral + technical in one engine | SHL, Mercer Mettl | **P1** |
| Bias-audit dashboards & blind-review modes | Codility, SHL | **P1** |
| Hybrid technical + psychometric assessment engines | Mercer Mettl | **P2** |
| Executive/leadership talent analytics | SHL | **P2** |

### 2.4 Agentic AI Innovations (2025–2026 State of the Art)

| Innovation | Description | Priority |
|---|---|---|
| Multi-agent evaluation swarms | Specialized agents (Designer, QA, Examiner, Adversarial, Integrity, Tutor) coordinated by an orchestrator | **P0** |
| AI-generated equivalent assessment forms | Same competency, different surface details → defeats leakage/memorization | **P0** |
| Adaptive scenario generation | Live difficulty/constraint tuning based on observed candidate behavior | **P1** |
| AI-native engineering assessment modes | Closed-book / AI-Allowed / AI-Required tiers that measure human+AI collaboration | **P1** |
| Privacy-preserving, risk-scored integrity | Explainable evidence feeding a "requires human review" flag rather than an auto-fail verdict | **P0** |
| Longitudinal Skills Graph & Skills Passport | Evidence → proficiency → credential → employability, compounding in value over time | **P1** |
| Human-in-the-loop calibration | Agents propose; humans retain final authority on high-stakes and flagged decisions | **P0** |
| Agent-to-agent critique (critic/aggregator pattern) | A second agent actively tries to falsify the first agent's judgment before a score is finalized | **P0** |
| Tool-using evaluator agents | Agents call real compilers, linters, test runners, and cloud APIs rather than "eyeballing" code | **P0** |
| Meta-evaluation ("evaluator of evaluators") | A supervisory agent audits agent-score drift and bias over time | **P1** |

---

## 3. Current EvalOS State & Gap Analysis

### 3.1 Existing Capabilities

- Keycloak SSO authentication
- Timed, randomized MCQ exams with auto-grading (on-cluster LiteLLM)
- Study Coach (post-attempt AI remediation)
- AI Interview practice
- Coding Lab (Monaco editor + Qwen Coder review)
- Digital PDF certificates with a verification code
- Prerequisite gating (≥90% pass threshold)
- Basic anti-cheat: tab-switch/focus-loss logging, question/option shuffle, limited copy-paste restriction
- 30-minute inactivity resume window
- Leaderboard and the "Zuri" chat assistant

### 3.2 Critical Gaps

| Gap Area | Current State | Target State |
|---|---|---|
| Identity Verification | SSO login only | Photo ID + live selfie match + mid-exam re-verification + device fingerprint binding + optional passkeys |
| Environment Lockdown | None | Kiosk mode, tab/window/devtools/monitor detection |
| Webcam / Audio Monitoring | None | Periodic AI vision snapshots + flagged-session human review queue |
| Item Bank & Leakage | Fixed pool, order shuffled only | Large rotating bank + AI-generated equivalent forms |
| Adaptive Testing | Fixed question sets | Computer-adaptive (CAT) with real-time skill estimation |
| Practical Evidence | Browser code editor only | Ephemeral multi-tier AI-Lab sandboxes (K8s, Docker, cloud scenarios) |
| Evaluation Depth | Correctness + basic AI review | Multi-agent scoring (Architect, Security, Quality, AI-Collaboration) |
| Skills Representation | Per-exam score | Multi-dimensional Skills Graph + portable Skills Passport |
| Integrity Model | Event logging only | Risk-scored Integrity/Identity/Behavior/Trust confidence with explainable evidence |
| Integrations | Limited | LTI Advantage, QTI 3.0, Open Badges 3.0, admissions webhooks, SCIM, LMS |
| Commercial Surfaces | Internal exams only | B2C Passport, B2B Workforce, University Admissions, Talent Assess, public API, white-label |

---

## 4. Target Product Architecture

### 4.1 Product Family (Single Engine, Multiple Commercial Surfaces)

```
i3 SkillForge AI™  (Platform Brand)
│
├── EvalOS Assess™          – AI-powered multi-modal assessment engine
├── EvalOS Lab™             – Practical cloud laboratory & incident-simulation sandbox
├── EvalOS CertReady™       – Certification-readiness diagnostics & mock exams
├── EvalOS Interview AI™    – Agentic behavioral & technical interviewing
├── EvalOS AdmitAI™         – AI-assisted admissions pre-screening
├── EvalOS Passport™        – Verifiable, longitudinal skills identity
├── EvalOS Talent™          – Employer-facing skills assessment & sourcing
├── EvalOS Workforce™       – Enterprise organizational skills intelligence
└── EvalOS API™             – Assessment-as-a-Service infrastructure
```

All products run on the shared **i3 Skills Intelligence Platform**, on the existing IBM ROKS/OpenShift stack.

### 4.2 Logical Architecture

```
CDN / WAF
    │
API Gateway (Kong / Envoy) + OIDC / mTLS
    │
Identity & IAM (Keycloak + Device Fingerprint + Passkeys + Session Binding)
    │
┌───────────────────────┼───────────────────────┐
│                       │                       │
Assessment API     AI Gateway / Agent Runtime   Integrity Service
│                       │                       │
├─ Test Catalog         ├─ Assessment Designer  ├─ Proctor Agent
├─ Adaptive Engine      ├─ Question Quality     ├─ Vision Monitor
├─ Results Engine       ├─ Code Examiner        ├─ Anomaly Detector
└─ Credential Engine    ├─ Tutor Agent          └─ Collusion Engine
                        ├─ Interview Agent
                        ├─ Certification Agent
                        └─ Career / Admissions Agent
    │
Skills Graph / AI Profile (vector + relational)
    │
┌───────────┼───────────┬──────────────┐
│           │           │              │
AI-Lab     LMS         Admissions     Employers
(Sandbox)  (Skillsoft) (AdmitAI)      (Talent)
    │
Digital Credential / Open Badges 3.0 / Verifiable Credentials
```

### 4.3 Bounded Contexts (Domain-Driven Design)

| Bounded Context | Responsibility | Primary Tech |
|---|---|---|
| Identity & Context | Auth, session binding, device fingerprint, consent, passkeys | Keycloak, FingerprintJS, Redis |
| Assessment Pipeline | Blueprint, form assembly, adaptive selection, session lifecycle | Go / Node.js, PostgreSQL |
| Execution & Inference | Sandbox orchestration, multi-agent evaluation | Go + Kubernetes/Nomad, Python (LangGraph) |
| Integrity & Proctoring | Vision, behavioral signals, risk scoring | Python vision models, event stream |
| Skills & Credentials | Skills Graph, Passport, Open Badges issuance | PostgreSQL + Vector DB, credential engine |
| Integration Hub | Admissions webhooks, LTI, QTI, ATS, LMS | Event backbone (Kafka/NATS) |

---

## 5. Core Capability Layers

### Layer 1 — Enterprise Identity, Trust & Integrity Framework
*Inspired by Pearson VUE, PSI, Kryterion, Prometric, Meazure Learning*

**AI Identity Verification**
- Face verification, liveness detection, voice verification, government-ID validation
- Digital identity wallets and passkeys as a lower-friction re-authentication path for repeat candidates
- Device fingerprint + session binding to detect proxy test-takers

**Secure/Locked Browser**
- Browser lockdown, clipboard controls, screen-capture prevention, secondary-monitor detection, background-application monitoring

**Risk-Based Proctoring (not blanket surveillance)**
Instead of a binary "cheating detected" verdict, EvalOS computes four composable scores:

| Score | What it Measures |
|---|---|
| **Identity Score** | Confidence the person taking the exam is who they claim to be |
| **Behavior Score** | Deviation from expected interaction patterns (timing, focus, input cadence) |
| **Integrity Score** | Aggregate signal across copy-paste, tab-switch, code-similarity, AI-generation likelihood |
| **Trust Score** | Composite of the above, feeding a "requires human review" queue — never an automatic fail |

Human review remains the final authority on every flagged session. This mirrors where the high-stakes-testing industry is heading (away from blunt lockdown-and-punish models) while preserving the rigor certification bodies require.

### Layer 2 — Adaptive Psychometric Engine
*Inspired by SHL, Talent Q, Mercer Mettl*

**AI Adaptive Testing** — move from "everyone answers the same 50 questions" to items selected dynamically by knowledge level, response confidence, response speed, error patterns, and skill trajectory (CAT/IRT).

**Psychometric AI Models** evaluate three dimensions in one pass:
- **Cognitive** — numerical reasoning, abstract reasoning, critical thinking, problem-solving
- **Behavioral** — team orientation, leadership signal, innovation, adaptability
- **AI-Readiness** *(new category, i3-specific)* — prompt engineering skill, AI collaboration quality, output-verification discipline, hallucination detection, AI-assisted decision-making

### Layer 3 — Advanced Technical Assessment Cloud
*Inspired by HackerRank, Codility, CoderPad, HackerEarth, TestDome, Glider AI*

**Browser-Based Cloud IDE** — VS Code–class experience: Git integration, Docker support, Kubernetes support, integrated debugging, real terminal access (progressive enhancement path from the existing Monaco editor).

**Supported Assessment Modes**

| Mode | Candidates Do |
|---|---|
| Coding | Algorithms, APIs, full-stack implementation |
| Architecture | Design cloud systems, security models, data platforms |
| DevOps | Resolve real CI/CD failures, Kubernetes incidents, infrastructure faults |
| Cybersecurity | Investigate attacks, malware, SIEM incidents |
| Data Engineering | Build pipelines, data lakes, AI/ML workflows |

### Layer 4 — Practical Skills Assessment Labs (EvalOS Lab™)
The single most important differentiator versus every peer platform, because it converts assessment from **question-based** to **evidence-based**.

Instead of "What is Kubernetes?", the candidate receives: *"Production is down. Fix it."* The lab provisions a live cluster with a genuine fault (misconfigured RBAC, failing deployment, network policy break) and observes commands, configuration changes, the troubleshooting path taken, time-to-resolution, and security decisions — not just the final state.

- Ephemeral, isolated containers / microVMs (Firecracker- or gVisor-style)
- Pre-warmed images for popular stacks + customer-provided images
- Language/technology coverage: Python, Java, JS/TS, Go, Rust, C/C++, SQL, Bash, PowerShell, Docker, Kubernetes, Terraform, Ansible, AWS/Azure/GCP, IBM technologies, cybersecurity tooling, AI/ML, data engineering
- Network isolation by default; only the internal AI-Lab Model Gateway reachable during timed exams
- Full telemetry (command history, config diffs, error trail) scraped to cold storage and disposed of after evaluation

### Layer 5 — Agentic AI Assessment Platform
The strongest innovation opportunity in the entire architecture — see **Section 6** for the full deep dive.

### Layer 6 — Skills Graph, Skills Passport & Digital Credentials

Every piece of evidence maps through a consistent hierarchy:

```
Technology → Competency → Skill → Sub-skill → Assessment Evidence → Proficiency
```

The **Skills Passport** is a portable professional identity containing multi-dimensional proficiency scores, verifiable credentials (Open Badges 3.0 / W3C Verifiable Credentials), lab evidence and project artifacts, and an employability mapping layer usable by admissions offices and employers alike.

Digital credentials carry: candidate, skill, level, assessment ID, score, evidence links, lab artifacts, issuer, date, verification URL, and credential ID — e.g., *"i3 Certified AI-Ready Cloud Engineer."*

---

## 6. Agentic AI Deep Dive — Architecture, Innovations & Use Cases

### 6.1 Agent Mesh Architecture

```
                    Assessment Orchestrator
                             │
        ┌────────────┬───────┴───────┬────────────┐
        │            │               │            │
   Designer      Examiner        Integrity     Interview
        │            │               │            │
      Tutor      Adversarial      Career/     Certification
                     QA           Admissions
```

An **orchestrator** (LangGraph- or CrewAI-style state machine) routes each submission through the agents relevant to that assessment type, aggregates their outputs, and applies human-in-the-loop gates before any high-stakes decision is finalized.

### 6.2 The Agent Roster

| Agent | Responsibility | Output |
|---|---|---|
| **Assessment Designer** | Generates MCQs, coding problems, scenarios, rubrics, and hidden tests from a natural-language brief, job description, or certification blueprint | Assessment blueprint + equivalent variants |
| **Question Quality / QA Agent** | Checks ambiguity, difficulty calibration, fairness, bias, and leakage risk before publication | Quality score + revision recommendations |
| **Architect Agent** | Parses project structure, dependency graphs, and design patterns in submitted code | Architecture score + findings |
| **Adversarial QA Agent** | Actively injects edge cases, fuzzing, race conditions, and malformed inputs against the candidate's solution | Resilience & security score |
| **Code Examiner** | Correctness, complexity, maintainability, test coverage, documentation quality | Multi-dimensional code-quality vector |
| **AI-Collaboration Agent** | Analyzes prompting technique, refinement loops, and hallucination-catching behavior in AI-assisted modes | AI-native engineering competency score |
| **Proctor / Integrity Agent** | Aggregates behavioral + vision signals into the Identity/Behavior/Integrity/Trust score set | Risk score + explainable evidence |
| **Interview Agent** | Conducts agentic behavioral and technical interviews, adapts follow-up questions live | Structured interview transcript + competency ratings |
| **Tutor Agent** | Post-assessment gap analysis and a personalized remediation plan | Study path with resource links |
| **Certification Agent** | Ready / Almost Ready / Not Ready decision plus concrete next actions | Readiness band + recommendation |
| **Admissions / Career Agent** | Maps a candidate's Skills Passport to matching programmes or roles | Recommendation verdict |

### 6.3 The Evaluation Pipeline (Per Submission)

```
Submission + Rubric + Context
        │
        ▼
1. Environment Setup — ephemeral sandbox provisioning
2. Deterministic Layer — unit/integration/e2e tests, coverage, security lint
3. Analytical Layer — static analysis, complexity metrics, architectural smells
4. LLM Judgment Layer
   ├── Primary Judge      – produces an initial scored rationale
   ├── Critic             – actively tries to find counter-evidence against the Judge
   └── Aggregator         – reconciles both into a calibrated score + confidence
5. Structured Output
   ├── Numeric skill vector
   ├── Natural-language justification
   └── Artifacts (logs, coverage reports, diffs)
```

The **Judge → Critic → Aggregator** pattern is the highest-leverage 2026-era agentic innovation to adopt: a single LLM grading its own output tends to be overconfident and inconsistent; a second agent whose explicit job is to disprove the first materially reduces both scoring drift and hallucinated justifications, at roughly linear (not exponential) extra inference cost.

### 6.4 Additional Agentic Innovations Worth Building In

- **Tool-using evaluator agents.** Agents should call real compilers, linters, test runners, and cloud provider APIs rather than reasoning over code as plain text — this is what separates a credible "AI Examiner" from a chatbot that merely reads code.
- **AI-generated equivalent assessment forms.** For every published item, an agent generates several scenario-equivalent variants (same competency, different surface facts/names/datasets), which is the single most cost-effective defense against item leakage and answer-sharing.
- **Adaptive scenario generation.** Mid-assessment, the Designer agent can tighten or loosen constraints (time pressure, ambiguous requirements, injected incidents) based on the candidate's demonstrated skill level — the Agentic-era analogue of IRT-based CAT, but for open-ended practical labs, not just MCQs.
- **Meta-evaluation ("evaluator of evaluators").** A supervisory agent periodically samples completed evaluations and checks for score drift, bias by demographic proxy, or systematic disagreement with human graders — closing the loop that keeps the Judge/Critic pair honest over time.
- **Memory-aware Tutor and Interview agents.** Persisting a candidate's prior attempts, weak areas, and remediation history lets the Tutor agent give compounding, personalized guidance instead of resetting to zero context each session.
- **Model routing and confidence-based early exit.** Route cheap/fast models for deterministic or low-ambiguity grading and reserve the most capable models for the Critic/Aggregator stage or for flagged, high-stakes cases — this is what keeps multi-agent inference cost proportional to actual risk.
- **AI-native "engineering with AI" assessment tier.** This is the differentiator most peer platforms have not yet shipped:

| Mode | AI Tools | What Is Measured |
|---|---|---|
| **Closed Book** | Forbidden | Pure unaided knowledge & skill |
| **AI Allowed** | Permitted | Human + AI collaboration competency |
| **AI Engineering** | Required | Prompting, verification, debugging, architecture, hallucination detection, testing, security |

This directly answers the question that will define hiring and certification through 2030: *"Can you engineer effectively with AI?"* — and no competitor in either the Pearson VUE peer group or the HackerRank peer group currently owns this category.

---

## 7. Detailed Technical Architecture

### 7.1 Microservices Topology

```
[ HTTPS / WSS ]
        │
┌───────▼──────────────────────────────────────────┐
│ Ingress / API Gateway (Kong / Envoy)              │
│ JWT, rate-limit, mTLS, WebSocket termination      │
└───────┬──────────────────┬────────────────────────┘
        │                  │
┌───────▼────────┐  ┌──────▼────────────┐  ┌───────▼────────────┐
│ Admissions     │  │ Test Definition   │  │ Candidate Session   │
│ Hook Service   │  │ & Blueprint Svc   │  │ State Service        │
└───────┬────────┘  └──────┬────────────┘  └───────┬────────────┘
        │                  │                       │
        └──────────────────┼───────────────────────┘
                            │
                 ┌──────────▼──────────┐
                 │  Agent Orchestrator │
                 │  (LangGraph/CrewAI) │
                 └──────────┬──────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                   │
   Sandbox Fleet     Integrity Service     Credential/Skills
   (K8s/Firecracker)  (Vision + Behavior)   Graph Service
```

### 7.2 Recommended Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| API Gateway | Kong or Envoy | Mature, mTLS, rate-limiting, WebSocket support |
| Identity | Keycloak (existing) + FingerprintJS + passkeys | Leverages current SSO investment |
| Primary DB | PostgreSQL | Relational integrity + JSONB for rubrics/telemetry |
| Vector Store | pgvector, or dedicated Qdrant/Weaviate | Skills embeddings, challenge retrieval |
| Event Backbone | Kafka or NATS | High-throughput assessment event stream |
| Sandbox Orchestration | Kubernetes + Firecracker/gVisor, or Nomad | Isolation at scale |
| Agent Runtime | Python — FastAPI + LangGraph/CrewAI | Strongest current multi-agent ecosystem |
| Code Execution | Isolated containers, resource quotas, network policies, timeouts | Security-first execution |
| Frontend IDE | Monaco (existing) → progressive enhancement toward full VS Code/Gitpod-style | Continuity of existing UX investment |
| LLM Serving | Existing on-cluster LiteLLM + model routing | Cost control & observability |
| Credentials | Open Badges 3.0 issuer + verifiable-credential library | Interoperability with LMS/ATS ecosystems |
| Standards | QTI 3.0 (items), LTI Advantage (LMS), SCIM (provisioning) | University & enterprise readiness |

### 7.3 Secure Execution Principles

- Candidate code is **never** executed on application servers
- Flow: Job queue → Execution Orchestrator → Isolated Sandbox → Test Runner → Result
- Resource quotas, network isolation, ephemeral filesystems, execution timeouts, syscall restrictions
- Every assessment environment is disposable after grading

### 7.4 Core Event Stream

```
assessment.started        code.executed          skill.updated
question.presented        lab.started             credential.issued
code.submitted             lab.command.executed    admission.updated
test.completed             assessment.completed    integrity.flagged
```

These events drive analytics, real-time dashboards, and Skills Graph updates.

### 7.5 Illustrative Core Data Model (PostgreSQL)

```sql
-- Assessment Blueprints
CREATE TABLE assessment_blueprints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(64) UNIQUE NOT NULL,
  title VARCHAR(255) NOT NULL,
  track_type VARCHAR(32) NOT NULL
    CHECK (track_type IN ('ADMISSIONS_FILTER','CERT_PREP_SIM','ENTERPRISE_BENCHMARK','CODING_LAB')),
  target_role VARCHAR(64),
  time_limit_minutes INT NOT NULL DEFAULT 60,
  rubric_config JSONB NOT NULL,
  adaptive BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Challenge Modules (practical / coding)
CREATE TABLE challenge_modules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  blueprint_id UUID REFERENCES assessment_blueprints(id),
  title VARCHAR(255) NOT NULL,
  problem_spec_markdown TEXT NOT NULL,
  container_image_ref VARCHAR(255) NOT NULL,
  starter_repo_url VARCHAR(512),
  test_suite_repo_url VARCHAR(512),
  resource_limits JSONB DEFAULT '{"cpu":"1.0","memory_mb":1024,"network_egress":false}',
  skill_tags TEXT[]
);

-- Assessment Sessions
CREATE TABLE assessment_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id VARCHAR(128) NOT NULL,
  blueprint_id UUID REFERENCES assessment_blueprints(id),
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  integrity_confidence NUMERIC(5,2),
  identity_score NUMERIC(5,2),
  behavior_score NUMERIC(5,2),
  trust_score NUMERIC(5,2),
  sandbox_endpoint VARCHAR(255),
  session_started_at TIMESTAMPTZ,
  submitted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL
);

-- Multi-Agent Evaluation Reports
CREATE TABLE evaluation_agent_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES assessment_sessions(id) ON DELETE CASCADE,
  agent_type VARCHAR(64) NOT NULL,  -- e.g. 'CODE_EXAMINER', 'CRITIC', 'AGGREGATOR'
  score_awarded NUMERIC(5,2) NOT NULL,
  max_score NUMERIC(5,2) NOT NULL,
  findings_summary TEXT,
  detailed_metrics JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Final Results & Recommendations
CREATE TABLE assessment_final_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID UNIQUE REFERENCES assessment_sessions(id),
  total_score NUMERIC(5,2) NOT NULL,
  performance_band VARCHAR(32),
  recommendation_verdict VARCHAR(64),
  skill_vector JSONB NOT NULL,
  certificate_hash VARCHAR(128),
  webhook_dispatched_at TIMESTAMPTZ
);

-- Skills Graph (simplified)
CREATE TABLE skill_nodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(128) NOT NULL,
  parent_id UUID REFERENCES skill_nodes(id),
  level VARCHAR(32)  -- technology / competency / skill / sub-skill
);

CREATE TABLE candidate_skill_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id VARCHAR(128) NOT NULL,
  skill_id UUID REFERENCES skill_nodes(id),
  proficiency NUMERIC(5,2),
  evidence_type VARCHAR(32),
  evidence_ref UUID,  -- session or lab artifact
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. Proctoring & Integrity Implementation Roadmap

Ordered by value-per-effort, aligned with the EvalOS Proctoring Recommendations:

| Phase | Capability | Effort | Deterrent Value | Notes |
|---|---|---|---|---|
| 1 | Kiosk-mode wrapper (Electron or hardened browser profile) + full-screen/tab-switch detection | Low | High | Highest-leverage first step |
| 1 | Full randomized question draw + order + option shuffle from an expanded bank | Low | High | Extends the existing `generate_exam.py` pattern |
| 2 | Identity verification (ID + selfie match) + device/session binding | Medium | High | Lightweight face-match model is sufficient at this stage |
| 2 | Tightened inactivity-resume (re-auth + fresh selfie) | Low | Medium | Closes the soft-resume integrity gap |
| 3 | AI webcam snapshot monitoring (30–60 s cadence) + flagged-session human review queue | Medium–High | High | Flag-then-human, never auto-fail |
| 4 | Session-anomaly & collusion-detection analytics | Medium | Medium | Post-hoc pattern analysis across cohorts |
| Ongoing | Item-bank growth + AI-generated equivalent-form rotation | Low (recurring) | Medium–High | Core, continuous leakage defense |

All monitoring requires explicit candidate consent, encrypted storage, a defined retention window, and an appeals process compliant with the **Kenya Data Protection Act 2019** (and GDPR where applicable).

---

## 9. Integration Surfaces

| System | Integration Pattern | Purpose |
|---|---|---|
| Admissions Application | Signed webhooks + REST (`CandidateInvited` → `AssessmentCompleted`) | Pre-flight diagnostic → readiness score → programme recommendation |
| i3 AI-Lab | Deep link + bidirectional API + shared sandbox fleet | Practical evidence collection |
| Skillsoft LMS | LTI Advantage (assignment & score exchange) | Assessment as an intelligence layer around the existing LMS |
| External LMS / University Systems | LTI Advantage + QTI 3.0 import/export | Interoperability |
| ATS / HRIS | Webhooks, SCIM, SSO (SAML/OIDC) | Talent-assessment workflow |
| Employers | Skills Passport search + verified competency queries | Talent Exchange |

**Example Admissions Callback Payload**

```json
{
  "event": "ASSESSMENT_COMPLETED",
  "applicant_id": "APP-2026-9812",
  "session_id": "b18d2fa3-5e92-4f3b-9a48-f682d334e12c",
  "results": {
    "total_score": 88.5,
    "performance_band": "PRODUCTION_READY",
    "recommendation": "FAST_TRACK_ADMIT",
    "skill_vector": {
      "code_correctness": 40.0,
      "architecture": 25.0,
      "test_coverage": 13.5,
      "agentic_ai_orchestration": 10.0
    },
    "summary": "Strong mastery of asynchronous patterns and secure parameterization."
  },
  "artifacts": {
    "report_url": "...",
    "code_snapshot_url": "..."
  }
}
```

---

## 10. Phased Implementation Roadmap

### Phase 1 — Foundation & Integrity MVP (3–4 months)
*Goal: close the most critical integrity and leakage gaps while delivering usable multi-modal assessment.*

- Authentication enhancements + device fingerprint binding
- Kiosk-mode wrapper + full-screen/tab-switch/focus detection
- Expanded item bank + true randomized form assembly
- Tightened inactivity-resume behavior
- Candidate management & assessment-builder improvements
- MCQ + coding questions with automated secure code execution
- Basic AI question generation + basic AI grading
- Skills-scoring skeleton
- Candidate and evaluator dashboards
- Core APIs
- Admissions webhook integration (inbound + outbound)
- Initial i3 AI-Lab deep-link for practical challenges

### Phase 2 — Agentic Core & Adaptive Intelligence (4–8 months)

- Full multi-agent evaluation suite (Architect, Adversarial QA, Code Examiner, Tutor, Critic/Aggregator)
- Computer-adaptive testing engine (CAT)
- Practical AI-Lab scenarios with full telemetry
- AI Examiner + AI Interviewer agents
- Certification-readiness engine
- Advanced plagiarism / code-similarity detection
- Integrity/Identity/Behavior/Trust scoring + human review queue
- Digital badges (Open Badges 3.0)
- QTI 3.0 import/export
- LTI Advantage integration
- Skillsoft LMS integration
- Advanced analytics & bias-audit dashboards

### Phase 3 — Platform & Marketplace (9–18 months)

- Complete Skills Graph + Skills Passport
- Workforce Intelligence (organizational skills inventory & gap analysis)
- Employer Talent Exchange
- Assessment Marketplace (third-party authors sell assessments; i3 takes a 20–30% share)
- White-label SaaS offering
- Public Skills API (Assessment-as-a-Service)
- AI Engineering assessment mode (signature, differentiating product)
- Advanced multi-tier simulations
- Multi-language UI (English, French, Swahili, Arabic, Portuguese)
- Offline / low-bandwidth modes + mobile-first diagnostics
- Regional hosting options for data residency

---

## 11. Commercial Model

| Product Surface | Customer | Pricing Model | Notes |
|---|---|---|---|
| Free Diagnostic | Individuals | Free | Customer-acquisition funnel |
| Skills Passport | Individuals | $5–15/month | Premium longitudinal identity |
| CertReady packages | Individuals | $20–100 per certification | Diagnostic + adaptive + labs + mock exam |
| EvalOS Assess (Campus) | Universities | Annual license by student volume | Admissions + coding + labs + analytics |
| Workforce Skills Cloud | Corporates | Per-employee/year or enterprise license | Inventory → gaps → learning → certification |
| Talent Assess | Recruiters / Employers | Per assessment or subscription | Role-specific readiness reports |
| AI-Lab usage | Universities / Corporates | Per learner-hour or annual | Practical evidence generation |
| White-label | Institutions | Annual license | Own branding & domain |
| Skills API | Technology platforms | Usage-based | Assessment infrastructure |
| Assessment Marketplace | Authors | 20–30% revenue share | Network-effect content growth |

**Africa-first design considerations:** offline/low-bandwidth resilience, mobile-first diagnostics, local payment rails (e.g., M-Pesa), multi-language support, regional data residency.

---

## 12. Strategic Moat

Four durable assets competitors cannot easily copy:

1. **Skills Graph** — a proprietary model of how skills relate and how evidence maps to proficiency
2. **Assessment Intelligence** — correlation of platform scores with real-world performance, improving with every evaluation
3. **Practical Evidence** — AI-Lab telemetry of what candidates can actually do under realistic conditions
4. **Longitudinal Skills Passport** — verified skills history that compounds in value over time

```
Learner → Assessment → AI-Lab Evidence → Skills Graph → Certification → Credential → Admissions / Employment
```

A competitor can copy a coding editor or a proctoring widget. They cannot easily replicate this closed loop.

---

## 13. Success Metrics

| Category | Metrics |
|---|---|
| Assessment Quality | Correlation of AI scores with later human review / on-the-job performance |
| Candidate Experience | NPS, completion rates, time-to-feedback |
| Integrity | False-positive / false-negative rates of integrity flags |
| Operational | Cost per evaluation, latency percentiles (p50/p95) |
| Business | Time-to-hire / time-to-admission reduction, diversity metrics, free-to-paid conversion |
| Learning Impact | Pre/post proficiency lift, certification pass-rate improvement |

---

## 14. Risk Register & Mitigations

| Risk | Mitigation |
|---|---|
| Over-intrusive proctoring damages candidate experience | Privacy-preserving, flag-then-human model; explicit consent; clear appeals process |
| LLM scoring drift or bias | Judge/Critic/Aggregator calibration loop, meta-evaluation agent, distribution monitoring, deterministic-first fallback |
| Sandbox escape / code-execution abuse | MicroVM/gVisor isolation, network policies, resource quotas, ephemeral environments |
| Item leakage | AI-generated equivalent forms + continuous bank rotation |
| Regulatory (Kenya DPA / GDPR) | Explicit consent, encryption, retention policies, data-residency options |
| Cost of multi-agent LLM inference | Model routing, caching, confidence-based early exit, deterministic-first pipelines |

---

## 15. Recommended Immediate Next Steps

1. **Approve this architecture** as the north-star for EvalOS's evolution.
2. **Stand up the Phase 1 backlog** — kiosk mode, identity verification, true form randomization, admissions webhooks.
3. **Expand the item bank** and instrument AI-assisted equivalent-form generation.
4. **Prototype the multi-agent evaluation pipeline** on a single practical challenge (e.g., a Kubernetes incident) inside the existing AI-Lab, including the Judge→Critic→Aggregator pattern.
5. **Define the Skills Graph schema** and begin mapping existing exam topics into it.
6. **Run a legal/privacy review** of the proposed consent, retention, and monitoring practices under the Kenya Data Protection Act 2019.

---

## 16. Closing Statement

EvalOS should not be positioned as "AI generates coding tests" — that capability will be commoditized within the next product cycle. It should be positioned as:

> **AI-powered Skills Verification Infrastructure** — the operating system for skills assessment, practical learning, and verified digital credentials.

By combining the integrity standards of high-stakes certification networks, the realism and scale of modern developer-screening platforms, the psychometric rigor of enterprise talent measurement, and the compounding power of Agentic AI — all tightly coupled to i3's existing AI-Lab, LMS, and admissions ecosystem — i3 Technologies can build a platform that is simultaneously more effective, more candidate-friendly, and more commercially defensible than any single peer group in the current market.

**This is the commercial and technical opportunity.**

---

*Prepared by synthesis of: Global Professional Exam & Assessment Platforms Report · EvalOS Technical Implementation Document (ARCH-EVALOS-2026-V1) · Senior Principal Architect Blueprint · EvalOS Proctoring Recommendations · EvalOS User Guide v2*
*i3 Technologies — Confidential · © 2026*
