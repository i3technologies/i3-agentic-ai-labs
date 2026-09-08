import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const AnswerSchema = z.object({
  attemptId: z.string().regex(UUID_RE, 'Invalid attempt ID'),
  questionId: z.string().regex(UUID_RE, 'Invalid question ID'),
  answer: z.union([z.string(), z.array(z.string())]),
})

export async function PATCH(
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
  const parsed = AnswerSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }

  const { attemptId, questionId, answer } = parsed.data
  const userId = session.user.userId || session.user.email || ''

  // Verify attempt ownership
  const { rows } = await pool.query(
    `SELECT id, answers FROM quiz_attempts
     WHERE id = $1 AND student_id = $2 AND exam_id = $3 AND status = 'in_progress'`,
    [attemptId, userId, examId]
  )
  if (rows.length === 0) {
    return NextResponse.json({ error: 'Attempt not found' }, { status: 404 })
  }

  const currentAnswers: Record<string, unknown> = rows[0].answers ?? {}
  currentAnswers[questionId] = answer

  await pool.query(
    `UPDATE quiz_attempts SET answers = $1 WHERE id = $2`,
    [JSON.stringify(currentAnswers), attemptId]
  )

  return NextResponse.json({ ok: true })
}
