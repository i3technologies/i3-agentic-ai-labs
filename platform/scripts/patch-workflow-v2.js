// Patch workflow: fix IF node typeVersion and condition format
// Uses the n8n REST API to update the workflow correctly

const http = require('http');
const WF_ID = '319537be-cd59-4645-9b5e-f183acfecf7e';
const CRED_ID = 'd035f766-f0fe-46a4-9962-1db39acfad4e';

const passHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">',
  '<div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:11px;margin-left:8px">TECHNOLOGIES</span></div>',
  '<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px">',
  '<h2 style="color:#166534;margin:0 0 10px">Congratulations {{$json.body.studentName}}!</h2>',
  '<p style="color:#374151;font-size:15px">You passed <b>{{$json.body.examCode}}</b> with ',
  '<b style="color:#16a34a;font-size:18px">{{$json.body.score}}%</b></p></div>',
  '<div style="padding:24px;background:#fff">',
  '<p style="color:#374151">The next set is now unlocked on your dashboard. Keep going!</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard" ',
  'style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold">Go to Dashboard</a></div>',
  '<div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>'
].join('');

const failHtml = [
  '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">',
  '<div style="background:#0f172a;padding:20px 24px;border-radius:8px 8px 0 0">',
  '<span style="color:#60a5fa;font-size:28px;font-weight:900;letter-spacing:2px">i3</span>',
  '<span style="color:#94a3b8;font-size:11px;margin-left:8px">TECHNOLOGIES</span></div>',
  '<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px">',
  '<h2 style="color:#991b1b;margin:0 0 10px">EvalOS Result - {{$json.body.examCode}}</h2>',
  '<p style="color:#374151;font-size:15px">Hi {{$json.body.studentName}}, you scored ',
  '<b style="color:#dc2626;font-size:18px">{{$json.body.score}}%</b>. You need 90% to pass.</p></div>',
  '<div style="padding:24px;background:#fff">',
  '<p style="color:#374151">Review your results and retake when ready. ',
  'You have {{$json.body.attemptsLeft}} attempt(s) remaining.</p>',
  '<a href="https://evalos.i3technologies.co.ke/dashboard" ',
  'style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;',
  'border-radius:6px;text-decoration:none;font-weight:bold">Review Results</a></div>',
  '<div style="padding:16px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px">',
  'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>'
].join('');

// Use IF node typeVersion:1 with simple value comparison — avoids the 'disabled' bug in v2
const nodes = [
  {
    id: 'webhook', name: 'EvalOS Webhook',
    type: 'n8n-nodes-base.webhook', position: [0, 0],
    webhookId: 'evalos-events-hook',
    parameters: { path: 'evalos-events', httpMethod: 'POST', responseMode: 'onReceived', options: {} },
    typeVersion: 2
  },
  {
    id: 'if-passed', name: 'Passed?',
    type: 'n8n-nodes-base.if', position: [240, 0],
    // typeVersion 1 uses simple conditions array — no 'disabled' property required
    parameters: {
      conditions: {
        boolean: [{
          value1: '={{$json.body.passed}}',
          value2: true
        }]
      }
    },
    typeVersion: 1
  },
  {
    id: 'pass-email', name: 'Pass Email',
    type: 'n8n-nodes-base.emailSend', position: [480, -140],
    parameters: {
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com',
      toEmail: '={{$json.body.studentEmail}}',
      subject: '=Passed {{$json.body.examCode}} - {{$json.body.score}}%',
      html: passHtml,
      options: {}
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'fail-email', name: 'Fail Email',
    type: 'n8n-nodes-base.emailSend', position: [480, 140],
    parameters: {
      emailType: 'html',
      fromEmail: 'pmukiti@gmail.com',
      toEmail: '={{$json.body.studentEmail}}',
      subject: '={{$json.body.examCode}} result: {{$json.body.score}}% (need 90%)',
      html: failHtml,
      options: {}
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  },
  {
    id: 'admin-alert', name: 'Admin Alert',
    type: 'n8n-nodes-base.emailSend', position: [720, 0],
    parameters: {
      emailType: 'text',
      fromEmail: 'pmukiti@gmail.com',
      toEmail: 'snjagi@i3technologies.co.ke',
      subject: '=[EvalOS] {{$json.body.studentName}} - {{$json.body.score}}% on {{$json.body.examCode}}',
      text: '={{"Student: " + $json.body.studentName + " (" + $json.body.studentEmail + ")\\nExam: " + $json.body.examCode + "\\nScore: " + $json.body.score + "%\\nPassed: " + $json.body.passed}}',
      options: {}
    },
    credentials: { smtp: { id: CRED_ID, name: 'i3 Gmail SMTP' } },
    typeVersion: 2.1
  }
];

const connections = {
  'EvalOS Webhook': { main: [[{ node: 'Passed?',     type: 'main', index: 0 }]] },
  'Passed?':        { main: [
    [{ node: 'Pass Email', type: 'main', index: 0 }],
    [{ node: 'Fail Email', type: 'main', index: 0 }]
  ]},
  'Pass Email':  { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] },
  'Fail Email':  { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] }
};

// ── Patch via REST API ────────────────────────────────────────────────────────
function request(method, path, body, headers, cb) {
  const b = body ? JSON.stringify(body) : null;
  const opts = {
    hostname: 'localhost', port: 5678, path, method,
    headers: { 'Content-Type': 'application/json', ...headers,
      ...(b ? { 'Content-Length': Buffer.byteLength(b) } : {}) }
  };
  const req = http.request(opts, res => {
    let d = ''; res.on('data', c => d += c);
    res.on('end', () => cb(res.statusCode, res.headers, d));
  });
  req.on('error', e => cb(0, {}, e.message));
  if (b) req.write(b);
  req.end();
}

// Login
request('POST', '/rest/login',
  { email: 'snjagi@i3technologies.co.ke', password: 'EvalOS@Admin2026!' }, {},
  (s, h, b) => {
    if (s !== 200) { console.error('LOGIN FAILED', s, b); process.exit(1); }
    const cookie = (h['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
    const H = { Cookie: cookie };
    console.log('Logged in as Sebastian');

    // Deactivate
    request('PATCH', '/rest/workflows/' + WF_ID, { active: false }, H, (s2) => {
      console.log('Deactivated:', s2);

      // PUT full workflow update
      request('GET', '/rest/workflows/' + WF_ID, null, H, (s3, _, b3) => {
        const wf = JSON.parse(b3);
        const wfData = wf.data || wf;
        wfData.nodes = nodes;
        wfData.connections = connections;
        wfData.active = false;

        request('PUT', '/rest/workflows/' + WF_ID, wfData, H, (s4, _, b4) => {
          console.log('PUT workflow:', s4);
          if (s4 !== 200) { console.error('PUT failed:', b4.substring(0, 300)); process.exit(1); }

          // Reactivate
          setTimeout(() => {
            request('PATCH', '/rest/workflows/' + WF_ID, { active: true }, H, (s5) => {
              console.log('Reactivated:', s5);
              console.log('DONE — workflow patched and active');
            });
          }, 1000);
        });
      });
    });
  }
);
