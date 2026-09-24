# PLN-05 — Atomic Step Execution Plan
## 9-Step Sequential Task List for i3 Platform Phase 1/2 Remediation

**Version:** 1.0  
**Author:** Engineering Manager (Bob i3-mesh-architect)  
**HC-1 Status:** `solution-01`–`solution-08` have been **fully migrated off this cluster**. Constraint is retired on this server — documented for audit traceability only. No tasks in this plan touch those namespaces.

---

## Pre-flight Checklist

Before executing any step, verify:

```bash
# 1. OpenBao is unsealed
vault status | grep -E "^Sealed.*false"
# 2. kubectl context points to i3 cluster (NOT legacy cluster)
kubectl config current-context
# 3. ArgoCD is healthy
kubectl get pods -n i3-gitops | grep argocd-server | grep Running
```

---

## Step Index

| Step | ID | Title | Status |
|------|----|-------|--------|
| 1 | A-1 / R-01 | Remove HC-7 `DEV_BYPASS_AUTH` guard | ✅ DONE |
| 2 | A-2 / SEC-01 | Rotate Brevo key in engage/pmaas secrets | ✅ DONE |
| 3 | A-3 / SEC-03 | Scrub `VOICE_API_KEY` literal from voice-deploy.yaml | ✅ DONE (confirmed) |
| 4 | A-4 / SEC-04 | Populate 7 `REPLACE_FROM_VAULT` entries in admissions-secrets | ⏳ PENDING |
| 5 | A-5 / SEC-06 | Fix `KEYCLOAK_ISSUER` in admissions-deploy.yaml | ⏳ PENDING |
| 6 | B-1 | Deploy Consent Service to `i3-consent` namespace | ⏳ PENDING |
| 7 | D-3 / SEC-07 | Enforce HMAC on `subject_id_hash` in campaigns/send | ⏳ PENDING |
| 8 | F-1 / R-08 | Rebuild admissions-agent image with `chromadb==0.4.24` | ✅ DONE (pinned) |
| 9 | F-2 / U-05 | Add `i3-onboarding` to namespaces.yaml | ⏳ PENDING |

---

## STEP-PLN05-01 — Remove HC-7 `DEV_BYPASS_AUTH` Guard

**Objective:** Eliminate the `DEV_BYPASS_AUTH=true` escape hatch from `keycloak-auth.ts` so production authentication cannot be bypassed by an environment variable.

**Status:** ✅ DONE — Confirmed resolved in EXPLORE-GATE §15.

**Pre-requisites:** None.

**Affected Files:**
- `onboarding-agent/src/security/keycloak-auth.ts` — **Modified** (bypass removed)

**Task List:**
1. Open `keycloak-auth.ts` and delete the `if (process.env.DEV_BYPASS_AUTH === 'true')` branch and all its body.
2. Remove `DEV_BYPASS_AUTH` from any `.env.example` or sample config files.
3. Confirm `.gitignore` covers `.env` and `.env.local`.

**Risk & Rollback:**
- Risk: Low. Removing a bypass tightens security with no functional change in production (where bypass was never set).
- Rollback: Revert commit. In production, bypass was never active so rollback is moot.

**Sensor Checks:**
```bash
# Must return 0 matches
grep -r "DEV_BYPASS_AUTH" onboarding-agent/src/
# Must pass
npm test --prefix onboarding-agent
```

---

## STEP-PLN05-02 — Rotate Brevo Key in `engage-secrets` + `pmaas-secrets`

**Objective:** Ensure Brevo API keys in both the Engage and PMaaS Kubernetes secrets are replaced with freshly-rotated values sourced from OpenBao, invalidating any previously-exposed key material.

**Status:** ✅ DONE — Confirmed in EXPLORE-GATE §15.

**Pre-requisites:** OpenBao unsealed; `vault` CLI authenticated with `i3/engage` and `i3/pmaas` policy.

**Affected Files:**
- `platform/engage/engage-deploy.yaml` — **Modified** (secretKeyRef updated)
- `platform/pmaas/pmaas-deploy.yaml` — **Modified** (secretKeyRef updated)

