import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import { CampaignsClient } from './CampaignsClient'

export default async function CampaignsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  return <Shell><CampaignsClient /></Shell>
}
