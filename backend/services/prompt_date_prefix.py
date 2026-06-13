"""i18n date-prefix for system prompts (section 3.4 of the 2026-06-12 review).

Background
----------
Every call to :func:`backend.services.llm_service.LLMService.generate`
injects a short date line into the system prompt so the model knows
"today".  The pre-fix code hard-coded a German sentence:

    "Heute ist der 2026-06-13. Alle Fristen, Termine und zeitlichen
     Bewertungen beziehen sich auf dieses Datum."

That violates the report's section 3.4 because:

* The date prefix is shipped into *every* LLM call regardless of the
  active language or the user's UI language preference.
* The SSOT for the project is English; injecting a German sentence
  into an English workflow is a confusing mixed-language prefix.
* For multi-locale deployments the prompt diverges from the
  configured persona.

Design
------
The English template is the single source of truth.  When the active
language is ``"en"`` (or unknown) the template is formatted in
process; no DB or LLM calls happen.

For any other language we route through the existing
:mod:`backend.services.translation_service` infrastructure — the same
mechanism the Kitsune assistant prompt already uses
(:func:`backend.services.assistant_service.load_kitsune_prompt`).
The translation is **cached once per language in the
``module_translation_cache`` table** and additionally memoised in
process for the lifetime of the server.

Crucially, we cache the *template* (with a ``{date}`` placeholder),
not the *formatted* string.  The actual date is plugged in at every
call site, so the cache stays valid across days without invalidation.

Fallback policy
---------------
If a language is not in :data:`backend.services.translation_service.SUPPORTED_LANGUAGES`
or the on-demand translation fails for any reason, we fall back to
the English template.  We never raise.  A failed cache fill is a
*correctness* problem (mixed-language prefix) not a *crash* problem,
and the fallback path is a one-line ``logger.debug``.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single source of truth: English template.
# ---------------------------------------------------------------------------

#: The English date-prefix template.  ``{date}`` is replaced with the
#: ISO 8601 date (``YYYY-MM-DD``) at format time.
DATE_PREFIX_TEMPLATE_EN: str = "Today is {date}. All deadlines and time-sensitive evaluations refer to this date."

#: The placeholder used in the template.  Exposed for tests and for
#: any caller that wants to introspect or substitute it.
DATE_PLACEHOLDER: str = "{date}"


# ---------------------------------------------------------------------------
# Translation-cache key.
# ---------------------------------------------------------------------------
#
# We use a synthetic module_id so the existing TranslationService
# schema can store the translated template without any new tables or
# migrations.  One row per supported language.
#
# The DB row key is exactly the same shape that
# :func:`backend.services.translation_service.TranslationService.import_source_content`
# already produces, so the schema, the back-translation QA, and the
# approval workflow all work out of the box.

_TRANSLATION_MODULE_ID: str = "_system_prompts"
_TRANSLATION_FILE_PATH: str = "date_prefix_template"


# ---------------------------------------------------------------------------
# In-process memoisation.
# ---------------------------------------------------------------------------
#
# Keyed on (language, source_hash) so that a future edit to the
# English template automatically invalidates every cached entry.

_template_cache: dict[str, tuple[str, str]] = {}


def _source_hash(content: str) -> str:
    """Stable 16-char SHA-256 prefix of *content* (matches the
    TranslationService's own hashing policy)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _format_template(template: str, date_str: str) -> str:
    """Substitute ``{date}`` in *template* with *date_str*.

    Uses plain ``str.replace`` rather than ``str.format`` so the
    template can contain literal ``{`` and ``}`` characters without
    needing to be doubled.  Only ``{date}`` is substituted; any
    other braces are left alone.
    """
    return template.replace(DATE_PLACEHOLDER, date_str)


def _today_iso() -> str:
    """Return today's date in ISO 8601 (``YYYY-MM-DD``) form.

    Split out for testability — tests can monkeypatch this rather
    than ``datetime.now`` directly.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def get_date_prefix(
    language: str | None = None,
    date: str | None = None,
) -> str:
    """Return the system-prompt date prefix in *language*.

    Args:
        language: ISO 639-1 code (e.g. ``"en"``, ``"de"``, ``"fr"``).
            Defaults to ``"en"`` when ``None`` or empty.  Unknown /
            unsupported languages fall back to English.
        date: ISO 8601 date string (``YYYY-MM-DD``) to embed in the
            template.  Defaults to today (UTC).

    Returns:
        A single line of text, ready to prepend to a system prompt.
        Never raises.
    """
    lang = (language or "en").strip().lower() or "en"
    date_str = date or _today_iso()
    template = _resolve_template(lang)
    return _format_template(template, date_str)


def _resolve_template(language: str) -> str:
    """Return the unformatted template for *language*.

    Three short-circuits happen *before* the DB/LLM path is reached:

    1. ``"en"`` -> SSOT, no cache, no I/O.
    2. Language not in :data:`SUPPORTED_LANGUAGES` -> SSOT, no I/O
       (covers the RTL locales ``ar``/``he``/``fa`` and any
       long-tail locale that the TranslationService can't handle).
    3. In-process cache hit on ``(language, source_hash)`` -> cached
       template, no I/O.

    Only if all three miss do we consult
    :class:`TranslationService` (DB hit, then on-demand translation).
    """
    if language == "en":
        return DATE_PREFIX_TEMPLATE_EN

    # Cheap static gate: don't even build a TranslationService
    # instance for languages the system can never translate.
    if not _is_supported_language(language):
        return DATE_PREFIX_TEMPLATE_EN

    src_hash = _source_hash(DATE_PREFIX_TEMPLATE_EN)
    cached = _template_cache.get(language)
    if cached is not None and cached[1] == src_hash:
        return cached[0]

    template = _load_or_translate_template(language, src_hash)
    # Cache the *template*, not the formatted string -- the date
    # changes daily but the template is stable.
    _template_cache[language] = (template, src_hash)
    return template


def _is_supported_language(language: str) -> bool:
    """Return True if *language* is in the canonical SUPPORTED set.

    The check is best-effort: if the TranslationService module is
    itself unimportable we treat every language as unsupported
    (which means a guaranteed English-fallback, no LLM call).
    """
    try:
        from backend.services.translation_service import SUPPORTED_LANGUAGES
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "TranslationService unavailable for SUPPORTED_LANGUAGES check (%s); treating %r as unsupported",
            exc,
            language,
        )
        return False
    return language in SUPPORTED_LANGUAGES


def _load_or_translate_template(language: str, src_hash: str) -> str:
    """DB-cache lookup, on-demand translation, English fallback.

    Assumes the caller has already verified that *language* is in
    :data:`SUPPORTED_LANGUAGES`.  Returns the translated template
    for *language*, falling back to the English SSOT on any error.
    Never raises.
    """
    try:
        from backend.services.translation_service import TranslationService
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "TranslationService unavailable for date prefix (%s); falling back to English",
            exc,
        )
        return DATE_PREFIX_TEMPLATE_EN

    try:
        svc = TranslationService()

        # 1. DB cache hit.
        entry = svc.get_translation(_TRANSLATION_MODULE_ID, _TRANSLATION_FILE_PATH, language)
        if entry is not None and entry.translated_content and entry.source_hash == src_hash:
            return entry.translated_content

        # 2. Cold cache: import the source (idempotent) and translate.
        svc.import_source_content(
            module_id=_TRANSLATION_MODULE_ID,
            file_path=_TRANSLATION_FILE_PATH,
            content=DATE_PREFIX_TEMPLATE_EN,
        )
        result = svc.translate_module(
            module_id=_TRANSLATION_MODULE_ID,
            target_language=language,
            force=False,
            auto_approve=True,
            quality_threshold=0.5,
        )
        if result.status in ("ok", "partial") and result.files_translated > 0:
            entry = svc.get_translation(_TRANSLATION_MODULE_ID, _TRANSLATION_FILE_PATH, language)
            if entry and entry.translated_content:
                return entry.translated_content
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Date-prefix translation for %r failed (%s); falling back to English",
            language,
            exc,
        )

    return DATE_PREFIX_TEMPLATE_EN


# ---------------------------------------------------------------------------
# Test helpers (not part of the public API).
# ---------------------------------------------------------------------------


def _reset_template_cache() -> None:
    """Empty the in-process template cache.

    Public to tests only.  The DB cache is *not* touched; tests that
    want a clean DB should pass a ``db_path=`` to
    :class:`TranslationService` directly.
    """
    _template_cache.clear()