**Task List:**
1. Generate new Brevo API key in Brevo dashboard → revoke old key.
2. `vault kv put i3/engage/brevo api-key=<new>`.
3. `vault kv put i3/pmaas/brevo api-key=<new>`.
4. Patch both Kubernetes secrets: `kubectl create secret generic engage-secrets --from-literal=BREVO_API_KEY=<new> -n i3-engage --dry-run=client -o yaml | kubectl apply -f -`.
5. Rollout restart both deployments.

**Risk & Rollback:**
- Risk: Low. Old key is revoked, so rollback requires re-rotation to a third key.
- Rollback: Re-generate in Brevo, re-run steps 2–5 with the replacement key.

**Sensor Checks:**
```bash
# Old key must be revoked — HTTP 401 expected
curl -s -o /dev/null -w "%{http_code}" \
  -H "api-key: $OLD_BREVO_KEY" https://api.brevo.com/v3/account
# OpenBao path must exist
vault kv get i3/engage/brevo
vault kv get i3/pmaas/brevo
```

---

## STEP-PLN05-03 — Scrub `VOICE_API_KEY` Literal from `voice-deploy.yaml`

**Objective:** Confirm no plaintext `VOICE_API_KEY` value exists in `platform/voice/voice-deploy.yaml`; all injection must go through the OpenBao agent sidecar.

**Status:** ✅ DONE — Audit confirms lines 94–95 carry only a comment documenting the OpenBao path; no literal value present.

**Pre-requisites:** OpenBao path `i3/voice/api-key` must be seeded.

**Affected Files:**
- `platform/voice/voice-deploy.yaml` — **Modified** (literal scrubbed; comment confirming OpenBao path already present)

**Task List:**
1. Verify: `grep -n "VOICE_API_KEY" platform/voice/voice-deploy.yaml` — must return only the comment lines (94–95).
2. Confirm OpenBao path: `vault kv get i3/voice/api-key`.
3. Confirm deployment reads from secret: `kubectl get deploy voice-tts -n i3-voice -o jsonpath='{.spec.template.spec.containers[0].env}' | jq '.[] | select(.name=="VOICE_API_KEY")'`.

**Risk & Rollback:**
- Risk: None (already done).
- Rollback: Not applicable.

**Sensor Checks:**
```bash
# Must return 0 literal value lines (only comment lines allowed)
grep -c "VOICE_API_KEY:" platform/voice/voice-deploy.yaml
# Expected output: 0
grep "VOICE_API_KEY" platform/voice/voice-deploy.yaml | grep -v "^#"
```

---

## STEP-PLN05-04 — Populate 7 `REPLACE_FROM_VAULT` Entries in `admissions-secrets`

**Objective:** Replace every `REPLACE_FROM_VAULT` placeholder in `admissions-secrets` with real values sourced from OpenBao KV v2, so the admissions-agent deployment is fully operational.

**Status:** ⏳ PENDING

**Pre-requisites:**
- STEP-PLN05-01 ✅ (auth is enforced before secrets matter)
- OpenBao unsealed; `admissions` policy bound to `admissions-agent` service account
- Odoo instance running; Google Calendar OAuth credentials provisioned; n8n webhook URL confirmed

**Affected Files:**
- `platform/admissions/admissions-deploy.yaml` — lines 233–239 — **Modified** (placeholders removed; values sourced via `secretKeyRef` / OpenBao agent)

**Task List:**
1. Seed all 7 secrets in OpenBao:
   ```bash
   vault kv put i3/admissions/litellm      key="<virtual-key>"
   vault kv put i3/admissions/odoo         url="https://odoo.i3technologies.co.ke" \
                                           db="i3_prod" \
                                           username="api_user" \
                                           password="<rotated>"
   vault kv put i3/admissions/google-cal   credentials='<JSON blob>'
   vault kv put i3/admissions/n8n          webhook_url="https://n8n.i3technologies.co.ke/webhook/admissions"
   ```
