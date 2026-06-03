"""Unit-Tests für den UITranslationService (Plan 20)."""
import pytest
from pathlib import Path

from backend.services.ui_translation_service import (
    UITranslationService, DEFAULT_LOCALES, CORE_LOCALES, RTL_LOCALES, LOCALE_NAMES, PLURAL_TAGS, get_plural_tags,
)


@pytest.fixture
def svc(tmp_path):
    """Isolated UITranslationService with temp database."""
    db = tmp_path / "test_i18n.db"
    yield UITranslationService(db_path=str(db))
    if db.exists():
        db.unlink()


class TestCRUD:
    def test_set_and_get(self, svc):
        svc.set_translation("nav.dashboard", "de", "Übersicht")
        assert svc.get_translation("nav.dashboard", "de") == "Übersicht"

    def test_get_missing_key(self, svc):
        assert svc.get_translation("nonexistent.key", "de") is None

    def test_update_translation(self, svc):
        svc.set_translation("key", "de", "Alt")
        svc.set_translation("key", "de", "Neu")
        assert svc.get_translation("key", "de") == "Neu"

    def test_delete_translation(self, svc):
        svc.set_translation("key", "de", "Wert")
        assert svc.delete_translation("key", "de") is True
        assert svc.get_translation("key", "de") is None

    def test_delete_missing_returns_false(self, svc):
        assert svc.delete_translation("nonexistent", "de") is False


class TestFallback:
    def test_fallback_to_english(self, svc):
        svc.set_translation("key", "en", "Hello")
        # German not set → fallback to en
        assert svc.resolve("key", "de") == "Hello"

    def test_fallback_to_key(self, svc):
        # Neither locale nor en has the key
        assert svc.resolve("missing.key", "fr") == "missing.key"

    def test_fallback_chain_order(self, svc):
        svc.set_translation("key", "en", "EN Value")
        # French not set, should fall back directly to English (no more DE middle step)
        result = svc.resolve("key", "fr")
        assert result == "EN Value"

    def test_existing_locale_returns_directly(self, svc):
        svc.set_translation("key", "fr", "Bonjour")
        svc.set_translation("key", "en", "Hello")
        assert svc.resolve("key", "fr") == "Bonjour"


class TestBulkResolve:
    def test_bulk_resolve_all_found(self, svc):
        svc.set_translation("k1", "fr", "Un")
        svc.set_translation("k2", "fr", "Deux")
        result = svc.resolve_bulk("fr", keys=["k1", "k2"])
        assert result == {"k1": "Un", "k2": "Deux"}

    def test_bulk_resolve_with_missing(self, svc):
        svc.set_translation("k1", "fr", "Un")
        svc.set_translation("k2", "en", "Two")
        result = svc.resolve_bulk("fr", keys=["k1", "k2", "k3"])
        assert result["k1"] == "Un"
        assert result["k3"] == "k3"

    def test_bulk_empty_keys(self, svc):
        result = svc.resolve_bulk("de", keys=[])
        assert result == {}


class TestNamespace:
    def test_isolation(self, svc):
        svc.set_translation("key", "de", "Global", namespace="global")
        svc.set_translation("key", "de", "Admin", namespace="admin")
        assert svc.get_translation("key", "de", "global") == "Global"
        assert svc.get_translation("key", "de", "admin") == "Admin"


class TestBulkImport:
    def test_bulk_import(self, svc):
        count = svc.bulk_import({
            "de": {"k1": "Eins", "k2": "Zwei"},
            "fr": {"k1": "Un", "k2": "Deux"},
        })
        assert count == 4
        assert svc.get_translation("k1", "de") == "Eins"
        assert svc.get_translation("k2", "fr") == "Deux"


class TestCache:
    def test_cache_invalidation(self, svc):
        svc.set_translation("key", "de", "Alt")
        # Populate cache via bulk load
        svc.get_translations_bulk("de", keys=["key"])
        assert "de" in svc._locales_cache
        # Update and invalidate
        svc.set_translation("key", "de", "Neu")
        assert svc._locales_cache.get("de") is None

    def test_invalidate_all(self, svc):
        svc.set_translation("k1", "de", "Wert")
        svc.resolve("k1", "de")
        svc.invalidate_cache()
        assert len(svc._locales_cache) == 0


class TestStats:
    def test_stats_empty(self, svc):
        stats = svc.get_stats()
        assert isinstance(stats, dict)

    def test_stats_after_import(self, svc):
        svc.bulk_import({
            "de": {"k1": "Eins", "k2": "Zwei"},
            "en": {"k1": "One", "k2": "Two"},
        })
        stats = svc.get_stats()
        assert "de" in stats
        assert "en" in stats


class TestCoverage:
    def test_coverage_report(self, svc):
        svc.bulk_import({
            "en": {"k1": "One", "k2": "Two"},
            "de": {"k1": "Eins", "k2": "Zwei"},
        })
        # Register de in langpack namespace so it's discovered
        svc.bulk_import({"de": {"k1": "Eins", "k2": "Zwei"}}, namespace="langpack:lang-de")
        coverage = svc.get_coverage()
        assert "en" in coverage
        assert "de" in coverage


class TestConstants:
    def test_default_locales(self):
        """Only English is bundled as a default locale."""
        assert DEFAULT_LOCALES == ["en"]

    def test_core_locales(self):
        """Core locales are the non-English languages that were previously bundled."""
        assert "de" in CORE_LOCALES
        assert "fr" in CORE_LOCALES
        assert "en" not in CORE_LOCALES
        assert len(CORE_LOCALES) == 13

    def test_rtl_locales(self):
        assert "ar" in RTL_LOCALES
        assert "he" in RTL_LOCALES
        assert "de" not in RTL_LOCALES

    def test_locale_names(self):
        assert LOCALE_NAMES["de"] == "Deutsch"
        assert LOCALE_NAMES["en"] == "English"

    def test_plural_tags(self):
        """PLURAL_TAGS is still available as metadata in backend."""
        assert "one" in PLURAL_TAGS["de"]
        assert "other" in PLURAL_TAGS["de"]

    def test_get_plural_tags_fallback(self):
        """get_plural_tags returns fallback for unknown locales."""
        assert get_plural_tags("xx") == ["one", "other"]
        assert get_plural_tags("de") == ["one", "other"]
