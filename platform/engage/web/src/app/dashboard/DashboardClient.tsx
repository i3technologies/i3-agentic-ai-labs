'use client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface Stats {
  totalContacts: number; totalCampaigns: number; totalSent: number
  opens: number; clicks: number; bounces: number
  recentCampaigns: { name: string; status: string; sent_at: string | null; created_at: string }[]
  activityChart: { day: string; sends: number }[]
}

const statusBadge: Record<string, string> = {
  draft:     'bg-slate-100 text-slate-600',
  scheduled: 'bg-yellow-100 text-yellow-700',
  sent:      'bg-green-100 text-green-700',
  paused:    'bg-red-100 text-red-600',
}

export function DashboardClient({ stats, userName }: { stats: Stats; userName: string }) {
  const openRate = stats.totalSent ? Math.round((stats.opens / stats.totalSent) * 100) : 0
  const clickRate = stats.totalSent ? Math.round((stats.clicks / stats.totalSent) * 100) : 0

  const kpis = [
    { label: 'Total Contacts',  value: stats.totalContacts.toLocaleString(),  color: 'bg-indigo-50 text-indigo-700' },
    { label: 'Campaigns',       value: stats.totalCampaigns.toLocaleString(), color: 'bg-purple-50 text-purple-700' },
    { label: 'Emails Sent',     value: stats.totalSent.toLocaleString(),      color: 'bg-blue-50 text-blue-700' },
    { label: 'Open Rate',       value: `${openRate}%`,                        color: 'bg-green-50 text-green-700' },
    { label: 'Click Rate',      value: `${clickRate}%`,                       color: 'bg-teal-50 text-teal-700' },
    { label: 'Bounces (30d)',   value: stats.bounces.toLocaleString(),        color: 'bg-red-50 text-red-600' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Good day, {userName} 👋</h2>
        <p className="text-slate-500 text-sm mt-0.5">Here&apos;s your engagement overview</p>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {kpis.map(k => (
          <div key={k.label} className={`rounded-xl p-4 ${k.color} border border-current border-opacity-20`}>
            <div className="text-2xl font-bold">{k.value}</div>
            <div className="text-xs font-medium mt-1 opacity-80">{k.label}</div>
          </div>
        ))}
      </div>

      {/* Activity chart */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Emails Sent — Last 14 Days</h3>
        {stats.activityChart.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stats.activityChart}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="sends" fill="#6366f1" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-slate-400 text-sm">
            No send activity yet — create your first campaign!
          </div>
        )}
      </div>

      {/* Recent campaigns */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Recent Campaigns</h3>
        {stats.recentCampaigns.length === 0 ? (
          <p className="text-slate-400 text-sm">No campaigns yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {stats.recentCampaigns.map((c, i) => (
                <tr key={i} className="border-b border-slate-50 last:border-0">
                  <td className="py-2.5 font-medium text-slate-700">{c.name}</td>
                  <td className="py-2.5">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusBadge[c.status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-500 text-xs">
                    {new Date(c.sent_at ?? c.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
