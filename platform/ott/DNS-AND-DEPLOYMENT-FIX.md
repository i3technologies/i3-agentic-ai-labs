# OTT Platform — DNS & Deployment Fix Guide
# ============================================================
# Fixes: tv.i3technologies.co.ke "Application is not available" / 503
# Date: 2026
# Cluster: IBM ROKS 4.17 · eu-de · i3-platform (da0umukf0anep6valpig)
# ============================================================

## ── 1. ROOT CAUSE SUMMARY ────────────────────────────────────
#
# tv.i3technologies.co.ke returns "Application is not available" / 503 because:
#
#   (a) DNS is FINE — tv.i3technologies.co.ke resolves to IBM ROKS ingress ✓
#   (b) The OpenShift BuildConfig was never triggered — no container image exists
#       → Deployment pods are in ImagePullBackOff → Service has 0 ready endpoints
#       → OpenShift Router returns 503 / "Application is not available"
#   (c) Dockerfile COPY of non-existent public/ dir causes Docker build failure
#       (FIXED: now uses RUN mkdir + conditional copy)
#   (d) BuildConfig had wrong Git URI casing (i3-agentic-ai-labs vs i3-Agentic-AI-Labs)
#       (FIXED: corrected in tv-portal-build.yaml)
#   (e) Secret had literal "REPLACE_FROM_VAULT" — would cause pod CrashLoopBackOff
#       (FIXED: empty string placeholder — patch with real token per Step 4 below)
#   (f) OME ClusterIP service was missing port 8081 (stats REST API used by LiveGrid + liveness probe)
#       (FIXED: added in ome-deploy.yaml)
#   (g) Next.js 15 breaking change: params must be awaited in watch/[streamName]/page.tsx
#       (FIXED: component is now async and awaits params)
#   (h) Next.js 15: viewport in metadata is deprecated — causes build warning/failure
#       (FIXED: exported as separate viewport const in layout.tsx)
#   (i) OME REST API port 8081 not explicitly bound in Server.xml — implicit default unreliable
#       (FIXED: explicit <Managers><API><Port>8081 added; ome-api-secret created)
#   (j) directus-secrets / n8n-secrets all literal REPLACE_FROM_VAULT — CrashLoopBackOff
#       (FIXED: empty string placeholders; OpenBao inject annotations updated)
#   (k) SeaweedFS replication=000 — single-pod data loss risk
#       (FIXED: changed to 001 on both master defaultReplication and volume -replication)
#   (l) Wildcard CORS (*) on OME VHost.xml and nginx-hls
#       (FIXED: restricted to tv/stream/hls.i3technologies.co.ke origins)
#   (m) Pipeline webhook had no authentication
#       (FIXED: HMAC-SHA256 X-OME-Signature verification; PIPELINE_WEBHOOK_SECRET from vault)
#   (n) FFmpeg ran as blocking subprocess.run in async FastAPI handler
#       (FIXED: replaced with asyncio.create_subprocess_exec; Whisper/S3 in thread pool)
#   (o) n8n workflow hard-coded 5-min wait before Directus update
#       (FIXED: replaced with pipeline-complete callback webhook; n8n waits for real signal)
#   (p) VOD API offset param could be negative
#       (FIXED: Math.max(0, offset) in vod/route.ts)
#   (q) Back button in watch page used plain <a> (full SSR reload)
#       (FIXED: replaced with next/link <Link>)

## ── 2. PRE-FLIGHT: Verify DNS (already working) ─────────────
#
#   nslookup tv.i3technologies.co.ke
#   → Should show CNAME to 8eec2322-eu-de.lb.appdomain.cloud ✓
#
#   If NOT resolving, add this CNAME at your registrar:
#   Name:  tv
#   Type:  CNAME
#   Value: i3-platform-bcc5f5bc822da314835720fd0c9856ce-0000.eu-de.containers.appdomain.cloud
#   TTL:   300

## ── 3. STEP 1: Login & Apply Infrastructure Manifests ───────
#
# Get your oc login command from:
#   IBM Cloud Console → OpenShift → your cluster → Actions → Copy login command
#
#   oc login --token=<TOKEN> --server=<API_URL>
#
# Ensure namespace exists:
#   oc get ns i3-ott 2>/dev/null || oc create ns i3-ott
#
# Apply OME fix (adds port 8081 to ClusterIP + NLB annotations on ingest):
#   oc apply -f platform/ott/ome/ome-deploy.yaml -n i3-ott
#
# Apply nginx-hls (adds stream. and hls. routes):
#   oc apply -f platform/ott/nginx/nginx-hls.yaml -n i3-ott

