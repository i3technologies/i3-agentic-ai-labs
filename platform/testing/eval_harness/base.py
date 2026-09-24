"""
Base types for the i3 evaluation harness.

Every task suite module must export a module-level ``SUITE: TaskSuite``.
"""
from __future__ import annotations

import abc
import dataclasses
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Result primitives
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class TaskResult:
    task_id: str
    passed: bool
    score: float           # 0.0 – 1.0
    expected: str
    actual: str
    latency_ms: float
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class SuiteResult:
    suite_name: str
    tasks_total: int
    tasks_passed: int
    tasks_failed: int
    mean_score: float
    threshold: float
    gate_passed: bool      # mean_score >= threshold
    results: List[TaskResult]
    duration_s: float

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def summary_line(self) -> str:
        status = "PASS" if self.gate_passed else "FAIL"
        return (
            f"[{self.suite_name}] {status} "
            f"mean={self.mean_score:.3f} threshold={self.threshold:.2f} "
            f"passed={self.tasks_passed}/{self.tasks_total} "
            f"duration={self.duration_s:.1f}s"
        )


# ---------------------------------------------------------------------------
# Task suite base class
# ---------------------------------------------------------------------------

class TaskSuite(abc.ABC):
    """Abstract base for all pluggable evaluation suites."""

    name: str                    # unique suite slug, e.g. "swahili_sheng"
    description: str
    threshold: float = 0.70      # gate threshold — override in subclass

    @abc.abstractmethod
    def load_tasks(self) -> List[Dict[str, Any]]:
        """Return list of task dicts: {id, prompt, expected_keywords, language, ...}"""

    @abc.abstractmethod
    def score_task(self, task: Dict[str, Any], actual: str) -> float:
        """Return a score in [0, 1] for the model's response to a single task."""

    def call_model(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        litellm_base: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> tuple[str, float]:
        """Call the LiteLLM proxy and return (response_text, latency_ms)."""
        import requests  # local import so harness is importable without requests

        base = litellm_base or os.environ.get(
            "LITELLM_BASE_URL",
            "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1",
        )
        key = api_key or os.environ.get("LITELLM_API_KEY", "")
        mdl = model or os.environ.get("EVAL_MODEL", "qwen-fast")

        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        t0 = time.perf_counter()
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": mdl, "messages": messages, "max_tokens": 512, "temperature": 0},
            timeout=120,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return text, latency_ms

    def run(
        self,
        model: Optional[str] = None,
        litellm_base: Optional[str] = None,
        api_key: Optional[str] = None,
        verbose: bool = False,
    ) -> SuiteResult:
        tasks = self.load_tasks()
        results: List[TaskResult] = []
        t_start = time.perf_counter()

        for task in tasks:
            task_id: str = task["id"]
            prompt: str = task["prompt"]
            system_prompt: str = task.get("system_prompt", "")
            expected: str = task.get("expected", "")

            try:
                actual, latency = self.call_model(
                    prompt,
                    system_prompt=system_prompt,
                    model=model,
                    litellm_base=litellm_base,
                    api_key=api_key,
                )
                score = self.score_task(task, actual)
                passed = score >= self.threshold
            except Exception as exc:  # noqa: BLE001
                actual = f"ERROR: {exc}"
                score = 0.0
                passed = False
                latency = 0.0

            tr = TaskResult(
                task_id=task_id,
                passed=passed,
                score=score,
                expected=expected,
                actual=actual,
                latency_ms=latency,
                metadata=task.get("metadata", {}),
            )
            results.append(tr)
            if verbose:
                tag = "✓" if passed else "✗"
                print(f"  {tag} [{task_id}] score={score:.3f} latency={latency:.0f}ms")

        duration_s = time.perf_counter() - t_start
        scores = [r.score for r in results]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        tasks_passed = sum(1 for r in results if r.passed)

        return SuiteResult(
            suite_name=self.name,
            tasks_total=len(results),
            tasks_passed=tasks_passed,
            tasks_failed=len(results) - tasks_passed,
            mean_score=mean_score,
            threshold=self.threshold,
            gate_passed=mean_score >= self.threshold,
            results=results,
            duration_s=duration_s,
        )
