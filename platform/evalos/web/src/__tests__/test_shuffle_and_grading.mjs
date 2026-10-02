/**
 * test_shuffle_and_grading.mjs
 *
 * Intensive tests for the option-shuffle label-remap logic and the
 * inline grader — the two systems responsible for "No Results / Zero Scores".
 *
 * Run with: node platform/evalos/web/src/__tests__/test_shuffle_and_grading.mjs
 *
 * No external test framework — pure Node.js assertions.
 */

import assert from 'node:assert/strict'

// ── Helpers ──────────────────────────────────────────────────────────────────

const LABELS = ['A', 'B', 'C', 'D', 'E', 'F']

/** Deterministic "shuffle" for testing — reverses the array so A→D, B→C, C→B, D→A */
function deterministicReverse(arr) {
  return [...arr].reverse()
}

/**
 * Production shuffleAndRemapAnswers (copied verbatim from start/route.ts).
 * Uses the injected shuffleFn so tests can control the shuffle outcome.
 */
function shuffleAndRemapAnswers(normalised, correctAnswers, shuffleFn) {
  const labelToText = new Map(normalised.map((o) => [o.label.toUpperCase(), o.text]))
  const shuffled = shuffleFn(normalised)
  const relabelled = shuffled.map((o, i) => ({
    label: LABELS[i] ?? String(i + 1),
    text: o.text,
  }))
  const textToNewLabel = new Map(relabelled.map((o) => [o.text, o.label]))
  const remappedCorrect = correctAnswers.map((origLabel) => {
    const text = labelToText.get(origLabel.toUpperCase())
    if (text === undefined) return origLabel
    return textToNewLabel.get(text) ?? origLabel
  })
  return { options: relabelled, correct_answers: remappedCorrect }
}

/** Inline grader — mirrors gradeInline() in submit/route.ts */
function gradeInline(snapshot, answersRaw, passThreshold) {
  let correctCount = 0
  const total = snapshot.length

  for (const q of snapshot) {
    const selected = answersRaw[q.id] ?? null
    const isMr =
      q.type?.toUpperCase() === 'MR' ||
      ['mr', 'multiple_response', 'multi_select'].includes(q.question_type?.toLowerCase() ?? '')

    let isCorrect = false
    if (isMr) {
      if (Array.isArray(selected) && selected.length > 0) {
        const given = [...selected].map(String).map((s) => s.toUpperCase()).sort()
        const expected = [...q.correct_answers].map((s) => s.toUpperCase()).sort()
        isCorrect = JSON.stringify(given) === JSON.stringify(expected)
      }
    } else {
      if (selected !== null && selected !== undefined) {
        if (typeof selected === 'string') {
          isCorrect = selected.toUpperCase() === (q.correct_answers[0] ?? '').toUpperCase()
        } else if (typeof selected === 'number') {
          isCorrect = selected === parseInt(q.correct_answers[0] ?? '-1', 10)
        }
      }
    }
    if (isCorrect) correctCount++
  }

  const pct = total > 0 ? (correctCount / total) * 100 : 0
  return {
    score: correctCount,
    max_score: total,
    pct_score: Math.round(pct * 10000) / 10000,
    passed: pct >= passThreshold,
  }
}

// ── Tests ────────────────────────────────────────────────────────────────────

let passed = 0
let failed = 0

function test(name, fn) {
  try {
    fn()
    console.log(`  ✓ ${name}`)
    passed++
  } catch (err) {
    console.error(`  ✗ ${name}`)
    console.error(`    ${err.message}`)
    failed++
  }
}

// ── Suite 1: shuffleAndRemapAnswers ──────────────────────────────────────────

console.log('\n── Suite 1: shuffleAndRemapAnswers ──')

test('identity shuffle preserves labels and correct_answers unchanged', () => {
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
    { label: 'C', text: 'Gamma' },
    { label: 'D', text: 'Delta' },
  ]
  const result = shuffleAndRemapAnswers(opts, ['B'], (a) => [...a])
  assert.deepEqual(result.correct_answers, ['B'])
  assert.equal(result.options[0].label, 'A')
  assert.equal(result.options[1].label, 'B')
})

test('reverse shuffle remaps correct_answers: B (2nd of 4) → C (now 3rd after reverse)', () => {
  // Original: A=Alpha, B=Beta, C=Gamma, D=Delta
  // After reverse: A=Delta, B=Gamma, C=Beta, D=Alpha
  // Correct answer was originally 'B' (Beta). After remap, Beta is at position 'C'.
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
    { label: 'C', text: 'Gamma' },
    { label: 'D', text: 'Delta' },
  ]
  const result = shuffleAndRemapAnswers(opts, ['B'], deterministicReverse)
  // After reverse: [Delta, Gamma, Beta, Alpha] → relabelled A/B/C/D
  assert.deepEqual(result.correct_answers, ['C'], `Expected ['C'], got ${JSON.stringify(result.correct_answers)}`)
  assert.equal(result.options[2].text, 'Beta', 'Beta should be at position C (index 2)')
  assert.equal(result.options[2].label, 'C')
})

