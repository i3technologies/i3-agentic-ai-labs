import fs from 'fs'
import { Pool, type PoolConfig } from 'pg'

declare global {
  // eslint-disable-next-line no-var
  var _pgPool: Pool | undefined
}

function createPool(): Pool {
  const connectionString = process.env.DATABASE_URL
  if (!connectionString) {
    throw new Error('DATABASE_URL environment variable is not set')
  }

  const config: PoolConfig = {
    connectionString,
    max: 10,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  }

  // SSL: Crunchy Postgres uses a self-signed cluster CA.
  // We pin that CA certificate and disable rejectUnauthorized so Node.js does
  // not fail on a self-signed chain while still encrypting the connection.
  // If PG_CA_CERT_PATH is not set we still allow TLS (rejectUnauthorized: false)
  // so the app functions in all environments.
  const caCertPath = process.env.PG_CA_CERT_PATH
  if (caCertPath) {
    config.ssl = {
      rejectUnauthorized: false,           // Crunchy CA is self-signed
      ca: fs.readFileSync(caCertPath, 'utf8'),
    }
  } else if (process.env.NODE_ENV === 'production') {
    console.warn(
      '[evalos-db] WARNING: PG_CA_CERT_PATH is not set. ' +
      'Connecting with TLS but without CA pinning.'
    )
    config.ssl = { rejectUnauthorized: false }
  } else {
    // Development: allow plaintext or self-signed
    config.ssl = false
  }

  return new Pool(config)
}

// Reuse pool across hot reloads in development
const pool: Pool = global._pgPool ?? createPool()

if (process.env.NODE_ENV !== 'production') {
  global._pgPool = pool
}

export default pool
