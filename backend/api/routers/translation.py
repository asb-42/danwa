"""Translation API router — endpoints for translating modules and managing translations."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.translation_service import (
    SUPPORTED_LANGUAGES,
    TranslationService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_translation_service() -> TranslationService:
    """Get or create the translation service singleton."""
    # Import here to avoid circular imports at module level
    from backend.services.translation_service import TranslationService

    if not hasattr(get_translation_service, "_instance"):
        get_translation_service._instance = TranslationService()  # type: ignore[attr-defined]
    return get_translation_service._instance  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TranslateRequest(BaseModel):
    """Request body for module translation."""

    target_language: str = Field(..., description="Target language code (e.g. 'de')")
    force: bool = Field(False, description="Force re-translation even if cached")
    llm_profile_id: str | None = Field(None, description="Override LLM profile for translation")
    skip_back_translation: bool = Field(False, description="Skip back-translation QA (faster but lower quality)")
    auto_approve: bool = Field(True, description="Auto-approve translations meeting quality threshold")
    quality_threshold: float = Field(0.7, description="Minimum quality score for auto-approval (0.0-1.0)")


class ApproveTranslationRequest(BaseModel):
    """Request body for manual translation approval."""

    file_path: str = Field(..., description="File path of the translation")
    approved: bool = Field(True, description="Set to True to approve, False to reject")


class InvalidateTranslationRequest(BaseModel):
    """Request body for invalidating cached translations."""

    file_path: str | None = Field(None, description="Specific file to invalidate (None = all files)")
    target_language: str | None = Field(None, description="Specific language to invalidate (None = all languages)")


class BatchTranslateRequest(BaseModel):
    """Request body for batch translation of multiple modules."""

    module_ids: list[str] = Field(..., description="List of module IDs to translate")
    target_language: str = Field(..., description="Target language code")
    force: bool = Field(False, description="Force re-translation even if cached")
    parallel: bool = Field(False, description="Translate modules in parallel (requires async support)")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/supported-languages")
async def get_supported_languages() -> dict[str, Any]:
    """Get the list of supported target languages for translation."""
    return {
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "source_language": "en",
    }


@router.post("/{module_id}/translate", response_model=dict[str, Any])
async def translate_module(
    module_id: str,
    body: TranslateRequest,
) -> dict[str, Any]:
    """Translate a module's content to the target language.

    Performs a two-pass translation with optional back-translation QA:
    1. Forward translation: EN source → target language
    2. (Optional) Back-translation: target → EN for quality verification
    3. Semantic comparison to compute quality score
    4. Auto-approval if quality meets threshold

    Returns detailed status including per-file quality scores.
    """
    svc = get_translation_service()

    # Validate language
    if body.target_language not in SUPPORTED_LANGUAGES and body.target_language != "en":
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported target language: {body.target_language}",
                "supported": sorted(SUPPORTED_LANGUAGES),
            },
        )

    result = svc.translate_module(
        module_id=module_id,
        target_language=body.target_language,
        force=body.force,
        llm_profile_id=body.llm_profile_id,
        skip_back_translation=body.skip_back_translation,
        auto_approve=body.auto_approve,
        quality_threshold=body.quality_threshold,
    )

    response = {
        "module_id": result.module_id,
        "target_language": result.target_language,
        "files_translated": result.files_translated,
        "files_skipped": result.files_skipped,
        "files_errored": result.files_errored,
        "quality_scores": result.quality_scores,
        "back_translation_scores": result.back_translation_scores,
        "status": result.status,
        "estimated_cost_usd": result.estimated_cost_usd,
    }

    if result.errors:
        response["errors"] = result.errors
    if result.warnings:
        response["warnings"] = result.warnings

    return response


@router.post("/{module_id}/approve", response_model=dict[str, Any])
async def approve_translation(
    module_id: str,
    body: ApproveTranslationRequest,
) -> dict[str, Any]:
    """Manually approve or reject a specific translation.

    Args:
        module_id: The module ID
        file_path: The file path within the module
        approved: True to approve, False to reject

    Returns:
        Success status
    """
    svc = get_translation_service()
    success = svc.approve_translation(
        module_id=module_id,
        file_path=body.file_path,
        target_language="de",  # Default; could be extended with query param
        approved=body.approved,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Translation not found for {module_id}/{body.file_path}",
        )

    return {
        "module_id": module_id,
        "file_path": body.file_path,
        "approved": body.approved,
    }


@router.get("/{module_id}/status", response_model=dict[str, Any])
async def get_translation_status(
    module_id: str,
    target_language: str | None = Query(None, description="Filter by target language"),
    approved_only: bool = Query(False, description="Show only approved translations"),
) -> dict[str, Any]:
    """Get the translation status for all files in a module.

    Returns per-file details including quality scores and approval status.
    """
    svc = get_translation_service()
    translations = svc.get_all_translations(
        module_id=module_id,
        target_language=target_language,
        approved_only=approved_only,
    )

    return {
        "module_id": module_id,
        "translations": [
            {
                "file_path": t.file_path,
                "language": t.target_language,
                "source_hash": t.source_hash,
                "quality_score": t.quality_score,
                "back_translation_score": t.quality_score,  # Same metric for now
                "approved": t.approved,
                "generated_at": t.generated_at,
                "translated_content_length": len(t.translated_content) if t.translated_content else 0,
                "has_content": t.translated_content is not None and len(t.translated_content) > 0,
            }
            for t in translations
        ],
    }


@router.get("/{module_id}/statistics", response_model=dict[str, Any])
async def get_translation_statistics(module_id: str) -> dict[str, Any]:
    """Get translation statistics for a module.

    Returns per-language breakdown of total, translated, approved, and average quality.
    """
    svc = get_translation_service()
    stats = svc.get_translation_statistics(module_id)
    return {"module_id": module_id, "statistics": stats}


@router.post("/{module_id}/invalidate", response_model=dict[str, Any])
async def invalidate_translation(
    module_id: str,
    body: InvalidateTranslationRequest,
) -> dict[str, Any]:
    """Invalidate cached translations to force re-translation.

    Args:
        module_id: The module ID
        file_path: If specified, only this file is invalidated
        target_language: If specified, only this language is invalidated

    Returns:
        Number of entries invalidated
    """
    svc = get_translation_service()
    count = svc.invalidate_translation(
        module_id=module_id,
        file_path=body.file_path,
        target_language=body.target_language,
    )
    return {"module_id": module_id, "invalidated_count": count}


@router.post("/batch-translate", response_model=dict[str, Any])
async def batch_translate(body: BatchTranslateRequest) -> dict[str, Any]:
    """Translate multiple modules to the same target language.

    Translates each module sequentially. For parallel translation,
    use the async endpoint when available.
    """
    svc = get_translation_service()
    results = []

    for module_id in body.module_ids:
        result = svc.translate_module(
            module_id=module_id,
            target_language=body.target_language,
            force=body.force,
        )
        results.append(
            {
                "module_id": result.module_id,
                "status": result.status,
                "files_translated": result.files_translated,
                "files_skipped": result.files_skipped,
                "files_errored": result.files_errored,
            }
        )

    return {
        "target_language": body.target_language,
        "modules_processed": len(results),
        "results": results,
    }
