"""
Grading Service — Pydantic schemas (request / response)
"""
from __future__ import annotations

import uuid
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field


class Answer(BaseModel):
    question_id: uuid.UUID
    # Accepts:
    #   - a label string  "A" | "B" | "C" | "D"          (SC questions)
    #   - a list of label strings  ["A", "C"]             (MR questions)
    #   - None / null                                      (skipped)
    # Legacy integer index format is also accepted for backwards compatibility.
    selected_option: Union[str, List[str], int, None] = None


class QuestionSnapshot(BaseModel):
    id: uuid.UUID
    type: str  # "SC" | "MR"
    question_type: str
    correct_answers: List[str]
    domain_number: int
    domain_name: str


class GradeRequest(BaseModel):
    exam_id: uuid.UUID
    session_id: uuid.UUID
    tenant_id: uuid.UUID
    question_snapshot: List[QuestionSnapshot]
    answers: List[Answer]
    # Per-exam pass threshold supplied by the caller (e.g. 90.0 for Set 7).
    # Falls back to the service-level PASS_THRESHOLD env var when omitted.
    pass_threshold: Optional[float] = None


class DetailedResult(BaseModel):
    question_id: uuid.UUID
    correct: bool
    correct_option: int  # index of first correct answer in snapshot


class DomainBreakdown(BaseModel):
    domain: str
    score: int
    max: int
    pct: float


class GradeResponse(BaseModel):
    score: int
    max_score: int
    pct_score: float
    passed: bool
    domain_breakdown: List[DomainBreakdown]
    detailed_results: List[DetailedResult]
