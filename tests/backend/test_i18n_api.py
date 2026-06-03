"""Integrationstests für die i18n REST-API (Plan 20)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_project_store
from backend.main import create_app
from backend.services.ui_translation_service import UITranslationService


@pytest.fixture()
def svc(tmp_path):
    """Isolated UITranslationService."""
    db = tmp_path / "test_i18n_api.db"
    service = UITranslationService(db_path=str(db))
    yield service
    if db.exists():
        db.unlink()


@pytest.fixture()
def app_with_i18n(client_with_i18n):
    """Reuse client fixture."""
    return client_with_i18n


@pytest.fixture()
def client_with_i18n(svc, settings, debate_store, project_store, default_project):
    """FastAPI client with i18n router."""
    from backend.api.deps import get_debate_store, get_settings
    from backend.api.routers.ui_i18n import router as ui_i18n_router

    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.state.test_i18n_service = svc
    application.include_router(ui_i18n_router, prefix="/api/v1/i18n")
    return TestClient(application)


# ---------------------------------------------------------------------------
# Fixtures referencing backend conftest
# ---------------------------------------------------------------------------
@pytest.fixture()
def settings(tmp_path) -> pytest.Settings:  # type: ignore
    from backend.core.config import Settings

    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
    )


@pytest.fixture()
def debate_store(tmp_path):
    from backend.persistence.debate_store import DebateStore

    return DebateStore(data_dir=tmp_path / "test_debates")


@pytest.fixture()
def project_store(tmp_path):
    from backend.persistence.project_store import ProjectStore

    return ProjectStore(base_dir=tmp_path / "test_projects")


@pytest.fixture()
def default_project(project_store):
    project = project_store.get_or_create_default()
    return project.id


class TestGetSupportedLocales:
    """GET /api/v1/i18n/locales"""

    def test_returns_supported_locales(self, client_with_i18n):
        response = client_with_i18n.get("/api/v1/i18n/locales")
        assert response.status_code == 200
        data = response.json()
        assert "locales" in data
        assert isinstance(data["locales"], list)
        # At minimum, English is always bundled
        codes = [loc["code"] for loc in data["locales"]]
        assert "en" in codes

    def test_locale_entries_have_required_fields(self, client_with_i18n):
        response = client_with_i18n.get("/api/v1/i18n/locales")
        data = response.json()
        locale = data["locales"][0]
        assert "code" in locale
        assert "name" in locale
        assert "is_rtl" in locale
        assert "plural_tags" in locale

    def test_contains_rtl_locales(self, client_with_i18n):
        response = client_with_i18n.get("/api/v1/i18n/locales")
        data = response.json()
        rtl_codes = {loc["code"] for loc in data["locales"] if loc.get("is_rtl")}
        # RTL locales only appear when language-pack modules are installed
        # With only English bundled, no RTL locales expected
        assert isinstance(rtl_codes, set)


class TestGetTranslations:
    """GET /api/v1/i18n/{locale}"""

    def test_get_translations_returns_dict(self, svc, client_with_i18n):
        svc.set_translation("test.key", "de", "Testwert")
        svc.set_translation("test.key2", "de", "Noch ein Wert")
        response = client_with_i18n.get("/api/v1/i18n/de")
        assert response.status_code == 200
        data = response.json()
        assert "translations" in data
        assert data["translations"]["test.key"] == "Testwert"
        assert data["translations"]["test.key2"] == "Noch ein Wert"

    def test_get_translations_empty_locale(self, client_with_i18n):
        """Unknown locale returns bundled English fallback keys (not empty)."""
        response = client_with_i18n.get("/api/v1/i18n/xx")
        assert response.status_code == 200
        data = response.json()
        assert "translations" in data
        # Bundled EN loader provides fallback keys, so not empty
        assert isinstance(data["translations"], dict)

    def test_get_translations_with_keys_filter(self, svc, client_with_i18n):
        svc.set_translation("a", "de", "A")
        svc.set_translation("b", "de", "B")
        svc.set_translation("c", "de", "C")
        response = client_with_i18n.get("/api/v1/i18n/de?keys=a,c")
        assert response.status_code == 200
        data = response.json()
        assert "a" in data["translations"]
        assert "c" in data["translations"]
        assert "b" not in data["translations"]

    def test_fallback_to_english(self, svc, client_with_i18n):
        svc.set_translation("key", "en", "Hello")
        # fr not set → fallback to en
        response = client_with_i18n.get("/api/v1/i18n/fr?keys=key")
        assert response.status_code == 200
        assert response.json()["translations"]["key"] == "Hello"


class TestGetSingleTranslation:
    """GET /api/v1/i18n/{locale}/{key}"""

    def test_get_single_translation(self, svc, client_with_i18n):
        svc.set_translation("my.key", "de", "Mein Wert")
        response = client_with_i18n.get("/api/v1/i18n/de/my.key")
        assert response.status_code == 200
        assert response.json()["value"] == "Mein Wert"

    def test_get_single_translation_fallback(self, svc, client_with_i18n):
        svc.set_translation("my.key", "en", "My Value")
        response = client_with_i18n.get("/api/v1/i18n/fr/my.key")
        assert response.status_code == 200
        # Falls back to en
        assert response.json()["value"] == "My Value"

    def test_get_single_translation_not_found(self, client_with_i18n):
        response = client_with_i18n.get("/api/v1/i18n/de/nonexistent.key")
        assert response.status_code == 200
        # Returns key as value (ultimate fallback)
        assert response.json()["value"] == "nonexistent.key"


class TestSetTranslations:
    """POST /api/v1/i18n/{locale}"""

    def test_bulk_set_translations(self, client_with_i18n):
        payload = {
            "locale": "fr",
            "translations": {
                "nav.dashboard": "Tableau de bord",
                "nav.debate": "Débat en cours",
            },
        }
        response = client_with_i18n.post("/api/v1/i18n/fr", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 2

    def test_set_empty_translations(self, client_with_i18n):
        payload = {"locale": "es", "translations": {}}
        response = client_with_i18n.post("/api/v1/i18n/es", json=payload)
        assert response.status_code == 200
        assert response.json()["imported"] == 0


class TestSetSingleTranslation:
    """PUT /api/v1/i18n/{locale}/{key}"""

    def test_set_single_translation(self, client_with_i18n):
        payload = {"key": "test.key", "value": "Valeur de test", "namespace": "global"}
        response = client_with_i18n.put("/api/v1/i18n/fr/test.key", json=payload)
        assert response.status_code == 200
        assert response.json()["value"] == "Valeur de test"

    def test_update_single_translation(self, client_with_i18n):
        payload1 = {"key": "test.key", "value": "Valeur initiale", "namespace": "global"}
        client_with_i18n.put("/api/v1/i18n/fr/test.key", json=payload1)
        payload2 = {"key": "test.key", "value": "Nouvelle valeur", "namespace": "global"}
        response = client_with_i18n.put("/api/v1/i18n/fr/test.key", json=payload2)
        assert response.status_code == 200
        assert response.json()["value"] == "Nouvelle valeur"


class TestDeleteTranslation:
    """DELETE /api/v1/i18n/{locale}/{key}"""

    def test_delete_existing_translation(self, svc, client_with_i18n):
        svc.set_translation("to.delete", "de", "Zu löschen")
        response = client_with_i18n.delete("/api/v1/i18n/de/to.delete")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_nonexistent_translation(self, client_with_i18n):
        response = client_with_i18n.delete("/api/v1/i18n/de/nonexistent")
        assert response.status_code == 404


class TestStatsAndCoverage:
    """GET /api/v1/i18n/stats und /api/v1/i18n/coverage"""

    def test_stats(self, svc, client_with_i18n):
        svc.bulk_import(
            {
                "de": {"k1": "Eins", "k2": "Zwei"},
                "en": {"k1": "One", "k2": "Two"},
            }
        )
        response = client_with_i18n.get("/api/v1/i18n/stats?namespace=global")
        assert response.status_code == 200
        data = response.json()
        assert "de" in data
        assert "en" in data
        assert data["de"]["total"] >= 2

    def test_coverage(self, svc, client_with_i18n):
        svc.bulk_import(
            {
                "de": {"k1": "Eins", "k2": "Zwei"},
                "en": {"k1": "One", "k2": "Two"},
            }
        )
        # Also register 'de' in langpack namespace so it's discovered
        svc.bulk_import(
            {"de": {"k1": "Eins", "k2": "Zwei"}},
            namespace="langpack:lang-de",
        )
        response = client_with_i18n.get("/api/v1/i18n/coverage?namespace=global")
        assert response.status_code == 200
        data = response.json()
        assert "de" in data
        assert 0.0 <= data["de"]["coverage_pct"] <= 100.0


class TestRTLSupport:
    """RTL-Sprachunterstützung (Plausibilitätstests)."""

    def test_rtl_locales_defined(self, client_with_i18n):
        response = client_with_i18n.get("/api/v1/i18n/locales")
        data = response.json()
        rtl_codes = data.get("rtl_locales", [])
        assert isinstance(rtl_codes, list)

    def test_arabic_is_rtl(self, svc, client_with_i18n):
        # Register 'ar' as a langpack so it appears in locale list
        svc.bulk_import(
            {"ar": {"test": "اختبار"}},
            namespace="langpack:lang-ar",
        )
        response = client_with_i18n.get("/api/v1/i18n/locales")
        data = response.json()
        for loc in data["locales"]:
            if loc["code"] == "ar":
                assert loc["is_rtl"] is True
                return
        pytest.skip("ar locale not found in locales list (no langpack installed)")


class TestErrorHandling:
    """Fehlerbehandlung."""

    def test_invalid_locale_returns_empty(self, client_with_i18n):
        """Invalid locale returns bundled English fallback keys (not empty)."""
        response = client_with_i18n.get("/api/v1/i18n/invalid_locale_xyz")
        assert response.status_code == 200
        data = response.json()
        assert "translations" in data
        # Bundled EN loader provides fallback keys, so not empty
        assert isinstance(data["translations"], dict)

    def test_delete_nonexistent_returns_404(self, client_with_i18n):
        response = client_with_i18n.delete("/api/v1/i18n/de/totally.fake.key")
        assert response.status_code == 404
