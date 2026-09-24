---
name: extract-domain-service
description: Scaffolds a new bounded-context FastAPI service adhering to DDD, OpenBao injection, and CloudEvent standards.
---

When creating a new domain microservice:
1. Establish standard directory layout under `platform/<service-name>/`:
   - `main.py` (FastAPI app, lifespan asyncpg pool, health/ready probes)
   - `models.py` (Pydantic schemas with strict regex and length constraints)
   - `schemas.sql` (Postgres DDL with UUIDv7 PK, tenant_id UUID NOT NULL, and RLS policies)
   - `Dockerfile` (multi-stage unprivileged non-root container)
2. Ensure database pooling:
   - Wire `asyncpg.create_pool` into application lifespan.
   - Inject DB credentials via `DATABASE_URL` sourced from OpenBao.
3. Apply Row-Level Security:
   - Include `ALTER TABLE <name> ENABLE ROW LEVEL SECURITY;`
   - Include `CREATE POLICY tenant_isolation ON <name> USING (tenant_id = current_setting('app.tenant_id')::UUID);`
4. Register the service in `platform/namespaces/namespaces.yaml` and add an ArgoCD Application manifest in Wave 2.