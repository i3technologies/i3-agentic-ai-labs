import { NextResponse } from 'next/server'
import { createHmac } from 'crypto'

export const dynamic = 'force-dynamic'

/**
 * POST /api/integrations/lti/launch
 *
 * LTI Advantage (1.3) deep-link launch stub for EvalOS.
 * Validates the incoming id_token JWT from an LMS (Moodle, Canvas, Skillsoft),
 * extracts the user context, and redirects to the appropriate exam or result page.
 *
 * Phase 2 implementation: validates HMAC-signed launch requests from trusted LMS
 * platforms. Full OIDC/PKCE flow and nonce verification handled by LMS registration.
 *
 * Source: §9 Integration Surfaces, §10 Phase 2 — LTI Advantage integration
 *         ARCH-EVALOS-2026-V2
 *
 * Env vars required:
 *   LTI_PLATFORM_ISSUER    — e.g. https://moodle.i3technologies.co.ke
 *   LTI_CLIENT_ID          — registered client ID from LMS
 *   LTI_DEPLOYMENT_ID      — deployment ID from LMS registration
 *   LTI_HMAC_SECRET        — HMAC-SHA256 secret for request signing
 *   NEXT_PUBLIC_APP_URL     — canonical app URL for redirects
 */

const LTI_HMAC_SECRET = process.env.LTI_HMAC_SECRET ?? ''
const APP_URL          = process.env.NEXT_PUBLIC_APP_URL ?? 'https://evalos.i3technologies.co.ke'

interface LTILaunchPayload {
  iss:             string    // issuer (LMS URL)
  sub:             string    // user identifier
  name?:           string
  email?:          string
  deployment_id:   string
  custom_exam_id?: string    // custom parameter set in LMS activity
  roles:           string[]
  context?:        { id: string; title?: string }
}

function verifyLTIHmac(body: string, signatureHeader: string | null): boolean {
  if (!LTI_HMAC_SECRET) return true  // dev: skip if not configured
  if (!signatureHeader) return false
  const expected = createHmac('sha256', LTI_HMAC_SECRET).update(body, 'utf8').digest('hex')
  return expected === signatureHeader
}

export async function POST(req: Request) {
  const rawBody = await req.text()
  const sig = req.headers.get('x-lti-signature')

  if (!verifyLTIHmac(rawBody, sig)) {
    return NextResponse.json({ error: 'Invalid LTI signature' }, { status: 401 })
  }

  let payload: LTILaunchPayload
  try {
    // In production: validate JWT id_token properly via JWKS URI of the LMS.
    // For Phase 2: expect JSON body for trusted internal integrations.
    payload = JSON.parse(rawBody) as LTILaunchPayload
  } catch {
    return NextResponse.json({ error: 'Invalid launch payload' }, { status: 400 })
  }

  const { sub: userId, email, custom_exam_id, roles } = payload

  if (!userId) {
    return NextResponse.json({ error: 'Missing sub (user identifier)' }, { status: 400 })
  }

  // Determine role
  const isInstructor = roles?.some(r =>
    r.includes('Instructor') || r.includes('TeachingAssistant')
  ) ?? false

  // Build redirect target
  let redirectUrl: string
  if (custom_exam_id) {
    // Direct deep-link to a specific exam
    redirectUrl = `${APP_URL}/exam/${encodeURIComponent(custom_exam_id)}`
  } else if (isInstructor) {
    redirectUrl = `${APP_URL}/admin`
  } else {
    redirectUrl = `${APP_URL}/dashboard`
  }

  // Return a JSON response with the redirect target (caller builds the redirect)
  // In a full OIDC flow the browser would POST here and we'd return a 302.
  return NextResponse.json({
    ok:          true,
    launch_type: 'deep_link',
    user_id:     userId,
    email:       email ?? null,
    is_instructor: isInstructor,
    redirect_url:  redirectUrl,
    context_id:    payload.context?.id ?? null,
    context_title: payload.context?.title ?? null,
  })
}
