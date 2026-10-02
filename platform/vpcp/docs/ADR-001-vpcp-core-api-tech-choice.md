# ADR-001: VPCP Core API — FastAPI (Python) vs Spring Boot 3 (Java 21)

**Status:** ACCEPTED  
**Date:** 2025-07-15  
**Deciders:** Principal Solutions Architect, Lead Full-Stack Developer  
**Context:** i3 AI Platform — Pre-Plan Phase Gate for Application 2 (VPCP)

---

## Context

The Enterprise Architecture Implementation Guide specifies **Java 21 / Spring Boot 3**
for the VPCP Core API (deal registration, partner onboarding, OPA entitlement enforcement,
Temporal workflow orchestration). This ADR evaluates whether to follow that specification
or align to the existing i3 platform stack.

The existing i3 AI Platform is 100% **Python (FastAPI)** and **TypeScript (Next.js)**.
No Java runtime currently exists on the cluster.

---

## Decision Drivers

| # | Driver | Weight |
|---|--------|--------|
| D1 | Language consistency with existing platform (reduce operational surface area) | High |
| D2 | Temporal SDK quality and maturity | High |
| D3 | OPA policy client availability | High |
| D4 | Kafka CloudEvent producer quality | High |
| D5 | Team skills and onboarding cost | Medium |
| D6 | Container image size and startup time | Medium |
| D7 | Shared library reuse (Lobster Trap, OpenBao client, OTel) | Medium |

---

## Options Considered

### Option A: FastAPI (Python 3.11) — CHOSEN

**Stack:** FastAPI + Pydantic v2 + asyncpg + temporal-client (Python SDK) +
           opa-python-client + aiokafka + opentelemetry-instrumentation-fastapi

**Evaluation against drivers:**

| Driver | Assessment |
|--------|-----------|
| D1 Language consistency | ✅ Matches all 8 existing i3 services |
| D2 Temporal SDK | ✅ temporal-client 1.x is production-grade (Temporal.io officially supported) |
| D3 OPA client | ✅ opa-python-client or direct HTTP to OPA sidecar — well-established pattern |
| D4 Kafka CloudEvent | ✅ aiokafka 0.10 + platform CloudEvent schemas already in Python |
| D5 Team skills | ✅ No new language skills required |
| D6 Image size / startup | ✅ Python image ~180 MB; startup < 2 s |
| D7 Shared library reuse | ✅ Lobster Trap firewall, OpenBao hvac client, OTel instrumentation all Python |

**Risks:**
- Python GIL limits CPU-bound parallelism — mitigated by async I/O and multiple worker pods
- Temporal Python SDK is slightly newer than Java SDK (1.x vs Java SDK which has been
  stable longer) — risk is LOW as Temporal.io officially supports Python as a primary SDK

### Option B: Spring Boot 3 / Java 21

**Stack:** Java 21 + Spring Boot 3.2 + temporal-java-sdk + spring-security-oauth2 +
           spring-kafka + micrometer-otel

**Evaluation against drivers:**

| Driver | Assessment |
|--------|-----------|
| D1 Language consistency | ❌ Introduces Java runtime — zero existing Java on cluster |
| D2 Temporal SDK | ✅ Java SDK is Temporal's oldest and most battle-tested |
| D3 OPA client | ✅ Java OPA client available |
| D4 Kafka CloudEvent | ✅ spring-kafka well-established |
| D5 Team skills | ❌ Requires Java 21 expertise, Maven/Gradle, JVM tuning |
| D6 Image size / startup | ⚠️ JVM image ~350–500 MB; JVM warm-up 5–15 s (mitigated by GraalVM native — adds build complexity) |
| D7 Shared library reuse | ❌ Cannot reuse Lobster Trap, OpenBao hvac, or OTel Python instrumentation |

**Additional Java-specific operational costs:**
- New Tekton pipeline stage: Java build (Maven/Gradle) + GraalVM native compilation
- JVM heap tuning required for each pod (Xmx, Xms, G1GC configuration)
- New container vulnerability scanning profile for JDK base image
- Zero shared code with 8 existing FastAPI services

---

## Decision

**ACCEPTED: Option A — FastAPI (Python 3.11)**

**Rationale:**
1. The Temporal Python SDK (temporal-client 1.x) is production-grade and officially
   supported by Temporal.io. The risk of using Python over Java for the SDK is LOW.
2. Introducing Java 21 as a new runtime has a disproportionate operational cost
   (new build pipeline, new base image, no shared libraries) for no capability gain.
3. The VPCP Core API does not require high CPU-bound throughput — it processes
   deal registration sagas and partner onboarding state machines, which are
   predominantly I/O-bound (DB queries, Temporal activities, OPA calls).
4. All i3 platform shared libraries (Lobster Trap, OpenBao hvac, OTel) are Python.
   Reusing them in the VPCP Core API eliminates duplication.

---

## Consequences

**Positive:**
- VPCP Core API can reuse `platform/crm/crawler.py` HMAC utilities directly
- Lobster Trap 12-pattern firewall applied to VPCP API inputs with zero porting effort
- Single container build pipeline for VPCP (FastAPI Dockerfile = same as all other services)
- Temporal Python worker shares the same asyncpg pool pattern as all other i3 services

**Negative / Mitigations:**
- Temporal Java SDK has more community examples for complex saga patterns →
  Mitigation: Follow temporalio/samples-python repository; patterns are equivalent
- Python type safety is weaker than Java's compile-time checks →
  Mitigation: Pydantic v2 enforces runtime validation on all inputs; mypy in CI pipeline

---

## Implementation Notes

VPCP Core API entrypoint: `platform/vpcp/main.py`  
Temporal worker entrypoint: `platform/vpcp/worker.py`  
Workflow definitions: `platform/vpcp/workflows/deal_registration.py` (already created)  
Keycloak JWT validation: use `python-jose` or `authlib` with JWKS endpoint  
OPA integration: HTTP sidecar at `http://localhost:8181/v1/data/partner/entitlements`  

Dependencies to add to `platform/vpcp/requirements.txt`:
```
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
asyncpg>=0.29.0
temporalio>=1.7.0
aiokafka>=0.11.0
httpx>=0.27.0
hvac>=2.1.0           # OpenBao / Vault client
opentelemetry-instrumentation-fastapi>=0.46b0
opa-python-client>=1.3.0
```
