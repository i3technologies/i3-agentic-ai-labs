import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'
import { triggerN8nWebhook } from '@/lib/n8n'
import { computeIntegrityScores } from '@/lib/integrity-scorer'
import {
  dispatchAssessmentCompleted,
  scoreToBand,
  bandToRecommendation,
  type SkillVector,
} from '@/lib/admissions-dispatch'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const GRADING_SERVICE_URL =
  process.env.GRADING_SERVICE_URL ??
  'http://grading-service.i3-evalos.svc.cluster.local:8000'

const SubmitSchema = z.object({
  attemptId: z.string().regex(UUID_RE, 'Invalid attempt ID'),
})

interface DomainBreakdown {
  domain: string
  score: number
  max: number
  pct: number
}

interface GradeResponse {
  score: number
  max_score: number
  pct_score: number
  passed: boolean
  domain_breakdown: DomainBreakdown[]
  detailed_results: { question_id: string; correct: boolean; correct_option: number }[]
}

async function callGradingService(
  examId: string,
  attemptId: string,
  tenantId: string,
  snapshot: unknown[],
  answersRaw: Record<string, unknown>
): Promise<GradeResponse> {
  // Re-shape legacy answers map { question_id: selected_option_index }
  const answers = Object.entries(answersRaw).map(([question_id, val]) => ({
    question_id,
    selected_option: typeof val === 'number' ? val : -1,
  }))

  const res = await fetch(`${GRADING_SERVICE_URL}/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      exam_id: examId,
      session_id: attemptId,
      tenant_id: tenantId,
      question_snapshot: snapshot,
      answers,
    }),
    signal: AbortSignal.timeout(30_000),
  })

  if (!res.ok) {
    throw new Error(`Grading service error: ${res.status}`)
  }
  return res.json() as Promise<GradeResponse>
}

export async function POST(
  req: Request,
  { params }: { params: { examId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const examId = params.examId
  if (!UUID_RE.test(examId)) {
    return NextResponse.json({ error: 'Invalid exam ID' }, { status: 400 })
  }

  const body = await req.json().catch(() => null)
  const parsed = SubmitSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }

  const { attemptId } = parsed.data
  const userId = session.user.userId || session.user.email || ''

  const client = await pool.connect()
  let tenantId: string
  let gradeResult: GradeResponse
  let attempt: {
    question_snapshot: unknown[]
    answers: Record<string, unknown>
    pass_threshold: number
    tenant_id: string
    focus_lost_count: number
    fullscreen_exits: number
    clipboard_events: number
    tab_switch_events: unknown[]
    keystroke_entropy: number | null
    device_fingerprint: string | null
    proctor_flags: unknown[]
  }

  try {
    // ── SAGA Step 1: fetch attempt (must be in_progress or grading_failed) ────
    // HC-4: extract tenant_id from the joined exam row, then set RLS context.
    const { rows } = await client.query(
      `SELECT qa.id, qa.question_snapshot, qa.answers, e.pass_threshold, e.tenant_id,
              COALESCE(qa.focus_lost_count, 0)   AS focus_lost_count,
              COALESCE(qa.fullscreen_exits, 0)    AS fullscreen_exits,
              COALESCE(qa.clipboard_events, 0)    AS clipboard_events,
              COALESCE(qa.tab_switch_events, '[]'::jsonb) AS tab_switch_events,
              qa.keystroke_entropy,
              qa.device_fingerprint,
              COALESCE(qa.proctor_flags, '[]'::jsonb) AS proctor_flags
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       WHERE qa.id = $1 AND qa.student_id = $2 AND qa.exam_id = $3
         AND qa.status IN ('in_progress', 'grading_failed')`,
      [attemptId, userId, examId]
    )

    if (rows.length === 0) {
      const { rows: done } = await client.query(
        `SELECT id, pct_score, passed, status FROM quiz_attempts
         WHERE id = $1 AND student_id = $2`,
        [attemptId, userId]
      )
      if (done.length > 0 && done[0].status === 'submitted') {
        return NextResponse.json({
          ok: true,
          score: done[0].pct_score,
          passed: done[0].passed,
        })
      }
      return NextResponse.json({ error: 'Attempt not found or not in a submittable state' }, { status: 404 })
    }

    attempt = rows[0]
    tenantId = attempt.tenant_id ?? (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

    // HC-4: set RLS context now that we have the tenant_id
    await setTenantContext(client, tenantId)

    // ── SAGA Step 2: mark attempt as 'grading' ──────────────────────────────
    await client.query(
      `UPDATE quiz_attempts SET status = 'grading', submitted_at = NOW()
       WHERE id = $1 AND status IN ('in_progress', 'grading_failed')`,
      [attemptId]
    )

    // ── SAGA Step 3: call grading-service ───────────────────────────────────
    try {
      gradeResult = await callGradingService(
        examId,
        attemptId,
        tenantId,
        attempt.question_snapshot,
        attempt.answers
      )
    } catch (gradingErr) {
      await client.query(
        `UPDATE quiz_attempts
         SET status        = 'grading_failed',
             proctor_flags = proctor_flags || $1::jsonb
         WHERE id = $2`,
        [JSON.stringify({ grading_error: String(gradingErr), failed_at: new Date().toISOString() }), attemptId]
      )
      console.error(`[evalos-submit] grading_failed attemptId=${attemptId}:`, gradingErr)
      return NextResponse.json(
        {
          error: 'grading_service_unavailable',
          message: 'Grading is temporarily unavailable. Your answers are saved — please resubmit in a few minutes.',
          attempt_id: attemptId,
          retryable: true,
        },
        { status: 503 }
      )
    }

    const { score, max_score, pct_score, passed, domain_breakdown } = gradeResult
    const passThreshold = attempt.pass_threshold ?? 68

    // ── Compute integrity scores ────────────────────────────────────────────
    const integrityScores = computeIntegrityScores({
      focusLostCount:    attempt.focus_lost_count,
      fullscreenExits:   attempt.fullscreen_exits,
      clipboardEvents:   attempt.clipboard_events,
      tabSwitchEvents:   Array.isArray(attempt.tab_switch_events) ? attempt.tab_switch_events : [],
      keystrokeEntropy:  attempt.keystroke_entropy,
      deviceChanged:     false, // Phase 1: no mid-session fingerprint re-check yet
      proctorFlags:      Array.isArray(attempt.proctor_flags) ? attempt.proctor_flags : [],
    })

    // ── SAGA Step 4: persist grade result + integrity scores ────────────────
    await client.query(
      `UPDATE quiz_attempts
       SET status               = 'submitted',
           score                = $1,
           max_score            = $2,
           pct_score            = $3,
           passed               = $4,
           proctor_flags        = proctor_flags || $5::jsonb,
           identity_score       = $6,
           behavior_score       = $7,
           integrity_confidence = $8,
           trust_score          = $9,
           requires_review      = $10
       WHERE id = $11`,
      [
        score,
        max_score,
        pct_score,
        passed,
        JSON.stringify({ domain_breakdown }),
        integrityScores.identityScore,
        integrityScores.behaviorScore,
        integrityScores.integrityConfidence,
        integrityScores.trustScore,
        integrityScores.requiresReview,
        attemptId,
      ]
    )

    // ── SAGA Step 5: Skills Evidence skeleton ────────────────────────────────
    // Write per-domain evidence rows to candidate_skill_evidence (best-effort).
    if (domain_breakdown && Array.isArray(domain_breakdown)) {
      ;(async () => {
        const skillClient = await pool.connect()
        try {
          await setTenantContext(skillClient, tenantId)
          for (const d of domain_breakdown) {
            // Upsert skill node for this domain (idempotent)
            const { rows: skillRows } = await skillClient.query(
              `INSERT INTO skill_nodes (tenant_id, name, level)
               VALUES ($1, $2, 'competency')
               ON CONFLICT (tenant_id, name, level) DO UPDATE SET name = EXCLUDED.name
               RETURNING id`,
              [tenantId, d.domain]
            )
            const skillId: string | undefined = skillRows[0]?.id
            if (!skillId) continue

            await skillClient.query(
              `INSERT INTO candidate_skill_evidence
                 (tenant_id, candidate_id, skill_id, proficiency, evidence_type, evidence_ref)
               VALUES ($1, $2, $3, $4, 'exam', $5)`,
              [tenantId, userId, skillId, d.pct ?? 0, attemptId]
            )
          }
        } catch (err) {
          console.error('[evalos-submit] skill evidence write failed:', err)
        } finally {
          skillClient.release()
        }
      })()
    }

    // ── SAGA Step 6: side-effects (best-effort, non-blocking) ────────────────
    const examCodeRow = (await client.query(`SELECT code FROM exams WHERE id = $1`, [examId])).rows[0]
    const examCode: string = examCodeRow?.code ?? examId

    if (passed && examCode.endsWith('SET6')) {
      client.query(
        `INSERT INTO enrolment_queue
           (student_id, email, cohort_id, evalos_score, status)
         VALUES ($1, $2, 'default', $3, 'pending')
         ON CONFLICT DO NOTHING`,
        [userId, session.user.email || userId, pct_score]
      ).catch((err: unknown) => {
        console.error(`[evalos-submit] enrolment_queue insert failed attemptId=${attemptId}:`, err)
      })
    }

    // Dispatch ASSESSMENT_COMPLETED to admissions service (best-effort)
    const performanceBand = scoreToBand(pct_score)
    const recommendation  = bandToRecommendation(performanceBand)
    const skillVector: SkillVector = Object.fromEntries(
      (domain_breakdown ?? []).map((d: DomainBreakdown) => [d.domain, d.pct ?? 0])
    )
    dispatchAssessmentCompleted(
      {
        applicant_id: userId,
        session_id: attemptId,
        tenant_id: tenantId,
        results: {
          total_score:      pct_score,
          performance_band: performanceBand,
          recommendation,
          skill_vector:     skillVector,
          summary: integrityScores.requiresReview
            ? 'Assessment completed — integrity review required before credential issuance.'
            : `Completed with ${pct_score.toFixed(1)}% (${performanceBand}).`,
        },
      },
      attemptId,
      tenantId
    ).catch(() => { /* best-effort */ })

    triggerN8nWebhook({
      event: passed ? 'exam_passed' : 'exam_failed',
      student_id: userId,
      student_name: session.user.name || session.user.email || userId,
      student_email: session.user.email || '',
      exam_code: examCode,
      set6_completed: passed && examCode.endsWith('SET6'),
      pct_score,
      correct: score,
      total: max_score,
      pass_threshold: passThreshold,
      domain_breakdown,
      attempt_id: attemptId,
      trust_score: integrityScores.trustScore,
      requires_review: integrityScores.requiresReview,
    }).catch(() => { /* best-effort */ })

    return NextResponse.json({
      ok: true,
      score: pct_score,
      passed,
      correct: score,
      total: max_score,
      domainBreakdown: domain_breakdown,
      integrity: {
        trustScore:     integrityScores.trustScore,
        requiresReview: integrityScores.requiresReview,
      },
    })
  } finally {
    client.release()
  }
}