2. Update `admissions-secrets` in `admissions-deploy.yaml` — replace `stringData` literal section with OpenBao agent template annotations (already present at lines 180–181). Remove the `stringData` block entirely so the agent sidecar writes the file.
3. Apply: `kubectl apply -f platform/admissions/admissions-deploy.yaml -n i3-admissions`.
4. Confirm agent sidecar injects secrets: `kubectl exec -it deploy/admissions-agent -n i3-admissions -- cat /vault/secrets/admissions-secrets`.
5. Rollout restart: `kubectl rollout restart deploy/admissions-agent -n i3-admissions`.

**Risk & Rollback:**
- Risk: Medium. If OpenBao path names don't match agent template, pod will fail to start.
- Rollback: Re-apply with `stringData` placeholders restored; restart.

**Sensor Checks:**
```bash
# No REPLACE_FROM_VAULT must remain in any applied manifest
grep "REPLACE_FROM_VAULT" platform/admissions/admissions-deploy.yaml
# Expected: 0 matches

# Pod must be Running
kubectl get pods -n i3-admissions -l app=admissions-agent

# Secrets injected
kubectl exec deploy/admissions-agent -n i3-admissions -- \
  sh -c 'test -s /vault/secrets/admissions-secrets && echo PASS || echo FAIL'
```

---

## STEP-PLN05-05 — Fix `KEYCLOAK_ISSUER` in `admissions-deploy.yaml`

**Objective:** Ensure the `KEYCLOAK_ISSUER` environment variable in the admissions-agent deployment points to the correct Keycloak realm URL, so JWT validation succeeds in all environments.

**Status:** ⏳ PENDING

**Pre-requisites:**
- STEP-PLN05-04 ✅ (secrets must be populated before auth is testable)
- Keycloak running in `i3-auth` namespace; realm `i3` exists

**Affected Files:**
- `platform/admissions/admissions-deploy.yaml` — **Modified** (add or correct `KEYCLOAK_ISSUER` env var)

**Task List:**
1. Confirm the Keycloak issuer URL: `curl https://auth.i3technologies.co.ke/realms/i3/.well-known/openid-configuration | jq .issuer`.
2. If `KEYCLOAK_ISSUER` env var is absent from the Deployment, add it under `.spec.template.spec.containers[0].env`:
   ```yaml
   - name: KEYCLOAK_ISSUER
     value: "https://auth.i3technologies.co.ke/realms/i3"
   ```
3. If it exists with a wrong value (e.g. `localhost`, `http://`, or wrong realm), correct it.
4. Apply: `kubectl apply -f platform/admissions/admissions-deploy.yaml -n i3-admissions`.
5. Verify the admissions-agent accepts a valid JWT: `curl -H "Authorization: Bearer <token>" https://admissions.i3technologies.co.ke/healthz`.

**Risk & Rollback:**
- Risk: Low. Wrong issuer causes 401 on all chat endpoints; rollback is trivial.
- Rollback: Revert the env var value and re-apply.

**Sensor Checks:**
```bash
# Issuer must be the HTTPS realm URL, not localhost
grep "KEYCLOAK_ISSUER" platform/admissions/admissions-deploy.yaml | grep -v "localhost"

# Healthz must return 200
curl -s -o /dev/null -w "%{http_code}" https://admissions.i3technologies.co.ke/healthz
# Expected: 200

# JWT-authenticated endpoint must return 200 (not 401)
TOKEN=$(vault kv get -field=token i3/test/admissions-jwt)
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  https://admissions.i3technologies.co.ke/api/chat
# Expected: 200
```

---

## STEP-PLN05-06 — Deploy Consent Service to `i3-consent` Namespace

**Objective:** Deploy the `consent-service` FastAPI microservice into the already-provisioned `i3-consent` namespace so that downstream services (Engage `send/route.ts`, etc.) can perform real consent checks via the circuit-breaker client.

**Status:** ⏳ PENDING

**Pre-requisites:**
- `i3-consent` namespace exists in `platform/namespaces/namespaces.yaml` ✅ (already provisioned, line 89)
- PostgreSQL `i3-data` database has `consent_records` table with `tenant_id UUID NOT NULL` (HC-4)
- OpenBao path `i3/consent/db-url` seeded
- Activate skill `extract-domain-service` before scaffolding

