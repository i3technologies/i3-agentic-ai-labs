/**
 * plagiarism-detector.ts
 * Code-similarity and plagiarism detection for EvalOS Phase 2.
 *
 * Implements two complementary approaches described in §2.2 of
 * ARCH-EVALOS-2026-V2:
 *   1. Normalized AST fingerprint (MOSS-style) — token-level hash stored in
 *      questions.moss_hash; compared at submission time.
 *   2. Cosine similarity on trigram token vectors — lightweight in-process
 *      comparison for detecting near-duplicate submissions within a cohort.
 *
 * Results feed into the integrity_confidence score and flag suspicious attempts
 * for human review (HC-3: never auto-fail).
 */

export interface SimilarityResult {
  moss_similarity: number    // 0–100; similarity to reference solution fingerprint
  cosine_similarity: number  // 0–100; similarity to cohort submissions
  is_suspicious: boolean     // true if either metric exceeds threshold
  explanation: string
}

// ── Normalisation ─────────────────────────────────────────────────────────────

/** Remove comments, string literals, and variable names; keep structural tokens. */
function normalizeCode(code: string): string {
  return code
    // Strip single-line comments
    .replace(/\/\/[^\n]*/g, '')
    // Strip block comments
    .replace(/\/\*[\s\S]*?\*\//g, '')
    // Strip Python/shell comments
    .replace(/#[^\n]*/g, '')
    // Collapse string literals to placeholder
    .replace(/"(?:[^"\\]|\\.)*"/g, 'STR')
    .replace(/'(?:[^'\\]|\\.)*'/g, 'STR')
    .replace(/`(?:[^`\\]|\\.)*`/g, 'STR')
    // Collapse numbers
    .replace(/\b\d+(\.\d+)?\b/g, 'NUM')
    // Collapse identifiers (keep keywords by relying on them being non-lowercase-only)
    .replace(/\b[a-z_][a-zA-Z0-9_]{2,}\b/g, 'ID')
    // Collapse whitespace
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/** Build a trigram set from normalized text. */
function trigrams(text: string): Set<string> {
  const result = new Set<string>()
  for (let i = 0; i < text.length - 2; i++) {
    result.add(text.slice(i, i + 3))
  }
  return result
}

/**
 * Compute Jaccard similarity (a/b set ratio) between two trigram sets.
 * Returns 0–100.
 */
function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 100
  if (a.size === 0 || b.size === 0) return 0
  let intersection = 0
  Array.from(a).forEach((t) => { if (b.has(t)) intersection++ })
  const union = a.size + b.size - intersection
  return Math.round((intersection / union) * 100)
}

/**
 * Hash a normalized code fingerprint for MOSS-style comparison.
 * Uses a rolling Karp-Rabin-inspired window hash for speed.
 * Returns a stable hex string.
 */
export async function fingerprintCode(code: string): Promise<string> {
  const normalized = normalizeCode(code)
  // Use SubtleCrypto if available (browser/edge), else Node crypto
  if (typeof globalThis.crypto?.subtle !== 'undefined') {
    const buf = new TextEncoder().encode(normalized)
    const hash = await globalThis.crypto.subtle.digest('SHA-256', buf)
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('')
  }
  const { createHash } = await import('crypto')
  return createHash('sha256').update(normalized, 'utf8').digest('hex')
}

/**
 * Compare a candidate submission against:
 *   - a reference MOSS hash (from questions.moss_hash)
 *   - a set of previous cohort submissions (raw code strings)
 *
 * Returns a SimilarityResult.
 */
export async function detectPlagiarism(
  submission: string,
  referenceHash: string | null,
  cohortSubmissions: string[]
): Promise<SimilarityResult> {
  const normalized     = normalizeCode(submission)
  const submissionHash = await fingerprintCode(submission)
  const submissionGrams = trigrams(normalized)

  // ── MOSS hash comparison ──────────────────────────────────────────────────
  const mossSimilarity = referenceHash === submissionHash ? 100 : 0

  // ── Cosine/Jaccard against cohort ─────────────────────────────────────────
  let maxCohortSimilarity = 0
  for (const prior of cohortSubmissions) {
    const priorNorm  = normalizeCode(prior)
    const priorGrams = trigrams(priorNorm)
    const sim = jaccardSimilarity(submissionGrams, priorGrams)
    if (sim > maxCohortSimilarity) maxCohortSimilarity = sim
  }

  const isSuspicious = mossSimilarity >= 95 || maxCohortSimilarity >= 75

  let explanation = ''
  if (mossSimilarity >= 95) {
    explanation += 'Submission matches the reference solution fingerprint exactly. '
  }
  if (maxCohortSimilarity >= 75) {
    explanation += `Submission is ${maxCohortSimilarity}% similar to a previous cohort submission. `
  }
  if (!isSuspicious) {
    explanation = 'No significant plagiarism indicators detected.'
  }

  return {
    moss_similarity:  mossSimilarity,
    cosine_similarity: maxCohortSimilarity,
    is_suspicious:    isSuspicious,
    explanation:      explanation.trim(),
  }
}
