# PROJECT AURORA: Modern Enterprise Learning Platform
## Technical Specifications & Implementation Guide
**Modernisation of IBM Kenexa LCMS v8.2 & Moodle into an Agentic AI-Powered, Cloud-Native LMS/LXP/CMS Platform**

---

| Metadata | Value |
| :--- | :--- |
| **Document Type** | Comprehensive Technical Specification & Implementation Blueprint |
| **Document Class** | Enterprise Architecture & Delivery Masterplan |
| **Version** | 1.0.0-FINAL |
| **Status** | Approved for Architecture Board & Engineering Execution |
| **Date** | September 2026 |
| **Target Audience** | Executive Sponsors, Chief Architects, Lead Engineers, EdTech Product Leads, Security & Compliance Officers |

---

## Executive Summary & Strategic Vision

### Executive Summary
Project **AURORA** represents the strategic modernization of a legacy learning technology estate comprised of **IBM Kenexa LCMS v8.2** (a legacy, Windows Server-based, SCORM-centric LCMS) and self-hosted **Moodle** instances. The objective is to replace these fragmented systems with a unified, API-first, cloud-native, multi-tenant Learning Management System (LMS), Learning Experience Platform (LXP), and Content Management System (CMS) powered by an **Agentic AI Layer**.

AURORA is designed to support two GTM motions:
1. **Managed Lease Model (Dedicated/Isolated Tenancy):** For Tier-1 Universities, TVET systems, and government tertiary networks requiring custom branding, sovereign cloud hosting, or isolated compute/storage tiers.
2. **Multi-Tenant SaaS Model (Shared Tenancy):** For mid-tier colleges, private training providers, and corporate academies under tiered subscriptions (Starter, Professional, Enterprise).

```
+---------------------------------------------------------------------------------------------------+
|                                      PROJECT AURORA PLATFORM                                      |
|                                                                                                   |
|   +-----------------------+     +-----------------------+     +-------------------------------+   |
|   |    LMS (Core)         |     |    LXP (Experience)   |     |    CMS (Authoring & Assets)  |   |
|   |  - Academic Admin     |     |  - Adaptive Pathways  |     |  - Block Authoring Studio     |   |
|   |  - Gradebook & SIS    |     |  - Skills Ontology    |     |  - Asset Pipeline (HLS)       |   |
|   |  - Formal Assessment  |     |  - Social & Badging   |     |  - Reusable Learning Objects  |   |
|   +-----------------------+     +-----------------------+     +-------------------------------+   |
|                                                                                                   |
|   +-------------------------------------------------------------------------------------------+   |
|   |                          AGENTIC AI FABRIC (Orchestrator & RAG)                           |   |
|   |    - AI Tutor    - Course Designer    - Assessment Agent    - Administrative Copilot    |   |
|   +-------------------------------------------------------------------------------------------+   |
|                                                                                                   |
|   +-------------------------------------------------------------------------------------------+   |
|   |                   MULTI-TENANT FOUNDATION & STANDARDS INTEROPERABILITY                    |   |
|   |    - LTI 1.3 / Advantage    - xAPI 2.0 / LRS    - OneRoster 1.2    - Open Badges 3.0       |   |
|   +-------------------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------------------+
```

### Modernisation Principles
* **API-First & Event-Driven:** All system capabilities are exposed via RESTful OpenAPI, GraphQL, and async domain events (Kafka/Pulsar).
* **Agentic AI by Design, Governed by Policy:** Autonomous AI agents execute bounded workflows (tutoring, item generation, retention analysis) behind strict human-in-the-loop controls, permission checks, and immutable audit logs.
* **Strict Tenant Isolation:** Logical data isolation by default (Row-Level Security) with seamless elasticity to dedicated schema or dedicated Kubernetes cluster deployments.
* **Zero Content Loss Strategy:** Automated extraction, conversion, and metadata enrichment pipeline for legacy Kenexa learning objects and Moodle courses.
* **Global Compliance & Accessibility:** Built-in compliance with POPIA, GDPR, FERPA, and strict WCAG 2.2 AA accessibility standard.

---

## Current-State Analysis & Decommissioning Strategy

### Legacy System Comparison Matrix

