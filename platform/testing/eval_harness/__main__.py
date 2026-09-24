"""
i3 AI Platform — Evaluation Harness CLI entry-point (IMP-11)

Usage:
    python -m platform.testing.eval_harness [OPTIONS]

Options:
    --suite NAME        Run a specific suite (swahili_sheng | english_baseline | all)
                        Default: all
    --model NAME        Override EVAL_MODEL env var
    --litellm-base URL  Override LITELLM_BASE_URL env var
    --api-key KEY       Override LITELLM_API_KEY env var
    --threshold FLOAT   Override gate threshold for all suites
    --output FILE       Write JSON results to FILE (default: /tmp/eval_harness_result.json)
    --verbose           Print per-task results

Exit codes:
    0  all suites gate_passed == True
    1  one or more suites failed gate
    2  configuration / import error
"""
from __future__ import annotations

import argparse
import json
import sys
import os


def _load_suites():
    # Import using the package name relative to platform/testing/ on sys.path
    # (avoids conflict with stdlib 'platform' module)
    import importlib
    sw_mod = importlib.import_module("eval_harness.suite_swahili_sheng")
    en_mod = importlib.import_module("eval_harness.suite_english_baseline")
    return {"swahili_sheng": sw_mod.SUITE, "english_baseline": en_mod.SUITE}


def _ensure_path():
    """Add platform/testing to sys.path so eval_harness is importable."""
    import sys
    import os
    # When run as `python -m platform.testing.eval_harness` the testing dir
    # may not be on path; add it explicitly.
    testing_dir = os.path.join(os.path.dirname(__file__), "..")
    testing_dir = os.path.normpath(testing_dir)
    if testing_dir not in sys.path:
        sys.path.insert(0, testing_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description="i3 Eval Harness")
    parser.add_argument("--suite", default="all")
    parser.add_argument("--model", default=None)
    parser.add_argument("--litellm-base", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--output", default="/tmp/eval_harness_result.json")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    _ensure_path()
    try:
        suites = _load_suites()
    except ImportError as exc:
        print(f"IMPORT ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.suite == "all":
        selected = list(suites.values())
    elif args.suite in suites:
        selected = [suites[args.suite]]
    else:
        print(f"Unknown suite '{args.suite}'. Available: {list(suites)}", file=sys.stderr)
        sys.exit(2)

    if args.threshold is not None:
        for suite in selected:
            suite.threshold = args.threshold

    all_results = []
    any_failed = False

    for suite in selected:
        print(f"\n{'='*60}")
        print(f"Running suite: {suite.name}")
        print(f"  {suite.description}")
        print(f"  threshold: {suite.threshold}")
        print(f"{'='*60}")

        result = suite.run(
            model=args.model,
            litellm_base=args.litellm_base,
            api_key=args.api_key,
            verbose=args.verbose,
        )
        all_results.append(result.to_dict())
        status = "PASS ✅" if result.gate_passed else "FAIL ❌"
        print(f"\n{result.summary_line()}  →  {status}")
        if not result.gate_passed:
            any_failed = True

    # Aggregate summary
    aggregate = {
        "gate": "IMP-11-eval-harness",
        "status": "FAIL" if any_failed else "PASS",
        "suites": all_results,
    }

    with open(args.output, "w") as fh:
        json.dump(aggregate, fh, indent=2)

    print(f"\n{'='*60}")
    overall = "PASS ✅" if not any_failed else "FAIL ❌"
    print(f"OVERALL: {overall}")
    print(f"Results written to: {args.output}")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
