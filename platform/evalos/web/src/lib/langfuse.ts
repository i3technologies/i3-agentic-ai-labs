/**
 * Lightweight Langfuse trace helper — fire-and-forget, never throws.
 * Uses the Langfuse REST Ingestion API directly (no SDK dependency needed).
 * https://langfuse.com/docs/integrations/api
 */

const LANGFUSE_HOST = process.env.LANGFUSE_HOST ?? 'http://langfuse.i3-ott.svc.cluster.local:3000'
const LANGFUSE_PUBLIC_KEY = process.env.LANGFUSE_PUBLIC_KEY ?? ''
const LANGFUSE_SECRET_KEY = process.env.LANGFUSE_SECRET_KEY ?? ''

function basicAuth(pub: string, sec: string) {
  return 'Basic ' + Buffer.from(`${pub}:${sec}`).toString('base64')
}

export interface LangfuseTrace {
  traceId: string
  name: string
  userId?: string
  metadata?: Record<string, unknown>
  input?: unknown
  output?: unknown
  startTime: string
  endTime: string
  modelName?: string
  promptTokens?: number
  completionTokens?: number
  latencyMs?: number
  level?: 'DEBUG' | 'DEFAULT' | 'WARNING' | 'ERROR'
}

/**
 * Send a single generation trace to Langfuse.
 * Fire-and-forget — errors are caught and logged, never rethrown.
 */
export async function traceLangfuse(trace: LangfuseTrace): Promise<void> {
  if (!LANGFUSE_PUBLIC_KEY || !LANGFUSE_SECRET_KEY) return // skip if not configured

  const body = {
    batch: [
      {
        id: trace.traceId + '-trace',
        type: 'trace-create',
        timestamp: trace.startTime,
        body: {
          id: trace.traceId,
          name: trace.name,
          userId: trace.userId,
          metadata: trace.metadata,
          input: trace.input,
          output: trace.output,
          startTime: trace.startTime,
          endTime: trace.endTime,
        },
      },
      {
        id: trace.traceId + '-gen',
        type: 'generation-create',
        timestamp: trace.startTime,
        body: {
          id: trace.traceId + '-gen',
          traceId: trace.traceId,
          name: trace.name,
          model: trace.modelName,
          startTime: trace.startTime,
          endTime: trace.endTime,
          input: trace.input,
          output: trace.output,
          usage: {
            promptTokens: trace.promptTokens,
            completionTokens: trace.completionTokens,
            totalTokens: (trace.promptTokens ?? 0) + (trace.completionTokens ?? 0),
          },
          metadata: trace.metadata,
          level: trace.level ?? 'DEFAULT',
          latency: trace.latencyMs,
        },
      },
    ],
  }

  try {
    await fetch(`${LANGFUSE_HOST}/api/public/ingestion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: basicAuth(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY),
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(5_000),
    })
  } catch {
    // intentionally swallowed — tracing must never fail the main request
  }
}

/**
 * Rough token estimator (4 chars ≈ 1 token for English text).
 */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4)
}
