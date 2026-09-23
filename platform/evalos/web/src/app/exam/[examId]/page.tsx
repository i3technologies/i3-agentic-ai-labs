import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import ExamClient from './exam-client'

interface ExamPageProps {
  params: { examId: string }
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

async function getOrCreateAttempt(examId: string, userId: string, tenantId: string) {
  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows: existing } = await client.query(
      `SELECT id, question_snapshot, answers, started_at
       FROM quiz_attempts
       WHERE exam_id = $1 AND student_id = $2 AND status = 'in_progress'
       ORDER BY started_at DESC
       LIMIT 1`,
      [examId, userId]
    )
    return existing[0] ?? null
  } finally {
    client.release()
  }
}

async function getExamMeta(examId: string, tenantId: string) {
  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows } = await client.query(
      `SELECT id, title, code, description,
              COALESCE(duration_secs, 5400) AS duration_secs,
              COALESCE(pass_threshold, passing_score, 68) AS pass_threshold,
              COALESCE(randomize_order, true) AS randomize_order
       FROM exams
       WHERE id = $1 AND is_published = true`,
      [examId]
    )
    return rows[0] ?? null
  } finally {
    client.release()
  }
}

export default async function ExamPage({ params }: ExamPageProps) {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const examId = params.examId
  if (!UUID_RE.test(examId)) redirect('/dashboard')

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'
  const exam = await getExamMeta(examId, tenantId)
  if (!exam) redirect('/dashboard')

  const userId = session.user.userId || session.user.email || ''
  const existingAttempt = await getOrCreateAttempt(examId, userId, tenantId)

  return (
    <ExamClient
      exam={exam}
      existingAttemptId={existingAttempt?.id ?? null}
      existingSnapshot={existingAttempt?.question_snapshot ?? null}
      existingAnswers={existingAttempt?.answers ?? null}
      existingStartedAt={existingAttempt?.started_at ?? null}
    />
  )
}
