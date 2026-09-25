'use client'
// VideoPlayer — HLS.js player with live/VOD auto-detection
import { useEffect, useRef, useState } from 'react'
import styles from './VideoPlayer.module.css'

interface Props {
  streamName: string
  liveHlsUrl: string
  vodHlsUrl:  string
}

export default function VideoPlayer({ streamName, liveHlsUrl, vodHlsUrl }: Props) {
  const videoRef  = useRef<HTMLVideoElement>(null)
  const hlsRef    = useRef<import('hls.js').default | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode,  setMode]  = useState<'live' | 'vod' | 'loading'>('loading')
  const [quality, setQuality] = useState<string>('Auto')
  const [levels, setLevels]   = useState<string[]>([])

  useEffect(() => {
    let cancelled = false

    async function init() {
      const Hls = (await import('hls.js')).default
      if (cancelled) return

      const video = videoRef.current
      if (!video) return

      // Test live URL first; fall back to VOD
      const tryLive = await fetch(liveHlsUrl, { method: 'HEAD', signal: AbortSignal.timeout(3000) })
        .then(r => r.ok)
        .catch(() => false)

      const srcUrl = tryLive ? liveHlsUrl : vodHlsUrl
      if (!cancelled) setMode(tryLive ? 'live' : 'vod')

      if (Hls.isSupported()) {
        const hls = new Hls({
          enableWorker: true,
          lowLatencyMode: tryLive,
          maxBufferLength: tryLive ? 10 : 60,
          liveSyncDurationCount: tryLive ? 3 : undefined,
        })
        hlsRef.current = hls
        hls.loadSource(srcUrl)
        hls.attachMedia(video)

        hls.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
          if (cancelled) return
          const qs = ['Auto', ...data.levels.map((l, i) => `${l.height}p (level ${i})`)]
          setLevels(qs)
          video.play().catch(() => {/* autoplay blocked — user must click */})
        })

        hls.on(Hls.Events.ERROR, (_, data) => {
          if (data.fatal) {
            setError(`Stream error: ${data.details}`)
          }
        })
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        // Safari native HLS
        video.src = srcUrl
        video.play().catch(() => {})
        if (!cancelled) setMode(tryLive ? 'live' : 'vod')
      } else {
        setError('Your browser does not support HLS video playback.')
      }
    }

    init()

    return () => {
      cancelled = true
      hlsRef.current?.destroy()
      hlsRef.current = null
    }
  }, [liveHlsUrl, vodHlsUrl])

  function handleQualityChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const val = e.target.value
    setQuality(val)
    if (!hlsRef.current) return
    if (val === 'Auto') {
      hlsRef.current.currentLevel = -1
    } else {
      const idx = parseInt(val.match(/level (\d+)/)?.[1] ?? '-1', 10)
      hlsRef.current.currentLevel = idx
    }
  }

  return (
    <div className={styles.wrap}>
      {mode === 'loading' && (
        <div className={styles.overlay}>Loading stream…</div>
      )}
      {error && (
        <div className={styles.errorOverlay}>
          <p>⚠ {error}</p>
          <p className={styles.errorHint}>The stream may have ended or is not yet available.</p>
        </div>
      )}

      <video
        ref={videoRef}
        className={styles.video}
        controls
        playsInline
        crossOrigin="anonymous"
        aria-label={`${streamName} video player`}
      />

      {levels.length > 1 && (
        <div className={styles.controls}>
          <label className={styles.qualityLabel} htmlFor="quality-select">Quality</label>
          <select
            id="quality-select"
            className={styles.qualitySelect}
            value={quality}
            onChange={handleQualityChange}
          >
            {levels.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
          {mode === 'live' && <span className={styles.liveTag}>● LIVE</span>}
        </div>
      )}
    </div>
  )
}
