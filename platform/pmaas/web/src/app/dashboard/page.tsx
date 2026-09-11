import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import pool from '@/lib/db'

interface CampaignStats {
  totalVoters:      number
  registeredWards:  number
  activeCampaigns:  number
  daysToElection:   number
  sentimentScore:   number
  volunteersActive: number
}

async function getCampaignStats(): Promise<CampaignStats> {
  try {
    const { rows } = await pool.query(`
      SELECT
        (SELECT COUNT(*) FROM voters)::int                               AS total_voters,
        (SELECT COUNT(DISTINCT ward_id) FROM ward_targets)::int          AS registered_wards,
        (SELECT COUNT(*) FROM campaigns WHERE status='active')::int      AS active_campaigns,
        (SELECT COUNT(*) FROM volunteers WHERE status='active')::int     AS volunteers_active
    `)
    return {
      totalVoters:      rows[0]?.total_voters      ?? 0,
      registeredWards:  rows[0]?.registered_wards  ?? 0,
      activeCampaigns:  rows[0]?.active_campaigns  ?? 0,
      daysToElection:   128,
      sentimentScore:   72,
      volunteersActive: rows[0]?.volunteers_active ?? 0,
    }
  } catch {
    return {
      totalVoters: 0, registeredWards: 0, activeCampaigns: 0,
      daysToElection: 128, sentimentScore: 0, volunteersActive: 0,
    }
  }
}

async function getRecentActivity() {
  try {
    const { rows } = await pool.query(`
      SELECT id, type, description, created_at
      FROM campaign_activity
      ORDER BY created_at DESC
      LIMIT 10
    `)
    return rows
  } catch {
    return []
  }
}

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const [stats, activity] = await Promise.all([
    getCampaignStats(),
    getRecentActivity(),
  ])

  const statCards = [
    { label: 'Registered Voters',  value: stats.totalVoters.toLocaleString(),      color: 'text-green-400'  },
    { label: 'Wards Targeted',     value: stats.registeredWards.toString(),         color: 'text-blue-400'   },
    { label: 'Active Campaigns',   value: stats.activeCampaigns.toString(),         color: 'text-yellow-400' },
    { label: 'Days to Election',   value: stats.daysToElection.toString(),          color: 'text-red-400'    },
    { label: 'Sentiment Score',    value: `${stats.sentimentScore}%`,               color: 'text-purple-400' },
    { label: 'Active Volunteers',  value: stats.volunteersActive.toLocaleString(),  color: 'text-teal-400'   },
  ]

  return (
    <div className="space-y-8">
      {/* Page title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Campaign Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Welcome back, {session.user?.name}</p>
        </div>
        <a href="/briefing" className="btn-primary">
          AI Daily Briefing →
        </a>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map(s => (
          <div key={s.label} className="stat-card text-center">
            <p className={`text-3xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <a href="/campaigns/new"
          className="stat-card flex flex-col gap-2 hover:border-green-800 transition-colors cursor-pointer">
          <span className="text-2xl">🗳️</span>
          <span className="font-semibold text-white">New Campaign</span>
          <span className="text-xs text-gray-500">Launch a targeted ward campaign</span>
        </a>
        <a href="/briefing"
          className="stat-card flex flex-col gap-2 hover:border-purple-800 transition-colors cursor-pointer">
          <span className="text-2xl">🤖</span>
          <span className="font-semibold text-white">AI Strategy Briefing</span>
          <span className="text-xs text-gray-500">Daily AI analysis of campaign performance</span>
        </a>
        <a href="/voters/import"
          className="stat-card flex flex-col gap-2 hover:border-blue-800 transition-colors cursor-pointer">
          <span className="text-2xl">📋</span>
          <span className="font-semibold text-white">Import Voters</span>
          <span className="text-xs text-gray-500">Upload IEBC voter register CSV</span>
        </a>
      </div>

      {/* Recent activity */}
      <div className="stat-card">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">Recent Activity</h2>
        {activity.length === 0 ? (
          <p className="text-gray-600 text-sm">No recent activity. Start by creating a campaign.</p>
        ) : (
          <ul className="divide-y divide-gray-800 text-sm">
            {activity.map((a: Record<string, unknown>) => (
              <li key={String(a.id ?? '')} className="py-2.5 flex items-start gap-3">
                <span className="text-gray-600 text-xs w-32 flex-shrink-0">
                  {new Date(String(a.created_at ?? '')).toLocaleString('en-KE', {
                    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                  })}
                </span>
                <span className="text-gray-300">{String(a.description ?? '')}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
