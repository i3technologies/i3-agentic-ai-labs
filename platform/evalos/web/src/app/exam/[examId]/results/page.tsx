import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import CertificateButton from './certificate-button'
import StudyCoachPanel from './study-coach-panel'

interface ResultsPageProps {
  params: { examId: string }
  searchParams: { attemptId?: string }
}

interface AttemptRow {
  id: string
  exam_id: string
  exam_title: string
  exam_code: string
  pass_threshold: number
  question_snapshot: QuestionSnap[]
  answers: Record<string, string | string[]>
  score: number
  max_score: number
  pct_score: number
  passed: boolean
  submitted_at: string
}

interface QuestionSnap {
  id: string
  text: string
  type: string
  question_type: string
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_number: number
  domain_name: string
  topic: string
}

interface DomainRow {
  domain_number: number
  domain_name: string
  correct: number
  total: number
  pct: number
}

async function getAttemptResults(attemptId: string, userId: string): Promise<AttemptRow | null> {
  const { rows } = await pool.query<AttemptRow>(
    `SELECT
       qa.id,
       qa.exam_id,
       e.title AS exam_title,
       e.code AS exam_code,
       COALESCE(e.pass_threshold, 68) AS pass_threshold,
       qa.question_snapshot,
       qa.answers,
       qa.score,
       qa.max_score,
       qa.pct_score,
       qa.passed,
       qa.submitted_at
     FROM quiz_attempts qa
     JOIN exams e ON e.id = qa.exam_id
     WHERE qa.id = $1 AND qa.student_id = $2 AND qa.status = 'submitted'`,
    [attemptId, userId]
  )
  return rows[0] ?? null
}

function computeDomainBreakdown(
  snapshot: QuestionSnap[],
  answers: Record<string, string | string[]>
): DomainRow[] {
  const map = new Map<number, { domain_name: string; correct: number; total: number }>()

  for (const q of snapshot) {
    const key = q.domain_number
    if (!map.has(key)) {
      map.set(key, { domain_name: q.domain_name, correct: 0, total: 0 })
    }
    const entry = map.get(key)!
    entry.total += 1

    const ans = answers[q.id]
    const isMultiple = q.type === 'MR' || q.question_type === 'multiple_response' || q.question_type === 'MR'

    if (isMultiple) {
      const given = ((ans as string[]) ?? []).slice().sort()
      const expected = [...q.correct_answers].sort()
      if (JSON.stringify(given) === JSON.stringify(expected)) entry.correct += 1
    } else {
      if (ans === q.correct_answers[0]) entry.correct += 1
    }
  }

  return Array.from(map.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([domain_number, v]) => ({
      domain_number,
      domain_name: v.domain_name,
      correct: v.correct,
      total: v.total,
      pct: v.total > 0 ? Math.round((v.correct / v.total) * 100) : 0,
    }))
}

