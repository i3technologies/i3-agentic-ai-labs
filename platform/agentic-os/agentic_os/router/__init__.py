"""agentic_os.router — re-exports the adaptive model router."""
from agentic_os._router import score_financial, score_complexity, select_model, RoutingDecision

__all__ = ["score_financial", "score_complexity", "select_model", "RoutingDecision"]
