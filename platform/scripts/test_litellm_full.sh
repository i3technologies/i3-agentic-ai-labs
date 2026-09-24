#!/bin/bash
# Comprehensive LiteLLM + Ollama inference test
# API key retrieved at runtime from OpenBao — no plaintext secrets in source
echo "=== LiteLLM Model Tests ==="
BASE="http://localhost:4000"
KEY=$(vault kv get -field=key i3/litellm/api-key)

for MODEL in "granite-nano" "qwen-fast" "coder"; do
  echo ""
  echo "--- Testing: $MODEL ---"
  START=$(date +%s%N)
  RESP=$(curl -s -w "\nHTTP:%{http_code}" -X POST "$BASE/chat/completions" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $KEY" \
    --max-time 120 \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly the word: PASS\"}],\"max_tokens\":5}")
  END=$(date +%s%N)
  MS=$(( (END - START) / 1000000 ))
  HTTP_CODE=$(echo "$RESP" | grep "HTTP:" | cut -d: -f2)
  CONTENT=$(echo "$RESP" | python3 -c "import sys,json; lines=sys.stdin.read().split('\n'); body='\n'.join(l for l in lines if not l.startswith('HTTP:')); d=json.loads(body); print(d['choices'][0]['message']['content'])" 2>/dev/null)
  echo "HTTP: $HTTP_CODE | ${MS}ms | Response: $CONTENT"
done

echo ""
echo "--- Testing: embed ---"
EMBED_RESP=$(curl -s -w "\nHTTP:%{http_code}" -X POST "$BASE/embeddings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  --max-time 30 \
  -d '{"model":"embed","input":"test embedding"}')
HTTP_EMBED=$(echo "$EMBED_RESP" | grep "HTTP:" | cut -d: -f2)
DIM=$(echo "$EMBED_RESP" | python3 -c "import sys,json;lines=sys.stdin.read().split('\n');body='\n'.join(l for l in lines if not l.startswith('HTTP:'));d=json.loads(body);print(len(d['data'][0]['embedding']))" 2>/dev/null)
echo "HTTP: $HTTP_EMBED | Embedding dimensions: $DIM"
