import urllib.request, urllib.error, json, struct, wave, io, time

def test_tts():
    print("=== TTS Test ===")
    body = json.dumps({"text": "Hello, this is a platform test.", "voice": "en"}).encode()
    req = urllib.request.Request(
        "http://voice-tts.i3-voice.svc.cluster.local:5000/v1/tts",
        data=body,
        headers={"Content-Type": "application/json", "X-API-Key": "changeme"},
        method="POST"
    )
    try:
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=30)
        ms = int((time.time()-t0)*1000)
        audio = r.read()
        print(f"  HTTP {r.status} | {ms}ms | audio bytes: {len(audio)}")
        return r.status == 200
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  FAIL HTTP {e.code} | {body[:200]}")
        return False
    except Exception as e:
        print(f"  FAIL {e}")
        return False

def test_stt():
    print("\n=== STT Test ===")
    # Build a minimal 1s 16kHz mono WAV
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 16000)
    wav_bytes = buf.getvalue()

    boundary = b"--boundary"
    body = (
        boundary + b"\r\n" +
        b'Content-Disposition: form-data; name="audio"; filename="test.wav"\r\n' +
        b"Content-Type: audio/wav\r\n\r\n" +
        wav_bytes + b"\r\n" + boundary + b"--\r\n"
    )
    req = urllib.request.Request(
        "http://voice-stt.i3-voice.svc.cluster.local:5001/v1/transcribe",
        data=body,
        headers={
            "Content-Type": "multipart/form-data; boundary=boundary",
            "X-API-Key": "changeme"
        },
        method="POST"
    )
    try:
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=30)
        ms = int((time.time()-t0)*1000)
        resp = r.read().decode()
        print(f"  HTTP {r.status} | {ms}ms | response: {resp[:200]}")
        return r.status == 200
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        print(f"  FAIL HTTP {e.code} | {body_txt[:200]}")
        return False
    except Exception as e:
        print(f"  FAIL {e}")
        return False

test_tts()
test_stt()
