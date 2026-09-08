import pool from '@/lib/db'
import Link from 'next/link'
import Image from 'next/image'

interface VerifyPageProps {
  params: { code: string }
}

async function lookupCertificate(code: string) {
  const { rows } = await pool.query(
    `SELECT student_name, student_email, exam_code, exam_title, pct_score, issued_at
     FROM certificates WHERE verify_code = $1`,
    [code.toUpperCase()]
  )
  return rows[0] ?? null
}

export default async function VerifyPage({ params }: VerifyPageProps) {
  const cert = await lookupCertificate(params.code)

  return (
    <div className="min-h-[calc(100vh-3.5rem)] bg-slate-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Card */}
        <div className={`bg-white rounded-2xl border-2 shadow-xl overflow-hidden ${cert ? 'border-green-400' : 'border-red-300'}`}>

          {/* Header stripe */}
          <div className={`px-8 py-5 flex items-center gap-4 ${cert ? 'bg-green-600' : 'bg-red-500'}`}>
            <span className="text-3xl">{cert ? '✅' : '❌'}</span>
            <div>
              <div className="text-white font-bold text-lg">
                {cert ? 'Certificate Verified' : 'Certificate Not Found'}
              </div>
              <div className="text-white/80 text-sm">
                {cert ? 'This credential is authentic.' : 'This code does not match any issued certificate.'}
              </div>
            </div>
            <div className="ml-auto">
              <Image src="/i3-logo.svg" alt="i3" width={36} height={13} className="brightness-0 invert opacity-80" />
            </div>
          </div>

          {/* Body */}
          <div className="px-8 py-6">
            {cert ? (
              <dl className="space-y-4">
                <div>
                  <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Recipient</dt>
                  <dd className="text-xl font-bold text-slate-900">{cert.student_name}</dd>
                  <dd className="text-sm text-slate-500">{cert.student_email}</dd>
                </div>
                <div className="h-px bg-slate-100" />
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Examination</dt>
                    <dd className="text-sm font-semibold text-slate-800">{cert.exam_code}</dd>
                    <dd className="text-xs text-slate-500">{cert.exam_title}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Score</dt>
                    <dd className="text-2xl font-bold text-green-700">{Math.round(Number(cert.pct_score))}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Date Issued</dt>
                    <dd className="text-sm font-medium text-slate-700">
                      {new Date(cert.issued_at).toLocaleDateString('en-GB', {
                        day: 'numeric', month: 'long', year: 'numeric',
                      })}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Issued by</dt>
                    <dd className="text-sm font-medium text-slate-700">i3 Technologies</dd>
                    <dd className="text-xs text-slate-500">Nairobi, Kenya</dd>
                  </div>
                </div>
                <div className="h-px bg-slate-100" />
                <div>
                  <dt className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1">Verification Code</dt>
                  <dd className="font-mono text-sm font-bold text-slate-700 tracking-widest">
                    {params.code.toUpperCase()}
                  </dd>
                </div>
              </dl>
            ) : (
              <div className="text-center py-4">
                <p className="text-slate-600 text-sm mb-2">
                  The code <span className="font-mono font-bold text-slate-800">{params.code.toUpperCase()}</span> was not found.
                </p>
                <p className="text-slate-400 text-xs">
                  Ensure you have entered the full code exactly as shown on the certificate.
                </p>
              </div>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          <Link href="/" className="hover:underline">EvalOS</Link>
          {' '}·{' '}i3 Technologies · Nairobi, Kenya
        </p>
      </div>
    </div>
  )
}
