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

  if (!session.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const { rows } = await pool.query(
    `SELECT
       qa.id,
       qa.student_id,
       e.title AS exam_title,
       e.code AS exam_code,
       qa.status,
       qa.pct_score,
       qa.passed,
       qa.started_at,
       qa.submitted_at,
       COALESCE(qa.focus_lost_count, 0) AS focus_lost_count,
       COALESCE(qa.fullscreen_exits, 0) AS fullscreen_exits,
       COALESCE(qa.clipboard_events, 0) AS clipboard_events,
       qa.proctor_flags
     FROM quiz_attempts qa
     JOIN exams e ON e.id = qa.exam_id
     ORDER BY qa.started_at DESC
     LIMIT 500`
  )

  return NextResponse.json(rows)
}
