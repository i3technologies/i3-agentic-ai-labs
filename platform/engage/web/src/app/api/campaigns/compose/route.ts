import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export const dynamic = 'force-dynamic'

const LITELLM_URL = process.env.LITELLM_URL ?? ''
const LITELLM_KEY = process.env.LITELLM_KEY ?? ''

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { prompt, subject } = await req.json()
  if (!prompt?.trim()) return NextResponse.json({ error: 'prompt required' }, { status: 400 })

  if (!LITELLM_URL || !LITELLM_KEY) {
    return NextResponse.json({ error: 'AI service not configured' }, { status: 503 })
  }

  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${LITELLM_KEY}` },
    body: JSON.stringify({
      model: 'qwen-fast',
      messages: [{
        role: 'system',
        content: 'You are an expert email copywriter. Write clean, professional HTML emails for marketing campaigns. Return ONLY the HTML body content, no markdown, no explanation.',
      }, {
        role: 'user',
        content: `Write an HTML email body for this campaign:
Subject: ${subject ?? '(not provided)'}
Instructions: ${prompt}

Use professional formatting with inline styles. Include a clear call-to-action button. Keep it concise.`,
      }],
      temperature: 0.7,
      max_tokens: 800,
    }),
    signal: AbortSignal.timeout(30_000),
  })

  if (!resp.ok) {
    return NextResponse.json({ error: 'AI service error' }, { status: 502 })
  }

  const data = await resp.json()
  const html = data.choices?.[0]?.message?.content ?? ''
  return NextResponse.json({ html })
}
