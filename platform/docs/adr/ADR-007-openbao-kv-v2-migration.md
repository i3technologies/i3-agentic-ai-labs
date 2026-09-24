# ADR-007: OpenBao KV v2 Migration — Replace Kubernetes Secrets for All Application Secrets

**Status:** Proposed  
**Date:** 2026-09-22  
**Deciders:** i3 Platform Engineering Lead, Security Lead, Platform SRE  
**Relates to:** EXPLORE-GATE §4 (SEC-05), §9, §12 (R-06), §13 Track F  
**Supersedes:** — (no prior ADR; K8s Secrets were used as an interim mechanism)

---

## Context

### Problem Statement

The i3 AI Platform operates an OpenBao (open-source HashiCorp Vault fork) cluster in the
`i3-security` namespace — 3-pod StatefulSet, initialized and unsealed (EXPLORE-GATE §9 ✅).

However, EXPLORE-GATE §4 (SEC-05, Severity: Medium) found:

> **OpenBao initialized but root token not persisted — application secrets in K8s Secrets,
> not OpenBao KV.**

And EXPLORE-GATE §12 (R-06, Likelihood: High / Impact: Medium):

> **OpenBao not used for secret injection — K8s Secrets as fallback.**

The current state means:
1. Application secrets (DB passwords, API keys, HMAC secrets) are stored as Kubernetes Secrets
   in `etcd`. On IBM Cloud OpenShift, etcd is encrypted at rest (IBM KMS), but:
   - Any user with `get secret` RBAC can read secrets in plaintext.
   - Secrets are scoped to a namespace, not to a specific service account.
   - There is no secret versioning, rotation history, or access audit log.
   - There is no TTL or lease on secrets — once issued, they are valid indefinitely.
2. `REPLACE_FROM_VAULT` placeholders in `admissions-secrets` (SEC-04) indicate that OpenBao
   injection was planned but never completed — 7 environment variables are missing from the
   admissions agent.
3. `VOICE_API_KEY` was hardcoded in `platform/voice/voice-deploy.yaml:63` (SEC-03) — a symptom
   of no enforced secret injection workflow.
4. Secret rotation requires manual `kubectl create secret --from-literal` commands, with no
   audit trail and no automated rotation.

### OpenBao Capabilities Available

The OpenBao cluster is confirmed running at `https://openbao.i3-security.svc.cluster.local:8200`.
The following paths are confirmed populated (from Phase 1 rotation work):

```
i3/mariadb/root          → { password: <rotated> }
i3/erpnext/admin         → { password: <rotated> }
i3/keycloak/admin        → { password: <rotated> }
i3/litellm/api-key       → { key: <rotated> }
i3/pmaas/db-url          → { url: "postgresql://pmaas:<rotated>@..." }
i3/ford/hmac-secret      → { secret: <256-bit hex> }
i3/brevo/api-key         → { key: <rotated — EXPLORE-GATE §15> }
```

The remaining secrets currently in Kubernetes Secrets that are **not yet in OpenBao** are the
target of this migration.

---

## Decision

**Migrate all application secrets from Kubernetes Secrets to OpenBao KV v2 and inject them
into pods at startup using the OpenBao Agent Injector (Kubernetes admission webhook mutating
controller).**

### Migration Scope

| Secret Name (K8s) | Namespace | Fields | OpenBao KV v2 Path |
|------------------|-----------|---------|--------------------|
| `admissions-secrets` | i3-admissions | 7 env vars (REPLACE_FROM_VAULT) | `i3/admissions/*` |
| `engage-secrets` | i3-engage | BREVO_API_KEY, DB_URL | `i3/engage/*` |
| `pmaas-secrets` | i3-pmaas | DB_URL, BREVO_API_KEY | `i3/pmaas/*` (partially done) |
| `evalos-secrets` | i3-evalos | DB_URL, PG_CA_CERT_PATH | `i3/evalos/*` |
| `ford-secrets` | i3-ford | MEMBER_HMAC_SECRET, DB_URL | `i3/ford/*` (hmac done) |
| `voice-secrets` | i3-voice | VOICE_API_KEY | `i3/voice/*` |
| `onboarding-secrets` | i3-onboarding | KEYCLOAK_SECRET, DB_URL | `i3/onboarding/*` |
| `consent-secrets` | i3-consent | DB_URL, REDIS_URL | `i3/consent/*` |
| `agent-registry-secrets` | i3-agent-mesh | DB_URL | `i3/agent-mesh/*` |
| `mcp-gateway-secrets` | i3-agent-mesh | DB_URL | `i3/agent-mesh/*` |

### OpenBao KV v2 Path Schema (Normative)

