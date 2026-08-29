/**
 * skills-assessor.ts
 * Maps the incoming role to the correct set of subagents, fires them in
 * parallel, and collects their SubagentScanResult[].
 *
 * Role → subagent mapping (from architecture decisions):
 *   bootcamp_student   → evalos-scan, ailab-scan, curriculum-scan*
 *   platform_engineer  → infra-scan,  gitops-scan*, security-scan*
 *   ai_ml_engineer     → backend-scan, model-scan,  ailab-scan
 *   backend_engineer   → backend-scan, evalos-scan (schema), infra-scan
 *   security_engineer  → infra-scan, backend-scan, ailab-scan
 *
 * *curriculum-scan, gitops-scan, security-scan are aliases to existing scanners
 *  (infra covers gitops/security; evalos covers curriculum context).
 */

import { retrieveAsContext }    from '../context-store/retriever.js';
import { evalosScan }           from './subagents/evalos-scan.js';
import { ailabScan }            from './subagents/ailab-scan.js';
import { infraScan }            from './subagents/infra-scan.js';
import { backendScan }          from './subagents/backend-scan.js';
import { modelScan }            from './subagents/model-scan.js';
import { SubagentScanResult, OnboardingRole, SubagentInput } from './subagents/types.js';

interface ScanPlan {
  subagentName: string;
  scanner:      { run(input: SubagentInput): Promise<SubagentScanResult> };
  query:        string;
  roleTag:      string;
  focusAreas:   string[];
}

