# n8n OTT Workflow Import Guide

## Method 1 — n8n UI (Recommended)

1. Open `https://n8n.i3technologies.co.ke`
2. Sign in with your n8n admin credentials
3. Click **Workflows** → **Import from File**
4. Upload `platform/ott/pipeline/n8n-workflow.json`
5. Click **Save** then **Activate** the workflow

---

## Method 2 — n8n CLI (via `oc exec`)

```bash
# Copy workflow into pod
oc exec -n i3-ott deploy/n8n -- mkdir -p /tmp/import
# Use kubectl debug or cat + stdin if oc cp fails on Windows:
kubectl exec -n i3-ott deploy/n8n -it -- sh

# Inside the pod:
cat > /tmp/import/workflow.json << 'EOF'
{"workflows": [ <paste n8n-workflow.json contents here> ]}
EOF
n8n import:workflow --input=/tmp/import/workflow.json
```

---

## Method 3 — n8n REST API

```powershell
# First generate an API key in the n8n UI under Settings → API Keys
$apiKey = "<your-n8n-api-key>"
$wf = Get-Content "platform/ott/pipeline/n8n-workflow.json" -Raw | ConvertFrom-Json

Invoke-WebRequest `
  -Uri "https://n8n.i3technologies.co.ke/api/v1/workflows" `
  -Method POST `
  -Headers @{"X-N8N-API-KEY"=$apiKey; "Content-Type"="application/json"} `
  -Body ($wf | ConvertTo-Json -Depth 20)
```

---

## Workflow Overview

| Node | Purpose |
|------|---------|
| **Stream End Webhook** | Receives OME `stream-end` event |
| **Extract Stream Info** | Parses `stream.name` and `output_path` |
| **Call OTT Pipeline API** | POSTs to `ott-pipeline.i3-ott.svc.cluster.local:8090/webhook/stream-end` |
| **Wait for Pipeline** | Listens on `/webhook/pipeline-complete` callback |
| **Notify Directus** | Updates vod_recordings status to `ready` |
| **Send Notification** | Sends completion email/Slack (optional) |

## Webhook URLs (internal cluster)

- **OME → n8n**: `http://n8n.i3-ott.svc.cluster.local:5678/webhook/stream-end`
- **Pipeline → n8n callback**: `https://n8n.i3technologies.co.ke/webhook/pipeline-complete`

## Environment Variables Required in n8n

Set these as n8n Credentials or Environment Variables:

| Variable | Value |
|----------|-------|
| `PIPELINE_WEBHOOK_SECRET_HMAC` | From `ott-pipeline-secrets/PIPELINE_WEBHOOK_SECRET` |
| `DIRECTUS_URL` | `https://cms.i3technologies.co.ke` |
| `DIRECTUS_TOKEN` | `i3-pipeline-service-token-2026` |
