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

// ─── Styles ───────────────────────────────────────────────────────────────────
const W = 841.89  // A4 landscape width  (pt)
const H = 595.28  // A4 landscape height (pt)

const s = StyleSheet.create({
  page: {
    width: W,
    height: H,
    backgroundColor: '#ffffff',
    fontFamily: 'Helvetica',
    flexDirection: 'column',
  },

  // ── Left dark sidebar ──────────────────────────────────────────────────────
  sidebar: {
    position: 'absolute',
    left: 0,
    top: 0,
    width: 220,
    height: H,
    backgroundColor: '#0f172a',
  },
  sidebarAccent: {
    position: 'absolute',
    left: 0,
    top: 0,
    width: 6,
    height: H,
    backgroundColor: '#3b82f6',
  },

  // ── Sidebar content ────────────────────────────────────────────────────────
  sidebarContent: {
    position: 'absolute',
    left: 0,
    top: 0,
    width: 220,
    height: H,
    paddingLeft: 28,
    paddingRight: 20,
    paddingTop: 52,
    paddingBottom: 36,
    flexDirection: 'column',
    justifyContent: 'space-between',
  },
  sidebarTop: {},
  certOfLabel: {
    fontSize: 8,
    color: '#3b82f6',
    letterSpacing: 2.5,
    textTransform: 'uppercase',
    marginBottom: 10,
    marginTop: 28,
  },
  certOfTitle: {
    fontSize: 17,
    fontFamily: 'Helvetica-Bold',
    color: '#ffffff',
    lineHeight: 1.35,
  },
  sidebarDivider: {
    height: 1,
    backgroundColor: '#1e3a5f',
    marginTop: 28,
    marginBottom: 28,
    marginRight: 0,
  },

  // Score circle on sidebar
  scoreSection: {
    alignItems: 'flex-start',
    marginBottom: 28,
  },
  scoreCircleWrap: {
    width: 90,
    height: 90,
    marginBottom: 10,
  },
  scoreValueSide: {
    fontSize: 30,
    fontFamily: 'Helvetica-Bold',
    color: '#4ade80',
    textAlign: 'center',
  },
  scoreLabelSide: {
    fontSize: 8,
    color: '#22c55e',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    textAlign: 'center',
  },

  // Verify block at bottom of sidebar
  verifySection: {},
  verifyLabel: {
    fontSize: 7,
    color: '#475569',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  verifyCode: {
    fontSize: 11,
    fontFamily: 'Helvetica-Bold',
    color: '#60a5fa',
    letterSpacing: 1.8,
  },
  verifyUrl: {
    fontSize: 7,
    color: '#334155',
    marginTop: 4,
  },

  // ── Main content area ──────────────────────────────────────────────────────
  main: {
    position: 'absolute',
    left: 220,
    top: 0,
    width: W - 220,
    height: H,
    paddingLeft: 52,
    paddingRight: 50,
    paddingTop: 52,
    paddingBottom: 36,
    flexDirection: 'column',
    justifyContent: 'space-between',
  },

  // Logo row at top-right
  logoRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    marginBottom: 0,
  },
  logoTagline: {
    fontSize: 9,
    color: '#94a3b8',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginLeft: 10,
    marginTop: 6,
  },

  // Centre body
  body: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingTop: 10,
  },
  presentedTo: {
    fontSize: 9,
    color: '#94a3b8',
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: 12,
  },
  studentName: {
    fontSize: 40,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    marginBottom: 6,
  },
  studentEmail: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 24,
  },
  bodyText: {
    fontSize: 11.5,
    color: '#334155',
    lineHeight: 1.75,
    maxWidth: 460,
    marginBottom: 0,
  },
  bodyBold: {
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
  },

  // ── Meta panel (the landscape block) ──────────────────────────────────────
  metaPanel: {
    marginTop: 32,
    flexDirection: 'row',
    gap: 0,
  },
  metaCard: {
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderLeftWidth: 3,
    borderLeftColor: '#3b82f6',
    marginRight: 12,
    minWidth: 148,
  },
  metaCardKey: {
    fontSize: 7.5,
    color: '#94a3b8',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginBottom: 5,
  },
  metaCardValue: {
    fontSize: 11,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    lineHeight: 1.3,
  },

  // ── Bottom footer strip ────────────────────────────────────────────────────
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  footerLeft: {
    fontSize: 8,
    color: '#94a3b8',
  },
  footerRight: {
    fontSize: 8,
    color: '#94a3b8',
    textAlign: 'right',
  },
  stamp: {
    fontSize: 8,
    color: '#22c55e',
    fontFamily: 'Helvetica-Bold',
    letterSpacing: 1,
    textTransform: 'uppercase',
    borderWidth: 1.5,
    borderColor: '#22c55e',
    borderRadius: 3,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
})

