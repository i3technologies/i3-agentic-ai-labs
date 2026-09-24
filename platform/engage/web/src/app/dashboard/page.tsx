import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import pool from '@/lib/db'
import { DashboardClient } from './DashboardClient'

async function getStats() {
  try {
    const [contacts, campaigns, sent, events] = await Promise.all([
      pool.query('SELECT COUNT(*)::int AS n FROM contacts'),
      pool.query('SELECT COUNT(*)::int AS n FROM email_campaigns'),
      pool.query("SELECT COUNT(*)::int AS n FROM email_sends WHERE status='sent'"),
      pool.query(`
        SELECT event_type, COUNT(*)::int AS n
        FROM contact_events
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY event_type
      `),
    ])
    const evMap: Record<string,number> = {}
    for (const r of events.rows) evMap[r.event_type] = r.n

    const [recent, activity] = await Promise.all([
      pool.query(`
        SELECT name, status, sent_at, created_at
        FROM email_campaigns ORDER BY created_at DESC LIMIT 5
      `),
      pool.query(`
        SELECT DATE(created_at)::text AS day, COUNT(*)::int AS sends
        FROM email_sends
        WHERE sent_at > NOW() - INTERVAL '14 days' AND status='sent'
        GROUP BY day ORDER BY day
      `),
    ])
    return {
      totalContacts: contacts.rows[0].n,
      totalCampaigns: campaigns.rows[0].n,
      totalSent: sent.rows[0].n,
      opens: evMap['opened'] ?? 0,
      clicks: evMap['clicked'] ?? 0,
      bounces: evMap['bounced'] ?? 0,
      recentCampaigns: recent.rows,
      activityChart: activity.rows,
    }
  } catch {
    return {
      totalContacts: 0, totalCampaigns: 0, totalSent: 0,
      opens: 0, clicks: 0, bounces: 0,
      recentCampaigns: [], activityChart: [],
    }
  }
}

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  const stats = await getStats()
  return (
    <Shell>
      <DashboardClient stats={stats} userName={session.user?.name ?? 'there'} />
    </Shell>
  )
}
