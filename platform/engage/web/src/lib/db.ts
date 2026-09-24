import fs from 'fs'
import { Pool, type PoolConfig } from 'pg'

/**
 * STEP-P1-03: enforce TLS certificate validation in production.
 * PG_CA_CERT_PATH must be set to the Crunchy operator CA cert path mounted from
 * the crunchy-postgres-ca Secret. NEXT_BUILD=true is set by the BuildConfig to
 * skip the cert check during `next build` static page collection — cert files are
 * not present in the build container. The check is enforced at runtime (pod startup).
 */
function createPool(): Pool {
  const config: PoolConfig = {
    connectionString: process.env.DATABASE_URL,
    max: 10,
  }

  const caCertPath   = process.env.PG_CA_CERT_PATH
  const isBuildPhase = process.env.NEXT_BUILD === 'true'

  if (process.env.NODE_ENV === 'production' && !isBuildPhase) {
    if (!caCertPath) {
      throw new Error(
        'PG_CA_CERT_PATH is not set. Mount the crunchy-postgres-ca Secret and set ' +
        'PG_CA_CERT_PATH=/etc/ssl/certs/postgres-ca.crt in the Engage Deployment.'
      )
    }
    config.ssl = {
      rejectUnauthorized: true,   // SC-P1-03: validate Crunchy operator CA
      ca: fs.readFileSync(caCertPath),
    }
  } else {
    // Development or build phase: allow plaintext / skip cert check
    config.ssl = false
  }

  return new Pool(config)
}

const pool: Pool = createPool()

export default pool
