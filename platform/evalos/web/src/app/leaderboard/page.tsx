import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

interface LeaderboardEntry {
  student_id: string
  display_name: string
  sets_passed: number
  best_score: number | null
  avg_score: number | null
  total_submitted: number
  total_flags: number
  last_active: string | null
}

async function getLeaderboard(): Promise<LeaderboardEntry[]> {
  const { rows } = await pool.query<LeaderboardEntry>(`
    SELECT
      qa.student_id,
      COUNT(*) FILTER (WHERE qa.status = 'submitted')::int               AS total_submitted,
      COUNT(DISTINCT e.id) FILTER (
        WHERE qa.status = 'submitted' AND qa.passed = true
      )::int                                                              AS sets_passed,
      MAX(qa.pct_score) FILTER (WHERE qa.status = 'submitted')           AS best_score,
      AVG(qa.pct_score) FILTER (WHERE qa.status = 'submitted')           AS avg_score,
      SUM(
        COALESCE((qa.proctor_flags->>'focus_lost_count')::int, 0) +
        COALESCE((qa.proctor_flags->>'fullscreen_exits')::int, 0) +
        COALESCE((qa.proctor_flags->>'clipboard_events')::int, 0)
      )::int                                                              AS total_flags,
      MAX(qa.submitted_at)                                               AS last_active
    FROM quiz_attempts qa
    JOIN exams e ON e.id = qa.exam_id
    GROUP BY qa.student_id
    HAVING COUNT(*) FILTER (WHERE qa.status = 'submitted') > 0
    ORDER BY sets_passed DESC, best_score DESC NULLS LAST
  `)
  return rows
}

