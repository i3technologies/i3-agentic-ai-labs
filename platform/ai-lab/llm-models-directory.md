# i3 Platform — LLM & SLM Models Directory
> **Definitive reference for all AI models deployed on the i3 ROKS platform.**
> Last updated: 10 September 2026 · Cluster: i3-platform (IBM ROKS 4.17, eu-de)
> All models are 100% open-source and run on CPU (bx2.4x16 workers, no GPU).

---

## Model Deployment Overview

| Namespace        | Inference Engine | Models Loaded           | PVC Size |
|-----------------|-----------------|------------------------|----------|
| `i3-model-gateway` | Ollama StatefulSet | Qwen14B, LLaVA13B, Qwen7B, Qwen-Coder7B, Granite2B, Nomic-embed | 80 Gi |
| `i3-ott`           | Ollama Deployment  | Mistral 7B (EvalOS Study Coach) | 20 Gi |
| `i3-voice`         | FastAPI (Coqui/Whisper) | XTTS-v2, faster-whisper-large-v3 | 10 Gi |

---

## Tier 1 — Heavy Reasoning (30–120s on CPU, use for batch/async tasks)

### `qwen2.5:14b-instruct-q4_K_M`
| Property | Value |
|----------|-------|
| **Developer** | Alibaba Cloud (Qwen Team) |
| **Licence** | Apache 2.0 |
| **Parameters** | 14.7 billion |
| **Quantisation** | Q4_K_M (GGUF) |
| **RAM required** | ~9.0 GB |
| **Context window** | 128K tokens |
| **Ollama pull** | `ollama pull qwen2.5:14b-instruct-q4_K_M` |
| **LiteLLM name** | `qwen-heavy` |
| **Namespace** | `i3-model-gateway` |

**Best for:** Complex multi-step reasoning, long-form writing, detailed analysis, evaluation rubrics (AI Interview), financial narrative generation (AfroERP), PMaaS war room reports, agent planning.

**Not suitable for:** Real-time interactive chat (too slow on CPU), simple classifications.

**Recommended settings:**
```json
{ "temperature": 0.3, "top_p": 0.9, "num_predict": 1024, "timeout": 180 }
```

---

### `llava:13b-v1.6-mistral-q4`
| Property | Value |
|----------|-------|
| **Developer** | Haotian Liu et al. / LLaVA Team |
| **Licence** | Apache 2.0 |
| **Parameters** | 13 billion (Mistral 7B + CLIP ViT-L vision encoder) |
| **Quantisation** | Q4_K_M (GGUF) |
| **RAM required** | ~8.0 GB |
| **Ollama pull** | `ollama pull llava:13b-v1.6-mistral-q4` |
| **LiteLLM name** | `vision` |
| **Namespace** | `i3-model-gateway` |

**Best for:** Image + text understanding, document OCR, invoice/receipt parsing (AfroERP), certificate image validation, coding lab diagram analysis, multimodal Q&A in AI Lab.

**Recommended settings:**
```json
{ "temperature": 0.1, "top_p": 0.9, "num_predict": 512, "timeout": 120 }
```

---

## Tier 2 — RAG / Reasoning (10–45s on CPU, primary interactive models)

### `qwen2.5:7b-instruct-q4_K_M`
| Property | Value |
|----------|-------|
| **Developer** | Alibaba Cloud (Qwen Team) |
| **Licence** | Apache 2.0 |
| **Parameters** | 7.6 billion |
| **Quantisation** | Q4_K_M (GGUF) |
| **RAM required** | ~4.7 GB |
| **Context window** | 128K tokens |
| **Ollama pull** | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| **LiteLLM name** | `qwen-fast` |
| **Namespace** | `i3-model-gateway` |

**Best for:** EvalOS Study Coach, RAG-augmented answers (with ChromaDB), onboarding agent Q&A, i3-Engage campaign suggestions, AfroERP general assistant, interactive chat in Co-worker.

**Replaces:** `mistral-nemo:12b` (too large for CPU), `mistral:7b` (slightly weaker)

**Recommended settings:**
```json
{ "temperature": 0.7, "top_p": 0.9, "num_predict": 700, "timeout": 90 }
```

---

### `qwen2.5-coder:7b-instruct-q4_K_M`
| Property | Value |
|----------|-------|
| **Developer** | Alibaba Cloud (Qwen Team) |
| **Licence** | Apache 2.0 |
| **Parameters** | 7.6 billion (code-specialised) |
| **Quantisation** | Q4_K_M (GGUF) |
| **RAM required** | ~4.7 GB |
| **Context window** | 128K tokens |
| **Ollama pull** | `ollama pull qwen2.5-coder:7b-instruct-q4_K_M` |
| **LiteLLM name** | `coder` |
| **Namespace** | `i3-model-gateway` |

