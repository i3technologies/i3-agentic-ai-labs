/**
 * infra-scan.ts
 * Subagent: scans CI/CD pipelines, ArgoCD GitOps, Docker/OpenShift configs,
 * and cluster namespace topology.
 * Primarily serves the Platform Engineer onboarding role.
 *
 * Real files it will reference:
 *   platform/gitops/argocd/app-of-apps.yaml
 *   platform/gitops/tekton/pipeline-build.yaml
 *   platform/RUNBOOK.md
 *   platform/docs/platform-documentation.md  (namespace map, ROKS details)
 */

import { BaseScan }      from './base-scan.js';
import { SubagentInput } from './types.js';

export class InfraScan extends BaseScan {
  readonly subagentName = 'infra-scan';

  readonly systemPrompt = `
You are the Infrastructure Scanner for i3 Agentic AI Labs onboarding.

Your specialisation is the platform infrastructure layer:
- ROKS 4.15 cluster, Frankfurt (eu-de region), 12 managed namespaces
- ArgoCD app-of-apps.yaml with 6 waves (wave 7 = onboarding-agent to be added)
- Tekton pipeline i3-build-deploy: git-clone → buildah → trivy → rolling-update
- OpenBao KV v2 at path i3/ for secrets (new services → i3/<service>/)
- Keycloak realm i3 at sso.i3technologies.co.ke — 10-hour SSO sessions, JWKS endpoint
- cert-manager ClusterIssuers for TLS
- CRITICAL: solution-01 through solution-08 namespaces MUST NEVER BE MODIFIED
- n8n workflow automation connecting EvalOS → Keycloak → Directus
- Makefile 11-section structure for all operational commands

When producing findings, focus on:
1. Namespace topology and which namespaces are safe to work in
2. ArgoCD wave ordering and how to add a new service (wave 7)
3. Tekton pipeline structure and how to trigger a build
4. Secret management: OpenBao bootstrap procedure from RUNBOOK.md
5. Makefile targets a platform engineer needs on day 1
6. The FORBIDDEN namespaces rule (solution-01..08) — this must be finding #1

Always cite exact file paths from context. Do not invent paths.
`.trim();

  protected buildUserPrompt(input: SubagentInput): string {
    return (
      `SUBAGENT: ${this.subagentName}\n` +
      `ROLE: ${input.role}\n\n` +
      `FOCUS AREAS:\n${input.focusAreas.map(f => `- ${f}`).join('\n')}\n\n` +
      `PLATFORM CONTEXT:\n${input.ragContext}\n\n` +
      `Produce a JSON object with key "findings" (array of 5–7 items).\n` +
      `Each item: title, description, filePaths[], priority (high/medium/low), ` +
      `suggestedDay (1-5), roles[], optional historicalIssueRef.\n` +
      `Output ONLY valid JSON. No markdown fences.\n`
    );
  }
}

export const infraScan = new InfraScan();

export async function runInfraScan(ragContext: string): Promise<ReturnType<InfraScan['run']>> {
  const input: SubagentInput = {
    role:         'platform_engineer',
    contextQuery: 'ArgoCD Tekton ROKS namespaces OpenBao Keycloak Makefile solution namespaces',
    ragContext,
    focusAreas: [
      'FORBIDDEN: solution-01..08 namespaces — never touch',
      'ArgoCD app-of-apps.yaml wave ordering (currently 6 waves)',
      'Tekton pipeline i3-build-deploy: tasks and trigger',
      'OpenBao secret bootstrap procedure (RUNBOOK.md)',
      'Keycloak realm i3 — JWKS endpoint and 10-hour session config',
      'Namespace topology: 12 managed namespaces on ROKS 4.15',
      'cert-manager ClusterIssuers and TLS certificate management',
      'Makefile sections: build, deploy, secrets, test, dr',
    ],
  };
  return infraScan.run(input);
}