const SCAN_PLANS: Record<OnboardingRole, ScanPlan[]> = {
  bootcamp_student: [
    {
      subagentName: 'evalos-scan',
      scanner:      evalosScan,
      query:        'EvalOS schema exam quiz enrolment curriculum Bloom C1000-207',
      roleTag:      'bootcamp_student',
      focusAreas: [
        'PostgreSQL schema: questions, exams, quiz_attempts, enrolment_queue',
        'Bloom taxonomy and C1000-207 IBM exam domain mapping',
        'Anti-cheat recording in exam-engine.ts',
        'n8n auto-enrolment from enrolment_queue INSERT trigger',
        'Admissions confidence gate 0.65 threshold',
        'Local EvalOS Next.js developer setup',
      ],
    },
    {
      subagentName: 'ailab-scan',
      scanner:      ailabScan,
      query:        'LiteLLM admissions agent ChromaDB RAG Lobster Trap MCP RHOAI',
      roleTag:      'bootcamp_student',
      focusAreas: [
        'Admissions agent chat interface (how students interact with AI)',
        'LiteLLM tier-3 granite-nano used for student-facing responses',
        'Lobster Trap protections on student input',
        'RHOAI namespace — stale doc risk (Month 3 caveat)',
        'MCP tool confirmation gate before data changes',
      ],
    },
    {
      subagentName: 'infra-scan',
      scanner:      infraScan,
      query:        'student namespace Keycloak SSO login portal Directus programme',
      roleTag:      'bootcamp_student',
      focusAreas: [
        'Keycloak SSO login flow for students',
        'Which namespaces students interact with (not solution-01..08)',
        'Directus CMS programme guide content structure',
        'n8n automation from admissions → Keycloak → EvalOS',
      ],
    },
  ],

  platform_engineer: [
    {
      subagentName: 'infra-scan',
      scanner:      infraScan,
      query:        'ArgoCD Tekton ROKS namespaces OpenBao Keycloak cert-manager RUNBOOK Makefile',
      roleTag:      'platform_engineer',
      focusAreas: [
        'FORBIDDEN namespaces: solution-01..08 — never modify',
        'ArgoCD app-of-apps.yaml 6-wave structure — adding wave 7',
        'Tekton pipeline i3-build-deploy: git-clone → buildah → trivy → rollout',
        'OpenBao bootstrap procedure from RUNBOOK.md',
        'Namespace topology: 12 managed namespaces',
        'cert-manager and TLS management',
        'Makefile build/deploy/secrets/test/dr sections',
      ],
    },
    {
      subagentName: 'ailab-scan',
      scanner:      ailabScan,
      query:        'LiteLLM KEDA autoscaler ChromaDB cluster config IBM Cloud credits',
      roleTag:      'platform_engineer',
      focusAreas: [
        'LiteLLM KEDA autoscaler (1–6 replicas, Prometheus metric)',
        'IBM Cloud credits $14,047 — cost governance',
        'ChromaDB cluster-internal endpoint and collection management',
        'n8n workflow reliability and alerting',
      ],
    },
    {
      subagentName: 'backend-scan',
      scanner:      backendScan,
      query:        'admissions_agent FastAPI EvalOS API Directus API endpoints health',
      roleTag:      'platform_engineer',
      focusAreas: [
        'Service health endpoints and liveness probes',
        'Environment variable injection from OpenBao',
        'API URL directory from platform-documentation.md',
        'Logging and observability patterns',
      ],
    },
  ],

  ai_ml_engineer: [
    {
      subagentName: 'ailab-scan',
      scanner:      ailabScan,
      query:        'LiteLLM ChromaDB RAG admissions agent Lobster Trap MCP RHOAI KEDA',
      roleTag:      'ai_ml_engineer',
      focusAreas: [
        'LiteLLM gateway tiers and credit conservation strategy',
        'ChromaDB collections and embedding strategy',
        'Admissions agent streaming SSE and confidence gate',
        'Lobster Trap firewall extending for new vectors',
        'RHOAI stale-doc risk (i3-ai-lab namespace Month 3)',
        'MCP 2-stage confirmation gate pattern',
      ],
    },
    {
      subagentName: 'model-scan',
      scanner:      modelScan,
      query:        'RAGAS promptfoo Locust confidence LiteLLM models C1000-207 Bloom evaluation',
      roleTag:      'ai_ml_engineer',
      focusAreas: [
        'RAGAS evaluation — running testing.py --ragas',
        'promptfoo red-team attack patterns',
        'Confidence gate tuning and monitoring',
        'Adding new models to LiteLLM without code changes',
        'Locust load-test baselines for streaming endpoints',
      ],
    },
    {
      subagentName: 'backend-scan',
      scanner:      backendScan,
      query:        'FastAPI admissions route authentication schema API',
      roleTag:      'ai_ml_engineer',
      focusAreas: [
        'FastAPI route and streaming pattern in admissions_agent.py',
        'EvalOS ai_interviews table — AI interview transcript JSONB schema',
        'Authentication pattern for AI agent API calls',
        'Environment variable conventions for model keys',
      ],
    },
  ],

  backend_engineer: [
    {
      subagentName: 'backend-scan',
      scanner:      backendScan,
      query:        'FastAPI Express routes authentication JWT schema API Directus endpoints',
      roleTag:      'backend_engineer',
      focusAreas: [
        'FastAPI admissions_agent.py endpoint structure',
        'EvalOS schema: all tables and key relationships',
        'Keycloak JWT validation and req.user pattern',
        'OpenBao secret injection — never hardcode env vars',
        'API URL directory from platform-documentation.md',
        'n8n webhook integration points',
        'Local dev: running admissions_agent.py and EvalOS API',
      ],
    },
    {
      subagentName: 'evalos-scan',
      scanner:      evalosScan,
      query:        'EvalOS schema quiz_attempts enrolment_queue ai_interviews questions',
      roleTag:      'backend_engineer',
      focusAreas: [
        'EvalOS schema tables a backend engineer will query/modify',
        'Anti-cheat counter schema in quiz_attempts',
        'enrolment_queue INSERT trigger to n8n',
        'ai_interviews JSONB transcript storage pattern',
      ],
    },
    {
      subagentName: 'infra-scan',
      scanner:      infraScan,
      query:        'namespace service discovery health RUNBOOK deploy rolling-update',
      roleTag:      'backend_engineer',
      focusAreas: [
        'Service-to-service communication patterns within cluster',
        'Rolling update strategy via Tekton pipeline',
        'Environment variable injection from OpenBao secrets',
      ],
    },
  ],

  security_engineer: [
    {
      subagentName: 'infra-scan',
      scanner:      infraScan,
      query:        'OpenBao Keycloak cert-manager RBAC secrets RUNBOOK security',
      roleTag:      'security_engineer',
      focusAreas: [
        'OpenBao KV v2 secret structure at i3/ path',
        'Keycloak realm i3 JWKS and RBAC roles',
        'cert-manager TLS issuers and certificate rotation',
        'ROKS RBAC policies — solution-01..08 protection',
        'Security scanning: Trivy in Tekton pipeline',
      ],
    },
    {
      subagentName: 'ailab-scan',
      scanner:      ailabScan,
      query:        'Lobster Trap prompt injection firewall security MCP confirmation gate',
      roleTag:      'security_engineer',
      focusAreas: [
        'Lobster Trap 12-pattern prompt injection defence',
        'MCP 2-stage confirmation gate prevents unsanctioned writes',
        'Human approval gates: green/yellow/red policy',
        'LiteLLM key rotation and API key management',
      ],
    },
    {
      subagentName: 'backend-scan',
      scanner:      backendScan,
      query:        'authentication middleware JWT validation rate limiting secrets',
      roleTag:      'security_engineer',
      focusAreas: [
        'Keycloak Bearer token validation middleware',
        'Rate limiting and DDoS protection patterns',
        'Secret injection — never log sensitive env vars',
        'CORS and input sanitisation on API routes',
      ],
    },
  ],
};

export interface AssessmentResult {
  role:          OnboardingRole;
  scanResults:   SubagentScanResult[];
  totalFindings: number;
  durationMs:    number;
}

/**
 * Run all subagents for the given role in parallel.
 * Each subagent fetches its own RAG context via the retriever.
 */
export async function assessRole(role: OnboardingRole): Promise<AssessmentResult> {
  const t0    = Date.now();
  const plans = SCAN_PLANS[role] ?? SCAN_PLANS['platform_engineer'];

  const scanResults = await Promise.all(
    plans.map(async (plan) => {
      const ragContext = await retrieveAsContext(plan.query, {
        roleTag:    plan.roleTag,
        topK:       10,
        minScore:   0.25,
      });

      const input: SubagentInput = {
        role,
        contextQuery: plan.query,
        ragContext,
        focusAreas:   plan.focusAreas,
      };

      return plan.scanner.run(input);
    }),
  );

  return {
    role,
    scanResults,
    totalFindings: scanResults.reduce((sum, r) => sum + r.findings.length, 0),
    durationMs:    Date.now() - t0,
  };
}
