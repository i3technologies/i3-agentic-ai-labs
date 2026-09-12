import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { traceLangfuse, estimateTokens } from '@/lib/langfuse'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// LiteLLM gateway (preferred) — falls back to direct Ollama if not configured
const LITELLM_URL   = process.env.LITELLM_URL   ?? ''
const LITELLM_KEY   = process.env.LITELLM_KEY   ?? ''
const LITELLM_MODEL = process.env.LITELLM_MODEL ?? 'qwen-fast'

// Direct Ollama fallback (i3-ott, always available)
const OLLAMA_URL   = process.env.OLLAMA_URL   ?? 'http://ollama.i3-ott.svc.cluster.local:11434'
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
      const labelToText = Object.fromEntries(q.options.map(o => [o.label, o.text]))
      const studentText = studentLabels.map(l => `${l}. ${labelToText[l] ?? l}`).join('; ')
      const correctText = correctLabels.map(l => `${l}. ${labelToText[l] ?? l}`).join('; ')

      wrong.push({
        domain: q.domain_name,
        topic: q.topic,
        question: q.text.slice(0, 200),
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
    .sort((a, b) => a.pct - b.pct)
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
  const wrongSample = wrongAnswers.slice(0, 5)

  const domainLines = weakDomains.map(d =>
    `- ${d.domain}: ${d.pct}% (${d.wrong}/${d.total} wrong)`
  ).join('\n')

  const wrongLines = wrongSample.map((w, i) =>
    `Q${i + 1} [${w.domain}] ${w.question.slice(0, 120)}\n` +
    `  Student: ${w.studentAnswer.slice(0, 80)} | Correct: ${w.correctAnswer.slice(0, 80)}`
  ).join('\n')

  return `You are an IBM watsonx Orchestrate study coach for exam ${examCode}.

Student: ${studentName} | Score: ${score}% (${passed ? 'PASS' : 'FAIL'})

WEAK DOMAINS:
${domainLines || 'None'}

WRONG ANSWERS (sample):
${wrongLines || 'None — perfect score!'}

Write a coaching report with these sections:
## Overall Assessment (2 sentences)
## Domain Focus Areas (2 tips per weak domain, name specific IBM features)
## Key Misconceptions (2-3 patterns from wrong answers)
## 3-Day Study Plan (concrete daily tasks)
## Encouragement (one sentence for ${studentName})

Warm, direct tone. 300-400 words total.`
}

/**
 * Call LiteLLM OpenAI-compatible /chat/completions endpoint.
 * Returns the assistant message content.
 */
async function callLiteLLM(prompt: string, signal: AbortSignal): Promise<string> {
  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${LITELLM_KEY}`,
    },
    body: JSON.stringify({
      model: LITELLM_MODEL,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.7,
      max_tokens: 500,
      top_p: 0.9,
    }),
    signal,
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`LiteLLM ${resp.status}: ${err}`)
  }
  const data = await resp.json()
  return data.choices?.[0]?.message?.content ?? ''
}

/**
 * Call Ollama /api/generate endpoint directly (fallback path).
 */
async function callOllama(prompt: string, signal: AbortSignal): Promise<string> {
  const resp = await fetch(`${OLLAMA_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: OLLAMA_MODEL,
      prompt,
      stream: false,
      options: { temperature: 0.7, num_predict: 500, top_p: 0.9 },
    }),
    signal,
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`Ollama ${resp.status}: ${err}`)
  }
  const data = await resp.json()
  return data.response ?? ''
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

  let coachReport = ''
  const traceId = randomUUID()
  const inferenceStart = new Date()
  let modelUsed = ''

  try {
    const signal = AbortSignal.timeout(110_000)

    // Prefer LiteLLM if configured; fall back to direct Ollama
    if (LITELLM_URL && LITELLM_KEY) {
      try {
        coachReport = await callLiteLLM(prompt, signal)
        modelUsed = `litellm/${LITELLM_MODEL}`
      } catch (litellmErr) {
        console.warn('[study-coach] LiteLLM failed, falling back to Ollama:', litellmErr)
        coachReport = await callOllama(prompt, signal)
        modelUsed = `ollama/${OLLAMA_MODEL}`
      }
    } else {
      coachReport = await callOllama(prompt, signal)
      modelUsed = `ollama/${OLLAMA_MODEL}`
    }

    const inferenceEnd = new Date()
    const latencyMs = inferenceEnd.getTime() - inferenceStart.getTime()

    traceLangfuse({
      traceId,
      name: 'study-coach',
      userId,
      metadata: {
        examCode, score, passed, attemptId,
        wrongCount: wrongAnswers.length,
        weakDomains: domainSummary.filter(d => d.pct < 90).map(d => d.domain),
        modelUsed,
      },
      input: prompt,
      output: coachReport,
      startTime: inferenceStart.toISOString(),
      endTime: inferenceEnd.toISOString(),
      modelName: modelUsed,
      promptTokens: estimateTokens(prompt),
      completionTokens: estimateTokens(coachReport),
      latencyMs,
      level: 'DEFAULT',
    })
  } catch (err) {
    const inferenceEnd = new Date()
    console.error('[study-coach] Inference error:', err)
    traceLangfuse({
      traceId,
      name: 'study-coach',
      userId,
      metadata: { examCode, score, passed, attemptId },
      input: prompt,
      output: `ERROR: ${String(err)}`,
      startTime: inferenceStart.toISOString(),
      endTime: inferenceEnd.toISOString(),
      modelName: modelUsed || OLLAMA_MODEL,
      latencyMs: inferenceEnd.getTime() - inferenceStart.getTime(),
      level: 'ERROR',
    })
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
      modelUsed,
      weakDomains: domainSummary.filter(d => d.pct < 90).map(d => d.domain),
      wrongCount: wrongAnswers.length,
      totalQuestions: snapshot.length,
    },
  })
}
