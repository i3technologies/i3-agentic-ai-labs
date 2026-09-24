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
    const gr=http.request({hostname:'localhost',port:5678,
      path:'/rest/executions/33?includeData=true',method:'GET',
      headers:{'Cookie':cookie}
    },res2=>{
      let d='';
      res2.on('data',c=>d+=c);
      res2.on('end',()=>{
        // The execution data is a compressed reference structure
        // Parse it properly
        try {
          const parsed = JSON.parse(d);
          const raw = parsed.data || parsed;
          // data field is a stringified compressed object
          if (typeof raw.data === 'string') {
            // Decompress by parsing the reference structure
            const decompressed = raw.data;
            // Look for error-related substrings
            const keywords = ['Invalid','credentials could not','decryp','535','534','ECONNREFUSED','ETIMEDOUT','getaddrinfo','connect EREFUSED','wrong','Bad','auth','535-5','Username and Password','Application-specific'];
            keywords.forEach(k => {
              let i = decompressed.indexOf(k);
              if (i > -1) {
                process.stdout.write('FOUND ['+k+']: '+decompressed.substring(Math.max(0,i-30), i+200)+'\n---\n');
              }
            });
          }
          // Also check stoppedAt and status
          process.stdout.write('status: '+raw.status+'\n');
          process.stdout.write('stoppedAt: '+raw.stoppedAt+'\n');
        } catch(e) {
          process.stdout.write('PARSE ERR: '+e.message+'\n');
          process.stdout.write('RAW: '+d.substring(0,500)+'\n');
        }
      });
    });
    gr.end();
  });
});
lr.write(lb);lr.end();
