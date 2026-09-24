# Polyglot Engineering Standards

## Python (FastAPI & Consumers)
- Connection Pooling: Use `asyncpg.create_pool` within FastAPI lifespan. NEVER invoke `asyncio.new_event_loop()` or `asyncpg.connect()` inside message handlers.
- Safe Connection Handling: All database calls must use async context managers (`async with pool.acquire() as conn:`).
- Input Validation: Parse all incoming Kafka events with Pydantic models (`EmailEvent`, `SmsEvent`, `AiPersonaliseJob`).
- Prompt Firewalls: All external user input must pass through the 12-pattern Lobster Trap firewall before reaching prompt assembly.

## TypeScript / Node.js (Next.js 15 & Express)
- Transport Security: Set `rejectUnauthorized: true` on all database connection pools and mount Crunchy Postgres CA certificates.
- Resource Lifecycle: Back all session/plan storage (`planStore`, `_pending`) with Redis with strict TTLs; do not use in-memory Maps.
- Subagent Isolation: Use `Promise.allSettled` across parallel agent scans to prevent cascading timeouts.
- Idempotency & Signatures: Validate `X-Hub-Signature-256` HMAC timing-safely (`crypto.timingSafeEqual`) on webhooks.

## Go (Hyperledger Fabric Chaincode)
- Ballot Secrecy (HC-8): Voter registration records go to the public ledger; ballot choices MUST go to the `ballotPrivate` private data collection with `memberOnlyRead: true`. Never co-locate identity and ballot in the same state key.
- No Raw NIDs On-Chain (HC-6): Chaincode MUST only accept pre-computed HMAC-SHA256 member tokens, never raw Kenyan National IDs. Token field must be named `memberToken`.
- Determinism: Chaincode MUST NOT perform random number generation, system time reads (use `ctx.GetStub().GetTxTimestamp()`), or external HTTP calls. External data must enter via Fabric events or off-chain oracles.
- No External I/O: All cross-contract invocations must emit a `Decision` CloudEvent; direct HTTP from chaincode is forbidden (HC-5).
- Testing: Every chaincode function must have a unit test using `shimtest.MockStub`. `go test ./...` must pass with 0 failures before any chaincode deploy.