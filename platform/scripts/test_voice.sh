#!/bin/bash
# Test Voice TTS
echo "=== TTS Test ==="
TTS_IP=$(getent hosts voice-tts.i3-voice.svc.cluster.local | awk '{print $1}')
HTTP=$(curl -s -o /tmp/tts_out.wav -w "%{http_code}" \
  -X POST "http://voice-tts.i3-voice.svc.cluster.local:5000/v1/tts" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${VOICE_API_KEY:-changeme}" \
  -d '{"text":"Hello, this is a test.","voice":"en"}' 2>&1)
echo "TTS HTTP: $HTTP"
if [ "$HTTP" = "200" ]; then
  SIZE=$(wc -c < /tmp/tts_out.wav)
  echo "TTS response size: $SIZE bytes"
else
  cat /tmp/tts_out.wav
fi

echo ""
echo "=== STT Test ==="
# Generate a minimal WAV header for testing (mono, 16kHz, 1s silence)
python3 -c "
import struct,wave,io
buf=io.BytesIO()
with wave.open(buf,'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
    w.writeframes(b'\x00\x00'*16000)
open('/tmp/test.wav','wb').write(buf.getvalue())
print('WAV generated:',len(buf.getvalue()),'bytes')
"
HTTP2=$(curl -s -o /tmp/stt_out.json -w "%{http_code}" \
  -X POST "http://voice-stt.i3-voice.svc.cluster.local:5001/v1/transcribe" \
  -H "X-API-Key: ${VOICE_API_KEY:-changeme}" \
  -F "audio=@/tmp/test.wav" 2>&1)
echo "STT HTTP: $HTTP2"
cat /tmp/stt_out.json
