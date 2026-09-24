'use client'
import { useEffect, useState, useCallback } from 'react'

interface Campaign {
  id: string; name: string; subject: string; status: string
  from_name: string; from_email: string; ai_personalise: boolean
  scheduled_at: string | null; sent_at: string | null; created_at: string
}
interface List { id: string; name: string }

const statusBadge: Record<string, string> = {
  draft:     'bg-slate-100 text-slate-600',
  scheduled: 'bg-yellow-100 text-yellow-700',
  sent:      'bg-green-100 text-green-700',
  paused:    'bg-red-100 text-red-600',
}

const blank = {
  name:'', subject:'', from_name:'i3 Engage', from_email:'hello@i3technologies.co.ke',
  list_id:'', html_template:'', ai_personalise: false,
}

export function CampaignsClient() {
  const [campaigns, setCampaigns]   = useState<Campaign[]>([])
  const [lists, setLists]           = useState<List[]>([])
  const [loading, setLoading]       = useState(true)
  const [showNew, setShowNew]       = useState(false)
  const [form, setForm]             = useState({ ...blank })
  const [saving, setSaving]         = useState(false)
  const [sendingId, setSendingId]   = useState<string | null>(null)
  const [composing, setComposing]   = useState(false)
  const [aiPrompt, setAiPrompt]     = useState('')
  const [error, setError]           = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const [c, l] = await Promise.all([
      fetch('/api/campaigns').then(r => r.json()),
      fetch('/api/lists').then(r => r.json()),
    ])
    setCampaigns(c.campaigns ?? [])
    setLists(l.lists ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  async function createCampaign(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    const r = await fetch('/api/campaigns', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (r.ok) { setShowNew(false); setForm({ ...blank }); load() }
    else { const d = await r.json(); setError(d.error ?? 'Failed') }
    setSaving(false)
  }

  async function sendNow(id: string) {
    if (!confirm('Send this campaign immediately to all subscribed contacts in the list?')) return
    setSendingId(id)
    const r = await fetch('/api/campaigns/send', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campaign_id: id, send_now: true }),
    })
    const d = await r.json()
    alert(r.ok ? `Sent: ${d.sent} | Failed: ${d.failed}` : d.error ?? 'Error')
    setSendingId(null); load()
  }

  async function aiCompose() {
    if (!aiPrompt.trim()) return
    setComposing(true)
    const r = await fetch('/api/campaigns/compose', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: aiPrompt, subject: form.subject }),
    })
    const d = await r.json()
    if (r.ok) setForm(prev => ({ ...prev, html_template: d.html }))
    setComposing(false)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Email Campaigns</h2>
          <p className="text-slate-500 text-xs mt-0.5">{campaigns.length} campaigns</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
          + New Campaign
        </button>
      </div>

      {/* Campaign table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Subject</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">AI</th>
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="text-center py-10 text-slate-400">Loading…</td></tr>
            ) : campaigns.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-10 text-slate-400">No campaigns yet.</td></tr>
            ) : campaigns.map(c => (
              <tr key={c.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{c.name}</td>
                <td className="px-4 py-3 text-slate-500 truncate max-w-xs">{c.subject}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusBadge[c.status] ?? 'bg-slate-100 text-slate-600'}`}>
                    {c.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {c.ai_personalise && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">AI ✦</span>}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {c.sent_at ? new Date(c.sent_at).toLocaleDateString() : new Date(c.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  {c.status === 'draft' && (
                    <button
                      onClick={() => sendNow(c.id)}
                      disabled={sendingId === c.id}
                      className="text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-2 py-1 rounded font-medium disabled:opacity-50">
                      {sendingId === c.id ? 'Sending…' : 'Send Now'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New campaign modal */}
      {showNew && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <h3 className="font-bold text-slate-800 mb-4 text-lg">New Email Campaign</h3>
            {error && <div className="text-red-600 text-sm mb-3 bg-red-50 p-2 rounded">{error}</div>}
            <form onSubmit={createCampaign} className="space-y-4">

              <div className="grid grid-cols-2 gap-3">
                {[
                  { name:'name',       label:'Campaign Name *', col:'col-span-2' },
                  { name:'subject',    label:'Email Subject *',  col:'col-span-2' },
                  { name:'from_name',  label:'From Name',        col:'' },
                  { name:'from_email', label:'From Email',       col:'' },
                ].map(f => (
                  <div key={f.name} className={f.col}>
                    <label className="block text-xs font-medium text-slate-600 mb-1">{f.label}</label>
                    <input type="text" required={['name','subject'].includes(f.name)}
                      value={(form as Record<string, unknown>)[f.name] as string}
                      onChange={e => setForm(prev => ({ ...prev, [f.name]: e.target.value }))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    />
                  </div>
                ))}
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Contact List</label>
                <select value={form.list_id} onChange={e => setForm(prev => ({ ...prev, list_id: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300">
                  <option value="">— Select a list —</option>
                  {lists.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
              </div>

              {/* AI compose */}
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-semibold text-purple-700">✦ AI Compose</span>
                  <span className="text-xs text-purple-500">Describe your email, let AI write it</span>
                </div>
                <div className="flex gap-2">
                  <input type="text" placeholder="e.g. Announce our new AI Lab course launch, professional tone"
                    value={aiPrompt}
                    onChange={e => setAiPrompt(e.target.value)}
                    className="flex-1 border border-purple-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-300 bg-white"
                  />
                  <button type="button" onClick={aiCompose} disabled={composing || !aiPrompt.trim()}
                    className="bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50 whitespace-nowrap">
                    {composing ? 'Generating…' : '✦ Generate'}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">HTML Template *</label>
                <textarea required value={form.html_template}
                  onChange={e => setForm(prev => ({ ...prev, html_template: e.target.value }))}
                  rows={8} placeholder="<p>Hi {{first_name}}, …</p>"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-y"
                />
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.ai_personalise}
                  onChange={e => setForm(prev => ({ ...prev, ai_personalise: e.target.checked }))}
                  className="rounded border-slate-300 text-indigo-600" />
                <span className="text-sm text-slate-700">AI personalise each email before sending</span>
              </label>

              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={saving}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2.5 rounded-lg disabled:opacity-50">
                  {saving ? 'Saving…' : 'Create Campaign'}
                </button>
                <button type="button" onClick={() => setShowNew(false)}
                  className="flex-1 border border-slate-200 text-slate-600 text-sm py-2.5 rounded-lg hover:bg-slate-50">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