| Metric / Dimension | IBM Kenexa LCMS v8.2 (Windows) | Moodle (Self-Hosted) | AURORA Target State |
| :--- | :--- | :--- | :--- |
| **Architecture** | Monolithic 3-Tier (IIS, Java Servlets, MS SQL) | Monolithic LAMP (PHP / MySQL / PostgreSQL) | Cloud-Native Microservices / Event-Driven |
| **Multi-Tenancy** | Single-tenant per IIS installation | Weak (Course/Category hacks or Moodle Workplace) | Built-in 4-tier tenancy (Shared Pool to Cluster Isolation) |
| **Content Model** | SCORM 1.2/2004, Reusable Learning Objects (RLO) | Course-bound activities & files | Granular HTML5/JSON Block Objects + xAPI + cmi5 |
| **AI Capabilities** | None | Third-party community plugins (un-governed) | Native Agentic AI Fabric with RAG & Guardrails |
| **Scalability** | Vertical hardware scaling (High Cost) | Vertical / Complex Cluster (Stateful PHP session issues) | Horizontal Pod Autoscaling (Kubernetes & Serverless) |
| **Analytics** | Basic SCORM runtime tables | Standard activity logs | Real-time xAPI LRS + Data Lakehouse (Trino / Iceberg) |
| **Interoperability** | Legacy SCORM, AICC | SCORM, LTI 1.1/1.3, Basic Web Services | LTI 1.3 Advantage, OneRoster 1.2, QTI 3.0, Open Badges 3.0 |

### Decommissioning Strategy
1. **Freeze Phase (Month 6):** Freeze schema and core authoring on Kenexa LCMS. Direct all new content creation to AURORA CMS.
2. **Migration Extraction Phase (Months 6–9):** Execute automated migration scripts to extract objects from MS SQL Server (Kenexa) and MySQL/PostgreSQL (Moodle).
3. **Read-Only Coexistence (Months 9–18):** Modernized courses operate on AURORA; legacy systems transition to read-only state for transcript verification and historical compliance.
4. **Complete Cutover & Decommissioning (Month 18):** Final database backup, secure offsite archival, shutdown of Windows IIS / Kenexa infrastructure, and Moodle compute instances.

---

## Enterprise Target-State System Architecture

### Multi-Tenant System Architecture Diagram

```
[ Client Layer ]
   ├── Web Application (React / Next.js) [PWA]
   ├── Mobile App (React Native - iOS / Android)
   └── External Tool Consumers (LTI 1.3 Advantage Clients)
           │
           ▼
[ Security & Traffic Management ]
   ├── Cloudflare Enterprise (DDoS, WAF, Global CDN)
   └── API Gateway (Kong / Envoy with OIDC Auth & Rate Limiting)
           │
           ├──► [ Auth & Tenant Context Handler ] ──► Keycloak / Entra ID
           │
           ▼
[ Domain Microservices Layer (Kubernetes / EKS / GKE) ]
   ├── Identity & Tenant Service      ├── Course & Curriculum Engine
   ├── Content Management Studio      ├── Assessment & Grading Engine
   ├── LXP & Personalization Engine   ├── Competency & Skills Graph
   └── Integration & LTI Service      └── Analytics & Reporting Engine
           │                                   │
           ▼                                   ▼
[ Agentic AI Fabric ]                   [ Async Messaging Bus ]
   ├── AI Agent Runtime (LangGraph)        ├── Apache Kafka / Apache Pulsar
   ├── Model Gateway (LiteLLM)             └── Event Router & Dead-Letter Queue
   └── Vector Search & RAG (pgvector)          │
                                               ▼
[ Data Storage Tier ]                   [ Analytics & LRS ]
   ├── Operational DB: PostgreSQL          ├── Learning Record Store (xAPI 2.0)
   ├── Hot Cache: Redis Enterprise Cluster └── Data Lakehouse: Apache Iceberg / S3
   └── Asset Store: AWS S3 / Azure Blob
```

### Multi-Tenancy Models

AURORA implements four tenancy isolation tiers configured via single control plane metadata:

