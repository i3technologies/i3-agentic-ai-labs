// Patch n8n EvalOS Events workflow — Brevo HTTP API (port 443, no SMTP needed)
// Run inside n8n pod: node /tmp/patch-brevo.js

const http = require('http');

const WF       = '319537be-cd59-4645-9b5e-f183acfecf7e';
const BREVO_KEY = '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';
const FROM_EMAIL = 'noreply@i3technologies.co.ke';
const FROM_NAME  = 'EvalOS — i3 Technologies';
const ADMIN_EMAIL = 'snjagi@i3technologies.co.ke';
const BREVO_URL  = 'https://api.brevo.com/v3/smtp/email';

// ── Email HTML templates ──────────────────────────────────────────────────────

const passHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:10px;letter-spacing:1px;text-transform:uppercase">Technologies</span>',
  '</div>',
  '<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px">',
  '<h2 style="color:#166534;margin:0 0 10px;font-size:20px">Congratulations, {{params.studentName}}!</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">You passed <strong>{{params.examCode}}</strong>',
  ' with <strong style="color:#16a34a;font-size:22px">{{params.score}}%</strong></p>',
  '</div>',
  '<div style="padding:24px;background:#ffffff">',
  '<p style="color:#374151;line-height:1.6">',
  'Well done! The next practice set is now unlocked on your dashboard. ',
  'Keep going — you are on your way to the IBM C1000-207 certification!</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard"',
  ' style="display:inline-block;background:#0f172a;color:#ffffff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px;font-size:14px">',
  'Go to Dashboard &rarr;</a>',
  '</div>',
  '<div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; ',
  '<a href="https://evalos.i3technologies.co.ke" style="color:#9ca3af">evalos.i3technologies.co.ke</a>',
  '</div></div>'
].join('');

const failHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:10px;letter-spacing:1px;text-transform:uppercase">Technologies</span>',
  '</div>',
  '<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px">',
  '<h2 style="color:#991b1b;margin:0 0 10px;font-size:20px">EvalOS Result — {{params.examCode}}</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, you scored',
  ' <strong style="color:#dc2626;font-size:22px">{{params.score}}%</strong>.',
  ' You need <strong>90%</strong> to pass.</p>',
  '</div>',
  '<div style="padding:24px;background:#ffffff">',
  '<p style="color:#374151;line-height:1.6">',
  'Review the detailed explanations on your results page to understand where to improve, ',
  'then retake when ready. You have <strong>{{params.attemptsLeft}}</strong> attempt(s) remaining.</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard"',
  ' style="display:inline-block;background:#0f172a;color:#ffffff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px;font-size:14px">',
  'Review Results &rarr;</a>',
  '</div>',
  '<div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; ',
  '<a href="https://evalos.i3technologies.co.ke" style="color:#9ca3af">evalos.i3technologies.co.ke</a>',
  '</div></div>'
].join('');

const inviteHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:10px;letter-spacing:1px;text-transform:uppercase">Technologies</span>',
  '</div>',
  '<div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:24px">',
  '<h2 style="color:#1e40af;margin:0 0 10px;font-size:20px">Your IBM C1000-207 Practice Exams Are Ready</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}},',
  ' you have been enrolled in the EvalOS certification practice platform.</p>',
  '</div>',
  '<div style="padding:24px;background:#ffffff">',
  '<p style="color:#374151;line-height:1.6">',
  'Complete all 6 practice sets with a score of <strong>90% or higher</strong> ',
  'to earn your i3 completion certificate and unlock your IBM certification lab access.</p>',
  '<ul style="color:#374151;line-height:2;margin:16px 0">',
  '<li>6 practice exam sets — 60 questions each</li>',
  '<li>90-minute timed exam per set</li>',
  '<li>Instant results with full explanations per question</li>',
  '<li>Downloadable completion certificate on passing all sets</li>',
  '</ul>',
  '<a href="https://evalos.i3technologies.co.ke"',
  ' style="display:inline-block;background:#0f172a;color:#ffffff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:4px;font-size:14px">',
  'Start Your First Exam &rarr;</a>',
  '</div>',
  '<div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; ',
  '<a href="https://evalos.i3technologies.co.ke" style="color:#9ca3af">evalos.i3technologies.co.ke</a>',
  '</div></div>'
].join('');

const scoreHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:10px;letter-spacing:1px;text-transform:uppercase">Technologies</span>',
  '</div>',
  '<div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:24px">',
  '<h2 style="color:#0f172a;margin:0 0 10px;font-size:20px">Your EvalOS Score Report</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, here is your latest exam result.</p>',
  '</div>',
  '<div style="padding:24px;background:#ffffff">',
  '<table style="width:100%;border-collapse:collapse;font-size:14px">',
  '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:10px 0;color:#64748b">Examination</td>',
  '<td style="padding:10px 0;font-weight:bold;color:#0f172a">{{params.examCode}}</td></tr>',
  '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:10px 0;color:#64748b">Score</td>',
  '<td style="padding:10px 0;font-weight:bold;font-size:22px;color:{{params.passed === true ? \"#16a34a\" : \"#dc2626\"}}">{{params.score}}%</td></tr>',
  '<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:10px 0;color:#64748b">Result</td>',
  '<td style="padding:10px 0;font-weight:bold;color:{{params.passed === true ? \"#16a34a\" : \"#dc2626\"}}">{{params.passed === true ? \"PASS\" : \"FAIL\"}}</td></tr>',
  '<tr><td style="padding:10px 0;color:#64748b">Pass mark</td>',
  '<td style="padding:10px 0;color:#374151">90%</td></tr>',
  '</table>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard"',
  ' style="display:inline-block;background:#0f172a;color:#ffffff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:16px;font-size:14px">',
  'View Full Results &rarr;</a>',
  '</div>',
  '<div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>'
].join('');

// ── Helper: build Brevo HTTP Request node ─────────────────────────────────────
// Brevo transactional email API: POST /v3/smtp/email
// Payload: { sender, to, subject, htmlContent, params }
function brevoNode(id, name, position, toExpr, subjectExpr, htmlContent) {
  return {
    id, name,
    type: 'n8n-nodes-base.httpRequest',
    position,
    typeVersion: 4.2,
    parameters: {
      method: 'POST',
      url: BREVO_URL,
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: 'api-key',      value: BREVO_KEY },
          { name: 'Content-Type', value: 'application/json' },
          { name: 'Accept',       value: 'application/json' }
        ]
      },
      sendBody: true,
      contentType: 'json',
      // Build the Brevo payload as a JSON body expression
      // Use n8n expressions to inject student data into params
      specifyBody: 'json',
      jsonBody: JSON.stringify({
        sender:      { name: FROM_NAME, email: FROM_EMAIL },
        to:          [{ email: '{{$json.body.studentEmail}}', name: '{{$json.body.studentName}}' }],
        subject:     subjectExpr,
        htmlContent: htmlContent,
        params: {
          studentName: '{{$json.body.studentName}}',
          studentEmail:'{{$json.body.studentEmail}}',
          examCode:    '{{$json.body.examCode}}',
          score:       '{{$json.body.score}}',
          passed:      '{{$json.body.passed}}',
          attemptsLeft:'{{$json.body.attemptsLeft}}'
        }
      }),
      options: {}
    }
  };
}

function brevoAdminNode(id, name, position) {
  return {
    id, name,
    type: 'n8n-nodes-base.httpRequest',
    position,
    typeVersion: 4.2,
    parameters: {
      method: 'POST',
      url: BREVO_URL,
      sendHeaders: true,
      headerParameters: {
        parameters: [
          { name: 'api-key',      value: BREVO_KEY },
          { name: 'Content-Type', value: 'application/json' },
          { name: 'Accept',       value: 'application/json' }
        ]
      },
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: JSON.stringify({
        sender:      { name: FROM_NAME, email: FROM_EMAIL },
        to:          [{ email: ADMIN_EMAIL, name: 'Sebastian Njagi' }],
        subject:     '[EvalOS] {{$json.body.studentName}} — {{$json.body.score}}% on {{$json.body.examCode}}',
        textContent: 'Student: {{$json.body.studentName}} ({{$json.body.studentEmail}})\nExam: {{$json.body.examCode}}\nScore: {{$json.body.score}}%\nPassed: {{$json.body.passed}}\nEvent: {{$json.body.event}}\nTimestamp: {{$json.body.timestamp}}'
      }),
      options: {}
    }
  };
}

