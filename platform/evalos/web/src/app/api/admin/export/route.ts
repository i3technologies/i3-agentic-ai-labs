import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!session.user.isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let rows: any[]
  try {
    // HC-4: set RLS session variable before any tenant-scoped query
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const result = await client.query(
      `SELECT
         qa.student_id,
         e.code  AS exam_code,
         e.title AS exam_title,
         qa.status,
         ROUND(qa.pct_score, 1) AS pct_score,
         qa.passed,
         qa.started_at,
         qa.submitted_at,
         COALESCE(qa.focus_lost_count, 0)  AS focus_lost,
         COALESCE(qa.fullscreen_exits, 0)  AS fullscreen_exits,
         COALESCE(qa.clipboard_events, 0)  AS clipboard_events
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       ORDER BY qa.started_at DESC
       LIMIT 5000`
    )
    rows = result.rows
  } finally {
    client.release()
  }

  const header = [
    'student_id', 'exam_code', 'exam_title', 'status',
    'pct_score', 'passed', 'started_at', 'submitted_at',
    'focus_lost', 'fullscreen_exits', 'clipboard_events',
  ].join(',')

  const csvRows = rows.map((r) =>
    [
      `"${r.student_id}"`,
      `"${r.exam_code}"`,
      `"${r.exam_title}"`,
      r.status,
      r.pct_score ?? '',
      r.passed ?? '',
      r.started_at ? new Date(r.started_at).toISOString() : '',
      r.submitted_at ? new Date(r.submitted_at).toISOString() : '',
      r.focus_lost,
      r.fullscreen_exits,
      r.clipboard_events,
    ].join(',')
  )

  const csv = [header, ...csvRows].join('\n')
  const filename = `evalos-attempts-${new Date().toISOString().slice(0, 10)}.csv`

  return new NextResponse(csv, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
    },
  })
}
