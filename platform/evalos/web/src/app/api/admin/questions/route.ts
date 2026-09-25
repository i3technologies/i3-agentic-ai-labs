import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

interface IncomingQuestion {
  text: string
  type: 'SC' | 'MR'
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_name: string
  topic: string
  set_number: number
  is_active?: boolean
}

// ── GET /api/admin/questions ──────────────────────────────────
// Toggle is_active on a question by ID
// ?id=<uuid>&active=true|false
export async function GET(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const url = new URL(req.url)
  const id = url.searchParams.get('id')
  const active = url.searchParams.get('active')

  if (!id || active === null) {
    return NextResponse.json({ error: 'id and active are required' }, { status: 400 })
  }

  const tenantId = (session.user as { tenant_id?: string }).tenant_id || '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    // HC-4: set RLS session variable
    await setTenantContext(client, tenantId)

    const { rowCount } = await client.query(
      `UPDATE questions SET is_active = $1, updated_at = NOW()
       WHERE id = $2`,
      [active === 'true', id]
    )

    if (rowCount === 0) {
      return NextResponse.json({ error: 'Question not found' }, { status: 404 })
    }

    return NextResponse.json({ ok: true, id, is_active: active === 'true' })
  } finally {
    client.release()
  }
}

// ── POST /api/admin/questions ─────────────────────────────────
// Persist AI-generated questions as inactive drafts.
// Body: { questions: IncomingQuestion[] }
export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  let body: { questions: IncomingQuestion[] }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { questions } = body
  if (!Array.isArray(questions) || questions.length === 0) {
    return NextResponse.json({ error: 'questions array is required' }, { status: 400 })
  }
  if (questions.length > 10) {
    return NextResponse.json({ error: 'Maximum 10 questions per save call' }, { status: 400 })
  }

  const tenantId = (session.user as { tenant_id?: string }).tenant_id || '00000000-0000-0000-0000-000000000002'

  const savedIds: string[] = []
  const client = await pool.connect()

  try {
    // HC-4: set RLS session variable for all queries in this transaction
    await setTenantContext(client, tenantId)

    // Resolve domain_number from domain_name if we can
    const { rows: domainRows } = await client.query<{ domain_name: string; domain_number: number }>(
      `SELECT DISTINCT domain_name, domain_number FROM questions ORDER BY domain_number`
    )
    const domainMap = new Map(domainRows.map(r => [r.domain_name.toLowerCase(), r.domain_number]))

    await client.query('BEGIN')

    for (const q of questions) {
      // Basic validation
      if (!q.text?.trim() || !q.type || !Array.isArray(q.options) || !Array.isArray(q.correct_answers)) {
        continue  // skip malformed questions silently
      }

      const id = randomUUID()
      const domainNumber = domainMap.get(q.domain_name?.toLowerCase()) ?? 1

      await client.query(
        `INSERT INTO questions
           (id, set_number, domain_number, domain_name, topic, text,
            type, options, correct_answers, explanation, is_active,
            ai_generated, tenant_id, created_at, updated_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,NOW(),NOW())`,
        [
          id,
          q.set_number ?? 1,
          domainNumber,
          q.domain_name ?? 'Unknown Domain',
          q.topic ?? '',
          q.text.trim(),
          q.type,
          JSON.stringify(q.options),
          JSON.stringify(q.correct_answers),
          q.explanation?.trim() ?? '',
          false,           // always inactive — requires human review before activation
          true,            // ai_generated flag for audit trail
          tenantId,        // HC-4: tenant isolation
        ]
      )
      savedIds.push(id)
    }

    await client.query('COMMIT')
  } catch (err) {
    await client.query('ROLLBACK')
    console.error('[admin/questions] Save error:', err)
    return NextResponse.json({ error: 'Database error', detail: String(err) }, { status: 500 })
  } finally {
    client.release()
  }

  return NextResponse.json({
    saved: savedIds.length,
    ids: savedIds,
    note: 'Questions saved as inactive drafts. Activate in /admin/questions → filter Inactive only.',
  })
}
