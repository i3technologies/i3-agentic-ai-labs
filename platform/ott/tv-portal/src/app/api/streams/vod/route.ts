// /api/streams/vod — returns VOD catalogue from Directus CMS
import { NextResponse } from 'next/server'

const CMS_URL = process.env.DIRECTUS_INTERNAL_URL || 'http://directus.i3-ott.svc.cluster.local:8055'
const CMS_TOKEN = process.env.DIRECTUS_TOKEN || ''

export const dynamic = 'force-dynamic'
export const revalidate = 60

export interface VodItem {
  id: string
  stream_name: string
  hls_master_url: string
  subtitle_url: string
  duration_secs: number
  thumbnail_url: string | null
  status: string
  date_created: string
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const limit = Math.min(Math.max(0, parseInt(searchParams.get('limit') ?? '12', 10)), 50)
  const offset = Math.max(0, parseInt(searchParams.get('offset') ?? '0', 10))

  try {
    const params = new URLSearchParams({
      'filter[status][_eq]': 'published',
      'sort': '-date_created',
      'limit': String(limit),
      'offset': String(offset),
      'fields': 'id,stream_name,hls_master_url,subtitle_url,duration_secs,thumbnail_url,status,date_created',
    })

    const res = await fetch(`${CMS_URL}/items/vod_recordings?${params}`, {
      headers: {
        'Authorization': `Bearer ${CMS_TOKEN}`,
        'Accept': 'application/json',
      },
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(8000),
    })

    if (!res.ok) {
      return NextResponse.json({ items: [], total: 0 })
    }

    const json = await res.json()
    return NextResponse.json({
      items: json.data ?? [],
      total: json.meta?.total_count ?? 0,
    })
  } catch {
    return NextResponse.json({ items: [], total: 0 })
  }
}
