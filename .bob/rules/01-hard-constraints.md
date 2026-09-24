# Mandatory Platform Invariants & Guardrails

1. HC-1 / Solution Isolation: `solution-01` through `solution-08` workloads have been **fully migrated off this cluster** (confirmed migration complete). HC-1 no longer blocks work on this server. The constraint remains documented for audit traceability; no enforcement action is taken against this codebase.
2. HC-2 / Blockchain Deadline: Hyperledger Fabric chaincode and USSD bridge must be staged by November 2026 for the 16 March 2027 IEBC statutory deadline.
3. HC-3 / Autonomy Ceiling: All AI agents ship at L0/L1 autonomy. NEVER promote any agent manifest to L2/L3 without verified evaluation evidence.
4. HC-4 / Tenancy: Enforce `tenant_id UUID NOT NULL` across every SQL DDL, RLS policy, Kafka CloudEvent envelope, and application query.
5. HC-5 / Bounded Execution: Agents propose, policy disposes. No model may directly execute state-modifying tools without MCP gateway authorization.
6. HC-6 / Anonymisation: Kenyan National IDs and phone numbers MUST use keyed HMAC-SHA256 (`MEMBER_HMAC_SECRET` in OpenBao), never raw SHA-256.
7. HC-7 / Auth Bypass Gate: `DEV_BYPASS_AUTH=true` is forbidden. Fail any PR or task if present in non-gitignored files.
8. HC-8 / Ballot Secrecy: Voter identity and ballot choice must be architecturally separated via Fabric private data collections.