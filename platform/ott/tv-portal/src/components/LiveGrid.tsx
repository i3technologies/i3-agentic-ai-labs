import type { LiveStream } from '@/app/api/streams/live/route'
import StreamCard from './StreamCard'
import styles from './Grid.module.css'

async function getLiveStreams(): Promise<LiveStream[]> {
  try {
    // Server-side fetch during SSR — use internal URL directly
    const omeUrl = process.env.OME_INTERNAL_URL || 'http://ome-origin.i3-ott.svc.cluster.local:8081'
    const res = await fetch(`${omeUrl}/v1/stats/current`, {
      headers: { Accept: 'application/json' },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(4000),
    })
    if (!res.ok) return []
    const data = await res.json()
    const hlsBase = process.env.NEXT_PUBLIC_HLS_BASE_URL || 'https://stream.i3technologies.co.ke'
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
    return streams
  } catch {
    return []
  }
}

export default async function LiveGrid() {
  const streams = await getLiveStreams()

  if (streams.length === 0) {
    return (
      <div className={styles.empty}>
        <span className={styles.emptyIcon}>📡</span>
        <p>No live streams right now.</p>
        <span className={styles.emptyHint}>Check back soon or browse On Demand content below.</span>
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      {streams.map((s) => (
        <StreamCard
          key={`${s.app}/${s.name}`}
          title={s.name}
          href={`/watch/${encodeURIComponent(s.name)}`}
          badge="LIVE"
          badgeVariant="live"
          meta={`${(s.bitrate / 1000).toFixed(0)} kbps`}
        />
      ))}
    </div>
  )
}
