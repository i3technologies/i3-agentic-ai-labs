import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

// ── Types ────────────────────────────────────────────────────────────────────

interface AttemptRow {
  id: string
  student_id: string
  exam_title: string
  exam_code: string
  status: string
  pct_score: number | null
  passed: boolean | null
  started_at: string
  submitted_at: string | null
  focus_lost_count: number
  fullscreen_exits: number
  clipboard_events: number
  domain_breakdown: DomainBreakdown[] | null
}

interface DomainBreakdown {
  domain_number: number
  domain_name: string
  correct: number
  total: number
  pct: number
}

interface StudentStat {
  student_id: string
  display_name: string
  attempts: number
  submitted: number
  best_score: number | null
  pass_count: number
  sets_passed: number
  total_flags: number
  last_attempt: string | null
}

interface ExamStat {
  exam_code: string
  total: number
  submitted: number
  passes: number
  pass_rate: number
  avg_score: number | null
}

interface DomainStat {
  domain_number: number
  domain_name: string
  avg_pct: number
  attempt_count: number
}

// ── Data fetchers ─────────────────────────────────────────────────────────────

async function getAllAttempts(): Promise<AttemptRow[]> {
  const { rows } = await pool.query<AttemptRow>(
    `SELECT
       qa.id,
       qa.student_id,
       e.title AS exam_title,
       e.code  AS exam_code,
       qa.status,
       qa.pct_score,
       qa.passed,
       qa.started_at,
       qa.submitted_at,
       COALESCE(qa.focus_lost_count, 0)  AS focus_lost_count,
       COALESCE(qa.fullscreen_exits, 0)  AS fullscreen_exits,
       COALESCE(qa.clipboard_events, 0)  AS clipboard_events,
       -- extract domain breakdown from proctor_flags jsonb
       (qa.proctor_flags -> 'domain_breakdown') AS domain_breakdown
     FROM quiz_attempts qa
     JOIN exams e ON e.id = qa.exam_id
     ORDER BY qa.started_at DESC
     LIMIT 1000`
  )
  return rows
}

async function getExamStats(): Promise<ExamStat[]> {
  const { rows } = await pool.query<ExamStat>(
    `SELECT
       e.code AS exam_code,
       COUNT(qa.id)::int                                  AS total,
       COUNT(qa.id) FILTER (WHERE qa.status = 'submitted')::int AS submitted,
       COUNT(qa.id) FILTER (WHERE qa.passed = true)::int  AS passes,
       ROUND(
         100.0 * COUNT(qa.id) FILTER (WHERE qa.passed = true) /
         NULLIF(COUNT(qa.id) FILTER (WHERE qa.status = 'submitted'), 0)
       , 0)::int                                           AS pass_rate,
       ROUND(AVG(qa.pct_score) FILTER (WHERE qa.status='submitted'), 1) AS avg_score
     FROM exams e
     LEFT JOIN quiz_attempts qa ON qa.exam_id = e.id
     WHERE e.is_published = true
     GROUP BY e.id
     ORDER BY e.code`
  )
  return rows
}

