import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

interface Exam {
  id: string
  title: string
  code: string
  description: string
  duration_minutes: number
  pass_threshold: number
  max_attempts: number
  question_count: number
  attempt_count: number
  best_score: number | null
  last_score: number | null
  last_passed: boolean | null
  prerequisite_exam_id: string | null
  prerequisite_code: string | null
  prerequisite_passed: boolean
}

interface RecentAttempt {
  id: string
  exam_id: string
  exam_title: string
  exam_code: string
  pct_score: number | null
  passed: boolean | null
  started_at: string
  submitted_at: string | null
  status: string
}

async function getExamsWithAttempts(userId: string): Promise<Exam[]> {
  const { rows } = await pool.query<Exam>(
    `
    SELECT
      e.id,
      e.title,
      e.code,
      e.description,
      e.duration_minutes,
      COALESCE(e.pass_threshold, 90)  AS pass_threshold,
      COALESCE(e.max_attempts, 5)     AS max_attempts,
      (
        SELECT COUNT(*)::int
        FROM questions q
        WHERE q.set_number = REGEXP_REPLACE(e.code, '^.*SET', '', 'g')::int
          AND q.is_active = true
      ) AS question_count,
      COUNT(qa.id)::int AS attempt_count,
      MAX(qa.pct_score) AS best_score,
      (
        SELECT pct_score
        FROM quiz_attempts
        WHERE exam_id = e.id AND student_id = $1
        ORDER BY started_at DESC
        LIMIT 1
      ) AS last_score,
      (
        SELECT passed
        FROM quiz_attempts
        WHERE exam_id = e.id AND student_id = $1
        ORDER BY started_at DESC
        LIMIT 1
      ) AS last_passed,
      e.prerequisite_exam_id,
      pre.code AS prerequisite_code,
      -- prerequisite is met if the student has at least one passing submitted attempt
      COALESCE((
        SELECT true
        FROM quiz_attempts pqa
        WHERE pqa.exam_id = e.prerequisite_exam_id
          AND pqa.student_id = $1
          AND pqa.status IN ('submitted', 'graded')
          AND pqa.passed = true
        LIMIT 1
      ), e.prerequisite_exam_id IS NULL) AS prerequisite_passed
    FROM exams e
    LEFT JOIN exams pre ON pre.id = e.prerequisite_exam_id
    LEFT JOIN quiz_attempts qa
      ON qa.exam_id = e.id AND qa.student_id = $1
    WHERE e.is_published = true
    GROUP BY e.id, pre.code
    ORDER BY e.code
    `,
    [userId]
  )
  return rows
}

async function getRecentAttempts(userId: string): Promise<RecentAttempt[]> {
  const { rows } = await pool.query<RecentAttempt>(
    `
    SELECT
      qa.id,
      qa.exam_id,
      e.title AS exam_title,
      e.code AS exam_code,
      qa.pct_score,
      qa.passed,
      qa.started_at,
      qa.submitted_at,
      qa.status
    FROM quiz_attempts qa
    JOIN exams e ON e.id = qa.exam_id
    WHERE qa.student_id = $1
    ORDER BY qa.started_at DESC
    LIMIT 10
    `,
    [userId]
  )
  return rows
}

