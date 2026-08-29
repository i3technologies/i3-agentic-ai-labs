# platform/admissions/fastapi/admissions_agent.py
# This file re-exports the main admissions agent module.
# The canonical implementation is platform/admissions/admissions_agent.py.
# This symlink-equivalent is here so Docker COPY from this subdirectory also works.

from admissions_agent import app  # noqa: F401
