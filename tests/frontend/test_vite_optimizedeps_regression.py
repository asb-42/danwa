"""Regression test: vite.config.js must pre-bundle the heavy
client-only deps that are used by deep routes.

Background
----------
On 2026-06-18 the user reported a White-Screen-Of-Death after
clicking on the Canvas menu item.  Root cause: the canvas
view imports ``@xyflow/svelte``, and the first navigation
triggered Vite's lazy dep optimisation ("✨ new dependencies
optimized").  The optimisation reloads the page, but on the
reload the optimised chunk file is not yet on disk, so the
browser fails to load it and shows a blank page.

The fix: declare the heavy client-only deps in
``optimizeDeps.include`` so they are pre-bundled at server
startup, before the user has a chance to navigate to a
page that imports them.

This test guards the contract so a future refactor that
removes the pre-bundling (e.g. by moving to
``optimizeDeps.exclude``) will be caught immediately.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VITE_CONFIG = ROOT / "frontend" / "vite.config.js"


def test_vite_config_exists():
    assert VITE_CONFIG.exists(), f"Expected vite.config.js at {VITE_CONFIG}"


def test_vite_config_pre_bundles_xyflow():
    """The Canvas view uses @xyflow/svelte — must be pre-bundled."""
    src = VITE_CONFIG.read_text(encoding="utf-8")
    assert "optimizeDeps" in src, (
        "vite.config.js has no optimizeDeps block.  The first "
        "navigation to a heavy page (Canvas, Inbox, …) triggers "
        "Vite's lazy dep optimisation, which can produce a "
        "White-Screen-Of-Death if the optimised chunk is not yet "
        "on disk.  Pre-bundle the heavy client-only deps."
    )
    assert "@xyflow/svelte" in src, (
        "vite.config.js is missing @xyflow/svelte from "
        "optimizeDeps.include.  The Canvas view imports this "
        "library, so the first navigation to /blueprint would "
        "trigger lazy dep optimisation and potentially a WSOD."
    )


def test_vite_config_pre_bundles_cytoscape():
    """The Workspace view uses cytoscape — must be pre-bundled."""
    src = VITE_CONFIG.read_text(encoding="utf-8")
    assert "cytoscape" in src, (
        "vite.config.js is missing cytoscape from "
        "optimizeDeps.include.  The Workspace view (WorkspaceView) "
        "imports cytoscape, so the first navigation would trigger "
        "lazy dep optimisation."
    )


def test_vite_config_pre_bundles_elkjs():
    """Blueprint auto-layout uses elkjs — must be pre-bundled."""
    src = VITE_CONFIG.read_text(encoding="utf-8")
    assert "elkjs" in src, "vite.config.js is missing elkjs from optimizeDeps.include.  Blueprint auto-layout needs it at runtime."


def test_vite_config_has_optimizedeps_include_block():
    """The optimizeDeps.include list must be present and well-formed.

    A future refactor might switch to ``optimizeDeps.exclude`` (the
    opposite directive) or remove the list entirely.  This test
    ensures the list is in the include form, which is the safe
    direction for the WSOD regression.
    """
    src = VITE_CONFIG.read_text(encoding="utf-8")
    assert "optimizeDeps" in src, "missing optimizeDeps block"
    assert "include:" in src.split("optimizeDeps", 1)[1], (
        "optimizeDeps block exists but has no 'include:' list.  "
        "Use optimizeDeps.include (not exclude) to pre-bundle the "
        "heavy deps so the first navigation doesn't trigger lazy "
        "optimisation."
    )
