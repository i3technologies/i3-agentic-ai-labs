Scaffold a new bounded-context FastAPI microservice using the extract-domain-service skill.

Ask the user for the following details if not already provided:
1. Service name (e.g. consent-service, credential-service, grading-service)
2. Kubernetes namespace (e.g. i3-consent, i3-grading)
3. Primary domain entity name (e.g. Consent, Credential, GradeRecord)

Then activate the extract-domain-service skill and create:
- platform/<service-name>/main.py       — FastAPI app with asyncpg lifespan pool, /healthz, /readyz
- platform/<service-name>/models.py     — Pydantic request/response models
- platform/<service-name>/schemas.sql   — Postgres DDL with UUIDv7 PK, tenant_id UUID NOT NULL, RLS policy
- platform/<service-name>/Dockerfile    — Multi-stage, non-root, no hardcoded secrets

Ensure all files comply with HC-4 (tenant_id), HC-5 (no direct DB from agent), and the asyncpg
pooling standard from 02-architecture-standards.md.
Register the service in platform/namespaces/namespaces.yaml and note the ArgoCD Wave 2 entry required.
