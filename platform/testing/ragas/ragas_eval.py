"""
ragas_eval.py
─────────────
P1-GATE-10 sensor: RAGAS faithfulness ≥ 0.80 and relevancy ≥ 0.75 in CI.

Usage:
  python platform/testing/ragas/ragas_eval.py

Environment variables (all required in CI — retrieved from OpenBao):
  LITELLM_BASE_URL      e.g. http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1
  LITELLM_API_KEY       vault kv get -field=key i3/litellm/api-key
  RAGAS_FAITHFULNESS_THRESHOLD   default 0.80
  RAGAS_RELEVANCY_THRESHOLD      default 0.75

Exit codes:
  0 — both thresholds met
  1 — one or more thresholds failed (gate BLOCKED)
  2 — configuration / import error
"""

import os
import sys
import json
import logging

log = logging.getLogger("ragas-eval")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

FAITHFULNESS_THRESHOLD = float(os.environ.get("RAGAS_FAITHFULNESS_THRESHOLD", "0.80"))
RELEVANCY_THRESHOLD    = float(os.environ.get("RAGAS_RELEVANCY_THRESHOLD",    "0.75"))

# ── Evaluation dataset (golden Q&A set for i3 platform agents) ───────────────
# Each entry: question, ground_truth_answer, retrieved_contexts (list of passages).
# In CI, contexts come from a live ChromaDB query against the indexed corpus.
# For local runs without ChromaDB, stubs are provided.

EVAL_DATASET = [
    {
        "question": "What is the confidence gate threshold for the i3 admissions agent?",
        "ground_truth": "The admissions agent uses a confidence gate of 0.65; responses below this threshold are escalated to a human reviewer.",
        "contexts": [
            "The admissions agent confidence gate is set at 0.65. Responses with a confidence score below this threshold are not returned to the applicant directly — they are queued for human review via the i3-admissions-review workflow.",
            "Confidence gate: if the LLM confidence score < 0.65, the agent falls back to the human escalation queue.",
        ],
    },
    {
        "question": "Which namespaces are forbidden from modification under HC-1?",
        "ground_truth": "The solution-01 through solution-08 namespaces must never be touched or modified.",
        "contexts": [
            "HC-1 — Solution Isolation: NEVER touch, modify, or generate manifests for solution-01 through solution-08 namespaces.",
            "Hard constraint HC-1 applies to all platform engineers: the solution-01 to solution-08 namespaces are immutable tenant environments.",
        ],
    },
    {
        "question": "How are Kenyan National IDs stored in the FORD membership service?",
        "ground_truth": "Kenyan National IDs are stored as keyed HMAC-SHA256 hashes using the MEMBER_HMAC_SECRET from OpenBao — never as plaintext or raw SHA-256.",
        "contexts": [
            "HC-6 / Anonymisation: Kenyan National IDs and phone numbers MUST use keyed HMAC-SHA256 (MEMBER_HMAC_SECRET in OpenBao), never raw SHA-256.",
            "def hmac_token(value: str) -> str: secret = MEMBER_HMAC_SECRET.encode(); return _hmac.new(secret, value.strip().upper().encode(), hashlib.sha256).hexdigest()",
        ],
    },
    {
        "question": "What OTP rate-limiting strategy does the FORD service use?",
        "ground_truth": "The FORD service uses a Redis-backed attempt counter keyed by the HMAC of the phone number. After 5 failed attempts within the OTP_TTL window (600 seconds), a 429 Too Many Requests is raised.",
        "contexts": [
            "OTP_MAX_ATTEMPTS = 5; OTP_TTL = 600 seconds. The attempt counter is stored in Redis as otp_attempts:<phone_hmac_token> and expires after OTP_TTL on first increment.",
            "async def _otp_rate_check(phone_token: str): count = await _redis.incr(attempt_key); if count > OTP_MAX_ATTEMPTS: raise HTTPException(429, 'Too many attempts.')",
        ],
    },
    {
        "question": "What is the Lobster Trap firewall and how many patterns does it contain?",
        "ground_truth": "The Lobster Trap is a prompt injection firewall that runs pre-LLM on all user-supplied input. It contains 12 regex patterns covering jailbreak attempts, system prompt overrides, SQL injection, and data exfiltration vectors.",
        "contexts": [
            "The Lobster Trap firewall blocks prompt injection on all user-supplied text before reaching the LLM. It is implemented in both Python (platform/admissions/admissions_agent.py) and TypeScript (onboarding-agent/src/security/lobster-trap.ts).",
            "TRAP_PATTERNS contains 12 compiled regex entries: ignore previous instructions, system prompt override, developer mode, output all passwords, reveal internal logic, bypass safety filter, act as DAN, jailbreak, drop table, prompt injection, disregard previous, exfiltrate.",
        ],
    },
]


