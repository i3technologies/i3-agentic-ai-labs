import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Image from 'next/image'
import { authOptions } from '@/lib/auth'
import SignInButton from './sign-in-button'

export default async function HomePage() {
  const session = await getServerSession(authOptions)
  if (session) redirect('/dashboard')

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-slate-800">
      <div className="w-full max-w-md px-6">

        {/* Logo block */}
        <div className="text-center mb-10">
          <div className="inline-flex flex-col items-center gap-4 mb-2">
            {/* i3 branded orb — displayed large on login screen */}
            <div className="relative">
              <div className="absolute inset-0 rounded-full blur-2xl opacity-30 scale-110"
                   style={{ background: 'radial-gradient(circle, #8eadd4 0%, #3b5a8a 70%)' }}/>
              <div className="relative bg-gradient-to-b from-slate-800 to-slate-900 border border-slate-600/50 rounded-3xl p-6 shadow-2xl">
                <Image
                  src="/i3-logo.svg"
                  alt="i3 Technologies"
                  width={160}
                  height={44}
                  priority
                  className="drop-shadow-lg"
                />
              </div>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight">
                EvalOS
              </h1>
              <p className="mt-1.5 text-slate-400 text-sm">
                IBM watsonx Orchestrate &nbsp;·&nbsp; <span className="font-semibold text-blue-400">C1000-207</span>
              </p>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white border border-slate-200 rounded-2xl shadow-xl p-8">
          <h2 className="text-lg font-semibold text-slate-800 mb-1">
            Sign in to continue
          </h2>
          <p className="text-sm text-slate-500 mb-6">
            Use your i3 Technologies SSO credentials to access practice exams.
          </p>

          <SignInButton />

          <p className="mt-5 text-xs text-slate-400 text-center">
            Access is restricted to enrolled i3 students and staff.
          </p>
        </div>

        {/* Feature bullets */}
        <ul className="mt-8 space-y-2.5">
          {[
              ['360 practice questions across 7 IBM watsonx domains', '📚'],
              ['6 timed practice sets — 90 min, pass at 90%', '⏱'],
              ['AI Study Coach — personalised 3-day study plan', '🤖'],
              ['AI Interview Round + Coding Labs', '💻'],
            ].map(([label, icon]) => (
            <li key={label} className="flex items-center gap-3 text-sm text-slate-300">
              <span className="text-base leading-none">{icon}</span>
              {label}
            </li>
          ))}
        </ul>

        <p className="mt-8 text-center text-xs text-slate-500">
          i3 Technologies &nbsp;·&nbsp; Nairobi, Kenya
        </p>
      </div>
    </div>
  )
}
