// /api/health — liveness probe for Kubernetes
import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({ status: 'ok', service: 'i3-tv-portal', ts: Date.now() })
}
