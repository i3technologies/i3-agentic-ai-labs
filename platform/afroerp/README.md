# AfroERP — AI-Powered African Business OS

**Namespace:** `i3-afroerp`
**Domain:** `erp.i3technologies.co.ke`
**Keycloak Realm:** `afroerp`

## Stack
- **ERPNext 15** (Frappe Framework) — MIT licence
- **MariaDB 10.6** — StatefulSet with 50Gi PVC (ERPNext requires MariaDB, not PostgreSQL)
- **Redis** — Frappe queue and cache
- **Frappe Workers** — background job processors

## Kenya Custom Modules
- `afroerp_mpesa` — M-Pesa STK Push / B2C (Daraja v2)
- `afroerp_kratims` — KRA eTIMS e-invoicing integration
- `afroerp_tax` — Kenya tax tables (VAT, WHT, PAYE)

## AI Components
- **Mfumo Co-worker** — Open WebUI white-labelled, ERPNext expert persona
- **AfroERP AI Agent** — LangGraph + ERPNext REST API — autonomous ERP tasks
- **ChromaDB collection:** `afroerp-kb` — ERPNext docs + KRA guidelines

## AI Models Used
- `qwen-heavy` — financial narrative, anomaly detection
- `qwen-fast` — general ERP assistant, CRM scoring
- `coder` — scripting, ERPNext custom scripts

## Status: 📋 Phase 4 — To Build
