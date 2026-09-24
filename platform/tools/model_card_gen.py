#!/usr/bin/env python3
"""
i3 AI Platform — Model Card Generator (IMP-11)

Reads eval-harness JSON output (produced by the Tekton eval-harness-gate
task) and renders the model card template with measured scores.

Usage:
    python -m platform.tools.model_card_gen \\
        --harness-result /tmp/eval_harness_result.json \\
        --ragas-result   /tmp/ragas_result.json \\
        --model          qwen-fast \\
        --quantisation   q4_K_M \\
        --output         /tmp/model-card-qwen-fast.md

All --harness-result / --ragas-result flags are optional; missing values
are rendered as "N/A".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from string import Template


_TEMPLATE_PATH = Path(__file__).parent / "model_card_template.md"

# Map litellm model names to card metadata
_MODEL_REGISTRY: dict = {
    "granite-nano": {
        "base_model": "ibm/granite-3.1-dense-2b-instruct",
        "model_family": "Granite 3.1",
        "source": "Ollama (ollama/granite3.1-dense:2b)",
        "licence": "Apache 2.0",
        "max_tokens": 2048,
        "request_timeout_s": 60,
    },
    "qwen-fast": {
        "base_model": "Qwen/Qwen2.5-7B-Instruct",
        "model_family": "Qwen 2.5",
        "source": "Ollama (ollama/qwen2.5:7b-instruct-q4_K_M)",
        "licence": "Qwen LICENCE",
        "max_tokens": 4096,
        "request_timeout_s": 180,
    },
    "qwen-heavy": {
        "base_model": "Qwen/Qwen2.5-14B-Instruct",
        "model_family": "Qwen 2.5",
        "source": "Ollama (ollama/qwen2.5:14b-instruct-q4_K_M)",
        "licence": "Qwen LICENCE",
        "max_tokens": 8192,
        "request_timeout_s": 240,
    },
    "coder": {
        "base_model": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "model_family": "Qwen 2.5 Coder",
        "source": "Ollama (ollama/qwen2.5-coder:7b-instruct-q4_K_M)",
        "licence": "Qwen LICENCE",
        "max_tokens": 4096,
        "request_timeout_s": 180,
    },
    "vision": {
        "base_model": "mistralai/mistral-nemo — LLaVA 13B v1.6",
        "model_family": "LLaVA",
        "source": "Ollama (ollama/llava:13b-v1.6-mistral-q4)",
        "licence": "Apache 2.0 (Mistral base)",
        "max_tokens": 2048,
        "request_timeout_s": 240,
    },
}


def _fmt(value, fmt=".3f") -> str:
    if value is None:
        return "N/A"
    try:
        return format(float(value), fmt)
    except (TypeError, ValueError):
        return str(value)


def _gate_status(value, threshold) -> str:
    if value is None:
        return "-"
    return "PASS" if float(value) >= threshold else "FAIL"


def _suite_stats(suite_results: list, suite_name: str) -> dict:
    """Extract per-suite stats from harness result list."""
    for s in suite_results:
        if s.get("suite_name") == suite_name:
            return s
    return {}


def _sub_suite_stats(tasks: list, corpus: str) -> dict:
    """Aggregate tasks from a specific corpus within a suite."""
    matching = [t for t in tasks if t.get("metadata", {}).get("corpus", "") == corpus]
    if not matching:
        return {"total": "N/A", "passed": "N/A", "score": "N/A"}
    total = len(matching)
    passed = sum(1 for t in matching if t.get("passed", False))
    scores = [t.get("score", 0.0) for t in matching]
    mean = sum(scores) / len(scores) if scores else 0.0
    return {"total": total, "passed": passed, "score": f"{mean:.3f}"}


def generate(
    model: str,
    quantisation: str = "N/A",
    harness_result: dict | None = None,
    ragas_result: dict | None = None,
    pipeline_run_id: str = "N/A",
    ml_engineer: str = "N/A",
    security_reviewer: str = "N/A",
    platform_owner: str = "N/A",
) -> str:
    template_text = _TEMPLATE_PATH.read_text(encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    registry = _MODEL_REGISTRY.get(model, {})

    # RAGAS scores
    ragas = ragas_result or {}
    faithfulness = ragas.get("faithfulness")
    answer_relevancy = ragas.get("answer_relevancy")
    eval_run_date = ragas.get("eval_run_date", now)

    # Harness scores
    suites_list = (harness_result or {}).get("suites", [])
    sw_suite = _suite_stats(suites_list, "swahili_sheng")
    en_suite = _suite_stats(suites_list, "english_baseline")
    sw_tasks = sw_suite.get("results", [])
    overall_gate = (harness_result or {}).get("status", "N/A")

    mafand_stats = _sub_suite_stats(sw_tasks, "MAFAND-MT-v1")
    opus_stats   = _sub_suite_stats(sw_tasks, "OPUS-Swahili-Bible")
    sheng_stats  = _sub_suite_stats(sw_tasks, "i3-sheng-handauthored-v1")

    fallback_map = {
        "qwen-heavy": "qwen-heavy → qwen-fast → granite-nano",
        "qwen-fast":  "qwen-fast → granite-nano",
        "coder":      "coder → qwen-fast → granite-nano",
        "vision":     "vision → qwen-heavy → qwen-fast",
        "granite-nano": "granite-nano (terminal fallback)",
    }

    provenance = json.dumps(
        {
            "model": model,
            "quantisation": quantisation,
            "base_model": registry.get("base_model", "unknown"),
            "generated_at": now,
            "pipeline_run_id": pipeline_run_id,
        },
        indent=2,
    )

    values = {
        "model_name":           model,
        "generated_at":         now,
        "quantisation":         quantisation,
        "base_model":           registry.get("base_model", "N/A"),
        "model_family":         registry.get("model_family", "N/A"),
        "version_tag":          quantisation,
        "source":               registry.get("source", "N/A"),
        "licence":              registry.get("licence", "N/A"),
        "deployment_target":    "i3-model-gateway / Ollama on OpenShift 4.15",
        "primary_use_case":     "RAG Q&A, agent planning, code generation (per model tier)",
        "supported_languages":  "English, Swahili, Sheng",
        "out_of_scope":         (
            "- Medical diagnosis\n"
            "- Legal advice\n"
            "- Raw National ID or phone-number processing (HC-6)\n"
            "- Unsupervised autonomous action above L1 (HC-3)"
        ),
        "faithfulness":          _fmt(faithfulness),
        "faithfulness_status":   _gate_status(faithfulness, 0.80),
        "answer_relevancy":      _fmt(answer_relevancy),
        "answer_relevancy_status": _gate_status(answer_relevancy, 0.75),
        "swahili_sheng_score":   _fmt(sw_suite.get("mean_score")),
        "swahili_sheng_status":  _gate_status(sw_suite.get("mean_score"), 0.65),
        "english_baseline_score": _fmt(en_suite.get("mean_score")),
        "english_baseline_status": _gate_status(en_suite.get("mean_score"), 0.75),
        "sw_mafand_total":       str(mafand_stats["total"]),
        "sw_mafand_passed":      str(mafand_stats["passed"]),
        "sw_mafand_score":       str(mafand_stats["score"]),
        "sw_opus_total":         str(opus_stats["total"]),
        "sw_opus_passed":        str(opus_stats["passed"]),
        "sw_opus_score":         str(opus_stats["score"]),
        "sheng_total":           str(sheng_stats["total"]),
        "sheng_passed":          str(sheng_stats["passed"]),
        "sheng_score":           str(sheng_stats["score"]),
        "eval_run_date":         eval_run_date,
        "pipeline_run_id":       pipeline_run_id,
        "overall_gate_status":   overall_gate,
        "serving_stack":         "LiteLLM proxy → Ollama",
        "api_endpoint":          "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1",
        "max_tokens":            str(registry.get("max_tokens", "N/A")),
        "request_timeout_s":     str(registry.get("request_timeout_s", "N/A")),
        "cache_config":          "Redis semantic cache (TTL=3600s, similarity=0.95)",
        "fallback_chain":        fallback_map.get(model, "N/A"),
        "provenance_block":      provenance,
        "ml_engineer":           ml_engineer,
        "security_reviewer":     security_reviewer,
        "platform_owner":        platform_owner,
        "signoff_date":          now[:10],
        "autonomy_level":        "1",
    }

    # Replace {{key}} placeholders
    for k, v in values.items():
        template_text = template_text.replace("{{" + k + "}}", str(v))

    return template_text


def main(argv=None):
    parser = argparse.ArgumentParser(description="i3 Model Card Generator")
    parser.add_argument("--model", required=True, help="Model name (e.g. qwen-fast)")
    parser.add_argument("--quantisation", default="N/A")
    parser.add_argument("--harness-result", default=None,
                        help="Path to eval_harness_result.json")
    parser.add_argument("--ragas-result", default=None,
                        help="Path to ragas_result.json")
    parser.add_argument("--pipeline-run-id", default="N/A")
    parser.add_argument("--ml-engineer", default="N/A")
    parser.add_argument("--security-reviewer", default="N/A")
    parser.add_argument("--platform-owner", default="N/A")
    parser.add_argument("--output", default=None,
                        help="Output path (default: stdout)")
    args = parser.parse_args(argv)

    harness_result = None
    if args.harness_result and os.path.exists(args.harness_result):
        with open(args.harness_result) as f:
            harness_result = json.load(f)

    ragas_result = None
    if args.ragas_result and os.path.exists(args.ragas_result):
        with open(args.ragas_result) as f:
            ragas_result = json.load(f)

    card = generate(
        model=args.model,
        quantisation=args.quantisation,
        harness_result=harness_result,
        ragas_result=ragas_result,
        pipeline_run_id=args.pipeline_run_id,
        ml_engineer=args.ml_engineer,
        security_reviewer=args.security_reviewer,
        platform_owner=args.platform_owner,
    )

    if args.output:
        Path(args.output).write_text(card, encoding="utf-8")
        print(f"Model card written to: {args.output}")
    else:
        print(card)


if __name__ == "__main__":
    main()
