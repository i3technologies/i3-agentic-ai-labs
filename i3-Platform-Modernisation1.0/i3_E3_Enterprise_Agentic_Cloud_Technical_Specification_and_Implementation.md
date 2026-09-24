# i3 E³ + Enterprise Collaboration, Cloud & Agentic AI Platform
## Consolidated Technical Specification & Implementation Document

**Document Type:** Senior Solutions Architecture / Full-Stack Engineering Specification  
**Status:** Consolidated Architecture Baseline  
**Version:** 1.0  
**Date:** 20 September 2026  
**Primary Region:** Kenya / East Africa  
**Primary Deployment Target:** Red Hat OpenShift on IBM Cloud (ROKS), with a Nairobi sovereign deployment path and customer-premises portability  
**Architecture Style:** API-first, event-driven, graph-centred, multi-tenant, zero-trust, agentic AI platform  
**Audience:** CTO, Chief Architect, Engineering Leads, Platform/SRE, Security, Data, AI/Agent Engineering, Product and Delivery Teams

---

## 1. Executive Summary

This document consolidates the two supplied architecture baselines into one implementation-oriented technical specification.

The first source defines **i3 E³ — Ecosystem, Enablement & Execution Exchange** as a graph-centred, event-sourced execution platform with an agentic control layer. Its engineering north star is that every meaningful ecosystem capability, opportunity, delivery and proof should become actionable and discoverable through a shared Work Graph. The source explicitly requires a multi-tenant architecture, event-driven integration, progressive agent autonomy, evidence by construction, open protocols, cost attribution and portability across ROKS, Nairobi and a sovereign appliance path.

The second source defines a broader **Enterprise Digital Operating Platform** built around Nextcloud, Zimbra, Keycloak, PostgreSQL, Redis, Ceph/S3, LangGraph, local model serving and Qdrant. It extends the platform into collaboration, enterprise email, private knowledge, managed security, workflow automation, document intelligence, customer self-service, payments and managed-service operations.

The consolidated architecture therefore treats the platform as five integrated planes:

1. **Experience Plane** — customer portal, partner/engineer workspaces, collaboration, email, dashboards and public verification.
2. **Application & Ecosystem Plane** — Nextcloud, Zimbra, i3 E³ exchanges, ERP/CRM/LMS and managed-service applications.
3. **Agent Plane** — LangGraph, agent registry, model gateway, RAG, MCP tools, policy enforcement and evaluation.
4. **Data Plane** — PostgreSQL, Work Graph, Qdrant, OpenSearch, Ceph/S3, Kafka and analytical/lakehouse storage.
5. **Trust & Operations Plane** — Keycloak, OPA, Vault, WAF, SIEM/SOC, observability, evidence, credential trust and disaster recovery.

The i3 E³ source explicitly establishes ROKS Frankfurt as the primary target with a Nairobi sovereign node path and Sovereign AI Appliance portability. It also establishes the launch milestone of 16 October 2026. The implementation must therefore preserve portability and data-sovereignty boundaries from the first sprint rather than retrofitting them later.

The second source establishes Nextcloud + Zimbra + centralized identity + local Agentic AI as the core enterprise collaboration architecture, with a target of sovereign-capable, API-first operation. These systems should not be replaced by i3 E³; they should be integrated as foundational enterprise capabilities behind a common identity, API, event, policy and observability fabric.

---

# 2. Source Review and Architectural Synthesis

## 2.1 Source A — i3 E³

The i3 E³ document describes itself as the authoritative engineering implementation reference and identifies the Work Graph, event backbone, agentic runtime, trust/evidence plane, multi-tenancy, GitOps, observability and Kenya data-protection alignment as core engineering concerns.

Its central architectural statement is that i3 E³ is not a CRM, LMS, document repository or social network; it is a **graph-centred, event-sourced execution platform with an agentic control layer**.

Key source-derived architectural commitments:

- Work Graph is the system of context.
- Events are the integration spine.
- Agents propose; policy authorizes, blocks or escalates.
- Open protocols are preferred at integration seams.
- Containers and portability are preferred over platform lock-in.
- Evidence is generated as part of workflow execution.
- Multi-tenancy is mandatory from the beginning.
- Deterministic code controls money, permissions and credentials.
- LLMs are used primarily at the probabilistic edge.
- Observability and cost attribution are part of the definition of done.
- Agent autonomy is progressively promoted based on evaluation evidence.

The source also specifies digital passports for partners, engineers, solutions and agents; W3C Verifiable Credentials; Hyperledger Fabric for credential proof anchoring; and an MVP consisting of 13 capabilities.

## 2.2 Source B — Enterprise Collaboration / Cloud / Agentic AI

The second source establishes a broader enterprise platform around:

- Nextcloud for collaboration and content.
- Zimbra for enterprise mail and calendaring.
- Keycloak for centralized identity.
- PostgreSQL and Redis for application state/cache.
- Ceph/S3 for scalable object storage.
- LangGraph for agent orchestration.
- vLLM/Ollama for local/private model serving.
- Qdrant for semantic retrieval.
- OCR/PDF processing for document intelligence.
- API gateway + event bus + workflow engine for integration.
- SIEM/SOC/EDR/XDR/SOAR for managed security.
- Customer self-service, billing, metering and managed services.

The source also specifies zero-trust controls, permission-aware RAG, capability-based agent tools, human approval for high-impact actions, backup/DR, IaC, DevSecOps and an enterprise agent marketplace.

## 2.3 Consolidation Decision

The two documents are complementary rather than mutually exclusive.

The recommended architecture is:

```text
                 ENTERPRISE DIGITAL OPERATING PLATFORM
                                |
        +-----------------------+-----------------------+
        |                       |                       |
   Experience               Applications              Trust
        |                       |                       |
 Portal / PWA          Nextcloud / Zimbra       Keycloak / OPA
 Partner Workspace     i3 E³ Exchanges          Vault / Audit
 Mission Control       ERP / CRM / LMS          SIEM / SOC
        |                       |                       |
        +-----------------------+-----------------------+
                                |
                         Integration Fabric
                                |
                  API Gateway + Event Backbone
                                |
                     Agentic Control Plane
                                |
                Policy + Agents + MCP + A2A
                                |
                         Knowledge Plane
                                |
           Work Graph + Qdrant + OpenSearch + S3
                                |
                         Infrastructure
                                |
            OpenShift / Kubernetes / Storage / GPU
```

### Important reconciliation

The i3 E³ source recommends a **modular monolith with clean internal boundaries** because the initial team is approximately 14 FTE. The enterprise source recommends Kubernetes for stateless microservices and AI/integration services while cautioning against forcing every component into Kubernetes.

The consolidated decision is therefore:

- **i3 E³ domain core:** modular monolith initially.
- **AI runtime:** independently deployable services.
- **Nextcloud/Zimbra:** independently operated platform products.
- **Integration/event fabric:** independently scalable infrastructure.
- **Data infrastructure:** independently operated stateful services.
- **Extraction into microservices:** evidence-driven only.

This preserves the i3 E³ team-size constraint while still allowing enterprise platform components to scale independently.

---

# 3. Goals and Non-Goals

## 3.1 Goals

The implementation MUST provide:

1. Secure multi-tenancy.
2. Centralized identity and federation.
3. Collaboration and enterprise email integration.
4. i3 E³ ecosystem workflows.
5. Work Graph as canonical context.
6. Event-driven state propagation.
7. Agentic workflows with externalized authorization.
8. Permission-aware RAG.
9. Enterprise document/PDF intelligence.
10. Digital Passports and credential verification.
11. Managed-service capabilities.
12. Usage and AI cost metering.
13. Observability across application, infrastructure and agents.
14. Backup and disaster recovery.
15. Sovereign deployment portability.
16. API-first integration.
17. Full auditability of consequential actions.
18. CI/CD and infrastructure-as-code.
19. Automated security and AI evaluation gates.

