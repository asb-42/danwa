"""RenderJob — tracks the lifecycle of a single output render job."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RenderJobStatus(StrEnum):
    """Lifecycle states for a render job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RenderJob(BaseModel):
    """Tracks the lifecycle of a single render job.

    A render job is created when the user requests output generation
    for a completed session.  The ``plugin_key`` determines which
    ``OutputPlugin`` handles the rendering.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str  # references a DebateArtifact
    status: RenderJobStatus = RenderJobStatus.QUEUED
    plugin_key: str  # e.g. "print", "tts"
    config: dict = Field(default_factory=dict)  # plugin-specific config
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    output_files: list[str] = Field(default_factory=list)
    artifact_snapshot_hash: str = ""  # SHA-256 of DebateArtifact JSON
    progress_current: int = 0  # number of items processed so far
    progress_total: int = 0  # total number of items to process
