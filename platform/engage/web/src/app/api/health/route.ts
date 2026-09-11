import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({ status: 'ok', service: 'engage-web', ts: new Date().toISOString() })
}
