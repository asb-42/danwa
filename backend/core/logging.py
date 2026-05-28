"""Structured logging configuration using structlog.

Provides JSON logging in production, console logging in development.
Binds request_id and user_id to all log entries via contextvars.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structlog with appropriate processors for the environment.

    Args:
        debug: If True, use console renderer for human-readable output.
               If False, use JSON renderer for machine-parseable output.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if debug:
        # Development: colorful, human-readable console output
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production: structured JSON output
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if debug else logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries (uvicorn, etc.)
    # output through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )

    # Suppress noisy third-party loggers
    for name in [
        "httpx",
        "httpcore",
        "litellm",
        "python_multipart",
        "chromadb",
        "chromadb.utils.embedding_functions",
        "uvicorn.access",
    ]:
        logging.getLogger(name).setLevel(logging.WARNING)


def bind_request_context(request_id: str, user_id: str | None = None) -> None:
    """Bind request-scoped context to structlog contextvars.

    All subsequent log calls in the same async context will include
    these fields automatically.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)