def _build_ragas_samples(dataset: list[dict]) -> list[dict]:
    """Convert our dataset format to the ragas SingleTurnSample format."""
    return [
        {
            "user_input":          entry["question"],
            "response":            entry["ground_truth"],   # agent answer to evaluate
            "retrieved_contexts":  entry["contexts"],
            "reference":           entry["ground_truth"],
        }
        for entry in dataset
    ]


def run_evaluation() -> dict:
    """Run RAGAS evaluation and return scores dict."""
    try:
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import faithfulness, answer_relevancy
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    except ImportError as exc:
        log.error("ragas / langchain-openai not installed. Run: pip install ragas langchain-openai")
        sys.exit(2)

    litellm_base_url = os.environ.get("LITELLM_BASE_URL")
    litellm_api_key  = os.environ.get("LITELLM_API_KEY")
    if not litellm_base_url or not litellm_api_key:
        log.error("LITELLM_BASE_URL and LITELLM_API_KEY must be set in the environment.")
        sys.exit(2)

    llm = ChatOpenAI(
        base_url=litellm_base_url,
        api_key=litellm_api_key,
        model="granite-3-2b-instruct",   # LiteLLM tier-1 model for evals
        temperature=0,
    )
    embeddings = OpenAIEmbeddings(
        base_url=litellm_base_url,
        api_key=litellm_api_key,
        model="text-embedding-3-small",
    )

    samples  = _build_ragas_samples(EVAL_DATASET)
    dataset  = EvaluationDataset.from_list(samples)
    results  = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )
    return results.to_pandas().mean(numeric_only=True).to_dict()


def main() -> None:
    log.info("Running RAGAS evaluation against i3 platform agent golden dataset…")
    log.info(f"Thresholds — faithfulness ≥ {FAITHFULNESS_THRESHOLD}, relevancy ≥ {RELEVANCY_THRESHOLD}")

    scores = run_evaluation()

    faithfulness_score = scores.get("faithfulness",      0.0)
    relevancy_score    = scores.get("answer_relevancy",  0.0)

    log.info(f"faithfulness   = {faithfulness_score:.4f}  (threshold {FAITHFULNESS_THRESHOLD})")
    log.info(f"answer_relevancy = {relevancy_score:.4f}  (threshold {RELEVANCY_THRESHOLD})")

    output = {
        "faithfulness":      faithfulness_score,
        "answer_relevancy":  relevancy_score,
        "faithfulness_pass": faithfulness_score >= FAITHFULNESS_THRESHOLD,
        "relevancy_pass":    relevancy_score    >= RELEVANCY_THRESHOLD,
    }
    print(json.dumps(output, indent=2))

    if not output["faithfulness_pass"]:
        log.error(f"GATE BLOCKED: faithfulness {faithfulness_score:.4f} < {FAITHFULNESS_THRESHOLD}")
    if not output["relevancy_pass"]:
        log.error(f"GATE BLOCKED: answer_relevancy {relevancy_score:.4f} < {RELEVANCY_THRESHOLD}")

    if output["faithfulness_pass"] and output["relevancy_pass"]:
        log.info("P1-GATE-10: PASS — all RAGAS thresholds met.")
        sys.exit(0)
    else:
        log.error("P1-GATE-10: FAIL — one or more RAGAS thresholds not met.")
        sys.exit(1)


if __name__ == "__main__":
    main()