async function getKeycloakNames(token: string): Promise<Map<string, string>> {
  const nameMap = new Map<string, string>()
  try {
    const res = await fetch(
      `${process.env.KEYCLOAK_ISSUER?.replace('/realms/i3', '')}/admin/realms/i3/users?max=500`,
      { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
    )
    if (!res.ok) return nameMap
    const users: { id: string; firstName?: string; lastName?: string; email?: string }[] = await res.json()
    for (const u of users) {
      const name = [u.firstName, u.lastName].filter(Boolean).join(' ') || u.email || u.id
      nameMap.set(u.id, name)
    }
  } catch { /* best-effort */ }
  return nameMap
}

async function getAdminToken(): Promise<string> {
  try {
    const adminPass = Buffer.from(
      process.env.KEYCLOAK_ADMIN_PASSWORD ?? '',
      'utf-8'
    ).toString()
    const res = await fetch(
      `${process.env.KEYCLOAK_ISSUER?.replace('/realms/i3', '')}/realms/master/protocol/openid-connect/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'password',
          client_id: 'admin-cli',
          username: 'admin',
          password: adminPass,
        }),
        cache: 'no-store',
      }
    )
    if (!res.ok) return ''
    const data = await res.json()
    return data.access_token ?? ''
  } catch { return '' }
}

// ── Aggregation helpers ───────────────────────────────────────────────────────

function buildStudentStats(attempts: AttemptRow[], nameMap: Map<string, string>): StudentStat[] {
  const map = new Map<string, StudentStat>()
  for (const a of attempts) {
    if (!map.has(a.student_id)) {
      map.set(a.student_id, {
        student_id: a.student_id,
        display_name: nameMap.get(a.student_id) ?? a.student_id,
        attempts: 0,
        submitted: 0,
        best_score: null,
        pass_count: 0,
        sets_passed: 0,
        total_flags: 0,
        last_attempt: null,
      })
    }
    const s = map.get(a.student_id)!
    s.attempts += 1
    if (a.status === 'submitted') s.submitted += 1
    if (a.pct_score !== null) s.best_score = Math.max(s.best_score ?? 0, a.pct_score)
    if (a.passed) { s.pass_count += 1; s.sets_passed += 1 }
    s.total_flags += a.focus_lost_count + a.fullscreen_exits + a.clipboard_events
    if (!s.last_attempt || a.started_at > s.last_attempt) s.last_attempt = a.started_at
  }
  return Array.from(map.values()).sort((a, b) => (b.best_score ?? 0) - (a.best_score ?? 0))
}

function buildDomainStats(attempts: AttemptRow[]): DomainStat[] {
  const map = new Map<number, { name: string; pcts: number[] }>()
  for (const a of attempts) {
    if (!a.domain_breakdown || a.status !== 'submitted') continue
    for (const d of a.domain_breakdown) {
      if (!map.has(d.domain_number)) map.set(d.domain_number, { name: d.domain_name, pcts: [] })
      map.get(d.domain_number)!.pcts.push(d.pct)
    }
  }
  return Array.from(map.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([dn, v]) => ({
      domain_number: dn,
      domain_name: v.name,
      avg_pct: v.pcts.length > 0 ? Math.round(v.pcts.reduce((a, b) => a + b, 0) / v.pcts.length) : 0,
      attempt_count: v.pcts.length,
    }))
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className={`text-3xl font-bold ${color ?? 'text-slate-900'}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1 font-medium">{label}</div>
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function PassRateBar({ pct, code }: { pct: number; code: string }) {
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-400'
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-28 font-mono text-slate-600 flex-shrink-0">{code}</span>
      <div className="flex-1 bg-slate-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-semibold text-slate-700">{pct}%</span>
    </div>
  )
}

function DomainHeatBar({ name, pct, attempts }: { name: string; pct: number; attempts: number }) {
  const bg = pct >= 80 ? 'bg-green-100 text-green-800' : pct >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
  return (
    <div className="flex items-center gap-3 text-xs py-1">
      <span className="flex-1 text-slate-700 truncate">{name}</span>
      <span className={`px-2 py-0.5 rounded font-semibold ${bg}`}>{pct}%</span>
      <span className="text-slate-400 w-16 text-right">{attempts} attempts</span>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function AdminPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')
  if (!session.user.isAdmin) redirect('/dashboard')

  const adminToken = await getAdminToken()
  const [attempts, examStats, nameMap] = await Promise.all([
    getAllAttempts(),
    getExamStats(),
    getKeycloakNames(adminToken),
  ])

  const students = buildStudentStats(attempts, nameMap)
  const domainStats = buildDomainStats(attempts)

  const totalAttempts = attempts.length
  const submittedCount = attempts.filter((a) => a.status === 'submitted').length
  const passCount = attempts.filter((a) => a.passed).length
  const flaggedCount = attempts.filter(
    (a) => a.focus_lost_count + a.fullscreen_exits + a.clipboard_events > 3
  ).length
  const overallPassRate = submittedCount > 0 ? Math.round((passCount / submittedCount) * 100) : 0

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
          <p className="mt-1 text-slate-500 text-sm">
            EvalOS — real-time exam monitoring &amp; student progress
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/admin/questions"
            className="text-xs bg-slate-900 text-white px-4 py-2 rounded-lg hover:bg-slate-800 transition-colors font-medium"
          >
            Question Bank
          </Link>
          <Link
            href="/api/admin/export"
            className="text-xs border border-slate-300 text-slate-700 px-4 py-2 rounded-lg hover:bg-slate-50 transition-colors font-medium"
          >
            Export CSV
          </Link>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-8">
        <StatCard label="Total Attempts" value={totalAttempts} />
        <StatCard label="Submitted" value={submittedCount} />
        <StatCard
          label="Pass Rate"
          value={`${overallPassRate}%`}
          sub={`${passCount} of ${submittedCount}`}
          color={overallPassRate >= 50 ? 'text-green-700' : 'text-red-600'}
        />
        <StatCard label="Students" value={students.length} />
        <StatCard
          label="Proctor Alerts"
          value={flaggedCount}
          color={flaggedCount > 0 ? 'text-orange-600' : 'text-slate-900'}
        />
      </div>

      {/* Two-column: pass rates + domain heatmap */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Pass rates per set */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
            Pass Rate by Exam Set
          </h2>
          <div className="space-y-3">
            {examStats.map((e) => (
              <div key={e.exam_code}>
                <PassRateBar pct={e.pass_rate ?? 0} code={e.exam_code} />
                <div className="text-xs text-slate-400 mt-0.5 pl-[7.5rem]">
                  {e.passes ?? 0}/{e.submitted ?? 0} passed · avg {e.avg_score ?? '—'}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Domain weakness heatmap */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
            Cohort Domain Scores (avg %)
          </h2>
          {domainStats.length === 0 ? (
            <p className="text-xs text-slate-400">No submitted attempts yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {domainStats.map((d) => (
                <DomainHeatBar
                  key={d.domain_number}
                  name={`D${d.domain_number}. ${d.domain_name}`}
                  pct={d.avg_pct}
                  attempts={d.attempt_count}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Proctor alert queue */}
      {flaggedCount > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
            ⚠ Proctor Alert Queue ({flaggedCount})
          </h2>
          <div className="bg-orange-50 border border-orange-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b border-orange-200">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-orange-700 uppercase">Student</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-orange-700 uppercase">Exam</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-orange-700 uppercase">Focus Lost</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-orange-700 uppercase">FS Exits</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-orange-700 uppercase">Clipboard</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-orange-700 uppercase">Date</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-orange-100">
                {attempts
                  .filter((a) => a.focus_lost_count + a.fullscreen_exits + a.clipboard_events > 3)
                  .slice(0, 50)
                  .map((a) => (
                    <tr key={a.id} className="hover:bg-orange-100/40">
                      <td className="px-4 py-2.5 text-xs text-slate-700">
                        {nameMap.get(a.student_id) ?? a.student_id}
                      </td>
                      <td className="px-4 py-2.5 text-xs font-semibold text-blue-700">{a.exam_code}</td>
                      <td className="px-4 py-2.5 text-right text-xs font-semibold text-orange-700">{a.focus_lost_count}</td>
                      <td className="px-4 py-2.5 text-right text-xs font-semibold text-orange-700">{a.fullscreen_exits}</td>
                      <td className="px-4 py-2.5 text-right text-xs font-semibold text-orange-700">{a.clipboard_events}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-400">
                        {new Date(a.started_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {a.status === 'submitted' && (
                          <Link
                            href={`/exam/${a.id}/results?attemptId=${a.id}`}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Review
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Student leaderboard */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
          Students ({students.length})
        </h2>
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Name</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Attempts</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Best Score</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Sets Passed</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase hidden lg:table-cell">Flags</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase hidden md:table-cell">Last Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {students.map((s, idx) => (
                <tr key={s.student_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-xs text-slate-400">{idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-800 text-sm">{s.display_name}</div>
                    <div className="text-xs text-slate-400 font-mono truncate max-w-[200px]">{s.student_id}</div>
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">{s.attempts}</td>
                  <td className="px-4 py-3 text-right">
                    {s.best_score !== null ? (
                      <span className={`font-bold ${s.best_score >= 90 ? 'text-green-700' : s.best_score >= 68 ? 'text-yellow-700' : 'text-red-600'}`}>
                        {Math.round(s.best_score)}%
                      </span>
                    ) : <span className="text-slate-400">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-semibold ${s.sets_passed === 6 ? 'text-green-700' : s.sets_passed > 0 ? 'text-blue-600' : 'text-slate-400'}`}>
                      {s.sets_passed}/6
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right hidden lg:table-cell">
                    {s.total_flags > 3 ? (
                      <span className="text-xs font-semibold text-orange-600">{s.total_flags}</span>
                    ) : (
                      <span className="text-xs text-slate-300">{s.total_flags}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400 hidden md:table-cell">
                    {s.last_attempt ? new Date(s.last_attempt).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* All attempts */}
      <section>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
          All Attempts (latest {Math.min(attempts.length, 1000)})
        </h2>
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Student</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Exam</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Score</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase">Result</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase hidden lg:table-cell">Flags</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase hidden md:table-cell">Date</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {attempts.map((a) => {
                const flags = a.focus_lost_count + a.fullscreen_exits + a.clipboard_events
                return (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <div className="text-sm font-medium text-slate-700 truncate max-w-[180px]">
                        {nameMap.get(a.student_id) ?? '—'}
                      </div>
                      <div className="text-xs text-slate-400 font-mono truncate max-w-[180px]">
                        {a.student_id}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs font-semibold text-blue-600">{a.exam_code}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-semibold text-slate-800">
                      {a.pct_score !== null ? `${Math.round(a.pct_score)}%` : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      {a.status === 'submitted' ? (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${a.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {a.passed ? 'Pass' : 'Fail'}
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800">
                          In Progress
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right hidden lg:table-cell">
                      {flags > 3 ? (
                        <span className="text-xs font-semibold text-orange-600">{flags}</span>
                      ) : (
                        <span className="text-xs text-slate-300">{flags || '0'}</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-400 hidden md:table-cell">
                      {new Date(a.started_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {a.status === 'submitted' && (
                        <Link
                          href={`/exam/${a.id}/results?attemptId=${a.id}`}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          View
                        </Link>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
