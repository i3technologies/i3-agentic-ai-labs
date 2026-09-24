import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const DEFAULT_TENANT_ID = process.env.ENGAGE_TENANT_ID ?? '00000000-0000-0000-0000-000000000003'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
  const client = await pool.connect()
  try {
    // Set RLS session variable (STEP-P2-05 / HC-4)
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows } = await client.query(`
      SELECT ec.*, cl.name AS list_name
      FROM email_campaigns ec
      LEFT JOIN contact_lists cl ON cl.id = ec.list_id
      ORDER BY ec.created_at DESC
    `)
    return NextResponse.json({ campaigns: rows })
  } finally {
    client.release()
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
  const body = await req.json()
  const { name, subject, html_template, from_name, from_email, list_id, ai_personalise } = body

  if (!name?.trim())          return NextResponse.json({ error: 'Name required' },     { status: 400 })
  if (!subject?.trim())       return NextResponse.json({ error: 'Subject required' },  { status: 400 })
  if (!html_template?.trim()) return NextResponse.json({ error: 'Template required' }, { status: 400 })

  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows } = await client.query(
      `INSERT INTO email_campaigns
         (name, subject, html_template, from_name, from_email, list_id, ai_personalise, tenant_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *`,
      [
        name.trim(), subject.trim(), html_template,
        from_name  ?? 'i3 Engage',
        from_email ?? 'hello@i3technologies.co.ke',
        list_id    || null,
        ai_personalise ?? false,
        tenantId,
      ]
    )
    return NextResponse.json({ campaign: rows[0] }, { status: 201 })
  } finally {
    client.release()
  }
}
