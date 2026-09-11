import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'
import { BriefingClient } from './briefing-client'

export const dynamic = 'force-dynamic'

export default async function BriefingPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Strategy Briefing</h1>
        <p className="text-gray-400 text-sm mt-1">
          Daily campaign intelligence powered by Dawa AI · {new Date().toLocaleDateString('en-KE', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
          })}
        </p>
      </div>
      <BriefingClient userName={session.user?.name ?? 'Campaign Manager'} />
    </div>
  )
}
