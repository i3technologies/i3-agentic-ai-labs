import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'
import { runEvaluationPipeline, type AgentInput } from '@/lib/agent-pipeline'

export const dynamic = 'force-dynamic'
export const maxDuration = 115

/**
 * POST /api/agent/evaluate
 *
 * Runs the full multi-agent evaluation pipeline (Code Examiner → Architect →
 * Adversarial QA → Critic → Aggregator) against a code/prose submission.
 *
 * Source: §6.3 — The Evaluation Pipeline, ARCH-EVALOS-2026-V2
 * HC-3: agents propose; result is stored as a report — never auto-applied to grade.
 * HC-4: tenant_id propagated throughout.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const EvalSchema = z.object({
  attempt_id:        z.string().regex(UUID_RE),
  submission:        z.string().min(1).max(50_000),
  language:          z.string().optional(),
  problem_statement: z.string().min(1).max(5_000),
  rubric:            z.string().min(1).max(2_000),
})

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => null)
  const parsed = EvalSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid request', details: parsed.error.flatten() },
      { status: 400 }
    )
  }

  const { attempt_id, submission, language, problem_statement, rubric } = parsed.data
  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id || '00000000-0000-0000-0000-000000000002'

  // Verify the attempt belongs to this user (or is admin)
  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)
    const { rows } = await client.query(
      `SELECT id FROM quiz_attempts WHERE id = $1 AND (student_id = $2 OR $3)`,
      [attempt_id, userId, session.user.isAdmin]
    )
    if (rows.length === 0) {
      return NextResponse.json({ error: 'Attempt not found' }, { status: 404 })
    }
  } finally {
    client.release()
  }

  const agentInput: AgentInput = {
    submission,
    language,
    problem_statement,
    rubric,
    tenantId,
    userId,
    attemptId: attempt_id,
  }

  const start = Date.now()
  const result = await runEvaluationPipeline(agentInput)
  const totalMs = Date.now() - start

  // Persist agent reports to DB (best-effort, non-blocking)
  ;(async () => {
    const dbClient = await pool.connect()
    try {
      await setTenantContext(dbClient, tenantId)
      for (const report of result.reports) {
        await dbClient.query(
          `INSERT INTO evaluation_agent_reports
             (tenant_id, attempt_id, agent_type, score_awarded, max_score,
              findings_summary, detailed_metrics, model_used, latency_ms)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
          [
            tenantId, attempt_id, report.agentType,
            report.scoreAwarded, report.maxScore,
            report.findingsSummary, JSON.stringify(report.detailedMetrics),
            report.modelUsed, report.latencyMs,
          ]
        )
      }

      // If pipeline requires human review, flag the attempt
      if (result.requiresHumanReview) {
        await dbClient.query(
          `UPDATE quiz_attempts SET requires_review = true WHERE id = $1`,
          [attempt_id]
        )
      }
    } catch (err) {
      console.error('[agent-evaluate] DB persist failed:', err)
    } finally {
      dbClient.release()
    }
  })()

  return NextResponse.json({
    ok: true,
    attempt_id,
    final_score:           result.finalScore,
    skill_vector:          result.skillVector,
    justification:         result.justification,
    requires_human_review: result.requiresHumanReview,
    pipeline_latency_ms:   totalMs,
    reports: result.reports.map(r => ({
      agent:           r.agentType,
      score:           r.scoreAwarded,
      summary:         r.findingsSummary,
      latency_ms:      r.latencyMs,
    })),
  })
}
