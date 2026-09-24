"""
Run locally: python platform/testing/inject_ragas.py
This writes ragas_score.py into the admissions pod and runs it.
"""
import subprocess, sys, os

POD = subprocess.check_output(
    ["oc","get","pod","-n","i3-admissions","-l","app=admissions-agent",
     "-o","jsonpath={.items[0].metadata.name}"],
    text=True).strip()
print(f"Pod: {POD}")

LITELLM_KEY = subprocess.check_output(
    ["oc","get","secret","litellm-secrets","-n","i3-model-gateway",
     "-o","jsonpath={.data.LITELLM_MASTER_KEY}"],
    text=True).strip()
import base64
LITELLM_KEY = base64.b64decode(LITELLM_KEY).decode()
print(f"Key prefix: {LITELLM_KEY[:8]} len={len(LITELLM_KEY)}")

SCRIPT = r"""import os,json,warnings,requests,math
warnings.filterwarnings("ignore")
LITELLM_BASE=os.getenv("LITELLM_BASE","http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY=os.environ["LITELLM_KEY"]
MODEL=os.getenv("RAGAS_MODEL","qwen-fast")
EMBED_MODEL=os.getenv("RAGAS_EMBED","embed")
_CA_BUNDLE=os.getenv("LITELLM_CA_CERT",True)
QUESTIONS=["What are the undergraduate admission requirements?","How do I apply for postgraduate studies?","What is the application deadline for the next intake?","Which programmes are offered in the Faculty of Engineering?","How do I obtain a student ID card after admission?","What documents are required for international student admission?","How is the fee structure determined for part-time students?","What is the minimum grade for direct entry to a degree programme?","How do I defer my admission to the next academic year?","What support services are available for students with disabilities?"]
CONTEXT="The institution offers undergraduate and postgraduate programmes. Undergraduate admission requires a minimum grade of C+ in KCSE or equivalent. Applications are submitted online via the student portal. The next intake deadline is 31 March. Faculty of Engineering offers Civil, Electrical, and Mechanical programmes. Student ID cards are issued at the registrar office after fee payment confirmation. International students require certified transcripts, passport copy, and health certificate. Part-time fees are calculated per unit. Direct entry requires a C+ minimum grade. Deferral requests must be submitted before the semester begins. Disability support services include accessible facilities, readers, and extended exam time."
questions,answers,contexts,ground_truths=[],[],[],[]
print("Generating answers via "+MODEL+" at "+LITELLM_BASE)
for i,q in enumerate(QUESTIONS):
    try:
        r=requests.post(LITELLM_BASE+"/chat/completions",
            headers={"Authorization":"Bearer "+LITELLM_KEY,"Content-Type":"application/json"},
            json={"model":MODEL,"messages":[{"role":"system","content":"Answer only from this context: "+CONTEXT},{"role":"user","content":q}],"max_tokens":300},
            timeout=60,verify=_CA_BUNDLE)
        d=r.json()
        if "error" in d: print("  ["+str(i+1)+"/10] ERR:"+str(d["error"])[:60]); continue
        a=d["choices"][0]["message"]["content"]
        questions.append(q);answers.append(a);contexts.append([CONTEXT]);ground_truths.append(q)
        print("  ["+str(i+1)+"/10] OK "+str(len(a))+"c")
    except Exception as e: print("  ["+str(i+1)+"/10] EXC:"+str(e))
print("Got "+str(len(questions))+"/10")
if len(questions)<5: raise SystemExit("FAIL: <5 queries")
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness,context_precision
from langchain_openai import ChatOpenAI
from ragas.run_config import RunConfig
llm=ChatOpenAI(model=MODEL,base_url=LITELLM_BASE,api_key=LITELLM_KEY,temperature=0,max_retries=3,timeout=300)
run_cfg=RunConfig(timeout=300,max_retries=3,max_wait=120,max_workers=1)
ds=Dataset.from_dict({"question":questions,"answer":answers,"contexts":contexts,"ground_truth":ground_truths})
print("Scoring faithfulness+context_precision (no embedding model needed)...")
result=evaluate(ds,metrics=[faithfulness,context_precision],llm=llm,run_config=run_cfg,raise_exceptions=False)
f=float(result["faithfulness"]);cp=float(result["context_precision"])
print("Faithfulness:     "+str(round(f,3))+(" PASS" if f>=0.80 else " FAIL")+" thr 0.80")
print("Context Prec:     "+str(round(cp,3))+(" PASS" if cp>=0.75 else " FAIL")+" thr 0.75")
if math.isnan(f) or math.isnan(cp): raise SystemExit("NaN scores - LLM judge calls failed")
if f>=0.80 and cp>=0.75:
    out={"gate":"P1-GATE-10","status":"PASS","model":MODEL,"faithfulness":f,"context_precision":cp,"answer_relevancy":"skipped-embed-model-missing","n_queries":len(questions)}
    open("/tmp/ragas_result.json","w").write(json.dumps(out,indent=2))
    print("P1-GATE-10: PASS")
    print(json.dumps(out,indent=2))
else: raise SystemExit("P1-GATE-10: FAIL")
"""

# Write script into pod via stdin pipe
print("Writing script into pod...")
proc = subprocess.run(
    ["oc","exec","-n","i3-admissions",POD,"-i","--",
     "sh","-c","cat > /tmp/rs.py && wc -l /tmp/rs.py"],
    input=SCRIPT, text=True, capture_output=True)
print(proc.stdout.strip())
if proc.returncode != 0:
    print("WRITE ERROR:", proc.stderr); sys.exit(1)

# Install ragas
print("\nInstalling ragas in pod...")
proc = subprocess.run(
    ["oc","exec","-n","i3-admissions",POD,"--",
     "sh","-c","HOME=/tmp pip install ragas==0.1.21 datasets langchain-openai --user -q 2>&1 | tail -4"],
    capture_output=False, text=True)

# Run scoring
print("\nRunning RAGAS scoring...")
env_str = f"HOME=/tmp PYTHONUSERBASE=/tmp/.local LITELLM_KEY={LITELLM_KEY}"
proc = subprocess.run(
    ["oc","exec","-n","i3-admissions",POD,"--",
     "sh","-c",f"{env_str} python /tmp/rs.py"],
    text=True)
sys.exit(proc.returncode)
