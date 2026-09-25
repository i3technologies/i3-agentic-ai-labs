-- ============================================================
-- Migration: 014_fix_rls_empty_tenant.sql
-- Fix all RLS policies to handle missing / empty app.tenant_id
--
-- Problem: current_setting('app.tenant_id', true) returns ''
-- (empty string) when the parameter has not been SET on the
-- current connection. Casting '' to uuid throws:
--   ERROR 22P02: invalid input syntax for type uuid: ""
--
-- Root causes:
--   1. SET LOCAL only persists within a BEGIN/COMMIT block.
--      Without an explicit transaction, the setting reverts
--      before the next query runs on the same pooled connection.
--   2. Keycloak may return tenant_id as '' (empty string) which
--      passes through ??(nullish coalescing) in JavaScript.
--
-- Fix A (this migration): wrap the cast in NULLIF so that an
--   empty / missing setting evaluates to NULL, making the policy
--   return FALSE (row hidden) instead of crashing.
--
--   Before: current_setting('app.tenant_id', true)::uuid
--   After:  NULLIF(current_setting('app.tenant_id', true), '')::uuid
--
-- Fix B (db.ts): changed SET LOCAL → SET (session-level) so the
--   tenant context persists for the lifetime of the pool client
--   checkout, not just within a transaction block.
--
-- Covers all 32 RLS-enabled tables in evalos_db.
-- Safe to run multiple times (DROP POLICY IF EXISTS).
-- ============================================================

BEGIN;

-- ── Core exam tables ─────────────────────────────────────────
DROP POLICY IF EXISTS questions_tenant_isolation ON questions;
CREATE POLICY questions_tenant_isolation ON questions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS exams_tenant_isolation ON exams;
CREATE POLICY exams_tenant_isolation ON exams
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS quiz_attempts_tenant_isolation ON quiz_attempts;
CREATE POLICY quiz_attempts_tenant_isolation ON quiz_attempts
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ── AI / Interview tables ─────────────────────────────────────
DROP POLICY IF EXISTS ai_interview_evaluations_tenant_isolation ON ai_interview_evaluations;
CREATE POLICY ai_interview_evaluations_tenant_isolation ON ai_interview_evaluations
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS ai_interview_questions_tenant_isolation ON ai_interview_questions;
CREATE POLICY ai_interview_questions_tenant_isolation ON ai_interview_questions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS ai_interviews_tenant_isolation ON ai_interviews;
CREATE POLICY ai_interviews_tenant_isolation ON ai_interviews
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS ai_engineering_sessions_tenant_isolation ON ai_engineering_sessions;
CREATE POLICY ai_engineering_sessions_tenant_isolation ON ai_engineering_sessions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ── Assessment / CAT tables ───────────────────────────────────
DROP POLICY IF EXISTS assessment_blueprints_tenant_isolation ON assessment_blueprints;
CREATE POLICY assessment_blueprints_tenant_isolation ON assessment_blueprints
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS assessment_final_results_tenant_isolation ON assessment_final_results;
CREATE POLICY assessment_final_results_tenant_isolation ON assessment_final_results
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS assessment_sessions_tenant_isolation ON assessment_sessions;
CREATE POLICY assessment_sessions_tenant_isolation ON assessment_sessions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS cat_item_responses_tenant_isolation ON cat_item_responses;
CREATE POLICY cat_item_responses_tenant_isolation ON cat_item_responses
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS cat_sessions_tenant_isolation ON cat_sessions;
CREATE POLICY cat_sessions_tenant_isolation ON cat_sessions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS irt_parameters_tenant_isolation ON irt_parameters;
CREATE POLICY irt_parameters_tenant_isolation ON irt_parameters
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ── Badges / Certificates / Skills ───────────────────────────
DROP POLICY IF EXISTS badge_classes_tenant_isolation ON badge_classes;
CREATE POLICY badge_classes_tenant_isolation ON badge_classes
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS candidate_skill_evidence_tenant_isolation ON candidate_skill_evidence;
CREATE POLICY candidate_skill_evidence_tenant_isolation ON candidate_skill_evidence
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS cert_readiness_tenant_isolation ON cert_readiness_scores;
CREATE POLICY cert_readiness_tenant_isolation ON cert_readiness_scores
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS certificates_tenant_isolation ON certificates;
CREATE POLICY certificates_tenant_isolation ON certificates
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS credential_issuances_tenant_isolation ON credential_issuances;
CREATE POLICY credential_issuances_tenant_isolation ON credential_issuances
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS skills_passports_tenant_isolation ON skills_passports;
CREATE POLICY skills_passports_tenant_isolation ON skills_passports
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS skill_nodes_tenant_isolation ON skill_nodes;
CREATE POLICY skill_nodes_tenant_isolation ON skill_nodes
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS org_skills_tenant_isolation ON org_skills;
CREATE POLICY org_skills_tenant_isolation ON org_skills
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ── Marketplace / Enrolment / Integrity ──────────────────────
DROP POLICY IF EXISTS marketplace_listings_tenant_isolation ON marketplace_listings;
CREATE POLICY marketplace_listings_tenant_isolation ON marketplace_listings
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS marketplace_purchases_tenant_isolation ON marketplace_purchases;
CREATE POLICY marketplace_purchases_tenant_isolation ON marketplace_purchases
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS enrolment_queue_tenant_isolation ON enrolment_queue;
CREATE POLICY enrolment_queue_tenant_isolation ON enrolment_queue
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS integrity_events_tenant_isolation ON integrity_events;
CREATE POLICY integrity_events_tenant_isolation ON integrity_events
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS admissions_webhook_log_tenant_isolation ON admissions_webhook_log;
CREATE POLICY admissions_webhook_log_tenant_isolation ON admissions_webhook_log
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

-- ── Other tables ─────────────────────────────────────────────
DROP POLICY IF EXISTS challenge_modules_tenant_isolation ON challenge_modules;
CREATE POLICY challenge_modules_tenant_isolation ON challenge_modules
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS code_submissions_tenant_isolation ON code_submissions;
CREATE POLICY code_submissions_tenant_isolation ON code_submissions
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS evaluation_agent_reports_tenant_isolation ON evaluation_agent_reports;
CREATE POLICY evaluation_agent_reports_tenant_isolation ON evaluation_agent_reports
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS exam_banks_tenant_isolation ON exam_banks;
CREATE POLICY exam_banks_tenant_isolation ON exam_banks
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS question_sets_tenant_isolation ON question_sets;
CREATE POLICY question_sets_tenant_isolation ON question_sets
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

DROP POLICY IF EXISTS topics_tenant_isolation ON topics;
CREATE POLICY topics_tenant_isolation ON topics
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

COMMIT;

-- ── Verification ─────────────────────────────────────────────
-- SELECT COUNT(*) AS total,
--        COUNT(*) FILTER (WHERE qual LIKE '%NULLIF%') AS fixed,
--        COUNT(*) FILTER (WHERE qual NOT LIKE '%NULLIF%') AS unfixed
--   FROM pg_policies;
-- Expected: unfixed = 0
