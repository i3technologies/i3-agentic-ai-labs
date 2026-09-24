'use client'
import { useEffect, useState, useCallback } from 'react'

interface ContactList { id: string; name: string; description: string; created_at: string; contact_count?: number }

export function ListsClient() {
  const [lists, setLists]       = useState<ContactList[]>([])
  const [loading, setLoading]   = useState(true)
  const [showNew, setShowNew]   = useState(false)
  const [form, setForm]         = useState({ name: '', description: '' })
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const r = await fetch('/api/lists')
    const d = await r.json()
    setLists(d.lists ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  async function createList(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    const r = await fetch('/api/lists', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    if (r.ok) { setShowNew(false); setForm({ name:'', description:'' }); load() }
    else { const d = await r.json(); setError(d.error ?? 'Failed') }
    setSaving(false)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Contact Lists</h2>
          <p className="text-slate-500 text-xs mt-0.5">{lists.length} lists</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
          + New List
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-3 text-center text-slate-400 py-10">Loading…</div>
        ) : lists.length === 0 ? (
          <div className="col-span-3 text-center text-slate-400 py-10">
            No lists yet. Create one to start segmenting your contacts.
          </div>
        ) : lists.map(l => (
          <div key={l.id} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-slate-800">{l.name}</h3>
                {l.description && <p className="text-slate-500 text-xs mt-1">{l.description}</p>}
              </div>
              <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                {l.contact_count ?? 0} contacts
              </span>
            </div>
            <p className="text-slate-400 text-xs mt-3">
              Created {new Date(l.created_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>

      {showNew && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="font-bold text-slate-800 mb-4">New Contact List</h3>
            {error && <div className="text-red-600 text-sm mb-3 bg-red-50 p-2 rounded">{error}</div>}
            <form onSubmit={createList} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">List Name *</label>
                <input type="text" required value={form.name}
                  onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Description</label>
                <textarea rows={2} value={form.description}
                  onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                />
              </div>
              <div className="flex gap-2 pt-1">
                <button type="submit" disabled={saving}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-2 rounded-lg disabled:opacity-50">
                  {saving ? 'Saving…' : 'Create List'}
                </button>
                <button type="button" onClick={() => setShowNew(false)}
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