export default async function ResultsPage({ params, searchParams }: ResultsPageProps) {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
  const examId = params.examId
  const attemptId = searchParams.attemptId ?? ''

  if (!UUID_RE.test(examId) || !UUID_RE.test(attemptId)) redirect('/dashboard')

  const userId = session.user.userId || session.user.email || ''
  const attempt = await getAttemptResults(attemptId, userId)

  if (!attempt) redirect('/dashboard')

  const domains = computeDomainBreakdown(attempt.question_snapshot, attempt.answers)
  const score = Math.round(attempt.pct_score)
  const passed = attempt.passed

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Score hero */}
      <div className="bg-white border border-slate-200 rounded-xl p-8 text-center mb-8">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
          {attempt.exam_code} — {attempt.exam_title}
        </div>
        <div className={`text-7xl font-extrabold tabular-nums mb-3 ${passed ? 'text-green-600' : 'text-red-600'}`}>
          {score}%
        </div>
        <span
          className={`inline-flex items-center px-4 py-1.5 rounded-full text-sm font-bold ${
            passed
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          {passed ? 'PASS' : 'FAIL'}
        </span>
        <p className="mt-3 text-sm text-slate-500">
          Passing score: <span className="font-medium text-slate-700">{attempt.pass_threshold}%</span>
          {attempt.submitted_at && (
            <>
              {' '}— Completed{' '}
              <span className="font-medium text-slate-700">
                {new Date(attempt.submitted_at).toLocaleString()}
              </span>
            </>
          )}
        </p>
        <p className="text-sm text-slate-500 mt-1">
          {attempt.score} correct out of {attempt.max_score} questions
        </p>
      </div>

      {/* Domain breakdown */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">Score by Domain</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">#</th>
              <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Domain</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Correct</th>
              <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Score</th>
              <th className="px-5 py-3 w-32" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {domains.map((d) => (
              <tr key={d.domain_number} className="hover:bg-slate-50">
                <td className="px-5 py-3 text-slate-400 text-xs">{d.domain_number}</td>
                <td className="px-5 py-3 text-slate-800">{d.domain_name}</td>
                <td className="px-5 py-3 text-right text-slate-600">
                  {d.correct}/{d.total}
                </td>
                <td className="px-5 py-3 text-right">
                  <span
                    className={`font-semibold ${
                      d.pct >= attempt.pass_threshold
                        ? 'text-green-700'
                        : 'text-red-600'
                    }`}
                  >
                    {d.pct}%
                  </span>
                </td>
                <td className="px-5 py-3">
                  <div className="w-full bg-slate-200 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${d.pct >= attempt.pass_threshold ? 'bg-green-500' : 'bg-red-400'}`}
                      style={{ width: `${d.pct}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* AI Study Coach */}
      <StudyCoachPanel
        attemptId={attempt.id}
        passed={passed}
        score={score}
      />

      {/* Question review */}
      <div className="mb-8">
        <h2 className="font-semibold text-slate-800 mb-4">Question Review</h2>
        <div className="space-y-4">
          {attempt.question_snapshot.map((q, idx) => {
            const ans = attempt.answers[q.id]
            const isMultiple = q.type === 'MR' || q.question_type === 'multiple_response' || q.question_type === 'MR'

            let isCorrect: boolean
            if (isMultiple) {
              const given = ((ans as string[]) ?? []).slice().sort()
              const expected = [...q.correct_answers].sort()
              isCorrect = JSON.stringify(given) === JSON.stringify(expected)
            } else {
              isCorrect = ans === q.correct_answers[0]
            }

            const givenLabels = Array.isArray(ans) ? ans : ans ? [ans] : []

            return (
              <div
                key={q.id}
                className={`bg-white border rounded-xl p-5 ${
                  isCorrect ? 'border-green-200' : 'border-red-200'
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                    Q{idx + 1} — {q.domain_name}
                  </span>
                  <span
                    className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                      isCorrect
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {isCorrect ? 'Correct' : 'Incorrect'}
                  </span>
                </div>

                <p className="text-sm font-medium text-slate-900 mb-3 leading-relaxed whitespace-pre-wrap">
                  {q.text}
                </p>

                <div className="space-y-1.5">
                  {q.options.map((opt) => {
                    const isYours = givenLabels.includes(opt.label)
                    const isCorrectOpt = q.correct_answers.includes(opt.label)
                    let optClass = 'border-slate-200 text-slate-600'
                    if (isCorrectOpt) optClass = 'border-green-400 bg-green-50 text-green-800 font-medium'
                    else if (isYours && !isCorrectOpt) optClass = 'border-red-400 bg-red-50 text-red-700'

                    return (
                      <div
                        key={opt.label}
                        className={`flex items-start gap-2 p-2 rounded border text-xs ${optClass}`}
                      >
                        <span className="font-semibold w-4 flex-shrink-0">{opt.label}.</span>
                        <span>{opt.text}</span>
                        <span className="ml-auto flex-shrink-0">
                          {isCorrectOpt && <span className="text-green-600 font-semibold">Correct</span>}
                          {isYours && !isCorrectOpt && <span className="text-red-600 font-semibold">Your answer</span>}
                        </span>
                      </div>
                    )
                  })}
                </div>

                {q.explanation && (
                  <div className="mt-3 p-3 bg-slate-50 rounded border border-slate-200 text-xs text-slate-600 leading-relaxed">
                    <span className="font-semibold text-slate-700">Explanation: </span>
                    {q.explanation}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 justify-center">
        {/* Certificate download — available for any passing attempt */}
        {attempt.passed && (
          <CertificateButton attemptId={attempt.id} />
        )}
        <Link
          href={`/exam/${examId}`}
          className="px-6 py-2.5 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-colors"
        >
          Retake Exam
        </Link>
        <Link
          href="/dashboard"
          className="px-6 py-2.5 border border-slate-300 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
