import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// UUID v4 pattern
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export async function POST(
  _req: Request,
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

  const userId = session.user.userId || session.user.email || ''

  // Check for an existing in-progress attempt — resume it
  const { rows: existing } = await pool.query(
    `SELECT id, question_snapshot, answers, started_at
     FROM quiz_attempts
     WHERE exam_id = $1 AND student_id = $2 AND status = 'in_progress'
     ORDER BY started_at DESC
     LIMIT 1`,
    [examId, userId]
  )

  if (existing.length > 0) {
    const a = existing[0]
    return NextResponse.json({
      attemptId: a.id,
      questions: a.question_snapshot,
      answers: a.answers,
      startedAt: a.started_at,
    })
  }

  // Fetch exam metadata including new columns
  const { rows: examRows } = await pool.query(
    `SELECT id, code, randomize_order,
            COALESCE(pass_threshold, 90) AS pass_threshold,
            COALESCE(max_attempts, 5)    AS max_attempts,
            prerequisite_exam_id
     FROM exams
     WHERE id = $1 AND is_published = true`,
    [examId]
  )
  if (examRows.length === 0) {
    return NextResponse.json({ error: 'Exam not found' }, { status: 404 })
  }
  const exam = examRows[0]

  // ── Rule 1: attempt limit ──────────────────────────────────────────────────
  const { rows: countRows } = await pool.query(
    `SELECT COUNT(*)::int AS total
     FROM quiz_attempts
     WHERE exam_id = $1 AND student_id = $2
       AND status IN ('submitted', 'graded', 'in_progress')`,
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

  // ── Rule 2: prerequisite pass check ───────────────────────────────────────
  if (exam.prerequisite_exam_id) {
    const { rows: prereqRows } = await pool.query(
      `SELECT COUNT(*)::int AS passed_count
       FROM quiz_attempts
       WHERE exam_id = $1 AND student_id = $2
         AND status IN ('submitted', 'graded')
         AND passed = true`,
      [exam.prerequisite_exam_id, userId]
    )
    const hasPassed: number = prereqRows[0].passed_count
    if (hasPassed === 0) {
      // Find the prerequisite exam code for a friendly message
      const { rows: prereqMeta } = await pool.query(
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

  // ── Create new attempt ─────────────────────────────────────────────────────

  // Derive set_number from exam code (e.g. "C1000-207-SET1" -> 1)
  const setNumberMatch = exam.code.match(/SET(\d+)$/i)
  const setNumber = setNumberMatch ? parseInt(setNumberMatch[1], 10) : null

  // Fetch questions for this exam set
  let questionsQuery: string
  let queryParams: (string | number)[]

  if (setNumber !== null) {
    questionsQuery = `
      SELECT
        id, text, type, question_type, options, correct_answers,
        explanation, domain_number, domain_name, topic, set_number
      FROM questions
      WHERE set_number = $1 AND is_active = true
      ORDER BY question_number`
    queryParams = [setNumber]
  } else {
    questionsQuery = `
      SELECT
        id, text, type, question_type, options, correct_answers,
        explanation, domain_number, domain_name, topic, set_number
      FROM questions
      WHERE is_active = true
      ORDER BY domain_number, question_number
      LIMIT 60`
    queryParams = []
  }

  const { rows: rawQuestions } = await pool.query(questionsQuery, queryParams)

  // Shuffle options per question if randomise is on
  const questions = rawQuestions.map((q) => {
    const opts = exam.randomize_order ? shuffle(q.options) : q.options
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

  const finalQuestions = exam.randomize_order ? shuffle(questions) : questions

  // Insert attempt record
  const { rows: attemptRows } = await pool.query(
    `INSERT INTO quiz_attempts
       (exam_id, student_id, status, question_snapshot, answers, started_at)
     VALUES ($1, $2, 'in_progress', $3, $4, NOW())
     RETURNING id, started_at`,
    [examId, userId, JSON.stringify(finalQuestions), JSON.stringify({})]
  )

  return NextResponse.json({
    attemptId: attemptRows[0].id,
    questions: finalQuestions,
    answers: {},
    startedAt: attemptRows[0].started_at,
  })
}
