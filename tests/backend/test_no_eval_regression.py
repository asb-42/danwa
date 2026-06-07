"""Regression tests for C4 — ensure ``eval()`` does not creep back in.

C1 and C4 were both manifestations of the same bug class: calling
``eval()`` on user-supplied condition strings.  Sprint 28
(``d48d387``) replaced them with ``backend.workflow.safe_eval``,
an AST-whitelist evaluator.  These tests guard against a
regression: no module under ``backend/`` may use ``eval()`` or
``exec()`` (Python builtin) again, and no module may suppress
the ``S307`` bandit warning to re-enable ``eval()``.

The Python ``exec()`` builtin is distinct from
``asyncio.create_subprocess_exec`` — only the builtin is
rejected by this test.  ``ast.literal_eval`` is allowed (it is
the safe, structured alternative).

The check uses ``ast.parse`` (not regex on raw text) so that
mentions of ``eval`` in docstrings or comments do not produce
false positives.  Only actual code-level call sites are
forbidden.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"

# ``noqa: S307`` is bandit-specific.  We grep for any ``noqa``
# comment that mentions ``S307`` to catch a future attempt
# to re-enable ``eval()`` with a band-aid suppression.
NOQA_S307 = re.compile(r"noqa[^\n]*S307", re.IGNORECASE)


def _iter_python_files() -> list[Path]:
    """Yield every ``.py`` file under ``backend/``."""
    return sorted(BACKEND.rglob("*.py"))


def _find_builtin_calls(path: Path, builtin: str) -> list[tuple[int, str]]:
    """Return ``(line_no, source)`` for every actual call to
    the given Python builtin in the file's executable code.

    Docstrings and comments are excluded because they are not
    executed.  Attribute access chains (e.g.
    ``asyncio.create_subprocess_exec``) do not match because
    the root name is not ``exec`` — the AST ``Call.func`` for
    such chains is an ``Attribute`` node, not a ``Name`` node.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # Files with parse errors are caught by the broader
        # test suite.  Skip here to avoid double-reporting.
        return []

    hits: list[tuple[int, str]] = []
    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Bare ``eval(...)`` or ``exec(...)`` — the function
        # name is a ``Name`` node, not an ``Attribute``.
        if isinstance(func, ast.Name) and func.id == builtin:
            line = lines[node.lineno - 1] if node.lineno - 1 < len(lines) else ""
            hits.append((node.lineno, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# No-Python-eval regression
# ---------------------------------------------------------------------------


class TestNoEvalExecInBackend:
    """No Python builtin ``eval()`` or ``exec()`` is allowed
    anywhere under ``backend/``.  ``asyncio.create_subprocess_exec``
    uses the same identifier but is an unrelated API — its AST
    representation is ``Call(func=Attribute)``, not
    ``Call(func=Name('exec'))``, so the AST check below
    correctly ignores it.
    """

    @pytest.mark.parametrize("path", _iter_python_files(), ids=str)
    def test_no_eval_builtin(self, path: Path) -> None:
        hits = _find_builtin_calls(path, "eval")
        assert not hits, (
            f"{path}: Python builtin eval() is forbidden — "
            f"use backend.workflow.safe_eval.evaluate_condition "
            f"or ast.literal_eval instead.  Found at lines: "
            f"{[h[0] for h in hits]}"
        )

    @pytest.mark.parametrize("path", _iter_python_files(), ids=str)
    def test_no_exec_builtin(self, path: Path) -> None:
        hits = _find_builtin_calls(path, "exec")
        assert not hits, f"{path}: Python builtin exec() is forbidden.  Found at lines: {[h[0] for h in hits]}"


class TestNoBanditS307Suppression:
    """No file may use ``# noqa: S307`` to suppress the bandit
    warning for ``eval()``.  Such suppressions were the
    original sin behind C1/C4 — they papered over an actual
    security issue.  Use ``backend.workflow.safe_eval`` or
    ``ast.literal_eval`` instead.
    """

    @pytest.mark.parametrize("path", _iter_python_files(), ids=str)
    def test_no_s307_noqa(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        match = NOQA_S307.search(text)
        assert match is None, (
            f"{path}: forbidden ``# noqa: S307`` suppression — "
            f"the underlying eval() must be removed, not silenced.  "
            f"Use backend.workflow.safe_eval.evaluate_condition.  "
            f"Match: {match.group(0)!r}"
        )


# ---------------------------------------------------------------------------
# Sanity check: the safe alternative exists
# ---------------------------------------------------------------------------


class TestSafeAlternativeExists:
    """The path forward is ``backend.workflow.safe_eval``.  The
    AST whitelist module must continue to exist; if it is
    removed, C1/C4 protection silently disappears.
    """

    def test_safe_eval_module_importable(self) -> None:
        from backend.workflow import safe_eval

        assert hasattr(safe_eval, "evaluate_condition")
        assert hasattr(safe_eval, "safe_eval")

    def test_safe_eval_rejects_dunder_traversal(self) -> None:
        """The classic ``(1).__class__.__base__.__subclasses__()``
        escape is the canonical reason ``eval()`` against a
        ``{"__builtins__": {}}`` sandbox is unsafe.  Make
        sure ``safe_eval`` continues to reject it.
        """
        from backend.workflow.safe_eval import evaluate_condition

        with pytest.raises(Exception):  # noqa: S101  (test code)
            evaluate_condition("(1).__class__.__base__", {})
