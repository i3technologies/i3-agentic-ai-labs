"""
STEP-P1-01: Hardcoded credential removed.
Retrieve the LiteLLM key at runtime:
  export LITELLM_KEY=$(vault kv get -field=master_key i3/model-gateway/litellm)
  python test_litellm_py.py
"""
import os
import urllib.request
import json
import time

BASE = "http://localhost:4000"
KEY = os.environ.get("LITELLM_KEY", "")
if not KEY:
    raise SystemExit(
        "ERROR: LITELLM_KEY env var not set.\n"
        "Run: export LITELLM_KEY=$(vault kv get -field=master_key i3/model-gateway/litellm)"
    )

HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def post(path, body, timeout=120):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=HDR, method="POST")
    try:
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=timeout)
        ms = int((time.time() - t0) * 1000)
        resp = json.loads(r.read())
        return r.status, ms, resp
    except Exception as e:
        return 0, 0, str(e)


print("=== LiteLLM Inference Tests ===\n")

for model in ["granite-nano", "qwen-fast", "coder"]:
    print(f"Testing {model}...")
    status, ms, resp = post("/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: PASS"}],
        "max_tokens": 5,
    })
    if status == 200:
        content = resp["choices"][0]["message"]["content"].strip()
        print(f"  HTTP {status} | {ms}ms | response: {repr(content)}\n")
    else:
        print(f"  FAIL HTTP {status} | {str(resp)[:200]}\n")

print("Testing embed...")
status, ms, resp = post("/embeddings", {"model": "embed", "input": "test embedding"})
if status == 200:
    dims = len(resp["data"][0]["embedding"])
    print(f"  HTTP {status} | {ms}ms | dimensions: {dims}\n")
else:
    print(f"  FAIL HTTP {status} | {str(resp)[:200]}\n")

print("=== Done ===")
