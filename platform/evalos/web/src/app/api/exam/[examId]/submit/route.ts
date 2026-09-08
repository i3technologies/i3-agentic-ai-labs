import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { triggerN8nWebhook } from '@/lib/n8n'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const SubmitSchema = z.object({
  attemptId: z.string().regex(UUID_RE, 'Invalid attempt ID'),
})

interface QuestionSnap {
  id: number
  type: string
  question_type: string
  correct_answers: string[]
  domain_number: number
  domain_name: string
}

function gradeAttempt(
  snapshot: QuestionSnap[],
  answers: Record<string, string | string[]>,
  passThreshold: number
) {
  let correct = 0
  const domainMap = new Map<
    number,
    { domain_name: string; correct: number; total: number }
  >()

  for (const q of snapshot) {
    const d = q.domain_number
    if (!domainMap.has(d)) {
      domainMap.set(d, { domain_name: q.domain_name, correct: 0, total: 0 })
    }
    const domain = domainMap.get(d)!
    domain.total += 1

    const ans = answers[q.id]
    const isMultiple =
      q.type === 'MR' ||
      q.question_type === 'multiple_response' ||
      q.question_type === 'MR'

    let isCorrect = false
    if (isMultiple) {
      const given = ((ans as string[]) ?? []).slice().sort()
      const expected = [...q.correct_answers].sort()
      isCorrect = JSON.stringify(given) === JSON.stringify(expected)
    } else {
      isCorrect = ans === q.correct_answers[0]
    }

    if (isCorrect) {
      correct += 1
      domain.correct += 1
    }
  }

  const total = snapshot.length
  const pctScore = total > 0 ? (correct / total) * 100 : 0
  const passed = pctScore >= passThreshold

  const domainBreakdown = Array.from(domainMap.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([domain_number, v]) => ({
      domain_number,
      domain_name: v.domain_name,
      correct: v.correct,
      total: v.total,
      pct: v.total > 0 ? (v.correct / v.total) * 100 : 0,
    }))

  return { correct, total, pctScore, passed, domainBreakdown }
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

  // Fetch attempt
  const { rows } = await pool.query(
    `SELECT qa.id, qa.question_snapshot, qa.answers, e.pass_threshold
     FROM quiz_attempts qa
     JOIN exams e ON e.id = qa.exam_id
     WHERE qa.id = $1 AND qa.student_id = $2 AND qa.exam_id = $3
       AND qa.status = 'in_progress'`,
    [attemptId, userId, examId]
  )

  if (rows.length === 0) {
    // Already submitted — return gracefully
    const { rows: done } = await pool.query(
      `SELECT id, pct_score, passed FROM quiz_attempts
       WHERE id = $1 AND student_id = $2`,
      [attemptId, userId]
    )
    if (done.length > 0) {
      return NextResponse.json({
        ok: true,
        score: done[0].pct_score,
        passed: done[0].passed,
      })
    }
    return NextResponse.json({ error: 'Attempt not found' }, { status: 404 })
  }

  const attempt = rows[0]
  const passThreshold = attempt.pass_threshold ?? 68
  const { correct, total, pctScore, passed, domainBreakdown } = gradeAttempt(
    attempt.question_snapshot,
    attempt.answers,
    passThreshold
  )

  await pool.query(
    `UPDATE quiz_attempts
     SET status       = 'submitted',
         score        = $1,
         max_score    = $2,
         pct_score    = $3,
         passed       = $4,
         submitted_at = NOW(),
         proctor_flags = proctor_flags || $5::jsonb
     WHERE id = $6`,
    [
      correct,
      total,
      pctScore,
      passed,
      JSON.stringify({ domain_breakdown: domainBreakdown }),
      attemptId,
    ]
  )

  // Fire-and-forget n8n webhook — pass/fail notification email
  const examCodeRow = (await pool.query(`SELECT code FROM exams WHERE id = $1`, [examId])).rows[0]
  const examCode: string = examCodeRow?.code ?? examId

  // If SET6 passed — insert into enrolment_queue for lab provisioning
  if (passed && examCode.endsWith('SET6')) {
    await pool.query(
      `INSERT INTO enrolment_queue
         (student_id, email, cohort_id, evalos_score, status)
       VALUES ($1, $2, 'default', $3, 'pending')
       ON CONFLICT DO NOTHING`,
      [userId, session.user.email || userId, pctScore]
    ).catch(() => { /* best-effort — do not fail submit on this */ })
  }

  triggerN8nWebhook({
    event: passed ? 'exam_passed' : 'exam_failed',
    student_id: userId,
    student_name: session.user.name || session.user.email || userId,
    student_email: session.user.email || '',
    exam_code: examCode,
    set6_completed: passed && examCode.endsWith('SET6'),
    pct_score: pctScore,
    correct,
    total,
    pass_threshold: passThreshold,
    domain_breakdown: domainBreakdown,
    attempt_id: attemptId,
  }).catch(() => { /* best-effort */ })

  return NextResponse.json({
    ok: true,
    score: pctScore,
    passed,
    correct,
    total,
    domainBreakdown,
  })
}