```
+----------------------------------------------------------------------------------------------------+
|                                    AURORA TENANCY TIERS                                            |
+-------------------+--------------------+-----------------------+-----------------------------------+
| Tier              | Database Strategy  | Compute Strategy      | Target Audience                   |
+-------------------+--------------------+-----------------------+-----------------------------------+
| 1. Starter        | Shared Database,   | Shared K8s Pods       | Small Colleges / Training Hubs    |
|                   | Shared Schema (RLS)|                       |                                   |
| 2. Professional   | Shared Database,   | Shared K8s Pods       | Mid-sized TVETs & Academies       |
|                   | Tenant Schema      |                       |                                   |
| 3. Enterprise     | Dedicated Database | Shared / Dedicated    | Large Universities                |
|                   | Instance           | Node Groups           |                                   |
| 4. Sovereign Lease| Dedicated Database | Fully Isolated        | Government Institutions /         |
|                   | Instance           | K8s Cluster / VPC     | Defence Academies                 |
+-------------------+--------------------+-----------------------+-----------------------------------+
```

#### Database Tenant Isolation Implementation Strategy (PostgreSQL Row-Level Security)
For shared schema tenants, row-level isolation is enforced strictly at the database layer to eliminate cross-tenant data leaks:

```sql
-- Enable Row Level Security on Core Table
ALTER TABLE aurora_learning.course_enrolments ENABLE ROW LEVEL SECURITY;

-- Create Application Tenant Policy
CREATE POLICY tenant_isolation_policy ON aurora_learning.course_enrolments
    AS RESTRICTIVE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
```

---

## Agentic AI Fabric & Governance

### Agentic AI Capability Matrix

```
+--------------------------------------------------------------------------------------------------+
|                                    AGENTIC AI FABRIC MAP                                         |
+---------------------+-----------------------------------+----------------------------------------+
| Agent Name          | Primary Objective                 | Permitted Tools & Scopes               |
+---------------------+-----------------------------------+----------------------------------------+
| Learner Success     | Hyper-personalized tutoring,      | Read: Enrolments, Progress, RAG Docs   |
| Agent               | socratic guidance, study plans    | Write: Study Plan, Reminders           |
|                     |                                   | Prohibited: Direct Answer on High-     |
|                     |                                   | Stake Exams                            |
+---------------------+-----------------------------------+----------------------------------------+
| Course Design       | Generates course outlines, draft  | Read: Curriculum Standards, RLO Studio |
| Agent               | modules, H5P interactive items    | Write: Draft Content Blocks            |
|                     |                                   | Approval Gate: Educator Publish Action |
+---------------------+-----------------------------------+----------------------------------------+
| Assessment &        | Item generation, distractor       | Read: Question Banks, Bloom's Taxonomy |
| Feedback Agent      | analysis, rubric-based feedback   | Write: Draft Items, Suggested Rubrics  |
|                     | suggestions                       | Approval Gate: Grade Commit Override   |
+---------------------+-----------------------------------+----------------------------------------+
| Academic Ops        | Automates cohort assignment,      | Read: SIS Sync, Attendance Logs        |
| Agent               | flag at-risk learners             | Write: At-risk Notifications, Action   |
|                     |                                   | Escalation                             |
+---------------------+-----------------------------------+----------------------------------------+
```

### AI Technical Architecture & RAG Pipeline

```
[ Student / Educator Query ]
             │
             ▼
[ Model Gateway (LiteLLM & Guardrails) ]
   ├── Input Guardrails (Prompt Injection Filter, PII Anonymizer)
   └── Rate & Cost Controller (Token Bucket / Tenant Meter)
             │
             ▼
[ Agent Orchestrator (LangGraph State Machine) ]
   ├── Context Manager (Session Memory + Learner Profile)
   └── Tool Execution Engine
             │
             ├──► [ Vector Search / Retrieval Engine ]
             │       ├── Tenant Query Filter (`tenant_id = X`)
             │       └── Hybrid Search (Dense Pgvector + Sparse BM25)
             │
             └──► [ Policy Engine & Human Checkpoint ]
                     ├── Check Action Scope (Read / Draft / Commit)
                     └── Request Educator Review (If High Confidence Required)
             │
             ▼
[ Model Execution (Claude 3.5 Sonnet / Llama 3 Enterprise / GPT-4o) ]
             │
             ▼
[ Output Guardrail ]
   ├── Hallucination Check (Grounding Verification)
   ├── Citation Injector & Schema Validator
   └── Immutable Event Audit Logged to Kafka
```

---

## Functional Specifications by Domain

