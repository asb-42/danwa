"""Blueprint Canvas — custom exceptions and centralized error handlers.

Maps domain exceptions to HTTP status codes for consistent API responses.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class BlueprintNotFoundError(Exception):
    """Raised when a blueprint entity is not found."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} '{entity_id}' not found")


class BlueprintConflictError(Exception):
    """Raised when creating an entity with a duplicate ID."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} '{entity_id}' already exists")


class BlueprintValidationError(Exception):
    """Raised for business logic validation errors."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------


def register_error_handlers(app: FastAPI) -> None:
    """Register centralized error handlers on the FastAPI app."""

    @app.exception_handler(BlueprintNotFoundError)
    async def handle_not_found(request: Request, exc: BlueprintNotFoundError) -> JSONResponse:
        logger.debug("Not found: %s", exc)
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(BlueprintConflictError)
    async def handle_conflict(request: Request, exc: BlueprintConflictError) -> JSONResponse:
        logger.debug("Conflict: %s", exc)
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )

    @app.exception_handler(BlueprintValidationError)
    async def handle_validation(request: Request, exc: BlueprintValidationError) -> JSONResponse:
        logger.debug("Validation error: %s", exc)
        return JSONResponse(
            status_code=422,
            content={"detail": exc.detail},
        )


# ---------------------------------------------------------------------------
# Rate Limit Handler (used by slowapi)
# ---------------------------------------------------------------------------


async def _rate_limit_handler(request: Request, exc) -> JSONResponse:
    """Handler for slowapi RateLimitExceeded exceptions."""
    logger.warning("Rate limit exceeded for %s: %s", request.url.path, exc.detail)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
