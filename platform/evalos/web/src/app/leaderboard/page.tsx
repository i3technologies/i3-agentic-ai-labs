import { redirect } from 'next/navigation'

/**
 * Leaderboard disabled — redirects to dashboard.
 * Re-enable by restoring the full page implementation.
 */
export default function LeaderboardPage() {
  redirect('/dashboard')
}
