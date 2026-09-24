import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  try {
    const [eventsByDay, eventsByType, topCampaigns, growth] = await Promise.all([
      pool.query(`
        SELECT
          DATE(created_at)::text AS day,
          COUNT(*) FILTER (WHERE event_type = 'opened')    ::int AS opened,
          COUNT(*) FILTER (WHERE event_type = 'clicked')   ::int AS clicked,
          COUNT(*) FILTER (WHERE event_type = 'bounced')   ::int AS bounced
        FROM contact_events
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY day ORDER BY day
      `),
      pool.query(`
        SELECT event_type, COUNT(*)::int AS n
        FROM contact_events
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY event_type ORDER BY n DESC
      `),
      pool.query(`
        SELECT
          ec.name,
          COUNT(es.id)::int                                       AS sent,
          COUNT(es.id) FILTER (WHERE ce.event_type = 'opened')::int AS opens,
          COUNT(es.id) FILTER (WHERE ce.event_type = 'clicked')::int AS clicks
        FROM email_campaigns ec
        JOIN email_sends es ON es.campaign_id = ec.id
        LEFT JOIN contact_events ce ON ce.contact_id = es.contact_id::text
        WHERE ec.status = 'sent'
        GROUP BY ec.id, ec.name
        ORDER BY opens DESC
        LIMIT 10
      `),
      pool.query(`
        SELECT DATE(created_at)::text AS day, COUNT(*)::int AS new_contacts
        FROM contacts
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY day ORDER BY day
      `),
    ])

    return NextResponse.json({
      eventsByDay:  eventsByDay.rows,
      eventsByType: eventsByType.rows,
      topCampaigns: topCampaigns.rows,
      growth:       growth.rows,
    })
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