## 3.2 Non-Goals

The supplied i3 E³ source explicitly excludes or defers:

- Foundation-model training/fine-tuning.
- Physical Sovereign AI Appliance hardware build.
- Commercial pricing and partner economics.
- Legal drafting of agreements.
- Marketing/event-site development.
- Full financial forecasting.
- Agent marketplace monetization in MVP.
- Full contribution settlement engine in MVP.
- Multi-country federation in MVP.
- Native mobile applications in the first year.

These exclusions should remain protected by architecture governance.

---

# 4. Architecture Principles

The following principles are binding unless an ADR records an exception.

## P1 — Work Graph as System of Context

The Work Graph is not a reporting database. It is the canonical graph of organizations, people, capabilities, opportunities, solutions, evidence, agents, projects and relationships.

## P2 — Events as the Spine

Every material domain state change emits a versioned event. Consumers build projections, analytics, notifications, agent triggers and evidence records asynchronously.

## P3 — Agents Propose; Policy Disposes

An LLM or agent does not independently authorize a consequential action. It submits an intent. Policy determines whether the action is allowed, requires approval, or must be rejected.

## P4 — Open Protocols

Preferred boundaries:

- REST/OpenAPI for synchronous APIs.
- CloudEvents for events.
- MCP for agent-to-tool access.
- A2A for agent delegation where required.
- OpenTelemetry for telemetry.
- W3C Verifiable Credentials for credentials.

## P5 — Portability First

Production workloads MUST be OCI-containerized and deployable without source-code changes across the primary OpenShift environment, a Nairobi sovereign environment and an approved customer-premises environment.

## P6 — Evidence by Construction

Business workflows should create evidence automatically. Proof should not depend on retrospective manual uploads.

## P7 — Multi-Tenant from Day One

`tenant_id` MUST be represented in:

- application state,
- database indexes,
- event envelopes,
- object storage paths,
- vector metadata,
- prompts/context,
- audit events,
- agent transactions,
- logs and traces.

## P8 — Deterministic Core, Probabilistic Edge

Deterministic code controls:

- permissions,
- money,
- state transitions,
- credential issuance,
- tenant isolation,
- contractual state.

AI handles:

- extraction,
- classification,
- summarization,
- matching,
- drafting,
- ranking,
- explanation.

## P9 — Small, Deeply Governed Interfaces

Every API, event and tool should have a typed contract, versioning strategy, authorization policy and audit semantics.

## P10 — Observable by Default

A feature is incomplete if its traces, metrics, logs, business KPI and cost attribution are missing.

## P11 — Progressive Autonomy

Agents begin at the lowest useful autonomy level and are promoted only through evaluation evidence and release governance.

## P12 — Privacy as a Design Input

Personal data is minimized, classified, encrypted and retained only for defined purposes. Credential proof infrastructure MUST NOT become a repository for personal data.

---

# 5. Target Logical Architecture

## 5.1 Eight-Layer Platform Model

| Layer | Responsibility | Primary Technology |
|---|---|---|
| L1 Experience | PWA, portals, workspaces, dashboards, verification | Next.js, React, TypeScript |
| L2 Edge | TLS, WAF, rate limiting, API composition | NGINX/HAProxy, WAF, API Gateway |
| L3 Identity | Authentication, federation, authorization | Keycloak, OIDC, SAML, LDAP, OPA |
| L4 Domain | i3 E³ and enterprise business modules | Java 21/Quarkus + selected Python services |
| L5 Agent | Orchestration, tools, memory, evaluation | LangGraph, MCP, A2A, model gateway |
| L6 Knowledge/Data | Relational, graph, vector, search, object and events | PostgreSQL, Graph, Qdrant, OpenSearch, S3, Kafka |
| L7 Trust/Evidence | Credentials, proofs, audit and verification | W3C VC, Fabric, Vault/HSM |
| L8 Platform/Ops | Containers, GitOps, CI/CD, telemetry, backup | OpenShift, Argo CD, Tekton, OTel, Prometheus |

---

# 6. Experience Architecture

## 6.1 Applications

The platform SHOULD expose a single logical experience with role-aware workspaces:

### Customer Workspace

- Services dashboard.
- Users and domains.
- Storage.
- Mail.
- Incidents.
- Backups.
- Security posture.
- AI usage.
- Support tickets.
- Billing/usage.
- AI approvals.

### Partner Workspace

- Partner Passport.
- Capabilities.
- Certifications.
- Opportunities.
- Matching.
- Solutions.
- Delivery history.
- Evidence.
- Contribution records.

### Engineer Workspace

- Engineer Passport.
- Skills.
- Certifications.
- Availability.
- Assignments.
- Learning.
- Assessments.
- Evidence.

### Transformation Room

- Opportunity.
- Customer requirements.
- Partner shortlist.
- Solution architecture.
- FDE pod.
- Documents.
- Decisions.
- Milestones.
- Evidence.
- Approvals.

### Mission Control

- Platform health.
- Ecosystem KPIs.
- Opportunity pipeline.
- Partner activation.
- Delivery.
- AI usage/cost.
- Agent quality.
- Security.
- SLOs.

### Public Verification

- Credential QR verification.
- Passport verification.
- Issuer key status.
- Credential status.
- No unnecessary personal information.

---

# 7. Front-End Technical Specification

## 7.1 Technology

Recommended:

- Next.js App Router.
- React.
- TypeScript.
- Tailwind CSS.
- PWA service worker.
- WebSocket/SSE for live state.
- IndexedDB for offline-tolerant reads and queued writes.

## 7.2 Front-End Architecture

```text
apps/
  portal/
  partner-workspace/
  engineer-workspace/
  customer-room/
  mission-control/
  verification/

packages/
  ui/
  auth/
  api-client/
  event-client/
  permissions/
  telemetry/
  offline/
```

## 7.3 PWA Requirements

The client MUST support:

- cached application shell,
- cached non-sensitive reference data,
- offline read access where permitted,
- queued low-risk writes,
- idempotency keys,
- synchronization status,
- conflict detection,
- retry with exponential backoff.

Sensitive data SHOULD NOT be cached offline unless the tenant policy explicitly permits it.

---

# 8. Identity and Access Architecture

## 8.1 Identity Provider

Keycloak is the central identity broker.

Supported federation:

- OIDC.
- SAML 2.0.
- LDAP/Active Directory.
- WebAuthn/passkeys.
- MFA.

## 8.2 Identity Domains

Use separate administrative and end-user identities.

Service and agent identities MUST be separate from human identities.

## 8.3 Authorization

Authorization is evaluated at multiple layers:

```text
User / Agent Identity
        |
        v
Tenant Context
        |
        v
Role / Attribute
        |
        v
Resource Permission
        |
        v
Purpose / Data Classification
        |
        v
Tool Policy
        |
        v
Action Policy
```

Recommended policy engine: OPA.

## 8.4 Tenant Isolation

Tenant isolation MUST be enforced at:

1. API layer.
2. Application/domain layer.
3. PostgreSQL Row-Level Security.
4. Object storage.
5. Vector database metadata/collections.
6. Search indexes.
7. Event consumers.
8. Agent context.
9. Tool authorization.
10. Audit logs.

---

# 9. Domain Architecture

## 9.1 i3 E³ Domain Modules

Initial modular-monolith modules:

```text
partner
opportunity
solution
engineering
academy
lab
event
delivery
commercial
trust
passport
graph
evidence
agentops
notification
integration
```

## 9.2 Enterprise Platform Modules

```text
tenant
identity
customer
mail-integration
collaboration
document
workflow
billing
metering
support
security
backup
ai-platform
knowledge
```

## 9.3 Module Boundary Rule

A module MUST own:

- commands,
- domain state,
- validation,
- domain events,
- authorization checks,
- database migrations,
- tests.

Modules MUST NOT directly manipulate another module's database tables.

Cross-module interactions occur through:

