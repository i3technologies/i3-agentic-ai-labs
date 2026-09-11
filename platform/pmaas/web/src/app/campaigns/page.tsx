import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import pool from '@/lib/db'
import Link from 'next/link'

const STATUS_COLORS: Record<string, string> = {
  draft:     'bg-gray-700 text-gray-300',
  active:    'bg-green-900/60 text-green-300',
  paused:    'bg-yellow-900/60 text-yellow-300',
  completed: 'bg-blue-900/60 text-blue-300',
}

async function getCampaigns() {
  try {
    const { rows } = await pool.query(`
      SELECT c.id, c.name, c.status, c.start_date, c.end_date,
             c.budget_kes, c.description,
             COUNT(DISTINCT wt.ward_id)::int AS ward_count
      FROM campaigns c
      LEFT JOIN ward_targets wt ON wt.campaign_id = c.id
      GROUP BY c.id
      ORDER BY c.created_at DESC
      LIMIT 50
    `)
    return rows
  } catch { return [] }
}

export default async function CampaignsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const campaigns = await getCampaigns()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Campaigns</h1>
          <p className="text-gray-400 text-sm mt-1">{campaigns.length} campaigns</p>
        </div>
        <Link href="/campaigns/new" className="btn-primary">
          + New Campaign
        </Link>
      </div>

      {campaigns.length === 0 ? (
        <div className="stat-card text-center py-16 text-gray-600">
          <p className="text-4xl mb-3">🗳️</p>
          <p>No campaigns yet. Create your first campaign to get started.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {campaigns.map((c: Record<string, unknown>) => (
            <div key={String(c.id)} className="stat-card hover:border-gray-700 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="font-semibold text-white">{String(c.name)}</h2>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[String(c.status)] ?? 'bg-gray-700 text-gray-300'}`}>
                      {String(c.status)}
                    </span>
                  </div>
                  {c.description && (
                    <p className="text-sm text-gray-400 mt-1 truncate">{String(c.description)}</p>
                  )}
                  <div className="flex flex-wrap gap-4 mt-2 text-xs text-gray-500">
                    {c.start_date && <span>Starts {new Date(String(c.start_date)).toLocaleDateString('en-KE')}</span>}
                    {c.end_date   && <span>Ends {new Date(String(c.end_date)).toLocaleDateString('en-KE')}</span>}
                    <span>{Number(c.ward_count)} wards targeted</span>
                    {c.budget_kes && <span>KES {Number(c.budget_kes).toLocaleString()}</span>}
                  </div>
                </div>
                <Link
                  href={`/campaigns/${String(c.id)}`}
                  className="btn-secondary flex-shrink-0"
                >
                  View →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
