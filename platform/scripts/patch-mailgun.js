// Patch n8n EvalOS Events workflow to use HTTP Request → Mailgun API
// No credential encryption needed — API key passed as Basic Auth header inline
// Run inside n8n pod: node /tmp/patch-mailgun.js <MAILGUN_API_KEY> <MAILGUN_DOMAIN>
// Example: node /tmp/patch-mailgun.js key-abc123 mg.i3technologies.co.ke

const http  = require('http');
const https = require('https');

const WF     = '319537be-cd59-4645-9b5e-f183acfecf7e';
const MGKEY  = process.argv[2] || 'REPLACE_KEY';
const MGDOM  = process.argv[3] || 'REPLACE_DOMAIN';
const FROM   = 'EvalOS <noreply@i3technologies.co.ke>';
const MGURL  = `https://api.mailgun.net/v3/${MGDOM}/messages`;
// Basic auth: "api:<key>" base64 encoded
const MGAUTH = 'Basic ' + Buffer.from('api:' + MGKEY).toString('base64');

// ── Email HTML builders ───────────────────────────────────────────────────────
const passHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 22px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span></div>',
  '<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:22px">',
  '<h2 style="color:#166534;margin:0 0 8px">Congratulations {{$json.body.studentName}}!</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">You passed <b>{{$json.body.examCode}}</b>',
  ' with <b style="color:#16a34a;font-size:20px">{{$json.body.score}}%</b></p></div>',
  '<div style="padding:22px;background:#fff">',
  '<p style="color:#374151">The next set is now unlocked. Keep going!</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard"',
  ' style="display:inline-block;background:#0f172a;color:#fff;padding:11px 26px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Go to Dashboard</a></div>',
  '<div style="padding:14px 22px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; evalos.i3technologies.co.ke</div></div>'
].join('');

const failHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 22px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span></div>',
  '<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:22px">',
  '<h2 style="color:#991b1b;margin:0 0 8px">EvalOS Result - {{$json.body.examCode}}</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">Hi {{$json.body.studentName}}, you scored',
  ' <b style="color:#dc2626;font-size:20px">{{$json.body.score}}%</b>. You need 90% to pass.</p></div>',
  '<div style="padding:22px;background:#fff">',
  '<p style="color:#374151">Review the explanations on your results page, then retake when ready.',
  ' You have {{$json.body.attemptsLeft}} attempt(s) remaining.</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard"',
  ' style="display:inline-block;background:#0f172a;color:#fff;padding:11px 26px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Review Results</a></div>',
  '<div style="padding:14px 22px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya &middot; evalos.i3technologies.co.ke</div></div>'
].join('');

const inviteHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto">',
  '<div style="background:#0f172a;padding:18px 22px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:10px;margin-left:8px;letter-spacing:1px">TECHNOLOGIES</span></div>',
  '<div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:22px">',
  '<h2 style="color:#1e40af;margin:0 0 8px">Your IBM C1000-207 Practice Exams Are Ready</h2>',
  '<p style="color:#374151;font-size:15px;margin:0">Hi {{$json.body.studentName}},',
  ' you have been enrolled in the EvalOS certification practice platform.</p></div>',
  '<div style="padding:22px;background:#fff">',
  '<p style="color:#374151">Complete all 6 practice sets with <b>90%+</b> to earn your',
  ' i3 completion certificate and unlock your IBM certification lab access.</p>',
  '<ul style="color:#374151;line-height:1.8">',
  '<li>6 practice exam sets (60 questions each, 90 minutes)</li>',
  '<li>Instant results with full explanations</li>',
  '<li>Completion certificate on passing all sets</li></ul>',
  '<a href="https://evalos.i3technologies.co.ke"',
  ' style="display:inline-block;background:#0f172a;color:#fff;padding:11px 26px;',
  'border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Start Your First Exam</a></div>',
  '<div style="padding:14px 22px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>'
].join('');

// ── Helper: build HTTP Request node that POSTs to Mailgun ─────────────────────
function mailgunNode(id, name, position, toExpr, subjectExpr, htmlExpr) {
  return {
    id, name,
    type: 'n8n-nodes-base.httpRequest',
    position,
    typeVersion: 4.2,
    parameters: {
      method: 'POST',
      url: MGURL,
      authentication: 'genericCredentialType',
      genericAuthType: 'httpBasicAuth',
      sendHeaders: true,
      headerParameters: {
        parameters: [{
          name: 'Authorization',
          value: MGAUTH
        }]
      },
      sendBody: true,
      contentType: 'form-urlencoded',
      bodyParameters: {
        parameters: [
          { name: 'from',    value: FROM },
          { name: 'to',      value: toExpr },
          { name: 'subject', value: subjectExpr },
          { name: 'html',    value: htmlExpr }
        ]
      },
      options: {}
    }
  };
}

