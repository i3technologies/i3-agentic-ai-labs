# ADR-006: API Gateway Introduction (Kong)

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** Platform Security Lead, Engineering Manager  

---

## Context

Five services — admissions-agent, FORD API, talent API, PMaaS campaign agent, voice TTS — are
directly reachable without any authentication on their OpenShift Routes.  All five have
`allow_origins=["*"]` CORS headers.  The admissions-agent MCP connectors endpoint is fully
unauthenticated (audit finding H-2).  Rate limiting is absent at the platform edge, allowing
unconstrained LLM cost accrual per IP.

E³ guide L2 (Edge & Gateway layer) mandates a unified API gateway handling JWT validation,
rate limiting, and CORS scoping before requests reach any domain service.

---

## Decision

Deploy Kong (DB-less mode) in the `i3-gateway` namespace as the cluster API gateway.  
All external traffic routes through `https://api.i3technologies.co.ke/{service}/*`.  
JWT plugin validates tokens against Keycloak JWKS at
`http://keycloak.i3-auth.svc.cluster.local:8080/realms/i3/protocol/openid-connect/certs`.  
Rate-limit plugin uses Redis backend: 100 RPM default per tenant, 10 RPM for LLM endpoints.  
Direct OpenShift Routes for previously-exposed services are removed after a one-sprint cutover
validation window.  
Internal service-to-service calls continue to use cluster-internal DNS — they do NOT route
through the gateway.

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| IBM API Connect | Licensed cost on every call; configuration overhead for cluster-internal topology |
| OpenShift Route-level auth (mod_auth_openidc) | No rate limiting; no centralized audit; per-route configuration drift |
| Istio mTLS ingress | Operational complexity; certificate management overhead at Phase 2 maturity level |
| Per-service JWT middleware (keep current approach) | Duplicated code; inconsistent enforcement; admissions already missing it |

---

## Consequences

**Positive:**
- Single JWT enforcement point — adding a new service requires only a Kong Route definition,
  not per-service auth middleware.
- Per-tenant rate limiting at the gateway prevents LLM cost runaway without application changes.
- Removes `allow_origins=["*"]` CORS from all five services — gateway enforces
  origin allowlist centrally.
- Audit finding H-2 (unauthenticated admissions endpoint) is closed.

**Negative:**
- All external clients must present a valid Keycloak JWT — any integration partner using static
  API keys must be migrated to OAuth 2.0 client credentials flow.
- One-sprint parallel routing period (old routes + gateway) increases operational complexity
  transiently.

---

## Rollback Plan

If Kong deployment fails or JWT plugin blocks legitimate traffic:
1. Re-enable direct OpenShift Routes on affected services:
   `kubectl annotate route admissions-agent -n i3-admissions haproxy.router.openshift.io/disable-balance-algorithm-`
2. DNS cutover back to direct route CNAME — zero downtime.
3. Investigate Kong config; re-deploy with corrected JWKS URI.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-7 | `DEV_BYPASS_AUTH=true` is blocked at the gateway — no JWT = 401, regardless of service-side config |
| HC-4 | Kong forwards `X-Tenant-Id` claim from JWT to all upstream services |
| HC-5 | All agent endpoints require JWT — unauthenticated agent invocations are impossible |
| E³ L2 | Kong implements the Edge & Gateway layer of the 8-layer architecture |
| E³ P9 | Small surface — one entry point (`api.i3technologies.co.ke`) for all external traffic |

---

## Sensor Gate (P2-GATE-06)

```bash
kubectl get pod -n i3-gateway -l app=kong              # Running
# Unauthenticated → 401
curl -s -o /dev/null -w "%{http_code}" \
  https://api.i3technologies.co.ke/admissions/chat
# Expected: 401
# Authenticated → 200
curl -s -H "Authorization: Bearer $VALID_TOKEN" \
  https://api.i3technologies.co.ke/admissions/chat \
  -d '{"message":"what programmes do you offer"}'
# Expected: 200
# allow_origins wildcard removed
grep -rn 'allow_origins.*\*\|origins.*"\*"' \
  platform/admissions/ platform/ford/ platform/talent/ \
  platform/pmaas/ platform/voice/
# Expected: 0 matches
```
