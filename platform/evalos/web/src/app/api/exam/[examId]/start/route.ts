import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'
import { computeIntegrityScores } from '@/lib/integrity-scorer'

export const dynamic = 'force-dynamic'

/** Cryptographically secure Fisher-Yates shuffle (crypto.getRandomValues). */
function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  const bytes = new Uint32Array(a.length)
  crypto.getRandomValues(bytes)
  for (let i = a.length - 1; i > 0; i--) {
    const j = bytes[i] % (i + 1)
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// UUID v4 pattern
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export async function POST(
  req: Request,
  { params }: { params: { examId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // HC-6-adjacent: device fingerprint is a pseudonym, not a NID/phone.
  // Stored as-is; no HMAC required for non-PII device tokens.
  const deviceFingerprint =
    req.headers.get('x-device-fingerprint') ?? null

  const examId = params.examId
  if (!UUID_RE.test(examId)) {
    return NextResponse.json({ error: 'Invalid exam ID' }, { status: 400 })
  }

  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    // HC-4: set RLS session variable for all queries in this request
    await setTenantContext(client, tenantId)

    // Check for an existing in-progress attempt — resume it
    const { rows: existing } = await client.query(
      `SELECT id, question_snapshot, answers, started_at
       FROM quiz_attempts
       WHERE exam_id = $1 AND student_id = $2 AND status = 'in_progress'
       ORDER BY started_at DESC
       LIMIT 1`,
      [examId, userId]
    )

    if (existing.length > 0) {
      const a = existing[0]

      // ── Fingerprint drift check on resume ──────────────────────────────────
      // If the device fingerprint has changed since the attempt was started,
      // flag it as a potential proxy test-taker (does not block resume in Phase 1).
      if (
        deviceFingerprint &&
        a.device_fingerprint &&
        deviceFingerprint !== a.device_fingerprint
      ) {
        const integritySignal = computeIntegrityScores({
          focusLostCount:   0,
          fullscreenExits:  0,
          clipboardEvents:  0,
          tabSwitchEvents:  [],
          keystrokeEntropy: null,
          deviceChanged:    true,
          proctorFlags:     [],
        })
        // Record the drift signal non-blocking; do not block resume
        client.query(
          `UPDATE quiz_attempts
           SET requires_review = true,
               trust_score     = LEAST(COALESCE(trust_score, 100), $1)
           WHERE id = $2`,
          [integritySignal.trustScore, a.id]
        ).catch(() => { /* best-effort */ })
      }

      return NextResponse.json({
        attemptId: a.id,
        questions: a.question_snapshot,
        answers: a.answers,
        startedAt: a.started_at,
      })
    }

    // Fetch exam metadata including draw_spec for rotating-bank exams
    const { rows: examRows } = await client.query(
      `SELECT id, code, randomize_order,
              COALESCE(pass_threshold, 90)  AS pass_threshold,
              COALESCE(max_attempts, 5)     AS max_attempts,
              retake_window_hours,
              prerequisite_exam_id,
              draw_spec
       FROM exams
       WHERE id = $1 AND is_published = true`,
      [examId]
    )
    if (examRows.length === 0) {
      return NextResponse.json({ error: 'Exam not found' }, { status: 404 })
    }
    const exam = examRows[0]

    // ── Rule 1: attempt limit ────────────────────────────────────────────────
    const { rows: countRows } = await client.query(
      `SELECT COUNT(*)::int AS total,
              MIN(started_at) AS first_attempt_at
       FROM quiz_attempts
       WHERE exam_id = $1 AND student_id = $2
         AND status IN ('submitted', 'graded', 'in_progress', 'grading', 'grading_failed')`,
      [examId, userId]
    )
    const usedAttempts: number = countRows[0].total
    if (usedAttempts >= exam.max_attempts) {
      return NextResponse.json(
        {
          error: 'attempts_exhausted',
          message: `You have used all ${exam.max_attempts} attempts for this exam.`,
          used: usedAttempts,
          max: exam.max_attempts,
        },
        { status: 403 }
      )
    }

    // ── Rule 1b: retake window enforcement ─────────────────────────────────
    // If retake_window_hours is set and this is a retake (attempt > 0),
    // the new attempt must be started within retake_window_hours of the FIRST attempt.
    if (exam.retake_window_hours != null && usedAttempts > 0) {
      const firstAttemptAt: Date | null = countRows[0].first_attempt_at
        ? new Date(countRows[0].first_attempt_at)
        : null
      if (firstAttemptAt) {
        const windowMs   = exam.retake_window_hours * 60 * 60 * 1000
        const deadlineMs = firstAttemptAt.getTime() + windowMs
        const nowMs      = Date.now()
        if (nowMs > deadlineMs) {
          const deadline = new Date(deadlineMs).toISOString()
          return NextResponse.json(
            {
              error: 'retake_window_expired',
              message: `Retake window for this exam has closed. Retakes must be started within ${exam.retake_window_hours} hours of your first attempt (deadline: ${deadline}).`,
              retake_window_hours: exam.retake_window_hours,
              first_attempt_at: firstAttemptAt.toISOString(),
              deadline,
            },
            { status: 403 }
          )
        }
      }
    }

    // ── Rule 2: prerequisite pass check ─────────────────────────────────────
    if (exam.prerequisite_exam_id) {
      const { rows: prereqRows } = await client.query(
        `SELECT COUNT(*)::int AS passed_count
         FROM quiz_attempts
         WHERE exam_id = $1 AND student_id = $2
           AND status IN ('submitted', 'graded')
           AND passed = true`,
        [exam.prerequisite_exam_id, userId]
      )
      const hasPassed: number = prereqRows[0].passed_count
      if (hasPassed === 0) {
        const { rows: prereqMeta } = await client.query(
          `SELECT code FROM exams WHERE id = $1`,
          [exam.prerequisite_exam_id]
        )
        const prereqCode = prereqMeta[0]?.code ?? 'the previous set'
        return NextResponse.json(
          {
            error: 'prerequisite_not_met',
            message: `You must pass ${prereqCode} (≥90%) before attempting ${exam.code}.`,
            prerequisite_exam_id: exam.prerequisite_exam_id,
          },
          { status: 403 }
        )
      }
    }

    // ── Create new attempt ───────────────────────────────────────────────────

    const setNumberMatch = exam.code.match(/SET(\d+)$/i)
    const setNumber = setNumberMatch ? parseInt(setNumberMatch[1], 10) : null

    // HC-4: questions are filtered by (tenant_id = current tenant OR tenant_id IS NULL)
    // so system/shared questions are visible to all tenants but cross-tenant leakage is blocked.
    let rawQuestions: Array<Record<string, unknown>> = []

    type DrawSpecEntry = { domain_number: number; domain_name: string; count: number }
    const drawSpec: DrawSpecEntry[] | null =
      exam.draw_spec && Array.isArray(exam.draw_spec) && exam.draw_spec.length > 0
        ? (exam.draw_spec as DrawSpecEntry[])
        : null

    if (drawSpec && setNumber !== null) {
      // ── draw_spec rotating bank: proportional per-domain random draw ────────
      // For each domain entry, draw `count` questions at random using DB RANDOM().
      // This guarantees a unique 60-question combination on every attempt.
      for (const entry of drawSpec) {
        const { rows: domainRows } = await client.query(
          `SELECT
             id, text, type, question_type, options, correct_answers,
             explanation, domain_number, domain_name, topic, set_number
           FROM questions
           WHERE set_number = $1
             AND domain_number = $2
             AND is_active = true
             AND (tenant_id = $3 OR tenant_id IS NULL)
           ORDER BY RANDOM()
           LIMIT $4`,
          [setNumber, entry.domain_number, tenantId, entry.count]
        )
        rawQuestions = rawQuestions.concat(domainRows)
      }
    } else if (setNumber !== null) {
      // ── Fallback: all active questions for this set (Sets 1–6 without draw_spec) ─
      const { rows } = await client.query(
        `SELECT
           id, text, type, question_type, options, correct_answers,
           explanation, domain_number, domain_name, topic, set_number
         FROM questions
         WHERE set_number = $1
           AND is_active = true
           AND (tenant_id = $2 OR tenant_id IS NULL)
         ORDER BY question_number`,
        [setNumber, tenantId]
      )
      rawQuestions = rows
    } else {
      // ── No set number: draw first 60 active questions across all sets ─────
      const { rows } = await client.query(
        `SELECT
           id, text, type, question_type, options, correct_answers,
           explanation, domain_number, domain_name, topic, set_number
         FROM questions
         WHERE is_active = true
           AND (tenant_id = $1 OR tenant_id IS NULL)
         ORDER BY domain_number, question_number
         LIMIT 60`,
        [tenantId]
      )
      rawQuestions = rows
    }

    const questions = rawQuestions.map((q) => {
      const opts = exam.randomize_order ? shuffle(q.options as unknown[]) : q.options
      return {
        id: q.id,
        text: q.text,
        type: q.type,
        question_type: q.question_type,
        options: opts,
        correct_answers: q.correct_answers,
        explanation: q.explanation,
        domain_number: q.domain_number,
        domain_name: q.domain_name,
        topic: q.topic,
      }
    })

    // Apply Fisher-Yates shuffle to merge the per-domain draws into a single random order
    const finalQuestions = exam.randomize_order ? shuffle(questions) : questions

    // Insert attempt record (HC-4: tenant_id included in INSERT)
    const { rows: attemptRows } = await client.query(
      `INSERT INTO quiz_attempts
         (exam_id, student_id, tenant_id, status, question_snapshot, answers,
          device_fingerprint, started_at)
       VALUES ($1, $2, $3, 'in_progress', $4, $5, $6, NOW())
       RETURNING id, started_at`,
      [examId, userId, tenantId, JSON.stringify(finalQuestions), JSON.stringify({}), deviceFingerprint]
    )

    return NextResponse.json({
      attemptId: attemptRows[0].id,
      questions: finalQuestions,
      answers: {},
      startedAt: attemptRows[0].started_at,
    })
  } finally {
    client.release()
  }
}