## ── 4. STEP 2: Build the TV Portal ──────────────────────────
#
# Apply ImageStream + BuildConfig:
#   oc apply -f platform/ott/tv-portal/tv-portal-build.yaml -n i3-ott
#
# Trigger the Docker build (builds from Git source, pushes to internal registry):
#   oc start-build tv-portal -n i3-ott --follow
#
# The build will:
#   1. Pull node:20-alpine
#   2. Clone https://github.com/i3-technologies/i3-Agentic-AI-Labs.git (main)
#   3. cd platform/ott/tv-portal && npm ci && npm run build
#   4. Produce standalone Next.js output
#   5. Push to image-registry.openshift-image-registry.svc:5000/i3-ott/tv-portal:latest
#
# If build fails, inspect logs:
#   oc logs -n i3-ott bc/tv-portal -f

## ── 5. STEP 3: Deploy the TV Portal ─────────────────────────
#
# Apply Deployment + Service + Route + Secret skeleton:
#   oc apply -f platform/ott/tv-portal/tv-portal-deploy.yaml -n i3-ott
#
# Wait for pods to be Ready:
#   oc rollout status deployment/tv-portal -n i3-ott --timeout=3m

## ── 6. STEP 4: Inject All Secrets from OpenBao ──────────────
#
# All secrets use empty-string placeholders and require vault injection.
# Run these BEFORE applying any deployments (or patch after apply):
#
# TV Portal (Directus token):
#   oc patch secret tv-portal-secrets -n i3-ott \
#     -p '{"stringData":{"DIRECTUS_TOKEN":"<directus-static-token>"}}'
#   bao kv get i3/ott/directus  (field: static_token)
#
# Directus CMS:
#   oc patch secret directus-secrets -n i3-ott \
#     -p '{"stringData":{"DB_USER":"...","DB_PASSWORD":"...","KEY":"...","SECRET":"...","ADMIN_PASSWORD":"...","KEYCLOAK_CLIENT_SECRET":"...","SEAWEEDFS_ACCESS_KEY":"...","SEAWEEDFS_SECRET_KEY":"..."}}'
#   bao kv get i3/ott/directus
#
# n8n Workflow Engine:
#   oc patch secret n8n-secrets -n i3-ott \
#     -p '{"stringData":{"DB_USER":"...","DB_PASSWORD":"...","ENCRYPTION_KEY":"..."}}'
#   bao kv get i3/ott/n8n
#
# OME REST API token:
#   oc patch secret ome-api-secret -n i3-ott \
#     -p '{"stringData":{"OME_API_TOKEN":"<strong-random-token>"}}'
#   bao kv put i3/ott/ome api_token=<same-token>
#
# OTT Pipeline:
#   oc patch secret ott-pipeline-secrets -n i3-ott \
#     -p '{"stringData":{"PIPELINE_WEBHOOK_SECRET":"<32-char-random>","AWS_ACCESS_KEY_ID":"...","AWS_SECRET_ACCESS_KEY":"...","DIRECTUS_TOKEN":"..."}}'
#   bao kv get i3/ott/pipeline
#
# After patching, restart all deployments:
#   oc rollout restart deployment/tv-portal deployment/directus deployment/n8n deployment/ott-pipeline -n i3-ott
#   oc rollout status  deployment/tv-portal deployment/directus deployment/n8n deployment/ott-pipeline -n i3-ott --timeout=5m

## ── 7. STEP 5: Get OME Ingest External IP ───────────────────
#
# Wait ~3-5 minutes after applying ome-deploy.yaml, then:
#   oc get svc ome-ingest -n i3-ott -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
#
# Add an A record at your registrar:
#   Name:  ingest
#   Type:  A
#   Value: <OME_LOADBALANCER_IP>
#   TTL:   300

## ── 8. STEP 6: End-to-End Verification ──────────────────────
#
# 1. Health check:
#   curl -I https://tv.i3technologies.co.ke/api/health
#   → Expected: HTTP/2 200  {"status":"ok","service":"i3-tv-portal"}
#
# 2. Homepage:
#   curl -I https://tv.i3technologies.co.ke/
#   → Expected: HTTP/2 200
#
# 3. Pods status:
#   oc get pods -n i3-ott
#   → Expected: tv-portal-* Running (2/2), ome-origin-* Running, nginx-hls-* Running
#
# 4. Routes:
#   oc get routes -n i3-ott
#   → Expected:
#       tv-portal        tv.i3technologies.co.ke       edge  ✓
#       nginx-hls        stream.i3technologies.co.ke   edge  ✓
#       nginx-hls-alias  hls.i3technologies.co.ke      edge  ✓
#
# 5. Service endpoints:
#   oc get endpoints tv-portal -n i3-ott
#   → Must show IP:3000 (not "<none>")

