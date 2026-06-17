"""Minimal conftest for the RAG-scope_id regression tests.

The full backend conftest pulls in LangGraph + many heavy deps that
aren't needed for these focused unit tests.  This slimmed-down version
keeps the path setup and skips the heavyweight app fixtures.
"""

import sys
from pathlib import Path

# Ensure the project root is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