- domain APIs,
- application commands,
- events.

---

# 10. Core Domain State Machines

## 10.1 Partner

```text
prospect
  -> registered
  -> verified
  -> enabled
  -> active
  -> dormant
  -> offboarded
```

Source guard conditions:

- verification requires KYC evidence hashes.
- enabled requires at least one certified engineer.
- active requires a recent registered opportunity or delivery.

## 10.2 Opportunity

```text
captured
  -> qualified
  -> registered
  -> matched
  -> proposed
  -> won/lost
  -> delivering
  -> delivered
  -> renewed
```

Registration creates the source-defined exclusivity period.

## 10.3 Agent

```text
draft
  -> evaluated
  -> approved
  -> L0
  -> L1
  -> L2
  -> L3
  -> suspended
  -> retired
```

Promotion is a release decision, not a runtime configuration toggle.

## 10.4 Credential

```text
evidence-created
  -> assessment-complete
  -> issuance-proposed
  -> human-approved
  -> issued
  -> active
  -> expired/revoked
```

---

# 11. Work Graph Specification

## 11.1 Canonical Entities

Minimum graph entities:

- Tenant.
- Organization.
- Person.
- Partner.
- Engineer.
- Skill.
- Certification.
- Opportunity.
- Solution.
- Project.
- Delivery.
- Evidence.
- Credential.
- Agent.
- Tool.
- Workflow.
- Revenue Event.
- Learning Activity.
- Assessment.

## 11.2 Core Relationships

```text
Person -[:HAS_SKILL]-> Skill
Person -[:CERTIFIED_IN]-> Certification
Organization -[:EMPLOYS]-> Person
Organization -[:DELIVERED]-> Opportunity
Opportunity -[:REQUIRES]-> Skill
Opportunity -[:REGISTERED_BY]-> Organization
Evidence -[:ATTESTS]-> Credential
Evidence -[:ATTESTS]-> Milestone
RevenueEvent -[:ATTRIBUTED_TO]-> Organization
RevenueEvent -[:ATTRIBUTED_TO]-> Person
Agent -[:USES]-> Tool
Agent -[:OPERATES_ON]-> BusinessObject
```

## 11.3 Graph Projection

The graph is projected from domain events rather than becoming the transactional source of truth for every operation.

Recommended pattern:

```text
Domain Transaction
       |
Outbox
       |
Kafka / Event Backbone
       |
Graph Projection Consumer
       |
Work Graph
```

This gives deterministic transactional state plus rebuildable context.

---

# 12. Relational Data Architecture

## 12.1 PostgreSQL

PostgreSQL is the system of record for transactional state.

Requirements:

- UUIDv7 primary keys.
- `tenant_id` on every tenant-owned table.
- Row-Level Security.
- audit timestamps.
- optimistic concurrency/version field where appropriate.
- migration versioning.
- point-in-time recovery.

## 12.2 Example Base Table

```sql
CREATE TABLE organization (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    legal_name TEXT NOT NULL,
    country_code CHAR(2) NOT NULL,
    org_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'prospect',
    attributes JSONB NOT NULL DEFAULT '{}',
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE organization ENABLE ROW LEVEL SECURITY;

CREATE POLICY organization_tenant_isolation
ON organization
USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

## 12.3 Opportunity Exclusivity

The source specifies a 180-day exclusivity period and duplicate registration blocking.

Implementation MUST use:

- normalized scope fingerprint,
- transaction-level locking,
- database uniqueness constraints,
- state-aware validation,
- idempotency.

The database constraint is the final protection; UI checks are not sufficient.

---

# 13. Object Storage

Ceph/S3-compatible object storage is the recommended common object layer.

Object key convention:

```text
s3://platform/
  tenant/{tenant_id}/
    documents/{document_id}/
      version/{version}/
    evidence/{evidence_id}/
    passports/{passport_id}/
    exports/{export_id}/
    backups/{backup_id}/
```

Controls:

- encryption at rest.
- object versioning.
- lifecycle rules.
- malware scanning.
- retention policies.
- legal hold.
- immutable evidence buckets where required.

---

# 14. Knowledge and RAG Architecture

## 14.1 RAG Pipeline

```text
Source Systems
   |
Document Acquisition
   |
Malware / DLP Scan
   |
OCR / Parsing
   |
Layout + Table Extraction
   |
Classification
   |
Metadata Enrichment
   |
Chunking
   |
Embedding
   |
Qdrant
   |
Permission-Aware Retrieval
   |
Reranking
   |
LLM
   |
Grounded Response + Citations
```

## 14.2 Permission Model

Every indexed chunk MUST retain:

- tenant ID,
- document ID,
- owner,
- department,
- classification,
- source system,
- ACL/security labels,
- retention class,
- version.

The retrieval service MUST filter against the requesting principal's effective permissions before context reaches the model.

## 14.3 Knowledge Graph + Vector Search

Use hybrid retrieval:

```text
Structured question
      |
Graph retrieval
      +
Semantic vector retrieval
      +
Keyword/search retrieval
      |
Reranker
      |
Context assembler
      |
LLM
```

This supports the i3 E³ Work Graph while preserving document-level semantic retrieval.

---

# 15. Document and PDF Intelligence

## 15.1 Pipeline

```text
PDF / Scan / Image
       |
PaddleOCR / pdfplumber
       |
Layout / Table Detection
       |
Document Classification
       |
Chunk + Metadata
       |
Embedding
       |
Qdrant
       |
Specialist Agents
       |
Cross-check / Validation
       |
Human Review
       |
Generated Report
       |
Evidence + Audit
```

## 15.2 Initial Use Cases

Prioritize:

1. RFP/tender analysis.
2. Contract compliance.
3. Invoice extraction.
4. Procurement analysis.
5. Policy compliance.
6. Technical specification comparison.
7. Regulatory document analysis.
8. Executive briefing generation.

---

# 16. Event-Driven Architecture

## 16.1 Event Backbone

Kafka/Redpanda is the preferred high-volume event backbone.

RabbitMQ may be used for workflow/task semantics where appropriate.

NATS may be used for lightweight internal messaging.

The final selection MUST be recorded in an ADR.

## 16.2 CloudEvents Envelope

Example:

```json
{
  "specversion": "1.0",
  "type": "i3.opportunity.registered.v1",
  "source": "opportunity-service",
  "id": "0192...",
  "time": "2026-09-20T16:30:00Z",
  "subject": "opportunity/0192...",
  "datacontenttype": "application/json",
  "data": {
    "tenant_id": "tenant-001",
    "opportunity_id": "opp-001",
    "registered_by": "org-001",
    "exclusivity_until": "2027-03-19T16:30:00Z"
  }
}
```

## 16.3 Event Rules

Events MUST be:

- versioned.
- immutable.
- tenant-aware.
- trace-correlated.
- idempotently consumable.
- schema-validated.

---

# 17. API Architecture

## 17.1 External API

Expose REST/OpenAPI APIs behind an API Gateway.

Capabilities:

- OAuth2/OIDC.
- JWT validation.
- API keys where appropriate.
- tenant quotas.
- rate limiting.
- request signing for selected integrations.
- API versioning.
- webhooks.
- audit logging.

## 17.2 API Domains

```text
/api/v1/tenants
/api/v1/organizations
/api/v1/partners
/api/v1/engineers
/api/v1/opportunities
/api/v1/solutions
/api/v1/projects
/api/v1/passports
/api/v1/evidence
/api/v1/credentials
/api/v1/agents
/api/v1/tools
/api/v1/workflows
/api/v1/documents
/api/v1/knowledge
/api/v1/ai
/api/v1/metering
/api/v1/audit
```

## 17.3 API Design Rules

Every mutating API SHOULD support:

- idempotency key.
- request ID.
- tenant context.
- actor identity.
- authorization decision.
- audit event.
- trace ID.

---

# 18. Agentic AI Architecture

## 18.1 Agent Runtime

```text
                    Agent Gateway
                         |
                   Identity Context
                         |
                  Policy / Guardrails
                         |
                   Agent Registry
                         |
                    LangGraph
                         |
        +----------------+----------------+
        |                |                |
      Planner        Specialist        Reviewer
        |                |                |
        +----------------+----------------+
                         |
                     Tool Broker
                         |
              MCP / approved connectors
                         |
         +---------------+----------------+
         |               |                |
     Nextcloud         Zimbra           ERP/CRM
         |               |                |
         +---------------+----------------+
                         |
                     Audit Ledger
