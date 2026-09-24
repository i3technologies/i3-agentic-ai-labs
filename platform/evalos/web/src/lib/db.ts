import fs from 'fs'
import { Pool, type PoolConfig } from 'pg'

declare global {
  // eslint-disable-next-line no-var
  var _pgPool: Pool | undefined
}

/**
 * Strip the sslmode query parameter from a Postgres connection string.
 *
 * The `pg` library (v8+) merges sslmode from the connection string with the
 * config.ssl object. When sslmode=require/verify-ca/verify-full is present,
 * pg enforces certificate chain validation even when rejectUnauthorized: false
 * is set in config.ssl — causing SELF_SIGNED_CERT_IN_CHAIN on the Crunchy
 * operator CA. Removing sslmode lets config.ssl take full control.
 */
function stripSslMode(connectionString: string): string {
  try {
    const u = new URL(connectionString)
    u.searchParams.delete('sslmode')
    u.searchParams.delete('sslrootcert')
    u.searchParams.delete('sslcert')
    u.searchParams.delete('sslkey')
    return u.toString()
  } catch {
    // Not a parseable URL — return as-is and let pg report the error
    return connectionString
  }
}

/**
 * Read a CA certificate from a file path.
 *
 * Kubernetes secrets mounted as files are already base64-decoded by kubelet.
 * If the Secret was accidentally stored double-base64 encoded, the mounted
 * file will contain base64 text. This function detects and decodes that case.
 * A UTF-8 BOM is also stripped if present.
 */
function readCaCert(certPath: string): string {
  let raw = fs.readFileSync(certPath, 'utf8')
  // Strip UTF-8 BOM
  if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1)
  raw = raw.trim()
  // If it doesn't start with '-----BEGIN', it's still base64-encoded
  if (!raw.startsWith('-----BEGIN')) {
    try {
      raw = Buffer.from(raw, 'base64').toString('utf8').trim()
    } catch {
      // Leave as-is; TLS will report the real error
    }
  }
  return raw
}

function createPool(): Pool {
  const rawConnectionString = process.env.DATABASE_URL
  if (!rawConnectionString) {
    throw new Error('DATABASE_URL environment variable is not set')
  }

  // Remove sslmode from the connection string so config.ssl has full control
  const connectionString = stripSslMode(rawConnectionString)

  const config: PoolConfig = {
    connectionString,
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  }

  // SSL configuration — STEP-P1-03: enforce certificate validation in production.
  // PG_CA_CERT_PATH must be set to the Crunchy operator CA cert path
  // (mounted from the crunchy-postgres-ca Secret by the EvalOS Deployment).
  // NEXT_BUILD=true is set by the OpenShift BuildConfig to skip the cert check
  // during `next build` static page collection — cert files are not present in
  // the build container. The check is enforced at runtime (pod startup), not
  // at build time, so fail-closed behaviour is preserved.
  const caCertPath = process.env.PG_CA_CERT_PATH
  const isBuildPhase = process.env.NEXT_BUILD === 'true'
  if (process.env.NODE_ENV === 'production' && !isBuildPhase) {
    if (!caCertPath) {
      throw new Error(
        'PG_CA_CERT_PATH is not set. Mount the crunchy-postgres-ca Secret and set ' +
        'PG_CA_CERT_PATH=/etc/ssl/certs/postgres-ca.crt in the EvalOS Deployment.'
      )
    }
    config.ssl = {
      rejectUnauthorized: true,   // STEP-P1-03: validate Crunchy operator CA
      ca: readCaCert(caCertPath),
    }
  } else {
    // Development or build phase: allow plaintext / skip cert check
    config.ssl = false
  }

  return new Pool(config)
}

// Reuse pool across hot reloads in development; created fresh each build in prod.
const pool: Pool = global._pgPool ?? createPool()

if (process.env.NODE_ENV !== 'production') {
  global._pgPool = pool
}

export default pool

/**
 * Set the RLS tenant context for the current transaction.
 *
 * PgBouncer in transaction-pooling mode rejects parameterised SET statements
 * (`SET LOCAL app.tenant_id = $1`) with "syntax error at or near $1" (PG-42601).
 * The workaround is to inline the value. This is safe because tenantId is always
 * a UUID extracted from the verified Keycloak JWT — never raw user input.
 *
 * Usage:
 *   await setTenantContext(client, tenantId)
 */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export async function setTenantContext(
  client: { query: (sql: string) => Promise<unknown> },
  tenantId: string
): Promise<void> {
  if (!UUID_RE.test(tenantId)) {
    throw new Error(`Invalid tenant_id — must be a UUID, got: ${tenantId}`)
  }
  // Inline the UUID: no injection risk — UUID charset is [0-9a-f-] only.
  await client.query(`SET LOCAL app.tenant_id = '${tenantId}'`)
}
