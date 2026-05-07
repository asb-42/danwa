"""A2A Pydantic schemas — request/response models for A2A protocol."""

from __future__ import annotations

from pydantic import BaseModel, Field


class A2ATextPart(BaseModel):
    """A single text part in an A2A message."""

    type: str = "text"
    text: str = ""


class A2AMessage(BaseModel):
    """An A2A message containing one or more parts."""

    role: str = "user"
    parts: list[A2ATextPart] = Field(default_factory=list)


class A2ATask(BaseModel):
    """An A2A task request."""

    id: str | None = None
    message: A2AMessage | None = None
    metadata: dict = Field(default_factory=dict)


class A2ATaskStatus(BaseModel):
    """Status of an A2A task."""

    state: str = "submitted"
    message: str | None = None


class A2AResponse(BaseModel):
    """A JSON-RPC 2.0 response envelope for A2A."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: dict | None = None
    error: dict | None = None