test('reverse shuffle remaps MR correct_answers [A, C] correctly', () => {
  // Original: A=Alpha, B=Beta, C=Gamma, D=Delta
  // After reverse: A=Delta, B=Gamma, C=Beta, D=Alpha
  // Correct answers: A (Alpha) → D, C (Gamma) → B
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
    { label: 'C', text: 'Gamma' },
    { label: 'D', text: 'Delta' },
  ]
  const result = shuffleAndRemapAnswers(opts, ['A', 'C'], deterministicReverse)
  const sorted = [...result.correct_answers].sort()
  assert.deepEqual(sorted, ['B', 'D'], `Expected ['B','D'], got ${JSON.stringify(sorted)}`)
})

test('handles unknown label in correct_answers gracefully (passthrough)', () => {
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
  ]
  const result = shuffleAndRemapAnswers(opts, ['Z'], (a) => [...a])
  // 'Z' is not in the options — should pass through unchanged
  assert.deepEqual(result.correct_answers, ['Z'])
})

test('case-insensitive: lowercase correct_answer "b" is remapped correctly', () => {
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
    { label: 'C', text: 'Gamma' },
    { label: 'D', text: 'Delta' },
  ]
  // lowercase 'b' in correct_answers (as stored in DB sometimes)
  const result = shuffleAndRemapAnswers(opts, ['b'], deterministicReverse)
  assert.deepEqual(result.correct_answers, ['C'], `Expected ['C'], got ${JSON.stringify(result.correct_answers)}`)
})

test('options relabelled sequentially after shuffle (no label gaps)', () => {
  const opts = [
    { label: 'A', text: 'One' },
    { label: 'B', text: 'Two' },
    { label: 'C', text: 'Three' },
    { label: 'D', text: 'Four' },
  ]
  const result = shuffleAndRemapAnswers(opts, ['A'], deterministicReverse)
  const labels = result.options.map((o) => o.label)
  assert.deepEqual(labels, ['A', 'B', 'C', 'D'], `Expected A/B/C/D labels, got ${labels.join(',')}`)
})

test('student selects post-shuffle label and scores correctly', () => {
  // Options originally: A=Alpha, B=Beta(correct), C=Gamma, D=Delta
  // After reverse: A=Delta, B=Gamma, C=Beta, D=Alpha
  // correct_answers remapped to ['C']
  // Student clicks 'C' (which is the new label for Beta)
  const opts = [
    { label: 'A', text: 'Alpha' },
    { label: 'B', text: 'Beta' },
    { label: 'C', text: 'Gamma' },
    { label: 'D', text: 'Delta' },
  ]
  const { options: shuffledOpts, correct_answers: remapped } =
    shuffleAndRemapAnswers(opts, ['B'], deterministicReverse)

  const questionId = 'q1'
  const snapshot = [{
    id: questionId,
    type: 'SC',
    question_type: 'mcq',
    correct_answers: remapped,
    domain_number: 1,
    domain_name: 'Test Domain',
    options: shuffledOpts,
  }]

  // Student submits the correct post-shuffle label 'C'
  const answers = { [questionId]: 'C' }
  const result = gradeInline(snapshot, answers, 90)
  assert.equal(result.score, 1, `Expected score=1, got ${result.score}`)
  assert.equal(result.pct_score, 100)
  assert.equal(result.passed, true)
})

test('PRE-FIX BUG REPRODUCTION: old code without remap causes 0 score', () => {
  // Simulate the bug: store original correct_answers WITHOUT remapping
  // Then grade with the answer the student actually gave (post-shuffle label)
  const questionId = 'q1'
  const snapshot = [{
    id: questionId,
    type: 'SC',
    question_type: 'mcq',
    // BUG: stores original label 'B', not the post-shuffle label 'C'
    correct_answers: ['B'],
    domain_number: 1,
    domain_name: 'Test Domain',
  }]

  // Student correctly selected Beta (now at label 'C' after shuffle)
  const answers = { [questionId]: 'C' }
  const result = gradeInline(snapshot, answers, 90)
  // Under the bug: 'C' !== 'B' → scores 0
  assert.equal(result.score, 0, 'BUG: should score 0 (pre-fix behaviour)')
  assert.equal(result.passed, false)
})

// ── Suite 2: gradeInline ─────────────────────────────────────────────────────

console.log('\n── Suite 2: gradeInline ──')

