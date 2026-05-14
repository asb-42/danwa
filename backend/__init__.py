"""Debate Engine — LangGraph-based multi-agent debate workflow.

Version is read dynamically from the ``version`` file (single source of truth).
"""

from __future__ import annotations

import re
from pathlib import Path


def _get_version() -> str:
    """Read version from the VERSION single source of truth file.

    Reads the last non-comment, non-blank line from the ``/version`` file.
    Falls back to ``0.0.0-dev`` if the file is missing or unreadable.
    """
    v = Path(__file__).resolve().parent.parent / "version"
    if not v.exists():
        return "0.0.0-dev"
    lines = [line.strip() for line in v.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return "0.0.0-dev"
    ver = lines[-1].strip()
    return ver if re.match(r"^\d+\.\d+\.\d+$", ver) else "0.0.0-dev"


__version__ = _get_version()
