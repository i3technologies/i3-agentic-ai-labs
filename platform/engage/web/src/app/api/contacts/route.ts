import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { createHmac, timingSafeEqual } from 'crypto'

// HC-6: MEMBER_HMAC_SECRET injected from OpenBao/env — never raw SHA-256 on PII.
const MEMBER_HMAC_SECRET = process.env.MEMBER_HMAC_SECRET ?? ''

/**
 * Compute HMAC-SHA256(LOWERCASE(email), MEMBER_HMAC_SECRET) hex digest (HC-6).
 * Used as subject_id_hash for consent checks; raw email is never forwarded to
 * the consent service or stored as a lookup key.
 */
function hmacSubjectId(email: string): string {
  if (!MEMBER_HMAC_SECRET) {
    throw new Error('MEMBER_HMAC_SECRET is not set — cannot compute subject_id_hash (HC-6)')
  }
  return createHmac('sha256', MEMBER_HMAC_SECRET)
    .update(email.trim().toLowerCase())
    .digest('hex')
}

export const dynamic = 'force-dynamic'

const DEFAULT_TENANT_ID = process.env.ENGAGE_TENANT_ID ?? '00000000-0000-0000-0000-000000000003'

// HMAC-SHA256 validation for inbound contact-event webhook callbacks.
// Set CONTACTS_WEBHOOK_SECRET to the shared secret agreed with the upstream provider.
// Header: X-Webhook-Signature (hex-encoded HMAC-SHA256 of the raw request body).
const CONTACTS_WEBHOOK_SECRET = process.env.CONTACTS_WEBHOOK_SECRET ?? ''

/**
 * Validate an inbound contact-event webhook request.
 * Reads raw bytes from the stream (must be called before any body parsing) and
 * compares HMAC digests with crypto.timingSafeEqual to prevent timing attacks.
 *
 * @returns { valid: true, rawBody } when the signature is correct
 * @returns { valid: false } on mismatch, missing header, or unconfigured secret
 */
async function validateContactWebhookSignature(
  req: NextRequest,
): Promise<{ valid: true; rawBody: ArrayBuffer } | { valid: false }> {
  const sig = req.headers.get('x-webhook-signature')
  if (!sig) return { valid: false }

  if (!CONTACTS_WEBHOOK_SECRET) {
    console.error('[webhook] CONTACTS_WEBHOOK_SECRET is not set — rejecting signed request')
    return { valid: false }
  }

  const rawBody = await req.arrayBuffer()
  const expected = createHmac('sha256', CONTACTS_WEBHOOK_SECRET)
    .update(new Uint8Array(rawBody))
    .digest('hex')

  const sigBuf      = Buffer.from(sig,      'utf8')
  const expectedBuf = Buffer.from(expected, 'utf8')

  if (sigBuf.length !== expectedBuf.length) return { valid: false }
  if (!timingSafeEqual(sigBuf, expectedBuf)) return { valid: false }

  return { valid: true, rawBody }
}

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const tenantId: string = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
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

  const client = await pool.connect()
  try {
    // Set RLS session variable (STEP-P2-05 / HC-4)
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows } = await client.query(
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
    const { rows: countRows } = await client.query(
      `SELECT COUNT(*)::int AS total FROM contacts c ${where}`,
      params.slice(2)
    )
    return NextResponse.json({ contacts: rows, total: countRows[0].total, page })
  } finally {
    client.release()
  }
}

export async function POST(req: NextRequest) {
  // ── Auth: webhook (HMAC) or UI session ──────────────────────────────────────
  // Consume raw bytes once to support both signature verification and JSON parsing.
  let parsedBody: Record<string, unknown>
  let tenantId: string = DEFAULT_TENANT_ID
  const webhookSig = req.headers.get('x-webhook-signature')

  if (webhookSig !== null) {
    // Inbound contact-event webhook: validate HMAC-SHA256 signature first.
    const check = await validateContactWebhookSignature(req)
    if (!check.valid) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    // Parse from the already-consumed bytes — the stream cannot be re-read.
    parsedBody = JSON.parse(Buffer.from(check.rawBody).toString('utf8')) as Record<string, unknown>
    // Webhook callers do not carry a session; tenantId stays as default.
  } else {
    // UI caller: session required.
    const session = await getServerSession(authOptions)
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    tenantId  = (session.user as { tenant_id?: string })?.tenant_id ?? DEFAULT_TENANT_ID
    parsedBody = await req.json() as Record<string, unknown>
  }

  const body = parsedBody
  const { email, first_name, last_name, company, tags } = body

  if (!email?.trim()) return NextResponse.json({ error: 'Email required' }, { status: 400 })

  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    // HC-6: compute keyed HMAC before any DB write — raw email must not be the lookup key.
    const subjectIdHash = hmacSubjectId(email as string)

    const { rows } = await client.query(
      `INSERT INTO contacts (email, first_name, last_name, company, tags, subscribed, created_at, tenant_id, subject_id_hash)
       VALUES ($1, $2, $3, $4, $5, true, NOW(), $6, $7)
       ON CONFLICT (email) DO UPDATE SET
         first_name      = EXCLUDED.first_name,
         last_name       = EXCLUDED.last_name,
         company         = EXCLUDED.company,
         tags            = EXCLUDED.tags,
         subject_id_hash = EXCLUDED.subject_id_hash
       RETURNING *`,
      [email.trim().toLowerCase(), first_name ?? '', last_name ?? '', company ?? '', tags ?? [], tenantId, subjectIdHash]
    )
    return NextResponse.json({ contact: rows[0] }, { status: 201 })
  } finally {
    client.release()
  }
}
