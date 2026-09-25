import { Suspense } from 'react'
import LiveGrid from '@/components/LiveGrid'
import VodGrid from '@/components/VodGrid'
import Header from '@/components/Header'
import styles from './page.module.css'

export const dynamic = 'force-dynamic'
export const revalidate = 30

export default function HomePage() {
  return (
    <div className={styles.page}>
      <Header />
      <main className={styles.main}>
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>
            <span className={styles.liveDot} aria-hidden="true" />
            Live Now
          </h2>
          <Suspense fallback={<GridSkeleton count={2} />}>
            <LiveGrid />
          </Suspense>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>On Demand</h2>
          <Suspense fallback={<GridSkeleton count={6} />}>
            <VodGrid />
          </Suspense>
        </section>
      </main>

      <footer className={styles.footer}>
        <p>© {new Date().getFullYear()} i3 Technologies Academy · Powered by IBM Cloud ROKS</p>
      </footer>
    </div>
  )
}

function GridSkeleton({ count }: { count: number }) {
  return (
    <div className={styles.grid}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={styles.skeleton} />
      ))}
    </div>
  )
}
