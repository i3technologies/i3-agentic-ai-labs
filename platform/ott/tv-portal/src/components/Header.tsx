import Link from 'next/link'
import styles from './Header.module.css'

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href="/" className={styles.logo}>
          <span className={styles.logoIcon} aria-hidden="true">▶</span>
          <span>i3 <strong>TV</strong></span>
        </Link>
        <nav className={styles.nav}>
          <Link href="/" className={styles.navLink}>Home</Link>
          <a
            href="https://sso.i3technologies.co.ke/realms/i3/account"
            className={styles.navLink}
            target="_blank"
            rel="noopener noreferrer"
          >
            My Account
          </a>
        </nav>
      </div>
    </header>
  )
}
