import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const OLLAMA_URL = process.env.OLLAMA_URL ?? 'http://ollama.i3-ott.svc.cluster.local:11434'
const OLLAMA_MODEL = process.env.OLLAMA_MODEL ?? 'mistral:7b-instruct-q4_K_M'

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

interface WrongQuestion {
  domain: string
  topic: string
  question: string
  studentAnswer: string
  correctAnswer: string
  explanation: string
}

function buildWrongAnswers(
  snapshot: QuestionSnap[],
  answers: Record<string, string | string[]>
): WrongQuestion[] {
  const wrong: WrongQuestion[] = []

  for (const q of snapshot) {
    const ans = answers[q.id]
    const isMultiple = q.type === 'MR' || q.question_type === 'MR' || q.question_type === 'multiple_response'

    let isCorrect: boolean
    if (isMultiple) {
      const given = ((ans as string[]) ?? []).slice().sort()
      const expected = [...q.correct_answers].sort()
      isCorrect = JSON.stringify(given) === JSON.stringify(expected)
    } else {
      isCorrect = ans === q.correct_answers[0]
    }

    if (!isCorrect) {
      const studentLabels = Array.isArray(ans) ? ans : ans ? [ans] : ['(no answer)']
      const correctLabels = q.correct_answers

      // Resolve labels to option text
      const labelToText = Object.fromEntries(q.options.map(o => [o.label, o.text]))
      const studentText = studentLabels.map(l => `${l}. ${labelToText[l] ?? l}`).join('; ')
      const correctText = correctLabels.map(l => `${l}. ${labelToText[l] ?? l}`).join('; ')

      wrong.push({
        domain: q.domain_name,
        topic: q.topic,
        question: q.text.slice(0, 200), // truncate for token budget
        studentAnswer: studentText,
        correctAnswer: correctText,
        explanation: q.explanation?.slice(0, 300) ?? '',
      })
    }
  }

  return wrong
}

function buildDomainSummary(
  snapshot: QuestionSnap[],
  answers: Record<string, string | string[]>
): { domain: string; pct: number; wrong: number; total: number }[] {
  const map = new Map<string, { correct: number; total: number }>()

  for (const q of snapshot) {
    const key = q.domain_name
    if (!map.has(key)) map.set(key, { correct: 0, total: 0 })
    const e = map.get(key)!
    e.total++

    const ans = answers[q.id]
    const isMultiple = q.type === 'MR' || q.question_type === 'MR' || q.question_type === 'multiple_response'
    let isCorrect: boolean
    if (isMultiple) {
      const given = ((ans as string[]) ?? []).slice().sort()
      const expected = [...q.correct_answers].sort()
      isCorrect = JSON.stringify(given) === JSON.stringify(expected)
    } else {
      isCorrect = ans === q.correct_answers[0]
    }
    if (isCorrect) e.correct++
  }

  return Array.from(map.entries())
    .map(([domain, v]) => ({
      domain,
      pct: Math.round((v.correct / v.total) * 100),
      wrong: v.total - v.correct,
      total: v.total,
    }))
    .sort((a, b) => a.pct - b.pct) // weakest first
}

