# i3-Engage Cloud — Customer 360 CDP + Omnichannel

**Namespace:** `i3-engage`
**Domain:** `engage.i3technologies.co.ke`
**Keycloak Realm:** `engage`

## Components

| Service | Description |
|---------|-------------|
| Engage Web (Next.js) | CDP dashboard: contacts, segments, campaigns, analytics |
| CDP Core | PostgreSQL `engage_db` + Kafka streams for real-time events |
| SMS Gateway | Africa's Talking SMPP API / direct SMPP |
| WhatsApp Gateway | Meta WhatsApp Business Cloud API relay |
| Email | Brevo API (existing) extended for Engage |
| M-Pesa / Paystack | In-message payment links |
| Nuru Co-worker | Open WebUI white-labelled — Campaign Manager persona |
| Campaign AI Agent | LangGraph — segment builder, content gen, send-time optimiser |

## AI Models Used
- `qwen-fast` — campaign content, segment queries, churn prediction
- `granite-nano` — intent classification in chatbot flows
- `nomic-embed-text` — contact behaviour embeddings for lookalike audiences

## Kafka Topics
- `engage.contact-events` — all customer interactions
- `engage.campaign-sent` — dispatch confirmations
- `engage.campaign-replied` — inbound responses
- `engage.payment-events` — M-Pesa / Paystack webhooks

## Status: 📋 Phase 4 — To Build