### 1. LMS Core (System of Record)
* **Academic Hierarchy:** Flexible mapping of Institution $\rightarrow$ Campus $\rightarrow$ Faculty $\rightarrow$ Department $\rightarrow$ Programme $\rightarrow$ Course $\rightarrow$ Module $\rightarrow$ Activity.
* **Enrolment Management:** Rules-based automatic enrolments, SIS sync (OneRoster/REST), waitlists, prerequisite checking, cohort grouping.
* **Advanced Gradebook:** Weighted grade aggregation, rubric grading, double-blind marking, grade override audit trails, release schedules.
* **Assessment Engine:** Support for 20+ item types, dynamic question pooling, randomisation, secure exam browser integration, accommodations engine (time multiplier, assistive flags).

### 2. LXP Experience Layer (System of Engagement)
* **Adaptive Learning Paths:** AI-driven path selection based on initial diagnostic assessment, current skills gaps, and career track objectives.
* **Skills Graph & Framework Mapping:** Mapping activities and modules to regional and global competency frameworks (e.g., SFIA, ESCO).
* **Social & Community Hub:** Cohort discussion spaces, peer-to-peer study group formation, mentor matching, interactive social feeds.
* **Verifiable Credentials:** Native issuance of Open Badges 3.0 and W3C Verifiable Credentials for micro-credentials and formal certificates.

### 3. CMS & Authoring Studio (Modern LCMS)
* **Block-Based Content Editor:** Modular, block-structured authoring (Notion/Gutenberg style) supporting nested text, media, interactive H5P objects, and dynamic code sandboxes.
* **Asset Pipeline:** Automated ingestion, virus scanning, multi-bitrate HLS video transcoding, automated AI caption generation (Whisper), CDN distribution.
* **Granular Object Reuse:** Learning Objects managed as independent entities with global versioning, branching, and impact analysis (tracing where objects are used across courses).

---

## Technical Architecture & Recommended Technology Stack

### Recommended Technology Blueprint

```
+----------------------------------------------------------------------------------------------------+
|                                    RECOMMENDED TECH STACK                                          |
+-------------------+----------------------------------+---------------------------------------------+
| Layer             | Selected Technology              | Justification                               |
+-------------------+----------------------------------+---------------------------------------------+
| Front-End Web     | Next.js 15+ (React 19),          | Server-Side Rendering (SSR) for speed,      |
|                   | TypeScript, Tailwind CSS         | robust PWA offline support, WCAG compliance |
| Front-End Mobile  | React Native (Expo)              | Cross-platform parity, offline storage sync |
| API Gateway       | Kong API Gateway / Envoy         | Enterprise traffic management, rate limits |
| Core Services     | Java 21 (Spring Boot 3.3) OR     | Production-grade performance, typing,       |
|                   | Node.js (NestJS)                 | modular dependency structures               |
| Agent Orchestrator| Python 3.12 (LangGraph / FastAPI)| Leading ecosystem for AI agent tool-use     |
| Main Database     | PostgreSQL 16+ with pgvector     | Enterprise relational consistency + vector  |
| Event Streaming   | Apache Kafka / Apache Pulsar     | Event sourcing, xAPI streaming at scale    |
| Cache & Session   | Redis Enterprise Cluster         | In-memory caching, rate-limiting counters   |
| Search Engine     | OpenSearch 2.12+                 | High-performance catalog & document search  |
| Object Storage    | AWS S3 / MinIO (On-Prem Lease)   | Scalable blob storage for video and SCORM   |
| Observability     | OpenTelemetry, Prometheus, Grafana| Standardised metrics, tracing, and logging  |
+-------------------+----------------------------------+---------------------------------------------+
```

---

## Interoperability, Integration & Data Standards

### Standards Implementation Matrix

```
+--------------------------------------------------------------------------------------------------+
|                                  INTEROPERABILITY STANDARDS                                      |
+--------------------+---------------------+-------------------------------------------------------+
| Standard           | Specification Level | Implementation Scope                                  |
+--------------------+---------------------+-------------------------------------------------------+
| LTI 1.3 / Advantage| IMS / 1EdTech       | Core LTI, Assignment & Grade Services (AGS),          |
|                    | Certified           | Names & Role Provisioning (NRPS), Deep Linking        |
+--------------------+---------------------+-------------------------------------------------------+
| xAPI / cmi5        | IEEE 9274.1.1-2023  | Embedded LRS capturing all learner interaction        |
|                    |                     | events across Web, Mobile, and External Tools         |
+--------------------+---------------------+-------------------------------------------------------+
| OneRoster          | v1.2 REST & CSV     | SIS roster integration for automated user, course,    |
|                    |                     | and enrolment synchronization                         |
+--------------------+---------------------+-------------------------------------------------------+
| QTI                | v3.0 Specification  | Interoperable export and import of assessment items   |
|                    |                     | and question banks                                    |
+--------------------+---------------------+-------------------------------------------------------+
| Open Badges        | v3.0 (1EdTech)      | Digital credential issuance, verifiable cryptographically|
+--------------------+---------------------+-------------------------------------------------------+
```

