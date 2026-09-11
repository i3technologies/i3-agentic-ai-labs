// Test Brevo API directly from n8n pod, then patch workflow with correct body format

const http  = require('http');
const https = require('https');

const BREVO_KEY  = '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';
const FROM_EMAIL = 'noreply@i3technologies.co.ke';
const FROM_NAME  = 'EvalOS - i3 Technologies';
const BREVO_URL  = 'https://api.brevo.com/v3/smtp/email';
const WF         = '319537be-cd59-4645-9b5e-f183acfecf7e';

// ── Step 1: Send test email directly via Brevo API ────────────────────────────
function sendBrevoEmail(to, toName, subject, html, params, cb) {
  const payload = JSON.stringify({
    sender:      { name: FROM_NAME, email: FROM_EMAIL },
    to:          [{ email: to, name: toName }],
    subject,
    htmlContent: html,
    params
  });

  const opts = {
    hostname: 'api.brevo.com', port: 443, path: '/v3/smtp/email', method: 'POST',
    headers: {
      'api-key':      BREVO_KEY,
      'Content-Type': 'application/json',
      'Accept':       'application/json',
      'Content-Length': Buffer.byteLength(payload)
    }
  };

  const req = https.request(opts, res => {
    let d = ''; res.on('data', c => d += c);
    res.on('end', () => cb(res.statusCode, d));
  });
  req.on('error', e => cb(0, e.message));
  req.write(payload);
  req.end();
}

const passHtml = '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px"><h2 style="color:#166534;margin:0 0 10px">Congratulations, {{params.studentName}}!</h2><p style="color:#374151;font-size:15px;margin:0">You passed <strong>{{params.examCode}}</strong> with <strong style="color:#16a34a;font-size:22px">{{params.score}}%</strong></p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Well done! The next practice set is now unlocked on your dashboard.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Go to Dashboard</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>';

const failHtml = '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px"><h2 style="color:#991b1b;margin:0 0 10px">EvalOS Result - {{params.examCode}}</h2><p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, you scored <strong style="color:#dc2626;font-size:22px">{{params.score}}%</strong>. You need 90% to pass.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Review the explanations on your results page and retake when ready. You have <strong>{{params.attemptsLeft}}</strong> attempt(s) remaining.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Review Results</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>';

process.stdout.write('Sending test pass email to philipm@i3technologies.co.ke...\n');

