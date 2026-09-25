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

## ── 6. STEP 4: Inject the Directus Token ────────────────────
#
# The Secret was deployed with an empty DIRECTUS_TOKEN.
# Patch it with the real token from OpenBao / Directus admin:
#
#   oc patch secret tv-portal-secrets -n i3-ott \
#     -p '{"stringData":{"DIRECTUS_TOKEN":"<your-directus-static-token>"}}'
#
# Then restart the pods to pick up the new secret:
#   oc rollout restart deployment/tv-portal -n i3-ott
#   oc rollout status  deployment/tv-portal -n i3-ott --timeout=2m
#
# To get the Directus token from OpenBao:
#   bao kv get i3/ott/directus  (field: admin_token or static_token)

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
#  FIX: platform/ott/tv-portal/Dockerfile               — public/ dir handling
#  FIX: platform/ott/tv-portal/next.config.js           — images + serverExternalPackages
#  FIX: platform/ott/tv-portal/src/app/layout.tsx       — viewport exported separately
#  FIX: platform/ott/tv-portal/src/app/watch/[streamName]/page.tsx — await params (Next.js 15)
#  FIX: platform/ott/tv-portal/tv-portal-build.yaml     — correct Git URI casing
#  FIX: platform/ott/tv-portal/tv-portal-deploy.yaml    — Secret placeholder removed
#  FIX: platform/ott/ome/ome-deploy.yaml                — added port 8081 to ome-origin ClusterIP
