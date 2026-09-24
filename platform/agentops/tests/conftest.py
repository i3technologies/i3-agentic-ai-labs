"""
platform/agentops/tests/conftest.py — pytest setup for agentops package tests.

Registers platform/agentops/ as a standalone package under the name
`_i3_agentops_` in sys.modules so that tests can import it without
shadowing the stdlib `platform` module.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_AGENTOPS_DIR = Path(__file__).resolve().parents[1]  # .../platform/agentops/
_PKG_NAME     = "_i3_agentops_"


def _make_package() -> None:
    if _PKG_NAME in sys.modules:
        return

    # 1. Register top-level package
    pkg = types.ModuleType(_PKG_NAME)
    pkg.__path__    = [str(_AGENTOPS_DIR)]
    pkg.__package__ = _PKG_NAME
    pkg.__file__    = str(_AGENTOPS_DIR / "__init__.py")
    sys.modules[_PKG_NAME] = pkg

    # 2. Pre-register sub-modules so relative imports resolve
    for name in ("risk_register", "review_pack", "report", "cli"):
        full = f"{_PKG_NAME}.{name}"
        path = _AGENTOPS_DIR / f"{name}.py"
        spec = importlib.util.spec_from_file_location(
            full, str(path),
            submodule_search_locations=[],
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = _PKG_NAME
        sys.modules[full] = mod

    # 3. Exec each module (forward-refs now resolve)
    for name in ("risk_register", "review_pack", "report", "cli"):
        full = f"{_PKG_NAME}.{name}"
        path = _AGENTOPS_DIR / f"{name}.py"
        spec = importlib.util.spec_from_file_location(full, str(path))
        mod  = sys.modules[full]
        mod.__spec__ = spec
        spec.loader.exec_module(mod)


_make_package()
