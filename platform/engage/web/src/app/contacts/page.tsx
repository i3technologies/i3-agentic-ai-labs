import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { Shell } from '@/components/Shell'
import { ContactsClient } from './ContactsClient'

export default async function ContactsPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/login')
  return <Shell><ContactsClient /></Shell>
}
