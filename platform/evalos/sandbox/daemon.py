"""
EvalOS Sandbox daemon entrypoint — sandbox subdirectory.
Imports from the main sandbox_daemon module.
"""
from sandbox_daemon import app  # noqa: F401

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
