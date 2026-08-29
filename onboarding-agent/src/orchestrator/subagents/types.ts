/**
 * types.ts — shared types for all subagents and the planner.
 */

export type OnboardingRole =
  | 'bootcamp_student'
  | 'platform_engineer'
  | 'ai_ml_engineer'
  | 'backend_engineer'
  | 'security_engineer';

export interface SubagentFinding {
  /** Human-readable heading for this finding */
  title:       string;
  /** Short description — fed into the planner as task rationale */
  description: string;
  /** File path(s) referenced — used by verify.ts to confirm existence */
  filePaths:   string[];
  /** Severity or importance: high | medium | low */
  priority:    'high' | 'medium' | 'low';
  /** Suggested day (1–5) for the new hire to tackle this */
  suggestedDay: 1 | 2 | 3 | 4 | 5;
  /** Which roles this finding is relevant to */
  roles:       OnboardingRole[];
  /** Optional: reference to a historical issue/bug for learning */
  historicalIssueRef?: string;
}

export interface SubagentScanResult {
  subagentName: string;
  role:         OnboardingRole;
  findings:     SubagentFinding[];
  /** Raw context passages used (for audit trail) */
  contextUsed:  string[];
  durationMs:   number;
}

/** Input to every subagent run() call */
export interface SubagentInput {
  role:         OnboardingRole;
  contextQuery: string;
  /** Pre-retrieved RAG context (passed by the orchestrator) */
  ragContext:   string;
  /** Specific focus areas the subagent should prioritise */
  focusAreas:   string[];
}
