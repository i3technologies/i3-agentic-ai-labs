import urllib.request, urllib.error, json, time, socket

def check(label, url, timeout=8, expected_code=200, auth=None):
    headers = {}
    if auth:
        headers["Authorization"] = auth
    req = urllib.request.Request(url, headers=headers)
    try:
        t0 = time.time()
        r = urllib.request.urlopen(req, timeout=timeout)
        ms = int((time.time()-t0)*1000)
        body = r.read().decode(errors="replace")[:120]
        status = "PASS" if r.status == expected_code else "WARN"
        print(f"  [{status}] {label}: HTTP {r.status} | {ms}ms | {body}")
        return r.status == expected_code
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:100]
        # 401/403 means service is UP but auth-protected — that's OK
        if e.code in (401, 403, 302):
            print(f"  [PASS] {label}: HTTP {e.code} (auth-protected, service up)")
            return True
        print(f"  [FAIL] {label}: HTTP {e.code} | {body}")
        return False
    except Exception as e:
        print(f"  [FAIL] {label}: {type(e).__name__}: {str(e)[:100]}")
        return False

results = {}

print("\n=== 1. EvalOS Web ===")
results["evalos_health"] = check("EvalOS /api/health", "http://172.17.28.147:3000/api/health")
results["evalos_exams"]  = check("EvalOS /api/exams",  "http://172.17.28.147:3000/api/exams")

print("\n=== 2. PMaaS Web ===")
results["pmaas_root"]    = check("PMaaS root",         "http://172.17.57.239:3000/")

print("\n=== 3. Engage Web ===")
results["engage_root"]   = check("Engage root",        "http://172.17.63.43:3000/")

print("\n=== 4. AfroERP (ERPNext) ===")
results["afroerp_root"]  = check("AfroERP root",       "http://172.17.13.109:8000/", timeout=10)

print("\n=== 5. JupyterHub ===")
results["jupyterhub"]    = check("JupyterHub root",    "http://172.17.59.191:8000/", timeout=10)
results["jupyterhub_hub"]= check("JupyterHub /hub",    "http://172.17.59.191:8000/hub/login", timeout=10)

print("\n=== 6. Langfuse ===")
results["langfuse"]      = check("Langfuse root",      "http://172.17.63.63:3000/")

print("\n=== 7. ChromaDB ===")
results["chromadb"]      = check("ChromaDB /api/v1",   "http://172.17.57.217:8000/api/v1")

print("\n=== 8. Open WebUI (Sage) ===")
OWUI_IP = socket.gethostbyname("open-webui.i3-ai-lab.svc.cluster.local")
results["sage_webui"]    = check("Sage Open WebUI",    f"http://{OWUI_IP}:8080/")

print("\n=== 9. Zuri Co-worker ===")
ZURI_IP = socket.gethostbyname("zuri-coworker.i3-evalos.svc.cluster.local")
results["zuri"]          = check("Zuri Open WebUI",    f"http://{ZURI_IP}:8080/")

print("\n=== 10. Dawa Co-worker ===")
DAWA_IP = socket.gethostbyname("dawa-coworker.i3-pmaas.svc.cluster.local")
results["dawa"]          = check("Dawa Open WebUI",    f"http://{DAWA_IP}:8080/")

print("\n=== 11. Nuru Co-worker ===")
NURU_IP = socket.gethostbyname("nuru-coworker.i3-engage.svc.cluster.local")
results["nuru"]          = check("Nuru Open WebUI",    f"http://{NURU_IP}:8080/")

print("\n=== 12. Mfumo Co-worker ===")
MFUMO_IP = socket.gethostbyname("mfumo-coworker.i3-afroerp.svc.cluster.local")
results["mfumo"]         = check("Mfumo Open WebUI",   f"http://{MFUMO_IP}:8080/")

print("\n=== 13. Langfuse (i3-ott) ===")
LF2_IP = socket.gethostbyname("langfuse.i3-ott.svc.cluster.local")
results["langfuse_ott"]  = check("Langfuse i3-ott",    f"http://{LF2_IP}:3000/")

print("\n=== 14. ChromaDB version ===")
try:
    import subprocess, sys
    r = urllib.request.urlopen("http://172.17.57.217:8000/api/v1/version", timeout=5)
    version = json.loads(r.read())
    print(f"  [INFO] ChromaDB version: {version}")
    results["chromadb_version"] = True
except Exception as e:
    print(f"  [INFO] ChromaDB version check: {e}")
    results["chromadb_version"] = False

# Summary
print("\n" + "="*50)
print("SUMMARY")
print("="*50)
passed = sum(1 for v in results.values() if v)
total  = len(results)
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print(f"\nTotal: {passed}/{total} passing")
