# i3 Voice AI Stack

**Namespace:** `i3-voice` (new — to be created)
**Quota:** 16 Gi RAM, 8 vCPU
**Purpose:** Shared voice services for all platform products

## Services

### TTS + Voice Cloning: XTTS-v2 (Coqui)
- **Licence:** MPL-2.0 (open-source)
- **Endpoints:**
  - `POST /v1/tts` — text + voice_id → WAV audio
  - `POST /v1/clone` — audio file (≥6s WAV) → voice_id stored in OpenBao
  - `GET /v1/voices` — list available cloned voices
- **Deploy:** `xtts-deploy.yaml` (FastAPI wrapper around Coqui XTTS-v2)

### STT: faster-whisper
- **Licence:** MIT
- **Endpoints:**
  - `POST /v1/transcribe` — audio file → { transcript, language, segments }
  - `POST /v1/transcribe/stream` — streaming transcription (WebSocket)
- **Languages:** English, Swahili, French + 96 others
- **Deploy:** `whisper-deploy.yaml`

### PMaaS AI Caller (Asterisk SIP)
- **Deploy:** `asterisk-deploy.yaml`
- **Flow:** Campaign scheduler → Asterisk dial → XTTS-v2 opens → Whisper transcribes voter → LLM responds → XTTS-v2 speaks → loop
- **SIP Trunk:** Configured per PMaaS campaign (external SIP provider)

## Internal Service URLs
- TTS: `http://xtts.i3-voice.svc.cluster.local:5002`
- STT: `http://whisper.i3-voice.svc.cluster.local:9000`
- Caller: `http://asterisk.i3-voice.svc.cluster.local:8088` (AMI REST)

## Status: 📋 Phase 3 — To Build
