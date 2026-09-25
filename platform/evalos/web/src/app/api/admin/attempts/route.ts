import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  if (!session.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const tenantId = (session.user as { tenant_id?: string }).tenant_id || '00000000-0000-0000-0000-000000000002'

  // Pagination: ?page=1&limit=100  (max 500 per page)
  const { searchParams } = new URL(req.url)
  const page   = Math.max(1, parseInt(searchParams.get('page')  ?? '1',   10))
  const limit  = Math.min(500, Math.max(1, parseInt(searchParams.get('limit') ?? '100', 10)))
  const offset = (page - 1) * limit

  const client = await pool.connect()
  try {
    // HC-4: set RLS session variable before any tenant-scoped query
    await setTenantContext(client, tenantId)

    const { rows } = await client.query(
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
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    )

    const { rows: countRows } = await client.query(
      `SELECT COUNT(*)::int AS total FROM quiz_attempts`
    )

    return NextResponse.json({
      data: rows,
      pagination: {
        page,
        limit,
        total: countRows[0]?.total ?? 0,
        pages: Math.ceil((countRows[0]?.total ?? 0) / limit),
      },
    })
  } finally {
    client.release()
  }
}
