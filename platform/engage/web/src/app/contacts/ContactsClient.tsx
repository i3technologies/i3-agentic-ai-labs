'use client'
import { useEffect, useState, useCallback } from 'react'

interface Contact {
  id: string; email: string; first_name: string; last_name: string
  company: string; subscribed: boolean; created_at: string
  tags: string[]; event_count: number
}

export function ContactsClient() {
  const [contacts, setContacts]   = useState<Contact[]>([])
  const [total, setTotal]         = useState(0)
  const [page, setPage]           = useState(1)
  const [search, setSearch]       = useState('')
  const [loading, setLoading]     = useState(true)
  const [showAdd, setShowAdd]     = useState(false)
  const [form, setForm]           = useState({ email:'', first_name:'', last_name:'', company:'', tags:'' })
  const [saving, setSaving]       = useState(false)
  const [error, setError]         = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const q = new URLSearchParams({ page: String(page), ...(search ? { q: search } : {}) })
    const r = await fetch(`/api/contacts?${q}`)
    const d = await r.json()
    setContacts(d.contacts ?? [])
    setTotal(d.total ?? 0)
    setLoading(false)
  }, [page, search])

  useEffect(() => { load() }, [load])

  async function addContact(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setError('')
    const tags = form.tags.split(',').map(t => t.trim()).filter(Boolean)
    const r = await fetch('/api/contacts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, tags }),
    })
    if (r.ok) { setShowAdd(false); setForm({ email:'', first_name:'', last_name:'', company:'', tags:'' }); load() }
    else { const d = await r.json(); setError(d.error ?? 'Failed') }
    setSaving(false)
  }

  const pages = Math.ceil(total / 50)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Contacts</h2>
          <p className="text-slate-500 text-xs mt-0.5">{total.toLocaleString()} total</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Add Contact
        </button>
      </div>

      {/* Search */}
      <input
        type="text" placeholder="Search email, name…"
        value={search}
        onChange={e => { setSearch(e.target.value); setPage(1) }}
        className="w-full md:w-80 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
      />

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Tags</th>
              <th className="px-4 py-3 font-medium">Events</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-10 text-slate-400 text-sm">Loading…</td></tr>
            ) : contacts.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-10 text-slate-400 text-sm">No contacts found.</td></tr>
            ) : contacts.map(c => (
              <tr key={c.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-indigo-700">{c.email}</td>
                <td className="px-4 py-3 text-slate-700">{[c.first_name, c.last_name].filter(Boolean).join(' ') || '—'}</td>
                <td className="px-4 py-3 text-slate-500">{c.company || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(c.tags ?? []).slice(0,3).map(t => (
                      <span key={t} className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">{t}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-500">{c.event_count}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${c.subscribed ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                    {c.subscribed ? 'Subscribed' : 'Unsubscribed'}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center gap-2 text-sm">
          <button disabled={page === 1} onClick={() => setPage(p => p-1)}
            className="px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-100">← Prev</button>
          <span className="text-slate-500">Page {page} of {pages}</span>
          <button disabled={page === pages} onClick={() => setPage(p => p+1)}
            className="px-3 py-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-100">Next →</button>
        </div>
      )}

      {/* Add modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="font-bold text-slate-800 mb-4">Add Contact</h3>
            {error && <div className="text-red-600 text-sm mb-3 bg-red-50 p-2 rounded">{error}</div>}
            <form onSubmit={addContact} className="space-y-3">
              {[
                { name:'email',      label:'Email *',     type:'email' },
                { name:'first_name', label:'First name',  type:'text' },
                { name:'last_name',  label:'Last name',   type:'text' },
                { name:'company',    label:'Company',     type:'text' },
                { name:'tags',       label:'Tags (comma-separated)', type:'text' },
              ].map(f => (
                <div key={f.name}>
                  <label className="block text-xs font-medium text-slate-600 mb-1">{f.label}</label>
                  <input
                    type={f.type}
                    required={f.name === 'email'}
                    value={(form as Record<string,string>)[f.name]}
                    onChange={e => setForm(prev => ({ ...prev, [f.name]: e.target.value }))}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
              ))}
              <div className="flex gap-2 pt-2">
                <button type="submit" disabled={saving}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50">
                  {saving ? 'Saving…' : 'Add Contact'}
                </button>
                <button type="button" onClick={() => setShowAdd(false)}
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
