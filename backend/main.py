"""FastAPI application entry point for Danwa Debate Engine.

.. deprecated::
    This legacy backend has been superseded by danwa-core.
    Start the replacement with::

        cd danwa-core && ./manage.sh start be
        # or directly:
        cd danwa-core && uv run uvicorn backend.main:app --port 8000

    All code below is retained for reference only and will be removed
    in a future cleanup pass.  Do NOT start this backend — it shares
    the same port (8000) as danwa-core and will conflict.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env file into os.environ BEFORE any module reads os.getenv().
# Use Path(__file__) to always resolve relative to the project root,
# independent of the working directory the server was started from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Fallback: if .env not found in project root, check sibling danwa-core/
if not (_PROJECT_ROOT / ".env").exists():
    _sibling = _PROJECT_ROOT.parent / "danwa-core" / ".env"
    if _sibling.exists():
        load_dotenv(_sibling)

# NOTE: All heavy imports are intentionally removed.  This file is
# DEPRECATED — the real backend lives in danwa-core.  Only lightweight
# imports needed for the stub are kept below.

logger = logging.getLogger(__name__)


# ============================================================
# DEPRECATED: Application factory — DO NOT START THIS BACKEND.
#
# This legacy backend has been superseded by danwa-core.
# Use instead:
#   cd danwa-core && ./manage.sh start be
#   cd danwa-core && uv run uvicorn backend.main:app --port 8000
#
# The stub below allows legacy test imports to succeed.
# Calling create_app() will raise RuntimeError at runtime.
# ============================================================


def create_app():  # type: ignore[no-redef]
    """DEPRECATED stub — the real factory is in danwa-core.

    Raises RuntimeError if called.  Retained only so that legacy
    ``from backend.main import create_app`` imports in tests don't
    break at collection time.
    """
    raise RuntimeError(
        "DEPRECATED: This legacy backend has been superseded by danwa-core. Use: cd ../danwa-core && uv run uvicorn backend.main:app --port 8000"
    )


# Uvicorn entry point — DEPRECATED, do not start
# app = create_app()

# Stub for legacy ``from backend.main import app`` in tests.
# Will raise RuntimeError if used as a real ASGI app.
app = None  # type: ignore[assignment]
