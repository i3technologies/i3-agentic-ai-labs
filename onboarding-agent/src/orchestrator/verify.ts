/**
 * verify.ts
 * Step 3 of the Task Execution Loop: verify that every file path referenced
 * in the subagent findings actually exists in the seed repo.
 *
 * If a path is missing → mark the task as verified: false and prefix title
 * with "Needs verification: [title] (referenced path not found — likely stale doc)"
 *
 * Special demo proof-point:
 *   platform/docs/platform-documentation.md notes RHOAI (i3-ai-lab namespace)
 *   as "available from Month 3". verify.ts checks the live ROKS namespace via
 *   the cluster API. If not found → verified: false is emitted.
 */

import { existsSync }        from 'fs';
import { resolve, join }     from 'path';
import { SubagentScanResult, SubagentFinding } from './subagents/types.js';

const PLATFORM_REPO = resolve(
  process.env.PLATFORM_REPO_PATH ?? '../platform',
);

export interface VerifiedFinding extends SubagentFinding {
  verified:         boolean;
  verificationNote: string;
}

export interface VerifiedScanResult {
  subagentName:  string;
  findings:      VerifiedFinding[];
  verifiedCount: number;
  stalePaths:    string[];
}

// ──────────────────────────────────────────────────────────────────────────────
// File-system verification
// ──────────────────────────────────────────────────────────────────────────────

function fileExists(filePath: string): boolean {
  if (!filePath || filePath.trim() === '') return false;

  // Absolute path — check directly
  if (filePath.startsWith('/')) return existsSync(filePath);

  // Relative to platform repo root
  return existsSync(join(PLATFORM_REPO, filePath));
}

/** Resolve a file path to its canonical form for display */
function canonicalPath(filePath: string): string {
  if (filePath.startsWith('platform/')) return filePath;
  if (filePath.startsWith('/')) return filePath;
  return `platform/${filePath}`;
}

// ──────────────────────────────────────────────────────────────────────────────
// RHOAI namespace check (demo proof-point)
// Tests whether the i3-ai-lab OpenShift namespace exists.
// In the hackathon demo, this call confirms it does NOT exist yet
// (docs say "Month 3") → flags task as verified: false.
// ──────────────────────────────────────────────────────────────────────────────

async function checkRhoaiNamespace(): Promise<boolean> {
  const k8sApiUrl = process.env.KUBE_API_URL;
  const k8sToken  = process.env.KUBE_SA_TOKEN;

  if (!k8sApiUrl || !k8sToken) {
    // Cannot check without cluster credentials — assume not available
    // (conservative: docs explicitly say Month 3)
    return false;
  }

  try {
    const resp = await fetch(
      `${k8sApiUrl}/api/v1/namespaces/i3-ai-lab`,
      {
        headers: { Authorization: `Bearer ${k8sToken}` },
        signal:  AbortSignal.timeout(5_000),
      },
    );
    return resp.status === 200;
  } catch {
    return false;
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Main verification function
// ──────────────────────────────────────────────────────────────────────────────

let _rhoaiLive: boolean | null = null;

async function getRhoaiStatus(): Promise<boolean> {
  if (_rhoaiLive !== null) return _rhoaiLive;
  _rhoaiLive = await checkRhoaiNamespace();
  return _rhoaiLive;
}

/** Apply stale-doc prefix to a task title */
function stalePrefixTitle(title: string): string {
  return `Needs verification: ${title} (referenced path not found — likely stale doc)`;
}

/** Verify all findings in a single subagent scan result */
export async function verifyScanResult(
  scanResult: SubagentScanResult,
): Promise<VerifiedScanResult> {
  const rhoaiLive  = await getRhoaiStatus();
  const stalePaths: string[] = [];

  const findings: VerifiedFinding[] = await Promise.all(
    scanResult.findings.map(async (finding): Promise<VerifiedFinding> => {
      const missingPaths: string[] = [];

      // Check each referenced file path
      for (const fp of finding.filePaths) {
        if (!fileExists(fp)) {
          missingPaths.push(canonicalPath(fp));
        }
      }

      // Special RHOAI check: if finding references i3-ai-lab or RHOAI
      const referencesRhoai =
        finding.description.toLowerCase().includes('rhoai') ||
        finding.description.toLowerCase().includes('i3-ai-lab') ||
        finding.title.toLowerCase().includes('rhoai') ||
        finding.title.toLowerCase().includes('i3-ai-lab') ||
        (finding.historicalIssueRef ?? '').toLowerCase().includes('rhoai');

      const rhoaiFails = referencesRhoai && !rhoaiLive;

      if (missingPaths.length > 0 || rhoaiFails) {
        const notes: string[] = [];
        if (missingPaths.length > 0) {
          notes.push(`missing paths: ${missingPaths.join(', ')}`);
          stalePaths.push(...missingPaths);
        }
        if (rhoaiFails) {
          notes.push(
            'RHOAI/i3-ai-lab namespace not live — ' +
            'platform-documentation.md states "available from Month 3"',
          );
        }

        return {
          ...finding,
          title:            stalePrefixTitle(finding.title),
          verified:         false,
          verificationNote: notes.join('; '),
        };
      }

      return {
        ...finding,
        verified:         true,
        verificationNote: 'all referenced paths confirmed present',
      };
    }),
  );

  return {
    subagentName:  scanResult.subagentName,
    findings,
    verifiedCount: findings.filter(f => f.verified).length,
    stalePaths:    [...new Set(stalePaths)],
  };
}

/** Verify an entire assessment (all subagent results) in parallel */
export async function verifyAll(
  scanResults: SubagentScanResult[],
): Promise<VerifiedScanResult[]> {
  return Promise.all(scanResults.map(verifyScanResult));
}
