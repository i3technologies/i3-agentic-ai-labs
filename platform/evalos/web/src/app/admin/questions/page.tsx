import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import QuestionGeneratorPanel from '../question-generator-panel'

interface Question {
  id: string
  set_number: number
  domain_number: number
  domain_name: string
  topic: string
  text: string
  type: string
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  is_active: boolean
}

interface Filters {
  set?: number
  domain?: number
  type?: string
  search?: string
  active?: string
  page?: number
}

const PAGE_SIZE = 20

async function getQuestions(filters: Filters): Promise<{ rows: Question[]; total: number }> {
  const conditions: string[] = []
  const values: unknown[] = []
  let idx = 1

  if (filters.set) { conditions.push(`set_number = $${idx++}`); values.push(filters.set) }
  if (filters.domain) { conditions.push(`domain_number = $${idx++}`); values.push(filters.domain) }
  if (filters.type) { conditions.push(`type = $${idx++}`); values.push(filters.type) }
  if (filters.active !== undefined && filters.active !== '') {
    conditions.push(`is_active = $${idx++}`)
    values.push(filters.active === 'true')
  }
  if (filters.search) {
    conditions.push(`(text ILIKE $${idx} OR topic ILIKE $${idx})`)
    values.push(`%${filters.search}%`)
    idx++
  }

  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''
  const page = Math.max(1, filters.page ?? 1)
  const offset = (page - 1) * PAGE_SIZE

  const countRes = await pool.query(`SELECT COUNT(*)::int AS total FROM questions ${where}`, values)
  const dataRes = await pool.query<Question>(
    `SELECT id, set_number, domain_number, domain_name, topic,
            LEFT(text, 120) AS text, type, options, correct_answers, explanation, is_active
     FROM questions ${where}
     ORDER BY set_number, domain_number, id
     LIMIT ${PAGE_SIZE} OFFSET ${offset}`,
    values
  )

  return { rows: dataRes.rows, total: countRes.rows[0].total }
}

export default async function QuestionBankPage({
  searchParams,
}: {
  searchParams: { set?: string; domain?: string; type?: string; search?: string; active?: string; page?: string }
}) {
  const session = await getServerSession(authOptions)
  if (!session?.user.isAdmin) redirect('/dashboard')

  const filters: Filters = {
    set: searchParams.set ? parseInt(searchParams.set) : undefined,
    domain: searchParams.domain ? parseInt(searchParams.domain) : undefined,
    type: searchParams.type || undefined,
    search: searchParams.search || undefined,
    active: searchParams.active ?? '',
    page: searchParams.page ? parseInt(searchParams.page) : 1,
  }

  const { rows: questions, total } = await getQuestions(filters)
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = filters.page ?? 1

  // Domain list for filter dropdown
  const { rows: domains } = await pool.query<{ domain_number: number; domain_name: string }>(
    `SELECT DISTINCT domain_number, domain_name FROM questions ORDER BY domain_number`
  )

  function buildUrl(override: Record<string, string | number | undefined>) {
    const p = new URLSearchParams()
    const merged = { ...searchParams, ...override }
    for (const [k, v] of Object.entries(merged)) {
      if (v !== undefined && v !== '') p.set(k, String(v))
    }
    return `/admin/questions?${p.toString()}`
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Question Bank</h1>
          <p className="text-sm text-slate-500 mt-1">{total.toLocaleString()} questions total · Showing page {currentPage} of {totalPages}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin"
            className="px-4 py-2 border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50 transition-colors"
          >
            ← Admin Dashboard
          </Link>
        </div>
      </div>

      {/* AI Question Generator */}
      <QuestionGeneratorPanel />

      {/* Filters */}
      <form method="GET" className="bg-white border border-slate-200 rounded-xl p-4 mb-6">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          <select name="set" defaultValue={searchParams.set ?? ''} className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white">
            <option value="">All Sets</option>
            {[1,2,3,4,5,6].map(s => <option key={s} value={s}>SET {s}</option>)}
          </select>
          <select name="domain" defaultValue={searchParams.domain ?? ''} className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white">
            <option value="">All Domains</option>
            {domains.map(d => <option key={d.domain_number} value={d.domain_number}>D{d.domain_number} — {d.domain_name.slice(0, 24)}</option>)}
          </select>
          <select name="type" defaultValue={searchParams.type ?? ''} className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white">
            <option value="">All Types</option>
            <option value="SC">Single Choice</option>
            <option value="MR">Multiple Response</option>
          </select>
          <select name="active" defaultValue={searchParams.active ?? ''} className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white">
            <option value="">Active &amp; Inactive</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
          <div className="flex gap-2 md:col-span-1 col-span-2 sm:col-span-3">
            <input
              name="search"
              defaultValue={searchParams.search ?? ''}
              placeholder="Search text or topic…"
              className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 placeholder-slate-400"
            />
            <button type="submit" className="px-4 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-800 transition-colors whitespace-nowrap">
              Filter
            </button>
          </div>
        </div>
        {/* Clear */}
        {Object.values(searchParams).some(Boolean) && (
          <div className="mt-2">
            <Link href="/admin/questions" className="text-xs text-slate-400 hover:text-slate-600 underline">Clear all filters</Link>
          </div>
        )}
      </form>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-16">Set</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-24">Domain</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Question (truncated)</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide hidden md:table-cell">Topic</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-14">Type</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-16">Answer</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-16">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {questions.map((q) => (
                <tr key={q.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-center">
                    <span className="inline-block bg-slate-100 text-slate-600 text-xs font-semibold px-2 py-0.5 rounded">
                      SET{q.set_number}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                    D{q.domain_number}
                  </td>
                  <td className="px-4 py-3 text-slate-800 leading-snug max-w-xs">
                    <span className="line-clamp-2">{q.text}</span>
                    {q.explanation && (
                      <span className="block text-xs text-slate-400 mt-0.5 line-clamp-1">{q.explanation.slice(0, 80)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500 hidden md:table-cell max-w-[140px] truncate">
                    {q.topic}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      q.type === 'MR' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                    }`}>
                      {q.type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center text-xs font-mono font-bold text-green-700">
                    {q.correct_answers.join(', ')}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <a
                      href={`/api/admin/questions?id=${q.id}&active=${!q.is_active}`}
                      title={q.is_active ? 'Click to deactivate' : 'Click to activate'}
                      className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full transition-colors ${
                        q.is_active
                          ? 'bg-green-100 text-green-700 hover:bg-green-200'
                          : 'bg-red-50 text-red-500 hover:bg-red-100'
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${q.is_active ? 'bg-green-500' : 'bg-red-400'}`} />
                      {q.is_active ? 'On' : 'Off'}
                    </a>
                  </td>
                </tr>
              ))}
              {questions.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400 text-sm">
                    No questions match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 flex-wrap">
          {currentPage > 1 && (
            <Link href={buildUrl({ page: currentPage - 1 })} className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
              ← Prev
            </Link>
          )}
          {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => {
            const p = i + 1
            return (
              <Link
                key={p}
                href={buildUrl({ page: p })}
                className={`px-3 py-1.5 border rounded-lg text-sm transition-colors ${
                  p === currentPage
                    ? 'bg-slate-900 text-white border-slate-900'
                    : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {p}
              </Link>
            )
          })}
          {currentPage < totalPages && (
            <Link href={buildUrl({ page: currentPage + 1 })} className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
              Next →
            </Link>
          )}
        </div>
      )}

      {/* Stats summary */}
      <div className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[1,2,3,4,5,6].map(s => null) /* spacer — replaced below */}
      </div>
    </div>
  )
}
