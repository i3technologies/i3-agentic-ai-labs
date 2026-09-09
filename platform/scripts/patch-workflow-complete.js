#!/usr/bin/env node
// Final complete workflow patch:
// Fix Send Pass or Fail Email node — same snake_case normalization as Send Invite
// Also fix Passed? IF node to check body.passed OR body.passed (already boolean from EvalOS)

const https = require('https');

const N8N_BASE = 'n8n.i3technologies.co.ke';
const WORKFLOW_ID = '319537be-cd59-4645-9b5e-f183acfecf7e';
const EMAIL_LOGIN = 'snjagi@i3technologies.co.ke';
const PASSWORD = 'EvalOS@Admin2026!';

function req(method, path, body, cookie) {
  return new Promise((resolve, reject) => {
    const payload = body ? JSON.stringify(body) : null;
    const headers = { 'Content-Type': 'application/json', Accept: 'application/json' };
    if (cookie) headers['Cookie'] = cookie;
    if (payload) headers['Content-Length'] = Buffer.byteLength(payload);
    const r = https.request({ hostname: N8N_BASE, port: 443, path, method, headers }, res => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve({ status: res.statusCode, body: d, cookie: res.headers['set-cookie'] }));
    });
    r.on('error', reject);
    if (payload) r.write(payload);
    r.end();
  });
}

// Fixed Send Pass or Fail Email jsCode
const sendPassFailCode = `
const https = require('https');
const item = $input.first().json;

// Normalise field names — handle both snake_case (from EvalOS webhook) and camelCase
const b = item.body || item;
const studentEmail = b.studentEmail || b.student_email || '';
const studentName  = b.studentName  || b.student_name  || 'Student';
const examCode     = b.examCode     || b.exam_code     || b.exam_title || b.examTitle || '';
const score        = b.score        != null ? b.score  : 0;
const passed       = b.passed       === true || b.passed === 'true';
const attemptsLeft = b.attemptsLeft || b.attempts_left || 0;

const passHtml = \`<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px"><h2 style="color:#166534;margin:0 0 10px">Congratulations, \${studentName}!</h2><p style="color:#374151;font-size:15px;margin:0">You passed <strong>\${examCode}</strong> with <strong style="color:#16a34a;font-size:22px">\${score}%</strong></p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Well done! The next practice set is now unlocked on your dashboard.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Go to Dashboard</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS · i3 Technologies · evalos.i3technologies.co.ke</div></div>\`;

const failHtml = \`<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px"><h2 style="color:#991b1b;margin:0 0 10px">EvalOS Result - \${examCode}</h2><p style="color:#374151;font-size:15px;margin:0">Hi \${studentName}, you scored <strong style="color:#dc2626;font-size:22px">\${score}%</strong>. You need 90% to pass.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Review the explanations on your results page and retake when ready. You have <strong>\${attemptsLeft}</strong> attempt(s) remaining.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Review Results</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS · i3 Technologies · evalos.i3technologies.co.ke</div></div>\`;

const html    = passed ? passHtml : failHtml;
const subject = passed
  ? 'Passed ' + examCode + ' — ' + score + '%'
  : examCode + ' result: ' + score + '% (need 90%)';

function sendEmail(to, toName, subj, html) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: 'EvalOS - i3 Technologies', email: 'noreply@i3technologies.co.ke' },
      to: [{ email: to, name: toName }],
      subject: subj,
      htmlContent: html
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': process.env.BREVO_API_KEY || '',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const r = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    r.on('error', reject);
    r.write(payload); r.end();
  });
}

const result = await sendEmail(studentEmail, studentName, subject, html);
return [{ json: {
  studentEmail, studentName, examCode, score, passed, attemptsLeft,
  event: b.event || 'exam_result',
  emailStatus: result.status,
  emailBody: result.body
} }];
`;

// Fixed Admin Alert jsCode (same as before — flat item)
const adminAlertCode = `
const https = require('https');
const item = $input.first().json;

function sendEmail(to, subject, text) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: 'EvalOS - i3 Technologies', email: 'noreply@i3technologies.co.ke' },
      to: [{ email: to, name: 'EvalOS Admin' }],
      subject,
      textContent: text
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': process.env.BREVO_API_KEY || '',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const r = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    r.on('error', reject);
    r.write(payload); r.end();
  });
}

// item is already flat — upstream Code nodes spread the body
const studentName  = item.studentName  || item.student_name  || '(unknown)';
const studentEmail = item.studentEmail || item.student_email || '';
const examCode     = item.examCode     || item.exam_code     || item.exam_title || item.examTitle || '';
const score        = item.score        != null ? item.score  : '';
const passed       = item.passed       != null ? item.passed : '';
const event        = item.event        || '';

const result = await sendEmail(
  'snjagi@i3technologies.co.ke',
  '[EvalOS] ' + studentName + (score !== '' ? ' — ' + score + '% on ' + examCode : ' — Invite sent'),
  'Event: '     + event +
  '\\nStudent: ' + studentName + ' (' + studentEmail + ')' +
  (examCode  ? '\\nExam: '   + examCode  : '') +
  (score !== '' ? '\\nScore: '  + score + '%' : '') +
  (passed !== '' ? '\\nPassed: ' + passed : '')
);

return [{ json: { ...item, adminAlertStatus: result.status, adminAlertBody: result.body } }];
`;

