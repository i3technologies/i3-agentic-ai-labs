import { createHmac, timingSafeEqual } from 'crypto'
import { NextRequest, NextResponse } from 'next/server'
import pool from '@/lib/db'

/**
 * WhatsApp webhook for Brevo / Meta Cloud API
 *
 * GET  /webhook/whatsapp  — verification handshake (hub.challenge)
 * POST /webhook/whatsapp  — inbound message / status update
 */

const VERIFY_TOKEN = process.env.WHATSAPP_VERIFY_TOKEN || 'i3-engage-webhook-2026'

// ── HMAC-SHA256 signature validation (HC-2 audit finding H-1) ───────────────
function verifyWhatsAppSignature(rawBody: Buffer, signature: string | null, secret: string): boolean {
  if (!signature) return false
  const expected = 'sha256=' + createHmac('sha256', secret).update(rawBody).digest('hex')
  try {
    return timingSafeEqual(Buffer.from(signature), Buffer.from(expected))
  } catch {
    // Buffer lengths differ — signature is structurally invalid
    return false
  }
}

// ── GET: Meta webhook verification ──────────────────────────────────────────
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const mode      = searchParams.get('hub.mode')
  const token     = searchParams.get('hub.verify_token')
  const challenge = searchParams.get('hub.challenge')

  if (mode === 'subscribe' && token === VERIFY_TOKEN) {
    console.log('[webhook/whatsapp] Verification OK')
    return new NextResponse(challenge, { status: 200 })
  }
  return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
}

// ── POST: inbound messages / delivery receipts ───────────────────────────────
export async function POST(req: NextRequest) {
  // ── Signature validation — must run before body parsing ──────────────────
  const appSecret = process.env.WHATSAPP_APP_SECRET
  if (!appSecret) {
    console.error('[webhook/whatsapp] WHATSAPP_APP_SECRET not configured')
    return NextResponse.json({ error: 'Server misconfiguration' }, { status: 500 })
  }

  const signature = req.headers.get('x-hub-signature-256')
  const rawBody = Buffer.from(await req.arrayBuffer())

  if (!verifyWhatsAppSignature(rawBody, signature, appSecret)) {
    console.warn('[webhook/whatsapp] Invalid or missing X-Hub-Signature-256')
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 })
  }

  let body: any
  try {
    body = JSON.parse(rawBody.toString('utf-8'))
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  try {
    // Handle Meta Cloud API format
    const entry = body?.entry?.[0]
    const changes = entry?.changes?.[0]
    const value = changes?.value

    if (value?.messages?.length) {
      const msg = value.messages[0]
      const from = msg.from        // WhatsApp phone number
      const text = msg.text?.body || msg.type
      const msgId = msg.id
      const ts = new Date(parseInt(msg.timestamp) * 1000)

      console.log(`[webhook/whatsapp] Message from ${from}: ${text}`)

      // Persist inbound message to engage_db
      await pool.query(
        `INSERT INTO inbound_messages (message_id, channel, sender, content, received_at)
         VALUES ($1, 'whatsapp', $2, $3, $4)
         ON CONFLICT (message_id) DO NOTHING`,
        [msgId, from, text, ts]
      )
    }

    // Handle Brevo webhook format (alternative)
    if (body?.event && body?.messageId) {
      const { event, messageId, email, date } = body
      console.log(`[webhook/whatsapp] Brevo event: ${event} for ${email}`)
      await pool.query(
        `INSERT INTO webhook_events (event_type, message_id, recipient, event_data, received_at)
         VALUES ($1, $2, $3, $4, NOW())
         ON CONFLICT DO NOTHING`,
        [event, messageId, email || '', JSON.stringify(body)]
      )
    }

    return NextResponse.json({ status: 'ok' }, { status: 200 })
  } catch (err: any) {
    // Log but always return 200 to avoid webhook retry storms
    console.error('[webhook/whatsapp] Error:', err?.message)
    return NextResponse.json({ status: 'ok', warning: 'logged' }, { status: 200 })
  }
}