async function resolveDisplayNames(
  entries: LeaderboardEntry[]
): Promise<LeaderboardEntry[]> {
  const adminPassword = process.env.KEYCLOAK_ADMIN_PASSWORD ?? ''
  const keycloakIssuer = process.env.KEYCLOAK_ISSUER ?? ''
  const realm = keycloakIssuer.split('/realms/')[1] ?? 'i3'
  const baseUrl = keycloakIssuer.split('/realms/')[0] ?? ''

  try {
    const tokenResp = await fetch(
      `${baseUrl}/realms/master/protocol/openid-connect/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: 'admin-cli',
          username: 'admin',
          password: adminPassword,
          grant_type: 'password',
        }),
        signal: AbortSignal.timeout(5000),
      }
    )
    if (!tokenResp.ok) throw new Error('KC token failed')
    const { access_token } = await tokenResp.json()

    const nameMap = new Map<string, string>()
    await Promise.allSettled(
      entries.map(async (e) => {
        try {
          const r = await fetch(
            `${baseUrl}/admin/realms/${realm}/users/${e.student_id}`,
            { headers: { Authorization: `Bearer ${access_token}` }, signal: AbortSignal.timeout(3000) }
          )
          if (r.ok) {
            const u = await r.json()
            nameMap.set(e.student_id, `${u.firstName ?? ''} ${u.lastName ?? ''}`.trim() || u.email || e.student_id.slice(0, 8))
          }
        } catch { /* skip */ }
      })
    )

    return entries.map(e => ({ ...e, display_name: nameMap.get(e.student_id) || e.student_id.slice(0, 8) + '…' }))
  } catch {
    return entries.map(e => ({ ...e, display_name: e.student_id.slice(0, 8) + '…' }))
  }
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-slate-400 text-sm">—</span>
  const s = Math.round(score)
  const cls = s >= 90 ? 'text-green-700 font-bold' : s >= 70 ? 'text-yellow-700 font-semibold' : 'text-red-600 font-semibold'
  return <span className={`text-sm tabular-nums ${cls}`}>{s}%</span>
}

function SetProgress({ passed }: { passed: number }) {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: 6 }, (_, i) => (
        <div
          key={i}
          className={`w-4 h-4 rounded-sm text-xs flex items-center justify-center font-bold
            ${i < passed ? 'bg-green-500 text-white' : 'bg-slate-200 text-slate-400'}`}
        >
          {i + 1}
        </div>
      ))}
    </div>
  )
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-xl">🥇</span>
  if (rank === 2) return <span className="text-xl">🥈</span>
  if (rank === 3) return <span className="text-xl">🥉</span>
  return <span className="text-sm font-semibold text-slate-500 tabular-nums">{rank}</span>
}

export default async function LeaderboardPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const raw = await getLeaderboard()
  const entries = await resolveDisplayNames(raw)
  const currentUserId = session.user.userId || session.user.email || ''
  const myRank = entries.findIndex(e => e.student_id === currentUserId) + 1

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Cohort Leaderboard</h1>
            <p className="text-sm text-slate-500 mt-1">
              IBM C1000-207 — {entries.length} active student{entries.length !== 1 ? 's' : ''} · Ranked by sets passed, then best score
            </p>
          </div>
          {myRank > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 text-center">
              <div className="text-xs text-blue-500 font-semibold uppercase tracking-wide mb-0.5">Your Rank</div>
              <div className="text-3xl font-extrabold text-blue-700">#{myRank}</div>
              <div className="text-xs text-blue-500">of {entries.length}</div>
            </div>
          )}
        </div>
      </div>

      {/* Top 3 podium (only when ≥3 students) */}
      {entries.length >= 3 && (
        <div className="grid grid-cols-3 gap-3 mb-8">
          {[entries[1], entries[0], entries[2]].map((e, podiumIdx) => {
            const actualRank = podiumIdx === 0 ? 2 : podiumIdx === 1 ? 1 : 3
            const heights = ['h-24', 'h-32', 'h-20']
            const isMe = e.student_id === currentUserId
            return (
              <div key={e.student_id} className={`flex flex-col items-center justify-end ${heights[podiumIdx]}`}>
                <div className={`w-full rounded-t-xl flex flex-col items-center justify-center py-3 px-2 text-center
                  ${actualRank === 1 ? 'bg-yellow-400' : actualRank === 2 ? 'bg-slate-300' : 'bg-amber-600'}
                  ${isMe ? 'ring-2 ring-blue-500' : ''}`}>
                  <div className="text-lg mb-0.5">
                    {actualRank === 1 ? '🥇' : actualRank === 2 ? '🥈' : '🥉'}
                  </div>
                  <div className="text-xs font-bold text-slate-800 truncate w-full text-center">
                    {e.display_name}{isMe ? ' (You)' : ''}
                  </div>
                  <div className="text-xs text-slate-700 mt-0.5">
                    {e.sets_passed}/6 sets
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Full table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Full Rankings</span>
          <span className="text-xs text-slate-400">· auto-updates on page refresh</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide w-12">#</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide">Student</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide text-center">Sets Passed</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide text-right">Best Score</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide text-right">Avg Score</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide text-right hidden sm:table-cell">Attempts</th>
                <th className="px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wide text-right hidden md:table-cell">Last Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {entries.map((entry, idx) => {
                const rank = idx + 1
                const isMe = entry.student_id === currentUserId
                return (
                  <tr
                    key={entry.student_id}
                    className={`transition-colors ${isMe ? 'bg-blue-50 hover:bg-blue-100' : 'hover:bg-slate-50'}`}
                  >
                    <td className="px-4 py-3 text-center">
                      <RankBadge rank={rank} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">
                        {entry.display_name}
                        {isMe && (
                          <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full font-semibold">You</span>
                        )}
                      </div>
                      <div className="mt-1">
                        <SetProgress passed={entry.sets_passed} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-bold tabular-nums text-sm ${
                        entry.sets_passed === 6 ? 'text-green-700' :
                        entry.sets_passed >= 3 ? 'text-blue-700' : 'text-slate-700'
                      }`}>
                        {entry.sets_passed} / 6
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ScoreBadge score={entry.best_score} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ScoreBadge score={entry.avg_score} />
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500 text-sm hidden sm:table-cell tabular-nums">
                      {entry.total_submitted}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400 text-xs hidden md:table-cell">
                      {entry.last_active
                        ? new Date(entry.last_active).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
                        : '—'}
                    </td>
                  </tr>
                )
              })}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400 text-sm">
                    No submitted attempts yet — be the first to complete a set!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Back link */}
      <div className="mt-6 text-center">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-700 transition-colors">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