function ScoreBadge({
  score,
  passed,
}: {
  score: number | null
  passed: boolean | null
}) {
  if (score === null) return null
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
        passed
          ? 'bg-green-100 text-green-800'
          : 'bg-red-100 text-red-800'
      }`}
    >
      {Math.round(score)}% {passed ? 'Pass' : 'Fail'}
    </span>
  )
}

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const userId = session.user.userId || session.user.email || ''
  const [exams, recentAttempts] = await Promise.all([
    getExamsWithAttempts(userId),
    getRecentAttempts(userId),
  ])

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-slate-500 text-sm">
          Welcome back, <span className="font-medium text-slate-700">{session.user.name || session.user.email}</span>.
          {' '}Complete each set with ≥90% to unlock the next one.
        </p>
      </div>

      {/* Exam cards */}
      <section>
        <h2 className="text-base font-semibold text-slate-700 mb-4 uppercase tracking-wide text-xs">
          Practice Exam Sets
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {exams.map((exam) => {
            const attemptsLeft = Math.max(0, exam.max_attempts - exam.attempt_count)
            const isExhausted = exam.attempt_count >= exam.max_attempts && !exam.last_passed
            const isLocked = !exam.prerequisite_passed
            const isPassed = exam.last_passed === true
            const isDisabled = isLocked || isExhausted

            return (
              <div
                key={exam.id}
                className={`bg-white border rounded-xl p-5 flex flex-col gap-3 transition-colors ${
                  isDisabled
                    ? 'border-slate-200 opacity-60'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                {/* Card header */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
                      {exam.code}
                    </span>
                    <h3 className="text-base font-semibold text-slate-900 mt-0.5">
                      {exam.title}
                    </h3>
                  </div>
                  {isPassed ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                      ✓ Passed
                    </span>
                  ) : exam.last_score !== null ? (
                    <ScoreBadge score={exam.last_score} passed={exam.last_passed} />
                  ) : null}
                </div>

                <p className="text-sm text-slate-500 flex-1 leading-relaxed">
                  {exam.description ?? 'IBM watsonx Orchestrate C1000-207 practice exam.'}
                </p>

                {/* Stats row */}
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span>
                    <span className="font-semibold text-slate-700">{exam.question_count || 60}</span> questions
                  </span>
                  <span>
                    <span className="font-semibold text-slate-700">{exam.duration_minutes ?? 90}</span> min
                  </span>
                  <span>
                    Pass at <span className="font-semibold text-slate-700">{exam.pass_threshold}%</span>
                  </span>
                </div>

                {/* Attempts tracker */}
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    {Array.from({ length: exam.max_attempts }).map((_, i) => (
                      <span
                        key={i}
                        className={`w-3 h-3 rounded-full border ${
                          i < exam.attempt_count
                            ? 'bg-slate-400 border-slate-400'
                            : 'bg-white border-slate-300'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-slate-400">
                    {exam.attempt_count}/{exam.max_attempts} attempts used
                  </span>
                </div>

                {/* Status / action */}
                {isLocked ? (
                  <div className="mt-auto flex items-center gap-2 bg-slate-50 border border-slate-200 text-slate-500 text-sm font-medium rounded-lg py-2.5 px-4">
                    <span>🔒</span>
                    <span className="text-xs">Pass {exam.prerequisite_code} first</span>
                  </div>
                ) : isExhausted ? (
                  <div className="mt-auto flex items-center justify-center gap-2 bg-red-50 border border-red-200 text-red-700 text-xs font-medium rounded-lg py-2.5 px-4">
                    No attempts remaining
                  </div>
                ) : (
                  <Link
                    href={`/exam/${exam.id}`}
                    className="mt-auto w-full flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-lg py-2.5 transition-colors"
                  >
                    {exam.attempt_count > 0 && !isPassed ? `Retake (${attemptsLeft} left)` : isPassed ? 'Retake Exam' : 'Start Exam'}
                  </Link>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* AI Features quick-launch */}
      <section className="mt-12">
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-4">
          AI-Powered Features
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">

          {/* AI Study Coach */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.384A5 5 0 0112 17.5a5 5 0 01-3.071-1.088l-.348-.383z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">AI Study Coach</p>
                <p className="text-xs text-slate-500">Personalised after each exam</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 flex-1">
              After submitting a practice set, get a domain-by-domain analysis and a 3-day study plan powered by on-cluster AI.
            </p>
            <p className="text-xs text-blue-600 font-medium">
              Available on every results page →
            </p>
          </div>

          {/* AI Interview */}
          <div className="bg-gradient-to-br from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-purple-600 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3v-3z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">AI Interview Round</p>
                <p className="text-xs text-slate-500">5 questions · real-time scoring</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 flex-1">
              3 technical questions + 2 coding challenges. Evaluated instantly by AI against IBM watsonx Orchestrate rubrics.
            </p>
            <Link
              href="/interview"
              className="mt-auto w-full flex items-center justify-center gap-2 bg-purple-700 hover:bg-purple-800 text-white text-xs font-medium rounded-lg py-2 transition-colors"
            >
              Start Interview →
            </Link>
          </div>

          {/* Coding Labs */}
          <div className="bg-gradient-to-br from-slate-50 to-slate-100 border border-slate-200 rounded-xl p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">Coding Labs</p>
                <p className="text-xs text-slate-500">JS · Python · SQL · AI review</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 flex-1">
              Hands-on IBM watsonx integration coding exercises with Monaco editor, live execution, and AI code review.
            </p>
            <Link
              href="/lab"
              className="mt-auto w-full flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-lg py-2 transition-colors"
            >
              Open Labs →
            </Link>
          </div>

        </div>
      </section>

      {/* Recent attempts */}
      {recentAttempts.length > 0 && (
        <section className="mt-12">
          <h2 className="text-base font-semibold text-slate-700 mb-4 uppercase tracking-wide text-xs">
            Recent Attempts
          </h2>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Exam</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Score</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide hidden sm:table-cell">Date</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentAttempts.map((attempt) => (
                  <tr key={attempt.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-800">{attempt.exam_title}</span>
                      <span className="ml-2 text-xs text-slate-400">{attempt.exam_code}</span>
                    </td>
                    <td className="px-4 py-3">
                      {attempt.pct_score !== null ? (
                        <span className="font-semibold text-slate-800">
                          {Math.round(attempt.pct_score)}%
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {attempt.status === 'submitted' ? (
                        <ScoreBadge score={attempt.pct_score} passed={attempt.passed} />
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800">
                          In Progress
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400 hidden sm:table-cell">
                      {new Date(attempt.started_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {attempt.status === 'submitted' ? (
                        <div className="flex flex-col items-end gap-1">
                          <Link
                            href={`/exam/${attempt.exam_id}/results?attemptId=${attempt.id}`}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            View Results
                          </Link>
                          {attempt.passed && (
                            <Link
                              href={`/exam/${attempt.exam_id}/results?attemptId=${attempt.id}`}
                              className="text-xs text-green-700 font-semibold hover:underline"
                            >
                              🏅 Get Certificate
                            </Link>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
