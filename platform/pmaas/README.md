# PMaaS 4.0 — Platform Deployment

**Namespace:** `i3-pmaas`
**Domain:** `pmaas.i3technologies.co.ke`
**Keycloak Realm:** `pmaas`

## Components

| Service | File | Description |
|---------|------|-------------|
| PMaaS Web (Next.js) | `pmaas-deploy.yaml` | Campaign dashboard, war room, voter DB |
| Campaign Agent | `campaign-agent-deploy.yaml` | LangGraph agent: targeting, briefings, content |
| AI Caller Engine | `ai-caller-deploy.yaml` | Asterisk SIP + XTTS-v2 + Whisper + LLM |
| Dawa Co-worker | `open-webui-pmaas-deploy.yaml` | White-labelled Open WebUI for campaign strategist |
| M-Pesa Webhook | `mpesa-webhook-deploy.yaml` | Daraja API v2 donation receiver |

## AI Models Used
- `qwen-heavy` — war room reports, daily briefings, content generation
- `qwen-fast` — voter Q&A, manifesto RAG, WhatsApp bot
- `XTTS-v2` — candidate voice synthesis (voice clone)
- `faster-whisper` — voter call transcription (inbound)

## Database: `pmaas_db` (PostgreSQL via pgbouncer)

## Status: 📋 Phase 3 — To Build