---

## Data Migration Strategy (Kenexa LCMS & Moodle)

### Migration Pipeline Architecture

```
[ Source Systems ]
   ├── IBM Kenexa LCMS v8.2 (MS SQL Server + SCORM Zip Store)
   └── Moodle Instance (MySQL/PostgreSQL + moodledata directory)
           │
           ▼
[ Phase 1: Staging & Extraction (ETL Runner) ]
   ├── Raw Extraction to Parquet Files on Migration Storage
   └── Preserve Original IDs, Foreign Keys, and Audit Hashes
           │
           ▼
[ Phase 2: Transformation Engine ]
   ├── Metadata Normalization & Taxonomy Enrichment Engine
   ├── AI Metadata Enrichment (Auto-tagging, Bloom's Level Extraction)
   ├── SCORM Hydrator (Extract SCORM XML -> HTML5 / JSON Blocks)
   └── Moodle Quiz XML -> QTI 3.0 / AURORA Native JSON Converter
           │
           ▼
[ Phase 3: Reconciliation & Dry Run ]
   ├── Integrity Validator (Checksum, Enrolment Counts, Grade Matching)
   └── Automated Migration Test Suite Executed
           │
           ▼
[ Phase 4: Production Loading ]
   └── High-Throughput Loaders -> AURORA Production Database / S3 Store
```

### Legacy Data Migration Mapping

| Legacy Source | Source Structure | Target AURORA Model | Transformation Logic |
| :--- | :--- | :--- | :--- |
| **Kenexa LCMS** | `LCMS_CONTENT_OBJECT` | `aurora_cms.learning_objects` | Extract XML/HTML, strip IE-era scripts, wrap in modern responsive HTML5 container, generate embeddings. |
| **Kenexa LCMS** | SCORM Packages (.zip) | `aurora_cms.packages` / Native RLO | Unpack, parse manifest, convert static slides to CMS blocks; fallback to cmi5 player wrapper if complex JS runtime. |
| **Moodle** | `mdl_course` / `mdl_course_modules` | `aurora_lms.courses` / `aurora_lms.modules` | Map Moodle sections to AURORA structured modules; re-link activity parameters. |
| **Moodle** | `mdl_quiz` / `mdl_question` | `aurora_assessment.question_banks` | Map Moodle question types (multichoice, shortanswer, match) to QTI 3.0 JSON schemas. |
| **Moodle** | `mdl_grade_grades` | `aurora_lms.historical_transcripts` | Immutable historical transcript store with original audit dates preserved. |

---

## Non-Functional Requirements (NFRs) & SLA Commitments

```
+----------------------------------------------------------------------------------------------------+
|                                    NON-FUNCTIONAL REQUIREMENTS                                     |
+-------------------+--------------------------------------------------------------------------------+
| Metric            | Target Specification                                                           |
+-------------------+--------------------------------------------------------------------------------+
| Availability SLA  | 99.9% Uptime (Shared SaaS), 99.95% Uptime (Dedicated Enterprise / Lease)       |
| Latency Targets   | API p95 < 200ms; Page load p95 < 1.5s; RAG Query response p95 < 2.5s            |
| Concurrency Scale | 2,000,000 Total Active Learners; 150,000 Peak Concurrent Active Users          |
| Disaster Recovery | Recovery Point Objective (RPO) <= 15 min; Recovery Time Objective (RTO) <= 1 hour|
| Security & Auth   | TLS 1.3 in transit, AES-256-GCM at rest; SAML 2.0 / OIDC / MFA enforced      |
| Accessibility     | Strict WCAG 2.2 Level AA Conformance across all learner and educator views     |
+-------------------+--------------------------------------------------------------------------------+
```

---

## Implementation Roadmap & Governance

### 24-Month Phased Roadmap