**Affected Files — Created:**
- `platform/consent-service/` — new directory
- `platform/consent-service/consent_service.py` — **Created** (FastAPI app)
- `platform/consent-service/requirements.txt` — **Created**
- `platform/consent-service/Dockerfile` — **Created**
- `platform/consent-service/consent-deploy.yaml` — **Created** (Deployment + Service + Route + Secret)

**Affected Files — Modified:**
- `platform/gitops/apps/` — **Modified** (add ArgoCD Application CR for consent-service)

**Task List:**
1. Activate skill: `extract-domain-service` to scaffold the FastAPI bounded-context service.
2. Create `consent_records` DDL migration:
   ```sql
   CREATE TABLE IF NOT EXISTS consent_records (
     id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     tenant_id   UUID NOT NULL,             -- HC-4
     subject_id_hash  TEXT NOT NULL,        -- HMAC-SHA256 of email (HC-6)
     channel     TEXT NOT NULL,             -- 'email' | 'sms' | 'push'
     purpose     TEXT NOT NULL,             -- 'marketing' | 'transactional'
     granted     BOOLEAN NOT NULL DEFAULT false,
     created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
   );
   CREATE INDEX ON consent_records(tenant_id, subject_id_hash, channel, purpose);
   ALTER TABLE consent_records ENABLE ROW LEVEL SECURITY;
   CREATE POLICY consent_rls ON consent_records
     USING (tenant_id = current_setting('app.tenant_id')::UUID);
   ```
3. Implement `GET /consent/{subject_id_hash}?channel=&purpose=&tenant_id=` returning `{ allowed: bool }`.
4. Emit CloudEvent `i3.consent.record.queried` on every check (9-field envelope, UUIDv7 `id`, HC-4 `tenantid`).
5. Build and push image: `docker build -t de.icr.io/i3-platform/consent-service:latest .` then `docker push`.
6. Apply manifest: `kubectl apply -f platform/consent-service/consent-deploy.yaml -n i3-consent`.
7. Add ArgoCD Application CR and sync.

**Risk & Rollback:**
- Risk: Medium. Circuit-breaker in `consentAllowed()` defaults to `false` (deny) on service outage, so campaign sends fail-safe rather than failing open.
- Rollback: `kubectl delete deploy consent-service -n i3-consent`. The circuit-breaker trips and all sends are skipped (no data corruption).

**Sensor Checks:**
```bash
# Service is Running
kubectl get pods -n i3-consent -l app=consent-service | grep Running

# Health endpoint
curl -s http://consent-service.i3-consent.svc.cluster.local:8000/healthz

# Consent lookup returns JSON with 'allowed' key
curl -s "http://consent-service.i3-consent.svc.cluster.local:8000/consent/TESTHASH?channel=email&purpose=marketing&tenant_id=00000000-0000-0000-0000-000000000003" \
  | jq '.allowed'

# RLS: query without app.tenant_id must return empty
psql $CONSENT_DB_URL -c "SELECT count(*) FROM consent_records;"
```

---

## STEP-PLN05-07 — Enforce HMAC on `subject_id_hash` in `campaigns/send/route.ts`

**Objective:** Replace the raw-email fallback (`contact.email`) used as the consent subject hash with a proper HMAC-SHA256 value computed at runtime, eliminating the HC-6 violation TODO comment.

**Status:** ⏳ PENDING

**Pre-requisites:**
- STEP-PLN05-06 ✅ (consent-service must accept HMAC-hashed subjects)
- OpenBao path `i3/engage/hmac-secret` seeded with 256-bit hex key
- `MEMBER_HMAC_SECRET` environment variable injected into the engage-web deployment

**Affected Files:**
- `platform/engage/web/src/app/api/campaigns/send/route.ts` — **Modified** (lines 242–243)

