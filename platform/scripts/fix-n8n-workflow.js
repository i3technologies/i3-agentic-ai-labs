// Run inside n8n pod: node /tmp/fix-n8n-workflow.js
// Updates both the SMTP credential and the workflow nodes to match EvalOS payload fields

const { execSync } = require('child_process');

const CRED_ID   = 'd035f766-f0fe-46a4-9962-1db39acfad4e';
const WF_ID     = '319537be-cd59-4645-9b5e-f183acfecf7e';
const ENC_DATA  = 'U2FsdGVkX1+X+BkdmjdFYJEDL0QVfNJ6pg+01d+ZZ0yvMSbyxO1LIH8pyVIioh5/75Sp5hTfKkR3b8zdyXXgyaqOgyGj2SiyZz2aUbxYoDMPiW9MbrvnDPobKrOCJ4AK3SUTZvO9eTEhcfHzbrz3BgQ2UGt7SsVpLuFLdYqov/0=';

// ── Email HTML templates ───────────────────────────────────────────────────

const passHtml = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">
    <span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>
    <span style="color:#94a3b8;font-size:11px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span>
  </div>
  <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px">
    <h2 style="color:#166534;margin:0 0 10px">Congratulations, {{ $json.body.studentName }}!</h2>
    <p style="color:#374151;font-size:15px;margin:0">
      You passed <strong>{{ $json.body.examCode }}</strong> with
      <strong style="color:#16a34a;font-size:18px">{{ $json.body.score }}%</strong>
    </p>
  </div>
  <div style="padding:24px;background:#fff">
    <p style="color:#374151">
      The next set is now unlocked on your dashboard. Keep going — you are on your way to the IBM C1000-207 certification!
    </p>
    <a href="https://evalos.i3technologies.co.ke/dashboard"
       style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">
      Go to Dashboard
    </a>
  </div>
  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
    EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; evalos.i3technologies.co.ke
  </div>
</div>`;

const failHtml = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">
    <span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>
    <span style="color:#94a3b8;font-size:11px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span>
  </div>
  <div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px">
    <h2 style="color:#991b1b;margin:0 0 10px">EvalOS Result — {{ $json.body.examCode }}</h2>
    <p style="color:#374151;font-size:15px;margin:0">
      Hi {{ $json.body.studentName }}, you scored
      <strong style="color:#dc2626;font-size:18px">{{ $json.body.score }}%</strong>.
      You need <strong>90%</strong> to pass.
    </p>
  </div>
  <div style="padding:24px;background:#fff">
    <p style="color:#374151">
      Review the detailed explanations on your results page to understand where to improve, then retake when ready.
      You have {{ $json.body.attemptsLeft }} attempt(s) remaining on this set.
    </p>
    <a href="https://evalos.i3technologies.co.ke/dashboard"
       style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">
      Review Results
    </a>
  </div>
  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
    EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; evalos.i3technologies.co.ke
  </div>
</div>`;

const inviteHtml = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">
    <span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>
    <span style="color:#94a3b8;font-size:11px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span>
  </div>
  <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:24px">
    <h2 style="color:#1e40af;margin:0 0 10px">Your IBM C1000-207 Practice Exams Are Ready</h2>
    <p style="color:#374151;font-size:15px;margin:0">Hi {{ $json.body.studentName }}, you have been enrolled in the EvalOS certification practice platform.</p>
  </div>
  <div style="padding:24px;background:#fff">
    <p style="color:#374151">Complete all 6 practice sets with a score of <strong>90% or higher</strong> to earn your i3 completion certificate and unlock your IBM certification lab access.</p>
    <ul style="color:#374151;line-height:1.8">
      <li>6 practice exam sets (60 questions each)</li>
      <li>90-minute timed exam per set</li>
      <li>Instant results with full explanations</li>
      <li>Completion certificate on passing all sets</li>
    </ul>
    <a href="https://evalos.i3technologies.co.ke"
       style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">
      Start Your First Exam
    </a>
  </div>
  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
    EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; evalos.i3technologies.co.ke
  </div>
</div>`;

const scoreHtml = `<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">
    <span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>
    <span style="color:#94a3b8;font-size:11px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span>
  </div>
  <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:24px">
    <h2 style="color:#0f172a;margin:0 0 10px">Your EvalOS Score Report</h2>
    <p style="color:#374151;font-size:15px;margin:0">Hi {{ $json.body.studentName }}, here is your latest exam result.</p>
  </div>
  <div style="padding:24px;background:#fff">
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Exam</td><td style="padding:8px 0;font-weight:bold;color:#0f172a">{{ $json.body.examCode }}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Score</td><td style="padding:8px 0;font-weight:bold;font-size:20px;color:{{ $json.body.passed ? '#16a34a' : '#dc2626' }}">{{ $json.body.score }}%</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Result</td><td style="padding:8px 0;font-weight:bold;color:{{ $json.body.passed ? '#16a34a' : '#dc2626' }}">{{ $json.body.passed ? 'PASS' : 'FAIL' }}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;font-size:13px">Pass mark</td><td style="padding:8px 0;color:#374151">90%</td></tr>
    </table>
    <a href="https://evalos.i3technologies.co.ke/dashboard"
       style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:16px">
      View Full Results
    </a>
  </div>
  <div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">
    EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya
  </div>