**Best for:** AI Lab coding labs (Python, JS, SQL, Bash), EvalOS code assessment evaluation, AfroERP scripting assistant, Co-worker code mode, Hackathon AI pair programmer.

**Replaces:** `deepseek-coder-v2:16b` (too large for CPU)

**Recommended settings:**
```json
{ "temperature": 0.2, "top_p": 0.95, "num_predict": 1024, "timeout": 90 }
```

---

## Tier 2 — Chat Baseline (already live)

### `mistral:7b-instruct-q4_K_M`
| Property | Value |
|----------|-------|
| **Developer** | Mistral AI |
| **Licence** | Apache 2.0 |
| **Parameters** | 7.3 billion |
| **Quantisation** | Q4_K_M (GGUF) |
| **RAM required** | ~4.4 GB |
| **Ollama pull** | Already pulled — `ollama list` in i3-ott |
| **LiteLLM name** | Not in gateway — direct Ollama call from EvalOS |
| **Namespace** | `i3-ott` (EvalOS Study Coach only) |

**Status:** Live and serving EvalOS Study Coach. Will be upgraded to route through LiteLLM with `qwen-fast` as the primary model (Phase 2).

---

## Tier 3 — Fast/Edge (sub-second to 5s, always warm)

### `granite3.1-dense:2b`
| Property | Value |
|----------|-------|
| **Developer** | IBM Research (open-weight) |
| **Licence** | Apache 2.0 |
| **Parameters** | 2.0 billion |
| **Quantisation** | Q4 (GGUF) |
| **RAM required** | ~1.6 GB |
| **Ollama pull** | Already pulled — running in `i3-model-gateway` |
| **LiteLLM name** | `granite-nano` |
| **Namespace** | `i3-model-gateway` |

**Best for:** Intent classification, quick yes/no decisions, short entity extraction, routing decisions inside LangGraph agents, pre-screening queries before escalating to larger models.

**Note:** IBM Granite models are open-weight and hosted on HuggingFace — they do NOT require watsonx.ai SaaS.

---

### `nomic-embed-text:v1.5`
| Property | Value |
|----------|-------|
| **Developer** | Nomic AI |
| **Licence** | Apache 2.0 |
| **Embedding dimensions** | 768 (Matryoshka — can reduce to 256/512) |
| **RAM required** | ~274 MB |
| **Ollama pull** | `ollama pull nomic-embed-text:v1.5` |
| **LiteLLM name** | `embed` |
| **Namespace** | `i3-model-gateway` |

**Best for:** All RAG embeddings. ChromaDB ingest and query for: exam corpus, onboarding docs, ERPNext KB, campaign materials, manifesto, AI Lab content.

**API usage (Ollama direct):**
```bash
curl http://ollama.i3-model-gateway.svc:11434/api/embed \
  -d '{"model":"nomic-embed-text:v1.5","input":"your text here"}'
```

---

## Voice Models (Namespace: `i3-voice`)

### `XTTS-v2` (Coqui TTS)
| Property | Value |
|----------|-------|
| **Developer** | Coqui AI |
| **Licence** | MPL-2.0 (open-source) |
| **Model size** | ~1.8 GB |
| **Capabilities** | TTS (17 languages incl. English, French, Spanish) + Zero-shot voice cloning from 6s audio |
| **Supported languages** | en, fr, es, pt, de, it, pl, tr, ru, nl, cs, ar, zh, hu, ko, ja, hi |
| **Docker image** | `ghcr.io/coqui-ai/tts:latest` or custom FastAPI wrapper |
| **API endpoint** | `POST /v1/tts` · `POST /v1/clone` |

**PMaaS Voice Clone workflow:**
1. Upload 30–60s WAV of candidate → `POST /v1/clone` → returns `voice_id`
2. `voice_id` stored securely in OpenBao
3. Generate speech: `POST /v1/tts` with `{ text, voice_id, language: "en" }`

**EvalOS audio feedback:** TTS of study coach report → student can listen on results page.

---

### `faster-whisper-large-v3`
| Property | Value |
|----------|-------|
| **Developer** | OpenAI (original) / Systran (faster-whisper port) |
| **Licence** | MIT |
| **Model size** | ~1.5 GB |
| **Languages** | 99 languages including Swahili (sw), English (en), Kikuyu |
| **Word Error Rate** | ~2.7% on English (state-of-the-art) |
| **API endpoint** | `POST /v1/transcribe` · params: audio file, language (optional auto-detect) |