**Task List:**
1. Seed HMAC secret: `vault kv put i3/engage/hmac-secret key="$(openssl rand -hex 32)"`.
2. Inject into engage-web deployment as `MEMBER_HMAC_SECRET` via secretKeyRef.
3. In `send/route.ts`, add the HMAC helper **before** the contact loop:
   ```typescript
   import { createHmac } from 'crypto'
   const HMAC_SECRET = process.env.MEMBER_HMAC_SECRET ?? ''
   function hmacHash(value: string): string {
     return createHmac('sha256', HMAC_SECRET).update(value).digest('hex')
   }
   ```
4. Replace lines 242–243:
   ```typescript
   // BEFORE (violates HC-6 — raw email fallback)
   const subjectHash: string = (contact.subject_id_hash as string | undefined)
     ?? contact.email   // TODO: replace with HMAC column after Phase 2 migration

   // AFTER (HC-6 compliant)
   const subjectHash: string = (contact.subject_id_hash as string | undefined)
     ?? hmacHash(contact.email)
   ```
5. Remove the `// TODO` comment.
6. Run `npm test --prefix platform/engage/web`.

**Risk & Rollback:**
- Risk: Low. If `MEMBER_HMAC_SECRET` is unset, `createHmac` throws on empty key — add a startup guard: `if (!HMAC_SECRET) throw new Error('MEMBER_HMAC_SECRET not set')`.
- Rollback: Revert the two changed lines; the raw-email fallback was already in place so no regression in behaviour.

**Sensor Checks:**
```bash
# No raw-email TODO must remain
grep -n "TODO.*HMAC\|subject_id_hash.*email" \
  platform/engage/web/src/app/api/campaigns/send/route.ts
# Expected: 0 matches

# HMAC helper must be present
grep "createHmac\|hmacHash" \
  platform/engage/web/src/app/api/campaigns/send/route.ts

# Tests pass
npm test --prefix platform/engage/web

# HC-6: raw email must NOT appear in any consent request
# (integration test: send a campaign and confirm subject in consent check is hex, not email@domain)
```

---

## STEP-PLN05-08 — Rebuild Admissions-Agent Image with `chromadb==0.4.24`

**Objective:** Confirm `platform/admissions/requirements.txt` pins `chromadb==0.4.24` (the CVE-patched version) and rebuild the admissions-agent container image so the pinned library is baked in.

**Status:** ✅ DONE — `platform/admissions/requirements.txt` line 9 already reads `chromadb==0.4.24`.

**Pre-requisites:**
- STEP-PLN05-04 ✅ (secrets populated so image can be tested)
- IBM Cloud Container Registry login: `ibmcloud cr login`

**Affected Files:**
- `platform/admissions/requirements.txt` — **Confirmed** (already correct, no change needed)
- `platform/admissions/admissions-deploy.yaml` — **Modified** (update image tag to timestamped build)

**Task List:**
1. Verify pin: `grep chromadb platform/admissions/requirements.txt` → must output `chromadb==0.4.24`.
2. Build: `docker build -t de.icr.io/i3-platform/admissions-agent:$(date +%Y%m%d) platform/admissions/`.
3. Scan: `ibmcloud cr va de.icr.io/i3-platform/admissions-agent:$(date +%Y%m%d)` — 0 critical CVEs.
4. Push: `docker push de.icr.io/i3-platform/admissions-agent:$(date +%Y%m%d)`.
5. Update image tag in `admissions-deploy.yaml` from `:latest` to the dated tag.
6. Apply and rollout: `kubectl rollout restart deploy/admissions-agent -n i3-admissions`.

**Risk & Rollback:**
- Risk: Low. If new image fails health checks, Kubernetes rolls back to previous revision automatically (`maxUnavailable: 0`).
- Rollback: `kubectl rollout undo deploy/admissions-agent -n i3-admissions`.

**Sensor Checks:**
```bash
# Pin confirmed
grep "chromadb==0.4.24" platform/admissions/requirements.txt

# Image contains correct version
docker run --rm de.icr.io/i3-platform/admissions-agent:latest \
  pip show chromadb | grep "Version: 0.4.24"

# Rollout complete
kubectl rollout status deploy/admissions-agent -n i3-admissions

# Health check
curl -s -o /dev/null -w "%{http_code}" \
  https://admissions.i3technologies.co.ke/healthz
# Expected: 200
```