## ── 9. TROUBLESHOOTING ───────────────────────────────────────
#
# Still 503 after pods Running?
#   oc get endpoints tv-portal -n i3-ott
#   → If "<none>": pods failed readiness probe → check logs:
#   oc logs -n i3-ott -l app=tv-portal --tail=50
#
# ImagePullBackOff?
#   oc describe pod -n i3-ott -l app=tv-portal | grep -A5 Events
#   → Means build didn't complete or image tag mismatch
#   → Re-run: oc start-build tv-portal -n i3-ott --follow
#
# CrashLoopBackOff?
#   oc logs -n i3-ott -l app=tv-portal --previous
#   → Usually means DIRECTUS_TOKEN is wrong or PORT/HOSTNAME env missing

## ── 10. FULL DNS RECORD TABLE ───────────────────────────────
#
# CNAME Target: i3-platform-bcc5f5bc822da314835720fd0c9856ce-0000.eu-de.containers.appdomain.cloud
#
# Subdomain    Type   Value                    App
# ──────────────────────────────────────────────────────────────
# tv           CNAME  <CNAME_TARGET>           i3 TV Portal ← THIS ONE
# stream       CNAME  <CNAME_TARGET>           HLS CDN Edge
# hls          CNAME  <CNAME_TARGET>           HLS CDN Alias
# cms          CNAME  <CNAME_TARGET>           Directus CMS
# n8n          CNAME  <CNAME_TARGET>           n8n Automation
# sso          CNAME  <CNAME_TARGET>           Keycloak SSO
# evalos       CNAME  <CNAME_TARGET>           EvalOS
# admissions   CNAME  <CNAME_TARGET>           Admissions Agent
# grafana      CNAME  <CNAME_TARGET>           Grafana
# argocd       CNAME  <CNAME_TARGET>           ArgoCD
# onboarding   CNAME  <CNAME_TARGET>           Onboarding Agent
# ingest       A      <OME_LB_IP>              OME RTMP/SRT Ingest

## ── 11. Architecture ────────────────────────────────────────
#
#  Browser → tv.i3technologies.co.ke
#       ↓ DNS CNAME → IBM ROKS Ingress
#       ↓ OpenShift Route → tv-portal Service → tv-portal Pod (Next.js 15 SSR)
#       ↓ VideoPlayer fetches stream.i3technologies.co.ke/hls/live/<stream>/llhls.m3u8
#                             → nginx-hls → OME (live) or SeaweedFS (VOD)
#       ↓ VodGrid/LiveGrid SSR → ome-origin.i3-ott.svc:8081 / directus.i3-ott.svc:8055
#
#  OBS Studio → ingest.i3technologies.co.ke:1935 (RTMP)
#       → OME NLB → ome-origin → ABR encode → nginx-hls serves LL-HLS

## ── 12. Files Changed ───────────────────────────────────────
#
# ── Original fixes (Phase 1) ───────────────────────────────
#  FIX: platform/ott/tv-portal/Dockerfile               — public/ dir handling
#  FIX: platform/ott/tv-portal/next.config.js           — images + serverExternalPackages
#  FIX: platform/ott/tv-portal/src/app/layout.tsx       — viewport exported separately
#  FIX: platform/ott/tv-portal/src/app/watch/[streamName]/page.tsx — await params (Next.js 15)
#  FIX: platform/ott/tv-portal/tv-portal-build.yaml     — correct Git URI casing
#  FIX: platform/ott/tv-portal/tv-portal-deploy.yaml    — Secret placeholder removed
#  FIX: platform/ott/ome/ome-deploy.yaml                — added port 8081 to ome-origin ClusterIP
#
# ── Full remediation (Phase 2 — all blockers resolved) ─────
#  FIX: platform/ott/seaweedfs/seaweedfs-deploy.yaml    — replication 000→001 (CRITICAL)
#  FIX: platform/ott/directus/directus-deploy.yaml      — secrets REPLACE_FROM_VAULT→"" + runbook (CRITICAL)
#  FIX: platform/ott/n8n/n8n-deploy.yaml                — secrets REPLACE_FROM_VAULT→"" + runbook
#  FIX: platform/ott/ome/ome-deploy.yaml                — explicit API port 8081 in Server.xml + ome-api-secret (CRITICAL)
#  FIX: platform/ott/ome/ome-deploy.yaml                — CORS restricted to portal origins (VHost.xml)
#  FIX: platform/ott/nginx/nginx-hls.yaml               — CORS restricted to portal origins (not wildcard)
#  FIX: platform/ott/tv-portal/src/app/api/streams/vod/route.ts — Math.max(0,offset) + Math.max(0,limit)
#  FIX: platform/ott/tv-portal/src/app/watch/[streamName]/page.tsx — back button uses next/link
#  NEW: platform/ott/tv-portal/.eslintrc.json           — ESLint config added
#  FIX: platform/ott/pipeline/pipeline.py               — HMAC auth + async FFmpeg + n8n callback (v1.1.0)
#  FIX: platform/ott/pipeline/n8n-workflow.json         — callback webhook replaces 5-min wait; cohort notify fixed
#  NEW: platform/ott/pipeline/pipeline-deploy.yaml      — pipeline Deployment + Service + Secret manifest
