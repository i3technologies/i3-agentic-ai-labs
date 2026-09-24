import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import { SmsClient } from './SmsClient'

export default async function SmsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  return <Shell><SmsClient /></Shell>
}
