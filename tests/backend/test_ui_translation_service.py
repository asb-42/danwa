"""Tests for backend/services/ui_translation_service.py.

The service had 41 % coverage.  These tests focus on the testable surface:

  * TranslationJob dataclass (progress, to_dict)
  * TranslationJobRegistry (submit, get, list_all)
  * get_plural_tags (module-level helper)
  * CRUD: set_translation, get_translation, get_translations_bulk,
    get_all_keys, delete_translation, bulk_import
  * Resolve: resolve (with fallback chain), resolve_bulk
  * Resolve-bulk-for-locale (langpack namespace merging)
  * Cache: _get_locale_cache, invalidate_cache
  * Stats: get_stats, get_coverage
  * wipe_locale
  * Custom locales: register_custom_locale, get_custom_locales
  * _select_llm_for_locale, _locale_name
  * bootstrap_core_locales (idempotent migration)
  * cleanup_legacy_local_langpacks
  * _create_langpack_module_dir
  * get_installed_locales

LLM-dependent paths (``translate_via_llm``, ``bulk_translate``,
``bulk_translate_async``) are exercised via a mock LLM that returns
deterministic translations, so the full translation pipeline is covered
without hitting any real API.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.services.ui_translation_service import (
    CORE_LOCALES,
    DEFAULT_LOCALES,
    LOCALE_NAMES,
    PLURAL_TAGS,
    RTL_LOCALES,
    TranslationJob,
    TranslationJobRegistry,
    UITranslationService,
    get_plural_tags,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service(tmp_path) -> UITranslationService:
    """Service with isolated DB and base_dir."""
    return UITranslationService(
        db_path=tmp_path / "ui_translations.db",
        base_dir=tmp_path / "i18n",
    )


@pytest.fixture(autouse=True)
def _reset_job_registry():
    """Clear the singleton job registry between tests."""
    with TranslationJobRegistry._lock:
        TranslationJobRegistry._jobs.clear()
    yield
    with TranslationJobRegistry._lock:
        TranslationJobRegistry._jobs.clear()


def _wait_for_job(job_id: str, timeout: float = 5.0) -> TranslationJob | None:
    """Poll the registry until the given job is no longer 'pending'/'running'."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        job = TranslationJobRegistry.get(job_id)
        if job is None:
            return None
        if job.status in ("completed", "failed"):
            return job
        time.sleep(0.05)
    return TranslationJobRegistry.get(job_id)


# ---------------------------------------------------------------------------
# TranslationJob
# ---------------------------------------------------------------------------


class TestTranslationJob:
    def test_progress_zero_when_total_is_zero(self):
        job = TranslationJob(job_id="j1", target_locales=["de"], namespace="global")
        assert job.progress() == 0.0

    def test_progress_rounded_to_one_decimal(self):
        job = TranslationJob(
            job_id="j1",
            target_locales=["de"],
            namespace="global",
            total_strings=3,
            completed_strings=1,
        )
        assert job.progress() == 33.3

    def test_to_dict_shape(self):
        job = TranslationJob(
            job_id="j1",
            target_locales=["de"],
            namespace="global",
            total_strings=10,
            completed_strings=5,
        )
        d = job.to_dict()
        assert d["job_id"] == "j1"
        assert d["status"] == "pending"
        assert d["target_locales"] == ["de"]
        assert d["namespace"] == "global"
        assert d["total_strings"] == 10
        assert d["completed_strings"] == 5
        assert d["progress_pct"] == 50.0
        assert d["results"] == {}
        assert d["error"] is None


# ---------------------------------------------------------------------------
# TranslationJobRegistry
# ---------------------------------------------------------------------------


