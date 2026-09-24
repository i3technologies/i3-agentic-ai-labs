"""
platform/audit/tests/conftest.py — pytest setup for audit package tests.

Registers platform/audit/ as a standalone package under the name
`_i3_audit_` in sys.modules so that tests can import it without
shadowing the stdlib `platform` module.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_AUDIT_DIR  = Path(__file__).resolve().parents[1]   # .../platform/audit/
_PKG_NAME   = "_i3_audit_"


def _make_package():
    """Register _i3_audit_ package backed by platform/audit/."""
    if _PKG_NAME in sys.modules:
        return

    # 1. Register the top-level package
    pkg = types.ModuleType(_PKG_NAME)
    pkg.__path__    = [str(_AUDIT_DIR)]
    pkg.__package__ = _PKG_NAME
    pkg.__file__    = str(_AUDIT_DIR / "__init__.py")
    sys.modules[_PKG_NAME] = pkg

    # 2. Load each sub-module with __package__ set so relative imports work
    for name in ("models", "writer", "tamper_check", "cli"):
        full = f"{_PKG_NAME}.{name}"
        path = _AUDIT_DIR / f"{name}.py"

        spec = importlib.util.spec_from_file_location(
            full, str(path),
            submodule_search_locations=[],
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = _PKG_NAME
        sys.modules[full] = mod

    # 3. Exec each module now that all names are registered (so forward
    #    relative imports such as `from .models import` can resolve)
    for name in ("models", "writer", "tamper_check", "cli"):
        full = f"{_PKG_NAME}.{name}"
        path = _AUDIT_DIR / f"{name}.py"
        spec = importlib.util.spec_from_file_location(
            full, str(path),
        )
        mod = sys.modules[full]
        mod.__spec__    = spec
        spec.loader.exec_module(mod)


_make_package()
