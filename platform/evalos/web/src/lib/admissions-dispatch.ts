/**
 * admissions-dispatch.ts
 * Server-side helper: dispatches ASSESSMENT_COMPLETED events to the
 * i3 Admissions service after a successful exam grade.
 *
 * Source: §9 Integration Surfaces — Example Admissions Callback Payload
 *         (EvalOS Technical Implementation Guide ARCH-EVALOS-2026-V2)
 *
 * Uses ADMISSIONS_WEBHOOK_URL + ADMISSIONS_WEBHOOK_SECRET env vars.
 * Idempotency: caller should persist webhook_dispatched_at in DB after success.
 */

import { createHmac } from 'crypto'
import pool from './db'

const ADMISSIONS_URL    = process.env.ADMISSIONS_WEBHOOK_URL    ?? ''
const ADMISSIONS_SECRET = process.env.ADMISSIONS_WEBHOOK_SECRET ?? ''
const DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000002'

export interface SkillVector {
  [skill: string]: number
}

export interface DomainBreakdown {
  domain: string
  score: number
  max: number
  pct: number
}

export interface AssessmentCompletedPayload {
  applicant_id: string
  session_id: string        // quiz_attempts.id (attempt UUID)
  tenant_id?: string
  results: {
    total_score: number
    performance_band: string
    recommendation: string
    skill_vector: SkillVector
    summary: string
  }
  artifacts?: {
    report_url?: string
    code_snapshot_url?: string
  }
}

/** Sign the payload body with HMAC-SHA256 for the receiving service. */
function signPayload(body: string): string {
  if (!ADMISSIONS_SECRET) return ''
  return 'sha256=' + createHmac('sha256', ADMISSIONS_SECRET).update(body, 'utf8').digest('hex')
}

/** Map a percentage score to the 5-tier performance band. */
export function scoreToBand(pctScore: number): string {
  if (pctScore >= 95) return 'EXCEPTIONAL'
  if (pctScore >= 80) return 'PRODUCTION_READY'
  if (pctScore >= 65) return 'EMERGING'
  if (pctScore >= 50) return 'DEVELOPING'
  return 'NOT_READY'
}

/** Map performance band to a recommendation verdict for admissions. */
export function bandToRecommendation(band: string): string {
  switch (band) {
    case 'EXCEPTIONAL':       return 'FAST_TRACK_ADMIT'
    case 'PRODUCTION_READY':  return 'STANDARD_ADMIT'
    case 'EMERGING':          return 'CONDITIONAL_ADMIT'
    case 'DEVELOPING':        return 'DEFER_WITH_STUDY_PLAN'
    default:                  return 'NOT_READY'
  }
}

/**
 * Dispatch an ASSESSMENT_COMPLETED event to the admissions service.
 * Non-throwing: logs errors instead of propagating them (best-effort side-effect).
 *
 * @param payload   The structured result payload.
 * @param attemptId The quiz_attempts.id, used to update webhook_dispatched_at.
 * @param tenantId  Tenant UUID for RLS and log tagging.
 */
export async function dispatchAssessmentCompleted(
  payload: AssessmentCompletedPayload,
  attemptId: string,
  tenantId: string = DEFAULT_TENANT_ID
): Promise<void> {
  const fullPayload = {
    event: 'ASSESSMENT_COMPLETED' as const,
    ...payload,
  }

  const body = JSON.stringify(fullPayload)
  const signature = signPayload(body)

  // Log outbound event regardless of delivery outcome
  const client = await pool.connect()
  let logId: string | undefined
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const { rows } = await client.query(
      `INSERT INTO admissions_webhook_log
         (tenant_id, direction, event_type, payload, applicant_id, attempt_id)
       VALUES ($1, 'outbound', 'ASSESSMENT_COMPLETED', $2, $3, $4)
       RETURNING id`,
      [tenantId, JSON.stringify(fullPayload), payload.applicant_id, attemptId]
    )
    logId = rows[0]?.id
  } catch (dbErr) {
    console.error('[admissions-dispatch] webhook log insert failed:', dbErr)
  } finally {
    client.release()
  }

  // Fire-and-forget if no URL configured
  if (!ADMISSIONS_URL) {
    console.info('[admissions-dispatch] ADMISSIONS_WEBHOOK_URL not set — skipping HTTP dispatch')
    return
  }

  try {
    const res = await fetch(ADMISSIONS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(signature ? { 'X-Hub-Signature-256': signature } : {}),
      },
      body,
      signal: AbortSignal.timeout(15_000),
    })

    // Update log row with HTTP status
    if (logId) {
      const logClient = await pool.connect()
      try {
        await logClient.query('SET LOCAL app.tenant_id = $1', [tenantId])
        await logClient.query(
          `UPDATE admissions_webhook_log
           SET status_code = $1, error_message = $2
           WHERE id = $3`,
          [res.status, res.ok ? null : `HTTP ${res.status}`, logId]
        )
      } finally {
        logClient.release()
      }
    }

    if (!res.ok) {
      console.error(`[admissions-dispatch] delivery failed: HTTP ${res.status}`)
    }
  } catch (httpErr) {
    console.error('[admissions-dispatch] network error:', httpErr)
    if (logId) {
      const logClient = await pool.connect()
      try {
        await logClient.query('SET LOCAL app.tenant_id = $1', [tenantId])
        await logClient.query(
          `UPDATE admissions_webhook_log SET error_message = $1 WHERE id = $2`,
          [String(httpErr), logId]
        )
      } finally {
        logClient.release()
      }
    }
  }
}