test('all SC questions answered correctly → 100%', () => {
  const snapshot = [
    { id: 'q1', type: 'SC', question_type: 'mcq', correct_answers: ['B'], domain_number: 1, domain_name: 'D1' },
    { id: 'q2', type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: 1, domain_name: 'D1' },
    { id: 'q3', type: 'SC', question_type: 'mcq', correct_answers: ['C'], domain_number: 1, domain_name: 'D1' },
  ]
  const answers = { q1: 'B', q2: 'A', q3: 'C' }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 3)
  assert.equal(r.pct_score, 100)
  assert.equal(r.passed, true)
})

test('all SC questions answered wrong → 0%', () => {
  const snapshot = [
    { id: 'q1', type: 'SC', question_type: 'mcq', correct_answers: ['B'], domain_number: 1, domain_name: 'D1' },
    { id: 'q2', type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: 1, domain_name: 'D1' },
  ]
  const answers = { q1: 'A', q2: 'C' }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 0)
  assert.equal(r.pct_score, 0)
  assert.equal(r.passed, false)
})

test('MR question: all labels correct → 1 point', () => {
  const snapshot = [{
    id: 'q1', type: 'MR', question_type: 'multi_select', correct_answers: ['A', 'C'], domain_number: 2, domain_name: 'D2',
  }]
  const answers = { q1: ['A', 'C'] }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 1)
})

test('MR question: partial selection → 0 points (all-or-nothing)', () => {
  const snapshot = [{
    id: 'q1', type: 'MR', question_type: 'multi_select', correct_answers: ['A', 'B', 'D'], domain_number: 2, domain_name: 'D2',
  }]
  const answers = { q1: ['A', 'B'] }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 0)
})

test('MR question: order-independent matching → 1 point', () => {
  const snapshot = [{
    id: 'q1', type: 'MR', question_type: 'multi_select', correct_answers: ['B', 'A', 'D'], domain_number: 2, domain_name: 'D2',
  }]
  const answers = { q1: ['D', 'A', 'B'] }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 1)
})

test('pass threshold boundary: exactly at threshold → passed', () => {
  // 3 correct out of 5 = 60% — threshold 60
  const snapshot = Array.from({ length: 5 }, (_, i) => ({
    id: `q${i}`, type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: 1, domain_name: 'D1',
  }))
  const answers = { q0: 'A', q1: 'A', q2: 'A', q3: 'B', q4: 'B' }
  const r = gradeInline(snapshot, answers, 60)
  assert.equal(r.score, 3)
  assert.equal(r.passed, true)
})

test('pass threshold boundary: 1 below threshold → failed (Set 7: 90%)', () => {
  // 53 correct out of 60 = 88.33% < 90
  const snapshot = Array.from({ length: 60 }, (_, i) => ({
    id: `q${i}`, type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: (i % 7) + 1, domain_name: `D${(i % 7) + 1}`,
  }))
  const answers = Object.fromEntries(
    Array.from({ length: 60 }, (_, i) => [`q${i}`, i < 53 ? 'A' : 'B'])
  )
  const r = gradeInline(snapshot, answers, 90)
  assert.equal(r.score, 53)
  assert.ok(r.pct_score < 90, `Expected pct_score < 90, got ${r.pct_score}`)
  assert.equal(r.passed, false)
})

test('pass threshold: 54 correct out of 60 = 90% → passed', () => {
  const snapshot = Array.from({ length: 60 }, (_, i) => ({
    id: `q${i}`, type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: (i % 7) + 1, domain_name: `D${(i % 7) + 1}`,
  }))
  const answers = Object.fromEntries(
    Array.from({ length: 60 }, (_, i) => [`q${i}`, i < 54 ? 'A' : 'B'])
  )
  const r = gradeInline(snapshot, answers, 90)
  assert.equal(r.score, 54)
  assert.equal(r.pct_score, 90)
  assert.equal(r.passed, true)
})

test('MC type treated same as SC (single answer)', () => {
  const snapshot = [{
    id: 'q1', type: 'MC', question_type: 'mcq', correct_answers: ['C'], domain_number: 1, domain_name: 'D1',
  }]
  const answers = { q1: 'C' }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 1)
})

test('case-insensitive: lowercase answer "a" matches uppercase correct_answers ["A"]', () => {
  const snapshot = [{
    id: 'q1', type: 'SC', question_type: 'mcq', correct_answers: ['A'], domain_number: 1, domain_name: 'D1',
  }]
  const answers = { q1: 'a' }
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 1)
})

test('unanswered question scores 0 points', () => {
  const snapshot = [{
    id: 'q1', type: 'SC', question_type: 'mcq', correct_answers: ['B'], domain_number: 1, domain_name: 'D1',
  }]
  const answers = {}
  const r = gradeInline(snapshot, answers, 68)
  assert.equal(r.score, 0)
})

