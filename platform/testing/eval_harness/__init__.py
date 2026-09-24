"""
i3 AI Platform — Evaluation Harness (IMP-11 / Workstream B5)

Pluggable task-suite runner.  Each suite is a Python module in this
package that exposes a single ``SUITE`` object of type ``TaskSuite``.

Entry-point (CLI):
    python -m platform.testing.eval_harness [--suite all|<name>] [OPTIONS]

Exit codes:
    0  all suites above threshold
    1  one or more suites failed threshold checks
    2  configuration / import error
"""
