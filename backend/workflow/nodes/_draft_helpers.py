"""Shared helpers for the workflow ``current_draft`` running log.

Sprint 39 — H2 fix.  The ``current_draft`` state key is a running
concatenation of every agent's output.  Without bounds it grows
without limit across long debates and interjection-rich flows,
which in turn blows up the next agent's user prompt (every agent
injects the entire ``current_draft`` into its prompt, see
``agent_nodes.py:232``).

The previous design (a 50 000-char cap with head+tail preservation)
was lossy in two ways: it dropped the head (the early debate
history is exactly what the LLM needs to keep context coherent)
and it was applied inconsistently — the interjection node and
the legacy ``run_agent_node`` accumulated without any cap at all.

The new design:

* **Tail-only** — the most recent content is what matters for
  context continuity.  The head is dropped when we hit the cap.
* **Single helper** — all three accumulators
  (``agent_nodes._agent_node``, ``system_nodes.interjection_node``,
  ``legacy_nodes.run_agent_node``) call this helper, so the
  truncation semantics stay in sync.
* **Marker at the start** — when truncation fires, a short
  ``[… content truncated …]`` marker is prepended so the LLM (or
  the human reader of the final export) sees that some content
  was dropped.

Consensus estimation (``moderator_nodes.py:152``) is unaffected
by the content loss because it only uses the draft length, not
its content.  HITL context snippets (``hitl/nodes.py:205``) read
only the last 500 chars and are likewise unaffected.
"""

from __future__ import annotations

# Cap on the running ``current_draft`` log.  Promoted to a
# module-level constant in Sprint 35 (L2 fix); the value is kept
# here as the single source of truth.  The same constant is
# re-exported by ``agent_nodes`` for backward compatibility.
MAX_RUNNING_DRAFT_LEN = 50000

# Short marker prepended when truncation fires.  The marker is
# short enough to keep the visible content dense but visible
# enough that an LLM (or human reader) can see that the head of
# the debate was dropped.
RUNNING_DRAFT_TRUNCATION_MARKER = "\n\n[… content truncated …]\n\n"


def truncate_running_draft(
    text: str,
    max_len: int = MAX_RUNNING_DRAFT_LEN,
    marker: str = RUNNING_DRAFT_TRUNCATION_MARKER,
) -> str:
    """Bound a running log of text to the last ``max_len`` characters.

    Tail-only — keeps the most recent content (which is what
    LLM prompts and the next agent need) and discards the head.

    A short ``marker`` is prepended when truncation fires so the
    reader sees that content was dropped.  The total output
    length is at most ``max_len`` characters — the marker is
    included in the cap so the helper's output never exceeds
    ``max_len`` even when truncation is active.

    Parameters
    ----------
    text:
        The accumulated text to bound.  May be empty.
    max_len:
        Maximum allowed length of the returned string.  Must be
        at least ``len(marker) + 1`` (otherwise the function
        raises ``ValueError``).
    marker:
        Text prepended when truncation fires.  Counts toward
        ``max_len``.

    Returns
    -------
    str
        ``text`` unchanged if its length is ``<= max_len``;
        otherwise ``marker + text[-(max_len - len(marker))]``.

    Raises
    ------
    ValueError
        If ``max_len < len(marker) + 1`` — the helper could not
        produce a meaningful output.
    """
    if max_len < len(marker) + 1:
        raise ValueError(f"max_len={max_len} too small for marker of length {len(marker)}; need at least {len(marker) + 1}")
    if len(text) <= max_len:
        return text
    keep = max_len - len(marker)
    return marker + text[-keep:]
