import { NextResponse } from 'next/server'
import { createHmac, timingSafeEqual } from 'crypto'
import { z } from 'zod'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

// ── Inbound webhook validation ────────────────────────────────────────────────
// Admissions service signs requests with HMAC-SHA256 using ADMISSIONS_WEBHOOK_SECRET.
// Header: X-Hub-Signature-256: sha256=<hex>
const ADMISSIONS_WEBHOOK_SECRET = process.env.ADMISSIONS_WEBHOOK_SECRET ?? ''
const DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000002'

// ── Inbound payload schema ─────────────────────────────────────────────────────
// The admissions service sends CandidateInvited events to trigger assessment start.
const CandidateInvitedSchema = z.object({
  event: z.literal('CANDIDATE_INVITED'),
  applicant_id: z.string().min(1),
  tenant_id: z.string().uuid().optional(),
  exam_id: z.string().uuid().optional(),
  exam_code: z.string().optional(),
  candidate_email: z.string().email(),
  candidate_name: z.string().optional(),
  deadline_at: z.string().datetime().optional(),
  metadata: z.record(z.unknown()).optional(),
})

type CandidateInvited = z.infer<typeof CandidateInvitedSchema>

// ── HMAC signature verification ───────────────────────────────────────────────
function verifySignature(rawBody: string, signatureHeader: string | null): boolean {
  if (!ADMISSIONS_WEBHOOK_SECRET) {
    // If secret not configured, skip verification (development only)
    console.warn('[admissions-webhook] ADMISSIONS_WEBHOOK_SECRET not set — skipping signature check')
    return true
  }
  if (!signatureHeader?.startsWith('sha256=')) return false
  const expected = createHmac('sha256', ADMISSIONS_WEBHOOK_SECRET)
    .update(rawBody, 'utf8')
    .digest('hex')
  const provided = signatureHeader.slice(7)
  try {
    return timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(provided, 'hex'))
  } catch {
    return false
  }
}

// ── POST /api/admissions/webhook — inbound from admissions service ─────────────
export async function POST(req: Request) {
  const rawBody = await req.text()
  const signature = req.headers.get('x-hub-signature-256')

  if (!verifySignature(rawBody, signature)) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 })
  }

  let body: unknown
  try {
    body = JSON.parse(rawBody)
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const parsed = CandidateInvitedSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid payload', details: parsed.error.flatten() },
      { status: 400 }
    )
  }

  const event: CandidateInvited = parsed.data
  const tenantId = event.tenant_id ?? DEFAULT_TENANT_ID

  const client = await pool.connect()
  try {
    // HC-4: set RLS context
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    // Log inbound webhook event for audit trail
    await client.query(
      `INSERT INTO admissions_webhook_log
         (tenant_id, direction, event_type, payload, applicant_id)
       VALUES ($1, 'inbound', $2, $3, $4)`,
      [tenantId, event.event, JSON.stringify(event), event.applicant_id]
    )

    // Resolve exam_id from exam_code if not provided directly
    let resolvedExamId: string | null = event.exam_id ?? null
    if (!resolvedExamId && event.exam_code) {
      const { rows } = await client.query(
        `SELECT id FROM exams WHERE code = $1 AND is_published = true LIMIT 1`,
        [event.exam_code]
      )
      resolvedExamId = rows[0]?.id ?? null
    }

    return NextResponse.json({
      ok: true,
      event: event.event,
      applicant_id: event.applicant_id,
      exam_id: resolvedExamId,
      message: 'Candidate invited — assessment link ready for delivery',
    })
  } finally {
    client.release()
  }
}
