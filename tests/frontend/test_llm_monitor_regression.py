"""Structural regression tests for the global LLM Activity Monitor.

Background
----------
The "LLM-Monitor" is a persistent status bar in the application header
that shows what the LLM is currently doing (active agent name, model,
elapsed time, token count, error count).  It is implemented inline
in ``frontend/src/components/Header.svelte`` and is fed by a 4-second
polling loop that calls ``getLLMActivity()``.

Yesterday a refactor accidentally:
  1. Wrapped the entire LLM-monitor markup in ``{#if false}`` (which
     silently hid the indicator and confused users), and
  2. Added a parallel "DebateActivityStrip" + "StatusBar" in other
     components that duplicated the same data in a less prominent
     location.

The fix was to:
  - Deactivate the duplicate UI elements (by removing their imports /
    by wrapping them in ``{#if false}`` with a NOTE), and
  - Restore the Header.svelte LLM-Monitor to its active state.
  - Add a clearly visible ``data-debug-component="Header-LLMActivity"``
    marker so future regressions are easy to spot visually.

These tests pin the structural invariants of the fix:

  * ``Header.svelte`` MUST render the LLM-Monitor element
    (``.llm-activity`` div) and the debug marker
    (``data-debug-component="Header-LLMActivity"``).
  * The LLM-Monitor markup MUST NOT be wrapped in ``{#if false}``.
  * The polling code (``setInterval`` + ``getLLMActivity``) MUST
    still be present.
  * The duplicate UI elements (StatusBar in App.svelte) MUST NOT
    be rendered.
  * The debug marker badge MUST contain the string
    ``DBG: Header.svelte (LLM Activity)``.

Because these are Svelte-component source checks (not rendered
runtime tests), they catch accidental removal of the markup even
when the dev server has not been started, and run in any node env
without a Svelte compiler.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"


def _read(rel: str) -> str:
    p = FRONTEND_SRC / rel
    assert p.exists(), f"Expected file at {p} -- repo layout changed?"
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Header.svelte must still contain the LLM-Monitor markup
# ---------------------------------------------------------------------------


def test_header_svelte_renders_llm_activity_div():
    """The .llm-activity div must still be present in Header.svelte."""
    src = _read("components/Header.svelte")
    assert 'class="llm-activity"' in src, (
        "Header.svelte no longer contains the .llm-activity div. "
        "The LLM-Monitor has been removed -- agents will appear "
        "silent to the user during long operations."
    )


def test_header_svelte_debug_marker_present():
    """The visual debug marker badge must be present."""
    src = _read("components/Header.svelte")
    assert 'data-debug-component="Header-LLMActivity"' in src, (
        "The DBG: Header.svelte (LLM Activity) marker has been removed. "
        "If this is intentional (cleanup), please also remove the "
        "matching test and update plans/2026-06-17_*."
    )
    assert "DBG: Header.svelte (LLM Activity)" in src, (
        "The debug marker element is present but the human-readable "
        "label has been changed.  The label is part of the visible "
        "regression-detection contract."
    )


def test_header_svelte_llm_activity_is_not_disabled():
    """The LLM-Monitor markup must NOT be wrapped in ``{#if false}``."""
    src = _read("components/Header.svelte")

    guard = re.search(
        r"\{#if\s+isActive\s*\|\|\s*totalTokens\s*>\s*0\s*\}",
        src,
    )
    assert guard, "Could not find the {#if isActive || totalTokens > 0} guard that gates the LLM-Monitor.  Did the guard disappear?"

    after = src[guard.end() :]
    closing = after.find("{/if}")
    assert closing != -1, "LLM-Monitor {#if} block is not closed."
    block = after[:closing]
    assert 'class="llm-activity"' in block, (
        "The .llm-activity div is no longer inside the "
        "{#if isActive || totalTokens > 0} guard.  This means "
        "the monitor is either removed or hidden behind a "
        "{#if false} -- restoring it is part of the 2026-06-17 fix."
    )

    deactivated_window = after[: after.find('class="llm-activity"')]
    assert "DEACTIVATED" not in deactivated_window, (
        "The .llm-activity div is preceded by a DEACTIVATED comment, which means someone re-wrapped the monitor in a kill switch.  Restore it."
    )


def test_header_svelte_polls_llm_activity():
    """The 4-second polling loop against getLLMActivity() must remain."""
    src = _read("components/Header.svelte")
    assert "getLLMActivity" in src, "Header.svelte no longer imports or calls getLLMActivity().  The LLM-Monitor has no data source."
    assert "setInterval" in src, "Header.svelte no longer uses setInterval.  The polling loop was removed and the monitor will not update."
    assert "4000" in src, "Header.svelte polling interval was changed away from 4000ms.  If intentional, update the test."


# ---------------------------------------------------------------------------
# 2. Duplicate UI elements must remain disabled
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,expected_inactive_marker",
    [
        # App.svelte must not render StatusBar (it was removed in the fix)
        ("App.svelte", "StatusBar"),
        # ActivityLogPanel must still be wrapped in {#if false}
        (
            "components/feedback/ActivityLogPanel.svelte",
            "DEACTIVATED 2026-06-15",
        ),
        # MvpDebateView's DebateActivityLog render block must be disabled
        (
            "views/MvpDebateView.svelte",
            "DEACTIVATED 2026-06-16",
        ),
    ],
)
def test_duplicate_llm_monitor_remains_disabled(path, expected_inactive_marker):
    """The duplicate UI elements removed during the fix must stay gone."""
    src = _read(path)

    if path == "App.svelte":
        assert "StatusBar" not in src, (
            "App.svelte is rendering StatusBar again.  This duplicates "
            "the global LLM-Monitor from Header.svelte and was the "
            "cause of the 2026-06-17 user confusion."
        )
        return

    assert expected_inactive_marker in src, (
        f"{path} no longer contains the '{expected_inactive_marker}' "
        "marker.  The duplicate UI element is no longer explicitly "
        "marked as deactivated -- please re-add the marker to make "
        "the deactivation obvious to future readers."
    )


