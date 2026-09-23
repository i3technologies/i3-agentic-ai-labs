import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    // HC-4: set RLS session variable before any tenant-scoped query
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows } = await client.query(
      `SELECT
         e.id,
         e.title,
         e.code,
         e.description,
         e.duration_minutes,
         COALESCE(e.pass_threshold, 68) AS pass_threshold,
         e.tags,
         (
           SELECT COUNT(*)::int
           FROM questions q
           WHERE q.set_number = REGEXP_REPLACE(e.code, '^.*SET', '', 'g')::int
             AND q.is_active = true
         ) AS question_count,
         (
           SELECT COUNT(*)::int
           FROM quiz_attempts qa
           WHERE qa.exam_id = e.id AND qa.student_id = $1
         ) AS attempt_count,
         (
           SELECT MAX(pct_score)
           FROM quiz_attempts qa
           WHERE qa.exam_id = e.id AND qa.student_id = $1 AND qa.status = 'submitted'
         ) AS best_score
       FROM exams e
       WHERE e.is_published = true
       ORDER BY e.code`,
      [userId]
    )

    return NextResponse.json(rows)
  } finally {
    client.release()
  }
}