// ── Workflow definition ───────────────────────────────────────────────────────
const nodes = [
  // 1. Webhook — receives all EvalOS events
  {
    id: 'n-wh', name: 'EvalOS Webhook',
    type: 'n8n-nodes-base.webhook', position: [0, 0],
    webhookId: 'evalos-events-hook', typeVersion: 2,
    parameters: { path: 'evalos-events', httpMethod: 'POST', responseMode: 'onReceived', options: {} }
  },
  // 2. IF node v1 — check passed (true/false)
  {
    id: 'n-if', name: 'Passed?',
    type: 'n8n-nodes-base.if', position: [240, 0],
    typeVersion: 1,
    parameters: {
      conditions: {
        boolean: [{ value1: '={{$json.body.passed}}', value2: true }]
      }
    }
  },
  // 3. Pass email
  brevoNode(
    'n-pe', 'Pass Email', [480, -180],
    '={{$json.body.studentEmail}}',
    'Passed {{$json.body.examCode}} — {{$json.body.score}}%',
    passHtml
  ),
  // 4. Fail email
  brevoNode(
    'n-fe', 'Fail Email', [480, 180],
    '={{$json.body.studentEmail}}',
    '{{$json.body.examCode}} result: {{$json.body.score}}% (need 90%)',
    failHtml
  ),
  // 5. Admin alert (always fires after pass or fail)
  brevoAdminNode('n-aa', 'Admin Alert', [740, 0])
];

const connections = {
  'EvalOS Webhook': { main: [[{ node: 'Passed?',     type: 'main', index: 0 }]] },
  'Passed?':        { main: [
    [{ node: 'Pass Email',   type: 'main', index: 0 }],
    [{ node: 'Fail Email',   type: 'main', index: 0 }]
  ]},
  'Pass Email':     { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] },
  'Fail Email':     { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] }
};

// ── n8n REST API ──────────────────────────────────────────────────────────────
function api(method, path, body, cookie, cb) {
  const b = body ? JSON.stringify(body) : null;
  const r = http.request({
    hostname: 'localhost', port: 5678, path, method,
    headers: {
      'Content-Type': 'application/json',
      ...(cookie ? { Cookie: cookie } : {}),
      ...(b ? { 'Content-Length': Buffer.byteLength(b) } : {})
    }
  }, res => {
    let d = ''; res.on('data', c => d += c);
    res.on('end', () => cb(res.statusCode, res.headers, d));
  });
  r.on('error', e => cb(0, {}, e.message));
  if (b) r.write(b);
  r.end();
}

// ── Execute ───────────────────────────────────────────────────────────────────
api('POST', '/rest/login',
  { email: 'snjagi@i3technologies.co.ke', password: 'EvalOS@Admin2026!' }, null,
  (s, h) => {
    if (s !== 200) { process.stderr.write('LOGIN FAILED ' + s + '\n'); process.exit(1); }
    const ck = (h['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
    process.stdout.write('[1/4] Logged in as Sebastian Njagi\n');

    api('PATCH', '/rest/workflows/' + WF, { active: false }, ck, (s2) => {
      process.stdout.write('[2/4] Deactivated workflow: ' + s2 + '\n');

      api('PATCH', '/rest/workflows/' + WF, { nodes, connections }, ck, (s3, _, b3) => {
        process.stdout.write('[3/4] Nodes patched: ' + s3 + '\n');
        if (s3 !== 200) {
          process.stderr.write('PATCH ERROR: ' + b3.substring(0, 500) + '\n');
          process.exit(1);
        }
        setTimeout(() => {
          api('PATCH', '/rest/workflows/' + WF, { active: true }, ck, (s4) => {
            process.stdout.write('[4/4] Reactivated: ' + s4 + '\n');
            process.stdout.write('\n=== DONE ===\n');
            process.stdout.write('Provider : Brevo HTTP API (port 443)\n');
            process.stdout.write('From     : ' + FROM_NAME + ' <' + FROM_EMAIL + '>\n');
            process.stdout.write('Admin to : ' + ADMIN_EMAIL + '\n');
            process.stdout.write('Nodes    : Webhook → IF(passed) → Pass/Fail Email → Admin Alert\n');
          });
        }, 800);
      });
    });
  }
);
