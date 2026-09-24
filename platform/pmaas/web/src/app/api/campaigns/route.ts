import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const DEFAULT_TENANT_ID = process.env.PMAAS_TENANT_ID ?? '00000000-0000-0000-0000-000000000005'

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID

  const { searchParams } = new URL(req.url)
  const page  = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10))
  const limit = 20
  const offset = (page - 1) * limit

  const client = await pool.connect()
  try {
    // HC-4: set RLS tenant context for all queries in this request
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows } = await client.query(
      `SELECT c.id, c.name, c.status, c.start_date, c.end_date,
              c.budget_kes, c.description,
              COUNT(DISTINCT wt.ward_id) AS ward_count
       FROM campaigns c
       LEFT JOIN ward_targets wt ON wt.campaign_id = c.id
       GROUP BY c.id
       ORDER BY c.created_at DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    )
    const { rows: countRows } = await client.query('SELECT COUNT(*)::int AS total FROM campaigns')

    return NextResponse.json({ campaigns: rows, total: countRows[0].total, page })
  } finally {
    client.release()
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
  const body = await req.json()
  const { name, description, start_date, end_date, budget_kes } = body

  if (!name?.trim()) return NextResponse.json({ error: 'Name required' }, { status: 400 })

  const client = await pool.connect()
  try {
    // HC-4: set RLS tenant context
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows } = await client.query(
      `INSERT INTO campaigns (name, description, start_date, end_date, budget_kes, status, tenant_id, created_at)
       VALUES ($1, $2, $3, $4, $5, 'draft', $6, NOW())
       RETURNING *`,
      [name.trim(), description ?? '', start_date ?? null, end_date ?? null, budget_kes ?? 0, tenantId]
    )

    // Log activity (tenant-scoped)
    await client.query(
      `INSERT INTO campaign_activity (type, description, tenant_id, created_at) VALUES ($1, $2, $3, NOW())`,
      ['campaign_created', `Campaign "${rows[0].name}" created`, tenantId]
    )

    return NextResponse.json({ campaign: rows[0] }, { status: 201 })
  } finally {
    client.release()
  }
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
  const body = await req.json()
  const { id, status } = body
  if (!id || !status) return NextResponse.json({ error: 'id and status required' }, { status: 400 })

  const validStatuses = ['draft', 'active', 'paused', 'completed']
  if (!validStatuses.includes(status)) {
    return NextResponse.json({ error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` }, { status: 400 })
  }

  const client = await pool.connect()
  try {
    // HC-4: set RLS tenant context
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows } = await client.query(
      `UPDATE campaigns SET status = $1, updated_at = NOW() WHERE id = $2 AND tenant_id = $3 RETURNING *`,
      [status, id, tenantId]
    )
    if (rows.length === 0) return NextResponse.json({ error: 'Campaign not found' }, { status: 404 })

    return NextResponse.json({ campaign: rows[0] })
  } finally {
    client.release()
  }
}
