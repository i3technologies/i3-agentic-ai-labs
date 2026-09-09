const http = require('http');
const WF = '319537be-cd59-4645-9b5e-f183acfecf7e';
const CR  = 'd035f766-f0fe-46a4-9962-1db39acfad4e';

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

const J = (s) => '={{' + s + '}}';   // n8n expression helper
const smtpCred = { smtp: { id: CR, name: 'i3 Gmail SMTP' } };

const nodes = [
  { id:'n-wh', name:'EvalOS Webhook', type:'n8n-nodes-base.webhook', position:[0,0],
    webhookId:'evalos-events-hook', typeVersion:2,
    parameters:{ path:'evalos-events', httpMethod:'POST', responseMode:'onReceived', options:{} }
  },
  // IF node typeVersion:1 — uses simple boolean array, no 'disabled' property needed
  { id:'n-if', name:'Passed?', type:'n8n-nodes-base.if', position:[240,0],
    typeVersion:1,
    parameters:{ conditions:{ boolean:[{ value1:J('$json.body.passed'), value2:true }] } }
  },
  { id:'n-pe', name:'Pass Email', type:'n8n-nodes-base.emailSend', position:[480,-140],
    typeVersion:2.1, credentials: smtpCred,
    parameters:{
      emailType:'html', fromEmail:'pmukiti@gmail.com',
      toEmail: J('$json.body.studentEmail'),
      subject: J('"Passed "+$json.body.examCode+" - "+$json.body.score+"%"'),
      html: '<div style="font-family:sans-serif;max-width:580px;margin:0 auto">'
          + '<div style="background:#0f172a;padding:18px 22px;border-radius:8px 8px 0 0">'
          + '<span style="color:#60a5fa;font-size:26px;font-weight:900">i3</span>'
          + '<span style="color:#94a3b8;font-size:10px;margin-left:8px">TECHNOLOGIES</span></div>'
          + '<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:22px">'
          + '<h2 style="color:#166534;margin:0 0 8px">Congratulations {{$json.body.studentName}}!</h2>'
          + '<p style="color:#374151;font-size:15px;margin:0">You passed <b>{{$json.body.examCode}}</b>'
          + ' with <b style="color:#16a34a;font-size:20px">{{$json.body.score}}%</b></p></div>'
          + '<div style="padding:22px;background:#fff">'
          + '<p style="color:#374151">The next set is now unlocked. Keep going!</p>'
          + '<a href="https://evalos.i3technologies.co.ke/dashboard"'
          + ' style="display:inline-block;background:#0f172a;color:#fff;padding:11px 26px;'
          + 'border-radius:6px;text-decoration:none;font-weight:bold">Go to Dashboard</a></div>'
          + '<div style="padding:14px 22px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px">'
          + 'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>',
      options:{}
    }
  },
  { id:'n-fe', name:'Fail Email', type:'n8n-nodes-base.emailSend', position:[480,140],
    typeVersion:2.1, credentials: smtpCred,
    parameters:{
      emailType:'html', fromEmail:'pmukiti@gmail.com',
      toEmail: J('$json.body.studentEmail'),
      subject: J('$json.body.examCode+" result: "+$json.body.score+"% (need 90%)"'),
      html: '<div style="font-family:sans-serif;max-width:580px;margin:0 auto">'
          + '<div style="background:#0f172a;padding:18px 22px;border-radius:8px 8px 0 0">'
          + '<span style="color:#60a5fa;font-size:26px;font-weight:900">i3</span>'
          + '<span style="color:#94a3b8;font-size:10px;margin-left:8px">TECHNOLOGIES</span></div>'
          + '<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:22px">'
          + '<h2 style="color:#991b1b;margin:0 0 8px">EvalOS Result - {{$json.body.examCode}}</h2>'
          + '<p style="color:#374151;font-size:15px;margin:0">Hi {{$json.body.studentName}}, you scored'
          + ' <b style="color:#dc2626;font-size:20px">{{$json.body.score}}%</b>. Need 90% to pass.</p></div>'
          + '<div style="padding:22px;background:#fff">'
          + '<p style="color:#374151">Review explanations and retake when ready.'
          + ' You have {{$json.body.attemptsLeft}} attempt(s) remaining.</p>'
          + '<a href="https://evalos.i3technologies.co.ke/dashboard"'
          + ' style="display:inline-block;background:#0f172a;color:#fff;padding:11px 26px;'
          + 'border-radius:6px;text-decoration:none;font-weight:bold">Review Results</a></div>'
          + '<div style="padding:14px 22px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:11px">'
          + 'EvalOS &middot; i3 Technologies &middot; Nairobi, Kenya</div></div>',
      options:{}
    }
  },
  { id:'n-aa', name:'Admin Alert', type:'n8n-nodes-base.emailSend', position:[720,0],
    typeVersion:2.1, credentials: smtpCred,
    parameters:{
      emailType:'text', fromEmail:'pmukiti@gmail.com',
      toEmail:'snjagi@i3technologies.co.ke',
      subject: J('"[EvalOS] "+$json.body.studentName+" - "+$json.body.score+"% on "+$json.body.examCode'),
      text:    J('"Student: "+$json.body.studentName+" ("+$json.body.studentEmail+")\\nExam: "+$json.body.examCode+"\\nScore: "+$json.body.score+"%\\nPassed: "+$json.body.passed'),
      options:{}
    }
  }
];

const connections = {
  'EvalOS Webhook': { main: [[{ node:'Passed?',     type:'main', index:0 }]] },
  'Passed?':        { main: [[{ node:'Pass Email',  type:'main', index:0 }],
                              [{ node:'Fail Email',  type:'main', index:0 }]] },
  'Pass Email':     { main: [[{ node:'Admin Alert', type:'main', index:0 }]] },
  'Fail Email':     { main: [[{ node:'Admin Alert', type:'main', index:0 }]] }
};

// ── Run ───────────────────────────────────────────────────────────────────────
api('POST','/rest/login',{email:'snjagi@i3technologies.co.ke',password:'EvalOS@Admin2026!'},null,(s,h)=>{
  if(s!==200){ process.stderr.write('LOGIN FAILED '+s+'\n'); process.exit(1); }
  const ck = (h['set-cookie']||[]).map(c=>c.split(';')[0]).join('; ');
  process.stdout.write('Logged in\n');

  // Deactivate
  api('PATCH','/rest/workflows/'+WF,{active:false},ck,(s2)=>{
    process.stdout.write('Deactivated: '+s2+'\n');

    // PATCH nodes + connections
    api('PATCH','/rest/workflows/'+WF,{ nodes, connections },ck,(s3,_,b3)=>{
      process.stdout.write('Nodes patched: '+s3+'\n');
      if(s3!==200){ process.stderr.write('PATCH ERR: '+b3.substring(0,300)+'\n'); process.exit(1); }

      // Reactivate
      setTimeout(()=>{
        api('PATCH','/rest/workflows/'+WF,{active:true},ck,(s4)=>{
          process.stdout.write('Reactivated: '+s4+'\n');
          process.stdout.write('DONE\n');
        });
      }, 800);
    });
  });
});
