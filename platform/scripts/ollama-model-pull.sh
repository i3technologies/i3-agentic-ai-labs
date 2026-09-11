#!/usr/bin/env bash
# ============================================================
# ollama-model-pull.sh
# Pull all required OSS models into the i3-model-gateway Ollama
# instance. Run this once after expanding the PVC to 80 Gi.
#
# Usage:
#   # 1. Patch PVC size first (requires StorageClass with allowVolumeExpansion)
#   oc patch pvc ollama-data-ollama-0 -n i3-model-gateway \
#     --type=merge -p '{"spec":{"resources":{"requests":{"storage":"80Gi"}}}}'
#
#   # 2. Port-forward Ollama so this script can reach it locally
#   oc port-forward svc/ollama-service -n i3-model-gateway 11434:11434 &
#   PF_PID=$!
#
#   # 3. Run this script
#   bash platform/scripts/ollama-model-pull.sh
#
#   # 4. Stop port-forward
#   kill $PF_PID
#
# Alternatively exec into the Ollama pod directly:
#   POD=$(oc get pod -n i3-model-gateway -l app=ollama -o name | head -1)
#   oc exec -it -n i3-model-gateway $POD -- bash
#   # then run: ollama pull <model>
# ============================================================

set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

pull() {
  local model="$1"
  local desc="$2"
  echo ""
  echo "══════════════════════════════════════════════════"
  echo "  Pulling: $model"
  echo "  Purpose: $desc"
  echo "══════════════════════════════════════════════════"
  curl -sf "${OLLAMA_HOST}/api/pull" \
    -X POST \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"${model}\"}" | \
    python3 -c "
import sys, json
for line in sys.stdin:
  line = line.strip()
  if not line: continue
  try:
    d = json.loads(line)
    status = d.get('status','')
    total  = d.get('total',0)
    compl  = d.get('completed',0)
    if total > 0:
      pct = round(compl/total*100,1)
      print(f'  {status} [{pct}%]', end='\r', flush=True)
    else:
      print(f'  {status}', flush=True)
  except: pass
print()
"
  echo "  ✓ Done: $model"
}

echo "i3 Platform — Ollama Model Pull"
echo "Target: ${OLLAMA_HOST}"
echo ""

# ── Tier 3: Edge / Embeddings (always warm, tiny RAM) ────────
pull "nomic-embed-text:v1.5"          "RAG embeddings — 768-dim, 274 MB. Powers all ChromaDB collections."
pull "granite3.1-dense:2b"            "IBM Granite 3.1 2B — intent routing, fast classification. Already pulled — skip if present."

# ── Tier 2: RAG / Interactive Chat ───────────────────────────
pull "qwen2.5:7b-instruct-q4_K_M"    "Qwen2.5 7B — primary chat model. Study Coach (upgrade from Mistral 7B), RAG, Zuri, Onboarding."
pull "qwen2.5-coder:7b-instruct-q4_K_M" "Qwen2.5-Coder 7B — AI Interview code questions, Coding Lab, code review."

# ── Tier 1: Heavy Reasoning (pull last — largest files) ──────
pull "qwen2.5:14b-instruct-q4_K_M"   "Qwen2.5 14B — AI interview evaluation, PMaaS war room reports, AfroERP finance agent."
pull "llava:13b-v1.6-mistral-q4"     "LLaVA 13B — multimodal image+text. Certificate OCR, invoice parsing, diagram analysis."

echo ""
echo "══════════════════════════════════════════════════"
echo "  All models pulled successfully."
echo ""
echo "  Verify with:"
echo "    curl ${OLLAMA_HOST}/api/tags | python3 -m json.tool"
echo ""
echo "  Smoke-test via LiteLLM (after deploying litellm-deploy.yaml):"
echo "    curl https://litellm.i3technologies.co.ke/v1/chat/completions \\"
echo "      -H 'Authorization: Bearer \$LITELLM_MASTER_KEY' \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"model\":\"granite-nano\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}'"
echo "══════════════════════════════════════════════════"
