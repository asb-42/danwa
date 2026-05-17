"""UI i18n API — Endpunkte für Frontend-String-Übersetzungen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.services.ui_translation_service import (
    DEFAULT_LOCALES,
    LOCALE_NAMES,
    PLURAL_TAGS,
    RTL_LOCALES,
    UITranslationService,
)

router = APIRouter(tags=["i18n"])


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


def _get_service() -> UITranslationService:
    """Get or create the UI translation service singleton."""
    if not hasattr(_get_service, "_instance"):
        _get_service._instance = UITranslationService()  # type: ignore[attr-defined]
    return _get_service._instance  # type: ignore[attr-defined]


async def get_i18n_service(request: Request) -> UITranslationService:
    """Resolve the UI translation service, preferring test override from app state."""
    svc = getattr(request.app.state, "test_i18n_service", None)
    if svc is not None:
        return svc
    return _get_service()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TranslationSetRequest(BaseModel):
    """Set a single UI translation."""

    key: str
    value: str
    namespace: str = "global"


class BulkTranslationRequest(BaseModel):
    """Bulk-set translations for a locale."""

    locale: str
    translations: dict[str, str]
    namespace: str = "global"


class BulkTranslateRequest(BaseModel):
    """Request for batch LLM translation."""

    target_locales: list[str] | None = None
    namespace: str = "global"
    force: bool = False


class RegisterLocaleRequest(BaseModel):
    locale: str
    name: str | None = None
    is_rtl: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/locales")
async def get_supported_locales() -> dict[str, Any]:
    """Liste der unterstützten Sprachen mit Metadaten."""
    return {
        "default_locale": "de",
        "locales": [
            {
                "code": loc,
                "name": LOCALE_NAMES.get(loc, loc),
                "is_rtl": loc in RTL_LOCALES,
                "plural_tags": PLURAL_TAGS.get(loc, ["other"]),
                "coverage": "auto" if loc not in ("de", "en") else "manual",
            }
            for loc in DEFAULT_LOCALES
        ],
        "rtl_locales": sorted(RTL_LOCALES),
    }


# --- Stats & Coverage MUST come before /{locale} to avoid route collision ---


@router.get("/stats")
async def get_stats(
    namespace: str = Query("global"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Übersetzungsstatistiken pro Sprache."""
    return svc.get_stats(namespace)


@router.get("/coverage")
async def get_coverage(
    namespace: str = Query("global"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Coverage-Report für alle Sprachen."""
    return svc.get_coverage(namespace)


@router.get("/strings/{locale}")
async def get_locale_strings(
    locale: str,
    namespace: str = Query("global"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Per-locale string details with translation status, source, dates."""
    return svc.get_locale_details(locale, namespace)


# --- Locale registration MUST come before /{locale} to avoid route collision ---


@router.get("/custom-locales")
async def list_custom_locales(
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """List all custom-registered locales."""
    return {"custom_locales": svc.get_custom_locales()}


@router.post("/locales", status_code=201)
async def register_locale(
    body: RegisterLocaleRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Register a new custom locale not in the default set."""
    return svc.register_custom_locale(body.locale, body.name, body.is_rtl)


# --- Batch translation endpoint (MUST be before /{locale} to avoid shadowing) ---


@router.post("/bulk-translate")
async def bulk_translate(
    body: BulkTranslateRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Batch LLM-Übersetzung für fehlende Strings."""
    results = svc.bulk_translate(
        target_locales=body.target_locales,
        namespace=body.namespace,
    )
    # Invalidate cache for all affected locales
    for locale in results.keys():
        svc.invalidate_cache(locale)
    return {"results": results}


# --- Locale-specific routes ---


@router.get("/{locale}")
async def get_translations(
    locale: str,
    namespace: str = Query("global"),
    keys: str | None = Query(None, description="Komma-separierte Liste von Keys"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Übersetzungen für eine Sprache abrufen."""
    key_list = keys.split(",") if keys else None
    result = svc.resolve_bulk(locale, namespace, key_list)
    return {"locale": locale, "namespace": namespace, "translations": result}


@router.get("/{locale}/{key}")
async def get_single_translation(
    locale: str,
    key: str,
    namespace: str = Query("global"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, str]:
    """Einzelne Übersetzung abrufen."""
    value = svc.resolve(key, locale, namespace)
    return {"locale": locale, "key": key, "value": value}


@router.post("/{locale}")
async def set_translations(
    body: BulkTranslationRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Mehrere Übersetzungen für eine Sprache setzen."""
    count = svc.bulk_import(
        {body.locale: body.translations},
        namespace=body.namespace,
    )
    svc.invalidate_cache(body.locale)
    return {"locale": body.locale, "imported": count}


@router.put("/{locale}/{key}")
async def update_translation(
    locale: str,
    key: str,
    body: TranslationSetRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, str]:
    """Einzelne Übersetzung erstellen/aktualisieren."""
    svc.set_translation(body.key, locale, body.value, body.namespace)
    svc.invalidate_cache(locale)
    return {"locale": locale, "key": key, "value": body.value}


@router.delete("/{locale}/{key}")
async def delete_translation(
    locale: str,
    key: str,
    namespace: str = Query("global"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Übersetzung löschen."""
    deleted = svc.delete_translation(key, locale, namespace)
    if not deleted:
        raise HTTPException(status_code=404, detail="Translation not found")
    svc.invalidate_cache(locale)
    return {"deleted": True}
