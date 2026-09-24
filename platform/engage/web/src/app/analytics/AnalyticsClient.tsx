'use client'
import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

interface Analytics {
  eventsByDay:  { day: string; opened: number; clicked: number; bounced: number }[]
  eventsByType: { event_type: string; n: number }[]
  topCampaigns: { name: string; sent: number; opens: number; clicks: number }[]
  growth:       { day: string; new_contacts: number }[]
}

const COLORS = ['#6366f1','#10b981','#f59e0b','#ef4444','#8b5cf6']

export function AnalyticsClient() {
  const [data, setData]     = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/analytics').then(r => r.json()).then(d => { setData(d); setLoading(false) })
  }, [])

  if (loading) return <div className="text-slate-400 text-sm py-10 text-center">Loading analytics…</div>
  if (!data)   return <div className="text-red-400 text-sm py-10 text-center">Failed to load analytics.</div>

  const pieData = data.eventsByType.map(e => ({ name: e.event_type, value: e.n }))

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">Analytics</h2>
        <p className="text-slate-500 text-xs mt-0.5">Last 30 days overview</p>
      </div>

      {/* Events over time */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Email Events — Daily (30 days)</h3>
        {data.eventsByDay.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.eventsByDay}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="opened"  stroke="#6366f1" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="clicked" stroke="#10b981" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="bounced" stroke="#ef4444" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-slate-400 text-sm">No event data yet.</div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Event distribution pie */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm">Event Distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={80} label>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-400 text-sm">No events yet.</div>
          )}
        </div>

        {/* Contact growth */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm">New Contacts — Daily</h3>
          {data.growth.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={data.growth}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="new_contacts" fill="#6366f1" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-400 text-sm">No data yet.</div>
          )}
        </div>
      </div>

      {/* Top campaigns */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Top Campaigns by Engagement</h3>
        {data.topCampaigns.length === 0 ? (
          <p className="text-slate-400 text-sm">No campaigns sent yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                <th className="pb-2 font-medium">Campaign</th>
                <th className="pb-2 font-medium text-right">Sent</th>
                <th className="pb-2 font-medium text-right">Opens</th>
                <th className="pb-2 font-medium text-right">Clicks</th>
                <th className="pb-2 font-medium text-right">Open Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.topCampaigns.map((c, i) => (
                <tr key={i} className="border-b border-slate-50 last:border-0">
                  <td className="py-2.5 font-medium text-slate-700">{c.name}</td>
                  <td className="py-2.5 text-right text-slate-500">{c.sent}</td>
                  <td className="py-2.5 text-right text-indigo-600">{c.opens}</td>
                  <td className="py-2.5 text-right text-green-600">{c.clicks}</td>
                  <td className="py-2.5 text-right text-slate-500">
                    {c.sent ? `${Math.round((c.opens / c.sent) * 100)}%` : '—'}
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
