/**
 * graph.ts
 * Generates a Mermaid Gantt chart representation of the 5-day ramp-up plan.
 * Returned as a string; suitable for embedding in Markdown, GitHub wikis,
 * or the HTML one-pager artifact.
 *
 * Also exports a plain-text dependency graph of key platform services
 * for inclusion in the plan briefing.
 */

import { RampUpPlan, RampUpTask } from '../orchestrator/planner';

const PRIORITY_CRIT: Record<string, string> = {
  high:   'crit',
  medium: 'active',
  low:    '',
};

/** Sanitise a Mermaid task label — remove commas and colons */
function mermaidLabel(s: string): string {
  return s
    .replace(/[,:"]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 60);
}

/** Truncate title for Gantt — keep under 40 chars for readability */
function shortTitle(title: string): string {
  const clean = title.replace(/^Needs verification:\s*/i, '⚠ ');
  return clean.length > 45 ? clean.slice(0, 42) + '…' : clean;
}

/**
 * Render a Mermaid Gantt chart from the plan.
 * Each task occupies a time slot proportional to estimatedHours.
 * Days are used as section breaks.
 */
export function renderGantt(plan: RampUpPlan): string {
  const lines: string[] = [];
  const role            = plan.role.replace(/_/g, ' ');

  lines.push('```mermaid');
  lines.push(`gantt`);
  lines.push(`    title ${role} — First Week Ramp-Up`);
  lines.push(`    dateFormat  HH`);
  lines.push(`    axisFormat  Day %d`);
  lines.push('');

  // Group by day
  const byDay = new Map<number, RampUpTask[]>();
  for (const task of plan.tasks) {
    const arr = byDay.get(task.day) ?? [];
    arr.push(task);
    byDay.set(task.day, arr);
  }

  // Fake hour offset: each day starts at hour (day-1)*8
  for (let day = 1; day <= 5; day++) {
    const tasks   = byDay.get(day) ?? [];
    if (tasks.length === 0) continue;

    lines.push(`    section Day ${day}`);

    for (const task of tasks) {
      const label    = mermaidLabel(shortTitle(task.title));
      const modifier = PRIORITY_CRIT[task.priority] ?? '';
      const hours    = Math.max(1, Math.round(task.estimatedHours));
      const tag      = modifier ? `${modifier}, ` : '';
      lines.push(`    ${label} :${tag}${hours}h`);
    }
    lines.push('');
  }

  lines.push('```');
  return lines.join('\n');
}

/**
 * Render a static Mermaid flowchart of the i3 platform service topology.
 * Used in the plan preamble so the new hire immediately sees how services connect.
 */
export function renderServiceGraph(): string {
  return `\`\`\`mermaid
graph TD
    KC[Keycloak<br/>sso.i3technologies.co.ke] -->|JWT| AA[Admissions Agent<br/>i3-admissions]
    KC -->|JWT| OA[Onboarding Agent<br/>i3-onboarding]
    KC -->|JWT| EV[EvalOS API<br/>i3-evalos]

    AA -->|embed + query| CB[ChromaDB<br/>i3-admissions]
    OA -->|embed + query| CB

    AA -->|LLM calls| LT[LiteLLM Gateway<br/>litellm.i3technologies.co.ke]
    OA -->|LLM calls| LT
    LT -->|Tier 3| GN[granite-nano<br/>Ollama]
    LT -->|Tier 2| MN[mistral-nemo<br/>Ollama]
    LT -->|Tier 1| GH[granite-heavy<br/>watsonx.ai]

    AA -->|MCP tools| MCP[MCP Connectors<br/>i3-admissions]
    OA -->|MCP tools| MCP
    MCP -->|sync tasks| CRM[Directus CMS<br/>i3-cms]
    MCP -->|enrol| N8N[n8n Automations<br/>i3-automation]
    N8N -->|provision| KC

    EV -->|schema| PG[(PostgreSQL<br/>i3-evalos-db)]
    OA -->|secret injection| OB[OpenBao KV v2<br/>i3-secrets]

    AG[ArgoCD<br/>i3-gitops] -->|wave 1-6 + wave 7| OA
    TK[Tekton Pipeline<br/>i3-build-deploy] -->|buildah + trivy| AG
\`\`\``;
}
