import type { VodItem } from '@/app/api/streams/vod/route'
import StreamCard from './StreamCard'
import styles from './Grid.module.css'

async function getVodItems(): Promise<VodItem[]> {
  try {
    const cmsUrl = process.env.DIRECTUS_INTERNAL_URL || 'http://directus.i3-ott.svc.cluster.local:8055'
    const token  = process.env.DIRECTUS_TOKEN || ''
    const params = new URLSearchParams({
      'filter[status][_eq]': 'published',
      'sort': '-date_created',
      'limit': '12',
      'fields': 'id,stream_name,hls_master_url,subtitle_url,duration_secs,thumbnail_url,date_created',
    })
    const res = await fetch(`${cmsUrl}/items/vod_recordings?${params}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(8000),
    })
    if (!res.ok) return []
    const json = await res.json()
    return json.data ?? []
  } catch {
    return []
  }
}

function formatDuration(secs: number): string {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default async function VodGrid() {
  const items = await getVodItems()

  if (items.length === 0) {
    return (
      <div className={styles.empty}>
        <span className={styles.emptyIcon}>🎬</span>
        <p>No recordings available yet.</p>
        <span className={styles.emptyHint}>Recordings appear here after a live class ends.</span>
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <StreamCard
          key={item.id}
          title={item.stream_name}
          href={`/watch/${encodeURIComponent(item.stream_name)}`}
          badge={formatDuration(item.duration_secs)}
          badgeVariant="vod"
          meta={new Date(item.date_created).toLocaleDateString('en-KE', {
            year: 'numeric', month: 'short', day: 'numeric',
          })}
          thumbnailUrl={item.thumbnail_url ?? undefined}
        />
      ))}
    </div>
  )
}