---

## STEP-PLN05-09 — Add `i3-onboarding` to `platform/namespaces/namespaces.yaml`

**Objective:** Register the `i3-onboarding` namespace in the canonical namespace manifest so ArgoCD and the onboarding-agent deployment have a managed home namespace with proper resource quotas.

**Status:** ⏳ PENDING

**Pre-requisites:**
- STEP-PLN05-01 ✅ (auth guard removed so onboarding-agent can be deployed here)
- ArgoCD running in `i3-gitops`

**Affected Files:**
- `platform/namespaces/namespaces.yaml` — **Modified** (add Namespace + ResourceQuota for `i3-onboarding`)

**Task List:**
1. Append to `platform/namespaces/namespaces.yaml` after the last Tier 4 namespace (`i3-admissions`):
   ```yaml
   ---
   # ─── Tier 4: Application Workstreams (continued) ─────────
   apiVersion: v1
   kind: Namespace
   metadata:
     name: i3-onboarding
     labels:
       app.kubernetes.io/part-of: i3-platform
       i3.io/tier: "4-apps"
       i3.io/managed-by: argocd
   ---
   apiVersion: v1
   kind: ResourceQuota
   metadata:
     name: i3-onboarding-quota
     namespace: i3-onboarding
   spec:
     hard:
       requests.cpu: "2"
       requests.memory: 4Gi
       limits.cpu: "4"
       limits.memory: 8Gi
       count/pods: "20"
   ```
2. Apply: `kubectl apply -f platform/namespaces/namespaces.yaml`.
3. Verify namespace exists: `kubectl get namespace i3-onboarding`.
4. Confirm quota: `kubectl describe resourcequota i3-onboarding-quota -n i3-onboarding`.
5. Update ArgoCD Application CR for onboarding-agent to target `i3-onboarding`.

**Risk & Rollback:**
- Risk: Low. Adding a namespace is additive; it does not affect existing workloads.
- Rollback: `kubectl delete namespace i3-onboarding` (only safe if no workloads deployed yet).

**Sensor Checks:**
```bash
# Namespace must exist
kubectl get namespace i3-onboarding

# Labels must be correct
kubectl get namespace i3-onboarding -o jsonpath='{.metadata.labels}' \
  | jq '."app.kubernetes.io/part-of"'
# Expected: "i3-platform"

# ResourceQuota must be applied
kubectl describe resourcequota i3-onboarding-quota -n i3-onboarding \
  | grep "requests.cpu"

# No solution-01..08 namespace must be present on this cluster (migration confirmed)
kubectl get namespace | grep "solution-0" | wc -l
# Expected: 0
```

---

## HC-1 Compliance Statement

> **All 9 steps in this plan target exclusively `i3-*` namespaces.**  
> `solution-01` through `solution-08` have been **fully migrated off this cluster**.  
> No task in this plan references, touches, or generates manifests for those namespaces.  
> The constraint is retired on this server and documented here for audit traceability only.

---

## Step Dependency Graph

```
STEP-01 (A-1) ──────────────────┐
STEP-02 (A-2) ──────────────────┤
STEP-03 (A-3) ──────────────────┤─── No blockers (can run in parallel)
STEP-08 (F-1) ──────────────────┘

STEP-04 (A-4) ── depends on ── STEP-01 ✅
STEP-05 (A-5) ── depends on ── STEP-04
STEP-06 (B-1) ── depends on ── STEP-01, STEP-02 ✅
STEP-07 (D-3) ── depends on ── STEP-06
STEP-09 (F-2) ── depends on ── STEP-01 ✅
```

**Parallel execution opportunities:**
- Steps 3, 8, 9 can run simultaneously (no shared dependencies).
- Steps 4 and 6 can run in parallel after step 1.
- Step 5 must wait for step 4; step 7 must wait for step 6.

---

*Generated by Bob i3-mesh-architect — PLN-05 v1.0*
