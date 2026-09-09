#!/usr/bin/env node
// Patches the EvalOS Events n8n workflow:
// Fix: Admin Alert node reads item.body.* but upstream Code nodes already spread body flat
// Fix: Admin Alert now reads item.* directly

const https = require('https');

const N8N_BASE = 'n8n.i3technologies.co.ke';
const WORKFLOW_ID = '319537be-cd59-4645-9b5e-f183acfecf7e';
const EMAIL = 'snjagi@i3technologies.co.ke';
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
      res.on('end', () => {
        const setCookie = res.headers['set-cookie'];
        resolve({ status: res.statusCode, body: d, cookie: setCookie });
      });
    });
    r.on('error', reject);
    if (payload) r.write(payload);
    r.end();
  });
}

// Fixed Admin Alert jsCode — reads item.* directly (body already spread by upstream)
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

// item is already flat (studentName, studentEmail, examCode, score, event, passed etc.)
const studentName  = item.studentName  || item.student_name  || '(unknown)';
const studentEmail = item.studentEmail || item.student_email || '';
const examCode     = item.examCode     || item.exam_title    || '';
const score        = item.score        != null ? item.score  : '';
const passed       = item.passed       != null ? item.passed : '';
const event        = item.event        || '';

const result = await sendEmail(
  'snjagi@i3technologies.co.ke',
  '[EvalOS] ' + studentName + ' — ' + score + '% on ' + examCode,
  'Student: ' + studentName + ' (' + studentEmail + ')' +
  '\\nExam: '   + examCode  +
  '\\nScore: '  + score + '%' +
  '\\nPassed: ' + passed +
  '\\nEvent: '  + event
);

return [{ json: { ...item, adminAlertStatus: result.status, adminAlertBody: result.body } }];
`;

async function main() {
  // 1. Login
  const loginResp = await req('POST', '/rest/login', { email: EMAIL, password: PASSWORD });
  const rawCookie = loginResp.cookie ? loginResp.cookie.map(c => c.split(';')[0]).join('; ') : '';
  console.log('Login:', loginResp.status, rawCookie ? 'cookie ok' : 'NO COOKIE');
  if (loginResp.status !== 200) { console.error(loginResp.body); process.exit(1); }

  // 2. Fetch current workflow
  const wfResp = await req('GET', `/rest/workflows/${WORKFLOW_ID}`, null, rawCookie);
  if (wfResp.status !== 200) { console.error('Fetch workflow failed', wfResp.status, wfResp.body); process.exit(1); }
  const wf = JSON.parse(wfResp.body).data;

  // 3. Patch Admin Alert node
  const nodes = wf.nodes.map(n => {
    if (n.name === 'Admin Alert') {
      return { ...n, parameters: { ...n.parameters, jsCode: adminAlertCode } };
    }
    return n;
  });

  // 4. Update workflow
  const patchResp = await req('PATCH', `/rest/workflows/${WORKFLOW_ID}`,
    { nodes, connections: wf.connections, settings: wf.settings, staticData: wf.staticData },
    rawCookie
  );
  console.log('Patch workflow:', patchResp.status);
  if (patchResp.status !== 200) { console.error(patchResp.body); process.exit(1); }

  // 5. Reactivate
  const actResp = await req('PATCH', `/rest/workflows/${WORKFLOW_ID}`, { active: true }, rawCookie);
  console.log('Activate:', actResp.status);

  console.log('\nDone. Admin Alert node patched — reads item.* (flat) instead of item.body.*');
}

main().catch(e => { console.error(e); process.exit(1); });
