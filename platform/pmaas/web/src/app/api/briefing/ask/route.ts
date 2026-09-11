import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export const dynamic = 'force-dynamic'

const AGENT_URL  = process.env.AGENT_URL  ?? 'http://campaign-agent.i3-pmaas.svc.cluster.local:8080'
const LITELLM_URL = process.env.LITELLM_URL ?? ''
const LITELLM_KEY = process.env.LITELLM_KEY ?? ''

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { question } = await req.json()
  if (!question?.trim()) return NextResponse.json({ error: 'Question required' }, { status: 400 })

  // Try Campaign Agent RAG endpoint first
  try {
    const agentResp = await fetch(`${AGENT_URL}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': LITELLM_KEY,
      },
      body: JSON.stringify({ question }),
      signal: AbortSignal.timeout(60_000),
    })
    if (!agentResp.ok) throw new Error(`Agent ${agentResp.status}`)
    const data = await agentResp.json()
    return NextResponse.json({ answer: data.answer ?? data.response ?? '', source: 'rag' })
  } catch {
    // Fall back to direct LLM
    if (!LITELLM_URL || !LITELLM_KEY) {
      return NextResponse.json({ error: 'No AI backend configured' }, { status: 503 })
    }

    const prompt = `You are Dawa, a Kenyan political campaign AI assistant. 
Answer this campaign question based on your knowledge of the Kenyan political landscape, 
electoral law, and campaign strategy best practices.

Question: ${question}

Give a concise, practical answer in 2–4 sentences. Focus on actionable insights for the campaign team.`

    const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${LITELLM_KEY}`,
      },
      body: JSON.stringify({
        model:       'qwen-fast',
        messages:    [{ role: 'user', content: prompt }],
        temperature: 0.5,
        max_tokens:  400,
      }),
      signal: AbortSignal.timeout(60_000),
    })
    if (!resp.ok) {
      const err = await resp.text()
      return NextResponse.json({ error: `LiteLLM ${resp.status}: ${err}` }, { status: 502 })
    }
    const data = await resp.json()
    return NextResponse.json({
      answer: data.choices?.[0]?.message?.content ?? '',
      source: 'litellm',
    })
  }
}