```

## 18.2 Agent Passport

Each agent MUST declare:

- identity.
- purpose.
- owner.
- version.
- tools.
- data scope.
- model/runtime.
- risk tier.
- evaluation suite.
- cost envelope.
- autonomy level.
- approval policy.
- kill-switch state.

## 18.3 Agent Classes

Initial portfolio:

### Ecosystem

- Partner Onboarding Agent.
- Partner Match Agent.
- Opportunity Qualification Agent.
- Solution Architect Agent.
- FDE Dispatch Agent.
- Partner Health Agent.
- Revenue Attribution Agent.
- Ecosystem Strategist.

### Enterprise Productivity

- Email summarization.
- Meeting preparation.
- Meeting minutes.
- Task extraction.
- Document drafting.

### Business Operations

- Customer-service agent.
- Finance/invoice agent.
- HR onboarding agent.
- Support/ticket agent.

### Security

- Phishing analysis.
- Alert enrichment.
- Suspicious-login investigation.
- Security response preparation.

### Academic

- Academy Coach.
- Tutor.
- Assignment assessment assistant.

---

# 19. Agent Risk and Autonomy Model

## 19.1 Risk Tiers

### Tier 0 — Read Only

- Search.
- Retrieve.
- Summarize.
- Classify.

### Tier 1 — Draft

- Draft emails.
- Draft documents.
- Draft tickets.
- Draft quotations.

### Tier 2 — Controlled Action

- Create calendar events.
- Update CRM.
- Move files.
- Open tickets.

### Tier 3 — High Impact

Human approval required for:

- payments,
- account deletion,
- privileged access,
- legal acceptance,
- production infrastructure changes,
- critical security isolation.

### Tier 4 — Prohibited

Agents MUST NOT autonomously:

- extract uncontrolled credentials,
- bypass security controls,
- obtain arbitrary production shell access,
- perform destructive database operations outside governed break-glass procedures.

## 19.2 Autonomy Levels

```text
L0 Observe / Recommend
L1 Propose / Human Gate
L2 Execute Within Policy
L3 Autonomous Within Published Bounds
```

Promotion MUST require:

- evaluation results,
- security review,
- cost review,
- owner approval,
- rollback plan,
- updated Agent Passport.

---

# 20. Model Gateway

All model access MUST go through a model gateway.

Responsibilities:

- model selection.
- routing.
- authentication.
- tenant cost attribution.
- token accounting.
- rate limiting.
- semantic caching.
- fallback.
- model health.
- prompt/version metadata.
- policy enforcement.

## 20.1 Model Routing

```text
Simple classification
        -> small/fast model

Complex reasoning
        -> reasoning model

OCR/document extraction
        -> vision/document model

Embeddings
        -> embedding model

Reranking
        -> reranker

Security classification
        -> specialized model
```

No application should hard-code a specific model endpoint.

---

# 21. Agent Tool Architecture

## 21.1 Tool Registry

Each tool MUST declare:

```json
{
  "tool_id": "nextcloud.create_folder",
  "version": "1.0",
  "side_effect": "write",
  "risk_tier": 2,
  "required_scopes": [
    "files.write"
  ],
  "tenant_scoped": true,
  "audit_required": true
}
```

## 21.2 Tool Invocation Flow

```text
Agent Intent
    |
Identity Validation
    |
Tenant Validation
    |
Policy Evaluation
    |
Data Entitlement Check
    |
Tool Risk Evaluation
    |
Human Approval if required
    |
Execute
    |
Validate Result
    |
Audit
    |
Emit Event
```

---

# 22. Collaboration Integration

## 22.1 Nextcloud

Nextcloud is the collaboration/content plane.

Deploy:

- multiple application nodes.
- PHP-FPM.
- Redis for locking/cache.
- PostgreSQL HA.
- object storage.
- Talk/HPB where required.
- ONLYOFFICE or Collabora.
- background workers.
- malware/content scanning.
- audit logging.

## 22.2 Zimbra

Zimbra is the enterprise mail/calendar platform.

Production topology:

```text
Internet
   |
DNS / MX
   |
Mail Security Gateway
   |
Load Balancer
   |
MTA Cluster
   |
Mailbox Cluster
   |
Directory
   |
Storage
```

Email security MUST include:

- SPF.
- DKIM.
- DMARC.
- MTA-STS.
- TLS-RPT.
- malware scanning.
- attachment sandboxing.
- rate limiting.
- reputation monitoring.

---

# 23. Workflow Engine

The workflow engine is the deterministic bridge between applications and agents.

Example:

```text
Incoming Tender Email
       |
Zimbra
       |
Event
       |
Workflow Trigger
       |
Tender Agent
       |
Attachment Acquisition
       |
OCR / Parse
       |
Compliance Agent
       |
Pricing Agent
       |
Risk Agent
       |
Executive Review
       |
Proposal Draft
       |
Approval
       |
Outbound Response
```

Workflow state MUST be persisted and resumable.

Agents MUST NOT be responsible for maintaining authoritative workflow state.

---

# 24. Digital Passports and Trust Plane

## 24.1 Passport Types

- Partner Passport.
- Engineer Passport.
- Solution Passport.
- Agent Passport.

## 24.2 Credential Architecture

The source specifies:

- W3C Verifiable Credentials Data Model 2.0.
- Hyperledger Fabric for permissioned proof anchoring.
- HSM-backed issuer keys.
- sub-second QR verification target.
- offline verification against published issuer keys.

## 24.3 Issuance Flow

```text
Assessment Evidence
       |
Assessment Agent
       |
Issuance Proposal
       |
Named Human Approver
       |
W3C VC Signing
       |
Hash Anchor
       |
Fabric
       |
Verification API
```

The ledger MUST NOT store personal data or source documents.

---

# 25. Security Architecture

## 25.1 Security Layers

```text
1. DNS / DDoS
2. WAF
3. Network segmentation
4. Identity / MFA
5. Endpoint security
6. Application security
7. Data security
8. AI security
9. SOC / Monitoring
10. Backup / Recovery
```

## 25.2 Network Zones

Recommended zones:

- DMZ.
- Ingress.
- Identity.
- Application.
- Database.
- Storage.
- AI/GPU.
- Management.
- Backup.
- Monitoring.
- Tenant/customer integration.

Default deny between zones.

## 25.3 Secrets

Use Vault/KMS/HSM as appropriate.

Secrets include:

- database credentials.
- SMTP credentials.
- OAuth secrets.
- API tokens.
- encryption keys.
- agent tool credentials.
- backup credentials.
- issuer signing keys.

No long-lived secrets in source code.

---

# 26. AI Security

Treat AI as a security boundary.

Controls:

- prompt-injection detection.
- tool authorization.
- output validation.
- sensitive-data detection.
- PII redaction.
- secret scanning.
- retrieval authorization.
- model isolation.
- model registry.
- prompt/version governance.
- AI activity logging.
- kill switch.
- human approval gates.

## 26.1 Agent Transaction Record

```json
{
  "agent_id": "finance-agent",
  "tenant_id": "tenant-001",
  "user_id": "user-123",
  "intent": "process_invoice",
  "tools_used": ["ocr", "erp_lookup"],
  "data_accessed": ["invoice-44"],
  "decision": "requires_approval",
  "risk": "medium",
  "timestamp": "2026-09-20T16:30:00Z",
  "approval": null
}
```

---

# 27. Data Governance

## 27.1 Classification

| Classification | Example | Required Controls |
|---|---|---|
| Public | Marketing content | Standard controls |
| Internal | Procedures | Authenticated access |
| Confidential | Contracts | MFA + RBAC + DLP |
| Restricted | Financial/identity data | Strong authorization + encryption + audit |
| Highly Restricted | Secrets/credentials | Vault/HSM; excluded from default AI retrieval |

## 27.2 Data Lifecycle

Every data class MUST define:

- purpose.
- owner.
- retention period.
- legal hold behavior.
- backup retention.
- deletion mechanism.
- access review frequency.
- AI processing eligibility.

Kenya Data Protection Act alignment MUST be reviewed by the DPO and appropriate counsel before production personal-data processing.

---

# 28. Storage Architecture

## 28.1 Tiering

```text
Hot
  PostgreSQL
  Redis
  NVMe/cache

