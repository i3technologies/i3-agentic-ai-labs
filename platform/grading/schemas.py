"""
Grading Service — Pydantic schemas (request / response)
"""
from __future__ import annotations

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class Answer(BaseModel):
    question_id: uuid.UUID
    selected_option: int  # 0-based index; -1 for skipped


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