```
+---------------------------------------------------------------------------------------------------+
| 24-MONTH IMPLEMENTATION TIMELINE                                                                  |
+---------------------------------------------------------------------------------------------------+
| Phase 1: Foundation & Core Platform (Months 1–6)                                                  |
| [M1-M2] Discovery & Infrastructure Setup                                                          |
| [M3-M5] LMS Core Development (Auth, Course Model, Assessment Engine, Gradebook)                   |
| [M6]     Multi-Tenant Foundation & Initial Sandbox Deployment                                    |
+---------------------------------------------------------------------------------------------------+
| Phase 2: LXP, CMS & Agentic AI Layer (Months 7–12)                                                |
| [M7-M8] Modern Authoring Studio (CMS) & Media Pipeline Integration                                |
| [M9-M10] LXP Recommendation Engine, Skills Graph & Badging                                         |
| [M11-M12] Agentic AI Fabric Execution (AI Tutor, Course Assistant, Guardrails)                    |
| ** MILESTONE: SaaS Beta Release & First Tenant Onboarded (Month 9) **                              |
+---------------------------------------------------------------------------------------------------+
| Phase 3: Migration Factory & Interoperability (Months 13–18)                                       |
| [M13-M15] Migration Factory Execution (Kenexa LCMS & Moodle Extraction)                            |
| [M16-M17] LTI 1.3 Advantage, OneRoster & SIS Connectors Production Validation                      |
| [M18]     Parallel Running & Dual-System Validation                                               |
| ** MILESTONE: Legacy Kenexa & Moodle Systems Decommissioned (Month 18) **                         |
+---------------------------------------------------------------------------------------------------+
| Phase 4: Full Scale & GTM Expansion (Months 19–24)                                                |
| [M19-M21] Advanced AI Capabilities (Predictive Retention, Autonomous Course QA)                  |
| [M22-M24] Scale Hardening, Multi-Region Deployment, SOC 2 Type II & ISO 27001 Certification       |
| ** MILESTONE: SaaS General Availability & Multi-Region GTM (Month 24) **                           |
+---------------------------------------------------------------------------------------------------+
```

### Governance RACI Matrix

```
+--------------------------------------------------------------------------------------------------+
|                                      PROGRAMME RACI MATRIX                                       |
+-----------------------------------+--------+------------+------------+---------------+-----------+
| Deliverable / Task                | Exec   | Lead       | Dev Team   | Security &    | Migration |
|                                   | Sponsor| Architect  |            | Compliance    | Team      |
+-----------------------------------+--------+------------+------------+---------------+-----------+
| Target Architecture & Design      | I      | A / R      | C          | C             | I         |
| Core SaaS Platform Development    | I      | A          | R          | C             | I         |
| Agentic AI Implementation         | I      | A          | R          | C             | I         |
| Data Migration Engine             | I      | A          | C          | C             | A / R     |
| Security & Privacy Approval       | I      | C          | I          | A / R         | I         |
| Final Cutover & Decommissioning   | A      | C          | R          | C             | R         |
+-----------------------------------+--------+------------+------------+---------------+-----------+
```
*(Legend: R = Responsible, A = Accountable, C = Consulted, I = Informed)*

---

## Commercial Model & Operational Cost Framework

### SaaS Tiering & Leasing Structure

```
+---------------------------------------------------------------------------------------------------+
|                                 COMMERCIAL LEASING & SAAS TIERS                                   |
+--------------------+-----------------------+-----------------------+------------------------------+
| Dimension          | Starter Plan          | Professional Plan     | Enterprise / Managed Lease   |
+--------------------+-----------------------+-----------------------+------------------------------+
| Target Customer    | Small Academies       | Mid-Size TVETs        | Large Universities & Gov     |
| Active Learners    | Up to 2,500           | Up to 15,000          | 15,000+ (Unlimited Tiers)    |
| Tenancy Isolation  | Shared DB (RLS)       | Dedicated Schema      | Dedicated Cluster / VPC      |
| Custom Branding    | Standard Theme        | Full White-Label      | Custom Domain & PWA Build    |
| AI Agent Allocation| 10,000 Credits/mo     | 100,000 Credits/mo    | Custom Metered / Self-Hosted |
| Support Level      | Standard Email        | 8x5 Priority Escalation| 24x7 Dedicated SRE & CSM     |
+--------------------+-----------------------+-----------------------+------------------------------+
```

---

