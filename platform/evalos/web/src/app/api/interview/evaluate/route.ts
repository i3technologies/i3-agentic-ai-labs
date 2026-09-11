import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { traceLangfuse, estimateTokens } from '@/lib/langfuse'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const LITELLM_URL  = process.env.LITELLM_URL  ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY  = process.env.LITELLM_KEY  ?? ''

// Models: qwen-heavy for text evaluation, coder for code questions
const TEXT_MODEL = 'qwen-heavy'
const CODE_MODEL = 'coder'

interface EvaluateRequest {
  examId: string
  questionId: string
  questionText: string
  questionType: 'text' | 'code'
  language?: string       // 'javascript' | 'python' | 'sql' — for code questions
  studentAnswer: string
  rubric: string          // expected answer criteria
}

interface EvaluationResult {
  score: number           // 0–100
  maxScore: number        // always 100
  passed: boolean         // score >= 60
  feedback: string        // 2-4 sentences of detailed feedback
  strengths: string[]     // what the student got right
  improvements: string[]  // specific gaps to address
  modelUsed: string
}

function buildTextEvalPrompt(q: EvaluateRequest): string {
  return `You are an expert IBM watsonx Orchestrate examiner. Evaluate the following student answer against the rubric.

Question: ${q.questionText}

Rubric (what a perfect answer must cover):
${q.rubric}

Student's Answer:
${q.studentAnswer}

Evaluate strictly and fairly. Return ONLY a JSON object, no markdown:
{
  "score": <0-100>,
  "feedback": "<2-4 sentences of specific, educational feedback>",
  "strengths": ["<what was correct>", ...],
  "improvements": ["<specific gap or misconception to fix>", ...]
}

Scoring guide:
- 90-100: Covers all rubric points accurately with appropriate terminology
- 70-89:  Covers most points, minor gaps or imprecision
- 50-69:  Covers core concept but misses important details
- 30-49:  Partially correct, significant gaps
- 0-29:   Fundamentally incorrect or missing`
}

function buildCodeEvalPrompt(q: EvaluateRequest): string {
  return `You are an expert code reviewer for IBM watsonx certification coding challenges.

Question: ${q.questionText}
Language: ${q.language ?? 'javascript'}

Rubric:
${q.rubric}

Student's Code:
\`\`\`${q.language ?? 'javascript'}
${q.studentAnswer}
\`\`\`

Evaluate: correctness, approach, edge cases, code quality. Return ONLY JSON:
{
  "score": <0-100>,
  "feedback": "<2-4 sentences: does it work, is it idiomatic, key issues>",
  "strengths": ["<correct aspects>", ...],
  "improvements": ["<specific fix or improvement>", ...]
}

Scoring: 90-100 (correct + clean) · 70-89 (correct, style issues) · 50-69 (mostly right, bugs) · 30-49 (wrong approach) · 0-29 (does not solve problem)`
}

async function callLLM(
  prompt: string,
  model: string,
  signal: AbortSignal
): Promise<string> {
  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${LITELLM_KEY}`,
    },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.2,   // low temperature for consistent evaluation
      max_tokens: 800,
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

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  let body: EvaluateRequest
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { examId, questionId, questionText, questionType, language, studentAnswer, rubric } = body
  if (!questionText || !studentAnswer || !rubric) {
    return NextResponse.json({ error: 'questionText, studentAnswer, and rubric are required' }, { status: 400 })
  }
  if (!studentAnswer.trim()) {
    return NextResponse.json<EvaluationResult>({
      score: 0, maxScore: 100, passed: false,
      feedback: 'No answer provided.',
      strengths: [],
      improvements: ['Provide a substantive answer to receive credit.'],
      modelUsed: 'n/a',
    })
  }

  const model = questionType === 'code' ? CODE_MODEL : TEXT_MODEL
  const prompt = questionType === 'code'
    ? buildCodeEvalPrompt(body)
    : buildTextEvalPrompt(body)

  const traceId = randomUUID()
  const start = new Date()
  const userId = session.user.userId || session.user.email || ''

  try {
    const rawContent = await callLLM(prompt, model, AbortSignal.timeout(120_000))

    // Strip accidental markdown fences
    const cleaned = rawContent
      .replace(/^```(?:json)?\n?/m, '')
      .replace(/\n?```$/m, '')
      .trim()

    let parsed: { score: number; feedback: string; strengths: string[]; improvements: string[] }
    try {
      parsed = JSON.parse(cleaned)
    } catch {
      throw new Error(`LLM returned malformed JSON: ${rawContent.slice(0, 200)}`)
    }

    const score = Math.max(0, Math.min(100, Math.round(parsed.score ?? 0)))
    const end = new Date()

    // Persist evaluation to DB
    await pool.query(
      `INSERT INTO ai_interview_evaluations
         (id, exam_id, question_id, student_id, question_type, student_answer,
          score, feedback, strengths, improvements, model_used, created_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NOW())
       ON CONFLICT (exam_id, question_id, student_id) DO UPDATE
         SET score=$7, feedback=$8, strengths=$9, improvements=$10,
             model_used=$11, updated_at=NOW()`,
      [
        randomUUID(), examId, questionId, userId,
        questionType, studentAnswer.slice(0, 5000),
        score, parsed.feedback ?? '',
        JSON.stringify(parsed.strengths ?? []),
        JSON.stringify(parsed.improvements ?? []),
        model,
      ]
    )

    traceLangfuse({
      traceId,
      name: 'ai-interview-evaluate',
      userId,
      metadata: { examId, questionId, questionType, score, model },
      input: prompt,
      output: rawContent,
      startTime: start.toISOString(),
      endTime: end.toISOString(),
      modelName: model,
      promptTokens: estimateTokens(prompt),
      completionTokens: estimateTokens(rawContent),
      latencyMs: end.getTime() - start.getTime(),
      level: 'DEFAULT',
    })

    const result: EvaluationResult = {
      score,
      maxScore: 100,
      passed: score >= 60,
      feedback: parsed.feedback ?? '',
      strengths: parsed.strengths ?? [],
      improvements: parsed.improvements ?? [],
      modelUsed: model,
    }
    return NextResponse.json(result)
  } catch (err) {
    const end = new Date()
    console.error('[interview/evaluate] Error:', err)
    traceLangfuse({
      traceId,
      name: 'ai-interview-evaluate',
      userId,
      metadata: { examId, questionId, questionType },
      input: prompt,
      output: `ERROR: ${String(err)}`,
      startTime: start.toISOString(),
      endTime: end.toISOString(),
      modelName: model,
      latencyMs: end.getTime() - start.getTime(),
      level: 'ERROR',
    })
    return NextResponse.json({ error: 'Evaluation failed', detail: String(err) }, { status: 502 })
  }
}
