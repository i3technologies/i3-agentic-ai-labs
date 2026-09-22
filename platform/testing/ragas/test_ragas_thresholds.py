"""
test_ragas_thresholds.py
─────────────────────────
pytest-compatible CI wrapper for P1-GATE-10.

Run:
  pytest platform/testing/ragas/test_ragas_thresholds.py

Requires: ragas, langchain-openai, LITELLM_BASE_URL, LITELLM_API_KEY env vars.
Skipped automatically when LITELLM_BASE_URL is not set (local dev without cluster).
"""

import os
import pytest

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "")

pytestmark = pytest.mark.skipif(
    not LITELLM_BASE_URL,
    reason="LITELLM_BASE_URL not set — skipping live RAGAS evaluation",
)


@pytest.fixture(scope="module")
def ragas_scores():
    """Run RAGAS once per module; share results across all threshold tests."""
    import importlib.util, pathlib
    _ragas_eval_path = pathlib.Path(__file__).parent / "ragas_eval.py"
    _spec = importlib.util.spec_from_file_location("ragas_eval", _ragas_eval_path)
    _mod = importlib.util.module_from_spec(_spec)          # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)                         # type: ignore[union-attr]
    return _mod.run_evaluation()


def test_faithfulness_above_threshold(ragas_scores):
    threshold = float(os.environ.get("RAGAS_FAITHFULNESS_THRESHOLD", "0.80"))
    score = ragas_scores.get("faithfulness", 0.0)
    assert score >= threshold, (
        f"P1-GATE-10 FAIL: faithfulness={score:.4f} < threshold={threshold}"
    )


def test_answer_relevancy_above_threshold(ragas_scores):
    threshold = float(os.environ.get("RAGAS_RELEVANCY_THRESHOLD", "0.75"))
    score = ragas_scores.get("answer_relevancy", 0.0)
    assert score >= threshold, (
        f"P1-GATE-10 FAIL: answer_relevancy={score:.4f} < threshold={threshold}"
    )