```
i3/
  admissions/
    db-url            → { url: "postgresql://..." }
    chroma-url        → { url: "http://chromadb:8000" }
    keycloak-issuer   → { url: "https://keycloak.i3-auth.svc..." }
    litellm-api-key   → { key: "sk-litellm-..." }
    redis-url         → { url: "redis://..." }
    otel-endpoint     → { url: "http://otel-collector:4317" }
    hmac-secret       → { secret: "<256-bit hex>" }  # same as ford/hmac-secret
  engage/
    db-url            → { url: "postgresql://engage:..." }
    brevo-api-key     → { key: "xkeysib-..." }       # rotated in EXPLORE §15
    hmac-secret       → { secret: "<256-bit hex>" }  # same MEMBER_HMAC_SECRET
    redis-url         → { url: "redis://..." }
  pmaas/
    db-url            → { url: "postgresql://pmaas:..." }
    brevo-api-key     → { key: "xkeysib-..." }
  evalos/
    db-url            → { url: "postgresql://evalos:..." }
    pg-ca-cert        → { cert: "<PEM certificate>" }
  ford/
    hmac-secret       → { secret: "<256-bit hex>" }
    db-url            → { url: "postgresql://ford:..." }
  voice/
    api-key           → { key: "<voice API key>" }
  onboarding/
    keycloak-secret   → { secret: "..." }
    db-url            → { url: "postgresql://onboarding:..." }
  consent/
    db-url            → { url: "postgresql://consent:..." }
    redis-url         → { url: "redis://..." }
  agent-mesh/
    db-url            → { url: "postgresql://agent-mesh:..." }
    registry-token    → { token: "<internal registry API token>" }
  redis/
    url               → { url: "redis://:password@redis.i3-data.svc:6379/0" }
    password          → { password: "..." }
```

### Injection Method: OpenBao Agent Injector

The OpenBao Agent Injector (admission webhook) runs in `i3-security` namespace and mutates
pod specs to add a sidecar agent that fetches secrets from OpenBao and writes them to a shared
`tmpfs` volume. The application reads secrets from files rather than environment variables.

**Pod annotation pattern (added to each Deployment):**

```yaml
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "admissions-app"   # Kubernetes auth role
        vault.hashicorp.com/agent-inject-secret-config: "i3/admissions/db-url"
        vault.hashicorp.com/agent-inject-template-config: |
          {{- with secret "i3/admissions/db-url" -}}
          export ADMISSIONS_DB_URL="{{ .Data.data.url }}"
          {{- end }}
```

**Alternative: environment variable injection via Vault Agent template**

For services that use `os.environ` (Python) or `process.env` (Node.js), the agent writes
a shell script to `/vault/secrets/env` which is sourced at container startup via the `command`
entrypoint:

```yaml
command: ["/bin/sh", "-c", "source /vault/secrets/env && exec python main.py"]
```

### Kubernetes Auth Role Per Service

Each service authenticates to OpenBao using the Kubernetes Service Account JWT:

```
Role: admissions-app
  Bound SA: admissions-agent-sa (i3-admissions namespace)
  Policies: admissions-read-policy  # read-only on i3/admissions/* paths

Role: engage-app
  Bound SA: engage-web-sa (i3-engage namespace)
  Policies: engage-read-policy      # read-only on i3/engage/*

# ... one role per service
```

Each policy is **read-only** and **path-scoped**. No service account can read another
service's secrets or write to any KV path.

### Kubernetes Secrets Retirement

After all services are migrated and confirmed healthy:
1. Kubernetes Secrets are annotated with `i3/openbao-migrated: "true"`.
2. After a 2-sprint deprecation window, Kubernetes Secrets are deleted.
3. RBAC `get secret` permission is removed from all non-operator service accounts.

---

## Alternatives Considered

### A1 — Keep Kubernetes Secrets with etcd encryption only
**Rejected.** Kubernetes RBAC for secrets is coarse-grained — anyone with `get secret` in the
namespace can read all secrets. No audit log. No rotation history. SEC-05 explicitly requires
migration to OpenBao per platform standards.

### A2 — Use IBM Cloud Secrets Manager (external SaaS)
**Rejected.** Introduces external SaaS dependency and potential data residency concern. OpenBao
is already deployed and unsealed in-cluster. The cost and complexity of external Secrets Manager
is not justified when OpenBao is available.

### A3 — Use sealed-secrets (Bitnami)
**Rejected.** Sealed-secrets encrypts K8s Secrets for git storage — it does not provide access
audit, rotation workflows, dynamic secret generation, or lease-based TTL. It is a git-level
control, not an operational secret management system.

### A4 — Use environment variables injected by ArgoCD ApplicationSet generators
**Rejected.** ArgoCD ApplicationSet generators produce K8s Secrets (same problem as A1) or
require a secrets-plugin (adds ArgoCD Vault Plugin dependency). The OpenBao Agent Injector
is the canonical injection mechanism already available on cluster.

