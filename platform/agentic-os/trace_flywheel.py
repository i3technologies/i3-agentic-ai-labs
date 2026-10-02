"""
i3 Agentic AI OS — Continuous Learning Flywheel Curation Worker
File: platform/agentic-os/trace_flywheel.py

Curates live execution traces captured by LangfuseCallbackHandler into
post-training datasets:

  • Approved traces  → Supervised Fine-Tuning (SFT) golden instances.
  • Overridden traces → Direct Preference Optimisation (DPO) chosen/rejected pairs.

HC-6: provenance_hash uses keyed HMAC-SHA256 (MEMBER_HMAC_SECRET via OpenBao),
      never raw SHA-256.  Delegates to agent_runtime._provenance_hash which
      gracefully zeroes when the secret is absent (with a warning).

HC-4: DecisionTrace carries tenant_id; callers must supply it.
HC-3: No autonomous state-modifying writes; this worker only produces dicts.
      Persistence (COS / Kafka) is left to the calling pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from provenance import provenance_hash as _provenance_hash


class DecisionTrace(BaseModel):
    """
    A single agent decision captured from a Langfuse trace.

    Fields
    ------
    trace_id          Langfuse / correlation UUID for the originating session.
    tenant_id         HC-4: UUID of the owning tenant (sourced from session state).
    model_version     LiteLLM model key that produced generated_action.
    prompt            The full prompt string sent to the model.
    generated_action  The raw action dict produced by the model.
    supervisor_override
                      If a human / supervisor corrected the action, the corrected
                      dict is stored here; else None.
    human_approved    True when the action was explicitly approved (Tier 3 gate
                      returned 200 or a human reviewer clicked Approve).
    """

    trace_id:            str
    tenant_id:           str = Field(..., description="HC-4: tenant UUID, must not be empty")
    model_version:       str
    prompt:              str
    generated_action:    dict
    supervisor_override: dict | None = None
    human_approved:      bool = False


def process_flywheel_trace(trace: DecisionTrace) -> dict | None:
    """
    Curate a single live execution trace into a post-training dataset record.

    Returns
    -------
    dict  — one of:

      {"type": "DPO_PAIR",    "tenant_id": ..., "prompt": ...,
       "chosen": ..., "rejected": ..., "provenance_hash": ...}

      {"type": "GOLDEN_SFT",  "tenant_id": ..., "prompt": ...,
       "completion": ..., "provenance_hash": ...}

    None  — trace is neither overridden nor approved; skip silently.

    HC-6
    ----
    provenance_hash is HMAC-SHA256(trace_id, MEMBER_HMAC_SECRET).
    Raw SHA-256 is forbidden; _provenance_hash raises a warning and returns a
    zero-string when MEMBER_HMAC_SECRET is absent so missing-secret failures
    are observable in logs without crashing the pipeline.
    """
    ph = _provenance_hash(trace.trace_id)

    if trace.supervisor_override is not None:
        return {
            "type":             "DPO_PAIR",
            "tenant_id":        trace.tenant_id,
            "prompt":           trace.prompt,
            "chosen":           trace.supervisor_override,
            "rejected":         trace.generated_action,
            "provenance_hash":  ph,
        }

    if trace.human_approved:
        return {
            "type":             "GOLDEN_SFT",
            "tenant_id":        trace.tenant_id,
            "prompt":           trace.prompt,
            "completion":       trace.generated_action,
            "provenance_hash":  ph,
        }

    return None
