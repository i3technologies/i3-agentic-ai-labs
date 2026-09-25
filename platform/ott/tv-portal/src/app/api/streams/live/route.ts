// /api/streams/live — returns current live streams from OvenMediaEngine Stats API
import { NextResponse } from 'next/server'

const OME_API_URL = process.env.OME_INTERNAL_URL || 'http://ome-origin.i3-ott.svc.cluster.local:8081'

export const dynamic = 'force-dynamic'
export const revalidate = 0

export interface LiveStream {
  name: string
  app: string
  bitrate: number
  createdAt: string
  hlsUrl: string
}

export async function GET() {
  try {
    const res = await fetch(`${OME_API_URL}/v1/stats/current`, {
      headers: { 'Accept': 'application/json' },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(5000),
    })

    if (!res.ok) {
      return NextResponse.json({ streams: [] }, { status: 200 })
    }

    const data = await res.json()
    const hlsBase = process.env.NEXT_PUBLIC_HLS_BASE_URL || 'https://stream.i3technologies.co.ke'

    // OME /v1/stats/current returns { virtualHosts: [{ apps: [{ streams: [...] }] }] }
    const streams: LiveStream[] = []
    for (const vhost of data?.virtualHosts ?? []) {
      for (const app of vhost?.apps ?? []) {
        for (const stream of app?.streams ?? []) {
          streams.push({
            name:      stream.name,
            app:       app.name,
            bitrate:   stream.input?.bitrate ?? 0,
            createdAt: stream.createdAt ?? new Date().toISOString(),
            hlsUrl:    `${hlsBase}/hls/${app.name}/${stream.name}/llhls.m3u8`,
          })
        }
      }
    }

    return NextResponse.json({ streams })
  } catch {
    // OME unreachable (no active streams) — return empty gracefully
    return NextResponse.json({ streams: [] })
  }
}
