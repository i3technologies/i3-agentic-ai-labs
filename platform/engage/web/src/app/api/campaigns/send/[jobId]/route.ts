import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const ENGAGE_TENANT_ID = process.env.ENGAGE_TENANT_ID
  ?? '00000000-0000-0000-0000-000000000003'

/**
 * GET /api/campaigns/send/{jobId}
 *
 * Polls the status of an async campaign send job created by POST /api/campaigns/send
 * when ASYNC_CAMPAIGN_SEND=true is set.
 *
 * Response schema (STEP-P3-02 interface contract):
 * {
 *   job_id:        UUID,
 *   status:        "queued" | "processing" | "complete" | "failed",
 *   sent:          int,
 *   failed:        int,
 *   started_at?:   ISO8601,
 *   completed_at?: ISO8601
 * }
 */
export async function GET(
  req: NextRequest,
  { params }: { params: { jobId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? ENGAGE_TENANT_ID
  const { jobId } = params

  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows } = await client.query(
      `SELECT id, campaign_id, status, sent, failed, started_at, completed_at
       FROM campaign_send_jobs
       WHERE id = $1 AND tenant_id = $2`,
      [jobId, tenantId]
    )

    if (rows.length === 0) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 })
    }

    const job = rows[0]
    return NextResponse.json({
      job_id:        job.id,
      status:        job.status,
      sent:          job.sent          ?? 0,
      failed:        job.failed        ?? 0,
      started_at:    job.started_at    ?? undefined,
      completed_at:  job.completed_at  ?? undefined,
    })
  } finally {
    client.release()
  }
}