sendBrevoEmail(
  'philipm@i3technologies.co.ke', 'Philip Mukiti',
  'Passed C1000-207-SET1 — 98.33%',
  passHtml,
  { studentName: 'Philip Mukiti', examCode: 'C1000-207-SET1', score: '98.33', attemptsLeft: '4' },
  (status, body) => {
    process.stdout.write('PASS EMAIL STATUS: ' + status + '\n');
    process.stdout.write('PASS EMAIL BODY: ' + body + '\n');

    if (status !== 201) {
      process.stderr.write('FAILED — check error above\n');
      process.exit(1);
    }

    // ── Step 2: Now patch the workflow to call Brevo correctly ─────────────────
    // Use a Code node (n8n-nodes-base.code) to build and send the Brevo request
    // This avoids all n8n expression syntax issues — pure JS runs at execution time
    process.stdout.write('\nPatching workflow with Code node approach...\n');

    const codePassEmail = `
const https = require('https');
const item = $input.first().json;

function sendEmail(to, toName, subject, html, params) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: '${FROM_NAME}', email: '${FROM_EMAIL}' },
      to: [{ email: to, name: toName }],
      subject, htmlContent: html, params
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': '${BREVO_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const req = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    req.on('error', reject);
    req.write(payload); req.end();
  });
}

const passHtml = ${JSON.stringify(passHtml)};
const failHtml = ${JSON.stringify(failHtml)};

const html = item.body.passed ? passHtml : failHtml;
const subject = item.body.passed
  ? 'Passed ' + item.body.examCode + ' — ' + item.body.score + '%'
  : item.body.examCode + ' result: ' + item.body.score + '% (need 90%)';

const result = await sendEmail(
  item.body.studentEmail,
  item.body.studentName,
  subject,
  html,
  {
    studentName: item.body.studentName,
    examCode: item.body.examCode,
    score: String(item.body.score),
    passed: String(item.body.passed),
    attemptsLeft: String(item.body.attemptsLeft || 0)
  }
);

return [{ json: { ...item.body, emailStatus: result.status, emailResponse: result.body } }];
`;

    const codeAdminEmail = `
const https = require('https');
const item = $input.first().json;

function sendEmail(to, subject, text) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: '${FROM_NAME}', email: '${FROM_EMAIL}' },
      to: [{ email: to, name: 'EvalOS Admin' }],
      subject,
      textContent: text
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': '${BREVO_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const req = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    req.on('error', reject);
    req.write(payload); req.end();
  });
}

const result = await sendEmail(
  'snjagi@i3technologies.co.ke',
  '[EvalOS] ' + item.body.studentName + ' — ' + item.body.score + '% on ' + item.body.examCode,
  'Student: ' + item.body.studentName + ' (' + item.body.studentEmail + ')' +
  '\\nExam: ' + item.body.examCode +
  '\\nScore: ' + item.body.score + '%' +
  '\\nPassed: ' + item.body.passed +
  '\\nEvent: ' + item.body.event
);

return [{ json: { ...item.body, adminAlertStatus: result.status } }];
`;

    const inviteCode = `
const https = require('https');
const item = $input.first().json;
const inviteHtml = ${JSON.stringify('<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:24px"><h2 style="color:#1e40af;margin:0 0 10px">Your IBM C1000-207 Practice Exams Are Ready</h2><p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, you have been enrolled in EvalOS.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Complete all 6 practice sets with 90%+ to earn your i3 completion certificate.</p><ul style="color:#374151;line-height:2"><li>6 sets, 60 questions each, 90 minutes</li><li>Instant results with full explanations</li><li>Downloadable completion certificate</li></ul><a href="https://evalos.i3technologies.co.ke" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Start Your First Exam</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>')};

function sendEmail(to, toName, subject, html, params) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: '${FROM_NAME}', email: '${FROM_EMAIL}' },
      to: [{ email: to, name: toName }],
      subject, htmlContent: html, params
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': '${BREVO_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const req = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    req.on('error', reject);
    req.write(payload); req.end();
  });
}

const result = await sendEmail(
  item.body.studentEmail, item.body.studentName,
  'Your IBM C1000-207 Practice Exams Are Ready — EvalOS',
  inviteHtml,
  { studentName: item.body.studentName }
);
return [{ json: { ...item.body, inviteStatus: result.status } }];
`;

    // Nodes: Webhook → IF(passed) → Code(send pass/fail email) → Code(admin alert)
    //        Also handle exam_invite event via separate check
    const nodes = [
      {
        id: 'n-wh', name: 'EvalOS Webhook',
        type: 'n8n-nodes-base.webhook', position: [0, 0],
        webhookId: 'evalos-events-hook', typeVersion: 2,
        parameters: { path: 'evalos-events', httpMethod: 'POST', responseMode: 'onReceived', options: {} }
      },
      {
        // Check if exam_invite event — route separately
        id: 'n-ev', name: 'Event Type?',
        type: 'n8n-nodes-base.if', position: [220, 0],
        typeVersion: 1,
        parameters: {
          conditions: { string: [{ value1: '={{$json.body.event}}', value2: 'exam_invite' }] }
        }
      },
      {
        id: 'n-inv', name: 'Send Invite',
        type: 'n8n-nodes-base.code', position: [440, -200],
        typeVersion: 2,
        parameters: { jsCode: inviteCode, mode: 'runOnceForAllItems' }
      },
      {
        id: 'n-if', name: 'Passed?',
        type: 'n8n-nodes-base.if', position: [440, 100],
        typeVersion: 1,
        parameters: { conditions: { boolean: [{ value1: '={{$json.body.passed}}', value2: true }] } }
      },
      {
        id: 'n-email', name: 'Send Pass or Fail Email',
        type: 'n8n-nodes-base.code', position: [680, 100],
        typeVersion: 2,
        parameters: { jsCode: codePassEmail, mode: 'runOnceForAllItems' }
      },
      {
        id: 'n-aa', name: 'Admin Alert',
        type: 'n8n-nodes-base.code', position: [920, 0],
        typeVersion: 2,
        parameters: { jsCode: codeAdminEmail, mode: 'runOnceForAllItems' }
      }
    ];

    const connections = {
      'EvalOS Webhook': { main: [[{ node: 'Event Type?', type: 'main', index: 0 }]] },
      'Event Type?': { main: [
        [{ node: 'Send Invite',           type: 'main', index: 0 }],
        [{ node: 'Passed?',               type: 'main', index: 0 }]
      ]},
      'Passed?': { main: [
        [{ node: 'Send Pass or Fail Email', type: 'main', index: 0 }],
        [{ node: 'Send Pass or Fail Email', type: 'main', index: 0 }]
      ]},
      'Send Pass or Fail Email': { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] },
      'Send Invite':             { main: [[{ node: 'Admin Alert', type: 'main', index: 0 }]] }
    };

    function api(method, path, body, cookie, cb) {
      const b = body ? JSON.stringify(body) : null;
      const r = http.request({
        hostname: 'localhost', port: 5678, path, method,
        headers: {
          'Content-Type': 'application/json',
          ...(cookie ? { Cookie: cookie } : {}),
          ...(b ? { 'Content-Length': Buffer.byteLength(b) } : {})
        }
      }, res => { let d=''; res.on('data',c=>d+=c); res.on('end',()=>cb(res.statusCode,res.headers,d)); });
      r.on('error', e => cb(0,{},e.message));
      if (b) r.write(b);
      r.end();
    }

    api('POST', '/rest/login',
      { email: 'snjagi@i3technologies.co.ke', password: 'EvalOS@Admin2026!' }, null,
      (s, h) => {
        if (s !== 200) { process.stderr.write('LOGIN FAILED\n'); process.exit(1); }
        const ck = (h['set-cookie']||[]).map(c=>c.split(';')[0]).join('; ');

        api('PATCH', '/rest/workflows/'+WF, { active: false }, ck, () => {
          api('PATCH', '/rest/workflows/'+WF, { nodes, connections }, ck, (s3,_,b3) => {
            process.stdout.write('Workflow patched: '+s3+'\n');
            if (s3 !== 200) { process.stderr.write(b3.substring(0,400)+'\n'); process.exit(1); }
            setTimeout(() => {
              api('PATCH', '/rest/workflows/'+WF, { active: true }, ck, (s4) => {
                process.stdout.write('Reactivated: '+s4+'\n');
                process.stdout.write('\n=== ALL DONE ===\n');
                process.stdout.write('Emails now sent via Brevo API (HTTPS port 443)\n');
                process.stdout.write('From: ' + FROM_NAME + ' <' + FROM_EMAIL + '>\n');
              });
            }, 800);
          });
        });
      }
    );
  }
);