function buildPrompt(
  studentName: string,
  examCode: string,
  score: number,
  passed: boolean,
  domainSummary: { domain: string; pct: number; wrong: number; total: number }[],
  wrongAnswers: WrongQuestion[]
): string {
  const weakDomains = domainSummary.filter(d => d.pct < 90).slice(0, 3)
  const wrongSample = wrongAnswers.slice(0, 8) // keep prompt compact

  const domainLines = weakDomains.map(d =>
    `- ${d.domain}: ${d.pct}% (${d.wrong}/${d.total} wrong)`
  ).join('\n')

  const wrongLines = wrongSample.map((w, i) =>
    `Q${i + 1} [${w.domain} — ${w.topic}]\n` +
    `  Question: ${w.question}\n` +
    `  Student answered: ${w.studentAnswer}\n` +
    `  Correct answer: ${w.correctAnswer}\n` +
    (w.explanation ? `  Explanation: ${w.explanation}` : '')
  ).join('\n\n')

  return `You are an expert IBM watsonx Orchestrate study coach helping a student prepare for the IBM C1000-207 certification exam.

Student: ${studentName}
Exam: ${examCode}
Score: ${score}% — ${passed ? 'PASS' : 'FAIL'}

WEAK DOMAINS (below 90%):
${domainLines || 'None — all domains above threshold'}

SAMPLE WRONG ANSWERS (up to 8):
${wrongLines || 'No wrong answers — perfect score!'}

Write a personalised, encouraging study coaching report. Structure your response with exactly these sections:

## Overall Assessment
2-3 sentences about the student's performance and general readiness.

## Domain Focus Areas
For each weak domain, give 2-3 specific, actionable study tips referencing real IBM watsonx Orchestrate concepts (skills, agents, flows, orchestration, governance, etc.). Be concrete — name specific features, menus, or docs.

## Key Misconceptions
Based on the wrong answers above, identify 2-3 patterns in the student's thinking and correct them clearly.

## 3-Day Study Plan
A concrete day-by-day plan to improve score by next attempt. Include specific IBM documentation sections or topics to review.

## Encouragement
One final motivating sentence personalised to ${studentName}.

Keep the tone warm, direct, and professional. Do not invent question content beyond what is shown. Total length: 350-500 words.`
}

export async function GET(
  _req: Request,
  { params }: { params: { attemptId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { attemptId } = params
  if (!UUID_RE.test(attemptId)) return NextResponse.json({ error: 'Invalid attempt ID' }, { status: 400 })

  const userId = session.user.userId || session.user.email || ''

  // Fetch attempt + exam code
  const { rows } = await pool.query(
    `SELECT qa.question_snapshot, qa.answers, qa.pct_score, qa.passed,
            e.code AS exam_code, e.title AS exam_title
     FROM quiz_attempts qa
     JOIN exams e ON e.id = qa.exam_id
     WHERE qa.id = $1 AND qa.student_id = $2 AND qa.status = 'submitted'`,
    [attemptId, userId]
  )

  if (rows.length === 0) return NextResponse.json({ error: 'Attempt not found' }, { status: 404 })

  const row = rows[0]
  const snapshot: QuestionSnap[] = row.question_snapshot
  const answers: Record<string, string | string[]> = row.answers
  const score = Math.round(row.pct_score)
  const passed: boolean = row.passed
  const examCode: string = row.exam_code
  const studentName = session.user.name || session.user.email || 'Student'

  const domainSummary = buildDomainSummary(snapshot, answers)
  const wrongAnswers = buildWrongAnswers(snapshot, answers)

  const prompt = buildPrompt(studentName, examCode, score, passed, domainSummary, wrongAnswers)

  // Call Ollama
  let coachReport = ''
  try {
    const resp = await fetch(`${OLLAMA_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: OLLAMA_MODEL,
        prompt,
        stream: false,
        options: {
          temperature: 0.7,
          num_predict: 700,
          top_p: 0.9,
        },
      }),
      signal: AbortSignal.timeout(90_000), // 90s timeout for CPU inference
    })

    if (!resp.ok) {
      const err = await resp.text()
      console.error('[study-coach] Ollama error', resp.status, err)
      return NextResponse.json({ error: 'LLM unavailable', detail: err }, { status: 502 })
    }

    const data = await resp.json()
    coachReport = data.response ?? ''
  } catch (err) {
    console.error('[study-coach] Fetch error:', err)
    return NextResponse.json(
      { error: 'LLM request failed', detail: String(err) },
      { status: 502 }
    )
  }

  return NextResponse.json({
    report: coachReport,
    meta: {
      score,
      passed,
      examCode,
      weakDomains: domainSummary.filter(d => d.pct < 90).map(d => d.domain),
      wrongCount: wrongAnswers.length,
      totalQuestions: snapshot.length,
    },
  })
}