**AI Interview usage:** Student records spoken answer → Whisper transcribes → LLM evaluates transcript.
**PMaaS inbound:** Voter speaks → Whisper transcribes → LLM generates response → XTTS-v2 speaks reply.

---

## LiteLLM Model Name Reference

All models are accessible via the LiteLLM OpenAI-compatible API at `https://litellm.i3technologies.co.ke/v1/`:

```
Model Name          → Physical Model                    → Use Case
---------------------------------------------------------------------------
granite-nano        → ollama/granite3.1-dense:2b        → Intent routing, fast classification
embed               → ollama/nomic-embed-text:v1.5      → Embeddings (not chat)
qwen-fast           → ollama/qwen2.5:7b-instruct-q4_K_M → Interactive chat, RAG, Study Coach
coder               → ollama/qwen2.5-coder:7b-instruct-q4_K_M → Code generation, review
qwen-heavy          → ollama/qwen2.5:14b-instruct-q4_K_M → Complex reasoning, evaluation
vision              → ollama/llava:13b-v1.6-mistral-q4  → Image + text tasks
```

**Authentication:** `Authorization: Bearer sk-litellm-i3-<master-key>`

**Example (Python):**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1",
    api_key="sk-litellm-i3-<key>"
)

response = client.chat.completions.create(
    model="qwen-fast",
    messages=[{"role": "user", "content": "Explain what IBM watsonx Orchestrate does."}]
)
print(response.choices[0].message.content)
```

---

## Capacity Planning

| Scenario | Models Active | RAM Used | Available Headroom |
|----------|--------------|----------|-------------------|
| Idle (no requests) | 0 | ~2 GB (Ollama process) | ~41 GB |
| Normal load | granite-nano + qwen-fast | ~6.3 GB | ~37 GB |
| Peak load | qwen-fast + coder | ~9.4 GB | ~34 GB |
| Heavy batch | qwen-heavy + nomic | ~9.3 GB | ~34 GB |
| Vision task | vision (LLaVA) | ~8 GB | ~35 GB |
| Worst case (all loaded) | All models | ~28.3 GB | ~15 GB ✓ |

**Note:** Ollama default timeout is 5 minutes. Models auto-unload after 5 min of inactivity.
Set `OLLAMA_KEEP_ALIVE=10m` for granite-nano and nomic-embed (always-on, small enough).

---

## Model Selection Decision Tree

```
Incoming request
    │
    ├── Is it an EMBEDDING request?
    │       └── Use: embed (nomic-embed-text)
    │
    ├── Is it IMAGE + TEXT?
    │       └── Use: vision (LLaVA 13B)
    │
    ├── Is it CODE generation/review?
    │       └── Use: coder (Qwen2.5-Coder 7B)
    │
    ├── Is it INTENT classification / routing (< 100 tokens output)?
    │       └── Use: granite-nano
    │
    ├── Does it need COMPLEX REASONING or EVALUATION (AI Interview, reports)?
    │       └── Use: qwen-heavy (Qwen2.5 14B) — async only
    │
    └── Everything else (chat, RAG answers, study coach, campaign content)
            └── Use: qwen-fast (Qwen2.5 7B)
```

---

## Adding a New Model

1. Check RAM budget: `oc describe quota i3-model-gateway-quota -n i3-model-gateway`
2. Pull on Ollama: `oc exec -n i3-model-gateway ollama-0 -- ollama pull <model-name>`
3. Add to LiteLLM ConfigMap: `platform/model-gateway/litellm/litellm-deploy.yaml`
4. Add entry to this file (llm-models-directory.md)
5. Test via LiteLLM: `curl .../v1/models` to confirm it appears
6. Add fallback chain in LiteLLM router_settings if applicable

---

## Licence Summary

| Model | Licence | Commercial Use |
|-------|---------|---------------|
| Qwen2.5 (all sizes) | Apache 2.0 | ✅ Free |
| LLaVA 13B | Apache 2.0 | ✅ Free |
| Mistral 7B | Apache 2.0 | ✅ Free |
| Granite 3.1 2B | Apache 2.0 | ✅ Free |
| Nomic-embed-text | Apache 2.0 | ✅ Free |
| XTTS-v2 (Coqui) | MPL-2.0 | ✅ Free (open-source) |
| faster-whisper | MIT | ✅ Free |

**All models are cleared for commercial deployment. No usage fees, no API billing, no SaaS dependency.**
