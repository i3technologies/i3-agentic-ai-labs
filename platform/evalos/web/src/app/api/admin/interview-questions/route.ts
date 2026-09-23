import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

function isAdmin(session: { user: { roles?: string[] } }): boolean {
  return session.user.roles?.includes('admin') ?? false
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session || !isAdmin(session)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'
  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)
    const { rows } = await client.query(
      `SELECT id, text, type, language, time_limit, sort_order, is_active, created_at
       FROM ai_interview_questions
       ORDER BY sort_order, created_at`
    )
    return NextResponse.json({ questions: rows })
  } finally {
    client.release()
  }
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session || !isAdmin(session)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await req.json()
  const { text, type, language, rubric, time_limit, sort_order } = body

  if (!text?.trim() || !type) {
    return NextResponse.json({ error: 'text and type are required' }, { status: 400 })
  }
  if (!['text', 'code'].includes(type)) {
    return NextResponse.json({ error: 'type must be "text" or "code"' }, { status: 400 })
  }

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'
  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)
    const { rows } = await client.query(
      `INSERT INTO ai_interview_questions
         (text, type, language, rubric, time_limit, sort_order, is_active, tenant_id, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, true, $7, NOW())
       RETURNING *`,
      [text.trim(), type, language ?? null, rubric ?? '', time_limit ?? 600, sort_order ?? 99, tenantId]
    )
    return NextResponse.json({ question: rows[0] }, { status: 201 })
  } finally {
    client.release()
  }
}

export async function PATCH(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session || !isAdmin(session)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await req.json()
  const { id, is_active, sort_order } = body
  if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 })

  const updates: string[] = []
  const params: unknown[]  = []
  let p = 1

  if (typeof is_active === 'boolean') { updates.push(`is_active = $${p++}`);  params.push(is_active) }
  if (typeof sort_order === 'number') { updates.push(`sort_order = $${p++}`); params.push(sort_order) }

  if (updates.length === 0) return NextResponse.json({ error: 'Nothing to update' }, { status: 400 })

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'
  params.push(id)
  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)
    const { rows } = await client.query(
      `UPDATE ai_interview_questions SET ${updates.join(', ')} WHERE id = $${p} RETURNING *`,
      params
    )
    if (rows.length === 0) return NextResponse.json({ error: 'Not found' }, { status: 404 })
    return NextResponse.json({ question: rows[0] })
  } finally {
    client.release()
  }
}

export async function DELETE(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session || !isAdmin(session)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const { searchParams } = new URL(req.url)
  const id = searchParams.get('id')
  if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 })

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'
  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)
    await client.query('DELETE FROM ai_interview_questions WHERE id = $1', [id])
    return NextResponse.json({ deleted: true })
  } finally {
    client.release()
  }
}
