"""UI i18n API — Endpunkte für Frontend-String-Übersetzungen."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any

from backend.services.ui_translation_service import (
    UITranslationService,
    DEFAULT_LOCALES,
    LOCALE_NAMES,
    RTL_LOCALES,
    PLURAL_TAGS,
)

router = APIRouter(tags=["i18n"])


def _get_service() -> UITranslationService:
    """Get or create the UI translation service singleton."""
    if not hasattr(_get_service, "_instance"):
        _get_service._instance = UITranslationService()  # type: ignore[attr-defined]
    return _get_service._instance  # type: ignore[attr-defined]


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


@router.get("/{locale}")
async def get_translations(
    locale: str,
    namespace: str = Query("global"),
    keys: str | None = Query(None, description="Komma-separierte Liste von Keys"),
) -> dict[str, Any]:
    """Übersetzungen für eine Sprache abrufen."""
    svc = _get_service()
    key_list = keys.split(",") if keys else None
    result = svc.resolve_bulk(locale, namespace, key_list)
    return {"locale": locale, "namespace": namespace, "translations": result}


@router.get("/{locale}/{key}")
async def get_single_translation(locale: str, key: str,
                                  namespace: str = Query("global")) -> dict[str, str]:
    """Einzelne Übersetzung abrufen."""
    svc = _get_service()
    value = svc.resolve(key, locale, namespace)
    return {"locale": locale, "key": key, "value": value}


@router.post("/{locale}")
async def set_translations(body: BulkTranslationRequest) -> dict[str, Any]:
    """Mehrere Übersetzungen für eine Sprache setzen."""
    svc = _get_service()
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
) -> dict[str, str]:
    """Einzelne Übersetzung erstellen/aktualisieren."""
    svc = _get_service()
    svc.set_translation(body.key, locale, body.value, body.namespace)
    svc.invalidate_cache(locale)
    return {"locale": locale, "key": key, "value": body.value}


@router.delete("/{locale}/{key}")
async def delete_translation(locale: str, key: str,
                              namespace: str = Query("global")) -> dict[str, Any]:
    """Übersetzung löschen."""
    svc = _get_service()
    deleted = svc.delete_translation(key, locale, namespace)
    if not deleted:
        raise HTTPException(status_code=404, detail="Translation not found")
    svc.invalidate_cache(locale)
    return {"deleted": True}


@router.get("/stats")
async def get_stats(namespace: str = Query("global")) -> dict[str, Any]:
    """Übersetzungsstatistiken pro Sprache."""
    svc = _get_service()
    return svc.get_stats(namespace)


@router.get("/coverage")
async def get_coverage(namespace: str = Query("global")) -> dict[str, Any]:
    """Coverage-Report für alle Sprachen."""
    svc = _get_service()
    return svc.get_coverage(namespace)