Warm
  Ceph/S3

Cold
  Encrypted immutable archive

DR
  Independent failure domain
```

## 28.2 Backup

Implement 3-2-1 principles:

```text
Production
   |
Primary Backup
   |
Immutable Backup
   |
Off-site DR Copy
```

Recommended starting targets, to be validated through BIA:

- critical services: RPO <= 15 minutes where justified.
- critical services: RTO 1–4 hours.
- ordinary collaboration: RPO 4–24 hours.
- ordinary collaboration: RTO 4–24 hours.

---

# 29. High Availability

Do not place all replicas in one physical failure domain.

Illustrative topology:

```text
Site / Failure Domain A      Site / Failure Domain B

Nextcloud-01                 Nextcloud-02
Zimbra-01                    Zimbra-02
DB-01                         DB-02
Redis-01                      Redis-02
AI-01                         AI-02
Storage Nodes                 Storage Nodes
```

Availability targets MUST be calculated from actual dependency chains rather than simply asserting 99.99%.

---

# 30. Infrastructure and Deployment

## 30.1 Target Platform

Primary:

- Red Hat OpenShift on IBM Cloud.

Portability:

- Nairobi sovereign OpenShift/Kubernetes.
- approved customer-premises appliance/private cloud.

## 30.2 Kubernetes Candidates

Good candidates:

- API services.
- Agent gateway.
- workflow services.
- OCR workers.
- RAG services.
- model gateway.
- observability.
- internal APIs.

Stateful systems may be externalized or operated with mature operators:

- PostgreSQL.
- Ceph.
- Zimbra.
- specialized mail storage.

## 30.3 Infrastructure as Code

Use:

- Terraform/OpenTofu.
- Ansible.
- Git.
- Kubernetes manifests/Helm where appropriate.
- Argo CD.
- Tekton or equivalent CI.

---

# 31. Repository Architecture

Recommended monorepo:

```text
platform/
├── apps/
│   ├── portal/
│   ├── partner-workspace/
│   ├── engineer-workspace/
│   ├── mission-control/
│   └── verification/
├── services/
│   ├── api-gateway/
│   ├── domain-core/
│   ├── graph-projector/
│   ├── document-service/
│   ├── workflow-service/
│   ├── agent-gateway/
│   ├── model-gateway/
│   ├── retrieval-service/
│   └── evidence-service/
├── packages/
│   ├── contracts/
│   ├── ui/
│   ├── auth/
│   └── telemetry/
├── agents/
│   ├── partner-match/
│   ├── qualification/
│   ├── solution-architect/
│   ├── email/
│   ├── document/
│   └── security/
├── infrastructure/
│   ├── terraform/
│   ├── ansible/
│   ├── openshift/
│   └── networking/
├── policies/
│   ├── opa/
│   └── data-access/
├── schemas/
│   ├── events/
│   └── openapi/
├── tests/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   └── ai-evals/
└── docs/
    ├── adr/
    ├── architecture/
    └── runbooks/
```

---

# 32. CI/CD and DevSecOps

## 32.1 Pipeline

```text
Developer
   |
Git Pull Request
   |
Lint / Format
   |
Unit Tests
   |
SAST
   |
Dependency Scan
   |
Secret Scan
   |
Container Build
   |
Image Scan / Sign
   |
Integration Tests
   |
Contract Tests
   |
AI Evaluation
   |
Staging
   |
Security / QA Gates
   |
Production
   |
Post-Deploy Verification
```

No normal manual production deployments.

## 32.2 Deployment Strategy

Use:

- GitOps.
- immutable images.
- signed artifacts.
- progressive deployment.
- health probes.
- automated rollback.
- database migration gates.
- feature flags for controlled releases.

---

# 33. Observability

## 33.1 Three Pillars

- Metrics: Prometheus + Grafana.
- Logs: OpenSearch-compatible stack.
- Traces: OpenTelemetry + Tempo/Jaeger.

## 33.2 Required Metrics

### Platform

- request latency.
- error rate.
- CPU.
- memory.
- storage.
- database replication lag.
- queue depth.

### Email

- delivery success.
- queue depth.
- bounce rate.
- spam detection.
- phishing detections.

### AI

- inference latency.
- token usage.
- GPU utilization.
- agent success rate.
- tool failures.
- grounding rate.
- human override rate.
- cost per workflow.

### Security

- MTTD.
- MTTR.
- open vulnerabilities.
- MFA coverage.
- endpoint coverage.
- incidents.

---

# 34. FinOps and AI Cost Ledger

Every agent invocation MUST be attributable to:

```text
Tenant
  |
Business Object
  |
Workflow
  |
Agent
  |
Model
  |
Tokens
  |
GPU Seconds
  |
Infrastructure Cost
  |
