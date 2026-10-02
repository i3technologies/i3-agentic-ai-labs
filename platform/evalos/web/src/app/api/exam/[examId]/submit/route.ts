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

// Minimal question shape needed by the inline grader (subset of stored snapshot)
interface QuestionSnap {
  id: string
  type: string
  question_type: string
  correct_answers: string[]
  domain_number: number
  domain_name: string
}

/**
 * Inline fallback grader — pure TypeScript, no external I/O.
 * Mirrors the Python grading logic in platform/grading/main.py exactly.
 * Used when the grading-service pod is unreachable so attempts are never
 * permanently stuck in 'grading' status.
 */
function gradeInline(
  snapshot: QuestionSnap[],
  answersRaw: Record<string, unknown>,
  passThreshold: number
): GradeResponse {
  const domainMap = new Map<number, { domain_name: string; correct: number; total: number }>()
  const detailed: GradeResponse['detailed_results'] = []
  let correctCount = 0

  for (const q of snapshot) {
    const dn = q.domain_number
    if (!domainMap.has(dn)) {
      domainMap.set(dn, { domain_name: q.domain_name, correct: 0, total: 0 })
    }
    const bucket = domainMap.get(dn)!
    bucket.total += 1

    const selected = answersRaw[q.id] ?? null
    const isMr = q.type?.toUpperCase() === 'MR' ||
      ['mr', 'multiple_response', 'multi_select'].includes(q.question_type?.toLowerCase() ?? '')

    let isCorrect = false
    if (isMr) {
      if (Array.isArray(selected) && selected.length > 0) {
        const given = [...selected].map(String).map(s => s.toUpperCase()).sort()
        const expected = [...q.correct_answers].map(s => s.toUpperCase()).sort()
        isCorrect = JSON.stringify(given) === JSON.stringify(expected)
      }
    } else {
      if (selected !== null && selected !== undefined) {
        if (typeof selected === 'string') {
          isCorrect = selected.toUpperCase() === (q.correct_answers[0] ?? '').toUpperCase()
        } else if (typeof selected === 'number') {
          isCorrect = selected === parseInt(q.correct_answers[0] ?? '-1', 10)
        }
      }
    }

    if (isCorrect) {
      correctCount += 1
      bucket.correct += 1
    }

    const correctLabel = q.correct_answers[0] ?? ''
    let correctIdx = 0
    const parsed = parseInt(correctLabel, 10)
    if (!isNaN(parsed)) {
      correctIdx = parsed
    } else {
      correctIdx = Math.max(0, (correctLabel.toUpperCase().charCodeAt(0) || 65) - 65)
    }
    detailed.push({ question_id: q.id, correct: isCorrect, correct_option: correctIdx })
  }

  const total = snapshot.length
  const pct = total > 0 ? (correctCount / total) * 100 : 0

  const domain_breakdown: DomainBreakdown[] = Array.from(domainMap.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([, v]) => ({
      domain: v.domain_name,
      score: v.correct,
      max: v.total,
      pct: v.total > 0 ? Math.round((v.correct / v.total) * 100 * 100) / 100 : 0,
    }))

  return {
    score: correctCount,
    max_score: total,
    pct_score: Math.round(pct * 10000) / 10000,
    passed: pct >= passThreshold,
    domain_breakdown,
    detailed_results: detailed,
  }
}

async function callGradingService(
  examId: string,
  attemptId: string,
  tenantId: string,
  snapshot: unknown[],
  answersRaw: Record<string, unknown>,
  passThreshold: number
): Promise<GradeResponse> {
  // Re-shape answers map { question_id: label_string_or_array_or_index }
  // The client stores answers as label strings ("A","B","C","D") for SC
  // questions and string arrays (["A","C"]) for MR questions.
  // The grading service expects { question_id, selected_option: label }.
  const answers = Object.entries(answersRaw).map(([question_id, val]) => ({
    question_id,
    // Pass the raw value — grading service handles both string labels and arrays.
    selected_option: val ?? null,
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
      pass_threshold: passThreshold,
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
      `SELECT qa.id, qa.question_snapshot, qa.answers,
              COALESCE(e.pass_threshold, e.passing_score, 68) AS pass_threshold,
              e.tenant_id,
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
         AND qa.status IN ('in_progress', 'grading', 'grading_failed')`,
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
    tenantId = attempt.tenant_id || (session.user as { tenant_id?: string }).tenant_id || '00000000-0000-0000-0000-000000000002'

    // HC-4: set RLS context now that we have the tenant_id
    await setTenantContext(client, tenantId)

    // ── SAGA Step 2: mark attempt as 'grading' ──────────────────────────────
    // Also covers pod-restart recovery: if status is already 'grading' we still
    // proceed — the previous pod died before completing; we retry here.
    await client.query(
      `UPDATE quiz_attempts SET status = 'grading', submitted_at = COALESCE(submitted_at, NOW())
       WHERE id = $1 AND status IN ('in_progress', 'grading', 'grading_failed')`,
      [attemptId]
    )

    // ── SAGA Step 3: call grading-service (with inline fallback) ────────────
    try {
      gradeResult = await callGradingService(
        examId,
        attemptId,
        tenantId,
        attempt.question_snapshot,
        attempt.answers,
        attempt.pass_threshold ?? 68
      )
    } catch (gradingErr) {
      // ── Inline fallback grader ──────────────────────────────────────────
      // When the external grading service is unreachable we grade in-process
      // so the attempt is never left permanently stuck. This is a pure
      // calculation (no external I/O) identical to the Python grading logic.
      console.warn(`[evalos-submit] grading service unreachable — using inline fallback. attemptId=${attemptId}:`, gradingErr)
      try {
        gradeResult = gradeInline(
          attempt.question_snapshot as QuestionSnap[],
          attempt.answers,
          attempt.pass_threshold ?? 68
        )
      } catch (fallbackErr) {
        // Both external and inline grading failed — mark as grading_failed so
        // the student can resubmit. This should never happen in practice.
        await client.query(
          `UPDATE quiz_attempts
           SET status        = 'grading_failed',
               proctor_flags = proctor_flags || $1::jsonb
           WHERE id = $2`,
          [JSON.stringify({ grading_error: String(gradingErr), fallback_error: String(fallbackErr), failed_at: new Date().toISOString() }), attemptId]
        )
        console.error(`[evalos-submit] both graders failed attemptId=${attemptId}:`, fallbackErr)
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
    // WHERE status = 'grading' guards against double-write on retry:
    // if the pod crashed after writing 'submitted' but before returning the
    // response, the client may retry — the guard makes this safe (no-op).
    await client.query(
      `UPDATE quiz_attempts
       SET status               = 'submitted',
           submitted_at         = COALESCE(submitted_at, NOW()),
           graded_at            = NOW(),
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
       WHERE id = $11 AND status = 'grading'`,
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

    // Enrolment queue: trigger for any final set (SET6 or SET7+) when passed
    const SET_RE = /SET(\d+)$/
    const setMatch = examCode.match(SET_RE)
    const setNumber = setMatch ? parseInt(setMatch[1], 10) : 0
    if (passed && setNumber >= 6) {
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
      set_number: setNumber,
      final_set_completed: passed && setNumber >= 6,
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
