import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { randomUUID, createHmac, timingSafeEqual } from 'crypto'
import { Kafka, CompressionTypes } from 'kafkajs'
import { consentAllowed } from '@/lib/consent-breaker'

export const dynamic = 'force-dynamic'

// HMAC-SHA256 validation for inbound Brevo webhook callbacks.
// Set BREVO_WEBHOOK_SECRET to the shared secret configured in the Brevo dashboard.
// If the header is present but invalid → 401. If the header is absent → fall through
// to session-based auth (UI callers do not supply the header).
const BREVO_WEBHOOK_SECRET = process.env.BREVO_WEBHOOK_SECRET ?? ''

/**
 * Validate a Brevo webhook request using HMAC-SHA256.
 * Brevo sends the signature as a hex digest in X-Brevo-Signature.
 * We consume the raw request body bytes here and return them so the
 * downstream handler can deserialise without re-reading the stream.
 *
 * @returns { valid: true, rawBody } on success
 * @returns { valid: false } on signature mismatch or missing secret
 */
async function validateBrevoSignature(
  req: NextRequest,
): Promise<{ valid: true; rawBody: ArrayBuffer } | { valid: false }> {
  const sig = req.headers.get('x-brevo-signature')
  if (!sig) return { valid: false }

  if (!BREVO_WEBHOOK_SECRET) {
    console.error('[webhook] BREVO_WEBHOOK_SECRET is not set — rejecting signed request')
    return { valid: false }
  }

  const rawBody = await req.arrayBuffer()
  const expected = createHmac('sha256', BREVO_WEBHOOK_SECRET)
    .update(new Uint8Array(rawBody))
    .digest('hex')

  const sigBuf      = Buffer.from(sig,      'utf8')
  const expectedBuf = Buffer.from(expected, 'utf8')

  if (sigBuf.length !== expectedBuf.length) return { valid: false }
  if (!timingSafeEqual(sigBuf, expectedBuf)) return { valid: false }

  return { valid: true, rawBody }
}

const LITELLM_URL        = process.env.LITELLM_URL ?? ''
const LITELLM_KEY        = process.env.LITELLM_KEY ?? ''
const BREVO_KEY          = process.env.BREVO_API_KEY ?? ''
// Consent service (STEP-P2-02) — in-cluster DNS resolved at runtime
const CONSENT_SERVICE_URL = process.env.CONSENT_SERVICE_URL
  ?? 'http://consent-service.i3-consent.svc.cluster.local:8000'
// Default tenant for Engage; callers may override via env var
const ENGAGE_TENANT_ID   = process.env.ENGAGE_TENANT_ID
  ?? '00000000-0000-0000-0000-000000000003'

// Feature flag: set ASYNC_CAMPAIGN_SEND=true to use Kafka-backed async path.
// Set false (or unset) to revert to the synchronous path during rollout.
const ASYNC_CAMPAIGN_SEND = process.env.ASYNC_CAMPAIGN_SEND === 'true'

const KAFKA_BOOTSTRAP = process.env.KAFKA_BOOTSTRAP
  ?? 'kafka-bootstrap.i3-messaging.svc.cluster.local:9092'

// CloudEvent type for campaign trigger (FIX-11)
const CE_TYPE_CAMPAIGN_TRIGGERED = 'i3.engage.campaign.triggered'
const CE_SOURCE                  = 'i3/engage-send-api'

// Lazy-initialised Kafka producer — shared across requests in the same worker.
let _kafkaProducer: ReturnType<InstanceType<typeof Kafka>['producer']> | null = null

async function getKafkaProducer() {
  if (!_kafkaProducer) {
    const kafka = new Kafka({ clientId: 'engage-send-api', brokers: [KAFKA_BOOTSTRAP] })
    _kafkaProducer = kafka.producer()
    await _kafkaProducer.connect()
  }
  return _kafkaProducer
}

/**
 * Build a 9-field CloudEvent envelope (FIX-01 / FIX-11).
 * All fields mandated by the i3 platform schema skill are present.
 */
function buildCloudEvent(
  eventType: string,
  subject: string,
  tenantId: string,
  data: Record<string, unknown>,
  correlationId: string,
  causationId: string | null,
  actor: string | null,
): Record<string, unknown> {
  return {
    specversion:     '1.0',
    id:              randomUUID(),        // UUIDv4 — upgrade to UUIDv7 when available in Node
    source:          CE_SOURCE,
    type:            eventType,
    datacontenttype: 'application/json',
    time:            new Date().toISOString(),
    tenantid:        tenantId,           // HC-4
    subject,
    data: {
      ...data,
      correlation_id: correlationId,
      causation_id:   causationId ?? null,
      actor:          actor ?? null,
    },
  }
}

