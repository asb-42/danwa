"""A2A exception hierarchy (Phase 8).

Structured exceptions for A2A protocol errors, each carrying
context about the endpoint, task ID, and error details.
"""

from __future__ import annotations


class A2AError(Exception):
    """Base exception for all A2A protocol errors."""

    def __init__(
        self,
        message: str,
        endpoint: str | None = None,
        task_id: str | None = None,
        error_code: int | None = None,
    ) -> None:
        """Initialise A2AError."""
        super().__init__(message)
        self.endpoint = endpoint
        self.task_id = task_id
        self.error_code = error_code


class A2ATimeoutError(A2AError):
    """Raised when an A2A call exceeds the configured timeout."""


class A2AConnectionError(A2AError):
    """Raised when the HTTP connection to the A2A agent fails."""


class A2AProtocolError(A2AError):
    """Raised when the A2A agent returns an invalid JSON-RPC response."""


class A2AValidationError(A2AError):
    """Raised when the A2A URL fails validation (bad scheme, private IP)."""


class A2AAgentError(A2AError):
    """Raised when the external A2A agent returns an error in its response."""
