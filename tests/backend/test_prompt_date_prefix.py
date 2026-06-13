"""Tests for backend/services/prompt_date_prefix.py — P4.3.

These tests pin the P4.3 behaviour:

* English is the SSOT and is rendered without touching the DB or the LLM.
* The English fallback path is used for any language that is not in
  :data:`backend.services.translation_service.SUPPORTED_LANGUAGES`
  (the canonical 11-language set: de, fr, es, it, pt, nl, pl, cs, zh,
  ja, ko).  RTL locales (``ar``/``he``/``fa``) and any long-tail locale
  must take this fast path.
* The in-process memoisation cache is keyed on ``(language,
  source_hash)``; flipping the source template flushes every entry.
* The on-demand translation path is delegated to
  :class:`TranslationService` with the synthetic module id
  ``_system_prompts`` and file path ``date_prefix_template``; a
  pre-populated DB cache hit short-circuits the LLM call.
* The template (not the formatted string) is what gets cached — i.e.
  the date is plugged in at every call so the cache survives a
  midnight rollover.
* Failures from the underlying :class:`TranslationService` never raise;
  they fall back to the English SSOT and emit a ``logger.debug``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services import prompt_date_prefix as pdp
from backend.services.prompt_date_prefix import (
    DATE_PLACEHOLDER,
    DATE_PREFIX_TEMPLATE_EN,
    _format_template,
    _load_or_translate_template,
    _reset_template_cache,
    _resolve_template,
    _source_hash,
    _today_iso,
    get_date_prefix,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_template_cache():
    """Wipe the in-process cache between tests so memoisation is
    deterministic."""
    _reset_template_cache()
    yield
    _reset_template_cache()


# ---------------------------------------------------------------------------
# TestSSOT
# ---------------------------------------------------------------------------


class TestSSOT:
    """English is the single source of truth."""

    def test_template_contains_date_placeholder(self) -> None:
        assert DATE_PLACEHOLDER in DATE_PREFIX_TEMPLATE_EN
        assert DATE_PREFIX_TEMPLATE_EN.startswith("Today is")

    def test_template_is_english_only(self) -> None:
        # Defensive: the SSOT must not regress into other languages.
        assert "Heute" not in DATE_PREFIX_TEMPLATE_EN
        assert "Aujourd" not in DATE_PREFIX_TEMPLATE_EN
        # ASCII-only check on the rest of the SSOT -- the only allowed
        # non-ASCII char is in the {date} placeholder.
        assert DATE_PREFIX_TEMPLATE_EN.encode("ascii", errors="strict").decode("ascii") == DATE_PREFIX_TEMPLATE_EN.replace("é", "e")

    def test_source_hash_is_stable_16_chars(self) -> None:
        h = _source_hash("hello world")
        assert len(h) == 16
        assert _source_hash("hello world") == h  # idempotent
        assert _source_hash("hello world") != _source_hash("hello WORLD")


class TestFormatTemplate:
    """``_format_template`` substitutes only the ``{date}`` placeholder."""

    def test_substitutes_date(self) -> None:
        assert _format_template(DATE_PREFIX_TEMPLATE_EN, "2026-06-13") == (
            "Today is 2026-06-13. All deadlines and time-sensitive evaluations refer to this date."
        )

    def test_leaves_other_braces_alone(self) -> None:
        # ``str.replace`` (not ``str.format``) is used so the template
        # is free to contain literal braces without escaping.
        tpl = "Today is {date}. Mention {not_a_placeholder} if asked."
        out = _format_template(tpl, "2030-01-01")
        assert out == "Today is 2030-01-01. Mention {not_a_placeholder} if asked."

    def test_no_substitution_is_a_noop(self) -> None:
        tpl = "Hello world"
        assert _format_template(tpl, "2026-06-13") == tpl


class TestTodayIso:
    def test_returns_iso_format(self) -> None:
        s = _today_iso()
        assert len(s) == 10
        assert s[4] == "-" and s[7] == "-"
        int(s[:4])
        int(s[5:7])
        int(s[8:10])


# ---------------------------------------------------------------------------
# TestEnglishShortCircuit
# ---------------------------------------------------------------------------


class TestEnglishShortCircuit:
    """English is rendered from the SSOT without DB/LLM traffic."""

    def test_default_language_is_english(self) -> None:
        out = get_date_prefix()
        assert out == _format_template(DATE_PREFIX_TEMPLATE_EN, _today_iso())

    def test_none_language_defaults_to_english(self) -> None:
        assert get_date_prefix(None) == get_date_prefix("en")

    def test_empty_string_defaults_to_english(self) -> None:
        assert get_date_prefix("") == get_date_prefix("en")

    def test_case_insensitive_english(self) -> None:
        assert get_date_prefix("EN") == get_date_prefix("en")
        assert get_date_prefix("En") == get_date_prefix("en")

    def test_en_does_not_consult_cache(self) -> None:
        # An English call must not populate the in-process cache --
        # otherwise the cache would grow without bound and would
        # leak stale source_hash entries after an English template
        # edit.
        get_date_prefix("en")
        assert "en" not in pdp._template_cache

    def test_en_does_not_consult_translation_service(self) -> None:
        with patch.object(pdp, "_load_or_translate_template") as mock_load:
            get_date_prefix("en")
            mock_load.assert_not_called()

    def test_explicit_date_is_used(self) -> None:
        assert get_date_prefix("en", "2030-01-15") == ("Today is 2030-01-15. All deadlines and time-sensitive evaluations refer to this date.")


# ---------------------------------------------------------------------------
# TestUnsupportedLanguageFallback
# ---------------------------------------------------------------------------


class TestUnsupportedLanguageFallback:
    """Languages outside the 11-language SUPPORTED set fall back to
    English without paying the on-demand translation cost."""

    @pytest.mark.parametrize("lang", ["ar", "he", "fa", "sv", "tr", "hu", "tlh"])
    def test_unsupported_language_falls_back_to_english(self, lang: str) -> None:
        assert get_date_prefix(lang) == _format_template(DATE_PREFIX_TEMPLATE_EN, _today_iso())

    def test_unsupported_language_skips_translation_service(self) -> None:
        # The ``_load_or_translate_template`` function is the *only*
        # path that touches TranslationService for non-English.  An
        # unsupported language must never reach it -- the early
        # SUPPORTED_LANGUAGES check should short-circuit in
        # ``_resolve_template``.
        with patch.object(pdp, "_load_or_translate_template") as mock_load:
            get_date_prefix("ar")
            mock_load.assert_not_called()

    def test_unsupported_language_skips_llm(self) -> None:
        # Belt-and-braces: if the SUPPORTED_LANGUAGES gate ever
        # regresses, the underlying ``translate_module`` call is the
        # one we most want to avoid (it's expensive).  This test
        # guards the gate by patching the whole ``TranslationService``
        # constructor and asserting it is *not* invoked for "ar".
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            get_date_prefix("ar")
            mock_cls.assert_not_called()

    def test_unknown_case_insensitive_uppercase(self) -> None:
        assert get_date_prefix("AR") == get_date_prefix("en")
        assert get_date_prefix(" Ar ") == get_date_prefix("en")


# ---------------------------------------------------------------------------
# TestSupportedLanguageDBCache
# ---------------------------------------------------------------------------


def _entry(language: str, translated: str, source_hash: str | None = None) -> object:
    """Build a fake ``TranslationEntry`` for the DB-cache hit path."""
    from backend.services.translation_service import TranslationEntry

    return TranslationEntry(
        id=f"_system_prompts:date_prefix_template:{language}",
        module_id="_system_prompts",
        file_path="date_prefix_template",
        source_language="en",
        target_language=language,
        source_hash=source_hash or _source_hash(DATE_PREFIX_TEMPLATE_EN),
        source_content=DATE_PREFIX_TEMPLATE_EN,
        translated_content=translated,
        back_translation=None,
        quality_score=1.0,
        approved=True,
        generated_at="2026-06-13T00:00:00Z",
        generated_by="llm",
        error=None,
    )


class TestSupportedLanguageDBCache:
    """A pre-populated DB cache hit short-circuits the LLM call."""

    def test_db_cache_hit_returns_translated_template(self) -> None:
        de_translation = "Heute ist der {date}. ..."
        fake_entry = _entry("de", de_translation)

        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = fake_entry
            out = get_date_prefix("de", "2030-01-15")

        assert out == "Heute ist der 2030-01-15. ..."
        # DB hit ⇒ no LLM call.
        mock_svc.translate_module.assert_not_called()
        # And the in-process cache must now hold the template.
        assert "de" in pdp._template_cache

    def test_db_cache_miss_triggers_translation(self) -> None:
        from backend.services.translation_service import TranslationResult

        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = None
            mock_svc.translate_module.return_value = TranslationResult(
                status="ok",
                module_id="_system_prompts",
                target_language="fr",
                files_translated=1,
                files_failed=0,
                files_total=1,
                duration_ms=42.0,
            )
            # After the on-demand translation, the cache must have
            # been re-read; simulate that.
            mock_svc.get_translation.side_effect = [
                None,
                _entry("fr", "Aujourd'hui, le {date}. ..."),
            ]
            out = get_date_prefix("fr", "2030-02-20")

        assert out == "Aujourd'hui, le 2030-02-20. ..."
        mock_svc.translate_module.assert_called_once()
        # The synthetic module id is honoured.
        kwargs = mock_svc.translate_module.call_args.kwargs
        assert kwargs["module_id"] == "_system_prompts"
        assert kwargs["target_language"] == "fr"

    def test_db_cache_stale_hash_refetches(self) -> None:
        # If the SSOT was edited (i.e. the hash changed) the cached
        # entry's source_hash no longer matches, so we must not
        # return the stale translation.
        stale = _entry("de", "stale!", source_hash="0" * 16)
        _ = _entry("de", "frisch: {date}")

        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = stale
            mock_svc.translate_module.return_value = None  # failure path
            mock_svc.get_translation.side_effect = [stale, None]

            out = get_date_prefix("de", "2030-01-01")

        # Falls back to English.
        assert out.startswith("Today is 2030-01-01")
        # LLM *was* consulted because the DB entry was stale.
        mock_svc.translate_module.assert_called_once()


# ---------------------------------------------------------------------------
# TestMemoisation
# ---------------------------------------------------------------------------


class TestMemoisation:
    """The in-process cache short-circuits repeated calls."""

    def test_second_call_does_not_re_consult_db(self) -> None:
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = _entry("it", "Oggi è il {date}. ...")
            first = get_date_prefix("it", "2030-01-01")
            second = get_date_prefix("it", "2030-01-02")

        # Same template, different dates -- the template cache is
        # what we cache, not the formatted string.
        assert first == "Oggi è il 2030-01-01. ..."
        assert second == "Oggi è il 2030-01-02. ..."
        # DB was consulted exactly once across both calls.
        assert mock_svc.get_translation.call_count == 1

    def test_cache_is_invalidated_when_source_hash_changes(self) -> None:
        # Prime the cache.
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_cls.return_value.get_translation.return_value = _entry("es", "Hoy es {date}. ...")
            get_date_prefix("es", "2030-01-01")
        # Simulate an edit to the SSOT.
        with patch.object(pdp, "DATE_PREFIX_TEMPLATE_EN", DATE_PREFIX_TEMPLATE_EN + "!"):
            with patch("backend.services.translation_service.TranslationService") as mock_cls:
                mock_svc = mock_cls.return_value
                # New SSOT has no DB entry yet, so the LLM path runs.
                mock_svc.get_translation.return_value = None
                mock_svc.translate_module.return_value = None
                get_date_prefix("es", "2030-02-02")
                # We re-entered the translation path ⇒ the cache was
                # invalidated.
                mock_svc.translate_module.assert_called_once()


# ---------------------------------------------------------------------------
# TestFailureFallback
# ---------------------------------------------------------------------------


class TestFailureFallback:
    """Any exception from the underlying service must fall back to
    English and *never* raise."""

    def test_translation_service_import_failure(self) -> None:
        # If for any reason TranslationService is not importable we
        # must not crash the LLM call.
        import builtins

        real_import = builtins.__import__

        def _import(name, *args, **kwargs):
            if name == "backend.services.translation_service" or name.endswith("translation_service"):
                raise ImportError("simulated import failure")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_import):
            out = get_date_prefix("de", "2030-01-01")

        assert out.startswith("Today is 2030-01-01")

    def test_translation_service_init_raises(self) -> None:
        with patch(
            "backend.services.translation_service.TranslationService",
            side_effect=RuntimeError("db down"),
        ):
            out = get_date_prefix("fr", "2030-01-01")

        assert out.startswith("Today is 2030-01-01")

    def test_translate_module_raises(self) -> None:
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = None
            mock_svc.import_source_content.return_value = True
            mock_svc.translate_module.side_effect = RuntimeError("llm down")
            out = get_date_prefix("ja", "2030-01-01")

        assert out.startswith("Today is 2030-01-01")

    def test_get_translation_returns_partial_entry_falls_back(self) -> None:
        from backend.services.translation_service import TranslationEntry

        empty = TranslationEntry(
            id="x:date_prefix_template:de",
            module_id="_system_prompts",
            file_path="date_prefix_template",
            target_language="de",
            source_hash=_source_hash(DATE_PREFIX_TEMPLATE_EN),
            translated_content="",  # empty -> not a hit
        )
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = empty
            mock_svc.translate_module.return_value = None  # fails
            out = get_date_prefix("de", "2030-01-01")

        assert out.startswith("Today is 2030-01-01")


# ---------------------------------------------------------------------------
# TestNeverRaises
# ---------------------------------------------------------------------------


class TestNeverRaises:
    """The contract: ``get_date_prefix`` never raises."""

    @pytest.mark.parametrize("lang", ["en", "de", "fr", "ar", "tlh", "", None])
    def test_never_raises_for_any_language(self, lang) -> None:
        # Patch the failure-prone code paths to raise and assert we
        # still get a string back.
        with patch(
            "backend.services.translation_service.TranslationService",
            side_effect=RuntimeError("nope"),
        ):
            out = get_date_prefix(lang, "2030-01-01")
        assert isinstance(out, str)
        assert out.startswith("Today is 2030-01-01")


# ---------------------------------------------------------------------------
# TestIntegrationWithLLMService (smoke test)
# ---------------------------------------------------------------------------


class TestIntegrationWithLLMService:
    """The LLM service must import cleanly with the new module and
    carry the ``language`` parameter."""

    def test_llm_service_generate_accepts_language(self) -> None:
        import inspect

        from backend.services.llm_service import LLMService

        sig = inspect.signature(LLMService.generate)
        assert "language" in sig.parameters
        assert sig.parameters["language"].default == "en"

    def test_llm_service_generate_with_fallback_accepts_language(self) -> None:
        import inspect

        from backend.services.llm_service import LLMService

        sig = inspect.signature(LLMService.generate_with_fallback)
        assert "language" in sig.parameters
        assert sig.parameters["language"].default == "en"

    def test_llm_service_generate_sync_accepts_language(self) -> None:
        import inspect

        from backend.services.llm_service import LLMService

        sig = inspect.signature(LLMService.generate_sync)
        assert "language" in sig.parameters
        assert sig.parameters["language"].default == "en"

    def test_llm_service_no_longer_hard_codes_german(self) -> None:
        src = open("backend/services/llm_service.py").read()
        assert "Heute ist der" not in src
        assert "Bewertungen" not in src
        assert "from backend.services.prompt_date_prefix import get_date_prefix" in src


# ---------------------------------------------------------------------------
# TestResolveTemplateDirect (white-box)
# ---------------------------------------------------------------------------


class TestResolveTemplateDirect:
    """White-box checks of ``_resolve_template``."""

    def test_en_returns_ssot(self) -> None:
        assert _resolve_template("en") == DATE_PREFIX_TEMPLATE_EN

    def test_caches_template(self) -> None:
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_cls.return_value.get_translation.return_value = _entry("pl", "Dziś jest {date}. ...")
            _resolve_template("pl")
            _resolve_template("pl")
            _resolve_template("pl")

        # DB was hit exactly once.
        assert mock_cls.return_value.get_translation.call_count == 1

    def test_unknown_language_skips_translation_service(self) -> None:
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            out = _resolve_template("xx")
        assert out == DATE_PREFIX_TEMPLATE_EN
        mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# TestLoadOrTranslateTemplateDirect
# ---------------------------------------------------------------------------


class TestLoadOrTranslateTemplateDirect:
    """White-box checks of ``_load_or_translate_template``."""

    def test_unsupported_via_resolve_returns_ssot_without_loading(self) -> None:
        # ``_load_or_translate_template`` assumes the caller has
        # already gated on ``SUPPORTED_LANGUAGES`` (that gate lives
        # in ``_resolve_template``).  Verify the gate: an unsupported
        # language never reaches the DB/LLM path through the
        # public-ish entry point.
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            out = _resolve_template("ar")
        assert out == DATE_PREFIX_TEMPLATE_EN
        mock_cls.assert_not_called()

    def test_load_or_translate_template_is_pure_db_path(self) -> None:
        # ``_load_or_translate_template`` is now an *internal* helper
        # that does not re-check SUPPORTED_LANGUAGES -- it is the
        # DB-cache + on-demand LLM path only.  Verify it honours a
        # DB hit and returns the translated template.
        with patch("backend.services.translation_service.TranslationService") as mock_cls:
            mock_svc = mock_cls.return_value
            mock_svc.get_translation.return_value = _entry("de", "Heute ist {date}. ...")
            out = _load_or_translate_template("de", _source_hash(DATE_PREFIX_TEMPLATE_EN))
        assert out == "Heute ist {date}. ..."
        mock_svc.translate_module.assert_not_called()
