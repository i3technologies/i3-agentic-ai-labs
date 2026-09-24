/**
 * Consent-service circuit-breaker for Next.js server-side callers.
 *
 * Pattern: half-open exponential back-off with fail-closed default.
 *
 * States
 *   CLOSED    — normal operation; failures counted.
 *   OPEN      — fast-fail for OPEN_TIMEOUT_MS after FAILURE_THRESHOLD consecutive failures.
 *   HALF_OPEN — single probe allowed; success → CLOSED, failure → OPEN (back-off doubles).
 *
 * HC compliance: default-deny on OPEN state as required by STEP-P2-02 / DPA 2019 §25.
 * State is module-level (per-worker process). In multi-replica deployments each
 * replica maintains its own state; the fail-closed guarantee is preserved regardless.
 */

const FAILURE_THRESHOLD  = parseInt(process.env.CONSENT_CB_FAILURE_THRESHOLD  ?? '5',  10)
const OPEN_TIMEOUT_MS    = parseInt(process.env.CONSENT_CB_OPEN_TIMEOUT_MS     ?? '30000', 10)
const MAX_OPEN_TIMEOUT_MS = parseInt(process.env.CONSENT_CB_MAX_OPEN_TIMEOUT_MS ?? '300000', 10)
const REQUEST_TIMEOUT_MS = parseInt(process.env.CONSENT_CB_REQUEST_TIMEOUT_MS  ?? '5000', 10)

type State = 'CLOSED' | 'OPEN' | 'HALF_OPEN'

let _state: State           = 'CLOSED'
let _failures               = 0
let _openedAt               = 0
let _currentTimeoutMs       = OPEN_TIMEOUT_MS

function _trip(): void {
  _state = 'OPEN'
  _openedAt = Date.now()
  console.warn(
    `[consent-breaker] OPEN (failures=${_failures}, retry_in=${_currentTimeoutMs / 1000}s)`
  )
}

function _reset(): void {
  _state = 'CLOSED'
  _failures = 0
  _currentTimeoutMs = OPEN_TIMEOUT_MS
  console.info('[consent-breaker] CLOSED (recovered)')
}

function _isProbeAllowed(): boolean {
  return (Date.now() - _openedAt) >= _currentTimeoutMs
}

async function _callConsentService(
  url: string,
  subjectIdHash: string,
  channel: string,
  purpose: string,
  tenantId: string,
): Promise<boolean> {
  const endpoint = new URL(`${url}/consent/${encodeURIComponent(subjectIdHash)}`)
  endpoint.searchParams.set('channel', channel)
  endpoint.searchParams.set('purpose', purpose)
  endpoint.searchParams.set('tenant_id', tenantId)

  const resp = await fetch(endpoint.toString(), {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  })
  if (!resp.ok) return false
  const data = await resp.json() as { allowed?: boolean }
  return data.allowed === true
}

function _onFailure(err: unknown): void {
  _failures++
  console.warn(
    `[consent-breaker] failure ${_failures}/${FAILURE_THRESHOLD}:`,
    err instanceof Error ? err.message : String(err),
  )
  if (_state === 'HALF_OPEN') {
    _currentTimeoutMs = Math.min(_currentTimeoutMs * 2, MAX_OPEN_TIMEOUT_MS)
    _trip()
  } else if (_failures >= FAILURE_THRESHOLD) {
    _trip()
  }
}

function _onSuccess(): void {
  if (_state === 'HALF_OPEN' || _state === 'CLOSED') {
    _reset()
  }
}

/**
 * Primary API.  Returns true only when the consent-service confirms allowed=true.
 * Fail-closed: returns false when the circuit is OPEN, on timeout, or service error.
 */
export async function consentAllowed(
  consentServiceUrl: string,
  subjectIdHash: string,
  channel: string,
  purpose: string,
  tenantId: string,
): Promise<boolean> {
  // OPEN state — check if we can probe
  if (_state === 'OPEN') {
    if (!_isProbeAllowed()) {
      console.debug('[consent-breaker] fast-fail (OPEN)')
      return false
    }
    _state = 'HALF_OPEN'
    console.info('[consent-breaker] HALF_OPEN (probing)')
  }

  try {
    const result = await _callConsentService(
      consentServiceUrl, subjectIdHash, channel, purpose, tenantId
    )
    _onSuccess()
    return result
  } catch (err) {
    _onFailure(err)
    return false
  }
}

/** Returns the current breaker state for health endpoints. */
export function breakerState(): State {
  return _state
}