test('empty snapshot returns score=0, passed=false', () => {
  const r = gradeInline([], {}, 68)
  assert.equal(r.score, 0)
  assert.equal(r.max_score, 0)
  assert.equal(r.passed, false)
})

// ── Suite 3: End-to-end shuffle→submit→grade flow ────────────────────────────

console.log('\n── Suite 3: End-to-end shuffle → grade ──')

test('full flow: 60-question Set 7 exam with reverse shuffle scores correctly', () => {
  // Build 60 questions with known correct answers
  const rawQuestions = Array.from({ length: 60 }, (_, i) => ({
    id: `q${i}`,
    type: 'SC',
    question_type: 'mcq',
    options: [
      { label: 'A', text: `Option A for Q${i}` },
      { label: 'B', text: `Option B for Q${i}` },
      { label: 'C', text: `Option C for Q${i}` },
      { label: 'D', text: `Option D for Q${i}` },
    ],
    correct_answers: ['B'],   // original correct answer is always B
    domain_number: (i % 7) + 1,
    domain_name: `Domain ${(i % 7) + 1}`,
  }))

  // Apply shuffleAndRemapAnswers (deterministic reverse: A→D, B→C, C→B, D→A)
  // B becomes C after reverse shuffle
  const snapshot = rawQuestions.map((q) => {
    const { options: shuffledOpts, correct_answers: remapped } =
      shuffleAndRemapAnswers(q.options, q.correct_answers, deterministicReverse)
    return { ...q, options: shuffledOpts, correct_answers: remapped }
  })

  // Verify all correct_answers were remapped from B → C
  for (const q of snapshot) {
    assert.deepEqual(q.correct_answers, ['C'], `Q${q.id}: expected remapped to ['C'], got ${JSON.stringify(q.correct_answers)}`)
  }

  // Student correctly selects C on every question (the post-shuffle correct label)
  const answers = Object.fromEntries(snapshot.map((q) => [q.id, 'C']))
  const result = gradeInline(snapshot, answers, 90)

  assert.equal(result.score, 60, `Expected 60, got ${result.score}`)
  assert.equal(result.max_score, 60)
  assert.equal(result.pct_score, 100)
  assert.equal(result.passed, true)
})

test('full flow: student selects wrong labels on shuffled exam → scores 0', () => {
  const rawQuestions = Array.from({ length: 5 }, (_, i) => ({
    id: `q${i}`,
    type: 'SC',
    question_type: 'mcq',
    options: [
      { label: 'A', text: `Opt A${i}` },
      { label: 'B', text: `Opt B${i}` },  // correct
      { label: 'C', text: `Opt C${i}` },
      { label: 'D', text: `Opt D${i}` },
    ],
    correct_answers: ['B'],
    domain_number: 1,
    domain_name: 'D1',
  }))

  const snapshot = rawQuestions.map((q) => {
    const { options, correct_answers } = shuffleAndRemapAnswers(q.options, q.correct_answers, deterministicReverse)
    return { ...q, options, correct_answers }
  })

  // Student guesses wrong label 'B' (which is now Gamma, not Beta, after shuffle)
  const answers = Object.fromEntries(snapshot.map((q) => [q.id, 'B']))
  const result = gradeInline(snapshot, answers, 68)
  assert.equal(result.score, 0)
  assert.equal(result.passed, false)
})

test('MR questions in Set 7 with shuffle are graded correctly', () => {
  // MR question: A=Opt1, B=Opt2(correct), C=Opt3(correct), D=Opt4
  // correct_answers = ['B','C']
  const opts = [
    { label: 'A', text: 'Opt1' },
    { label: 'B', text: 'Opt2' },
    { label: 'C', text: 'Opt3' },
    { label: 'D', text: 'Opt4' },
  ]
  // After reverse: A=Opt4, B=Opt3, C=Opt2, D=Opt1
  // B(Opt2)→C, C(Opt3)→B → new correct_answers = ['B','C'] (sorted)
  const { options: shuffledOpts, correct_answers: remapped } =
    shuffleAndRemapAnswers(opts, ['B', 'C'], deterministicReverse)

  const sorted = [...remapped].sort()
  assert.deepEqual(sorted, ['B', 'C'], `Expected ['B','C'], got ${JSON.stringify(sorted)}`)

  const snapshot = [{
    id: 'qMR', type: 'MR', question_type: 'multi_select',
    correct_answers: remapped, options: shuffledOpts,
    domain_number: 1, domain_name: 'D1',
  }]

  const answers = { qMR: remapped }  // student selects the remapped correct labels
  const result = gradeInline(snapshot, answers, 90)
  assert.equal(result.score, 1)
})

// ── Summary ──────────────────────────────────────────────────────────────────

console.log(`\n── Results: ${passed} passed, ${failed} failed ──\n`)

if (failed > 0) {
  process.exit(1)
}
