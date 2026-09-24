import fs from 'fs'
import { Pool } from 'pg'

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
  ssl: {
    rejectUnauthorized: true,
    ca: fs.readFileSync(process.env.PG_CA_CERT_PATH!),
  },
})

export default pool
