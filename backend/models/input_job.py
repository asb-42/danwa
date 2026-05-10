"""InputJob — tracks the lifecycle of a single input processing job."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.models.debate_input import DebateInput


class InputJobStatus(StrEnum):
    """Lifecycle states for an input processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_APPROVAL = "pending_approval"


class InputJob(BaseModel):
    """Tracks the lifecycle of a single input processing job.

    An input job is created when a user or external agent submits input
    via an ``InputPlugin``.  The ``plugin_key`` determines which plugin
    handles the capture/processing.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: InputJobStatus = InputJobStatus.QUEUED
    plugin_key: str  # e.g. "standard_text", "stt", "a2a_inbound"
    config: dict = Field(default_factory=dict)  # plugin-specific config
    raw_input_data: dict = Field(default_factory=dict)  # original input
    processed_input: DebateInput | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