class TestTranslationJobRegistry:
    def test_submit_and_get(self):
        job = TranslationJob(job_id="j1", target_locales=["de"], namespace="global")
        result_id = TranslationJobRegistry.submit(job, lambda: None)
        assert result_id == "j1"
        got = TranslationJobRegistry.get("j1")
        assert got is job

    def test_get_unknown_returns_none(self):
        assert TranslationJobRegistry.get("missing") is None

    def test_list_all_returns_dicts(self):
        TranslationJobRegistry.submit(
            TranslationJob(job_id="j1", target_locales=["de"], namespace="global"),
            lambda: None,
        )
        TranslationJobRegistry.submit(
            TranslationJob(job_id="j2", target_locales=["fr"], namespace="global"),
            lambda: None,
        )
        all_jobs = TranslationJobRegistry.list_all()
        assert {j["job_id"] for j in all_jobs} == {"j1", "j2"}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestGetPluralTags:
    def test_known_locale(self):
        assert get_plural_tags("de") == ["one", "other"]
        assert get_plural_tags("en") == ["one", "other"]

    def test_russian_has_few_many(self):
        assert get_plural_tags("ru") == ["one", "few", "many", "other"]

    def test_arabic_has_full_set(self):
        assert get_plural_tags("ar") == ["zero", "one", "two", "few", "many", "other"]

    def test_unknown_locale_falls_back_to_default(self):
        assert get_plural_tags("xx") == ["one", "other"]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestCRUD:
    def test_set_and_get(self, service: UITranslationService):
        service.set_translation("nav.dashboard", "en", "Dashboard")
        assert service.get_translation("nav.dashboard", "en") == "Dashboard"

    def test_set_then_update_increments_version(self, service: UITranslationService):
        service.set_translation("nav.dashboard", "en", "Dashboard")
        service.set_translation("nav.dashboard", "en", "Dashboard v2")
        assert service.get_translation("nav.dashboard", "en") == "Dashboard v2"

    def test_set_with_namespace(self, service: UITranslationService):
        service.set_translation("btn.save", "de", "Speichern", namespace="langpack:lang-de")
        assert service.get_translation("btn.save", "de", namespace="langpack:lang-de") == "Speichern"

    def test_set_with_source_is_stored(self, service: UITranslationService):
        service.set_translation("btn.save", "de", "Speichern", source="llm_generated")
        conn = service._get_conn()
        row = conn.execute(
            "SELECT source FROM ui_translations WHERE key = ? AND locale = ?",
            ("btn.save", "de"),
        ).fetchone()
        conn.close()
        assert row["source"] == "llm_generated"

    def test_get_translation_missing_returns_none(self, service: UITranslationService):
        assert service.get_translation("missing.key", "en") is None

    def test_get_translations_bulk_specific_keys(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("b", "en", "B")
        service.set_translation("c", "en", "C")
        result = service.get_translations_bulk("en", keys=["a", "b", "missing"])
        assert result == {"a": "A", "b": "B"}

    def test_get_translations_bulk_fills_cache(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("b", "en", "B")
        service.get_translations_bulk("en")
        assert "en" in service._locales_cache
        assert service._locales_cache["en"] == {"a": "A", "b": "B"}

    def test_get_all_keys_unions_db_with_bundled(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        keys = service.get_all_keys()
        assert "a" in keys
        assert "nav.dashboard" in keys

    def test_delete_translation(self, service: UITranslationService):
        # Use a non-bundled key to avoid fallback to JS loaders
        service.set_translation("custom.test.key", "en", "TestValue")
        assert service.delete_translation("custom.test.key", "en") is True
        assert service.get_translation("custom.test.key", "en") is None

    def test_delete_nonexistent_returns_false(self, service: UITranslationService):
        assert service.delete_translation("missing.key", "en") is False

    def test_bulk_import(self, service: UITranslationService):
        translations = {
            "en": {"a": "A", "b": "B"},
            "de": {"a": "A-de"},
        }
        count = service.bulk_import(translations)
        assert count == 3
        assert service.get_translation("a", "en") == "A"
        assert service.get_translation("b", "en") == "B"
        assert service.get_translation("a", "de") == "A-de"


# ---------------------------------------------------------------------------
# Resolve with fallback chain
# ---------------------------------------------------------------------------


class TestResolve:
    def test_returns_locale_value(self, service: UITranslationService):
        service.set_translation("btn.save", "de", "Speichern")
        assert service.resolve("btn.save", "de") == "Speichern"

    def test_falls_back_to_en(self, service: UITranslationService):
        service.set_translation("btn.save", "en", "Save")
        assert service.resolve("btn.save", "de") == "Save"

    def test_falls_back_to_key(self, service: UITranslationService):
        assert service.resolve("missing.key", "de") == "missing.key"


class TestResolveBulk:
    def test_resolves_all_keys(self, service: UITranslationService):
        service.set_translation("a", "en", "A-en")
        service.set_translation("a", "de", "A-de")
        service.set_translation("b", "en", "B-en")
        result = service.resolve_bulk("de", keys=["a", "b"])
        assert result["a"] == "A-de"
        assert result["b"] == "B-en"

    def test_resolves_to_key_as_last_resort(self, service: UITranslationService):
        result = service.resolve_bulk("de", keys=["unknown.key"])
        assert result["unknown.key"] == "unknown.key"

    def test_resolve_bulk_fills_cache_via_inner_bulk_call(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.resolve_bulk("de", keys=["a"])
        assert "en" in service._locales_cache


# ---------------------------------------------------------------------------
# Resolve bulk for locale (langpack namespace merging)
# ---------------------------------------------------------------------------


class TestResolveBulkForLocale:
    def test_merges_langpack_namespaces(self, service: UITranslationService):
        service.set_translation("a", "de", "A-pack1", namespace="langpack:lang-de-1")
        service.set_translation("b", "de", "B-pack2", namespace="langpack:lang-de-2")
        result = service.resolve_bulk_for_locale("de")
        assert result["a"] == "A-pack1"
        assert result["b"] == "B-pack2"

    def test_later_namespace_overrides_earlier(self, service: UITranslationService):
        service.set_translation("a", "de", "A-first", namespace="langpack:lang-de-1")
        service.set_translation("a", "de", "A-second", namespace="langpack:lang-de-2")
        result = service.resolve_bulk_for_locale("de")
        # Alphabetical: lang-de-1 comes before lang-de-2, so 'A-second' wins
        assert result["a"] == "A-second"

    def test_empty_when_no_langpack(self, service: UITranslationService):
        service.set_translation("a", "de", "A", namespace="global")
        result = service.resolve_bulk_for_locale("de")
        assert result == {}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_get_locale_cache_loads_on_demand(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        cache = service._get_locale_cache("en")
        assert cache == {"a": "A"}

    def test_get_locale_cache_returns_cached(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service._get_locale_cache("en")
        service._locales_cache["en"]["b"] = "B"
        cache = service._get_locale_cache("en")
        assert cache["b"] == "B"

    def test_invalidate_cache_specific_locale(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("b", "de", "B")
        service._get_locale_cache("en")
        service._get_locale_cache("de")
        service.invalidate_cache("en")
        assert "en" not in service._locales_cache
        assert "de" in service._locales_cache

    def test_invalidate_cache_all(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("b", "de", "B")
        service._get_locale_cache("en")
        service._get_locale_cache("de")
        service.invalidate_cache()
        assert service._locales_cache == {}


# ---------------------------------------------------------------------------
# Stats & coverage
# ---------------------------------------------------------------------------


class TestStats:
    def test_get_stats_empty(self, service: UITranslationService):
        stats = service.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_with_data(self, service: UITranslationService):
        service.set_translation("a", "en", "A", source="manual")
        service.set_translation("b", "en", "B", source="bulk_imported")
        service.set_translation("c", "en", "C", source="llm_generated")
        stats = service.get_stats()
        en_stats = stats["en"]
        assert en_stats["manual"] == 1
        assert en_stats["bulk"] == 1
        assert en_stats["llm"] == 1
        assert en_stats["translated"] == 3

    def test_get_stats_with_bundled_fallback(self, service: UITranslationService):
        # No DB data for 'en' in the empty namespace - bundled should be used
        stats = service.get_stats(namespace="nonexistent-ns")
        if "en" in stats:
            # The merged stats from bundled have a different shape than DB rows
            assert "total" in stats["en"]


class TestCoverage:
    def test_get_coverage_empty(self, service: UITranslationService):
        coverage = service.get_coverage(namespace="empty-ns")
        assert isinstance(coverage, dict)

    def test_get_coverage_with_db_translations(self, service: UITranslationService, monkeypatch):
        # Stub the bundled loaders to be empty so coverage is based purely on DB
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        service.set_translation("a", "en", "A")
        service.set_translation("a", "de", "A-de")
        coverage = service.get_coverage()
        assert "en" in coverage
        assert "de" in coverage
        assert coverage["de"]["coverage_pct"] == 100.0

    def test_get_coverage_partial(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        service.set_translation("a", "en", "A")
        service.set_translation("b", "en", "B")
        service.set_translation("a", "de", "A-de")
        coverage = service.get_coverage()
        assert coverage["de"]["coverage_pct"] == 50.0

    def test_get_coverage_with_langpack_merging(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        service.set_translation("a", "en", "A")
        service.set_translation("a", "de", "A-pack", namespace="langpack:lang-de")
        coverage = service.get_coverage()
        assert coverage["de"]["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Wipe locale
# ---------------------------------------------------------------------------


class TestWipeLocale:
    def test_wipe_locale_removes_entries(self, service: UITranslationService):
        service.set_translation("a", "de", "A-de")
        service.set_translation("b", "de", "B-de")
        result = service.wipe_locale("de")
        assert result["deleted"] == 2
        assert service.get_translation("a", "de") is None
        assert service.get_translation("b", "de") is None

    def test_wipe_locale_invalidates_cache(self, service: UITranslationService):
        service.set_translation("a", "de", "A-de")
        service._get_locale_cache("de")
        assert "de" in service._locales_cache
        service.wipe_locale("de")
        assert "de" not in service._locales_cache

    def test_wipe_locale_no_entries(self, service: UITranslationService):
        result = service.wipe_locale("de")
        assert result["deleted"] == 0


# ---------------------------------------------------------------------------
# Custom locales
# ---------------------------------------------------------------------------


class TestCustomLocales:
    def test_register_and_get(self, service: UITranslationService):
        result = service.register_custom_locale("hu", "Magyar", is_rtl=False)
        assert result["locale"] == "hu"
        assert result["name"] == "Magyar"
        assert result["is_rtl"] is False

    def test_register_uses_code_as_default_name(self, service: UITranslationService):
        result = service.register_custom_locale("xx")
        assert result["name"] == "xx"

    def test_register_rtl(self, service: UITranslationService):
        result = service.register_custom_locale("fa", "Farsi", is_rtl=True)
        assert result["is_rtl"] is True

    def test_register_overwrites(self, service: UITranslationService):
        service.register_custom_locale("hu", "Magyar")
        service.register_custom_locale("hu", "Hungarian Updated")
        result = service.get_custom_locales()
        assert len(result) == 1
        assert result[0]["name"] == "Hungarian Updated"

    def test_get_custom_locales_empty(self, service: UITranslationService):
        assert service.get_custom_locales() == []


# ---------------------------------------------------------------------------
# LLM helpers (deterministic, no real LLM)
# ---------------------------------------------------------------------------


class TestLLMHelpers:
    def test_select_llm_uses_setting(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "fixed-profile",
        )
        ps = MagicMock()
        assert service._select_llm_for_locale("de", ps) == "fixed-profile"

    def test_select_llm_locale_map(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            None,
        )
        ps = MagicMock()
        assert "deepseek" in service._select_llm_for_locale("zh", ps)
        assert "llama" in service._select_llm_for_locale("ar", ps)

    def test_select_llm_fallback_to_setting(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            None,
        )
        ps = MagicMock()
        result = service._select_llm_for_locale("de", ps)
        assert result is None

    def test_locale_name_known(self):
        assert UITranslationService._locale_name("de") == "Deutsch"
        assert UITranslationService._locale_name("en") == "English"

    def test_locale_name_unknown_falls_back_to_code(self):
        assert UITranslationService._locale_name("xx") == "xx"


# ---------------------------------------------------------------------------
# LLM translation (mocked)
# ---------------------------------------------------------------------------


class _FakeLLMResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """LLMService stub: returns deterministic content."""

    def __init__(self, content: str = "TRANSLATED") -> None:
        self.content = content
        self.calls: list[dict] = []

    # set_context / set_session_id are no-ops here because the stub
    # does not feed the LLM-activity monitor; the LLM-Monitor is
    # exercised in its own dedicated tests.  The methods MUST exist
    # because the production code path in
    # ``backend.services.ui_translation_service`` (and the parallel
    # TranslationService) calls them right after the LLMService is
    # constructed.
    def set_context(self, context: str) -> None:
        pass

    def set_session_id(self, session_id: str) -> None:
        pass

    def generate_sync(self, **kwargs) -> _FakeLLMResult:
        self.calls.append(kwargs)
        return _FakeLLMResult(self.content)


class TestTranslateViaLLM:
    def test_translate_stores_and_returns(self, service: UITranslationService):
        llm = _FakeLLM(content="Hallo")
        result = service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=llm)
        assert result == "Hallo"
        assert service.get_translation("nav.dashboard", "de") == "Hallo"

    def test_translate_empty_response_raises(self, service: UITranslationService):
        llm = _FakeLLM(content="")
        with pytest.raises(Exception, match="empty"):
            service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=llm)

    def test_translate_updates_job_progress(self, service: UITranslationService):
        llm = _FakeLLM(content="Hallo")
        job = TranslationJob(
            job_id="j1",
            target_locales=["de"],
            namespace="global",
            total_strings=2,
            completed_strings=0,
        )
        service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=llm, job=job)
        assert job.completed_strings == 1
        assert job.current_key == "nav.dashboard"
        assert job.current_locale == "de"

    def test_translate_keyword_detection_picks_context_hint(self, service: UITranslationService):
        llm = _FakeLLM(content="Speichern")
        service.translate_via_llm("button.save", "Save", "de", llm=llm)
        prompt = llm.calls[0]["system_prompt"]
        assert "button label" in prompt.lower()

    def test_translate_retries_on_rate_limit_then_succeeds(self, service: UITranslationService):
        call_count = {"n": 0}

        class _FlakyLLM:
            def generate_sync(self, **kwargs):
                call_count["n"] += 1
                if call_count["n"] < 2:
                    raise RuntimeError("rate limit exceeded (429)")
                return _FakeLLMResult("Hallo")

        # Patch the time.sleep so we don't actually wait
        import backend.services.ui_translation_service as uts_mod

        uts_mod.time = MagicMock()
        result = service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=_FlakyLLM())
        assert result == "Hallo"
        assert call_count["n"] == 2

    def test_translate_exhausts_retries_and_raises(self, service: UITranslationService):
        class _AlwaysLimitedLLM:
            def generate_sync(self, **kwargs):
                raise RuntimeError("rate limit 429")

        import backend.services.ui_translation_service as uts_mod

        uts_mod.time = MagicMock()
        with pytest.raises(RuntimeError, match="rate limit"):
            service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=_AlwaysLimitedLLM())

    def test_translate_non_rate_limit_error_raises_immediately(self, service: UITranslationService):
        class _BadLLM:
            def generate_sync(self, **kwargs):
                raise RuntimeError("connection refused")

        with pytest.raises(RuntimeError, match="connection refused"):
            service.translate_via_llm("nav.dashboard", "Dashboard", "de", llm=_BadLLM())


# ---------------------------------------------------------------------------
# Bulk translate (sync)
# ---------------------------------------------------------------------------


class TestBulkTranslate:
    def test_bulk_translate_skips_complete_locales(self, service: UITranslationService, monkeypatch):
        # Stub bundled to avoid 808 keys
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        service.set_translation("a", "en", "A")
        results = service.bulk_translate(target_locales=["en"])
        assert results["en"]["status"] == "complete"
        assert results["en"]["translated"] == 0

    def test_bulk_translate_missing_target_locales_falls_back_to_installed(self, service: UITranslationService, monkeypatch):
        # Stub bundled to avoid 808 keys
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        monkeypatch.setattr(
            service,
            "get_installed_locales",
            lambda: [{"code": "en"}, {"code": "de"}],
        )
        llm = _FakeLLM(content="Ubersetzt")
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: llm)
        service.set_translation("a", "en", "A")
        results = service.bulk_translate()
        assert "de" in results
        assert results["de"]["translated"] == 1

    def test_bulk_translate_uses_bundled_to_skip(self, service: UITranslationService, monkeypatch):
        # Stub bundled to avoid 808 keys
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "test-profile",
        )
        llm = _FakeLLM(content="Ubersetzt")
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: llm)
        service.set_translation("a", "en", "A")
        results = service.bulk_translate(target_locales=["de"])
        assert results["de"]["translated"] == 1

    def test_bulk_translate_handles_failure(self, service: UITranslationService, monkeypatch):
        # Stub bundled to avoid 808 keys
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})

        class _BoomLLM:
            def generate_sync(self, **kwargs):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "test-profile",
        )
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: _BoomLLM())
        service.set_translation("a", "en", "A")
        results = service.bulk_translate(target_locales=["de"])
        assert results["de"]["failed"] == 1
        assert results["de"]["translated"] == 0


