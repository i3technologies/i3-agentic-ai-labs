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
    * Multiple-response (MR): the set of selected labels must exactly match
      correct_answers (order-independent, case-insensitive).
    * Single-choice (SC / default): the selected label must match
      correct_answers[0] (case-insensitive).
    * A null / missing answer is treated as skipped (wrong).

    Answer format
    -------------
    The client stores answers as label strings ("A", "B", "C", "D") for SC
    questions and lists of label strings (["A", "C"]) for MR questions.
    Legacy integer-index format is also accepted for backwards compatibility.
    """
    # Build a lookup: question_id → raw selected value
    answer_map: dict[str, object] = {
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

        selected = answer_map.get(qid)  # None if not answered
        is_mr = q.type.upper() == "MR" or q.question_type.upper() in ("MR", "MULTIPLE_RESPONSE", "MULTI_SELECT")

        if is_mr:
            # MR: selected must be a list of labels matching correct_answers exactly.
            if isinstance(selected, list) and len(selected) > 0:
                given  = sorted(str(s).upper() for s in selected)
                expect = sorted(str(c).upper() for c in q.correct_answers)
                is_correct = given == expect
            else:
                is_correct = False
        else:
            # SC: selected is either a label string ("A") or a legacy integer index.
            if selected is None or selected == -1:
                is_correct = False
            elif isinstance(selected, str):
                # Label-string comparison (primary path for all current clients)
                correct_label = str(q.correct_answers[0]).upper() if q.correct_answers else ""
                is_correct = selected.upper() == correct_label
            elif isinstance(selected, int):
                # Legacy integer-index path
                correct_raw = q.correct_answers[0] if q.correct_answers else ""
                try:
                    is_correct = selected == int(correct_raw)
                except ValueError:
                    # correct_answers[0] is a label, not an index — can't compare
                    is_correct = False
            else:
                is_correct = False

        # Represent the first correct answer as its label for the detailed result.
        # Keep as 0 (legacy default) when correct_answers is empty.
        correct_label_for_detail = q.correct_answers[0] if q.correct_answers else ""
        correct_idx = 0
        try:
            correct_idx = int(correct_label_for_detail)
        except (ValueError, TypeError):
            # Label string like "A" — store its ordinal offset from 'A'
            correct_idx = max(0, ord(str(correct_label_for_detail).upper()[:1] or "A") - ord("A"))

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
    threshold = req.pass_threshold if req.pass_threshold is not None else PASS_THRESHOLD

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
