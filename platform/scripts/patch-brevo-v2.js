// Patch n8n EvalOS Events workflow — Brevo HTTP API correct body format
// Uses rawBody with n8n expression so fields are evaluated at runtime

const http = require('http');

const WF        = '319537be-cd59-4645-9b5e-f183acfecf7e';
const BREVO_KEY = 'BREVO_API_KEY_REDACTED_SEE_CLUSTER_SECRET';
const FROM_EMAIL = 'noreply@i3technologies.co.ke';
const FROM_NAME  = 'EvalOS - i3 Technologies';
const ADMIN_EMAIL = 'snjagi@i3technologies.co.ke';
const BREVO_URL   = 'https://api.brevo.com/v3/smtp/email';

// ── HTML templates (static — no n8n expressions, params injected by Brevo) ───
// Brevo replaces {{params.KEY}} server-side after receiving the API call

const passHtml = '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:24px"><h2 style="color:#166534;margin:0 0 10px">Congratulations, {{params.studentName}}!</h2><p style="color:#374151;font-size:15px;margin:0">You passed <strong>{{params.examCode}}</strong> with <strong style="color:#16a34a;font-size:22px">{{params.score}}%</strong></p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Well done! The next practice set is now unlocked on your dashboard.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Go to Dashboard</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>';

const failHtml = '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#fef2f2;border-left:4px solid #dc2626;padding:24px"><h2 style="color:#991b1b;margin:0 0 10px">EvalOS Result - {{params.examCode}}</h2><p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, you scored <strong style="color:#dc2626;font-size:22px">{{params.score}}%</strong>. You need 90% to pass.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Review the explanations on your results page and retake when ready. You have <strong>{{params.attemptsLeft}}</strong> attempt(s) remaining.</p><a href="https://evalos.i3technologies.co.ke/dashboard" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:12px">Review Results</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>';

const inviteHtml = '<div style="font-family:Arial,sans-serif;max-width:580px;margin:0 auto"><div style="background:#0f172a;padding:18px 24px;border-radius:8px 8px 0 0"><span style="color:#60a5fa;font-size:26px;font-weight:900;letter-spacing:2px">i3</span><span style="color:#94a3b8;font-size:10px;margin-left:10px;text-transform:uppercase">Technologies</span></div><div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:24px"><h2 style="color:#1e40af;margin:0 0 10px">Your IBM C1000-207 Practice Exams Are Ready</h2><p style="color:#374151;font-size:15px;margin:0">Hi {{params.studentName}}, you have been enrolled in EvalOS.</p></div><div style="padding:24px;background:#fff"><p style="color:#374151;line-height:1.6">Complete all 6 practice sets with 90%+ to earn your i3 completion certificate.</p><ul style="color:#374151;line-height:2"><li>6 sets, 60 questions each, 90 minutes</li><li>Instant results with full explanations</li><li>Downloadable completion certificate</li></ul><a href="https://evalos.i3technologies.co.ke" style="display:inline-block;background:#0f172a;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">Start Your First Exam</a></div><div style="padding:14px 24px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px;text-align:center">EvalOS &middot; i3 Technologies &middot; evalos.i3technologies.co.ke</div></div>';

