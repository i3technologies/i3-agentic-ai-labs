import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { rows } = await pool.query(`
    SELECT s.*, c.email AS contact_email
    FROM sms_messages s
    LEFT JOIN contacts c ON c.id = s.contact_id
    ORDER BY s.created_at DESC
    LIMIT 100
  `)
  return NextResponse.json({ messages: rows })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { phone, content } = await req.json()
  if (!phone?.trim())   return NextResponse.json({ error: 'Phone required' },   { status: 400 })
  if (!content?.trim()) return NextResponse.json({ error: 'Content required' }, { status: 400 })

  const AT_KEY  = process.env.AT_API_KEY  ?? ''
  const AT_USER = process.env.AT_USERNAME ?? ''

  let status = 'pending'
  let providerId: string | null = null

  if (AT_KEY && AT_KEY !== 'REPLACE_WITH_AT_API_KEY') {
    try {
      const body = new URLSearchParams({
        username: AT_USER,
        to:       phone.trim(),
        message:  content.trim(),
      })
      const resp = await fetch('https://api.africastalking.com/version1/messaging', {
        method: 'POST',
        headers: { apiKey: AT_KEY, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
        signal: AbortSignal.timeout(15_000),
      })
      if (resp.ok) {
        const d = await resp.json()
        providerId = d.SMSMessageData?.Recipients?.[0]?.messageId ?? null
        status = 'sent'
      }
    } catch {
      status = 'failed'
    }
  }

  const { rows } = await pool.query(
    `INSERT INTO sms_messages (provider, provider_message_id, content, status, created_at)
     VALUES ('africastalking', $1, $2, $3, NOW()) RETURNING *`,
    [providerId, content.trim(), status]
  )

  return NextResponse.json({ message: rows[0] }, { status: 201 })
}
