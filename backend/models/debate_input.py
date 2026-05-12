"""DebateInput — standardized input artifact produced by Input Plugins.

This is the sole interface between input capture and workflow execution.
Workflow execution consumes **only** this artifact — never raw input data.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class InputAttachment(BaseModel):
    """An attachment included with a debate input.

    Can represent documents, audio files, transcriptions, or any
    supplementary material attached to the input.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mime_type: str = "text/plain"
    content_ref: str  # file path or inline string
    description: str = ""
    extracted_text: str | None = None  # for OCR documents, transcriptions


class DebateInput(BaseModel):
    """Standardized input artifact produced by Input Plugins.

    This is the sole interface between input capture and workflow
    execution.  Workflow execution consumes **only** this artifact —
    never the raw input data or plugin internals.
    """

    session_id: str | None = None  # set after workflow initialization
    source_plugin_key: str  # e.g. "standard_text", "stt", "a2a_inbound"
    source_metadata: dict = Field(default_factory=dict)
    # plugin-specific: filename, A2A agent ID, STT model, confidence, etc.
    topic: str  # the debate topic / case description
    attachments: list[InputAttachment] = Field(default_factory=list)
    context_overrides: dict = Field(default_factory=dict)
    # optional: ToneProfile, Workflow-Template selection, etc.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_hash: str = ""  # SHA-256 over topic + serialized attachments

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 over topic + attachments.

        Call this after construction to populate ``input_hash``.
        """
        payload = json.dumps(
            {
                "topic": self.topic,
                "attachments": [a.model_dump(include={"id", "mime_type", "content_ref"}) for a in self.attachments],
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def model_post_init(self, __context: object) -> None:
        """Auto-compute input_hash if not already set."""
        if not self.input_hash:
            self.input_hash = self.compute_hash()
