"""Tests for the Bundle Composer API router.

Covers all 8 endpoints under /api/v1/bundle-composer:
- GET  /components           — list available components
- POST /preview              — preview assembled prompt
- POST /bundles              — create a bundle
- GET  /bundles              — list bundles
- GET  /bundles/{id}         — get a bundle
- PUT  /bundles/{id}         — update a bundle
- POST /bundles/{id}/export  — export bundle
- POST /import               — import bundle from directory
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_blueprint_repository,
    get_debate_store,
    get_project_id,
    get_project_store,
    get_settings,
)
from backend.blueprints.repository import BlueprintRepository
from backend.core.config import Settings
from backend.main import create_app
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore

# ---------------------------------------------------------------------------
# Fake module data  (replaces module-filesystem scanning)
# ---------------------------------------------------------------------------

FAKE_AGENT_CORES = [
    {"id": "strategist-default", "name": "Default Strategist", "role": "strategist", "description": "Test strategist"},
    {"id": "critic-default", "name": "Default Critic", "role": "critic", "description": "Test critic"},
]

FAKE_ARG_PATTERNS = [
    {"id": "socratic", "name": "Socratic", "role": "strategist", "description": "Socratic method"},
    {"id": "hegelian", "name": "Hegelian", "role": "strategist", "description": "Thesis-antithesis-synthesis"},
]

FAKE_TONE_PROFILES = [
    {"id": "academic", "name": "Academic", "style": "academic", "description": "Scholarly tone"},
    {"id": "neutral", "name": "Neutral", "style": "neutral", "description": "Balanced tone"},
]

FAKE_PROMPT_MODIFIERS = [
    {
        "id": "concise",
        "name": "Concise",
        "content_preview": "Be concise and direct.",
        "description": "Short output modifier",
    },
    {
        "id": "detailed",
        "name": "Detailed",
        "content_preview": "Provide thorough detail.",
        "description": "Verbose output modifier",
    },
]


@pytest.fixture(autouse=True)
def _mock_module_functions(monkeypatch: pytest.MonkeyPatch):
    """Replace all module-filesystem scanning functions with fake data."""
    import backend.blueprints.composer as bp_composer
    import backend.services.composer_service as cs
    import backend.services.module_profile_sync as mps

    monkeypatch.setattr(mps, "get_agent_personas_from_modules", lambda **kw: FAKE_AGENT_CORES)
    monkeypatch.setattr(mps, "get_tone_profiles_from_modules", lambda **kw: FAKE_TONE_PROFILES)
    monkeypatch.setattr(mps, "get_prompt_modifiers_from_modules", lambda **kw: FAKE_PROMPT_MODIFIERS)
    monkeypatch.setattr(mps, "seed_prompt_modifiers_to_db", lambda: None)

    # Also patch the listers in composer.py so they don't reach module filesystem
    monkeypatch.setattr(bp_composer, "get_tone_profiles_from_modules", lambda **kw: FAKE_TONE_PROFILES)
    monkeypatch.setattr(bp_composer, "get_prompt_modifiers_from_modules", lambda **kw: FAKE_PROMPT_MODIFIERS)
    monkeypatch.setattr(bp_composer, "seed_prompt_modifiers_to_db", lambda: None)

    # Mock the argumentation patterns listing (internally uses _get_enabled_modules)
    monkeypatch.setattr(mps, "get_argumentation_patterns_from_modules", lambda **kw: [p["id"] for p in FAKE_ARG_PATTERNS])

    # Make ComposerService.list_argumentation_patterns return fake data
    monkeypatch.setattr(cs.ComposerService, "list_argumentation_patterns", staticmethod(lambda: FAKE_ARG_PATTERNS))
    monkeypatch.setattr(cs.ComposerService, "list_agent_cores", staticmethod(lambda: FAKE_AGENT_CORES))
    monkeypatch.setattr(cs.ComposerService, "list_tone_profiles", staticmethod(lambda: FAKE_TONE_PROFILES))

    # Make compose() return a predictable string so we don't need real module files
    monkeypatch.setattr(
        cs.ComposerService,
        "compose",
        lambda self, composition: f"# Composed prompt\n\nAgent: {composition.agent_core_id}\nPattern: {composition.argumentation_pattern_id}",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def blueprint_repo(tmp_path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
    )


@pytest.fixture()
def audit_service(tmp_path) -> AuditService:
    return AuditService(db_path=tmp_path / "test_audit.db")


@pytest.fixture()
def debate_store(tmp_path) -> DebateStore:
    return DebateStore(data_dir=tmp_path / "test_debates")


@pytest.fixture()
def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(base_dir=tmp_path / "test_projects")


@pytest.fixture()
def default_project(project_store):
    project = project_store.get_or_create_default()
    return project.id


@pytest.fixture()
def app(settings, audit_service, debate_store, project_store, default_project, blueprint_repo):
    get_project_store.cache_clear()
    get_blueprint_repository.cache_clear()
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.dependency_overrides[get_project_id] = lambda: default_project
    application.dependency_overrides[get_blueprint_repository] = lambda: blueprint_repo
    yield application
    get_blueprint_repository.cache_clear()


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def sample_llm_profile_id(client: TestClient) -> str:
    """Seed an LLM profile and return its ID."""
    resp = client.post(
        "/api/v1/blueprints/llm-profiles",
        json={"id": "test-llm", "name": "Test LLM", "provider": "openrouter", "model": "test/model"},
    )
    assert resp.status_code == 201
    return "test-llm"


# ---------------------------------------------------------------------------
# GET /components
# ---------------------------------------------------------------------------


class TestListComponents:
    def test_returns_all_categories(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/components")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_cores" in data
        assert "argumentation_patterns" in data
        assert "tone_profiles" in data
        assert "prompt_modifiers" in data
        assert "llm_profiles" in data

    def test_agent_cores_contains_fake_data(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/components")
        cores = resp.json()["agent_cores"]
        ids = {c["id"] for c in cores}
        assert "strategist-default" in ids
        assert "critic-default" in ids

    def test_argumentation_patterns_contains_fake_data(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/components")
        patterns = resp.json()["argumentation_patterns"]
        ids = {p["id"] for p in patterns}
        assert "socratic" in ids
        assert "hegelian" in ids

    def test_tone_profiles_contains_fake_data(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/components")
        profiles = resp.json()["tone_profiles"]
        ids = {p["id"] for p in profiles}
        assert "academic" in ids
        assert "neutral" in ids


# ---------------------------------------------------------------------------
# POST /preview
# ---------------------------------------------------------------------------


class TestPreview:
    def test_preview_with_all_fields(self, client: TestClient):
        resp = client.post(
            "/api/v1/bundle-composer/preview",
            json={
                "agent_core_id": "strategist-default",
                "argumentation_pattern_id": "socratic",
                "tone_profile_id": "academic",
                "prompt_modifier_id": "concise",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "prompt" in data
        assert "strategist-default" in data["prompt"]
        assert "socratic" in data["prompt"]

    def test_preview_with_partial_fields(self, client: TestClient):
        resp = client.post(
            "/api/v1/bundle-composer/preview",
            json={"agent_core_id": "strategist-default"},
        )
        assert resp.status_code == 200
        assert "prompt" in resp.json()

    def test_preview_with_empty_body(self, client: TestClient):
        resp = client.post(
            "/api/v1/bundle-composer/preview",
            json={},
        )
        assert resp.status_code == 200
        assert "prompt" in resp.json()


# ---------------------------------------------------------------------------
# POST /bundles (create)
# ---------------------------------------------------------------------------


class TestCreateBundle:
    def test_create_minimal(self, client: TestClient, sample_llm_profile_id: str):
        resp = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Test Bundle",
                "composition": {
                    "agent_core_id": "strategist-default",
                    "argumentation_pattern_id": "socratic",
                    "prompt_modifier_id": "concise",
                },
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Bundle"
        assert data["composition"]["agent_core_id"] == "strategist-default"
        assert data["role_type_id"] == "strategist"

    def test_create_with_all_fields(self, client: TestClient, sample_llm_profile_id: str):
        resp = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Full Bundle",
                "description": "A bundle with all options",
                "composition": {
                    "agent_core_id": "critic-default",
                    "argumentation_pattern_id": "hegelian",
                    "prompt_modifier_id": "detailed",
                },
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Full Bundle"
        assert data["description"] == "A bundle with all options"
        assert data["composition"]["argumentation_pattern_id"] == "hegelian"

    def test_create_missing_name(self, client: TestClient, sample_llm_profile_id: str):
        resp = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        assert resp.status_code == 422

    def test_create_missing_llm_profile(self, client: TestClient):
        resp = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "No LLM",
                "composition": {"agent_core_id": "strategist-default"},
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /bundles and GET /bundles/{id}
# ---------------------------------------------------------------------------


class TestListBundles:
    def test_list_empty(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/bundles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client: TestClient, sample_llm_profile_id: str):
        client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Bundle A",
                "composition": {"agent_core_id": "strategist-default", "argumentation_pattern_id": "socratic"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        resp = client.get("/api/v1/bundle-composer/bundles")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Bundle A"


class TestGetBundle:
    def test_get_existing(self, client: TestClient, sample_llm_profile_id: str):
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Get Me",
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        bundle_id = create.json()["id"]

        resp = client.get(f"/api/v1/bundle-composer/bundles/{bundle_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_get_not_found(self, client: TestClient):
        resp = client.get("/api/v1/bundle-composer/bundles/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PUT /bundles/{id}
# ---------------------------------------------------------------------------


class TestUpdateBundle:
    def test_update_name_and_composition(self, client: TestClient, sample_llm_profile_id: str):
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Original",
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        bundle_id = create.json()["id"]

        resp = client.put(
            f"/api/v1/bundle-composer/bundles/{bundle_id}",
            json={
                "name": "Updated",
                "composition": {"agent_core_id": "critic-default", "argumentation_pattern_id": "hegelian"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["composition"]["agent_core_id"] == "critic-default"

    def test_update_not_found(self, client: TestClient):
        resp = client.put(
            "/api/v1/bundle-composer/bundles/nonexistent",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /bundles/{id}/export
# ---------------------------------------------------------------------------


class TestExportBundle:
    def test_export_as_dict(self, client: TestClient, sample_llm_profile_id: str):
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Exportable",
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        bundle_id = create.json()["id"]

        resp = client.post(f"/api/v1/bundle-composer/bundles/{bundle_id}/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "manifest" in data
        assert "profile" in data
        assert data["manifest"]["module_id"] == bundle_id

    def test_export_to_directory(self, client: TestClient, sample_llm_profile_id: str):
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Dir Export",
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        bundle_id = create.json()["id"]

        resp = client.post(f"/api/v1/bundle-composer/bundles/{bundle_id}/export?to_directory=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        export_dir = Path(data["path"])
        assert export_dir.is_dir()
        assert (export_dir / "manifest.json").exists()
        assert (export_dir / "profile.json").exists()

    def test_export_not_found(self, client: TestClient):
        resp = client.post("/api/v1/bundle-composer/bundles/nonexistent/export")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /import
# ---------------------------------------------------------------------------


class TestImportBundle:
    def test_import_from_directory(self, client: TestClient, sample_llm_profile_id: str, tmp_path):
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "To Import",
                "composition": {"agent_core_id": "strategist-default"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        bundle_id = create.json()["id"]

        client.post(f"/api/v1/bundle-composer/bundles/{bundle_id}/export?to_directory=true")

        resp = client.post(
            "/api/v1/bundle-composer/import",
            json={"module_id": bundle_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "To Import"

    def test_import_not_found(self, client: TestClient):
        resp = client.post(
            "/api/v1/bundle-composer/import",
            json={"module_id": "nonexistent-module"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# End-to-end: create → get → update → export → import roundtrip
# ---------------------------------------------------------------------------


class TestBundleRoundtrip:
    def test_full_roundtrip(self, client: TestClient, sample_llm_profile_id: str):
        # 1. Create
        create = client.post(
            "/api/v1/bundle-composer/bundles",
            json={
                "name": "Roundtrip",
                "composition": {"agent_core_id": "strategist-default", "argumentation_pattern_id": "socratic"},
                "llm_profile_id": sample_llm_profile_id,
            },
        )
        assert create.status_code == 201
        bundle_id = create.json()["id"]

        # 2. Get
        get = client.get(f"/api/v1/bundle-composer/bundles/{bundle_id}")
        assert get.status_code == 200
        assert get.json()["name"] == "Roundtrip"

        # 3. Update
        update = client.put(
            f"/api/v1/bundle-composer/bundles/{bundle_id}",
            json={"name": "Roundtrip Updated", "description": "After edit"},
        )
        assert update.status_code == 200
        assert update.json()["name"] == "Roundtrip Updated"

        # 4. Export to directory
        export = client.post(f"/api/v1/bundle-composer/bundles/{bundle_id}/export?to_directory=true")
        assert export.status_code == 200

        # 5. List bundles includes it
        lst = client.get("/api/v1/bundle-composer/bundles")
        assert lst.status_code == 200
        names = [b["name"] for b in lst.json()]
        assert "Roundtrip Updated" in names
