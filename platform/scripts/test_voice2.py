import urllib.request, urllib.error, json, wave, io, time

TTS_URL = "http://172.17.57.29:8000"
STT_URL = "http://172.17.16.117:8001"
API_KEY = "changeme"

def test_tts():
    print("=== TTS Test ===")
    body = json.dumps({"text": "Hello, this is a platform test.", "voice": "en"}).encode()
    for path in ["/v1/tts", "/tts", "/synthesize", "/api/tts", "/"]:
        try:
            req = urllib.request.Request(f"{TTS_URL}{path}", data=body,
                headers={"Content-Type": "application/json", "X-API-Key": API_KEY}, method="POST")
            t0 = time.time()
            r = urllib.request.urlopen(req, timeout=20)
            ms = int((time.time()-t0)*1000)
            audio = r.read()
            print(f"  PASS {path}: HTTP {r.status} | {ms}ms | {len(audio)} bytes | content-type: {r.headers.get('content-type','?')}")
            return True
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} on {path}: {e.read().decode()[:80]}")
        except Exception as e:
            print(f"  ERR on {path}: {type(e).__name__}: {str(e)[:80]}")
    return False

def test_stt():
    print("\n=== STT Test ===")
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 16000)
    wav_bytes = buf.getvalue()
    boundary = b"testboundary"
    body = (b"--" + boundary + b"\r\n" +
            b'Content-Disposition: form-data; name="audio"; filename="test.wav"\r\n' +
            b"Content-Type: audio/wav\r\n\r\n" + wav_bytes +
            b"\r\n--" + boundary + b"--\r\n")
    for path in ["/v1/transcribe", "/transcribe", "/stt", "/api/transcribe", "/"]:
        try:
            req = urllib.request.Request(f"{STT_URL}{path}", data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary.decode()}", "X-API-Key": API_KEY},
                method="POST")
            t0 = time.time()
            r = urllib.request.urlopen(req, timeout=30)
            ms = int((time.time()-t0)*1000)
            resp = r.read().decode()
            print(f"  PASS {path}: HTTP {r.status} | {ms}ms | {resp[:150]}")
            return True
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} on {path}: {e.read().decode()[:80]}")
        except Exception as e:
            print(f"  ERR on {path}: {type(e).__name__}: {str(e)[:80]}")
    return False

# Also GET root to see what endpoints exist
print("=== TTS Service Info ===")
try:
    r = urllib.request.urlopen(f"{TTS_URL}/", timeout=5)
    print(f"  GET /: HTTP {r.status} | {r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"  GET /: HTTP {e.code}")
except Exception as e:
    print(f"  GET /: {e}")

print("=== STT Service Info ===")
try:
    r = urllib.request.urlopen(f"{STT_URL}/", timeout=5)
    print(f"  GET /: HTTP {r.status} | {r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"  GET /: HTTP {e.code}")
except Exception as e:
    print(f"  GET /: {e}")

test_tts()
test_stt()
