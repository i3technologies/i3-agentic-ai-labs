const http = require('http');
// STEP-P1-01: Hardcoded credential removed. Use env var N8N_ADMIN_PASS (from OpenBao i3/n8n/admin).
const N8N_PASS = process.env.N8N_ADMIN_PASS || (() => { console.error('ERROR: N8N_ADMIN_PASS not set. export N8N_ADMIN_PASS=$(vault kv get -field=password i3/n8n/admin)'); process.exit(1); })();
const lb = JSON.stringify({email:'snjagi@i3technologies.co.ke',password:N8N_PASS});
const lr = http.request({hostname:'localhost',port:5678,path:'/rest/login',method:'POST',
  headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(lb)}
},res=>{
  const cookie=(res.headers['set-cookie']||[]).map(c=>c.split(';')[0]).join('; ');
  res.resume();
  res.on('end',()=>{
    const execId = process.argv[2] || '36';
    const gr=http.request({hostname:'localhost',port:5678,
      path:'/rest/executions/'+execId+'?includeData=true',method:'GET',
      headers:{'Cookie':cookie}
    },res2=>{
      let d='';res2.on('data',c=>d+=c);
      res2.on('end',()=>{
        const keywords = [
          'Invalid','error','Error','decryp','ETIMEDOUT','ECONNREFUSED',
          'ENOTFOUND','400','401','403','422','500','message','htmlContent',
          'sender','Unprocessable','not verified','domain','api-key'
        ];
        const found = new Set();
        keywords.forEach(k=>{
          let i = d.indexOf(k);
          while(i>-1 && found.size < 8) {
            const snip = d.substring(Math.max(0,i-20),i+180);
            if(!snip.includes('PostHog') && !snip.includes('166534') && !snip.includes('991b1b')) {
              process.stdout.write('['+k+']: '+snip+'\n---\n');
              found.add(k);
            }
            i = d.indexOf(k, i+1);
          }
        });
        process.stdout.write('status: '+JSON.parse(d).status+'\n');
      });
    });
    gr.end();
  });
});
lr.write(lb);lr.end();