// ── Build Brevo node using httpRequest with rawBody JSON expression ───────────
// The body is a single n8n expression string that evaluates to valid JSON at runtime
function brevoNode(id, name, position, subjectExpr, htmlContent, extraParams) {
  // Build the JSON body as a JS template that n8n will evaluate
  // We embed the Brevo params using $json references inside the expression
  const bodyExpr = [
    '={',
    '  "sender": {"name":"' + FROM_NAME + '","email":"' + FROM_EMAIL + '"},',
    '  "to": [{"email":"{{$json.body.studentEmail}}","name":"{{$json.body.studentName}}"}],',
    '  "subject": "' + subjectExpr + '",',
    '  "htmlContent": ' + JSON.stringify(htmlContent) + ',',
    '  "params": {',
    '    "studentName":"{{$json.body.studentName}}",',
    '    "studentEmail":"{{$json.body.studentEmail}}",',
    '    "examCode":"{{$json.body.examCode}}",',
    '    "score":"{{$json.body.score}}",',
    '    "passed":"{{$json.body.passed}}",',
    '    "attemptsLeft":"{{$json.body.attemptsLeft}}"',
    (extraParams ? (',' + extraParams) : ''),
    '  }',
    '}'
  ].join('');

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
          { name: 'api-key', value: BREVO_KEY },
          { name: 'Accept',  value: 'application/json' }
        ]
      },
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      // body is a single expression evaluated by n8n at runtime
      body: '={{ JSON.stringify({'
        + '"sender":{"name":"' + FROM_NAME + '","email":"' + FROM_EMAIL + '"},'
        + '"to":[{"email":$json.body.studentEmail,"name":$json.body.studentName}],'
        + '"subject":"' + subjectExpr + '",'
        + '"htmlContent":' + JSON.stringify(htmlContent) + ','
        + '"params":{"studentName":$json.body.studentName,"studentEmail":$json.body.studentEmail,"examCode":$json.body.examCode,"score":String($json.body.score),"passed":String($json.body.passed),"attemptsLeft":String($json.body.attemptsLeft || 0)}'
        + '}) }}',
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
          { name: 'api-key', value: BREVO_KEY },
          { name: 'Accept',  value: 'application/json' }
        ]
      },
      sendBody: true,
      contentType: 'raw',
      rawContentType: 'application/json',
      body: '={{ JSON.stringify({'
        + '"sender":{"name":"' + FROM_NAME + '","email":"' + FROM_EMAIL + '"},'
        + '"to":[{"email":"' + ADMIN_EMAIL + '","name":"Sebastian Njagi"}],'
        + '"subject":"[EvalOS] "+$json.body.studentName+" - "+String($json.body.score)+"% on "+$json.body.examCode,'
        + '"textContent":"Student: "+$json.body.studentName+" ("+$json.body.studentEmail+")\\nExam: "+$json.body.examCode+"\\nScore: "+String($json.body.score)+"%\\nPassed: "+String($json.body.passed)+"\\nEvent: "+$json.body.event'
        + '}) }}',
      options: {}
    }
  };
}

// ── Nodes ─────────────────────────────────────────────────────────────────────
const nodes = [
  {
    id: 'n-wh', name: 'EvalOS Webhook',
    type: 'n8n-nodes-base.webhook', position: [0, 0],
    webhookId: 'evalos-events-hook', typeVersion: 2,
    parameters: { path: 'evalos-events', httpMethod: 'POST', responseMode: 'onReceived', options: {} }
  },
  {
    id: 'n-if', name: 'Passed?',
    type: 'n8n-nodes-base.if', position: [240, 0],
    typeVersion: 1,
    parameters: { conditions: { boolean: [{ value1: '={{$json.body.passed}}', value2: true }] } }
  },
  brevoNode('n-pe', 'Pass Email',  [480, -180],
    '={{$json.body.examCode}} - Passed {{$json.body.score}}%', passHtml),
  brevoNode('n-fe', 'Fail Email',  [480,  180],
    '={{$json.body.examCode}} result: {{$json.body.score}}% (need 90%)', failHtml),
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

// ── REST helper ───────────────────────────────────────────────────────────────
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

// ── Run ───────────────────────────────────────────────────────────────────────
api('POST', '/rest/login',
  { email: 'snjagi@i3technologies.co.ke', password: 'EvalOS@Admin2026!' }, null,
  (s, h) => {
    if (s !== 200) { process.stderr.write('LOGIN FAILED '+s+'\n'); process.exit(1); }
    const ck = (h['set-cookie']||[]).map(c=>c.split(';')[0]).join('; ');
    process.stdout.write('[1/4] Logged in\n');

    api('PATCH', '/rest/workflows/'+WF, { active: false }, ck, (s2) => {
      process.stdout.write('[2/4] Deactivated: '+s2+'\n');
      api('PATCH', '/rest/workflows/'+WF, { nodes, connections }, ck, (s3,_,b3) => {
        process.stdout.write('[3/4] Patched: '+s3+'\n');
        if (s3 !== 200) { process.stderr.write('ERR: '+b3.substring(0,400)+'\n'); process.exit(1); }
        setTimeout(() => {
          api('PATCH', '/rest/workflows/'+WF, { active: true }, ck, (s4) => {
            process.stdout.write('[4/4] Reactivated: '+s4+'\n');
            process.stdout.write('DONE\n');
          });
        }, 800);
      });
    });
  }
);