# ---------------------------------------------------------------------------
# 3. The 'DBG' markers in OTHER components must remain so they continue
#    to be useful as visual regression detectors.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,component_id,label_text",
    [
        (
            "components/debate/DebateActivityStrip.svelte",
            "DebateActivityStrip",
            "DBG: DebateActivityStrip.svelte",
        ),
        (
            "components/debate/DebateActivityLog.svelte",
            "DebateActivityLog",
            "DBG: DebateActivityLog.svelte",
        ),
        (
            "components/assistant/AssistantTypingIndicator.svelte",
            "AssistantTypingIndicator",
            "DBG: AssistantTypingIndicator.svelte",
        ),
        (
            "components/workflow/nodes/AgentNode.svelte",
            "AgentNode",
            "DBG: AgentNode.svelte",
        ),
    ],
)
def test_debug_markers_present_in_visual_components(path, component_id, label_text):
    """Each visually-rendered LLM-monitor-like component should keep
    its pink ``DBG:`` debug marker so the user can correlate the
    on-screen element with its source file during visual debugging.
    """
    src = _read(path)
    assert f'data-debug-component="{component_id}"' in src, (
        f"{path} is missing the data-debug-component={component_id!r} marker.  The visual regression detector is broken."
    )
    assert label_text in src, f"{path} is missing the human-readable debug label {label_text!r}.  Visual debugging is harder without it."


# ---------------------------------------------------------------------------
# 4. StatusBar.svelte must remain importable but inactive.
# ---------------------------------------------------------------------------


def test_statusbar_svelte_is_dead_code_with_banner():
    src = _read("components/feedback/StatusBar.svelte")
    assert "DEAD CODE 2026-06-17" in src, (
        "StatusBar.svelte no longer carries the 'DEAD CODE 2026-06-17' "
        "banner.  The next cleanup pass might delete this file thinking "
        "it's still used.  Restore the banner so the dead-code status is "
        "self-documenting."
    )
    app_src = _read("App.svelte")
    assert "StatusBar" not in app_src, (
        "App.svelte is importing StatusBar again.  The component was "
        "deactivated on 2026-06-17 -- re-importing it would re-introduce "
        "the duplicate UI element."
    )