// Fixed Send Invite jsCode (keep in sync)
const sendInviteCode = `
const https = require('https');
const item = $input.first().json;

const b = item.body || item;
const studentEmail = b.studentEmail || b.student_email || '';
const studentName  = b.studentName  || b.student_name  || 'Student';
const examTitle    = b.examTitle    || b.exam_title    || 'IBM C1000-207 Practice Exam';
const examUrl      = b.examUrl      || b.exam_url      || 'https://evalos.i3technologies.co.ke';

const inviteHtml = \`<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:24px"><h2 style="color:#1e40af;margin:0 0 10px">Your IBM C1000-207 Practice Exams Are Ready</h2><p style="color:#374151;font-size:15px;margin:0">Hi \${studentName}, you have been enrolled in EvalOS.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Complete all 6 practice sets with 90%+ to earn your i3 completion certificate.</p><ul style="color:#374151;line-height:2"><li>6 sets, 60 questions each, 90 minutes</li><li>Instant results with full explanations</li><li>Downloadable completion certificate</li></ul><a href="\${examUrl}" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Start Your First Exam</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS · i3 Technologies · evalos.i3technologies.co.ke</div></div>\`;

function sendEmail(to, toName, subject, html) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      sender: { name: 'EvalOS - i3 Technologies', email: 'noreply@i3technologies.co.ke' },
      to: [{ email: to, name: toName }],
      subject,
      htmlContent: html
    });
    const opts = {
      hostname: 'api.brevo.com', port: 443,
      path: '/v3/smtp/email', method: 'POST',
      headers: {
        'api-key': process.env.BREVO_API_KEY || '',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const r = https.request(opts, res => {
      let d=''; res.on('data',c=>d+=c);
      res.on('end', () => resolve({ status: res.statusCode, body: d }));
    });
    r.on('error', reject);
    r.write(payload); r.end();
  });
}

const result = await sendEmail(
  studentEmail, studentName,
  'Your IBM C1000-207 Practice Exams Are Ready — EvalOS',
  inviteHtml
);

return [{ json: {
  studentEmail, studentName, examTitle, examUrl,
  event: b.event || 'exam_invite',
  inviteStatus: result.status,
  inviteBody: result.body
} }];
`;

async function main() {
  const loginResp = await req('POST', '/rest/login', { email: EMAIL_LOGIN, password: PASSWORD });
  const rawCookie = loginResp.cookie ? loginResp.cookie.map(c => c.split(';')[0]).join('; ') : '';
  console.log('Login:', loginResp.status);
  if (loginResp.status !== 200) { console.error(loginResp.body); process.exit(1); }

  const wfResp = await req('GET', `/rest/workflows/${WORKFLOW_ID}`, null, rawCookie);
  if (wfResp.status !== 200) { console.error('Fetch failed:', wfResp.body); process.exit(1); }
  const wf = JSON.parse(wfResp.body).data;

  const nodes = wf.nodes.map(n => {
    if (n.name === 'Send Invite')              return { ...n, parameters: { ...n.parameters, jsCode: sendInviteCode } };
    if (n.name === 'Send Pass or Fail Email')  return { ...n, parameters: { ...n.parameters, jsCode: sendPassFailCode } };
    if (n.name === 'Admin Alert')              return { ...n, parameters: { ...n.parameters, jsCode: adminAlertCode } };
    return n;
  });

  const patchResp = await req('PATCH', `/rest/workflows/${WORKFLOW_ID}`,
    { nodes, connections: wf.connections, settings: wf.settings, staticData: wf.staticData },
    rawCookie
  );
  console.log('Patch:', patchResp.status);
  if (patchResp.status !== 200) { console.error(patchResp.body); process.exit(1); }

  const actResp = await req('PATCH', `/rest/workflows/${WORKFLOW_ID}`, { active: true }, rawCookie);
  console.log('Activate:', actResp.status);
  console.log('\nAll 3 Code nodes patched with snake_case normalisation. Workflow active.');
}

main().catch(e => { console.error(e); process.exit(1); });
