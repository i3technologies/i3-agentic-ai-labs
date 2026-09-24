# EvalOS Platform — Administrator Guide

> **Document ID:** ARCH-EVALOS-2026-V2  
> **Prepared for:** i3 Technologies Limited — EvalOS Platform Engineering  
> **Scope:** Phases 1, 2, and 3 Implementation  
> **Status:** Implementation-Ready

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Administrator Roles](#2-administrator-roles)
3. [Database Migrations](#3-database-migrations)
4. [Environment Variables](#4-environment-variables)
5. [Integrity Review Queue](#5-integrity-review-queue)
6. [Analytics & Bias Audit](#6-analytics--bias-audit)
7. [Digital Badges (Open Badges 3.0)](#7-digital-badges-open-badges-30)
8. [Multi-Agent Evaluation Pipeline](#8-multi-agent-evaluation-pipeline)
9. [Assessment Marketplace](#9-assessment-marketplace)
10. [Integration Reference](#10-integration-reference)
11. [Hard Constraints Compliance](#11-hard-constraints-compliance)
12. [API Quick Reference](#12-api-quick-reference)

---

## 1. Platform Overview

EvalOS is i3's **AI-Native Skills Verification Infrastructure** — the operating system for assessment, practical evidence, verified credentials, and workforce analytics. Deployed on IBM ROKS / OpenShift.

### Product Surfaces

| Product | Description | Phase |
|---|---|---|
| EvalOS Assess™ | MCQ, coding, and multi-modal assessment engine | P1 |
| EvalOS Lab™ | Practical cloud lab sandboxes | P1 |
| EvalOS CertReady™ | Certification-readiness diagnostics | P2 |
| EvalOS Interview AI™ | Agentic behavioral & technical interviewing | P1 |
| EvalOS Passport™ | Verifiable longitudinal skills identity | P3 |
| EvalOS Talent™ | Employer-facing skills assessment | P3 |
| EvalOS Marketplace™ | Third-party assessment marketplace | P3 |
| EvalOS API™ | Assessment-as-a-Service public API | P3 |

### The Skills Loop

```
ASSESS → PRACTICE → SIMULATE → CERTIFY → VERIFY → EMPLOY → UPSKILL
```

---

## 2. Administrator Roles

### Keycloak Realm Roles

| Role | Access Level | Notes |
|---|---|---|
| `i3-admin` | Full admin — all API routes, integrity review, analytics, badge issuance | Assign only to platform admins |
| `evalos-author` | Question bank, exam builder, marketplace listings creation | Content authors |
| `evalos-proctor` | Read-only integrity flag queue; can clear/void flagged sessions | Proctoring staff |
| *(none)* | Candidate — exam, study coach, interview, lab access only | Default role |

The `isAdmin` session flag is `true` when the JWT contains the `i3-admin` realm role. All admin API routes check via `session.user.isAdmin`.

---

## 3. Database Migrations

All migrations live in `platform/evalos/web/migrations/`. Apply in sequence — each is idempotent (`IF NOT EXISTS`).

| File | Phase | Contents |
|---|---|---|
| `003_ai_features.sql` | Existing | AI interview evaluations, question AI-generated flag |
| `004_interview_questions_seed.sql` | Existing | Interview question seed data |
| `005_add_tenant_id.sql` | HC-4 | `tenant_id` + RLS on all core tables |
| `006_assessment_blueprints_skills_graph.sql` | Phase 1 | Assessment blueprints, challenge modules, `skill_nodes`, `candidate_skill_evidence` |
| `007_integrity_scoring.sql` | Phase 1 | Integrity columns on `quiz_attempts`, `integrity_events`, `evaluation_agent_reports`, `assessment_final_results`, `admissions_webhook_log` |
| `008_cat_engine.sql` | Phase 2 | IRT parameters (3PL), `cat_sessions`, `cat_item_responses` |
| `009_digital_badges.sql` | Phase 2 | `badge_classes` (OB3), `credential_issuances`, `cert_readiness_scores` |
| `010_platform_marketplace.sql` | Phase 3 | `skills_passports`, `org_skills`, `marketplace_listings`, `marketplace_purchases`, `ai_engineering_sessions` |

### Applying Migrations

```bash
# Apply all Phase 1–3 migrations in order:
psql "$DATABASE_URL" -f migrations/006_assessment_blueprints_skills_graph.sql
psql "$DATABASE_URL" -f migrations/007_integrity_scoring.sql
psql "$DATABASE_URL" -f migrations/008_cat_engine.sql
psql "$DATABASE_URL" -f migrations/009_digital_badges.sql
psql "$DATABASE_URL" -f migrations/010_platform_marketplace.sql
```

> **Warning:** Always apply in numeric order. Each migration depends on tables from the previous one.

---

## 4. Environment Variables

### Core (all phases)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ Required | Crunchy Postgres connection string with `sslmode=verify-full` |
| `PG_CA_CERT_PATH` | ✅ Required | Path to Crunchy CA certificate file |
| `KEYCLOAK_ISSUER` | ✅ Required | `https://sso.i3technologies.co.ke/realms/i3` |
| `KEYCLOAK_CLIENT_ID` | ✅ Required | EvalOS public OIDC client ID |
| `NEXTAUTH_SECRET` | ✅ Required | 32-byte random session secret (`openssl rand -hex 32`) |
| `LITELLM_URL` | ✅ Required | LiteLLM proxy URL (cluster-internal) |
| `LITELLM_KEY` | ✅ Required | LiteLLM API key |

### Phase 1 Additions

| Variable | Description |
|---|---|
| `ADMISSIONS_WEBHOOK_URL` | Outbound `ASSESSMENT_COMPLETED` dispatch URL |
| `ADMISSIONS_WEBHOOK_SECRET` | HMAC-SHA256 secret for webhook signing (`openssl rand -hex 32`) |

### Phase 2 Additions

| Variable | Description |
|---|---|
| `LTI_HMAC_SECRET` | HMAC secret for LTI Advantage launch validation |
| `LTI_PLATFORM_ISSUER` | Registered LMS issuer URL |

---

## 5. Integrity Review Queue

EvalOS uses a **flag-then-human model** — no attempt is automatically failed. All anomalies surface to the human review queue.

### 5.1 Four Integrity Scores

| Score | What it Measures | Auto-flag threshold |
|---|---|---|
| **Identity Score** | Confidence the person is who they claim (device fingerprint, session binding) | < 65 |
| **Behavior Score** | Deviation from expected interaction patterns (focus loss, tab switches, fullscreen exits) | < 60 |
| **Integrity Confidence** | Copy/paste frequency, AI-content likelihood, keystroke entropy | < 60 |
| **Trust Score** | Weighted composite (Identity 30%, Behavior 40%, Integrity 30%) | < 60 → `requires_review = true` |

### 5.2 Score Weights

```
Trust Score = (Identity × 0.30) + (Behavior × 0.40) + (Integrity × 0.30)
```

A Trust Score below **60** sets `requires_review = true` on the `quiz_attempts` record.

### 5.3 Review Queue API

```
GET  /api/admin/integrity-flags
     Returns all attempts with requires_review=true, ordered by lowest trust score first.

PATCH /api/admin/integrity-flags
Body: { "attemptId": "<uuid>", "action": "clear" | "void" | "escalate" }

  clear     → Reviewer satisfied; removes flag, logs reviewer + timestamp in proctor_flags
  void      → Misconduct confirmed; sets status='voided', logs reason
  escalate  → Keeps flag; logs escalation for senior review
```

> **Never use auto-fail.** The Trust Score feeds a review queue — it is never a verdict. All adjudication must be made by a human reviewer.

### 5.4 Integrity Event Types

| Event | Severity | Description |
|---|---|---|
| `focus_lost` | 1 (low) | Window lost focus |
| `tab_switch` | 2 (medium) | Browser tab changed |
| `fullscreen_exit` | 2 (medium) | Fullscreen mode exited |
| `clipboard_copy` / `clipboard_paste` | 2 (medium) | Clipboard used |
| `devtools_open` | 3 (high) | Browser developer tools opened |
| `secondary_monitor` | 3 (high) | Second monitor detected |
| `device_change` | 3 (high) | Device fingerprint changed mid-session |
| `ai_content_flag` | 3 (high) | Low keystroke entropy — possible AI-generated input |

---

## 6. Analytics & Bias Audit

```
GET /api/admin/analytics?days=30
```

Query `?days=7` through `?days=90`. Returns:

| Field | Description |
|---|---|
| `attempt_volume` | Daily attempt count, pass rate, and average score |
| `domain_performance` | Per-domain averages across all exams |
| `integrity` | Flag rate %, average trust score, voided count |
| `readiness_bands` | Distribution of READY / ALMOST_READY / NEEDS_PREPARATION / NOT_READY |
| `badges_issued` | Badge class breakdown |
| `cohort_variance` | Avg/stddev score per cohort — **use for bias-audit** |

> **Bias Audit:** Flag cohorts where `stddev_score > 15` or where `avg_score` differs by more than 10 points from the platform average. Investigate before scaling that cohort's assessments.

---

## 7. Digital Badges (Open Badges 3.0)

### 7.1 Badge Class Management

```sql
-- Create a new badge class:
INSERT INTO badge_classes
  (tenant_id, slug, name, description, min_score, exam_id, is_active)
VALUES
  ('<tenant-uuid>', 'my-badge-slug', 'My Badge Name',
   'Award description...', 75.0, '<exam-uuid>', true);
```

A default badge for the IBM watsonx Orchestrate AI Engineer Associate (C1000-207) is seeded by migration 009.

### 7.2 Issuing Badges

```
POST /api/badges/issue
Body: {
  "attempt_id": "<uuid>",
  "badge_class_slug": "wxo-ai-engineer-associate"
}

Returns:
  credential_id, verification_code, issued_on, expires_on,
  verify_url, ob3_credential (full JSON-LD)
```

Credentials are valid for **3 years** from issuance. Renewal requires retaking the assessment.

### 7.3 Revoking a Credential

```sql
UPDATE credential_issuances
SET is_revoked = true,
    revoked_at = NOW(),
    revocation_reason = 'Academic misconduct confirmed'
WHERE id = '<credential-uuid>';
```

Revoked credentials are marked invalid at the verification URL immediately.

---

## 8. Multi-Agent Evaluation Pipeline

### 8.1 Agent Roster

| Agent | Role | HC-3 Status |
|---|---|---|
| `CODE_EXAMINER` | Correctness, complexity, maintainability, coverage | L1 — proposal only |
| `ARCHITECT` | Design quality, security posture, dependency graph | L1 — proposal only |
| `ADVERSARIAL_QA` | Edge cases, fuzzing, resilience, injection vectors | L1 — proposal only |
| `CRITIC` | Disputes primary judges — finds over-scoring and missed issues | L1 — proposal only |
| `AGGREGATOR` | Reconciles judges + critic; calibrated final score (60/40 weight) | L1 — proposal only |

### 8.2 Pipeline Endpoint

```
POST /api/agent/evaluate
Body: {
  "attempt_id": "<uuid>",
  "submission": "<code or prose>",
  "language": "python",
  "problem_statement": "...",
  "rubric": "..."
}

Returns:
  final_score, skill_vector, justification,
  requires_human_review, pipeline_latency_ms,
  reports[] (per-agent scores and summaries)
```

If `requires_human_review: true` (score spread > 25 pts or final score < 40), the attempt's `requires_review` flag is set automatically. Review via the integrity flags queue before issuing any credential.

### 8.3 Score Spread Trigger

```
Judge scores: [CODE_EXAMINER, ARCHITECT, ADVERSARIAL_QA]
If max(judges) - min(judges) > 25 → requires_human_review = true
If final_score < 40             → requires_human_review = true
```

---

## 9. Assessment Marketplace

### 9.1 Listing Lifecycle

| Status | Meaning | Transition |
|---|---|---|
| `draft` | Created by author, not visible | Author submits → `pending_review` |
| `pending_review` | Awaiting admin review | Admin approves → `published` |
| `published` | Visible, purchasable | Admin suspends → `suspended` |
| `suspended` | Hidden, no new purchases | Admin reinstates → `published` |
| `withdrawn` | Author removed listing | Terminal state |

### 9.2 Revenue Share

| Author Type | Author % | Platform % |
|---|---|---|
| Standard author | 75% | 25% |
| Admin-authored | 80% | 20% |

All purchase records are stored in `marketplace_purchases`.

### 9.3 Admin Review

To publish a pending listing:

```sql
UPDATE marketplace_listings
SET status = 'published', review_notes = 'Approved — content quality verified'
WHERE id = '<listing-uuid>' AND status = 'pending_review';
```

---

## 10. Integration Reference

| System | Endpoint | Method | Auth |
|---|---|---|---|
| Admissions (inbound) | `/api/admissions/webhook` | POST | `X-Hub-Signature-256` HMAC-SHA256 |
| LTI Advantage (LMS) | `/api/integrations/lti/launch` | POST | `X-LTI-Signature` HMAC |
| Public Skills API | `/api/public/skills` | GET | None (rate-limited at Kong) |
| Workforce Gap Analysis | `/api/workforce/gap-analysis?org_id=` | GET | `i3-admin` role |
| Skills Passport | `/api/passport/[candidateId]` | GET | Self / admin / public token |
| Variant Generator | `/api/admin/generate-variants` | POST | `i3-admin` role |
| Integrity Flags | `/api/admin/integrity-flags` | GET / PATCH | `i3-admin` role |
| Analytics | `/api/admin/analytics` | GET | `i3-admin` role |
| Badge Issuance | `/api/badges/issue` | POST | Authenticated candidate |
| Agent Evaluate | `/api/agent/evaluate` | POST | Authenticated user |
| Cert Readiness | `/api/cert-readiness/[attemptId]` | GET | Attempt owner |
| AI Engineering Assess | `/api/ai-engineering/assess` | POST | Authenticated user |

### Admissions Callback Payload (outbound)

```json
{
  "event": "ASSESSMENT_COMPLETED",
  "applicant_id": "<user-id>",
  "session_id": "<attempt-uuid>",
  "tenant_id": "<tenant-uuid>",
  "results": {
    "total_score": 88.5,
    "performance_band": "PRODUCTION_READY",
    "recommendation": "STANDARD_ADMIT",
    "skill_vector": { "Domain 1: AI Foundations": 92.0 },
    "summary": "Completed with 88.5% (PRODUCTION_READY)."
  }
}
```

---

## 11. Hard Constraints Compliance

| HC | Constraint | EvalOS Implementation |
|---|---|---|
| **HC-3** | No agent above L1 | All agent outputs are proposals stored in `evaluation_agent_reports` — never auto-applied to grade without human gate |
| **HC-4** | `tenant_id UUID NOT NULL` | Every table has `tenant_id` with `DEFAULT`; every query calls `SET LOCAL app.tenant_id`; RLS enabled on all 15+ tables |
| **HC-5** | No state-modifying calls without MCP gateway authorization | All agent inference routes through LiteLLM proxy only; no direct model calls from application code |
| **HC-6** | No raw NIDs / phone numbers | Device fingerprint is a pseudonymous visitor ID (not PII). Candidate identity uses Keycloak `sub` (UUID) |
| **HC-7** | `DEV_BYPASS_AUTH=true` forbidden | No auth bypass anywhere in EvalOS; all routes call `getServerSession(authOptions)` |

---

## 12. API Quick Reference

### Admin Endpoints

```
GET    /api/admin/integrity-flags          Integrity review queue (ordered by trust score ASC)
PATCH  /api/admin/integrity-flags          Adjudicate: clear | void | escalate
GET    /api/admin/analytics?days=N         Analytics dashboard data
GET    /api/admin/attempts                 All attempts (last 500)
GET    /api/admin/export                   Export attempts to CSV
POST   /api/admin/generate-questions       AI question generation
POST   /api/admin/generate-variants        AI equivalent-form variant generation
GET    /api/admin/questions                Question bank management
```

### Candidate Endpoints

```
GET    /api/exams                          List published exams
POST   /api/exam/[examId]/start            Start or resume an attempt
POST   /api/exam/[examId]/answer           Save an answer
POST   /api/exam/[examId]/anticheat/batch  Batch integrity events
POST   /api/exam/[examId]/submit           Submit and grade
GET    /api/study-coach/[attemptId]        Study Coach report
POST   /api/interview/evaluate             AI Interview evaluation
POST   /api/lab/run                        Coding Lab execution
GET    /api/cert-readiness/[attemptId]     Certification readiness band
POST   /api/badges/issue                   Issue Open Badge 3.0 credential
GET    /api/certificate/[attemptId]        PDF certificate download
GET    /api/verify/[code]                  Credential verification (public)
```

### Phase 3 Endpoints

```
GET    /api/passport/[candidateId]         Skills Passport (self/admin/token)
GET    /api/workforce/gap-analysis         Org skills gap analysis (admin)
GET    /api/marketplace/listings           Browse marketplace
POST   /api/marketplace/listings           Create listing
GET    /api/public/skills                  Public Skills API (unauthenticated)
POST   /api/ai-engineering/assess          AI Engineering assessment mode
POST   /api/admissions/webhook             Inbound admissions events
POST   /api/integrations/lti/launch        LTI Advantage deep-link
```

---

*EvalOS Administrator Guide · i3 Technologies Limited · ARCH-EVALOS-2026-V2*  
*Source: `Evalos-Modernisation/EvalOS_Technical_Implementation_Guide.md`*
