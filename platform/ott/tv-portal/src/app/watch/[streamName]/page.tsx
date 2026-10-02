// Watch page: /watch/[streamName]
import { Suspense } from 'react'
import Link from 'next/link'
import VideoPlayer from '@/components/VideoPlayer'
import styles from './page.module.css'

// Next.js 15: params is a Promise — must be awaited
interface Props {
  params: Promise<{ streamName: string }>
}

export default async function WatchPage({ params }: Props) {
  const { streamName } = await params
  const hlsBase = process.env.NEXT_PUBLIC_HLS_BASE_URL || 'https://stream.i3technologies.co.ke'

  // Live stream URL served by nginx-hls → OvenMediaEngine
  const liveHlsUrl = `${hlsBase}/hls/live/${streamName}/llhls.m3u8`
  // VOD URL served by nginx-hls → SeaweedFS S3
  const vodHlsUrl  = `${hlsBase}/vod/${streamName}/hls/master.m3u8`

  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <Link href="/" className={styles.back}>← Back to i3 TV</Link>
        <span className={styles.title}>{decodeURIComponent(streamName)}</span>
      </nav>

      <div className={styles.playerWrap}>
        <Suspense fallback={<div className={styles.playerPlaceholder}>Loading player…</div>}>
          <VideoPlayer
            streamName={streamName}
            liveHlsUrl={liveHlsUrl}
            vodHlsUrl={vodHlsUrl}
          />
        </Suspense>
      </div>

      <div className={styles.meta}>
        <h1 className={styles.streamTitle}>{decodeURIComponent(streamName)}</h1>
        <p className={styles.streamDesc}>
          i3 Technologies Academy · Live &amp; On-Demand Streaming
        </p>
      </div>
    </div>
  )
}
