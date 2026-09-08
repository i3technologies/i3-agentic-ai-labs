import React from 'react'
import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Font,
} from '@react-pdf/renderer'

Font.register({
  family: 'Helvetica',
  fonts: [],
})

const styles = StyleSheet.create({
  page: {
    backgroundColor: '#ffffff',
    padding: 0,
    fontFamily: 'Helvetica',
  },
  // Dark header band
  header: {
    backgroundColor: '#0f172a',
    paddingVertical: 40,
    paddingHorizontal: 50,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logoText: {
    color: '#60a5fa',
    fontSize: 36,
    fontFamily: 'Helvetica-Bold',
    letterSpacing: 2,
  },
  headerSub: {
    color: '#94a3b8',
    fontSize: 11,
    marginTop: 4,
    letterSpacing: 1,
  },
  verifyBlock: {
    alignItems: 'flex-end',
  },
  verifyLabel: {
    color: '#475569',
    fontSize: 8,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 3,
  },
  verifyCode: {
    color: '#60a5fa',
    fontSize: 13,
    fontFamily: 'Helvetica-Bold',
    letterSpacing: 2,
  },
  // Body
  body: {
    paddingHorizontal: 60,
    paddingVertical: 40,
    flexGrow: 1,
  },
  certLabel: {
    fontSize: 10,
    color: '#94a3b8',
    letterSpacing: 3,
    textTransform: 'uppercase',
    marginBottom: 20,
  },
  certTitle: {
    fontSize: 28,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    marginBottom: 8,
  },
  certSubtitle: {
    fontSize: 14,
    color: '#334155',
    marginBottom: 32,
  },
  divider: {
    height: 1,
    backgroundColor: '#e2e8f0',
    marginBottom: 32,
  },
  // Recipient block
  presentedTo: {
    fontSize: 10,
    color: '#94a3b8',
    letterSpacing: 2,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  studentName: {
    fontSize: 32,
    fontFamily: 'Helvetica-Bold',
    color: '#0f172a',
    marginBottom: 4,
  },
  studentEmail: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 28,
  },
  bodyText: {
    fontSize: 12,
    color: '#334155',
    lineHeight: 1.7,
    marginBottom: 8,
  },
  // Score badge
  scoreBadge: {
    marginTop: 24,
    marginBottom: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 20,
  },
  scoreBox: {
    backgroundColor: '#f0fdf4',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    minWidth: 100,
  },
  scoreValue: {
    fontSize: 32,
    fontFamily: 'Helvetica-Bold',
    color: '#166534',
  },
  scoreLabel: {
    fontSize: 9,
    color: '#16a34a',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  // Metadata table
  metaRow: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  metaLabel: {
    fontSize: 10,
    color: '#94a3b8',
    width: 120,
  },
  metaValue: {
    fontSize: 10,
    color: '#1e293b',
    fontFamily: 'Helvetica-Bold',
    flex: 1,
  },
  // Footer
  footer: {
    backgroundColor: '#f8fafc',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    paddingVertical: 20,
    paddingHorizontal: 60,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  footerLeft: {
    fontSize: 9,
    color: '#94a3b8',
  },
  footerRight: {
    fontSize: 9,
    color: '#94a3b8',
    textAlign: 'right',
  },
})

interface CertProps {
  studentName: string
  studentEmail: string
  examCode: string
  examTitle: string
  pctScore: number
  verifyCode: string
  issuedAt: Date
}

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

  return (
    <Document
      title={`i3 EvalOS Certificate — ${studentName}`}
      author="i3 Technologies"
      subject={`${examCode} Completion Certificate`}
      creator="EvalOS"
    >
      <Page size="A4" orientation="landscape" style={styles.page}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.logoText}>i3</Text>
            <Text style={styles.headerSub}>TECHNOLOGIES · NAIROBI</Text>
          </View>
          <View style={styles.verifyBlock}>
            <Text style={styles.verifyLabel}>Verification Code</Text>
            <Text style={styles.verifyCode}>{verifyCode}</Text>
          </View>
        </View>

        {/* Body */}
        <View style={styles.body}>
          <Text style={styles.certLabel}>Certificate of Completion</Text>
          <Text style={styles.certTitle}>IBM watsonx Orchestrate</Text>
          <Text style={styles.certSubtitle}>Associate Certification Practice — C1000-207</Text>
          <View style={styles.divider} />

          <Text style={styles.presentedTo}>This certifies that</Text>
          <Text style={styles.studentName}>{studentName}</Text>
          <Text style={styles.studentEmail}>{studentEmail}</Text>

          <Text style={styles.bodyText}>
            has successfully completed all six practice examination sets for the{' '}
            <Text style={{ fontFamily: 'Helvetica-Bold' }}>IBM {examCode}</Text> certification programme,
            demonstrating mastery of IBM watsonx Orchestrate across all seven knowledge domains.
          </Text>

          {/* Score badge */}
          <View style={styles.scoreBadge}>
            <View style={styles.scoreBox}>
              <Text style={styles.scoreValue}>{Math.round(pctScore)}%</Text>
              <Text style={styles.scoreLabel}>Final Score</Text>
            </View>
            <View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Examination</Text>
                <Text style={styles.metaValue}>{examTitle}</Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Pass threshold</Text>
                <Text style={styles.metaValue}>90%</Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Date issued</Text>
                <Text style={styles.metaValue}>{dateStr}</Text>
              </View>
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Platform</Text>
                <Text style={styles.metaValue}>EvalOS · i3 Technologies</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerLeft}>
            i3 Technologies Ltd · Nairobi, Kenya · evalos.i3technologies.co.ke
          </Text>
          <Text style={styles.footerRight}>
            Verify at evalos.i3technologies.co.ke/verify/{verifyCode}
          </Text>
        </View>
      </Page>
    </Document>
  )
}
