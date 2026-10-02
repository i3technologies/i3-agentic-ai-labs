"""
agentic_os._router — vendored copy of router/model_router.py
for the installable package (no path manipulation required).
"""
# Re-export everything from the canonical module location so existing
# internal imports keep working while the installed package resolves cleanly.

import sys, os as _os
# Allow the router/ sub-directory to be found when running from source
_here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_router_dir = _os.path.join(_here, "router")
if _router_dir not in sys.path:
    sys.path.insert(0, _router_dir)

from model_router import (  # noqa: E402
    score_financial,
    score_complexity,
    select_model,
    RoutingDecision,
    MODEL_HIGH_RISK,
    MODEL_MULTI_STEP,
    MODEL_SIMPLE,
)

__all__ = [
    "score_financial",
    "score_complexity",
    "select_model",
    "RoutingDecision",
    "MODEL_HIGH_RISK",
    "MODEL_MULTI_STEP",
    "MODEL_SIMPLE",
]
