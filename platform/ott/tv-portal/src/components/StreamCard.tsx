import Link from 'next/link'
import styles from './StreamCard.module.css'

interface StreamCardProps {
  title: string
  href: string
  badge: string
  badgeVariant: 'live' | 'vod'
  meta?: string
  thumbnailUrl?: string
}

export default function StreamCard({
  title, href, badge, badgeVariant, meta, thumbnailUrl,
}: StreamCardProps) {
  return (
    <Link href={href} className={styles.card}>
      <div className={styles.thumb}>
        {thumbnailUrl ? (
          // Next.js <Image> would be ideal but we keep deps minimal
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbnailUrl} alt={title} className={styles.thumbImg} loading="lazy" />
        ) : (
          <div className={styles.thumbPlaceholder} aria-hidden="true">▶</div>
        )}
        <span className={`${styles.badge} ${styles[`badge_${badgeVariant}`]}`}>{badge}</span>
      </div>
      <div className={styles.info}>
        <p className={styles.title}>{title}</p>
        {meta && <span className={styles.meta}>{meta}</span>}
      </div>
    </Link>
  )
}
