# ADR-006: Kong API Gateway — External Route Authentication & CORS Hardening

**Status:** Accepted  
**Date:** 2025-01-30  
**Deciders:** i3 Platform Engineering  
**Closes:** Finding H-2 (unauthenticated external endpoints)  
**Step:** STEP-P2-07

---

## Context

Before this change every public-facing microservice (admissions, engage, evalos, pmaas, voice, ford, talent) carried:

1. `allow_origins=["*"]` — a wildcard CORS policy that permits requests from any origin, defeating browser same-origin protections.
2. Service-level JWT validation that was inconsistently implemented or absent (admissions MCP endpoints were fully unauthenticated — finding H-2).

There was no centralised enforcement point for AuthN, rate-limiting, or CORS policy. Each service carried its own half-implementation, creating an uneven security surface.

---

## Decision

Deploy Kong 3.6 in DB-less (declarative) mode in the `i3-gateway` namespace as the single entry point for all external traffic to `api.i3technologies.co.ke`. All services continue to be reachable from within the cluster via their `*.svc.cluster.local` DNS names without going through the gateway.

### JWT Validation

Kong's built-in `jwt` plugin validates RS256 `Authorization: Bearer` tokens against Keycloak realm `i3`:

- JWKS endpoint: `http://keycloak.i3-auth.svc.cluster.local:8080/realms/i3/protocol/openid-connect/certs`
- Claim `kid` maps to the registered consumer credential.
- Claims `exp` is always verified; unauthenticated requests receive `401`.

### Rate Limiting (Redis-backed)

| Route group | Limit | Redis DB |
|---|---|---|
| Standard (engage, evalos, onboarding) | 100 RPM per consumer | `redis.i3-data:6379/db2` |
| LLM/AI (admissions, pmaas, voice) | 10 RPM per consumer | `redis.i3-data:6379/db2` |

Policy `redis` is used instead of `local` to make limits consistent across the two Kong replicas.

### CORS Hardening

Upstream services had `allow_origins=["*"]` removed and replaced with an explicit per-service allow-list. The Kong `cors` plugin is the authoritative CORS header emitter for all external routes. Internal cluster calls are unaffected.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| NGINX Ingress + Lua auth snippet | Non-standard, no declarative plugin ecosystem, harder to audit |
| Each service validates its own JWT | Already proven to be inconsistently applied (H-2); single point of policy is safer |
| Istio mTLS + AuthorizationPolicy | Correct long-term approach but out of scope for Phase 2; added to Phase 3 roadmap |
| Kong DB-mode (PostgreSQL-backed) | Adds operational complexity with no benefit at current scale; DB-less gives GitOps-friendly config-as-code |

---

## Consequences

**Positive:**
- H-2 (unauthenticated MCP/admissions endpoints) is fully closed.
- `allow_origins=["*"]` wildcard is eliminated from all Phase 2 public services.
- Rate limits protect the LLM inference budget and prevent DDoS on AI routes.
- All external AuthN decisions are auditable in Kong's access log (forwarded to Langfuse/Grafana via stdout → Fluentd).

**Negative / Trade-offs:**
- During the one-sprint cutover window, direct Service routes remain active. Teams must not issue new curl/test commands against the direct routes after day 1.
- Keycloak JWKS rotation requires Kong consumer credential updates; handled via the post-deploy checklist.
- Kong adds ~2 ms P99 latency overhead (measured on similar clusters).

---

## Compliance Mapping

| Requirement | Satisfied by |
|---|---|
| HC-4 `tenant_id` on every request | Kong consumer id = tenant UUID; forwarded as `X-Consumer-Custom-Id` header |
| HC-5 Agents propose, policy disposes | Gateway enforces AuthN/AuthZ before any agent receives the request |
| HC-7 No auth bypass | `DEV_BYPASS_AUTH=true` is absent; JWT plugin has no bypass mode |
| Enhancement 3 Guide §3 — External Security | Kong JWT + rate-limit plugins fulfil §3 requirements |