### A5 — Migrate only the high-severity secrets (admissions, FORD) in Phase 2
**Partially accepted as phasing.** The migration is ordered by severity:
- Priority 1: `admissions-secrets` (7 REPLACE_FROM_VAULT), `voice-secrets` (SEC-03, hardcoded)
- Priority 2: All remaining services listed in the scope table
- Phase 3: K8s Secret deletion and RBAC cleanup

---

## Technical Drivers

| Driver | Detail |
|--------|--------|
| HC-6 compliance | `MEMBER_HMAC_SECRET` must be in OpenBao (not K8s Secret) per HC-6 wording |
| Audit trail | OpenBao KV v2 provides read audit log — every secret access is logged |
| Rotation workflow | OpenBao KV v2 maintains secret versions; `kv put` creates a new version; rollback via `kv rollback` |
| Lease TTL | Future: dynamic secrets with TTL-based rotation (Phase 4) |
| RBAC precision | Per-path, per-service-account access policies — least-privilege enforcement |

---

## Security Implications

| # | Implication |
|---|------------|
| SEC-1 | OpenBao audit log must be enabled before migration. Each secret read is logged with service account, path, and timestamp. Log output: Prometheus Pushgateway + stdout for Fluentd collection. |
| SEC-2 | The OpenBao root token must be sealed after migration setup and stored in physical offline custody — not in a K8s Secret. |
| SEC-3 | Service accounts are granted `read` on specific paths only. No service can enumerate all paths or read other services' secrets. |
| SEC-4 | The OpenBao Agent Injector writes secrets to `tmpfs` (in-memory filesystem, not persisted to disk). Secrets are not visible in pod environment variables via `kubectl exec env`. |
| SEC-5 | Network policy: only pods in `i3-security` namespace can reach OpenBao on port 8200. All other pod → OpenBao communication is via the injected sidecar (which runs in the same pod network namespace). |
| SEC-6 | Secret version retention: KV v2 retains last 5 versions per path. `vault kv metadata` shows full version history. |

---

## Multi-Tenancy Implications

- OpenBao KV paths are **not tenant-partitioned** at this stage. All tenants of a service share
  the same DB connection URL and HMAC secret (single-tenancy at the infrastructure level).
- Phase 4 deferred: per-tenant dynamic database credentials (OpenBao database secrets engine)
  would create a DB user per tenant per lease — true tenant-level credential isolation.
- `tenant_id` is a runtime concept (JWT claim) — it is not part of the secret injection path.

---

## Agent-Autonomy Implications

- HC-5: The MCP gateway will read its own secrets from OpenBao paths. Agent tool calls that
  require credentials (e.g., `brevo.send` needing the Brevo API key) must receive those
  credentials through the gateway — agents never hold API keys directly.
- HC-3: No autonomy tier change.

---

## Data Implications

### Secret Metadata Schema in OpenBao KV v2

Every secret path includes custom metadata:

```
vault kv metadata put \
  -custom-metadata=owner="i3-technologies/platform-sre" \
  -custom-metadata=service="engage-web" \
  -custom-metadata=rotated_at="2026-09-22" \
  -custom-metadata=rotation_period="90d" \
  i3/engage/brevo-api-key
```

This metadata is used by the rotation skill (`rotate-secrets`) to determine which secrets are
due for rotation.

---

## Event Implications

No Kafka events are produced by this change. Secret access is audited via OpenBao audit log.

Phase 3 deferred: emit `com.i3.security.secret.rotated` CloudEvent to a `security-events` topic
when a secret is rotated, for downstream SIEM integration.

---

## Operational Implications

| Concern | Mitigation |
|---------|-----------|
| OpenBao injector admission webhook failure | If OpenBao Agent Injector is down, pod mutations fail — new pods will not start. This is intentional fail-closed behaviour. OpenBao HA (3-pod) ensures < 30s recovery. |
| Pod restart during secret rotation | After `vault kv put` rotates a secret, pods must be restarted to pick up the new version. Rolling restart via `kubectl rollout restart deployment/<name>` is the standard procedure. |
| AppRole vs Kubernetes auth | This ADR uses Kubernetes auth (SA JWT). AppRole is an alternative for CI/CD pipelines (Tekton). Both are supported by OpenBao. |
| admissions REPLACE_FROM_VAULT | The 7 placeholder values (SEC-04) must be populated in OpenBao before the admissions-agent deployment is triggered. Deployment gate: pod readiness check fails if env vars are missing. |

---

## Performance Implications

- OpenBao Agent sidecar: starts in ~2s, fetches secrets, writes to `/vault/secrets/`. Pod startup
  time increases by ~2-3 seconds. Acceptable for services with standard Kubernetes readiness probes.
