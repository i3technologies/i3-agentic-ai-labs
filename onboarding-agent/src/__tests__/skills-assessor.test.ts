/**
 * skills-assessor.test.ts
 * ────────────────────────
 * P1-GATE-09 sensor: npm test → PASSED (skills-assessor isolation test)
 *
 * Isolation contract under test:
 *   assessRole() orchestrates parallel subagent scans for a given OnboardingRole.
 *   Each subagent is isolated — one scanner's failure MUST NOT prevent others
 *   from returning results (Promise.allSettled contract).
 *
 * All external I/O is mocked:
 *   - retrieveAsContext  → empty string (no ChromaDB)
 *   - Each scanner.run() → deterministic SubagentScanResult fixture
 */

import { assessRole, AssessmentResult } from '../orchestrator/skills-assessor';
import { SubagentScanResult, OnboardingRole } from '../orchestrator/subagents/types';

// ── Mock all external dependencies ───────────────────────────────────────────

jest.mock('../context-store/retriever', () => ({
  retrieveAsContext: jest.fn().mockResolvedValue('mocked-rag-context'),
}));

// Build a deterministic scan-result factory used for all scanner mocks
const makeScanResult = (subagentName: string, role: OnboardingRole): SubagentScanResult => ({
  subagentName,
  role,
  findings: [
    {
      title:        `${subagentName} finding`,
      description:  `Mock finding from ${subagentName}`,
      filePaths:    ['platform/mock/file.py'],
      priority:     'medium',
      suggestedDay: 1,
      roles:        [role],
    },
  ],
  contextUsed: ['mocked-rag-context'],
  durationMs:  42,
});

jest.mock('../orchestrator/subagents/evalos-scan',   () => ({
  evalosScan: { run: jest.fn(({ role }: { role: OnboardingRole }) => Promise.resolve(makeScanResult('evalos-scan', role))) },
}));
jest.mock('../orchestrator/subagents/ailab-scan',    () => ({
  ailabScan:  { run: jest.fn(({ role }: { role: OnboardingRole }) => Promise.resolve(makeScanResult('ailab-scan', role))) },
}));
jest.mock('../orchestrator/subagents/infra-scan',    () => ({
  infraScan:  { run: jest.fn(({ role }: { role: OnboardingRole }) => Promise.resolve(makeScanResult('infra-scan', role))) },
}));
jest.mock('../orchestrator/subagents/backend-scan',  () => ({
  backendScan: { run: jest.fn(({ role }: { role: OnboardingRole }) => Promise.resolve(makeScanResult('backend-scan', role))) },
}));
jest.mock('../orchestrator/subagents/model-scan',    () => ({
  modelScan:  { run: jest.fn(({ role }: { role: OnboardingRole }) => Promise.resolve(makeScanResult('model-scan', role))) },
}));


// ── Test suite ────────────────────────────────────────────────────────────────

describe('assessRole — skills-assessor isolation', () => {

  beforeEach(() => jest.clearAllMocks());

  // ── Role routing ─────────────────────────────────────────────────────────

  it('returns AssessmentResult with correct role for bootcamp_student', async () => {
    const result: AssessmentResult = await assessRole('bootcamp_student');
    expect(result.role).toBe('bootcamp_student');
    expect(result.scanResults.length).toBeGreaterThan(0);
  });

  it('returns AssessmentResult with correct role for platform_engineer', async () => {
    const result = await assessRole('platform_engineer');
    expect(result.role).toBe('platform_engineer');
  });

  it('returns AssessmentResult for all five defined roles', async () => {
    const roles: OnboardingRole[] = [
      'bootcamp_student',
      'platform_engineer',
      'ai_ml_engineer',
      'backend_engineer',
      'security_engineer',
    ];
    for (const role of roles) {
      const result = await assessRole(role);
      expect(result.role).toBe(role);
    }
  });

  // ── Subagent isolation ────────────────────────────────────────────────────

  it('totalFindings equals sum of all scanner finding counts', async () => {
    const result = await assessRole('platform_engineer');
    const expected = result.scanResults.reduce((sum, r) => sum + r.findings.length, 0);
    expect(result.totalFindings).toBe(expected);
  });

  it('scanResults contain one result per scanner in the plan', async () => {
    const result = await assessRole('platform_engineer');
    // platform_engineer uses 3 scanners: infra-scan, ailab-scan, backend-scan
    expect(result.scanResults).toHaveLength(3);
  });

  it('scanResults subagentName matches scanner identity for ai_ml_engineer', async () => {
    const result = await assessRole('ai_ml_engineer');
    const names = result.scanResults.map((r) => r.subagentName).sort();
    // ai_ml_engineer uses: ailab-scan, model-scan, backend-scan
    expect(names).toEqual(['ailab-scan', 'backend-scan', 'model-scan'].sort());
  });

  it('one failing scanner does not prevent others from returning (isolation)', async () => {
    // Override infra-scan to reject for this test only
    const { infraScan } = jest.requireMock('../orchestrator/subagents/infra-scan') as { infraScan: { run: jest.Mock } };
    infraScan.run.mockRejectedValueOnce(new Error('infra-scan network timeout'));

    // FINDING-OA-2: assessRole now uses Promise.allSettled — a single scanner
    // failure drops that scanner's result but does NOT reject the whole call.
    // platform_engineer plan includes 3 scanners (infra-scan, ailab-scan, backend-scan).
    // With infra-scan rejected, we should get 2 results (not 3, not a rejection).
    const result = await assessRole('platform_engineer');
    expect(result.scanResults).toHaveLength(2);
    // Verify the surviving scanners are the non-failing ones
    const names = result.scanResults.map((r) => r.subagentName).sort();
    expect(names).toEqual(['ailab-scan', 'backend-scan'].sort());
  });

  // ── RAG context threading ─────────────────────────────────────────────────

  it('passes retrieveAsContext result into each scanner run() call', async () => {
    const { retrieveAsContext } = jest.requireMock('../context-store/retriever') as { retrieveAsContext: jest.Mock };
    retrieveAsContext.mockResolvedValue('custom-rag-context');

    const { ailabScan } = jest.requireMock('../orchestrator/subagents/ailab-scan') as { ailabScan: { run: jest.Mock } };

    await assessRole('bootcamp_student');

    // Every call to ailabScan.run must have received ragContext = 'custom-rag-context'
    const calls = ailabScan.run.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    calls.forEach(([input]: [{ ragContext: string }]) => {
      expect(input.ragContext).toBe('custom-rag-context');
    });
  });

  // ── Timing ───────────────────────────────────────────────────────────────

  it('durationMs is a non-negative number', async () => {
    const result = await assessRole('security_engineer');
    expect(result.durationMs).toBeGreaterThanOrEqual(0);
  });
});
