import React from 'react'
import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Svg,
  Circle,
  Rect,
  Path,
} from '@react-pdf/renderer'

// A4 landscape dimensions in points
const PW = 841.89
const PH = 595.28
const SIDEBAR = 226

const s = StyleSheet.create({
  page: {
    width: PW,
    height: PH,
    backgroundColor: '#ffffff',
    fontFamily: 'Helvetica',
  },

  // ── Sidebar (absolute, full height) ───────────────────────────────────────
  sidebarBg: {
    position: 'absolute',
    left: 0, top: 0,
    width: SIDEBAR, height: PH,
    backgroundColor: '#0f172a',
  },
  sidebarStripe: {
    position: 'absolute',
    left: 0, top: 0,
    width: 5, height: PH,
    backgroundColor: '#3b82f6',
  },
  sidebarInner: {
    position: 'absolute',
    left: 0, top: 0,
    width: SIDEBAR, height: PH,
    paddingTop: 44,
    paddingBottom: 32,
    paddingLeft: 26,
    paddingRight: 18,
    flexDirection: 'column',
    justifyContent: 'space-between',
  },

  // Sidebar top block
  sbTop: {},
  sbCertLabel: {
    fontSize: 7,
    color: '#3b82f6',
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginTop: 22,
    marginBottom: 6,
  },
  sbCertTitle: {
    fontSize: 15,
    fontFamily: 'Helvetica-Bold',
    color: '#ffffff',
    lineHeight: 1.4,
  },
  sbDivider: {
    height: 1,
    backgroundColor: '#1e3a5f',
    marginTop: 22,
    marginBottom: 22,
  },

  // Score on sidebar — plain box, no SVG text
  sbScoreBox: {
    backgroundColor: '#052e16',
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 16,
    alignItems: 'center',
    width: 110,
    marginBottom: 4,
  },
  sbScoreNum: {
    fontSize: 34,
    fontFamily: 'Helvetica-Bold',
    color: '#4ade80',
    textAlign: 'center',
  },
  sbScoreLabel: {
    fontSize: 7,
    color: '#22c55e',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    textAlign: 'center',
    marginTop: 3,
  },
  sbPassBadge: {
    marginTop: 10,
    backgroundColor: '#14532d',
    borderRadius: 4,
    paddingVertical: 4,
    paddingHorizontal: 10,
    width: 110,
  },
  sbPassText: {
    fontSize: 8,
    fontFamily: 'Helvetica-Bold',
    color: '#4ade80',
    textAlign: 'center',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },

  // Verify block at bottom of sidebar
  sbVerifyLabel: {
    fontSize: 7,
    color: '#475569',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  sbVerifyCode: {
    fontSize: 10,
    fontFamily: 'Helvetica-Bold',
    color: '#60a5fa',
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  sbVerifyUrl: {
    fontSize: 7,
    color: '#334155',
  },

  // ── Main panel ─────────────────────────────────────────────────────────────
  main: {
    position: 'absolute',
    left: SIDEBAR,
    top: 0,
    width: PW - SIDEBAR,
    height: PH,
    paddingLeft: 48,
    paddingRight: 44,
    paddingTop: 44,
    paddingBottom: 30,
    flexDirection: 'column',
    justifyContent: 'space-between',
  },

  // Top row: logo right-aligned
  topRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  topLogoTag: {
    fontSize: 8,
    color: '#94a3b8',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginLeft: 8,
    marginTop: 4,
  },

  // Centre recipient block
  recipient: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  presLabel: {
    fontSize: 8,
    color: '#94a3b8',
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  nameText: {
    fontSize: 36,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    marginBottom: 5,
  },
  emailText: {
    fontSize: 11,
    color: '#64748b',
    marginBottom: 18,
  },
  bodyLine1: {
    fontSize: 11,
    color: '#334155',
    lineHeight: 1.6,
    marginBottom: 2,
  },
  bodyLine2: {
    fontSize: 11,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    lineHeight: 1.6,
    marginBottom: 2,
  },
  bodyLine3: {
    fontSize: 11,
    color: '#334155',
    lineHeight: 1.6,
    marginBottom: 0,
  },

  // Meta cards row
  metaRow: {
    flexDirection: 'row',
    marginTop: 24,
  },
  metaCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 6,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderLeftWidth: 3,
    borderLeftColor: '#3b82f6',
    marginRight: 10,
    flex: 1,
  },
  metaKey: {
    fontSize: 7,
    color: '#94a3b8',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  metaVal: {
    fontSize: 10,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    lineHeight: 1.35,
  },

  // Footer
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  footerLeft: {
    fontSize: 7.5,
    color: '#94a3b8',
    flex: 1,
  },
  footerStamp: {
    fontSize: 7.5,
    fontFamily: 'Helvetica-Bold',
    color: '#16a34a',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    borderWidth: 1.5,
    borderColor: '#16a34a',
    borderRadius: 3,
    paddingVertical: 3,
    paddingHorizontal: 8,
    marginHorizontal: 12,
  },
  footerRight: {
    fontSize: 7.5,
    color: '#94a3b8',
    textAlign: 'right',
    flex: 1,
  },
})

// ── i3 Logo rendered as SVG primitives ────────────────────────────────────────
function I3Logo({ size }: { size: number }) {
  const w = (120 / 40) * size
  return (
    <Svg width={w} height={size} viewBox="0 0 120 40">
      <Circle cx="12" cy="8" r="4" fill="#60A5FA" />
      <Rect x="9" y="15" width="6" height="20" rx="3" fill="#60A5FA" />
      <Path
        d="M32 12 Q48 12 48 20 Q48 28 36 28 Q48 28 48 34 Q48 40 32 40"
        stroke="#60A5FA"
        strokeWidth="5.5"
        strokeLinecap="round"
        fill="none"
      />
    </Svg>
  )
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface CertProps {
  studentName: string
  studentEmail: string
  examCode: string
  examTitle: string
  pctScore: number
  verifyCode: string
  issuedAt: Date
}

// ── Certificate document ──────────────────────────────────────────────────────
export function CertificatePDF({
  studentName,
  studentEmail,
  examCode,
  examTitle,
  pctScore,
  verifyCode,
  issuedAt,
}: CertProps) {
  const dateStr = issuedAt.toLocaleDateString('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric',
  })
  const score = Math.round(pctScore)

  // "C1000-207-SET1" → "C1000-207 Practice Set 1"
  const setMatch = examCode.match(/SET(\d+)$/i)
  const setNum = setMatch ? setMatch[1] : ''
  const examDisplay = setNum ? `C1000-207 Practice Set ${setNum}` : examCode

  return (
    <Document
      title={`i3 EvalOS Certificate — ${studentName}`}
      author="i3 Technologies"
      subject={`${examCode} Completion Certificate`}
      creator="EvalOS"
    >
      <Page size="A4" orientation="landscape" style={s.page}>

        {/* ── Sidebar background + blue accent stripe ── */}
        <View style={s.sidebarBg} />
        <View style={s.sidebarStripe} />

        {/* ── Sidebar content ── */}
        <View style={s.sidebarInner}>

          {/* Top: logo + cert title */}
          <View style={s.sbTop}>
            <I3Logo size={60} />
            <Text style={s.sbCertLabel}>Certificate of</Text>
            <Text style={s.sbCertTitle}>{'Examination\nCompletion'}</Text>
            <View style={s.sbDivider} />

            {/* Score box */}
            <View style={s.sbScoreBox}>
              <Text style={s.sbScoreNum}>{score}%</Text>
              <Text style={s.sbScoreLabel}>Final Score</Text>
            </View>
            <View style={s.sbPassBadge}>
              <Text style={s.sbPassText}>PASS</Text>
            </View>
          </View>

          {/* Bottom: verification */}
          <View>
            <Text style={s.sbVerifyLabel}>Verification Code</Text>
            <Text style={s.sbVerifyCode}>{verifyCode}</Text>
            <Text style={s.sbVerifyUrl}>evalos.i3technologies.co.ke{'\n'}/verify/{verifyCode}</Text>
          </View>

        </View>

        {/* ── Main content panel ── */}
        <View style={s.main}>

          {/* Top-right logo */}
          <View style={s.topRow}>
            <I3Logo size={36} />
            <Text style={s.topLogoTag}>Technologies · Nairobi</Text>
          </View>

          {/* Recipient section */}
          <View style={s.recipient}>
            <Text style={s.presLabel}>This certifies that</Text>
            <Text style={s.nameText}>{studentName}</Text>
            <Text style={s.emailText}>{studentEmail}</Text>

            {/* Body text split into plain lines — no nested bold spans */}
            <Text style={s.bodyLine1}>has successfully completed the</Text>
            <Text style={s.bodyLine2}>{examDisplay}</Text>
            <Text style={s.bodyLine3}>
              practice examination of the IBM watsonx Orchestrate v2 Administrator (C1000-207){'\n'}
              certification programme, achieving a passing score across all examined knowledge domains.
            </Text>

            {/* Meta cards */}
            <View style={s.metaRow}>
              <View style={s.metaCard}>
                <Text style={s.metaKey}>Examination</Text>
                <Text style={s.metaVal}>{examDisplay}</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaKey}>Pass Threshold</Text>
                <Text style={s.metaVal}>90%</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaKey}>Date Issued</Text>
                <Text style={s.metaVal}>{dateStr}</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaKey}>Platform</Text>
                <Text style={s.metaVal}>EvalOS · i3 Technologies</Text>
              </View>
            </View>
          </View>

          {/* Footer */}
          <View style={s.footerRow}>
            <Text style={s.footerLeft}>
              i3 Technologies Ltd · Nairobi, Kenya · evalos.i3technologies.co.ke
            </Text>
            <Text style={s.footerStamp}>Verified Pass</Text>
            <Text style={s.footerRight}>
              IBM C1000-207 · watsonx Orchestrate v2 Administrator
            </Text>
          </View>

        </View>

      </Page>
    </Document>
  )
}