Outcome
```

The cost model should support:

- per-tenant cost.
- per-agent cost.
- per-workflow cost.
- per-document cost.
- OCR page cost.
- GPU usage.
- storage.
- API usage.

Cost controls:

- tenant caps.
- model routing.
- semantic caching.
- token budgets.
- rate limits.
- anomaly alerts.

---

# 35. Billing and Metering

Meter at least:

- users.
- mailboxes.
- storage.
- API requests.
- AI tokens.
- GPU time.
- OCR pages.
- document processing.
- workflow executions.
- SOC endpoints.
- backup volume.
- support tier.

Billing should consume immutable usage events rather than calculating usage from mutable application screens.

---

# 36. Integration Architecture

## 36.1 Enterprise Connectors

The platform SHOULD provide adapters for:

- ERP.
- CRM.
- HRIS.
- LMS.
- payment systems.
- ticketing.
- SMS.
- WhatsApp Business.
- M-Pesa/payment APIs.
- IBM ecosystem systems where approved.

## 36.2 Connector Contract

Every connector should define:

```text
Authentication
Rate limits
Capabilities
Inbound events
Outbound commands
Error mapping
Retry semantics
Idempotency
Audit requirements
Data classification
Tenant isolation
```

---

# 37. East African Connectivity and Offline Design

The i3 E³ source identifies connectivity variance as a specific design constraint.

Therefore:

- PWA is mandatory.
- public credential verification should support an offline verification path.
- critical reference data may be cached.
- writes should use durable client-side queues.
- large files should support resumable upload.
- synchronization must be explicit.
- the launch environment should support local-network fallback and pre-seeded demonstration data.

---

# 38. API and Event Security

Every request/event MUST support:

- correlation ID.
- tenant ID.
- actor/service identity.
- authorization context.
- timestamp.
- schema version.

Sensitive event payloads SHOULD contain references rather than raw personal information.

---

# 39. Testing Strategy

## 39.1 Unit Testing

Required for:

- state transitions.
- authorization.
- matching logic.
- pricing/attribution rules.
- validation.
- data transformations.

## 39.2 Integration Testing

Test:

- Keycloak.
- PostgreSQL.
- Redis.
- object storage.
- Kafka.
- Nextcloud.
- Zimbra.
- model gateway.
- Qdrant.
- external connectors.

## 39.3 Contract Testing

Every public API and event schema MUST have compatibility tests.

## 39.4 End-to-End Testing

Critical journeys:

1. Partner registration.
2. Passport creation.
3. Opportunity registration.
4. Duplicate opportunity rejection.
5. Partner/engineer matching.
6. FDE dispatch.
7. Academy enrolment.
8. Lab provisioning.
9. Credential issuance.
10. Credential verification.
11. Tender ingestion.
12. Agent proposal + approval.
13. Customer self-service.
14. Backup restoration.

## 39.5 AI Evaluation

Every production agent requires:

- functional tests.
- authorization tests.
- prompt-injection tests.
- tool-misuse tests.
- grounding tests.
- hallucination/error tests.
- reliability tests.
- regression tests.
- cost tests.

Maintain golden datasets for each agent.

---

# 40. Non-Functional Requirements

| Area | Initial Target |
|---|---|
| API latency | p95 < 500 ms for ordinary synchronous APIs, excluding long-running workflows |
| Partner matching | p95 < 3 seconds |
| Credential verification | p95 < 300 ms target |
| Lab provisioning | <= 5 minutes |
| Agent action | governed by workflow-specific SLO |
| Identity | 99.99% target |
| Email | 99.99% target |
| Collaboration | 99.95%–99.99% target |
| Agent gateway | 99.95% target |
| Backup job success | >= 99.9% |
| RPO critical | <= 15 minutes where justified |
| RTO critical | 1–4 hours |
| RPO standard | 4–24 hours |
| RTO standard | 4–24 hours |

These are engineering targets and must be validated against capacity, dependency and DR tests before contractual SLA commitments.

---

# 41. MVP Scope

The i3 E³ source defines 13 MVP capabilities. The consolidated platform should map them as follows:

| # | MVP Capability | Implementation |
|---|---|---|
| 1 | Partner registration + Passport | Partner module + Keycloak + evidence |
| 2 | Engineer/FDE Passport | Engineer module + skills/evidence |
| 3 | Academy + certification | Academy + LMS integration + credential workflow |
| 4 | Opportunity registration | Opportunity module + database exclusivity |
| 5 | Partner/engineer matching | Match agent + deterministic scoring |
| 6 | FDE dispatch | Dispatch workflow + availability |
| 7 | Solution catalogue | Solution Passport + SBOM |
| 8 | Lab booking | Lab provisioning + TTL + metering |
| 9 | AI Partner Copilot | Work Graph + RAG + citations |
| 10 | Work Graph | Event projection |
| 11 | Mission Control | Live KPI read models |
| 12 | Evidence + attribution | Evidence ledger + contribution events |
| 13 | Credential Trust Network | W3C VC + Fabric pilot |

---

# 42. Delivery Roadmap

## Phase 0 — Foundation

**Weeks 1–4**

Deliver:

- OpenShift baseline.
- GitOps.
- IAM.
- tenant model.
- event backbone.
- schema registry.
- observability.
- CI/CD.
- Partner aggregate.
- Opportunity aggregate.

Exit:

- partner registers end-to-end in staging.
- traces and metrics visible.
- security baseline clean.

## Phase 1 — MVP Core

**Weeks 5–12**

Deliver:

- Work Graph projection.
- Passports.
- Academy.
- Labs.
- Opportunity Exchange.
- Match/Qualification agents.
- Trust pilot.
- Mission Control.

Exit:

- all 13 MVP acceptance criteria pass for the controlled cohort.

## Phase 2 — Launch Hardening

**Weeks 13–16**

Deliver:

- performance testing.
- accessibility.
- adversarial testing.
- DR rehearsal.
- verification API scale test.
- launch onboarding.
- three complete rehearsals.

Launch milestone from the source: **16 October 2026**.

## Phase 3 — Depth

**Months 5–8**

Deliver:

- Solution Exchange depth.
- Engineering Exchange depth.
- Proposal Agent.
- Architect Agent.
- curriculum mapping.
- collaboration rooms.
- contribution ledger.
- first CRM/IBM connectors.

## Phase 4 — Scale

**Months 9–12**

Deliver:

- Agent Exchange.
- full AgentOps.
- attribution/settlement.
- country federation.
- public APIs.
- billing.
- second country node.

---

# 43. First 90-Day Engineering Backlog

## Sprint 1

Platform baseline:

- repository.
- CI.
- GitOps.
- tenant context.
- Keycloak.
- tracing.

## Sprint 2

Partner aggregate:

- registration.
- validation.
- tenant isolation.
- events.
- graph projection.

## Sprint 3

Passports:

- Partner Passport.
- Engineer Passport.
- evidence references.
- public verification shell.

## Sprint 4

Opportunity:

- registration.
- exclusivity.
- duplicate detection.
- event stream.

## Sprint 5

Agent runtime:

- Agent Registry.
- MCP broker.
- Match Agent.
- evaluation harness.

## Sprint 6

Academy/Trust:

- enrolment.
- lab.
- assessment.
- credential issuance.
- QR verification.

## Sprint 7

Qualification/Copilot:

- email ingestion.
- RFP extraction.
- Work Graph retrieval.
- cited response.

## Sprint 8

Hardening:

- load testing.
- penetration testing.
- prompt-injection tests.
- tenant-leakage tests.
- DR rehearsal.
- launch rehearsal.

---

# 44. Team Structure

The i3 E³ source defines a 14-FTE MVP team:

| Role | FTE |
|---|---:|
| Engineering Manager / Delivery Lead | 1 |
| Solutions Architect | 1 |
| Backend Engineers | 3 |
| AI / Agent Engineers | 2 |
| Frontend Engineers | 2 |
| Data Engineer | 1 |
| Platform / SRE | 1 |
| Security Engineer | 0.5 |
| QA / Test Engineer | 1 |
| Product Owner | 0.5 |

The broader enterprise platform will eventually require additional operational capacity in:

- security operations.
- customer support.
- database/storage operations.
- mail operations.
- network engineering.
- FinOps.
- compliance/data protection.

These can be added as managed services or dedicated teams after the MVP.

---

# 45. Governance and RACI

## Architecture

- Responsible: Solutions Architect.
- Accountable: CTO.
- Consulted: Engineering, Security, Platform.
- Informed: Programme stakeholders.

## Agent Autonomy

- Responsible: AI Engineering.
- Accountable: CTO.
- Consulted: Security, QA, Operations.
- Informed: governance stakeholders.

## Production Release

- Responsible: Engineering Manager.
- Accountable: CTO.
- Consulted: QA, SRE, Security.

## Data Classification

- Responsible: Security/Data Protection.
- Accountable: CTO/DPO.
- Consulted: Legal.

## Emergency Agent Halt

- Responsible: on-call engineer.
- Accountable: CTO.
- Act immediately; review afterward.

---

# 46. Architecture Decision Records

Create ADRs for at least:

```text
ADR-001 Platform Deployment Target
ADR-002 Modular Monolith Boundary
ADR-003 Identity Provider
ADR-004 API Gateway
ADR-005 Event Backbone
ADR-006 Work Graph Technology
ADR-007 Vector Database
ADR-008 Object Storage
ADR-009 Model Gateway
ADR-010 Agent Orchestration
ADR-011 Agent Tool Protocol
ADR-012 AI Policy Engine
ADR-013 Credential Trust Architecture
ADR-014 Multi-Tenant Isolation
ADR-015 Backup / DR
ADR-016 Nextcloud Integration
ADR-017 Zimbra Integration
ADR-018 ERP/CRM Integration Strategy
ADR-019 Payment Integration
ADR-020 Agent Marketplace
```

Each ADR MUST contain:

- Context.
- Problem.
- Options.
- Decision.
- Rationale.
- Security implications.
- Operational implications.
- Cost implications.
- Portability implications.
- Rollback/replacement strategy.

---

# 47. Technical Risks and Controls

| Risk | Impact | Control |
|---|---|---|
| Scope sprawl | High | Hard MVP boundary and change control |
| Agent quality insufficient | High | L0/L1 launch, golden datasets, human gates |
| AI cost growth | High | model routing, budgets, caching, tenant caps |
| Cross-tenant leakage | Critical | RLS, vector filtering, event isolation, leakage tests |
| Prompt injection | High | external authorization, provenance, adversarial suite |
| Launch pressure | Critical | release gates cannot be silently waived |
| Connectivity issues | Medium | PWA, offline verification, local rehearsal |
| Vendor lock-in | High | API abstraction, OCI, open protocols |
| Stateful platform complexity | High | mature operators / externalized services |
| DR untested | Critical | full restore drills |
| Credential key compromise | Critical | HSM/Vault, rotation, audit |
| Uncontrolled agent tooling | Critical | typed tool registry + policy broker |

---

# 48. Operational Runbooks

The production repository MUST include runbooks for:

1. Tenant isolation incident.
2. Agent kill switch.
3. Keycloak outage.
4. PostgreSQL failover.
5. Redis failure.
6. Kafka backlog.
7. Ceph/S3 failure.
8. Zimbra mail queue incident.
9. Nextcloud outage.
10. GPU/model outage.
11. Prompt-injection incident.
12. Data leakage incident.
13. Credential issuer key compromise.
14. Backup restore.
15. DR site activation.
16. WAF/DDoS incident.
17. Certificate expiry.
18. Secret rotation.
19. Failed deployment rollback.

---

# 49. Security and Compliance Gates

No production release should pass if any of the following is unresolved:

- critical vulnerability.
- failed tenant-isolation test.
- failed authorization test.
- unapproved secret.
- missing audit path for a consequential action.
- failed AI grounding threshold.
- failed prompt-injection regression.
- untested rollback for critical change.
- failed backup restore for critical service.
- missing data classification for a new data flow.

The source materials emphasize that security and evaluation gates are release-blocking and that waivers require explicit governance.

---

# 50. Recommended Implementation Sequence

The recommended implementation order is intentionally different from simply deploying every product in parallel.

## Stage 1 — Platform Kernel

Build:

- identity.
- tenancy.
- API gateway.
- event backbone.
- observability.
- secrets.
- CI/CD.
- policy engine.

## Stage 2 — Business Kernel

Build:

- Partner.
- Opportunity.
- Engineer.
- Passport.
- Evidence.
- Work Graph.

## Stage 3 — Enterprise Applications

Integrate:

- Nextcloud.
- Zimbra.
- document processing.
- customer portal.

## Stage 4 — Agent Kernel

Build:

- agent registry.
- model gateway.
- MCP broker.
- LangGraph runtime.
- evaluation harness.
- agent audit ledger.

## Stage 5 — Knowledge

Build:

- OCR.
- document pipeline.
- Qdrant.
- hybrid Graph + Vector retrieval.
- permission-aware RAG.

## Stage 6 — High-Value Agents

Launch:

1. Partner Match Agent.
2. Opportunity Qualification Agent.
3. Enterprise Document/RFP Agent.
4. Email/Meeting Agent.
5. Security Operations Agent.

## Stage 7 — Trust and Commercial Scale

Add:

- W3C credentials.
- Fabric anchoring.
- billing.
- metering.
- managed security.
- Agent Marketplace.
- country federation.

---

# 51. Definition of Done

A platform capability is DONE only when:

### Product

- acceptance criteria pass.

### Engineering

- code reviewed.
- tests pass.
- migration tested.
- API/event contracts documented.

### Security

- authorization tested.
- tenant isolation tested.
- secrets reviewed.
- threat model updated.

### AI

- evaluation suite passes.
- grounding validated.
- prompt-injection tests pass.
- cost budget configured.

### Operations

- metrics exist.
- logs exist.
- traces exist.
- alert rules exist.
- dashboard exists.
- runbook exists.

### Reliability

- failure behavior tested.
- backup/restore implications understood.
- rollback tested.

### Governance

- ADR updated if architecture changed.
- data classification updated.
- audit evidence available.

---

# 52. Recommended MVP Acceptance Matrix

| Capability | Functional Gate | Security Gate | Operational Gate |
|---|---|---|---|
| Partner Registration | End-to-end registration | Tenant isolation | Audit + traces |
| Passport | Correct rendering | Evidence access control | Verification monitoring |
| Opportunity | Exclusivity enforced | Authorization | Event trace |
| Matching | Ranked results + evidence | No mandatory violations | Latency SLO |
| FDE Dispatch | Costed options | Availability access control | Expiry monitoring |
| Solution Catalogue | Versioned solution | Tenant visibility | SBOM |
| Lab | <=5 min target | Sandbox isolation | Auto teardown |
| Copilot | Grounded cited answer | Permission-aware retrieval | Cost telemetry |
| Work Graph | Rebuildable projection | Tenant filtering | Projection lag |
| Mission Control | Live KPI data | Role-based access | Dashboard health |
| Evidence | Immutable references | Access controls | Retention |
| Credentials | Signed VC | Key protection | Verification SLO |

---

# 53. Architecture Quality Attributes

## Security

Primary concern. The architecture must prevent tenant escape, unauthorized tool use, credential compromise and AI-mediated data leakage.

## Availability

The platform should use independent failure domains and explicit dependency SLOs.

## Scalability

Scale independently:

- web.
- API.
- event consumers.
- OCR.
- agent workers.
- inference.
- vector retrieval.

## Portability

Containerized workloads, API abstractions and open protocols should permit deployment across approved sovereign environments.

## Maintainability

Modular domain boundaries reduce coordination cost and preserve the option to extract services later.

## Observability

Every meaningful operation must be traceable from user/request through domain state, events, agent actions and external tools.

## Cost Efficiency

AI compute and storage are treated as measurable resources rather than opaque infrastructure.

---

# 54. Key Architectural Decisions From the Review

## Decision 1 — Do not create a separate platform for i3 E³ and the collaboration stack

Use one platform foundation with distinct application/domain modules.

## Decision 2 — Keep the Work Graph as the ecosystem context layer

Do not replace it with a generic vector database.

## Decision 3 — Keep PostgreSQL as transactional authority

Do not use the graph as a replacement for transactional business state.

## Decision 4 — Keep agents behind a policy gateway

Do not allow agents to directly hold unrestricted credentials to Nextcloud, Zimbra, ERP, CRM or infrastructure.

## Decision 5 — Use hybrid Graph + Vector retrieval

Graph provides relationships and deterministic context; vector search provides semantic document retrieval.

## Decision 6 — Preserve modular-monolith economics

Do not create dozens of microservices for the initial team.

## Decision 7 — Separate stateful infrastructure from stateless AI/application services

This reduces blast radius and simplifies scaling.

## Decision 8 — Treat AI cost as a business metric

Every AI action should map to a tenant, workflow, model and outcome.

## Decision 9 — Treat sovereign deployment as a portability test

A feature that cannot run within the approved sovereign boundary should be explicitly classified as non-portable rather than silently depending on an external service.

---

# 55. Final Target State

```text
                           USERS / PARTNERS
                                  |
                         Web / PWA / Mobile
                                  |
                         CDN / DNS / WAF
                                  |
                           API Gateway
                                  |
              +-------------------+-------------------+
              |                                       |
        Identity Plane                          Policy Plane
       Keycloak / OIDC                        OPA / ABAC
              |                                       |
              +-------------------+-------------------+
                                  |
                         Application Plane
                                  |
       +------------------+-------+------------------+
       |                  |                          |
  Collaboration       i3 E³ Domain             Managed Services
 Nextcloud/Zimbra   Partner/Opportunity       Support/SOC/Billing
       |             Solution/Academy
       |                  |
       +------------------+--------------------------+
                                  |
                           Event Backbone
                              Kafka
                                  |
          +-----------------------+-----------------------+
          |                       |                       |
      Work Graph             Knowledge Plane          Analytics
          |                       |                       |
       Graph DB             Qdrant/OpenSearch       Lakehouse
          |                       |
          +-----------+-----------+
                      |
                Agent Control Plane
                      |
          +-----------+-----------+
          |           |           |
      LangGraph    MCP Broker   Model Gateway
          |                       |
      Agent Registry        vLLM / Ollama
          |                       |
          +-----------+-----------+
                      |
                 Tool Execution
                      |
       +--------------+---------------+
       |              |               |
   Nextcloud        Zimbra         ERP/CRM/LMS
       |              |               |
       +--------------+---------------+
                      |
                 Evidence Plane
                      |
             Audit / VC / Fabric
                      |
                 Operations
                      |
      OTel / Prometheus / OpenSearch / SIEM
                      |
                Backup / DR
                      |
             Ceph/S3 / Immutable
