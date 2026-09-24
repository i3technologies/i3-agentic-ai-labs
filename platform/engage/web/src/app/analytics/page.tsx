import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import { AnalyticsClient } from './AnalyticsClient'

export default async function AnalyticsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  return <Shell><AnalyticsClient /></Shell>
}