</div>`;

// ── Workflow nodes ─────────────────────────────────────────────────────────
const nodes = [
  {
    id: 'node-webhook',
    name: 'EvalOS Webhook',
    type: 'n8n-nodes-base.webhook',
    position: [0, 0],
    webhookId: 'evalos-events-hook',
    parameters: {
      path: 'evalos-events',
      options: {},
      httpMethod: 'POST',
      responseMode: 'onReceived'
    },
    typeVersion: 2
  },
  {
    id: 'node-router',
    name: 'Event Router',
    type: 'n8n-nodes-base.switch',
    position: [220, 0],
    parameters: {
      dataType: 'string',
      value1: '={{ $json.body.event }}',
      rules: {
        rules: [
          { value2: 'exam_submitted', output: 0 },
          { value2: 'exam_invite',    output: 1 },
          { value2: 'exam_score_report', output: 2 }
        ]
      },
      fallbackOutput: 0
    },
    typeVersion: 1
  },
  {
    id: 'node-pass-check',
    name: 'Passed?',
    type: 'n8n-nodes-base.if',
    position: [440, 0],
    parameters: {
      conditions: {
        options: { leftValue: '', caseSensitive: true, typeValidation: 'strict' },
        combinator: 'and',
        conditions: [{
          id: 'cond-passed',
          operator: { type: 'boolean', operation: 'true' },
          leftValue: '={{ $json.body.passed }}'
        }]
      }
    },
    typeVersion: 2
  },
  {
    id: 'node-pass-email',
    name: 'Send Pass Email',
    type: 'n8n-nodes-base.emailSend',
    position: [660, -120],
    parameters: {
      html: passHtml,
      options: {},
      subject: '=Passed {{ $json.body.examCode }} - {{ $json.body.score }}%',
      toEmail: '={{ $json.body.studentEmail }}',
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com'
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'node-fail-email',
    name: 'Send Fail Email',
    type: 'n8n-nodes-base.emailSend',
    position: [660, 120],
    parameters: {
      html: failHtml,
      options: {},
      subject: '={{ $json.body.examCode }} result: {{ $json.body.score }}% (need 90%)',
      toEmail: '={{ $json.body.studentEmail }}',
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com'
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'node-invite-email',
    name: 'Send Invite Email',
    type: 'n8n-nodes-base.emailSend',
    position: [440, 200],
    parameters: {
      html: inviteHtml,
      options: {},
      subject: 'Your IBM C1000-207 Practice Exams Are Ready — EvalOS',
      toEmail: '={{ $json.body.studentEmail }}',
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com'
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'node-score-email',
    name: 'Send Score Report',
    type: 'n8n-nodes-base.emailSend',
    position: [440, 360],
    parameters: {
      html: scoreHtml,
      options: {},
      subject: '=EvalOS Score Report: {{ $json.body.examCode }} - {{ $json.body.score }}%',
      toEmail: '={{ $json.body.studentEmail }}',
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com'
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'node-admin-alert',
    name: 'Admin Alert',
    type: 'n8n-nodes-base.emailSend',
    position: [880, 0],
    parameters: {
      text: '={{ "Student: " + $json.body.studentName + " (" + $json.body.studentEmail + ")\\nExam: " + $json.body.examCode + "\\nScore: " + $json.body.score + "%\\nPassed: " + $json.body.passed + "\\nEvent: " + $json.body.event }}',
      options: {},
      subject: '=[EvalOS] {{ $json.body.studentName }} scored {{ $json.body.score }}% on {{ $json.body.examCode }}',
      toEmail: 'snjagi@i3technologies.co.ke',
      emailType: 'text',
      fromEmail: 'pmukiti@gmail.com'
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  }
];

// Write SQL update to stdout — pipe to psql
const sql = `UPDATE credentials_entity SET data = '${ENC_DATA}' WHERE id = '${CRED_ID}';
UPDATE workflow_entity SET nodes = '${JSON.stringify(nodes).replace(/'/g, "''")}'::jsonb, active = true WHERE id = '${WF_ID}';
SELECT 'credential' AS type, id, name FROM credentials_entity WHERE id = '${CRED_ID}'
UNION ALL
SELECT 'workflow', id, name FROM workflow_entity WHERE id = '${WF_ID}';`;

process.stdout.write(sql);
