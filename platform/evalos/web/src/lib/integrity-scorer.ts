/**
 * integrity-scorer.ts
 * Computes the four composable integrity scores defined in §5 Layer 1 of
 * the EvalOS Technical Implementation Guide (ARCH-EVALOS-2026-V2).
 *
 * Scores:
 *   identity_score      — confidence the person is who they claim (0–100)
 *   behavior_score      — inverse deviation from expected interaction patterns (0–100)
 *   integrity_confidence— aggregate copy/paste/AI-gen signal (0–100)
 *   trust_score         — weighted composite; < 60 → requires_review = true
 *
 * Design principles:
 *   - Explainable: each penalty is tagged with its signal source
 *   - Human-in-the-loop: never auto-fail; only sets requires_review flag
 *   - Proportional: single events are minor; patterns compound
 */

export interface IntegrityInputs {
  focusLostCount:    number
  fullscreenExits:   number
  clipboardEvents:   number
  tabSwitchEvents:   unknown[]      // raw JSONB array from DB
  keystrokeEntropy?: number | null  // 0–1 or null if not measured
  deviceChanged:     boolean        // fingerprint mismatch on resume
  proctorFlags:      unknown[]      // existing proctor_flags JSONB
}

export interface IntegrityScores {
  identityScore:       number
  behaviorScore:       number
  integrityConfidence: number
  trustScore:          number
  requiresReview:      boolean
  explanation:         string[]
}

/**
 * Clamp a value to [0, 100].
 */
function clamp(v: number): number {
  return Math.min(100, Math.max(0, v))
}

/**
 * Compute the four integrity scores from raw telemetry captured during an exam.
 *
 * Thresholds are intentionally conservative for a Phase 1 implementation.
 * They should be calibrated once real cohort data is available (meta-evaluation).
 */
export function computeIntegrityScores(inputs: IntegrityInputs): IntegrityScores {
  const explanation: string[] = []

  // ── Identity Score (100 = full confidence) ───────────────────────────────
  // Phase 1 has no face-match yet; identity is inferred from session signals.
  let identityScore = 100

  if (inputs.deviceChanged) {
    identityScore -= 35
    explanation.push('Device fingerprint changed mid-session (possible proxy test-taker)')
  }

  // ── Behavior Score (100 = normal interaction) ────────────────────────────
  let behaviorScore = 100

  if (inputs.focusLostCount > 0) {
    const penalty = Math.min(25, inputs.focusLostCount * 5)
    behaviorScore -= penalty
    explanation.push(`Focus lost ${inputs.focusLostCount}× (-${penalty} pts)`)
  }

  if (inputs.fullscreenExits > 0) {
    const penalty = Math.min(20, inputs.fullscreenExits * 8)
    behaviorScore -= penalty
    explanation.push(`Fullscreen exited ${inputs.fullscreenExits}× (-${penalty} pts)`)
  }

  if (inputs.tabSwitchEvents.length > 0) {
    const penalty = Math.min(30, inputs.tabSwitchEvents.length * 6)
    behaviorScore -= penalty
    explanation.push(`Tab switched ${inputs.tabSwitchEvents.length}× (-${penalty} pts)`)
  }

  // Keystroke entropy anomaly: very low entropy suggests copy-pasted or AI-generated input
  if (inputs.keystrokeEntropy != null) {
    if (inputs.keystrokeEntropy < 0.15) {
      behaviorScore -= 15
      explanation.push(`Very low keystroke entropy (${inputs.keystrokeEntropy.toFixed(3)}) — possible AI-generated input`)
    } else if (inputs.keystrokeEntropy < 0.30) {
      behaviorScore -= 8
      explanation.push(`Low keystroke entropy (${inputs.keystrokeEntropy.toFixed(3)}) — possible paste-heavy behavior`)
    }
  }

  // ── Integrity Confidence (100 = no copy/paste/AI indicators) ─────────────
  let integrityConfidence = 100

  if (inputs.clipboardEvents > 0) {
    const penalty = Math.min(40, inputs.clipboardEvents * 10)
    integrityConfidence -= penalty
    explanation.push(`Clipboard used ${inputs.clipboardEvents}× (-${penalty} pts)`)
  }

  // Each existing proctor_flag that isn't a grading artefact is a signal
  const significantFlags = (inputs.proctorFlags as Array<Record<string, unknown>>).filter(
    (f) => f && typeof f === 'object' && !('grading_error' in f) && !('domain_breakdown' in f)
  )
  if (significantFlags.length > 0) {
    const penalty = Math.min(30, significantFlags.length * 10)
    integrityConfidence -= penalty
    explanation.push(`${significantFlags.length} existing proctor flag(s) on record (-${penalty} pts)`)
  }

  // ── Trust Score: weighted composite ──────────────────────────────────────
  // Weights: identity 30%, behavior 40%, integrity 30%
  const trustScore =
    clamp(identityScore)       * 0.30 +
    clamp(behaviorScore)       * 0.40 +
    clamp(integrityConfidence) * 0.30

  const requiresReview = trustScore < 60

  if (requiresReview) {
    explanation.push(`Trust score ${trustScore.toFixed(1)} < 60 — queued for human review`)
  }

  return {
    identityScore:       clamp(identityScore),
    behaviorScore:       clamp(behaviorScore),
    integrityConfidence: clamp(integrityConfidence),
    trustScore:          clamp(trustScore),
    requiresReview,
    explanation,
  }
}
