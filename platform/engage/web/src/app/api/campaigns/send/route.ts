import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const LITELLM_URL = process.env.LITELLM_URL ?? ''
const LITELLM_KEY = process.env.LITELLM_KEY ?? ''
const BREVO_KEY   = process.env.BREVO_API_KEY ?? ''

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
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const { campaign_id, send_now = false, schedule_at = null } = body

  if (!campaign_id) return NextResponse.json({ error: 'campaign_id required' }, { status: 400 })

  // Fetch campaign details
  const { rows: campaigns } = await pool.query(
    'SELECT * FROM email_campaigns WHERE id = $1',
    [campaign_id]
  )
  if (campaigns.length === 0) return NextResponse.json({ error: 'Campaign not found' }, { status: 404 })
  const campaign = campaigns[0]

  if (campaign.status === 'sent') {
    return NextResponse.json({ error: 'Campaign already sent' }, { status: 409 })
  }

  // Fetch subscribed contacts in the target list
  const { rows: contacts } = await pool.query(
    `SELECT id, email, first_name, last_name, company
     FROM contacts
     WHERE subscribed = true AND $1 = ANY(list_ids)`,
    [campaign.list_id]
  )

  if (!send_now) {
    // Schedule for later — just update status
    await pool.query(
      'UPDATE email_campaigns SET status = $1, scheduled_at = $2 WHERE id = $3',
      ['scheduled', schedule_at, campaign_id]
    )
    return NextResponse.json({ scheduled: true, recipients: contacts.length })
  }

  // Send immediately
  const batchId = randomUUID()
  let sent = 0; let failed = 0

  for (const contact of contacts) {
    try {
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
      await pool.query(
        `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, sent_at)
         VALUES ($1, $2, $3, 'sent', NOW())`,
        [campaign_id, contact.id, batchId]
      )
      sent++
    } catch (err) {
      failed++
      await pool.query(
        `INSERT INTO email_sends (campaign_id, contact_id, batch_id, status, error, sent_at)
         VALUES ($1, $2, $3, 'failed', $4, NOW())`,
        [campaign_id, contact.id, batchId, String(err)]
      )
    }
  }

  await pool.query(
    `UPDATE email_campaigns SET status = 'sent', sent_at = NOW() WHERE id = $1`,
    [campaign_id]
  )

  return NextResponse.json({ sent, failed, batch_id: batchId })
}
