const http = require('http');
const lb = JSON.stringify({email:'snjagi@i3technologies.co.ke',password:'EvalOS@Admin2026!'});
const lr = http.request({hostname:'localhost',port:5678,path:'/rest/login',method:'POST',
  headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(lb)}
}, res=>{
  const cookie=(res.headers['set-cookie']||[]).map(c=>c.split(';')[0]).join('; ');
  res.resume();
  res.on('end',()=>{
    const gr=http.request({hostname:'localhost',port:5678,
      path:'/rest/executions/32?includeData=true',method:'GET',
      headers:{'Cookie':cookie}
    },res2=>{
      let d='';res2.on('data',c=>d+=c);
      res2.on('end',()=>{
        const hits=['message','ECONNREFUSED','Invalid login','535','534','Username','password','SMTP','connect ETIMEDOUT','NodeSSL','certificate','auth'];
        hits.forEach(h=>{
          const i=d.indexOf(h);
          if(i>-1) console.log(h+':', d.substring(Math.max(0,i-10),i+150));
        });
      });
    });
    gr.end();
  });
});
lr.write(lb);lr.end();