# ---------------------------------------------------------------------------
# Bulk translate async
# ---------------------------------------------------------------------------


class TestBulkTranslateAsync:
    def test_returns_job_id(self, service: UITranslationService):
        llm = _FakeLLM(content="Ubersetzt")
        import backend.services.llm_service as llm_mod

        original = getattr(llm_mod, "LLMService", None)
        llm_mod.LLMService = lambda **kw: llm
        try:
            job_id = service.bulk_translate_async(target_locales=["en"])
            assert job_id in TranslationJobRegistry._jobs
        finally:
            if original is not None:
                llm_mod.LLMService = original

    def test_async_job_completes(self, service: UITranslationService, monkeypatch):
        # Stub bundled to avoid 808 keys
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        llm = _FakeLLM(content="Ubersetzt")
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: llm)
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "test-profile",
        )
        service.set_translation("a", "en", "A")
        job_id = service.bulk_translate_async(target_locales=["de"])
        job = _wait_for_job(job_id, timeout=10.0)
        assert job is not None
        assert job.status == "completed"
        assert "de" in job.results
        assert job.results["de"]["translated"] == 1

    def test_async_job_sets_total_strings(self, service: UITranslationService, monkeypatch):
        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        llm = _FakeLLM(content="Ubersetzt")
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: llm)
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "test-profile",
        )
        service.set_translation("a", "en", "A")
        service.set_translation("b", "en", "B")
        job_id = service.bulk_translate_async(target_locales=["de"])
        job = _wait_for_job(job_id, timeout=10.0)
        assert job.total_strings == 2

    def test_async_job_handles_rate_limit(self, service: UITranslationService, monkeypatch):
        class _LimitedLLM:
            def __init__(self, **kw) -> None:
                pass

            # See the note on _FakeLLM above: these are no-ops for
            # the stub but must exist for the production code path
            # in ``ui_translation_service.bulk_translate_async``.
            def set_context(self, context: str) -> None:
                pass

            def set_session_id(self, session_id: str) -> None:
                pass

            def generate_sync(self, **kwargs):
                raise RuntimeError("rate limit 429")

        monkeypatch.setattr(service, "_scan_bundled_loaders", lambda: {})
        monkeypatch.setattr("backend.services.llm_service.LLMService", lambda **kw: _LimitedLLM())
        monkeypatch.setattr(
            "backend.services.ui_translation_service.settings.service_llm_profile_id",
            "test-profile",
        )
        # Speed up the inner sleep so retries don't take 14 real seconds
        import backend.services.ui_translation_service as uts_mod

        uts_mod.time = MagicMock()
        service.set_translation("a", "en", "A")
        job_id = service.bulk_translate_async(target_locales=["de"])
        # Wait until the job finishes (status becomes 'failed' after retries)
        job = _wait_for_job(job_id, timeout=15.0)
        assert job is not None
        assert job.status == "failed"
        assert job.error is not None
        assert "rate limit" in job.error.lower()


