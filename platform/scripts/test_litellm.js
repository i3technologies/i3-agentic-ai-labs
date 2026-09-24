// STEP-P1-01: Hardcoded credential removed.
// Retrieve the LiteLLM key at runtime: vault kv get -field=master_key i3/model-gateway/litellm
// Usage:  LITELLM_KEY=$(vault kv get -field=master_key i3/model-gateway/litellm) node test_litellm.js
const http = require('http');
const body = JSON.stringify({
  model: 'qwen-fast',
  messages: [{ role: 'user', content: 'Reply with exactly: OK' }],
  max_tokens: 10
});

const key = process.env.LITELLM_KEY;
if (!key) {
  console.error('ERROR: LITELLM_KEY env var not set. Run: export LITELLM_KEY=$(vault kv get -field=master_key i3/model-gateway/litellm)');
  process.exit(1);
}

const options = {
  hostname: 'litellm-proxy.i3-model-gateway.svc.cluster.local',
  port: 4000,
  path: '/chat/completions',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + key,
    'Content-Length': Buffer.byteLength(body)
  }
};
const req = http.request(options, res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    try {
      const parsed = JSON.parse(data);
      const content = parsed.choices?.[0]?.message?.content;
      console.log('STATUS:', res.statusCode, '| RESPONSE:', content);
    } catch {
      console.log('STATUS:', res.statusCode, '| RAW:', data.slice(0, 300));
    }
  });
});
req.on('error', e => { console.error('ERROR:', e.message); process.exit(1); });
req.setTimeout(60000, () => { console.error('TIMEOUT'); req.destroy(); process.exit(1); });
req.write(body);
req.end();
