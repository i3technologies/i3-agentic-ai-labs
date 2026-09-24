import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { rows } = await pool.query(`
    SELECT c.*, 
      COUNT(DISTINCT co.id)::int AS contact_count
    FROM contact_lists c
    LEFT JOIN contacts co ON c.id = ANY(co.list_ids)
    GROUP BY c.id
    ORDER BY c.created_at DESC
  `)
  return NextResponse.json({ lists: rows })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { name, description } = await req.json()
  if (!name?.trim()) return NextResponse.json({ error: 'Name required' }, { status: 400 })

  const { rows } = await pool.query(
    `INSERT INTO contact_lists (name, description) VALUES ($1, $2) RETURNING *`,
    [name.trim(), description ?? '']
  )
  return NextResponse.json({ list: rows[0] }, { status: 201 })
}