// ─── i3 Logo SVG component ─────────────────────────────────────────────────
function I3Logo({ size = 52 }: { size?: number }) {
  // Scale from viewBox 0 0 120 40
  const scale = size / 40
  const w = 120 * scale
  const h = 40 * scale
  return (
    <Svg width={w} height={h} viewBox="0 0 120 40">
      {/* i — dot */}
      <Circle cx="12" cy="8" r="4" fill="#60A5FA" />
      {/* i — stem */}
      <Rect x="9" y="15" width="6" height="20" rx="3" fill="#60A5FA" />
      {/* 3 — numeral */}
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

// ─── Score badge — solid green circle with score text inside ─────────────
function ScoreBadge({ pct }: { pct: number }) {
  return (
    <Svg width={90} height={90} viewBox="0 0 90 90">
      {/* Outer ring track */}
      <Circle cx="45" cy="45" r="40" fill="#14532d" />
      {/* Inner fill */}
      <Circle cx="45" cy="45" r="34" fill="#052e16" />
    </Svg>
  )
}

// ─── Props ─────────────────────────────────────────────────────────────────
interface CertProps {
  studentName: string
  studentEmail: string
  examCode: string
  examTitle: string
  pctScore: number
  verifyCode: string
  issuedAt: Date
}

// ─── Certificate ───────────────────────────────────────────────────────────
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

  // Derive set label e.g. "Practice Set 1" from examCode "C1000-207-SET1"
  const setMatch = examCode.match(/SET(\d+)$/i)
  const setNum = setMatch ? setMatch[1] : ''
  const examDisplay = setNum
    ? `C1000-207 Practice Set ${setNum}`
    : examCode

  return (
    <Document
      title={`i3 EvalOS Certificate — ${studentName}`}
      author="i3 Technologies"
      subject={`${examCode} Completion Certificate`}
      creator="EvalOS"
    >
      <Page size="A4" orientation="landscape" style={s.page}>

        {/* ── Dark sidebar ──────────────────────────────────────── */}
        <View style={s.sidebar} />
        <View style={s.sidebarAccent} />

        <View style={s.sidebarContent}>
          {/* i3 logo full-size on sidebar */}
          <View style={s.sidebarTop}>
            <I3Logo size={72} />

            <Text style={s.certOfLabel}>Certificate of</Text>
            <Text style={s.certOfTitle}>Examination{'\n'}Completion</Text>

            <View style={s.sidebarDivider} />

            {/* Score ring */}
            <View style={s.scoreSection}>
              <View style={s.scoreCircleWrap}>
                <ScoreBadge pct={score} />
              </View>
              <Text style={s.scoreValueSide}>{score}%</Text>
              <Text style={s.scoreLabelSide}>Final Score</Text>
            </View>
          </View>

          {/* Verify code pinned to bottom */}
          <View style={s.verifySection}>
            <Text style={s.verifyLabel}>Verification Code</Text>
            <Text style={s.verifyCode}>{verifyCode}</Text>
            <Text style={s.verifyUrl}>evalos.i3technologies.co.ke/verify/{verifyCode}</Text>
          </View>
        </View>

        {/* ── Main content ─────────────────────────────────────── */}
        <View style={s.main}>

          {/* Logo top-right */}
          <View style={s.logoRow}>
            <I3Logo size={44} />
            <Text style={s.logoTagline}>Technologies · Nairobi</Text>
          </View>

          {/* Recipient */}
          <View style={s.body}>
            <Text style={s.presentedTo}>This certifies that</Text>
            <Text style={s.studentName}>{studentName}</Text>
            <Text style={s.studentEmail}>{studentEmail}</Text>

            <Text style={s.bodyText}>
              has successfully completed the{' '}
              <Text style={s.bodyBold}>{examDisplay}</Text>
              {' '}practice examination of the{' '}
              <Text style={s.bodyBold}>IBM watsonx Orchestrate v2 Administrator</Text>
              {' '}(C1000-207) certification programme, achieving a passing score
              and demonstrating proficiency across all examined knowledge domains.
            </Text>

            {/* ── Meta cards row — the landscape detail block ── */}
            <View style={s.metaPanel}>
              <View style={s.metaCard}>
                <Text style={s.metaCardKey}>Examination</Text>
                <Text style={s.metaCardValue}>{examDisplay}</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaCardKey}>Pass Threshold</Text>
                <Text style={s.metaCardValue}>90%</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaCardKey}>Date Issued</Text>
                <Text style={s.metaCardValue}>{dateStr}</Text>
              </View>
              <View style={s.metaCard}>
                <Text style={s.metaCardKey}>Platform</Text>
                <Text style={s.metaCardValue}>EvalOS · i3 Technologies</Text>
              </View>
            </View>
          </View>

          {/* Footer */}
          <View style={s.footer}>
            <Text style={s.footerLeft}>
              i3 Technologies Ltd · Nairobi, Kenya · evalos.i3technologies.co.ke
            </Text>
            <Text style={s.stamp}>✓ Verified Pass</Text>
            <Text style={s.footerRight}>
              IBM C1000-207 · watsonx Orchestrate v2 Administrator
            </Text>
          </View>

        </View>

      </Page>
    </Document>
  )
}