// ── Workflow nodes ─────────────────────────────────────────────────────────────
const nodes = [
  {
    id: 'n-wh', name: 'EvalOS Webhook',
    type: 'n8n-nodes-base.webhook', position: [0, 0],
    webhookId: 'evalos-events-hook', typeVersion: 2,
    parameters: { path: 'evalos-events', httpMethod: 'POST', responseMode: 'onReceived', options: {} }
  },
  {
    // IF node v1 — simple boolean check, no 'disabled' bug
    id: 'n-if', name: 'Passed?',
    type: 'n8n-nodes-base.if', position: [240, 0],
    typeVersion: 1,
    parameters: {
      conditions: {
        boolean: [{ value1: '={{$json.body.passed}}', value2: true }]
      }
    }
  },
  // Pass email via Mailgun HTTP API
  mailgunNode(
    'n-pe', 'Pass Email', [480, -160],
    '={{$json.body.studentEmail}}',
    '={{"Passed " + $json.body.examCode + " - " + $json.body.score + "%"}}',
    passHtml
  ),
  // Fail email via Mailgun HTTP API
  mailgunNode(
    'n-fe', 'Fail Email', [480, 160],
    '={{$json.body.studentEmail}}',
    '={{$json.body.examCode + " result: " + $json.body.score + "% (need 90%)"}}',
    failHtml
  ),
  // Invite email (for exam_invite event — sent to students who haven't started)
  mailgunNode(
    'n-inv', 'Invite Email', [480, 380],
    '={{$json.body.studentEmail}}',
    'Your IBM C1000-207 Practice Exams Are Ready - EvalOS',
    inviteHtml
  ),
  // Admin summary alert
  mailgunNode(
    'n-aa', 'Admin Alert', [720, 0],
    'snjagi@i3technologies.co.ke',
    '={{"[EvalOS] " + $json.body.studentName + " - " + $json.body.score + "% on " + $json.body.examCode}}',
    '={{"<pre>Student: " + $json.body.studentName + " (" + $json.body.studentEmail + ")\\nExam: " + $json.body.examCode + "\\nScore: " + $json.body.score + "%\\nPassed: " + $json.body.passed + "\\nEvent: " + $json.body.event + "</pre>"}}'
  )
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

// ── REST API helpers ──────────────────────────────────────────────────────────
function api(method, path, body, cookie, cb) {
  const b = body ? JSON.stringify(body) : null;
  const r = http.request({
    hostname: 'localhost', port: 5678, path, method,
    headers: {
      'Content-Type': 'application/json',
      ...(cookie ? { Cookie: cookie } : {}),
      ...(b ? { 'Content-Length': Buffer.byteLength(b) } : {})
    }
  }, res => { let d = ''; res.on('data', c => d += c); res.on('end', () => cb(res.statusCode, res.headers, d)); });
  r.on('error', e => cb(0, {}, e.message));
  if (b) r.write(b);
  r.end();
}

// ── Run ───────────────────────────────────────────────────────────────────────
api('POST', '/rest/login',
  { email: 'snjagi@i3technologies.co.ke', password: 'EvalOS@Admin2026!' }, null,
  (s, h) => {
    if (s !== 200) { process.stderr.write('LOGIN FAILED ' + s + '\n'); process.exit(1); }
    const ck = (h['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
    process.stdout.write('Logged in\n');

    api('PATCH', '/rest/workflows/' + WF, { active: false }, ck, (s2) => {
      process.stdout.write('Deactivated: ' + s2 + '\n');

      api('PATCH', '/rest/workflows/' + WF, { nodes, connections }, ck, (s3, _, b3) => {
        process.stdout.write('Nodes patched: ' + s3 + '\n');
        if (s3 !== 200) {
          process.stderr.write('PATCH ERR: ' + b3.substring(0, 400) + '\n');
          process.exit(1);
        }
        setTimeout(() => {
          api('PATCH', '/rest/workflows/' + WF, { active: true }, ck, (s4) => {
            process.stdout.write('Reactivated: ' + s4 + '\n');
            process.stdout.write('DONE — workflow now uses Mailgun HTTP API\n');
            process.stdout.write('API URL: ' + MGURL + '\n');
            process.stdout.write('From: ' + FROM + '\n');
          });
        }, 800);
      });
    });
  }
);