## Risk Register & Mitigation Controls

```
+--------------------------------------------------------------------------------------------------+
|                                     RISK MITIGATION MATRIX                                       |
+----------------------+--------+------------------------------------------------------------------+
| Risk Description     | Level  | Mitigation Action / Control                                      |
+----------------------+--------+------------------------------------------------------------------+
| AI Hallucination &   | High   | Enforce strict RAG grounding with source attribution. Prompt     |
| Academic Inaccuracy  |        | output validation layers block ungrounded statements.            |
|                      |        | Require Human-in-the-Loop approval for high-stakes assessment.   |
+----------------------+--------+------------------------------------------------------------------+
| Legacy Kenexa Data   | High   | Implement a staging extraction pipeline with automated structural|
| Corruption/Unstructured|      | cleanups. Use AI-assisted metadata taggers paired with manual    |
| Metadata             |        | sample verification by Instructional Designers.                 |
+----------------------+--------+------------------------------------------------------------------+
| Cross-Tenant Data    | Critical| Database Row-Level Security (RLS) enforced natively at the DB    |
| Leakage              |        | driver level. Automated daily multi-tenant isolation integration |
|                      |        | security tests in CI/CD pipeline.                               |
+----------------------+--------+------------------------------------------------------------------+
| Performance Degradation| Medium| Distributed event streaming (Kafka) decouples analytical write   |
| During Peak Exams    |        | workloads. Horizontal Pod Autoscaling (HPA) triggers on CPU/     |
|                      |        | Memory and queue depth thresholds.                               |
+----------------------+--------+------------------------------------------------------------------+
```

---

## Key Performance Indicators (KPIs) & Success Metrics

To ensure Project AURORA delivers on its strategic and technical objectives, system performance will be evaluated against six core metric dimensions:

```
+---------------------------------------------------------------------------------------------------+
|                                  SUCCESS METRICS & TARGET KPIS                                    |
+---------------------------+-----------------------------------+-----------------------------------+
| Metric Dimension          | Target Indicator                  | Evaluation Frequency              |
+---------------------------+-----------------------------------+-----------------------------------+
| Content Migration         | 100% Migration of Active Learning | Monthly during Migration Phase    |
| Integrity                 | Assets with Zero Integrity Loss   |                                   |
+---------------------------+-----------------------------------+-----------------------------------+
| System Reliability        | >= 99.9% Uptime;                  | Real-Time Observability (Grafana) |
|                           | API Latency p95 < 200ms           |                                   |
+---------------------------+-----------------------------------+-----------------------------------+
| AI Agent Grounding        | < 0.1% Un-grounded Response       | Continuous Automated Golden-Set   |
| Accuracy                  | Rate on Course Content Queries    | Evaluation                        |
+---------------------------+-----------------------------------+-----------------------------------+
| User Engagement           | >= 35% Increase in Student Daily  | Monthly Product Analytics         |
|                           | Active Usage vs. Legacy Moodle    |                                   |
+---------------------------+-----------------------------------+-----------------------------------+
| Cost Efficiency           | >= 40% Reduction in Infrastructure| Quarterly Financial Review        |
|                           | Operating Cost per Active Learner |                                   |
+---------------------------+-----------------------------------+-----------------------------------+
| Accessibility Compliance  | 100% WCAG 2.2 AA Automated &      | Per-Release Build Gate            |
|                           | Manual Audit Pass Rate            |                                   |
+---------------------------+-----------------------------------+-----------------------------------+
```

---

## Conclusion & Actionable Next Steps

The legacy estate consisting of **IBM Kenexa LCMS v8.2** and self-hosted **Moodle** cannot meet the needs of modern tertiary education nor can it support a profitable multi-tenant SaaS business model. Rebuilding from the ground up as a cloud-native, API-first platform with an integrated **Agentic AI Layer** secures long-term market differentiation.

### Immediate Action Plan (30-60-90 Days)
1. **Days 1–30:** Formally sign off on the Architecture Blueprint, establish the Infrastructure-as-Code foundation, and deploy the Kubernetes development cluster.
2. **Days 31–60:** Complete the Data Extraction dry-run from the legacy IBM Kenexa LCMS MS SQL database and establish the canonical content model schemas.
3. **Days 61–90:** Build the Core Tenant Management Service and API Gateway, paving the way for the Phase 1 LMS Core sprint.