```

---

# 56. Immediate Engineering Actions

The architecture review should result in the following concrete actions.

## Within 5 Business Days

- Freeze architecture baseline.
- Establish ADR repository.
- Establish repository structure.
- Confirm OpenShift topology.
- Confirm Keycloak tenancy model.
- Define tenant isolation tests.
- Define event naming/versioning standard.
- Define initial Work Graph schema.
- Define agent manifest schema.
- Define API standards.
- Define data classification matrix.

## Within 10 Business Days

- Deploy development OpenShift environment.
- Deploy Keycloak.
- Establish CI/CD.
- Establish observability.
- Establish PostgreSQL.
- Establish event backbone.
- Implement tenant context.
- Implement Partner aggregate.
- Implement Opportunity aggregate.
- Implement first graph projection.

## Within 30 Days

- Partner Passport.
- Engineer Passport.
- Opportunity registration.
- Work Graph.
- API Gateway.
- Agent Registry.
- Match Agent.
- Nextcloud integration.
- Zimbra integration.
- document ingestion foundation.

## Within 60 Days

- Academy.
- Lab provisioning.
- RAG.
- Copilot.
- credential issuance pilot.
- Mission Control.
- customer portal foundations.

## Within 90–120 Days

- full MVP acceptance.
- performance testing.
- adversarial AI testing.
- DR rehearsal.
- launch rehearsal.
- controlled production cohort.

---

# 57. Source Alignment Notes

This document intentionally preserves the supplied terminology and architecture rather than replacing it with a generic cloud architecture.

The i3 E³ guide identifies the Work Graph, event-driven architecture, agentic runtime, trust/evidence plane, multi-tenancy, portability, PWA/offline requirements, cost attribution and progressive autonomy as binding architecture concerns.

The enterprise collaboration guide identifies Nextcloud, Zimbra, Keycloak, PostgreSQL, Redis, Ceph/S3, LangGraph, vLLM/Ollama and Qdrant as the primary enterprise platform stack, with zero-trust security, private RAG, workflow automation, DevSecOps, SOC, backup/DR and managed services.

Where the sources provide different implementation choices, this specification records a consolidation decision rather than silently assuming one source is incorrect.

---

# 58. Qualification and Implementation Disclaimer

This is an engineering implementation specification derived from the supplied architecture documents. It is not a vendor commitment, regulatory determination, security certification, commercial forecast or legal opinion.

Before production commitments:

- verify current IBM/Red Hat product capabilities, licensing and regional availability;
- confirm Skillsoft and certification-body licensing before ingestion;
- obtain DPO/legal review for Kenya data-protection obligations;
- validate the actual ROKS/Nairobi sovereign topology;
- validate capacity and SLOs through performance testing;
- validate backup and DR through restore exercises;
- validate AI agents through representative evaluation datasets.

---

# 59. Appendix A — Recommended Initial Technology Baseline

| Capability | Technology |
|---|---|
| Frontend | Next.js + React + TypeScript |
| PWA | Service Worker + IndexedDB |
| API | REST/OpenAPI |
| Domain Backend | Java 21 + Quarkus |
| AI Services | Python 3.12 + FastAPI |
| Identity | Keycloak |
| Policy | OPA |
| Transaction DB | PostgreSQL |
| Cache | Redis |
| Object Storage | Ceph/S3 |
| Work Graph | Apache AGE or Neo4j; ADR required |
| Vector | Qdrant |
| Search/Logs | OpenSearch |
| Event Streaming | Kafka/Redpanda; ADR required |
| Workflow Queue | RabbitMQ where justified |
| Agent Orchestration | LangGraph |
| Tool Protocol | MCP |
| Agent Delegation | A2A |
| Model Serving | vLLM/Ollama |
| OCR | PaddleOCR |
| PDF | pdfplumber + document parsers |
| Collaboration | Nextcloud |
| Mail | Zimbra |
| Credentials | W3C VC 2.0 |
| Trust Ledger | Hyperledger Fabric |
| Secrets | Vault/KMS/HSM |
| Container Platform | OpenShift |
| GitOps | Argo CD |
| CI | Tekton or equivalent |
| IaC | Terraform/OpenTofu + Ansible |
| Metrics | Prometheus |
| Dashboards | Grafana |
| Tracing | OpenTelemetry + Tempo/Jaeger |
| SIEM/SOC | Enterprise SIEM + EDR/XDR/SOAR |
| Backup | Immutable 3-2-1 architecture |

---

# 60. Appendix B — Initial API Resource Model

```text
Tenant
Organization
Person
Partner
Engineer
Skill
Certification
Opportunity
OpportunityRequirement
Solution
SolutionVersion
Project
Milestone
Evidence
Credential
Passport
Agent
AgentVersion
AgentEvaluation
Tool
ToolPermission
Workflow
WorkflowExecution
Document
DocumentVersion
KnowledgeChunk
Embedding
AuditEvent
UsageEvent
BillingAccount
SupportTicket
SecurityIncident
BackupJob
```

---

# 61. Appendix C — Initial Event Catalogue

```text
tenant.created
tenant.policy.updated

