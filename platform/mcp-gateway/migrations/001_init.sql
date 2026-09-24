-- MCP Tool Gateway — initial schema
-- Namespace: i3-agent-mesh
-- Applied by: psql $MCP_GATEWAY_DB_URL -f migrations/001_init.sql

-- ── Tool registry ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mcp_tool_registry (
    name               TEXT        PRIMARY KEY,
    description        TEXT        NOT NULL DEFAULT '',
    version            TEXT        NOT NULL DEFAULT '1.0.0',
    tenant_scope       TEXT        NOT NULL DEFAULT 'single'   CHECK (tenant_scope IN ('single','all')),
    read_write         TEXT        NOT NULL DEFAULT 'read'      CHECK (read_write IN ('read','write','readwrite')),
    side_effect_class  TEXT        NOT NULL DEFAULT 'none'      CHECK (side_effect_class IN ('none','external_read','external_write','customer_facing')),
    risk_tier          SMALLINT    NOT NULL DEFAULT 0           CHECK (risk_tier BETWEEN 0 AND 3),
    rate_limit         INT         NOT NULL DEFAULT 60,
    timeout_ms         INT         NOT NULL DEFAULT 10000,
    audit_required     BOOLEAN     NOT NULL DEFAULT FALSE,
    registered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Invocation audit log ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mcp_invocation_log (
    invocation_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name       TEXT        NOT NULL REFERENCES mcp_tool_registry(name),
    agent_id        TEXT        NOT NULL,
    tenant_id       UUID        NOT NULL,                          -- HC-4
    correlation_id  UUID        NOT NULL,
    risk_tier       SMALLINT    NOT NULL,
    duration_ms     INT         NOT NULL,
    outcome         TEXT        NOT NULL DEFAULT 'success'         CHECK (outcome IN ('success','error','blocked')),
    error_detail    TEXT,
    invoked_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enforce tenant_id is always present (HC-4)
ALTER TABLE mcp_invocation_log ALTER COLUMN tenant_id SET NOT NULL;

-- Row-Level Security on audit log — tenant can only read their own rows
ALTER TABLE mcp_invocation_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON mcp_invocation_log
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::UUID);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_invlog_agent_id    ON mcp_invocation_log (agent_id, invoked_at DESC);
CREATE INDEX IF NOT EXISTS idx_invlog_tenant_id   ON mcp_invocation_log (tenant_id, invoked_at DESC);
CREATE INDEX IF NOT EXISTS idx_invlog_tool_name   ON mcp_invocation_log (tool_name, invoked_at DESC);

-- ── Rate-limit counters (1-minute sliding windows) ────────────────────────
-- Stored in Redis (see main.py); no SQL table needed.
