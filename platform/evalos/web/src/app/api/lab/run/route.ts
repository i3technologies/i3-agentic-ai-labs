import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { traceLangfuse, estimateTokens } from '@/lib/langfuse'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const LITELLM_URL = process.env.LITELLM_URL  ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY = process.env.LITELLM_KEY  ?? ''
const SANDBOX_URL = process.env.SANDBOX_URL  ?? 'http://sandbox-daemon.i3-evalos.svc.cluster.local:8080'

interface RunRequest {
  code: string
  language: 'javascript' | 'python' | 'sql'
  stdin?: string
  labId?: string
}

interface ReviewRequest {
  code: string
  language: 'javascript' | 'python' | 'sql'
  labContext: string    // what the lab asks the student to do
  runOutput?: string   // stdout from execution (if available)
  runError?: string    // stderr/error from execution
}

// ── POST /api/lab/run — execute code in sandbox ───────────────
export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const url = new URL(req.url)
  const action = url.searchParams.get('action') ?? 'run'

  if (action === 'review') {
    return handleReview(req, session.user.userId || session.user.email || '')
  }

  // Default: run code
  let body: RunRequest
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { code, language, stdin } = body
  if (!code?.trim()) return NextResponse.json({ error: 'code is required' }, { status: 400 })

  // Hard limits: 5s execution, 50 MB memory, no network
  try {
    const resp = await fetch(`${SANDBOX_URL}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        language,
        code,
        stdin: stdin ?? '',
        timeout: 5,
        memory_mb: 50,
      }),
      signal: AbortSignal.timeout(10_000),
    })

    if (!resp.ok) {
      const err = await resp.text()
      return NextResponse.json({ error: 'Sandbox error', detail: err }, { status: 502 })
    }

    const result = await resp.json()
    return NextResponse.json({
      stdout: result.stdout ?? '',
      stderr: result.stderr ?? '',
      exitCode: result.exit_code ?? 0,
      executionMs: result.execution_ms ?? 0,
    })
  } catch (err) {
    return NextResponse.json({ error: 'Execution failed', detail: String(err) }, { status: 502 })
  }
}

async function handleReview(req: Request, userId: string): Promise<NextResponse> {
  let body: ReviewRequest
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const { code, language, labContext, runOutput, runError } = body
  if (!code?.trim()) return NextResponse.json({ error: 'code is required' }, { status: 400 })

  const resultContext = runOutput
    ? `\nExecution output:\n\`\`\`\n${runOutput.slice(0, 500)}\n\`\`\``
    : runError
    ? `\nExecution error:\n\`\`\`\n${runError.slice(0, 500)}\n\`\`\``
    : ''

  const prompt = `You are an expert code reviewer and AI Lab instructor. Review the following student code.

Lab task: ${labContext}

Student's ${language} code:
\`\`\`${language}
${code.slice(0, 3000)}
\`\`\`${resultContext}

Provide a concise code review. Structure as:

## Does it work?
One sentence on whether the code correctly solves the task.

## What's good
1-2 things done well.

## Improvements
Up to 3 specific, actionable improvements (bugs, style, efficiency, edge cases).
For each: show the problematic code and suggest the fix.

## One tip
One broader learning tip relevant to the task (e.g., a JS/Python pattern, IBM API best practice).

Keep total length under 300 words. Be encouraging but precise.`

  const traceId = randomUUID()
  const start = new Date()

  try {
    const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${LITELLM_KEY}`,
      },
      body: JSON.stringify({
        model: 'coder',
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.3,
        max_tokens: 600,
      }),
      signal: AbortSignal.timeout(90_000),
    })

    const end = new Date()

    if (!resp.ok) {
      const err = await resp.text()
      throw new Error(`LiteLLM ${resp.status}: ${err}`)
    }

    const data = await resp.json()
    const review = data.choices?.[0]?.message?.content ?? ''

    traceLangfuse({
      traceId,
      name: 'coding-lab-review',
      userId,
      metadata: { language },
      input: prompt,
      output: review,
      startTime: start.toISOString(),
      endTime: end.toISOString(),
      modelName: 'coder',
      promptTokens: estimateTokens(prompt),
      completionTokens: estimateTokens(review),
      latencyMs: end.getTime() - start.getTime(),
      level: 'DEFAULT',
    })

    return NextResponse.json({ review })
  } catch (err) {
    return NextResponse.json({ error: 'Review failed', detail: String(err) }, { status: 502 })
  }
}
