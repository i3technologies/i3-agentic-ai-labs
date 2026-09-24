#!/bin/sh
# STEP-P1-01: Hardcoded credential removed.
# Retrieve the LiteLLM key at runtime:
#   export LITELLM_KEY=$(vault kv get -field=master_key i3/model-gateway/litellm)
#   sh test_litellm_from_evalos.sh
if [ -z "$LITELLM_KEY" ]; then
  echo "ERROR: LITELLM_KEY env var not set." >&2
  echo "Run: export LITELLM_KEY=\$(vault kv get -field=master_key i3/model-gateway/litellm)" >&2
  exit 1
fi
wget -q -O- --timeout=60 \
  --header="Authorization: Bearer ${LITELLM_KEY}" \
  --header="Content-Type: application/json" \
  --post-data='{"model":"qwen-fast","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":10}' \
  "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/chat/completions"