user.created
user.disabled
user.role.changed

partner.registered
partner.verified
partner.enabled
partner.activated

engineer.registered
engineer.skill.verified
engineer.availability.changed

opportunity.captured
opportunity.qualified
opportunity.registered
opportunity.matched
opportunity.proposed
opportunity.won
opportunity.lost
opportunity.delivered

solution.created
solution.version.published

lab.booked
lab.provisioned
lab.expired
lab.destroyed

document.uploaded
document.classified
document.parsed
document.embedded

credential.issuance.proposed
credential.issued
credential.revoked

agent.created
agent.evaluated
agent.promoted
agent.suspended
agent.invocation.requested
agent.invocation.completed
agent.action.requested
agent.action.approved
agent.action.rejected

workflow.started
workflow.completed
workflow.failed
workflow.approved
workflow.rejected

security.alert
security.incident.created
security.incident.resolved

usage.recorded
backup.completed
backup.failed
restore.completed
```

---

# 62. Appendix D — Engineering Definition of Success

The platform is technically successful when:

- partners can register and become discoverable;
- capabilities are represented in the Work Graph;
- opportunities can be registered and protected from duplicate registration;
- partners and engineers can be matched using deterministic requirements plus explainable AI assistance;
- solutions can be versioned and evidenced;
- labs can be provisioned and automatically destroyed;
- documents can be securely ingested and semantically searched;
- agents can execute controlled workflows without bypassing authorization;
- AI responses are grounded in permission-aware enterprise context;
- credentials can be independently verified;
- every consequential action is auditable;
- tenant boundaries remain intact under adversarial testing;
- platform operations are observable;
- backup restoration is proven;
- the same software can be deployed in the approved sovereign environment;
- AI cost is measurable against business outcomes.

---

## End State

**Connect → Build → Certify → Deploy → Operate → Evidence → Monetize**

The technical architecture should make that lifecycle executable through one governed platform rather than a collection of disconnected applications.

