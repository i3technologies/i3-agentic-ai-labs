'use client'
import { useEffect, useState, useCallback } from 'react'

interface SmsMessage {
  id: string; contact_email: string; content: string
  status: string; provider: string; created_at: string
}

export function SmsClient() {
  const [messages, setMessages]   = useState<SmsMessage[]>([])
  const [loading, setLoading]     = useState(true)
  const [showSend, setShowSend]   = useState(false)
  const [form, setForm]           = useState({ phone: '', content: '' })
  const [sending, setSending]     = useState(false)
  const [error, setError]         = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const r = await fetch('/api/sms')
    const d = await r.json()
    setMessages(d.messages ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  async function sendSms(e: React.FormEvent) {
    e.preventDefault(); setSending(true); setError('')
    const r = await fetch('/api/sms', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (r.ok) { setShowSend(false); setForm({ phone: '', content: '' }); load() }
    else { const d = await r.json(); setError(d.error ?? 'Failed to send') }
    setSending(false)
  }

  const statusColor: Record<string,string> = {
    sent:    'bg-green-100 text-green-700',
    pending: 'bg-yellow-100 text-yellow-700',
    failed:  'bg-red-100 text-red-600',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">SMS Messages</h2>
          <p className="text-slate-500 text-xs mt-0.5">Sent via Africa&apos;s Talking</p>
        </div>
        <button onClick={() => setShowSend(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
          + Send SMS
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-3 font-medium">Contact</th>
              <th className="px-4 py-3 font-medium">Message</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Sent</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="text-center py-10 text-slate-400">Loading…</td></tr>
            ) : messages.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-10 text-slate-400">No SMS messages yet.</td></tr>
            ) : messages.map(m => (
              <tr key={m.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 text-indigo-700 font-medium">{m.contact_email || '—'}</td>
                <td className="px-4 py-3 text-slate-600 max-w-xs truncate">{m.content}</td>
                <td className="px-4 py-3 text-slate-400 text-xs">{m.provider}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[m.status] ?? 'bg-slate-100 text-slate-600'}`}>
                    {m.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{new Date(m.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showSend && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="font-bold text-slate-800 mb-4">Send SMS</h3>
            {error && <div className="text-red-600 text-sm mb-3 bg-red-50 p-2 rounded">{error}</div>}
            <form onSubmit={sendSms} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Phone Number * (e.g. +254712345678)</label>
                <input type="tel" required value={form.phone}
                  onChange={e => setForm(p => ({ ...p, phone: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Message * ({form.content.length}/160)</label>
                <textarea required maxLength={160} rows={4} value={form.content}
                  onChange={e => setForm(p => ({ ...p, content: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                />
              </div>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={sending}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50">
                  {sending ? 'Sending…' : 'Send SMS'}
                </button>
                <button type="button" onClick={() => setShowSend(false)}
                  className="flex-1 border border-slate-200 text-slate-600 text-sm py-2 rounded-lg hover:bg-slate-50">
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
