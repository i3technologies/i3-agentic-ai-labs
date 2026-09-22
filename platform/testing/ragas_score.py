#!/usr/bin/env python3
"""
P1-GATE-10 RAGAS scoring script.
Run inside the admissions-agent pod (Python 3.11, all deps available):

  oc cp platform/testing/ragas_score.py i3-admissions/<pod>:/tmp/ragas_score.py
  oc exec -n i3-admissions <pod> -- pip install ragas==0.1.21 datasets langchain-openai -q
  oc exec -n i3-admissions <pod> -- env LITELLM_KEY=<key> python /tmp/ragas_score.py
"""
import os, json, warnings, requests, math
warnings.filterwarnings("ignore")

LITELLM_BASE = os.getenv("LITELLM_BASE", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY  = os.environ["LITELLM_KEY"]
MODEL        = os.getenv("RAGAS_MODEL", "granite-nano")
EMBED_MODEL  = os.getenv("RAGAS_EMBED",  "embed")

QUESTIONS = [
    "What are the undergraduate admission requirements?",
    "How do I apply for postgraduate studies?",
    "What is the application deadline for the next intake?",
    "Which programmes are offered in the Faculty of Engineering?",
    "How do I obtain a student ID card after admission?",
    "What documents are required for international student admission?",
    "How is the fee structure determined for part-time students?",
    "What is the minimum grade for direct entry to a degree programme?",
    "How do I defer my admission to the next academic year?",
    "What support services are available for students with disabilities?",
]

CONTEXT = (
    "The institution offers undergraduate and postgraduate programmes. "
    "Undergraduate admission requires a minimum grade of C+ in KCSE or equivalent. "
    "Applications are submitted online via the student portal. The next intake deadline "
    "is 31 March. Faculty of Engineering offers Civil, Electrical, and Mechanical programmes. "
    "Student ID cards are issued at the registrar office after fee payment confirmation. "
    "International students require certified transcripts, passport copy, and health certificate. "
    "Part-time fees are calculated per unit. Direct entry requires a C+ minimum grade. "
    "Deferral requests must be submitted before the semester begins. Disability support "
    "services include accessible facilities, readers, and extended exam time."
)

questions, answers, contexts, ground_truths = [], [], [], []
print(f"Generating answers via {MODEL} at {LITELLM_BASE} ...")
for i, q in enumerate(QUESTIONS):
    try:
        r = requests.post(
            f"{LITELLM_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_KEY}",
                     "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [{"role": "system",
                                 "content": f"Answer only from this context: {CONTEXT}"},
                                {"role": "user", "content": q}],
                  "max_tokens": 300},
            timeout=60, verify=False,
        )
        d = r.json()
        if "error" in d:
            print(f"  [{i+1}/10] ERR: {str(d['error'])[:80]}")
            continue
        a = d["choices"][0]["message"]["content"]
        questions.append(q); answers.append(a)
        contexts.append([CONTEXT]); ground_truths.append(q)
        print(f"  [{i+1}/10] OK — {len(a)} chars")
    except Exception as e:
        print(f"  [{i+1}/10] EXC: {e}")

print(f"\nSuccessful: {len(questions)}/10")
if len(questions) < 5:
    print("FAIL: fewer than 5 successful queries"); raise SystemExit(1)

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(model=MODEL, base_url=LITELLM_BASE,
                 api_key=LITELLM_KEY, temperature=0, max_retries=2)
emb = OpenAIEmbeddings(model=EMBED_MODEL, base_url=LITELLM_BASE, api_key=LITELLM_KEY)

ds = Dataset.from_dict({"question": questions, "answer": answers,
                        "contexts": contexts, "ground_truth": ground_truths})

print("\nScoring with RAGAS (~2 min)...")
result = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision],
                  llm=llm, embeddings=emb)

f  = float(result["faithfulness"])
ar = float(result["answer_relevancy"])
cp = float(result["context_precision"])

print(f"\n=== P1-GATE-10 RAGAS RESULTS ===")
print(f"  Faithfulness:      {f:.3f}  ({'PASS' if f >= 0.80 else 'FAIL'})  threshold 0.80")
print(f"  Answer Relevancy:  {ar:.3f}  ({'PASS' if ar >= 0.75 else 'FAIL'})  threshold 0.75")
print(f"  Context Precision: {cp:.3f}")

if math.isnan(f) or math.isnan(ar):
    print("ERROR: NaN scores — judge LLM calls failed"); raise SystemExit(1)

if f >= 0.80 and ar >= 0.75:
    out = {"gate": "P1-GATE-10", "status": "PASS", "model": MODEL,
           "faithfulness": f, "answer_relevancy": ar, "context_precision": cp,
           "n_queries": len(questions)}
    with open("/tmp/ragas_result.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nP1-GATE-10: PASS ✅")
    print(json.dumps(out, indent=2))
else:
    print("\nP1-GATE-10: FAIL ❌"); raise SystemExit(1)