/**
 * Check consent for a given subject (HMAC-SHA256 of email) before dispatch.
 * Routes through the shared circuit-breaker so that a consent-service outage
 * trips the breaker after FAILURE_THRESHOLD failures, returning false (default-deny)
 * immediately on subsequent calls instead of waiting 5s per contact.
 */
async function checkEmailConsent(subjectIdHash: string): Promise<boolean> {
  return consentAllowed(CONSENT_SERVICE_URL, subjectIdHash, 'email', 'marketing', ENGAGE_TENANT_ID)
}

async function sendViaBrevo(to: string, subject: string, html: string, fromName: string, fromEmail: string) {
  const resp = await fetch('https://api.brevo.com/v3/smtp/email', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'api-key': BREVO_KEY,
    },
    body: JSON.stringify({
      sender:  { name: fromName, email: fromEmail },
      to:      [{ email: to }],
      subject,
      htmlContent: html,
    }),
  })
  if (!resp.ok) throw new Error(`Brevo ${resp.status}: ${await resp.text()}`)
  return await resp.json()
}

async function generatePersonalisedContent(template: string, contact: Record<string, unknown>): Promise<string> {
  if (!LITELLM_URL || !LITELLM_KEY) return template

  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${LITELLM_KEY}` },
    body: JSON.stringify({
      model: 'qwen-fast',
      messages: [{
        role: 'user',
        content: `Personalise this email for the contact. Keep the same message and CTA.
Contact: ${JSON.stringify(contact)}
Template: ${template}
Return ONLY the personalised HTML email body, nothing else.`,
      }],
      temperature: 0.6,
      max_tokens: 600,
    }),
    signal: AbortSignal.timeout(30_000),
  })
  if (!resp.ok) return template
  const data = await resp.json()
  return data.choices?.[0]?.message?.content ?? template
}

export async function POST(req: NextRequest) {
  // ── Auth: webhook (HMAC) or UI session ──────────────────────────────────────
  // Read the raw body once here so we can both verify the signature and
  // deserialise JSON without consuming the stream twice.
  let parsedBody: Record<string, unknown>
  let tenantId: string = ENGAGE_TENANT_ID
  const brevoSig = req.headers.get('x-brevo-signature')

  if (brevoSig !== null) {
    // Inbound Brevo webhook: must carry a valid HMAC-SHA256 signature.
    const check = await validateBrevoSignature(req)
    if (!check.valid) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }
    // Deserialise from the already-consumed raw bytes (stream cannot be re-read).
    parsedBody = JSON.parse(Buffer.from(check.rawBody).toString('utf8')) as Record<string, unknown>
    // Webhook calls do not carry a session — tenantId stays as default.
  } else {
    // UI caller: must have a valid session.
    const session = await getServerSession(authOptions)
    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    tenantId = (session.user as { tenant_id?: string })?.tenant_id ?? ENGAGE_TENANT_ID
    parsedBody = await req.json() as Record<string, unknown>
  }

  const body = parsedBody
  const { campaign_id, send_now = false, schedule_at = null } = body

  if (!campaign_id) return NextResponse.json({ error: 'campaign_id required' }, { status: 400 })

  const client = await pool.connect()
  try {
    // Set RLS session variable for all queries in this request (STEP-P2-05 / HC-4)
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    // Fetch campaign details
    const { rows: campaigns } = await client.query(
      'SELECT * FROM email_campaigns WHERE id = $1',
      [campaign_id]
    )
    if (campaigns.length === 0) return NextResponse.json({ error: 'Campaign not found' }, { status: 404 })
    const campaign = campaigns[0]

    if (campaign.status === 'sent') {
      return NextResponse.json({ error: 'Campaign already sent' }, { status: 409 })
    }

    // Fetch subscribed contacts count for the target list
    const { rows: countRows } = await client.query(
      `SELECT COUNT(*) AS cnt FROM contacts WHERE subscribed = true AND $1 = ANY(list_ids)`,
      [campaign.list_id]
    )
    const estimatedRecipients = parseInt(countRows[0].cnt, 10)

    if (!send_now) {
      // Schedule for later — just update status
      await client.query(
        'UPDATE email_campaigns SET status = $1, scheduled_at = $2 WHERE id = $3',
        ['scheduled', schedule_at, campaign_id]
      )
      return NextResponse.json({ scheduled: true, recipients: estimatedRecipients })
    }

    // ── Async path (STEP-P3-02): feature-flagged via ASYNC_CAMPAIGN_SEND ──────
    if (ASYNC_CAMPAIGN_SEND) {
      const jobId      = randomUUID()
      const sendJobId  = randomUUID()
      const correlationId = randomUUID()  // FIX-06: trace ID propagated into CloudEvent
      // FIX-06: extract actor (Keycloak sub) from session — never null in authenticated path
      const actor = (session.user as { sub?: string; id?: string })?.sub
        ?? (session.user as { sub?: string; id?: string })?.id
        ?? null

      // Persist initial job status so the polling endpoint can answer immediately
      await client.query(
        `INSERT INTO campaign_send_jobs (id, campaign_id, tenant_id, status, estimated_recipients, created_at)
         VALUES ($1, $2, $3, 'queued', $4, NOW())`,
        [jobId, campaign_id, tenantId, estimatedRecipients]
      )

      // Update campaign to 'queued' (not yet 'sent')
      await client.query(
        `UPDATE email_campaigns SET status = 'queued' WHERE id = $1`,
        [campaign_id]
      )

      // FIX-01 / FIX-06 / FIX-11: produce full CloudEvent envelope with
      // correlation_id, actor, specversion, source, type, tenantid, subject.
      const producer = await getKafkaProducer()
      const ce = buildCloudEvent(
        CE_TYPE_CAMPAIGN_TRIGGERED,
        `campaign/${campaign_id}`,
        tenantId,
        {
          job_id:       jobId,
          campaign_id,
          tenant_id:    tenantId,
          send_job_id:  sendJobId,
          triggered_at: new Date().toISOString(),
          retry_count:  0,
        },
        correlationId,
        null,   // no causation_id at the HTTP origin
        actor,
      )
      await producer.send({
        topic: 'engage.campaign-trigger',
        compression: CompressionTypes.GZIP,
        messages: [{ key: jobId, value: JSON.stringify(ce) }],
      })

      return NextResponse.json(
        { job_id: jobId, status: 'queued', estimated_recipients: estimatedRecipients, correlation_id: correlationId },
        { status: 202 }
      )
    }

    // ── Synchronous path (legacy / feature flag off) ───────────────────────────
    const { rows: contacts } = await client.query(
      `SELECT id, email, subject_id_hash, first_name, last_name, company
       FROM contacts
       WHERE subscribed = true AND $1 = ANY(list_ids)`,
      [campaign.list_id]
    )

    const batchId = randomUUID()
    let sent = 0; let failed = 0

    for (const contact of contacts) {
      try {
        // Verify consent before dispatching to this contact (STEP-P2-02).
        // subject_id_hash MUST be the HMAC-SHA256(email, MEMBER_HMAC_SECRET) column.
        // HC-6: raw email MUST NOT be sent to the consent service — fail hard if missing.
        const subjectHash: string | undefined = contact.subject_id_hash as string | undefined
        if (!subjectHash) {
          // HC-6 violation: contact was not migrated to HMAC column; skip with error record.
          failed++
          await client.query(
            `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, error, sent_at)
             VALUES ($1, $2, $3, 'skipped', $4, NOW())`,
            [campaign_id, contact.id, batchId, 'missing_subject_id_hash_hc6']
          )
          continue
        }
        const consentAllowed = await checkEmailConsent(subjectHash)
        if (!consentAllowed) {
          failed++
          await client.query(
            `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, error, sent_at)
             VALUES ($1, $2, $3, 'skipped', $4, NOW())`,
            [campaign_id, contact.id, batchId, 'consent_denied']
          )
          continue
        }

        const personalised = await generatePersonalisedContent(
          campaign.html_template,
          { first_name: contact.first_name, last_name: contact.last_name, email: contact.email, company: contact.company }
        )
        await sendViaBrevo(
          contact.email,
          campaign.subject,
          personalised,
          campaign.from_name,
          campaign.from_email,
        )
        await client.query(
          `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, sent_at)
           VALUES ($1, $2, $3, 'sent', NOW())`,
          [campaign_id, contact.id, batchId]
        )
        sent++
      } catch (err) {
        failed++
        await client.query(
          `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, error, sent_at)
           VALUES ($1, $2, $3, 'failed', $4, NOW())`,
          [campaign_id, contact.id, batchId, String(err)]
        )
      }
    }

    await client.query(
      `UPDATE email_campaigns SET status = 'sent', sent_at = NOW() WHERE id = $1`,
      [campaign_id]
    )

    return NextResponse.json({ sent, failed, batch_id: batchId })
  } finally {
    client.release()
  }
}
