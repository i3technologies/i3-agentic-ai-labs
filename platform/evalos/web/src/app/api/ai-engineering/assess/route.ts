import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'
export const maxDuration = 115

/**
 * POST /api/ai-engineering/assess
 *
 * AI Engineering Assessment Mode — the signature differentiating Phase 3 product.
 *
 * Three tiers (§6.4 of ARCH-EVALOS-2026-V2):
 *   closed_book    — no AI tools; measures pure unaided knowledge
 *   ai_allowed     — AI tools permitted; measures human+AI collaboration competency
 *   ai_engineering — AI tools REQUIRED; measures prompting, verification, hallucination
 *                    detection, debugging, architecture, testing, security
 *
 * Evaluates:
 *   - Prompt quality (specificity, context, constraints)
 *   - Output verification discipline (did they check the AI's answer?)
 *   - Hallucination catching (did they identify and correct AI errors?)
 *   - AI-assisted design quality
 *
 * Source: §6.4 — "AI-native 'engineering with AI' assessment tier"
 * HC-3: agent proposes score; stored for human review if confidence < 70%.
 * HC-4: tenant_id propagated.
 */

const LITELLM_URL = process.env.LITELLM_URL ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY = process.env.LITELLM_KEY ?? ''

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const AssessSchema = z.object({
  attempt_id:        z.string().regex(UUID_RE),
  mode:              z.enum(['closed_book','ai_allowed','ai_engineering']),
  problem_statement: z.string().min(10).max(3000),
  submission:        z.string().min(1).max(20_000),
  // For ai_allowed / ai_engineering: log of prompts sent and responses received
  prompt_log: z.array(z.object({
    user_prompt:  z.string(),
    ai_response:  z.string(),
    verified:     z.boolean().optional(),  // did candidate verify the output?
    corrections:  z.string().optional(),   // corrections they made
  })).optional(),
  rubric: z.string().min(10).max(2000),
})

type AssessInput = z.infer<typeof AssessSchema>

async function evaluateAIEngineering(input: AssessInput, tenantId: string): Promise<{
  score: number
  prompt_quality: number
  hallucinations_caught: number
  output_verified: boolean
  justification: string
  recommendations: string[]
}> {
  const modeDesc: Record<string, string> = {
    closed_book:    'CLOSED BOOK — AI tools forbidden. Evaluate pure unaided knowledge and skill.',
    ai_allowed:     'AI ALLOWED — AI tools were permitted. Evaluate the human+AI collaboration quality.',
    ai_engineering: 'AI ENGINEERING — AI tools required. Evaluate prompting discipline, output verification, hallucination detection, and AI-native engineering competency.',
  }

  const promptLogStr = input.prompt_log?.length
    ? `\nAI Interaction Log (${input.prompt_log.length} exchanges):\n` +
      input.prompt_log.slice(0, 5).map((p, i) =>
        `Exchange ${i+1}:\n  Prompt: ${p.user_prompt.slice(0, 200)}\n  Response (excerpt): ${p.ai_response.slice(0, 200)}\n  Verified: ${p.verified ?? 'unknown'}`
      ).join('\n')
    : ''

  const systemPrompt = `You are an AI Engineering Assessment specialist.
Assessment mode: ${modeDesc[input.mode]}
Evaluate the candidate's final submission AND their AI collaboration discipline.
Return ONLY valid JSON.`

  const userContent = `Problem: ${input.problem_statement}
Rubric: ${input.rubric}
Final Submission:
${input.submission.slice(0, 5000)}
${promptLogStr}

Score the candidate on:
1. Technical correctness (0-100)
2. Prompt quality — specificity, context, constraints (0-100, N/A for closed_book → 50)
3. Hallucination catching — did they identify and correct AI errors? (0-100)
4. Output verification discipline — did they test/validate AI output? (0-100)

Return JSON:
{
  "overall_score": 0-100,
  "prompt_quality": 0-100,
  "hallucinations_caught_count": 0,
  "output_verified": true|false,
  "justification": "<3-4 sentences>",
  "recommendations": ["<concrete improvement>", ...]
}`

  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type':       'application/json',
      'Authorization':      `Bearer ${LITELLM_KEY}`,
      'x-litellm-metadata': JSON.stringify({ tenant_id: tenantId, agent_id: 'evalos-ai-collab' }),
    },
    body: JSON.stringify({
      model: 'qwen-heavy',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user',   content: userContent },
      ],
      temperature: 0.2,
      max_tokens: 1000,
    }),
    signal: AbortSignal.timeout(60_000),
  })

  if (!resp.ok) throw new Error(`LiteLLM ${resp.status}`)
  const data = await resp.json()
  const raw = data.choices?.[0]?.message?.content ?? ''
  const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim()

  let parsed: {
    overall_score: number; prompt_quality: number
    hallucinations_caught_count: number; output_verified: boolean
    justification: string; recommendations: string[]
  }
  try {
    parsed = JSON.parse(cleaned)
  } catch {
    throw new Error(`Malformed JSON from LLM: ${raw.slice(0, 300)}`)
  }

  return {
    score:                 Math.max(0, Math.min(100, Math.round(parsed.overall_score ?? 0))),
    prompt_quality:        Math.max(0, Math.min(100, Math.round(parsed.prompt_quality ?? 50))),
    hallucinations_caught: Math.max(0, parsed.hallucinations_caught_count ?? 0),
    output_verified:       Boolean(parsed.output_verified),
    justification:         parsed.justification ?? '',
    recommendations:       parsed.recommendations ?? [],
  }
}

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json().catch(() => null)
  const parsed = AssessSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request', details: parsed.error.flatten() }, { status: 400 })
  }

  const input = parsed.data
  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const result = await evaluateAIEngineering(input, tenantId)

  // Persist session record
  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    await client.query(
      `INSERT INTO ai_engineering_sessions
         (tenant_id, attempt_id, candidate_id, mode, prompts_sent,
          prompt_quality, hallucinations_caught, output_verified, ai_collab_score, final_score)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
      [
        tenantId, input.attempt_id, userId, input.mode,
        input.prompt_log?.length ?? 0,
        result.prompt_quality,
        result.hallucinations_caught,
        result.output_verified,
        result.prompt_quality,
        result.score,
      ]
    )
  } catch (err) {
    console.error('[ai-engineering] DB persist failed:', err)
  } finally {
    client.release()
  }

  return NextResponse.json({
    ok:                    true,
    mode:                  input.mode,
    score:                 result.score,
    prompt_quality:        result.prompt_quality,
    hallucinations_caught: result.hallucinations_caught,
    output_verified:       result.output_verified,
    justification:         result.justification,
    recommendations:       result.recommendations,
    // HC-3: L1 — result is a proposal
    human_review_advisory: result.score < 40 || !result.output_verified
      ? 'Low score or unverified output — flagged for human review before credential issuance.'
      : null,
  })
}
