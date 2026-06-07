"""UI i18n API — Endpunkte für Frontend-String-Übersetzungen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.services.ui_translation_service import (
    DEFAULT_LOCALES,
    RTL_LOCALES,
    UITranslationService,
    get_plural_tags,
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
    wipe_first: bool = False


class WipeLocaleRequest(BaseModel):
    """Request to wipe all translations for a locale."""

    namespace: str = "global"


class RegisterLocaleRequest(BaseModel):
    """RegisterLocaleRequest class."""

    locale: str
    name: str | None = None
    is_rtl: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/locales")
async def get_supported_locales(
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Dynamically discovered list of supported locales with metadata."""
    all_locales = svc.get_installed_locales()
    return {
        "default_locale": "en",
        "locales": [
            {
                "code": loc["code"],
                "name": loc["name"],
                "is_rtl": loc["is_rtl"],
                "plural_tags": get_plural_tags(loc["code"]),
                "coverage": loc["source"],
            }
            for loc in all_locales
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


# --- Batch translation endpoints (MUST be before /{locale} to avoid shadowing) ---


@router.post("/bulk-translate")
async def bulk_translate(
    body: BulkTranslateRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Start an async bulk translation job. Returns job_id for polling."""
    # Optionally wipe existing translations first
    if body.wipe_first and body.target_locales:
        for locale in body.target_locales:
            svc.wipe_locale(locale, body.namespace)
    job_id = svc.bulk_translate_async(
        target_locales=body.target_locales,
        namespace=body.namespace,
    )
    return {"job_id": job_id}


@router.post("/{locale}/wipe")
async def wipe_locale(
    locale: str,
    body: WipeLocaleRequest | None = None,
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Delete all translations for a locale. Use before re-translating."""
    namespace = body.namespace if body else "global"
    result = svc.wipe_locale(locale, namespace)
    return result


@router.get("/bulk-translate/{job_id}/status")
async def get_translation_job_status(
    job_id: str,
) -> dict[str, Any]:
    """Get the status and progress of a translation job."""
    from backend.services.ui_translation_service import TranslationJobRegistry

    job = TranslationJobRegistry.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job.to_dict()


@router.get("/bulk-translate")
async def list_translation_jobs() -> dict[str, Any]:
    """List all translation jobs."""
    from backend.services.ui_translation_service import TranslationJobRegistry

    return {"jobs": TranslationJobRegistry.list_all()}


# --- Locale-specific routes ---


@router.get("/{locale}")
async def get_translations(
    locale: str,
    namespace: str = Query("global"),
    keys: str | None = Query(None, description="Komma-separierte Liste von Keys"),
    merge_langpacks: bool = Query(True, description="Merge language-pack namespaces"),
    svc: UITranslationService = Depends(get_i18n_service),
) -> dict[str, Any]:
    """Übersetzungen für eine Sprache abrufen.

    When merge_langpacks is True (default), strings from language-pack
    namespaces (langpack:*) are merged on top of the global namespace.
    Always returns translations — falls back to global namespace if locale
    is not explicitly registered (e.g. language-pack modules installed from repo).
    """
    if locale not in DEFAULT_LOCALES and not merge_langpacks:
        installed = svc.get_installed_locales()
        if not any(loc["code"] == locale for loc in installed):
            return {"locale": locale, "namespace": namespace, "translations": {}}
    key_list = keys.split(",") if keys else None
    result = svc.resolve_bulk(locale, namespace, key_list)

    # Merge language-pack namespaces on top
    if merge_langpacks:
        langpack_strings = svc.resolve_bulk_for_locale(locale, prefix="langpack:")
        # Langpack strings override global
        result = {**result, **langpack_strings}

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


# --- Language Pack Export ---


class LanguagePackExportRequest(BaseModel):
    """Request to export UI translations as a Language Pack ZIP."""

    name: str = "Custom Language Pack"
    description: str = ""
    pack_id_suffix: str = "custom"
    author: str = ""


@router.post("/{locale}/export-as-pack")
async def export_language_pack(
    locale: str,
    body: LanguagePackExportRequest,
    svc: UITranslationService = Depends(get_i18n_service),
) -> Any:
    """Export all UI translations for a locale as a Language Pack ZIP.

    Creates a ZIP archive containing:
    - manifest.json (ModuleManifest with type=language-pack)
    - ui_strings.json (key-value pairs for the locale)
    """
    import io
    import json
    import zipfile
    from datetime import UTC, datetime

    from fastapi.responses import StreamingResponse

    # Fetch all strings for the locale from global namespace
    strings = svc.resolve_bulk(locale, "global")
    if not strings:
        raise HTTPException(
            status_code=404,
            detail=f"No translations found for locale '{locale}' in global namespace",
        )

    module_id = f"lang-{locale}-{body.pack_id_suffix}"
    now = datetime.now(UTC).isoformat()

    manifest = {
        "schema_version": "2.0.0",
        "module_id": module_id,
        "name": {"en": body.name},
        "description": {"en": body.description} if body.description else {"en": f"Language pack for {locale}"},
        "version": "1.0.0",
        "type": "language-pack",
        "category": "translations",
        "language": locale,
        "author": {"name": body.author} if body.author else {"name": "Danwa User"},
        "license": "CC-BY-4.0",
        "tags": [locale, "custom"],
        "profile_file": "ui_strings.json",
        "profile_format": "json",
        "created_at": now,
    }

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{module_id}/manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        zf.writestr(f"{module_id}/ui_strings.json", json.dumps(strings, indent=2, ensure_ascii=False))

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={module_id}.zip"},
    )
