/**
 * Lightweight Langfuse REST ingestion — no SDK dependency.
 * Fire-and-forget; never throws into calling code.
 */

const LANGFUSE_HOST       = process.env.LANGFUSE_HOST       ?? 'http://langfuse.i3-ott.svc.cluster.local:3000'
const LANGFUSE_PUBLIC_KEY = process.env.LANGFUSE_PUBLIC_KEY ?? ''
const LANGFUSE_SECRET_KEY = process.env.LANGFUSE_SECRET_KEY ?? ''

export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4)
}

export interface LangfuseTraceOptions {
  traceId:           string
  name:              string
  userId?:           string
  metadata?:         Record<string, unknown>
  input:             string
  output:            string
  startTime:         string
  endTime:           string
  modelName:         string
  promptTokens?:     number
  completionTokens?: number
  latencyMs:         number
  level?:            'DEFAULT' | 'DEBUG' | 'WARNING' | 'ERROR'
}

export function traceLangfuse(opts: LangfuseTraceOptions): void {
  if (!LANGFUSE_PUBLIC_KEY || !LANGFUSE_SECRET_KEY) return

  const auth = Buffer.from(`${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}`).toString('base64')

  const body = JSON.stringify({
    batch: [
      {
        id:        opts.traceId,
        type:      'trace-create',
        timestamp: opts.startTime,
        body: {
          id:        opts.traceId,
          name:      opts.name,
          userId:    opts.userId,
          metadata:  opts.metadata,
          input:     opts.input,
          output:    opts.output,
        },
      },
      {
        id:        `${opts.traceId}-gen`,
        type:      'generation-create',
        timestamp: opts.startTime,
        body: {
          traceId:           opts.traceId,
          name:              opts.name,
          startTime:         opts.startTime,
          endTime:           opts.endTime,
          model:             opts.modelName,
          level:             opts.level ?? 'DEFAULT',
          input:             opts.input,
          output:            opts.output,
          usage: {
            promptTokens:     opts.promptTokens,
            completionTokens: opts.completionTokens,
            totalTokens:      (opts.promptTokens ?? 0) + (opts.completionTokens ?? 0),
          },
          metadata: { latencyMs: opts.latencyMs },
        },
      },
    ],
  })

  fetch(`${LANGFUSE_HOST}/api/public/ingestion`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Basic ${auth}`,
    },
    body,
  }).catch(() => { /* fire-and-forget */ })
}
