import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export const dynamic = 'force-dynamic'

const LITELLM_URL   = process.env.LITELLM_URL   ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY   = process.env.LITELLM_KEY   ?? ''
const GENERATE_MODEL = 'qwen-heavy'  // Qwen2.5 14B for highest quality question generation

interface GenerateRequest {
  topic: string
  domain: string
  setNumber: number
  count: number            // 1–5
  difficulty: 'easy' | 'medium' | 'hard'
  questionTypes: ('SC' | 'MR')[]
}

interface GeneratedQuestion {
  text: string
  type: 'SC' | 'MR'
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_name: string
  topic: string
  set_number: number
}

function buildGenerationPrompt(req: GenerateRequest): string {
  const typeInstructions = req.questionTypes.includes('MR')
    ? 'Mix of Single Choice (SC, one correct answer) and Multiple Response (MR, 2-3 correct answers).'
    : 'Single Choice only (SC, one correct answer).'

  return `You are an expert IBM watsonx Orchestrate certification question author. Generate exactly ${req.count} high-quality multiple-choice exam questions on the following topic.

Topic: ${req.topic}
Domain: ${req.domain}
Set Number: ${req.setNumber}
Difficulty: ${req.difficulty}
Question types: ${typeInstructions}

Requirements:
- Questions must test real IBM watsonx Orchestrate concepts (not generic IT knowledge)
- Each question must have exactly 4 options labelled A, B, C, D
- For MR questions: 2 or 3 correct answers
- For SC questions: exactly 1 correct answer
- Explanations must be clear, educational, and reference specific IBM documentation/concepts
- Do NOT reuse questions from public IBM practice exams — create original content
- Difficulty "${req.difficulty}": ${req.difficulty === 'easy' ? 'Recall of core concepts' : req.difficulty === 'medium' ? 'Application of concepts in scenarios' : 'Synthesis across multiple IBM components, edge cases'}

Return ONLY a JSON array, no other text, no markdown code fences. Format:
[
  {
    "text": "Question text here?",
    "type": "SC",
    "options": [
      {"label": "A", "text": "Option A text"},
      {"label": "B", "text": "Option B text"},
      {"label": "C", "text": "Option C text"},
      {"label": "D", "text": "Option D text"}
    ],
    "correct_answers": ["B"],
    "explanation": "Explanation referencing IBM documentation or feature."
  }
]`
}

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  let body: GenerateRequest
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { topic, domain, setNumber, count, difficulty, questionTypes } = body
  if (!topic?.trim() || !domain?.trim()) {
    return NextResponse.json({ error: 'topic and domain are required' }, { status: 400 })
  }
  if (!count || count < 1 || count > 5) {
    return NextResponse.json({ error: 'count must be 1–5' }, { status: 400 })
  }

  const prompt = buildGenerationPrompt(body)

  try {
    const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LITELLM_KEY}`,
      },
      body: JSON.stringify({
        model: GENERATE_MODEL,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.8,
        max_tokens: 3000,
        top_p: 0.95,
      }),
      signal: AbortSignal.timeout(120_000),
    })

    if (!resp.ok) {
      const err = await resp.text()
      console.error('[question-generator] LiteLLM error', resp.status, err)
      return NextResponse.json({ error: 'LLM unavailable', detail: err }, { status: 502 })
    }

    const data = await resp.json()
    const rawContent: string = data.choices?.[0]?.message?.content ?? ''

    // Parse JSON — strip any accidental markdown fences
    const cleaned = rawContent
      .replace(/^```(?:json)?\n?/m, '')
      .replace(/\n?```$/m, '')
      .trim()

    let questions: GeneratedQuestion[]
    try {
      questions = JSON.parse(cleaned)
    } catch (parseErr) {
      console.error('[question-generator] JSON parse failed:', rawContent)
      return NextResponse.json(
        { error: 'LLM returned malformed JSON', raw: rawContent.slice(0, 500) },
        { status: 422 }
      )
    }

    // Inject metadata fields
    const enriched = questions.map(q => ({
      ...q,
      domain_name: domain,
      topic,
      set_number: setNumber,
      is_active: false,   // always draft — requires human review before activation
    }))

    return NextResponse.json({
      questions: enriched,
      count: enriched.length,
      model: GENERATE_MODEL,
      note: 'Questions are in DRAFT state (is_active: false). Review in Question Bank before activating.',
    })
  } catch (err) {
    console.error('[question-generator] Error:', err)
    return NextResponse.json({ error: 'Generation failed', detail: String(err) }, { status: 500 })
  }
}