- Runtime secret access: secrets are read once at pod start and cached in tmpfs. No per-request
  OpenBao calls. Zero latency impact on request path.

---

## Cost Implications

- OpenBao: already running (3 pods, StatefulSet with existing PVC). No additional cost.
- Developer effort: one-time per-service pod annotation update + policy creation.
- Estimated 2-3 sprint effort total across all services.

---

## Rollback Strategy

1. **Per-service rollback**: If a service fails after OpenBao injection, revert the pod
   annotation to remove `vault.hashicorp.com/agent-inject: "true"` and restore the K8s Secret
   reference. The K8s Secret is preserved during Phase 2 for exactly this purpose.
2. **Migration phasing**: Services are migrated one at a time. A failed migration for one
   service does not affect others.
3. **OpenBao outage**: If OpenBao is completely unavailable (all 3 pods down), pods with
   the injector annotation will fail to start. The K8s Secret fallback is the recovery path
   during Phase 2. In Phase 3, after K8s Secrets are deleted, the recovery path is restoring
   OpenBao from raft snapshot.

---

## HC-1 through HC-8 Mapping

| Constraint | Mapping |
|-----------|---------|
| HC-1 | No change to solution-01 through solution-08 namespaces. |
| HC-2 | FORD `MEMBER_HMAC_SECRET` is already in OpenBao (`i3/ford/hmac-secret`). This ADR ensures it stays there and is injected correctly into the FORD API pod. |
| HC-3 | Agents never hold API keys directly — only the MCP gateway holds tool credentials. OpenBao injection supports this separation. |
| HC-4 | Not directly applicable to secret storage. |
| HC-5 | MCP gateway retrieves tool credentials from OpenBao paths. Agent manifests (ADR-002) list tools; gateway policy maps tools to credential paths. |
| HC-6 | **MEMBER_HMAC_SECRET must live in OpenBao** — not in a K8s Secret or env var literal. This ADR makes that binding enforcement the default. |
| HC-7 | `DEV_BYPASS_AUTH=true` must not appear in any secret path value or injected env. OpenBao audit log would reveal any such injection. |
| HC-8 | Fabric MSP private keys (future Phase 3) will also be injected from OpenBao `i3/ford/fabric-*` paths — same pattern established here. |

---

## Compliance / Statutory Mapping

| Requirement | How This ADR Satisfies It |
|------------|--------------------------|
| Kenya DPA 2019 §29 — security of processing | Secret management in a dedicated secrets vault with audit logging satisfies technical security measures |
| Kenya DPA 2019 §61 — ODPC penalties | OpenBao audit trail demonstrates due diligence in credential management |
| ISO 27001 A.9.2 — access provisioning | Per-service-account, per-path KV policies implement least-privilege access to credentials |
| ISO 27001 A.12.4 — logging and monitoring | OpenBao audit log captures every secret read with timestamp, SA, and path |
| IEBC Act Cap. 7A — voter data security | FORD HMAC secret in OpenBao (not K8s Secret) provides stronger key custody for voter token derivation |
| IBM Cloud FSS (Financial Services Standard) | OpenBao KV v2 satisfies IBM Cloud FS validated secrets management requirement for production workloads |

---

## Acceptance Criteria

```
AC-1:  vault kv get i3/admissions/db-url → secret found (not REPLACE_FROM_VAULT placeholder)
AC-2:  All 7 admissions-secrets env vars populated from OpenBao (pod starts cleanly, no "env var missing" errors)
AC-3:  kubectl get secret voice-secrets -n i3-voice → NotFound (K8s Secret deleted post-migration)
       OR still present but with annotation i3/openbao-migrated: "true" during deprecation window
AC-4:  kubectl exec -n i3-admissions admissions-agent-* -- env | grep DB_URL → not present (secrets in /vault/secrets/, not env)
AC-5:  kubectl exec -n i3-admissions admissions-agent-* -- cat /vault/secrets/env | grep DB_URL → value present
AC-6:  vault audit list → audit backend enabled
AC-7:  vault kv metadata get i3/engage/brevo-api-key → rotated_at metadata present
AC-8:  MEMBER_HMAC_SECRET in OpenBao i3/engage/hmac-secret matches i3/ford/hmac-secret (same value — cross-service join key)
AC-9:  vault policy read admissions-read-policy → only lists read on i3/admissions/* (not engage or ford paths)
AC-10: Admissions agent pod restarts cleanly and passes readiness probe after OpenBao injection
AC-11: No K8s Secret contains a literal value for MEMBER_HMAC_SECRET (grep across cluster secrets)
AC-12: P2-GATE: rotate-secrets skill run completes with 0 errors after migration
```

---

*Author: Bob (IBM Bob AI software engineer) | i3 AI Platform | 2026-09-22*  
*Do not implement until this ADR is reviewed and status changed to **Accepted** by Deciders.*
