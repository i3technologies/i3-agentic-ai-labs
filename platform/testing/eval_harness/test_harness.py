"""
Tests for the IMP-11 eval harness (no live model calls required).

Run: pytest platform/testing/eval_harness/test_harness.py -v
"""
from __future__ import annotations

import sys
import os

# Ensure the repo root is on sys.path so we can import eval_harness directly
# without relying on a 'platform' package (platform is a stdlib module name).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
_HARNESS_PKG = os.path.join(_REPO_ROOT, "platform", "testing")
if _HARNESS_PKG not in sys.path:
    sys.path.insert(0, _HARNESS_PKG)

import pytest

from eval_harness.base import TaskResult, SuiteResult, TaskSuite
from eval_harness.suite_swahili_sheng import (
    SUITE as sw_suite,
    _keyword_recall,
    _normalize,
)
from eval_harness.suite_english_baseline import SUITE as en_suite


# ── Normalisation helpers ────────────────────────────────────────────────────

def test_normalize_strips_punctuation():
    assert _normalize("Habari, rafiki!") == "habari rafiki"


def test_normalize_lowercases():
    assert _normalize("NAIROBI") == "nairobi"


# ── Keyword recall ───────────────────────────────────────────────────────────

def test_keyword_recall_full():
    recall = _keyword_recall("hospitali,daktari,serikali", "hospitali na daktari wa serikali")
    assert recall == pytest.approx(1.0)


def test_keyword_recall_partial():
    recall = _keyword_recall("hospitali,daktari,serikali", "tu hospitali hapa")
    assert recall == pytest.approx(1 / 3)


def test_keyword_recall_empty_expected():
    assert _keyword_recall("", "any response") == pytest.approx(0.0)


# ── Suite metadata ───────────────────────────────────────────────────────────

def test_swahili_sheng_suite_loads_tasks():
    tasks = sw_suite.load_tasks()
    assert len(tasks) >= 10, "Expected at least 10 Swahili/Sheng tasks"


def test_swahili_sheng_suite_threshold():
    assert sw_suite.threshold == pytest.approx(0.65)


def test_english_baseline_suite_loads_tasks():
    tasks = en_suite.load_tasks()
    assert len(tasks) >= 5


def test_english_baseline_suite_threshold():
    assert en_suite.threshold == pytest.approx(0.75)


# ── Scoring without live model ───────────────────────────────────────────────

def test_swahili_score_task_keyword_component():
    """Keyword recall alone (no judge) should give >= 0.6 when all keywords hit."""
    task = {
        "id": "test-01",
        "prompt": "test",
        "expected": "hospitali,daktari,serikali",
        "language": "sw",
        "system_prompt": "",
    }
    # Simulate: score_task uses both keyword + coherence.
    # We mock _judge_coherence to return 0 and test keyword path only.
    original_judge = sw_suite._judge_coherence
    sw_suite._judge_coherence = lambda **_: 0.0  # type: ignore[method-assign]
    try:
        score = sw_suite.score_task(task, "hospitali na daktari wa serikali")
        assert score == pytest.approx(0.6)
    finally:
        sw_suite._judge_coherence = original_judge  # type: ignore[method-assign]


def test_english_score_factual_hit():
    task = {
        "id": "test-en-01",
        "prompt": "test",
        "expected": "Tekton",
        "system_prompt": "",
        "metadata": {"type": "factual"},
    }
    score = en_suite.score_task(task, "The platform uses Tekton for CI/CD.")
    assert score == pytest.approx(1.0)


def test_english_score_factual_miss():
    task = {
        "id": "test-en-02",
        "prompt": "test",
        "expected": "Tekton",
        "system_prompt": "",
        "metadata": {"type": "factual"},
    }
    score = en_suite.score_task(task, "The platform uses Jenkins.")
    assert score == pytest.approx(0.0)


def test_english_score_instruction_partial():
    task = {
        "id": "test-en-03",
        "prompt": "test",
        "expected": "1,2,3",
        "system_prompt": "",
        "metadata": {"type": "instruction-following"},
    }
    score = en_suite.score_task(task, "1. Speed  2. Cost")
    # "1" and "2" present, "3" not → 2/3
    assert score == pytest.approx(2 / 3)


# ── SuiteResult gate logic ───────────────────────────────────────────────────

def test_suite_result_gate_passed():
    result = SuiteResult(
        suite_name="test",
        tasks_total=4,
        tasks_passed=4,
        tasks_failed=0,
        mean_score=0.80,
        threshold=0.70,
        gate_passed=True,
        results=[],
        duration_s=1.0,
    )
    assert result.gate_passed is True
    assert "PASS" in result.summary_line()


def test_suite_result_gate_failed():
    result = SuiteResult(
        suite_name="test",
        tasks_total=4,
        tasks_passed=1,
        tasks_failed=3,
        mean_score=0.40,
        threshold=0.70,
        gate_passed=False,
        results=[],
        duration_s=1.0,
    )
    assert result.gate_passed is False
    assert "FAIL" in result.summary_line()


def test_task_result_dataclass():
    tr = TaskResult(
        task_id="x",
        passed=True,
        score=0.9,
        expected="foo",
        actual="foo bar",
        latency_ms=42.0,
    )
    assert tr.passed is True
    assert tr.metadata == {}
