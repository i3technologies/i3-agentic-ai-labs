import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const page  = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10))
  const limit = 20
  const offset = (page - 1) * limit

  const { rows } = await pool.query(
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
  const { rows: countRows } = await pool.query('SELECT COUNT(*)::int AS total FROM campaigns')

  return NextResponse.json({ campaigns: rows, total: countRows[0].total, page })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const { name, description, start_date, end_date, budget_kes } = body

  if (!name?.trim()) return NextResponse.json({ error: 'Name required' }, { status: 400 })

  const { rows } = await pool.query(
    `INSERT INTO campaigns (name, description, start_date, end_date, budget_kes, status, created_at)
     VALUES ($1, $2, $3, $4, $5, 'draft', NOW())
     RETURNING *`,
    [name.trim(), description ?? '', start_date ?? null, end_date ?? null, budget_kes ?? 0]
  )

  // Log activity
  await pool.query(
    `INSERT INTO campaign_activity (type, description, created_at) VALUES ($1, $2, NOW())`,
    ['campaign_created', `Campaign "${rows[0].name}" created`]
  )

  return NextResponse.json({ campaign: rows[0] }, { status: 201 })
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const { id, status } = body
  if (!id || !status) return NextResponse.json({ error: 'id and status required' }, { status: 400 })

  const validStatuses = ['draft', 'active', 'paused', 'completed']
  if (!validStatuses.includes(status)) {
    return NextResponse.json({ error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` }, { status: 400 })
  }

  const { rows } = await pool.query(
    `UPDATE campaigns SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING *`,
    [status, id]
  )
  if (rows.length === 0) return NextResponse.json({ error: 'Campaign not found' }, { status: 404 })

  return NextResponse.json({ campaign: rows[0] })
}