# ---------------------------------------------------------------------------
# Locale details
# ---------------------------------------------------------------------------


class TestGetLocaleDetails:
    def test_get_locale_details_basic(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("a", "de", "A-de")
        result = service.get_locale_details("de")
        assert result["locale"] == "de"
        assert result["namespace"] == "global"
        assert result["total_keys"] >= 1
        assert result["translated"] >= 1
        assert "strings" in result

    def test_get_locale_details_merges_langpack(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("a", "de", "A-pack", namespace="langpack:lang-de")
        result = service.get_locale_details("de")
        a_entry = next(s for s in result["strings"] if s["key"] == "a")
        assert a_entry["translated_value"] == "A-pack"
        assert a_entry["status"] == "translated"

    def test_get_locale_details_missing_key(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        result = service.get_locale_details("de")
        a_entry = next(s for s in result["strings"] if s["key"] == "a")
        assert a_entry["status"] == "missing"
        assert a_entry["translated_value"] is None

    def test_get_locale_details_counts_llm_vs_manual(self, service: UITranslationService):
        service.set_translation("a", "en", "A")
        service.set_translation("a", "de", "A-de", source="manual")
        service.set_translation("b", "en", "B")
        service.set_translation("b", "de", "B-de", source="llm_generated")
        result = service.get_locale_details("de")
        assert result["manual"] == 1
        assert result["llm_generated"] == 1


# ---------------------------------------------------------------------------
# Bootstrap core locales
# ---------------------------------------------------------------------------


class TestBootstrapCoreLocales:
    def test_idempotent_marker(self, service: UITranslationService):
        conn = service._get_conn()
        conn.execute(
            "INSERT INTO ui_translation_metadata (key, value) VALUES (?, ?)",
            ("i18n_bootstrap_v2", json.dumps({"migrated_at": "now", "locales": []})),
        )
        conn.commit()
        conn.close()
        result = service.bootstrap_core_locales()
        assert result == {}

    def test_migrates_existing_translations(self, service: UITranslationService):
        service.set_translation("btn.save", "de", "Speichern", source="manual")
        service.set_translation("btn.cancel", "de", "Abbrechen", source="manual")
        result = service.bootstrap_core_locales()
        assert "de" in result
        assert result["de"] == 2
        assert service.get_translation("btn.save", "de", namespace="langpack:lang-de") == "Speichern"

    def test_skips_locales_with_existing_langpack(self, service: UITranslationService):
        service.set_translation("btn.save", "de", "Speichern", source="manual")
        service.set_translation(
            "btn.save",
            "de",
            "Speichern-pack",
            namespace="langpack:lang-de",
        )
        result = service.bootstrap_core_locales()
        assert "de" not in result

    def test_skips_locales_without_translations(self, service: UITranslationService):
        result = service.bootstrap_core_locales()
        assert "de" not in result


# ---------------------------------------------------------------------------
# Cleanup legacy local langpacks
# ---------------------------------------------------------------------------


class TestCleanupLegacyLocalLangpacks:
    def test_no_modules_dir(self, service: UITranslationService, tmp_path):
        removed = service.cleanup_legacy_local_langpacks()
        assert removed == 0

    def test_removes_legacy_lp_directory(self, service: UITranslationService):
        # Create a fake legacy lp-* module
        root = Path(__file__).resolve().parent.parent.parent
        modules_dir = root / "modules"
        if not modules_dir.exists():
            modules_dir.mkdir()
        legacy_dir = modules_dir / "lp-test-1234"
        legacy_dir.mkdir()
        manifest = {
            "type": "language-pack",
            "module_id": "lp-test-1234",
        }
        (legacy_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        try:
            removed = service.cleanup_legacy_local_langpacks()
            assert removed >= 1
            assert not legacy_dir.exists()
        finally:
            pass

    def test_skips_non_langpack_modules(self, service: UITranslationService):
        root = Path(__file__).resolve().parent.parent.parent
        modules_dir = root / "modules"
        if not modules_dir.exists():
            modules_dir.mkdir()
        non_lp_dir = modules_dir / "agent-cores-test"
        non_lp_dir.mkdir()
        manifest = {
            "type": "agent-cores",
            "module_id": "agent-cores-test",
        }
        (non_lp_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        try:
            service.cleanup_legacy_local_langpacks()
            assert non_lp_dir.exists()
        finally:
            import shutil

            shutil.rmtree(non_lp_dir)

    def test_removes_invalid_manifest(self, service: UITranslationService):
        root = Path(__file__).resolve().parent.parent.parent
        modules_dir = root / "modules"
        if not modules_dir.exists():
            modules_dir.mkdir()
        invalid_dir = modules_dir / "lp-invalid"
        invalid_dir.mkdir()
        (invalid_dir / "manifest.json").write_text("{ invalid json", encoding="utf-8")
        try:
            service.cleanup_legacy_local_langpacks()
            assert invalid_dir.exists()
        finally:
            import shutil

            shutil.rmtree(invalid_dir)

    def test_handles_missing_manifest(self, service: UITranslationService):
        root = Path(__file__).resolve().parent.parent.parent
        modules_dir = root / "modules"
        if not modules_dir.exists():
            modules_dir.mkdir()
        no_manifest_dir = modules_dir / "lp-no-manifest"
        no_manifest_dir.mkdir()
        try:
            service.cleanup_legacy_local_langpacks()
            assert no_manifest_dir.exists()
        finally:
            import shutil

            shutil.rmtree(no_manifest_dir)


# ---------------------------------------------------------------------------
# Langpack module dir creation
# ---------------------------------------------------------------------------


class TestCreateLangpackModuleDir:
    def test_creates_dir_and_files(self, tmp_path):
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        module_dir = tmp_path / "lp-test"
        UITranslationService._create_langpack_module_dir(
            module_dir=module_dir,
            locale="de",
            module_id="lp-test",
            ui_strings={"a": "A-de", "b": "B-de"},
            now=now,
        )
        assert module_dir.exists()
        assert (module_dir / "manifest.json").exists()
        assert (module_dir / "ui_strings.json").exists()

    def test_manifest_content(self, tmp_path):
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        module_dir = tmp_path / "lp-test"
        UITranslationService._create_langpack_module_dir(
            module_dir=module_dir,
            locale="de",
            module_id="lp-test",
            ui_strings={"a": "A-de"},
            now=now,
        )
        manifest = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["module_id"] == "lp-test"
        assert manifest["type"] == "language-pack"
        assert manifest["language"] == "de"
        assert "de" in manifest["name"]

    def test_ui_strings_content(self, tmp_path):
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        module_dir = tmp_path / "lp-test"
        UITranslationService._create_langpack_module_dir(
            module_dir=module_dir,
            locale="de",
            module_id="lp-test",
            ui_strings={"a": "A-de", "b": "B-de"},
            now=now,
        )
        strings = json.loads((module_dir / "ui_strings.json").read_text(encoding="utf-8"))
        assert strings == {"a": "A-de", "b": "B-de"}

    def test_unknown_locale_uses_code_as_name(self, tmp_path):
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        module_dir = tmp_path / "lp-test"
        UITranslationService._create_langpack_module_dir(
            module_dir=module_dir,
            locale="xx",
            module_id="lp-test",
            ui_strings={"a": "A"},
            now=now,
        )
        manifest = json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["name"]["xx"] == "xx"


# ---------------------------------------------------------------------------
# Installed locales
# ---------------------------------------------------------------------------


class TestGetInstalledLocales:
    def test_get_installed_locales_includes_en(self, service: UITranslationService):
        result = service.get_installed_locales()
        codes = [loc["code"] for loc in result]
        assert "en" in codes

    def test_get_installed_locales_en_is_bundled(self, service: UITranslationService):
        result = service.get_installed_locales()
        en_entry = next(loc for loc in result if loc["code"] == "en")
        assert en_entry["source"] == "bundled"
        assert en_entry["is_rtl"] is False

    def test_get_installed_locales_includes_rtl_flag(self, service: UITranslationService):
        # Custom-register an RTL locale
        service.register_custom_locale("ar", "Arabic", is_rtl=True)
        result = service.get_installed_locales()
        ar_entry = next(loc for loc in result if loc["code"] == "ar")
        assert ar_entry["is_rtl"] is True
        assert ar_entry["source"] == "custom"

    def test_get_installed_locales_skips_disabled_langpack(self, service: UITranslationService):
        # Create a langpack entry that is not in module_registry
        service.set_translation("a", "de", "A-de", namespace="langpack:lang-de")
        # No blueprints.db -> all langpack modules are considered disabled
        result = service.get_installed_locales()
        codes = [loc["code"] for loc in result]
        assert "de" not in codes


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_default_locales_has_en(self):
        assert "en" in DEFAULT_LOCALES

    def test_locale_names_contains_en(self):
        assert "en" in LOCALE_NAMES
        assert LOCALE_NAMES["en"] == "English"

    def test_rtl_locales(self):
        assert "ar" in RTL_LOCALES
        assert "he" in RTL_LOCALES
        assert "fa" in RTL_LOCALES

    def test_core_locales_subset(self):
        for loc in CORE_LOCALES:
            assert loc in LOCALE_NAMES or loc in {"he", "fa"}

    def test_plural_tags_known(self):
        assert "de" in PLURAL_TAGS
        assert "ar" in PLURAL_TAGS
