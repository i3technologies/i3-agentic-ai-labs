import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * POST /api/admin/generate-variants
 *
 * Given a source question UUID, generates scenario-equivalent variant forms
 * using the on-cluster LLM. Variants preserve the competency being tested but
 * use different surface facts, datasets, or context — defeating memorized answers.
 *
 * Source: §6.4 — "AI-generated equivalent assessment forms. For every published
 * item, an agent generates several scenario-equivalent variants (same competency,
 * different surface facts/names/datasets), which is the single most cost-effective
 * defense against item leakage and answer-sharing."
 *
 * Admin-only endpoint.
 */

const LITELLM_URL    = process.env.LITELLM_URL    ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY    = process.env.LITELLM_KEY    ?? ''
const GENERATE_MODEL = 'qwen-heavy'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const RequestSchema = z.object({
  question_id: z.string().regex(UUID_RE, 'Invalid question UUID'),
  variant_count: z.number().int().min(1).max(5).default(3),
})

interface QuestionRow {
  id: string
  text: string
  type: string
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_name: string
  topic: string
  set_number: number
  difficulty: number | null
}

interface GeneratedVariant {
  text: string
  type: string
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_name: string
  topic: string
  set_number: number
  source_question_id: string
  is_active: boolean
  ai_generated: boolean
}

function buildVariantPrompt(source: QuestionRow, variantCount: number): string {
  return `You are an expert certification exam author specializing in IBM watsonx Orchestrate.

Your task: generate ${variantCount} scenario-equivalent variant(s) of the following question.

CRITICAL RULES:
1. Each variant must test the SAME competency/concept as the source question.
2. Change the surface details: use different product names, company contexts, workflow names, scenario descriptions, or numerical values — but keep the underlying knowledge requirement identical.
3. Wrong answers must be plausible distractors that reflect common misconceptions.
4. Correct answers must remain unambiguously correct.
5. Each variant must have exactly 4 options labelled A, B, C, D.
6. Type "${source.type}" — ${source.type === 'MR' ? '2–3 correct answers' : 'exactly 1 correct answer'}.
7. Do NOT copy any exact sentence from the source question.
8. Return ONLY a JSON array, no markdown, no other text.

SOURCE QUESTION:
${JSON.stringify({
  text: source.text,
  type: source.type,
  options: source.options,
  correct_answers: source.correct_answers,
  explanation: source.explanation,
  topic: source.topic,
}, null, 2)}

Return format (array of ${variantCount}):
[
  {
    "text": "...",
    "type": "${source.type}",
    "options": [
      {"label": "A", "text": "..."},
      {"label": "B", "text": "..."},
      {"label": "C", "text": "..."},
      {"label": "D", "text": "..."}
    ],
    "correct_answers": ["..."],
    "explanation": "..."
  }
]`
}

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const tenantId =
    (session.user as { tenant_id?: string }).tenant_id ||
    '00000000-0000-0000-0000-000000000001'

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const parsed = RequestSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid request', details: parsed.error.flatten() },
      { status: 400 }
    )
  }

  const { question_id, variant_count } = parsed.data

  // Fetch source question
  const client = await pool.connect()
  let source: QuestionRow
  try {
    await setTenantContext(client, tenantId)
    const { rows } = await client.query(
      `SELECT id, text, type, question_type, options, correct_answers,
              explanation, domain_name, topic, set_number, difficulty
       FROM questions
       WHERE id = $1 AND is_active = true`,
      [question_id]
    )
    if (rows.length === 0) {
      return NextResponse.json({ error: 'Question not found or inactive' }, { status: 404 })
    }
    source = rows[0] as QuestionRow
  } finally {
    client.release()
  }

  // Generate variants via LLM
  const prompt = buildVariantPrompt(source, variant_count)

  try {
    const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type':         'application/json',
        'Authorization':        `Bearer ${LITELLM_KEY}`,
        'x-litellm-max-tokens': '4000',
        'x-litellm-metadata':   JSON.stringify({
          tenant_id: tenantId,
          agent_id:  'evalos-variant-generator',
        }),
      },
      body: JSON.stringify({
        model: GENERATE_MODEL,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.85,
        max_tokens: 4000,
        top_p: 0.95,
      }),
      signal: AbortSignal.timeout(120_000),
    })

    if (!resp.ok) {
      const err = await resp.text()
      console.error('[variant-generator] LiteLLM error', resp.status, err)
      return NextResponse.json({ error: 'LLM unavailable', detail: err }, { status: 502 })
    }

    const data = await resp.json()
    const rawContent: string = data.choices?.[0]?.message?.content ?? ''

    // Strip accidental markdown fences
    const cleaned = rawContent
      .replace(/^```(?:json)?\n?/m, '')
      .replace(/\n?```$/m, '')
      .trim()

    let rawVariants: Array<Omit<GeneratedVariant, 'domain_name' | 'topic' | 'set_number' | 'source_question_id' | 'is_active' | 'ai_generated'>>
    try {
      rawVariants = JSON.parse(cleaned)
    } catch {
      console.error('[variant-generator] JSON parse failed:', rawContent)
      return NextResponse.json(
        { error: 'LLM returned malformed JSON', raw: rawContent.slice(0, 500) },
        { status: 422 }
      )
    }

    // Enrich with metadata
    const variants: GeneratedVariant[] = rawVariants.map((v) => ({
      ...v,
      domain_name:        source.domain_name,
      topic:              source.topic,
      set_number:         source.set_number,
      source_question_id: source.id,
      is_active:          false,   // Draft — requires human review
      ai_generated:       true,
    }))

    return NextResponse.json({
      source_question_id: source.id,
      variants,
      variant_count: variants.length,
      model: GENERATE_MODEL,
      note: 'Variants are DRAFT (is_active: false). Review and activate in Question Bank.',
    })
  } catch (err) {
    console.error('[variant-generator] Error:', err)
    return NextResponse.json({ error: 'Variant generation failed', detail: String(err) }, { status: 500 })
  }
}
