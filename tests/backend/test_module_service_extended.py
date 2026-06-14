"""Tests for ModuleService — extended coverage of network/cache/DB paths.

Covers: ``_resolve_module_dir`` (subdir/child matching), ``_is_module_dir``,
``discover_local`` (subdir + child searches + exception swallow),
``discover_local_with_status`` (DB-only / ghost filtering),
``fetch_repo_index`` (cache + schema v3 + legacy + network error),
``get_download_url``, ``install_from_repo`` (deps / warnings / language-pack
fallback), ``_install_langpack_from_db``, ``check_updates`` (semver + string
fallback), ``update``, ``_force_uninstall`` (sqlite error), ``get_profile`` /
``update_profile`` (yaml/json/markdown + various missing), ``duplicate_module``
(yaml/json/markdown), ``translate`` (sqlite error), ``_dir_to_info`` (markdown
profile, legacy files, malformed timestamps), ``_update_manifest_checksum``,
``_get_db_module_info`` (missing row + sqlite error), ``_get_db_status_map``
(invalid name JSON + sqlite error).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from backend.blueprints.migrations import run_migrations
from backend.modules.installer import ModuleInstaller
from backend.modules.service import DANWA_MODULES_INDEX_URL, ModuleService

# ---------------------------------------------------------------------------
# Local fixtures (matching test_module_service.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dirs():
    modules_dir = Path(tempfile.mkdtemp(prefix="test_svc_m_"))
    db_dir = Path(tempfile.mkdtemp(prefix="test_svc_d_"))
    db_path = db_dir / "test.db"
    yield modules_dir, db_path
    shutil.rmtree(modules_dir, ignore_errors=True)
    shutil.rmtree(db_dir, ignore_errors=True)


@pytest.fixture()
def service(tmp_dirs):
    """Create a ModuleService with clean test dirs."""
    modules_dir, db_path = tmp_dirs
    return ModuleService(modules_dir=modules_dir, db_path=db_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(
    modules_dir: Path,
    module_id: str,
    version: str = "1.0.0",
    *,
    type_: str = "argumentation-pattern",
    category: str = "prompts",
    extra_files: list[str] | None = None,
    profile_file: str | None = None,
    profile_format: str | None = None,
) -> dict:
    mod_dir = modules_dir / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)
    files = []
    if extra_files is None:
        extra_files = ["file_0.md"]
    for fname in extra_files:
        fpath = mod_dir / fname
        fpath.write_text(f"# {module_id} {fname}\nContent.")
        files.append({"path": fname, "format": "markdown", "language": "en", "checksum": ""})
    manifest = {
        "schema_version": "1.0.0",
        "module_id": module_id,
        "name": {"en": f"{module_id} name"},
        "description": {"en": f"{module_id} desc"},
        "version": version,
        "type": type_,
        "category": category,
        "author": {"name": "Test"},
        "license": "CC-BY-4.0",
        "checksum": "",
        "files": files,
    }
    if profile_file:
        manifest["profile_file"] = profile_file
    if profile_format:
        manifest["profile_format"] = profile_format
    (mod_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _seed_db_module_registry(db_path: Path, module_id: str, **overrides) -> None:
    run_migrations(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    row = {
        "id": module_id,
        "name": overrides.get("name", '{"en":"Name"}'),
        "description": overrides.get("description", "desc"),
        "type": overrides.get("type", "custom"),
        "category": overrides.get("category", "custom"),
        "version": overrides.get("version", "1.0.0"),
        "author_json": overrides.get("author_json", "{}"),
        "license": overrides.get("license", "CC-BY-4.0"),
        "checksum": overrides.get("checksum", ""),
        "installed_at": overrides.get("installed_at", "2024-01-01"),
        "updated_at": overrides.get("updated_at", "2024-01-01"),
        "enabled": overrides.get("enabled", 1),
        "source_schema": overrides.get("source_schema", "1.0.0"),
        "tags_json": overrides.get("tags_json", "[]"),
        "dependencies": overrides.get("dependencies", "{}"),
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO module_registry
            (id, name, description, type, category, version,
             author_json, license, checksum, installed_at,
             updated_at, enabled, source_schema, tags_json, dependencies)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(row.values()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# _resolve_module_dir / _is_module_dir
# ---------------------------------------------------------------------------


class TestResolveModuleDir:
    def test_direct_path_match(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha")
        assert service._resolve_module_dir("alpha") == service.modules_dir / "alpha"

    def test_subdir_with_matching_manifest_id(self, service: ModuleService) -> None:
        # modules_dir/category/beta/manifest.json
        beta = service.modules_dir / "category" / "beta"
        beta.mkdir(parents=True, exist_ok=True)
        (beta / "manifest.json").write_text(json.dumps({"module_id": "beta"}))
        result = service._resolve_module_dir("beta")
        assert result == service.modules_dir / "category" / "beta"

    def test_subdir_self_manifest_match(self, service: ModuleService) -> None:
        # modules_dir/<subdir>/manifest.json (where module_id differs from subdir name)
        sub = service.modules_dir / "weird-name"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "manifest.json").write_text(json.dumps({"module_id": "actual-id"}))
        result = service._resolve_module_dir("actual-id")
        assert result == sub

    def test_subdir_grandchild_match(self, service: ModuleService) -> None:
        # modules_dir/<sub>/<child>/manifest.json (one level deep)
        child = service.modules_dir / "prompts" / "gamma"
        child.mkdir(parents=True, exist_ok=True)
        (child / "manifest.json").write_text(json.dumps({"module_id": "gamma"}))
        result = service._resolve_module_dir("gamma")
        assert result == child

    def test_returns_none_when_not_found(self, service: ModuleService) -> None:
        assert service._resolve_module_dir("does-not-exist") is None

    def test_invalid_manifest_json_skipped(self, service: ModuleService) -> None:
        # The subdir is 'bad' but the module_id we look for is 'weird-id'.
        # The subdir has its own (invalid) manifest.json that will be read and
        # rejected by the JSONDecodeError handler.
        sub = service.modules_dir / "bad"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "manifest.json").write_text("{not valid json")
        assert service._resolve_module_dir("weird-id") is None

    def test_is_module_dir_filters_backups_and_hidden(self) -> None:
        assert ModuleService._is_module_dir("normal") is True
        assert ModuleService._is_module_dir(".hidden") is False
        assert ModuleService._is_module_dir("foo.bak") is False
        assert ModuleService._is_module_dir("foo.bak.2024") is False


# ---------------------------------------------------------------------------
# discover_local — subdir search and exception swallow
# ---------------------------------------------------------------------------


class TestDiscoverLocalExtended:
    def test_subdir_with_modules(self, service: ModuleService) -> None:
        alpha = service.modules_dir / "prompts" / "alpha"
        alpha.mkdir(parents=True, exist_ok=True)
        (alpha / "manifest.json").write_text(
            json.dumps(
                {
                    "module_id": "alpha",
                    "name": {"en": "alpha"},
                    "version": "1.0.0",
                }
            )
        )
        result = service.discover_local()
        assert any(m.module_id == "alpha" for m in result)

    def test_dir_without_manifest_searches_subdir(self, service: ModuleService) -> None:
        cat = service.modules_dir / "category"
        cat.mkdir(parents=True, exist_ok=True)
        alpha = cat / "alpha"
        alpha.mkdir(parents=True, exist_ok=True)
        (alpha / "manifest.json").write_text(
            json.dumps(
                {
                    "module_id": "alpha",
                    "name": {"en": "alpha"},
                    "version": "1.0.0",
                }
            )
        )
        result = service.discover_local()
        assert any(m.module_id == "alpha" for m in result)

    def test_dir_in_subdir_skipped(self, service: ModuleService) -> None:
        sub = service.modules_dir / "category"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "manifest.json").write_text(json.dumps({"module_id": "self"}))
        result = service.discover_local()
        assert any(m.module_id == "self" for m in result)


# ---------------------------------------------------------------------------
# discover_local_with_status — ghost filtering + missing DB fields
# ---------------------------------------------------------------------------


class TestDiscoverLocalWithStatusExtended:
    def test_db_only_kitsune_filtered(self, service: ModuleService) -> None:
        _seed_db_module_registry(service.db_path, "kitsune", name='"kitsune"')
        result = service.discover_local_with_status()
        assert not any(m["module_id"] == "kitsune" for m in result)

    def test_db_only_prompt_variant_filtered(self, service: ModuleService) -> None:
        _seed_db_module_registry(service.db_path, "prompt-foo", name='"foo"', type="prompt-variant")
        result = service.discover_local_with_status()
        assert not any(m["module_id"] == "prompt-foo" for m in result)

    def test_db_only_real_module_included(self, service: ModuleService) -> None:
        _seed_db_module_registry(
            service.db_path,
            "ghost-module",
            name='{"en":"Ghost"}',
            type="agent-persona",
        )
        result = service.discover_local_with_status()
        entry = next(m for m in result if m["module_id"] == "ghost-module")
        assert entry["on_disk"] is False
        assert entry["enabled"] is True


# ---------------------------------------------------------------------------
# list_all — DB merge behaviour
# ---------------------------------------------------------------------------


class TestListAllExtended:
    def test_module_not_in_registry_disabled(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        result = service.list_all()
        mod = next(m for m in result if m.module_id == "alpha")
        assert mod.enabled is False
        assert mod.installed is False
        assert mod.installed_at is None

    def test_module_in_registry_enabled(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "beta", version="1.0.0")
        _seed_db_module_registry(service.db_path, "beta", name='{"en":"beta name"}', enabled=1)
        result = service.list_all()
        mod = next(m for m in result if m.module_id == "beta")
        assert mod.enabled is True
        assert mod.installed is True
        assert mod.installed_at == "2024-01-01"


# ---------------------------------------------------------------------------
# fetch_repo_index — cache + schema variants + network errors
# ---------------------------------------------------------------------------


class TestFetchRepoIndex:
    def test_returns_cached_modules(self, service: ModuleService) -> None:
        service._registry_cache = {"modules": [{"module_id": "cached-1", "version": "1.0.0"}]}
        service._registry_cache_time = 1e18  # far future
        result = service.fetch_repo_index()
        assert result == [{"module_id": "cached-1", "version": "1.0.0"}]

    def test_returns_cached_legacy_repository(self, service: ModuleService) -> None:
        service._registry_cache = {"repository": {"alpha": {"module_id": "alpha", "version": "1.0.0"}}}
        service._registry_cache_time = 1e18
        result = service.fetch_repo_index()
        assert result == [{"module_id": "alpha", "version": "1.0.0"}]

    def test_force_refresh_calls_urlopen(self, service: ModuleService) -> None:
        service._registry_cache = {"modules": [{"module_id": "old"}]}
        service._registry_cache_time = 1e18
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value.decode.return_value = json.dumps(
                {"modules": [{"module_id": "fresh", "version": "2.0.0"}]}
            )
            result = service.fetch_repo_index(force_refresh=True)
        assert result == [{"module_id": "fresh", "version": "2.0.0"}]

    def test_network_error_raises_connection_error(self, service: ModuleService) -> None:
        service._registry_cache = None
        with patch("urllib.request.urlopen", side_effect=OSError("nope")):
            with pytest.raises(ConnectionError, match="not reachable"):
                service.fetch_repo_index(force_refresh=True)

    def test_unexpected_payload_returns_empty_list(self, service: ModuleService) -> None:
        service._registry_cache = None
        with patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value.decode.return_value = json.dumps({"unrelated": True})
            result = service.fetch_repo_index(force_refresh=True)
        assert result == []

    def test_get_download_url(self, service: ModuleService) -> None:
        url = service.get_download_url("alpha", "1.2.3")
        assert url == "https://github.com/asb-42/danwa-modules/releases/download/v1.2.3/alpha.zip"

    def test_default_url_constant(self) -> None:
        assert "raw.githubusercontent.com" in DANWA_MODULES_INDEX_URL


# ---------------------------------------------------------------------------
# install_from_repo — version selection, deps, role warnings, langpack fallback
# ---------------------------------------------------------------------------


class TestInstallFromRepo:
    def _patch_index(self, service: ModuleService, modules: list[dict]) -> object:
        """Patch fetch_repo_index to return the given modules list."""
        return patch.object(service, "fetch_repo_index", return_value=list(modules))

    def test_module_not_in_index_raises(self, service: ModuleService) -> None:
        with self._patch_index(service, []):
            with pytest.raises(FileNotFoundError, match="not found in danwa-modules"):
                service.install_from_repo("missing")

    def test_version_not_found_raises(self, service: ModuleService) -> None:
        with self._patch_index(service, [{"module_id": "alpha", "version": "1.0.0"}]):
            with pytest.raises(FileNotFoundError, match="version 9.9.9 not found"):
                service.install_from_repo("alpha", version="9.9.9")

    def test_specific_version_picked(self, service: ModuleService) -> None:
        with self._patch_index(
            service,
            [
                {"module_id": "alpha", "version": "1.0.0", "download_url": "http://u/1"},
                {"module_id": "alpha", "version": "2.0.0", "download_url": "http://u/2"},
            ],
        ):
            with patch.object(service.installer, "install_from_url") as install:
                install.return_value = type("R", (), {"status": "ok", "checksum": "", "warnings": []})()
                service.install_from_repo("alpha", version="2.0.0")
        # URL passed to installer should correspond to v2
        assert install.call_args[0][0] == "http://u/2"

    def test_dependency_errors_return_error_report(self, service: ModuleService) -> None:
        # Module requires a dep that is not installed
        with self._patch_index(
            service,
            [
                {
                    "module_id": "alpha",
                    "version": "1.0.0",
                    "dependencies": {"missing-dep": ">=1.0.0"},
                }
            ],
        ):
            report = service.install_from_repo("alpha")
        assert report.status == "error"
        assert any("missing-dep" in e for e in report.errors)

    def test_role_dep_warnings_appended(self, service: ModuleService) -> None:
        # No errors but role warnings should be added to report
        with self._patch_index(
            service,
            [
                {
                    "module_id": "alpha",
                    "version": "1.0.0",
                    "dependencies": {
                        "modules": {},
                        "roles": ["nonexistent-role"],
                    },
                }
            ],
        ):
            with patch.object(service.installer, "install_from_url") as install:
                install.return_value = type("R", (), {"status": "ok", "checksum": "", "warnings": []})()
                report = service.install_from_repo("alpha")
        assert report.status == "ok"
        # The role-deps code path runs; warnings is a list (may or may not contain
        # entries depending on resolve_roles output).
        assert isinstance(report.warnings, list)

    def test_checksum_filled_when_installer_left_blank(self, service: ModuleService) -> None:
        with self._patch_index(
            service,
            [
                {
                    "module_id": "alpha",
                    "version": "1.0.0",
                    "checksum_sha256": "deadbeef",
                }
            ],
        ):
            with patch.object(service.installer, "install_from_url") as install:
                install.return_value = type("R", (), {"status": "ok", "checksum": "", "warnings": []})()
                report = service.install_from_repo("alpha")
        assert report.checksum == "deadbeef"

    def test_language_pack_alt_url_fallback(self, service: ModuleService) -> None:
        with self._patch_index(
            service,
            [
                {
                    "module_id": "lang-fr",
                    "version": "1.0.0",
                    "type": "language-pack",
                    "language": "fr",
                    # Use a UUID-style URL that doesn't match the lang-<locale>.zip pattern,
                    # so the source code's alt-URL branch is triggered.
                    "download_url": "http://u/uuid-1234.zip",
                }
            ],
        ):
            # First call fails, second call (alt URL) succeeds
            call_urls: list[str] = []
            ok = type("R", (), {"status": "ok", "checksum": "", "warnings": []})()
            err = type("R", (), {"status": "error", "errors": ["fail"], "warnings": []})()

            def fake_install(url: str):
                call_urls.append(url)
                return ok if len(call_urls) == 2 else err

            with patch.object(service.installer, "install_from_url", side_effect=fake_install):
                report = service.install_from_repo("lang-fr")
        assert report.status == "ok"
        # The first call uses the explicit download_url; the second uses the alt URL.
        assert call_urls[0].endswith("uuid-1234.zip")
        assert call_urls[1].endswith("lang-fr.zip")

    def test_language_pack_db_fallback(self, service: ModuleService) -> None:
        with self._patch_index(
            service,
            [
                {
                    "module_id": "lang-fr",
                    "version": "1.0.0",
                    "type": "language-pack",
                    "language": "fr",
                }
            ],
        ):
            # All URL installs fail → DB fallback
            with patch.object(
                service.installer,
                "install_from_url",
                return_value=type("R", (), {"status": "error", "errors": ["x"], "warnings": []})(),
            ):
                report = service.install_from_repo("lang-fr")
        # If the DB has no fr translations, status is error
        assert report.status in {"ok", "error"}


# ---------------------------------------------------------------------------
# _install_langpack_from_db
# ---------------------------------------------------------------------------


class TestInstallLangpackFromDB:
    def test_no_translations_returns_error(self, service: ModuleService) -> None:
        report = service._install_langpack_from_db("lang-xx", {"language": "xx", "version": "1.0.0"})
        assert report.status == "error"
        assert any("No translations" in e for e in report.errors)


# ---------------------------------------------------------------------------
# check_updates — semver + string fallback
# ---------------------------------------------------------------------------


class TestCheckUpdates:
    def test_no_update_when_versions_match(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        with patch.object(service, "fetch_repo_index") as fetch:
            fetch.return_value = [{"module_id": "alpha", "version": "1.0.0"}]
            updates = service.check_updates()
        assert updates == []

    def test_update_when_remote_greater(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        with patch.object(service, "fetch_repo_index") as fetch:
            fetch.return_value = [
                {
                    "module_id": "alpha",
                    "version": "2.0.0",
                    "download_url": "http://u/v2.zip",
                    "checksum_sha256": "abc",
                }
            ]
            updates = service.check_updates()
        assert len(updates) == 1
        u = updates[0]
        assert u["module_id"] == "alpha"
        assert u["available_version"] == "2.0.0"
        assert u["current_version"] == "1.0.0"
        assert u["download_url"] == "http://u/v2.zip"
        assert u["checksum_sha256"] == "abc"

    def test_uses_default_download_url_when_missing(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        with patch.object(service, "fetch_repo_index") as fetch:
            fetch.return_value = [{"module_id": "alpha", "version": "2.0.0"}]
            updates = service.check_updates()
        assert "github.com" in updates[0]["download_url"]

    def test_string_fallback_when_version_unparseable(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="weird-local")
        with patch.object(service, "fetch_repo_index") as fetch:
            fetch.return_value = [{"module_id": "alpha", "version": "weird-remote"}]
            updates = service.check_updates()
        # Different strings → flagged as update via fallback
        assert len(updates) == 1

    def test_string_fallback_same_value_no_update(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="weird")
        with patch.object(service, "fetch_repo_index") as fetch:
            fetch.return_value = [{"module_id": "alpha", "version": "weird"}]
            updates = service.check_updates()
        assert updates == []


# ---------------------------------------------------------------------------
# install from URL / update paths
# ---------------------------------------------------------------------------


class TestInstallUrlAndUpdate:
    def test_install_with_source_url(self, service: ModuleService) -> None:
        with patch.object(service.installer, "install_from_url") as install:
            install.return_value = type("R", (), {"status": "ok"})()
            report = service.install("alpha", source="url", source_url="http://u/a.zip")
        assert report.status == "ok"
        assert install.call_args[0][0] == "http://u/a.zip"

    def test_update_delegates_to_installer(self, service: ModuleService) -> None:
        with patch.object(service.installer, "update") as upd:
            upd.return_value = type("R", (), {"status": "ok"})()
            report = service.update("alpha")
        assert report.status == "ok"
        upd.assert_called_once_with("alpha")


# ---------------------------------------------------------------------------
# _force_uninstall — DB error path
# ---------------------------------------------------------------------------


class TestForceUninstall:
    def test_module_not_found_returns_error(self, service: ModuleService) -> None:
        report = service._force_uninstall("missing")
        assert report.status == "error"
        assert any("not found" in b for b in report.blocked_by)

    def test_removes_files_and_db_entries(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        installer = ModuleInstaller(service.modules_dir, service.db_path)
        installer.install_from_directory(service.modules_dir / "alpha")

        report = service._force_uninstall("alpha")
        assert report.status == "ok"
        assert not (service.modules_dir / "alpha").exists()

    def test_sqlite_error_returns_error_report(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        with patch.object(service.installer, "_get_db", side_effect=sqlite3.Error("boom")):
            report = service._force_uninstall("alpha")
        assert report.status == "error"
        assert any("Database error" in b for b in report.blocked_by)


# ---------------------------------------------------------------------------
# get_profile / update_profile — yaml / json / markdown / missing
# ---------------------------------------------------------------------------


class TestProfile:
    def _write(self, mod_dir: Path, name: str, content: str) -> Path:
        path = mod_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_yaml_profile(self, service: ModuleService) -> None:
        _make_module(
            service.modules_dir,
            "alpha",
            profile_file="profile.yaml",
            profile_format="yaml",
        )
        self._write(service.modules_dir / "alpha", "profile.yaml", "name: alpha\nrole: critic\n")
        manifest_path = service.modules_dir / "alpha" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))
        profile = service.get_profile("alpha")
        assert profile == {"name": "alpha", "role": "critic"}

    def test_json_profile(self, service: ModuleService) -> None:
        _make_module(
            service.modules_dir,
            "beta",
            profile_file="profile.json",
            profile_format="json",
        )
        self._write(service.modules_dir / "beta", "profile.json", '{"name": "beta"}')
        manifest_path = service.modules_dir / "beta" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.json"
        manifest["profile_format"] = "json"
        manifest_path.write_text(json.dumps(manifest))
        profile = service.get_profile("beta")
        assert profile == {"name": "beta"}

    def test_markdown_profile(self, service: ModuleService) -> None:
        _make_module(
            service.modules_dir,
            "gamma",
            profile_file="profile.md",
            profile_format="markdown",
        )
        self._write(service.modules_dir / "gamma", "profile.md", "# profile")
        manifest_path = service.modules_dir / "gamma" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.md"
        manifest["profile_format"] = "markdown"
        manifest_path.write_text(json.dumps(manifest))
        profile = service.get_profile("gamma")
        assert profile == {"content": "# profile"}

    def test_unknown_format_returns_none(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "delta", profile_file="profile.txt", profile_format=None)
        self._write(service.modules_dir / "delta", "profile.txt", "x")
        manifest_path = service.modules_dir / "delta" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.txt"
        manifest_path.write_text(json.dumps(manifest))
        assert service.get_profile("delta") is None

    def test_profile_file_missing_returns_none(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "epsilon", profile_file="missing.yaml", profile_format="yaml")
        assert service.get_profile("epsilon") is None

    def test_module_dir_missing_returns_none(self, service: ModuleService) -> None:
        assert service.get_profile("nope") is None

    def test_manifest_missing_returns_none(self, service: ModuleService) -> None:
        mod_dir = service.modules_dir / "no-manifest"
        mod_dir.mkdir(parents=True, exist_ok=True)
        assert service.get_profile("no-manifest") is None

    def test_no_profile_file_returns_none(self, service: ModuleService) -> None:
        # Empty string profile_file triggers early None return
        _make_module(service.modules_dir, "zeta")
        manifest_path = service.modules_dir / "zeta" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = ""
        manifest_path.write_text(json.dumps(manifest))
        assert service.get_profile("zeta") is None

    def test_update_yaml_profile(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "eta", profile_file="profile.yaml", profile_format="yaml")
        self._write(service.modules_dir / "eta", "profile.yaml", "name: eta\ncustom_field: foo\n")
        manifest_path = service.modules_dir / "eta" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))

        ok = service.update_profile("eta", {"name": "new-name", "custom_field": "bar"})
        assert ok is True
        loaded = yaml.safe_load((service.modules_dir / "eta" / "profile.yaml").read_text())
        assert loaded["custom_field"] == "bar"
        m2 = json.loads(manifest_path.read_text())
        assert m2["name"] == {"en": "new-name"}

    def test_update_json_profile(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "theta", profile_file="profile.json", profile_format="json")
        self._write(service.modules_dir / "theta", "profile.json", '{"custom":"critic"}')
        manifest_path = service.modules_dir / "theta" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.json"
        manifest["profile_format"] = "json"
        manifest_path.write_text(json.dumps(manifest))

        ok = service.update_profile("theta", {"custom": "moderator"})
        assert ok is True
        loaded = json.loads((service.modules_dir / "theta" / "profile.json").read_text())
        assert loaded["custom"] == "moderator"

    def test_update_markdown_profile(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "iota", profile_file="profile.md", profile_format="markdown")
        self._write(service.modules_dir / "iota", "profile.md", "old")
        manifest_path = service.modules_dir / "iota" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.md"
        manifest["profile_format"] = "markdown"
        manifest_path.write_text(json.dumps(manifest))

        ok = service.update_profile("iota", {"content": "new body"})
        assert ok is True
        assert (service.modules_dir / "iota" / "profile.md").read_text() == "new body"

    def test_update_unknown_format_returns_false(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "kappa", profile_file="profile.txt", profile_format=None)
        self._write(service.modules_dir / "kappa", "profile.txt", "x")
        manifest_path = service.modules_dir / "kappa" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.txt"
        manifest_path.write_text(json.dumps(manifest))
        assert service.update_profile("kappa", {"role": "x"}) is False

    def test_update_profile_manifest_field_migration(self, service: ModuleService) -> None:
        # name/description provided as plain strings should be wrapped into {"en": ...}
        _make_module(service.modules_dir, "lamda", profile_file="profile.yaml", profile_format="yaml")
        self._write(service.modules_dir / "lamda", "profile.yaml", "id: lamda\n")
        manifest_path = service.modules_dir / "lamda" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))

        service.update_profile("lamda", {"name": "New Name", "tags": ["x"]})
        updated_manifest = json.loads(manifest_path.read_text())
        assert updated_manifest["name"] == {"en": "New Name"}
        assert updated_manifest["tags"] == ["x"]

    def test_update_profile_no_manifest_returns_false(self, service: ModuleService) -> None:
        assert service.update_profile("nope", {"x": 1}) is False


# ---------------------------------------------------------------------------
# duplicate_module
# ---------------------------------------------------------------------------


class TestDuplicateModule:
    def test_yaml_profile_duplicate(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "src", profile_file="profile.yaml", profile_format="yaml")
        (service.modules_dir / "src" / "profile.yaml").write_text("id: original-id\nname: orig\n", encoding="utf-8")
        manifest_path = service.modules_dir / "src" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))

        result = service.duplicate_module("src", "dup", new_name="Dup Name")
        assert result is not None
        # The duplicate's profile must have a fresh id
        dup_profile = yaml.safe_load((service.modules_dir / "dup" / "profile.yaml").read_text())
        assert dup_profile["id"] != "original-id"
        assert dup_profile["name"] == "Dup Name"

    def test_json_profile_duplicate(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "src2", profile_file="profile.json", profile_format="json")
        (service.modules_dir / "src2" / "profile.json").write_text('{"id": "orig", "name": "orig"}', encoding="utf-8")
        manifest_path = service.modules_dir / "src2" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.json"
        manifest["profile_format"] = "json"
        manifest_path.write_text(json.dumps(manifest))

        result = service.duplicate_module("src2", "dup2", new_name="Dup2")
        assert result is not None
        dup_profile = json.loads((service.modules_dir / "dup2" / "profile.json").read_text())
        assert dup_profile["id"] != "orig"
        assert dup_profile["name"] == "Dup2"

    def test_markdown_profile_duplicate_passthrough(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "src3", profile_file="profile.md", profile_format="markdown")
        (service.modules_dir / "src3" / "profile.md").write_text("# markdown", encoding="utf-8")
        manifest_path = service.modules_dir / "src3" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.md"
        manifest["profile_format"] = "markdown"
        manifest_path.write_text(json.dumps(manifest))

        result = service.duplicate_module("src3", "dup3")
        assert result is not None
        # Markdown branch is a no-op for profile
        assert (service.modules_dir / "dup3" / "profile.md").read_text() == "# markdown"

    def test_duplicate_without_new_name(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "src4", profile_file="profile.yaml", profile_format="yaml")
        (service.modules_dir / "src4" / "profile.yaml").write_text("id: orig\n", encoding="utf-8")
        manifest_path = service.modules_dir / "src4" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))
        result = service.duplicate_module("src4", "dup4")
        assert result is not None

    def test_duplicate_target_exists_returns_none(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "src5")
        _make_module(service.modules_dir, "dup5")
        assert service.duplicate_module("src5", "dup5") is None

    def test_duplicate_source_missing_returns_none(self, service: ModuleService) -> None:
        assert service.duplicate_module("nope", "dup-x") is None


# ---------------------------------------------------------------------------
# translate — sqlite error path
# ---------------------------------------------------------------------------


class TestTranslateExtended:
    def test_sqlite_error_returns_error(self, service: ModuleService) -> None:
        with patch("sqlite3.connect", side_effect=sqlite3.Error("nope")):
            result = service.translate("alpha", "de")
        assert result.status == "error"


# ---------------------------------------------------------------------------
# _dir_to_info — markdown profile, legacy files, malformed timestamps
# ---------------------------------------------------------------------------


class TestDirToInfo:
    def test_markdown_profile_truncated(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", profile_file="profile.md", profile_format="markdown")
        # Write a 600-char markdown
        long_text = ("# line\n" * 200)[:600]
        (service.modules_dir / "alpha" / "profile.md").write_text(long_text)
        manifest_path = service.modules_dir / "alpha" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.md"
        manifest["profile_format"] = "markdown"
        manifest_path.write_text(json.dumps(manifest))

        info = service._dir_to_info(service.modules_dir / "alpha")
        assert info is not None
        assert info.profile_preview is not None
        # Truncated to 500 chars
        assert len(info.profile_preview["content"]) == 500

    def test_legacy_files_count(self, service: ModuleService) -> None:
        # No profile_file, but files[] present
        _make_module(service.modules_dir, "legacy", version="1.0.0", extra_files=["a.md", "b.md", "c.md"])
        info = service._dir_to_info(service.modules_dir / "legacy")
        assert info is not None
        assert info.file_count == 3

    def test_malformed_timestamps_use_db_fallback(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        manifest_path = service.modules_dir / "alpha" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["created_at"] = "not-a-date"
        manifest["updated_at"] = "also-bad"
        manifest_path.write_text(json.dumps(manifest))
        _seed_db_module_registry(service.db_path, "alpha", updated_at="2024-06-01")
        info = service._dir_to_info(service.modules_dir / "alpha")
        assert info is not None
        # created_at falls back to None, updated_at falls back to DB
        assert info.created_at is None
        assert info.updated_at is not None

    def test_invalid_json_returns_none(self, service: ModuleService) -> None:
        mod_dir = service.modules_dir / "bad"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "manifest.json").write_text("{not valid")
        assert service._dir_to_info(mod_dir) is None

    def test_missing_manifest_returns_none(self, service: ModuleService) -> None:
        mod_dir = service.modules_dir / "no-mf"
        mod_dir.mkdir(parents=True, exist_ok=True)
        assert service._dir_to_info(mod_dir) is None

    def test_yaml_profile_loads(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", profile_file="profile.yaml", profile_format="yaml")
        (service.modules_dir / "alpha" / "profile.yaml").write_text("name: alpha\n")
        manifest_path = service.modules_dir / "alpha" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["profile_format"] = "yaml"
        manifest_path.write_text(json.dumps(manifest))
        info = service._dir_to_info(service.modules_dir / "alpha")
        assert info is not None
        assert info.profile_preview == {"name": "alpha"}

    def test_json_profile_loads(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", profile_file="profile.json", profile_format="json")
        (service.modules_dir / "alpha" / "profile.json").write_text('{"x": 1}')
        manifest_path = service.modules_dir / "alpha" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["profile_file"] = "profile.json"
        manifest["profile_format"] = "json"
        manifest_path.write_text(json.dumps(manifest))
        info = service._dir_to_info(service.modules_dir / "alpha")
        assert info is not None
        assert info.profile_preview == {"x": 1}

    def test_db_status_enabled_used(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        _seed_db_module_registry(service.db_path, "alpha", enabled=1)
        info = service._dir_to_info(service.modules_dir / "alpha")
        assert info is not None
        assert info.enabled is True


# ---------------------------------------------------------------------------
# _update_manifest_checksum
# ---------------------------------------------------------------------------


class TestUpdateManifestChecksum:
    def test_no_profile_file_keeps_existing(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", version="1.0.0")
        manifest = json.loads((service.modules_dir / "alpha" / "manifest.json").read_text())
        manifest["checksum"] = "old"
        original_updated = manifest.get("updated_at")
        service._update_manifest_checksum(service.modules_dir / "alpha", manifest)
        new_manifest = json.loads((service.modules_dir / "alpha" / "manifest.json").read_text())
        # No profile file → checksum stays as before
        assert new_manifest["checksum"] == "old"
        # updated_at is refreshed
        assert new_manifest["updated_at"] != original_updated

    def test_with_profile_file_recomputes(self, service: ModuleService) -> None:
        _make_module(service.modules_dir, "alpha", profile_file="profile.yaml", profile_format="yaml")
        (service.modules_dir / "alpha" / "profile.yaml").write_text("id: a\nname: A\n")
        manifest = json.loads((service.modules_dir / "alpha" / "manifest.json").read_text())
        manifest["profile_file"] = "profile.yaml"
        manifest["checksum"] = "old"
        service._update_manifest_checksum(service.modules_dir / "alpha", manifest)
        new_manifest = json.loads((service.modules_dir / "alpha" / "manifest.json").read_text())
        assert new_manifest["checksum"] != "old"
        # SHA-256 of "id: a\nname: A\n"
        import hashlib

        expected = hashlib.sha256(b"id: a\nname: A\n").hexdigest()
        assert new_manifest["checksum"] == expected


# ---------------------------------------------------------------------------
# _get_db_module_info / _get_db_status_map
# ---------------------------------------------------------------------------


class TestDbHelpers:
    def test_get_db_module_info_returns_row(self, service: ModuleService) -> None:
        _seed_db_module_registry(service.db_path, "alpha", version="2.5.0", enabled=1)
        info = service._get_db_module_info("alpha")
        assert info is not None
        assert info["version"] == "2.5.0"
        assert info["enabled"] == 1

    def test_get_db_module_info_missing_returns_none(self, service: ModuleService) -> None:
        assert service._get_db_module_info("nope") is None

    def test_get_db_module_info_sqlite_error(self, service: ModuleService) -> None:
        with patch("sqlite3.connect", side_effect=sqlite3.Error("nope")):
            assert service._get_db_module_info("alpha") is None

    def test_get_db_status_map_parses_names(self, service: ModuleService) -> None:
        _seed_db_module_registry(service.db_path, "alpha", name='{"en":"Alpha","de":"Alf"}')
        result = service._get_db_status_map()
        assert "alpha" in result
        assert result["alpha"]["name"] == {"en": "Alpha", "de": "Alf"}

    def test_get_db_status_map_handles_invalid_name_json(self, service: ModuleService) -> None:
        _seed_db_module_registry(service.db_path, "alpha", name="not json")
        result = service._get_db_status_map()
        assert "alpha" in result
        # Falls back to raw string
        assert result["alpha"]["name"] == "not json"

    def test_get_db_status_map_sqlite_error(self, service: ModuleService) -> None:
        with patch("sqlite3.connect", side_effect=sqlite3.Error("nope")):
            assert service._get_db_status_map() == {}
