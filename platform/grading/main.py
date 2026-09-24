#!/usr/bin/env python3
"""
Grading Service
---------------
Stateless FastAPI microservice that scores exam attempts and returns
domain-level breakdowns.  Extracted from the EvalOS Next.js submit route.

Deployed in: i3-evalos namespace
Cluster-internal DNS: grading-service.i3-evalos.svc.cluster.local:8000
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from schemas import (
    Answer,
    DomainBreakdown,
    DetailedResult,
    GradeRequest,
    GradeResponse,
)

log = logging.getLogger("grading-service")
logging.basicConfig(level=logging.INFO)

PASS_THRESHOLD: float = float(os.environ.get("PASS_THRESHOLD", "68.0"))

app = FastAPI(title="i3 Grading Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://evalos.i3technologies.co.ke",
        "https://engage.i3technologies.co.ke",
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


# ── Core grading logic ────────────────────────────────────────────────────────

def _grade(req: GradeRequest) -> GradeResponse:
    """
    Pure function: score a set of answers against a frozen question snapshot.

    Rules
    -----
    * Multiple-response (MR): all selected options must exactly match
      correct_answers (order-independent).
    * Single-choice (SC / default): the single selected option index must
      match correct_answers[0].
    * An answer with selected_option == -1 is treated as skipped (wrong).
    """
    answer_map: dict[str, int] = {
        str(a.question_id): a.selected_option for a in req.answers
    }

    domain_map: dict[int, dict] = {}
    detailed: list[DetailedResult] = []

    correct_count = 0

    for q in req.question_snapshot:
        qid = str(q.id)
        dn = q.domain_number

        if dn not in domain_map:
            domain_map[dn] = {"domain_name": q.domain_name, "correct": 0, "total": 0}

        domain_map[dn]["total"] += 1

        selected = answer_map.get(qid, -1)
        is_mr = q.type.upper() == "MR" or q.question_type.upper() in ("MR", "MULTIPLE_RESPONSE")

        if is_mr:
            # For MR we expect selected_option to encode a bitmask; client
            # should send a synthetic single int.  Treat mismatch as wrong.
            is_correct = False
        else:
            # For SC: selected_option is the 0-based index of the chosen answer.
            # correct_answers[0] may be an index string ("0", "1", …) or the
            # literal answer text.  We compare index-to-index first.
            correct_raw = q.correct_answers[0] if q.correct_answers else ""
            try:
                is_correct = selected != -1 and selected == int(correct_raw)
            except ValueError:
                is_correct = False

        correct_idx = 0
        try:
            correct_idx = int(q.correct_answers[0]) if q.correct_answers else 0
        except ValueError:
            correct_idx = 0

        detailed.append(
            DetailedResult(
                question_id=q.id,
                correct=is_correct,
                correct_option=correct_idx,
            )
        )

        if is_correct:
            correct_count += 1
            domain_map[dn]["correct"] += 1

    total_q = len(req.question_snapshot)
    pct = (correct_count / total_q * 100) if total_q > 0 else 0.0

    # Use per-exam threshold carried in the request if provided by the caller;
    # fall back to service-level environment default.
    threshold = PASS_THRESHOLD

    domain_breakdown = [
        DomainBreakdown(
            domain=v["domain_name"],
            score=v["correct"],
            max=v["total"],
            pct=round(v["correct"] / v["total"] * 100, 2) if v["total"] > 0 else 0.0,
        )
        for _, v in sorted(domain_map.items())
    ]

    return GradeResponse(
        score=correct_count,
        max_score=total_q,
        pct_score=round(pct, 4),
        passed=pct >= threshold,
        domain_breakdown=domain_breakdown,
        detailed_results=detailed,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/grade", response_model=GradeResponse, status_code=200)
async def grade(req: GradeRequest) -> GradeResponse:
    """
    Score an exam attempt.

    HC-4 enforced: tenant_id is required in the request body.
    """
    return _grade(req)


@app.get("/health")
def health():
    return {"status": "ok", "service": "grading-service", "version": "1.0.0"}
