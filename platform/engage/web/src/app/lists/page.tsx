import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import { ListsClient } from './ListsClient'

export default async function ListsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  return <Shell><ListsClient /></Shell>
}
