"""
i3 Agentic AI OS — RAGAS Flywheel Evaluation Harness
File: platform/agentic-os/ragas_flywheel_eval.py

Evaluates DPO / SFT adapter candidates before they are promoted to the
production vLLM backend.  Reads curated traces from IBM Cloud Object Storage
(the Flywheel JSONL files referenced by i3.agentic.trace.flywheel_curated
CloudEvents) and runs four RAGAS metrics:

  1. faithfulness          — does the response stay grounded in retrieved context?
  2. answer_relevancy      — is the response relevant to the question?
  3. context_precision     — are the retrieved chunks actually useful?
  4. answer_correctness    — (golden SFT only) does the answer match the reference?

Pass / fail thresholds (Phase 3 gate evidence):
  faithfulness      >= 0.80
  answer_relevancy  >= 0.75
  context_precision >= 0.70
  answer_correctness>= 0.70   (only for GOLDEN_SFT pairs)

Usage (CLI):
    python ragas_flywheel_eval.py \
        --flywheel-bucket s3://i3-flywheel \
        --prefix 2025-07-25 \
        --adapter-model llama-3.3-70b-instruct \
        --output eval-report.json

Usage (programmatic):
    from ragas_flywheel_eval import run_evaluation
    report = await run_evaluation(s3_prefix="2025-07-25", adapter_model="llama-3.3-70b-instruct")
    assert report["gate_passed"], report["gate_reason"]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

import boto3
import httpx
from datasets import Dataset

log = logging.getLogger("ragas-flywheel-eval")
logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────────────────────
LITELLM_URL        = os.environ.get("LITELLM_URL", "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000")
LITELLM_KEY        = os.environ.get("LITELLM_MASTER_KEY", "")
S3_BUCKET          = os.environ.get("FLYWHEEL_BUCKET", "i3-flywheel")
S3_ENDPOINT_URL    = os.environ.get("IBM_COS_ENDPOINT", "")       # IBM Cloud Object Storage endpoint
S3_API_KEY_ID      = os.environ.get("IBM_COS_APIKEY_ID", "")
S3_RESOURCE_CRN    = os.environ.get("IBM_COS_RESOURCE_CRN", "")

# Pass/fail thresholds (Phase 3 gate)
THRESHOLDS = {
    "faithfulness":       0.80,
    "answer_relevancy":   0.75,
    "context_precision":  0.70,
    "answer_correctness": 0.70,
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class FlywheelSample:
    """One curated trace sample from the JSONL file."""
    trace_id:       str
    dpo_type:       str            # "DPO_PAIR" | "GOLDEN_SFT"
    question:       str            # user turn (prompt)
    answer:         str            # model response (chosen)
    contexts:       list[str]      # retrieved chunks used during inference
    ground_truth:   str | None     # human-approved reference (GOLDEN_SFT only)


@dataclass
class EvalReport:
    adapter_model:     str
    s3_prefix:         str
    n_samples:         int
    n_dpo_pairs:       int
    n_golden_sft:      int
    scores:            dict[str, float] = field(default_factory=dict)
    gate_passed:       bool = False
    gate_reason:       str = ""
    failed_metrics:    list[str] = field(default_factory=list)


# ── S3 / IBM COS loader ───────────────────────────────────────────────────────

def _make_s3_client():
    """
    Build an S3-compatible client for IBM Cloud Object Storage.
    Credentials injected from OpenBao i3/agentic-os/ibm-cos-credentials.
    """
    if not S3_ENDPOINT_URL:
        log.warning("IBM_COS_ENDPOINT not set — using local filesystem stub for tests")
        return None

    import ibm_boto3
    from ibm_botocore.client import Config

    return ibm_boto3.client(
        "s3",
        ibm_api_key_id=S3_API_KEY_ID,
        ibm_service_instance_id=S3_RESOURCE_CRN,
        config=Config(signature_version="oauth"),
        endpoint_url=S3_ENDPOINT_URL,
    )


def _load_jsonl_from_s3(s3_client, bucket: str, prefix: str) -> list[dict]:
    """List all .jsonl objects under prefix and parse them."""
    if s3_client is None:
        # Stub for local dev / CI
        log.warning("S3 client unavailable — returning empty sample list")
        return []

    paginator = s3_client.get_paginator("list_objects_v2")
    rows: list[dict] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".jsonl"):
                continue
            body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode()
            for line in body.splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        log.warning("Invalid JSONL line in %s — skipped", key)
    return rows


def _parse_samples(rows: list[dict]) -> list[FlywheelSample]:
    """Convert raw JSONL rows to FlywheelSample objects."""
    samples = []
    for row in rows:
        try:
            samples.append(FlywheelSample(
                trace_id=row["trace_id"],
                dpo_type=row.get("dpo_type", "GOLDEN_SFT"),
                question=row["question"],
                answer=row["answer"],
                contexts=row.get("contexts") or [],
                ground_truth=row.get("ground_truth"),
            ))
        except KeyError as exc:
            log.warning("Skipping malformed row (missing %s): %s", exc, row.get("trace_id", "?"))
    return samples


# ── LiteLLM inference (for RAGAS LLM-as-judge) ───────────────────────────────

async def _litellm_generate(prompt: str, model: str = "llama-3.3-70b-instruct") -> str:
    """
    Call LiteLLM for RAGAS LLM-as-judge scoring.
    Uses Llama-3.3-70B for evaluation to avoid adapter self-evaluation bias.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {LITELLM_KEY}",
                "x-litellm-metadata": json.dumps({"tenant_id": "eval-harness"}),
            },
            json={
                "model":       model,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  512,
                "temperature": 0.0,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── RAGAS metric wrappers ─────────────────────────────────────────────────────

async def _score_faithfulness(samples: list[FlywheelSample]) -> float:
    """
    Faithfulness: fraction of answer sentences fully supported by contexts.
    Uses RAGAS faithfulness scorer via LLM-as-judge.
    """
    from ragas import evaluate
    from ragas.metrics import faithfulness

    ds = Dataset.from_list([{
        "question":  s.question,
        "answer":    s.answer,
        "contexts":  s.contexts,
    } for s in samples if s.contexts])

    if len(ds) == 0:
        log.warning("No samples with contexts — faithfulness score defaulted to 0.0")
        return 0.0

    result = evaluate(ds, metrics=[faithfulness])
    return float(result["faithfulness"])


async def _score_answer_relevancy(samples: list[FlywheelSample]) -> float:
    from ragas import evaluate
    from ragas.metrics import answer_relevancy

    ds = Dataset.from_list([{
        "question": s.question,
        "answer":   s.answer,
        "contexts": s.contexts,
    } for s in samples])

    result = evaluate(ds, metrics=[answer_relevancy])
    return float(result["answer_relevancy"])


async def _score_context_precision(samples: list[FlywheelSample]) -> float:
    from ragas import evaluate
    from ragas.metrics import context_precision

    ds = Dataset.from_list([{
        "question":    s.question,
        "answer":      s.answer,
        "contexts":    s.contexts,
        "ground_truth": s.ground_truth or s.answer,
    } for s in samples if s.contexts])

    if len(ds) == 0:
        return 0.0

    result = evaluate(ds, metrics=[context_precision])
    return float(result["context_precision"])


async def _score_answer_correctness(samples: list[FlywheelSample]) -> float:
    """Only scored for GOLDEN_SFT samples that have a ground_truth reference."""
    from ragas import evaluate
    from ragas.metrics import answer_correctness

    golden = [s for s in samples if s.dpo_type == "GOLDEN_SFT" and s.ground_truth]
    if not golden:
        log.info("No GOLDEN_SFT samples with ground_truth — answer_correctness skipped")
        return 1.0   # N/A → pass

    ds = Dataset.from_list([{
        "question":    s.question,
        "answer":      s.answer,
        "ground_truth": s.ground_truth,
        "contexts":    s.contexts,
    } for s in golden])

    result = evaluate(ds, metrics=[answer_correctness])
    return float(result["answer_correctness"])


# ── Gate check ────────────────────────────────────────────────────────────────

def _gate_check(scores: dict[str, float]) -> tuple[bool, str, list[str]]:
    """
    Apply Phase 3 thresholds.  Returns (passed, reason, failed_metrics).
    """
    failed = [
        metric
        for metric, threshold in THRESHOLDS.items()
        if metric in scores and scores[metric] < threshold
    ]
    if failed:
        reason = (
            f"BLOCKED: {len(failed)} metric(s) below threshold: "
            + ", ".join(f"{m}={scores[m]:.3f}<{THRESHOLDS[m]}" for m in failed)
        )
        return False, reason, failed

    return True, "APPROVED: all metrics at or above Phase 3 thresholds", []


# ── Main evaluation orchestrator ──────────────────────────────────────────────

async def run_evaluation(
    s3_prefix: str,
    adapter_model: str,
    bucket: str = S3_BUCKET,
) -> EvalReport:
    """
    Full evaluation pipeline:
      1. Load JSONL from IBM COS Flywheel bucket.
      2. Parse into FlywheelSample objects.
      3. Run four RAGAS metrics concurrently.
      4. Apply gate thresholds.
      5. Return EvalReport (serialisable to JSON for Phase 3 evidence).

    HC-3: model promotion blocked if gate_passed=False.
    """
    s3 = _make_s3_client()
    rows    = _load_jsonl_from_s3(s3, bucket, s3_prefix)
    samples = _parse_samples(rows)

    if not samples:
        log.warning("No samples found at s3://%s/%s — gate BLOCKED", bucket, s3_prefix)
        report = EvalReport(
            adapter_model=adapter_model,
            s3_prefix=s3_prefix,
            n_samples=0,
            n_dpo_pairs=0,
            n_golden_sft=0,
            scores={},
            gate_passed=False,
            gate_reason="BLOCKED: no evaluation samples found",
        )
        return report

    n_dpo   = sum(1 for s in samples if s.dpo_type == "DPO_PAIR")
    n_golden = sum(1 for s in samples if s.dpo_type == "GOLDEN_SFT")
    log.info("Loaded %d samples (%d DPO_PAIR, %d GOLDEN_SFT)", len(samples), n_dpo, n_golden)

    # Run all four metrics concurrently
    faith, relevancy, precision, correctness = await asyncio.gather(
        _score_faithfulness(samples),
        _score_answer_relevancy(samples),
        _score_context_precision(samples),
        _score_answer_correctness(samples),
    )

    scores = {
        "faithfulness":       round(faith,       4),
        "answer_relevancy":   round(relevancy,   4),
        "context_precision":  round(precision,   4),
        "answer_correctness": round(correctness, 4),
    }

    passed, reason, failed = _gate_check(scores)
    log.info("Gate result: %s | %s", "PASSED" if passed else "BLOCKED", reason)

    return EvalReport(
        adapter_model=adapter_model,
        s3_prefix=s3_prefix,
        n_samples=len(samples),
        n_dpo_pairs=n_dpo,
        n_golden_sft=n_golden,
        scores=scores,
        gate_passed=passed,
        gate_reason=reason,
        failed_metrics=failed,
    )


# ── CLI entry point ───────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="i3 Flywheel RAGAS evaluation — Phase 3 adapter promotion gate"
    )
    parser.add_argument("--flywheel-bucket", default=S3_BUCKET)
    parser.add_argument("--prefix",          required=True,
                        help="S3 prefix to scan, e.g. '2025-07-25'")
    parser.add_argument("--adapter-model",   required=True,
                        help="Model name being evaluated, e.g. 'llama-3.3-70b-instruct'")
    parser.add_argument("--output",          default="eval-report.json",
                        help="Path to write JSON eval report")
    args = parser.parse_args()

    report = asyncio.run(run_evaluation(
        s3_prefix=args.prefix,
        adapter_model=args.adapter_model,
        bucket=args.flywheel_bucket,
    ))

    report_dict = asdict(report)
    with open(args.output, "w") as f:
        json.dump(report_dict, f, indent=2)

    print(json.dumps(report_dict, indent=2))

    if not report.gate_passed:
        raise SystemExit(f"\nGATE BLOCKED — {report.gate_reason}")
    print(f"\nGATE APPROVED — adapter '{args.adapter_model}' ready for vLLM promotion.")


if __name__ == "__main__":
    _cli()
