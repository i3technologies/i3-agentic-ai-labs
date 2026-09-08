import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import ExamClient from './exam-client'

interface ExamPageProps {
  params: { examId: string }
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

async function getOrCreateAttempt(examId: string, userId: string) {
  // Check for an in-progress attempt
  const { rows: existing } = await pool.query(
    `SELECT id, question_snapshot, answers, started_at
     FROM quiz_attempts
     WHERE exam_id = $1 AND student_id = $2 AND status = 'in_progress'
     ORDER BY started_at DESC
     LIMIT 1`,
    [examId, userId]
  )
  if (existing.length > 0) return existing[0]

  // Create a new attempt via the API (start route handles snapshot creation)
  return null
}

async function getExamMeta(examId: string) {
  const { rows } = await pool.query(
    `SELECT id, title, code, description, duration_minutes,
            COALESCE(duration_secs, duration_minutes * 60) AS duration_secs,
            COALESCE(pass_threshold, 68) AS pass_threshold,
            randomize_order
     FROM exams
     WHERE id = $1 AND is_published = true`,
    [examId]
  )
  return rows[0] ?? null
}

export default async function ExamPage({ params }: ExamPageProps) {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const examId = params.examId
  if (!UUID_RE.test(examId)) redirect('/dashboard')

  const exam = await getExamMeta(examId)
  if (!exam) redirect('/dashboard')

  const userId = session.user.userId || session.user.email || ''
  const existingAttempt = await getOrCreateAttempt(examId, userId)

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
