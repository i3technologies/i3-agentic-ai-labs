import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const page   = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10))
  const search = searchParams.get('q') ?? ''
  const list   = searchParams.get('list') ?? ''
  const limit  = 50
  const offset = (page - 1) * limit

  const conditions: string[] = []
  const params: unknown[]    = [limit, offset]
  let p = 3

  if (search) { conditions.push(`(c.email ILIKE $${p} OR c.first_name ILIKE $${p} OR c.last_name ILIKE $${p})`); params.push(`%${search}%`); p++ }
  if (list)   { conditions.push(`$${p} = ANY(c.list_ids)`);   params.push(list);   p++ }

  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''

  const { rows } = await pool.query(
    `SELECT c.id, c.email, c.first_name, c.last_name, c.company,
            c.subscribed, c.created_at, c.tags,
            COUNT(e.id)::int AS event_count
     FROM contacts c
     LEFT JOIN contact_events e ON e.contact_id = c.id::text
     ${where}
     GROUP BY c.id
     ORDER BY c.created_at DESC
     LIMIT $1 OFFSET $2`,
    params
  )
  const { rows: countRows } = await pool.query(`SELECT COUNT(*)::int AS total FROM contacts c ${where}`, params.slice(2))

  return NextResponse.json({ contacts: rows, total: countRows[0].total, page })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const { email, first_name, last_name, company, tags } = body

  if (!email?.trim()) return NextResponse.json({ error: 'Email required' }, { status: 400 })

  const { rows } = await pool.query(
    `INSERT INTO contacts (email, first_name, last_name, company, tags, subscribed, created_at)
     VALUES ($1, $2, $3, $4, $5, true, NOW())
     ON CONFLICT (email) DO UPDATE SET
       first_name = EXCLUDED.first_name,
       last_name  = EXCLUDED.last_name,
       company    = EXCLUDED.company,
       tags       = EXCLUDED.tags
     RETURNING *`,
    [email.trim().toLowerCase(), first_name ?? '', last_name ?? '', company ?? '', tags ?? []]
  )

  return NextResponse.json({ contact: rows[0] }, { status: 201 })
}
