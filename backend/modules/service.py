"""Module Service — discover, list, and manage installed/available modules."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from packaging.version import Version

from backend.modules.dependency_resolver import DependencyResolver
from backend.modules.installer import ModuleInstaller
from backend.modules.models import (
    InstallationReport,
    ModuleInfo,
    TranslationResult,
    UninstallationReport,
)
from backend.modules.type_derivation import (
    derive_module_category,
    derive_module_type,
    parent_dir_name,
)
from backend.modules.validation import ModuleValidator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = ROOT / "modules"
DEFAULT_DB = ROOT / "data" / "blueprints.db"

DANWA_MODULES_REPO = "asb-42/danwa-modules"
DANWA_MODULES_INDEX_URL = "https://raw.githubusercontent.com/asb-42/danwa-modules/main/index.json"
DANWA_MODULES_RELEASE_URL = "https://github.com/asb-42/danwa-modules/releases/download/v{version}/{module_id}.zip"


class ModuleService:
    """ModuleService class."""

    def __init__(
        self,
        modules_dir: Path | str = MODULES_DIR,
        db_path: Path | str = DEFAULT_DB,
    ):
        """Initialise ModuleService."""
        self.modules_dir = Path(modules_dir)
        self.db_path = Path(db_path)
        self.validator = ModuleValidator(self.modules_dir)
        self.installer = ModuleInstaller(self.modules_dir, self.db_path)
        self.dependency_resolver = DependencyResolver()
        self._registry_cache: dict | None = None
        self._registry_cache_time: float = 0
        self._registry_cache_ttl: int = 86400

    def _resolve_module_dir(self, module_id: str) -> Path | None:
        """Find a module directory by ID, searching root and one level of subdirectories.

        First tries direct path match (modules/<module_id>/manifest.json),
        then falls back to reading all manifest.json files to check the
        ``module_id`` field (since directory names may differ from the
        module_id stored in the manifest).
        """
        direct = self.modules_dir / module_id
        if (direct / "manifest.json").exists():
            return direct
        for subdir in self.modules_dir.iterdir():
            if subdir.is_dir() and self._is_module_dir(subdir.name):
                candidate = subdir / module_id
                if (candidate / "manifest.json").exists():
                    return candidate
                # Also check the subdir itself as a module directory
                manifest_path = subdir / "manifest.json"
                if manifest_path.exists():
                    try:
                        data = json.loads(manifest_path.read_text(encoding="utf-8"))
                        if data.get("module_id") == module_id:
                            return subdir
                    except (json.JSONDecodeError, OSError):
                        continue
                # Check one more level (subdir/<child>/) for matching module_id
                for child in sorted(subdir.iterdir()):
                    if not child.is_dir() or not self._is_module_dir(child.name):
                        continue
                    child_manifest = child / "manifest.json"
                    if child_manifest.exists():
                        try:
                            data = json.loads(child_manifest.read_text(encoding="utf-8"))
                            if data.get("module_id") == module_id:
                                return child
                        except (json.JSONDecodeError, OSError):
                            continue
        return None

    @staticmethod
    def _is_module_dir(name: str) -> bool:
        """Return True if *name* looks like a real module directory (not backup/temp)."""
        if name.startswith("."):
            return False
        if ".bak." in name or name.endswith(".bak"):
            return False
        return True

    def discover_local(self) -> list[ModuleInfo]:
        """Discover local the instance."""
        modules: list[ModuleInfo] = []
        if not self.modules_dir.exists():
            return modules

        # Search root and one level of subdirectories (category dirs)
        search_dirs = []
        for entry in sorted(self.modules_dir.iterdir()):
            if not entry.is_dir() or not self._is_module_dir(entry.name):
                continue
            if (entry / "manifest.json").exists():
                search_dirs.append(entry)
            else:
                for sub in sorted(entry.iterdir()):
                    if sub.is_dir() and self._is_module_dir(sub.name):
                        search_dirs.append(sub)

        for module_dir in search_dirs:
            if not (module_dir / "manifest.json").exists():
                continue
            try:
                info = self._dir_to_info(module_dir)
                if info:
                    modules.append(info)
            except Exception:
                logger.exception("Failed to read module %s", module_dir.name)

        return modules

    def discover_local_with_status(self) -> list[dict[str, Any]]:
        """Discover local with status the instance."""
        modules = self.discover_local()
        db_status = self._get_db_status_map()

        result = []
        for mod in modules:
            db_info = db_status.get(mod.module_id, {})
            result.append(
                {
                    "module_id": mod.module_id,
                    "name": mod.name,
                    "description": mod.description,
                    "version": mod.version,
                    "type": mod.type,
                    "category": mod.category,
                    "author": mod.author,
                    "license": mod.license,
                    "tags": mod.tags,
                    "language": mod.language,
                    "checksum": mod.checksum,
                    "installed": True,
                    "enabled": bool(db_info.get("enabled", False)),
                    "installed_at": db_info.get("installed_at"),
                    "created_at": str(mod.created_at) if mod.created_at else None,
                    "updated_at": str(mod.updated_at) if mod.updated_at else None,
                    "dependencies": mod.dependencies,
                    "file_count": mod.file_count,
                    "profile_preview": mod.profile_preview,
                }
            )

        for mid, db_info in db_status.items():
            if not any(m.module_id == mid for m in modules):
                # Skip legacy ghost entries that now have a proper filesystem module
                db_type = db_info.get("type", "custom")
                if db_type == "custom" and mid in ("kitsune",):
                    continue
                if db_type == "prompt-variant" and mid.startswith("prompt-"):
                    continue
                result.append(
                    {
                        "module_id": mid,
                        "name": db_info.get("name", {}),
                        "description": db_info.get("description", ""),
                        "version": db_info.get("version", "0.0.0"),
                        "type": db_info.get("type", "custom"),
                        "category": db_info.get("category", "custom"),
                        "author": db_info.get("author", {}),
                        "license": db_info.get("license", "CC-BY-4.0"),
                        "tags": db_info.get("tags", []),
                        "language": db_info.get("language", "en"),
                        "checksum": db_info.get("checksum", ""),
                        "installed": True,
                        "enabled": db_info.get("enabled", True),
                        "installed_at": db_info.get("installed_at"),
                        "created_at": db_info.get("created_at"),
                        "updated_at": db_info.get("updated_at"),
                        "dependencies": db_info.get("dependencies", {}),
                        "file_count": db_info.get("file_count", 0),
                        "on_disk": False,
                    }
                )

        return result

    def get(self, module_id: str) -> ModuleInfo | None:
        """Retrieve and return the requested item."""
        module_dir = self._resolve_module_dir(module_id)
        if module_dir:
            return self._dir_to_info(module_dir)
        return None

    def list_all(self, category: str | None = None) -> list[ModuleInfo]:
        """Return a list of all."""
        modules = self.discover_local()
        if category:
            modules = [m for m in modules if m.category.value == category]
        # Merge enabled status from module_registry
        db_status = self._get_db_status_map()
        for m in modules:
            db_info = db_status.get(m.module_id, {})
            if db_info:
                m.enabled = bool(db_info.get("enabled", False))
                m.installed = True
                m.installed_at = db_info.get("installed_at")
            else:
                # Not in registry → treat as not installed/enabled
                m.enabled = False
                m.installed = False
        return modules

    def fetch_repo_index(
        self,
        repo_url: str = DANWA_MODULES_INDEX_URL,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch the ``index.json`` from the danwa-modules repository.

        Returns a list of module entries, each with ``module_id``,
        ``version``, ``type``, ``download_url``, ``checksum_sha256``,
        and optional ``translation_stats``.

        Results are cached for 24 hours (configurable via
        ``_registry_cache_ttl``).
        """
        import time

        now = time.time()
        if not force_refresh and self._registry_cache and (now - self._registry_cache_time) < self._registry_cache_ttl:
            cached = self._registry_cache
            if "modules" in cached:
                return cached["modules"]
            repo_dict = cached.get("repository")
            if isinstance(repo_dict, dict):
                return list(repo_dict.values())
            return []

        try:
            req = urllib.request.Request(
                repo_url,
                headers={"User-Agent": "Danwa/2.1.0 (ModuleService)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            self._registry_cache = data
            self._registry_cache_time = now
            # Support both schema v3 ("modules" list) and legacy ("repository" dict)
            if "modules" in data:
                return data["modules"]
            repo_dict = data.get("repository")
            if isinstance(repo_dict, dict):
                return list(repo_dict.values())
            return []
        except Exception as exc:
            logger.warning("Module repo index not reachable (%s): %s", repo_url, exc)
            raise ConnectionError(f"Module repository not reachable: {exc}") from exc

    def get_download_url(self, module_id: str, version: str) -> str:
        """Construct the download URL for a module release ZIP."""
        return DANWA_MODULES_RELEASE_URL.format(module_id=module_id, version=version)

    def install_from_repo(
        self,
        module_id: str,
        version: str | None = None,
    ) -> InstallationReport:
        """Install a module directly from the danwa-modules GitHub release.

        For language-pack modules, if the download fails (e.g. release ZIP
        not yet published), falls back to creating the module directory from
        existing DB translations + repo index metadata.

        Args:
            module_id: The module ID to install.
            version: Specific version to install (defaults to latest).

        Returns:
            InstallationReport with the result.

        Raises:
            FileNotFoundError: If the module or version is not found in the index.
        """
        index = self.fetch_repo_index(force_refresh=True)
        candidates = [m for m in index if m["module_id"] == module_id]
        if not candidates:
            raise FileNotFoundError(f"Module '{module_id}' not found in danwa-modules repository")

        target = candidates[0]
        if version:
            matches = [m for m in candidates if m.get("version") == version]
            if not matches:
                raise FileNotFoundError(f"Module '{module_id}' version {version} not found in danwa-modules repository")
            target = matches[0]

        module_version = target.get("version", "0.0.0")
        download_url = target.get(
            "download_url",
            self.get_download_url(module_id, module_version),
        )

        checksum = target.get("checksum_sha256", "")

        # Pre-flight dependency check
        installed_local = self.discover_local()
        installed_map = {m.module_id: m.version for m in installed_local}

        raw_deps = target.get("dependencies", {})
        # Handle both legacy flat dict and new structured format
        if isinstance(raw_deps, dict) and "modules" in raw_deps:
            module_deps = raw_deps.get("modules", {})
            role_deps = raw_deps.get("roles", [])
        elif isinstance(raw_deps, dict):
            module_deps = raw_deps
            role_deps = []
        else:
            module_deps = {}
            role_deps = []

        # 1. Module-level dependency check (semver constraints)
        errors = self.dependency_resolver.resolve(
            module_id,
            module_deps if isinstance(module_deps, dict) else {},
            installed_map,
        )
        if errors:
            report = InstallationReport(
                status="error",
                module_id=module_id,
                version=module_version,
                errors=errors,
            )
            return report

        # 2. Role-based dependency check (warn if roles are missing)
        warnings: list[str] = []
        if role_deps and isinstance(role_deps, list):
            installed_info = [
                {
                    "module_id": m.module_id,
                    "type": str(m.type) if m.type else "",
                    "role": m.role or "",
                    "tags": m.tags,
                }
                for m in installed_local
            ]
            role_errors, _ = self.dependency_resolver.resolve_roles(
                module_id,
                role_deps,
                installed_info,
            )
            # In Phase 2: warn only, don't block installation
            warnings.extend(role_errors)

        report = self.installer.install_from_url(download_url)
        if report.status == "ok" and checksum and not report.checksum:
            report.checksum = checksum
        if warnings:
            report.warnings.extend(warnings)

        # If the primary download failed for a language-pack module,
        # try an alternative URL using lang-{code}.zip naming (GitHub
        # releases may use locale-based naming instead of UUID).
        if report.status == "error" and target.get("type") == "language-pack":
            locale = target.get("language", "")
            if locale and not download_url.endswith(f"lang-{locale}.zip"):
                alt_url = DANWA_MODULES_RELEASE_URL.format(
                    module_id=f"lang-{locale}",
                    version=module_version,
                )
                logger.info(
                    "Primary download failed for %s, trying alternative URL: %s",
                    module_id,
                    alt_url,
                )
                alt_report = self.installer.install_from_url(alt_url)
                if alt_report.status == "ok":
                    if checksum and not alt_report.checksum:
                        alt_report.checksum = checksum
                    if warnings:
                        alt_report.warnings.extend(warnings)
                    return alt_report

            # Final fallback: create the module from existing DB translations.
            logger.warning(
                "Download failed for language-pack %s (%s), falling back to DB install",
                module_id,
                report.errors,
            )
            return self._install_langpack_from_db(module_id, target)

        return report

    def _install_langpack_from_db(
        self,
        module_id: str,
        target: dict,
    ) -> InstallationReport:
        """Create a language-pack module directory from DB translations.

        Used as fallback when the GitHub release ZIP is not available.
        Reads translations from the langpack DB namespace and creates
        manifest.json + ui_strings.json in the modules directory.
        """
        from backend.services.ui_translation_service import LOCALE_NAMES, UITranslationService

        locale = target.get("language", module_id.replace("lang-", ""))
        namespace = f"langpack:lang-{locale}"
        module_version = target.get("version", "1.0.0")
        now = datetime.now(UTC).isoformat()

        # Try to get translations from langpack namespace first, then global
        i18n_svc = UITranslationService()
        ui_strings = i18n_svc.get_translations_bulk(locale, namespace)
        if not ui_strings:
            ui_strings = i18n_svc.get_translations_bulk(locale, "global")
        if not ui_strings:
            return InstallationReport(
                status="error",
                module_id=module_id,
                version=module_version,
                errors=[f"No translations found for locale '{locale}' in DB"],
            )

        # Also copy to langpack namespace if not already there
        if namespace not in [ns for ns in ["langpack:lang-" + locale]]:
            for key, value in ui_strings.items():
                i18n_svc.set_translation(key, locale, value, namespace, "bulk_imported")
            i18n_svc.invalidate_cache(locale)

        # Use translations/ subdirectory to match repo structure and bootstrap
        module_dir = self.modules_dir / "translations" / module_id
        module_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "schema_version": "3.0.0",
            "module_id": module_id,
            "name": target.get("name", {"en": LOCALE_NAMES.get(locale, locale)}),
            "description": target.get("description", {"en": f"UI translation pack for {LOCALE_NAMES.get(locale, locale)}"}),
            "version": module_version,
            "type": "language-pack",
            "category": "translations",
            "language": locale,
            "author": target.get("author", {"name": "Danwa Community"}),
            "license": target.get("license", "CC-BY-4.0"),
            "tags": target.get("tags", [locale, "translation"]),
            "profile_file": "ui_strings.json",
            "profile_format": "json",
            "compatibility": target.get("compatibility", {"danwa_min_version": "2.2.0"}),
            "created_at": now,
        }

        (module_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (module_dir / "ui_strings.json").write_text(
            json.dumps(ui_strings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Language-pack %s installed from DB (%d keys)", module_id, len(ui_strings))
        return InstallationReport(
            status="ok",
            module_id=module_id,
            version=module_version,
            files_installed=2,
            db_entries_created=len(ui_strings),
        )

    def check_updates(
        self,
        repo_url: str = DANWA_MODULES_INDEX_URL,
    ) -> list[dict[str, Any]]:
        """Compare installed module versions against the danwa-modules repo index.

        Uses semver comparison — any remote version greater than the
        installed version is reported as an available update.

        Returns:
            List of ``{module_id, current_version, available_version,
            download_url, checksum_sha256}`` dicts.
        """
        remote_modules = self.fetch_repo_index(repo_url)
        installed = {m.module_id: m for m in self.discover_local()}

        updates = []
        for remote_mod in remote_modules:
            mod_id = remote_mod.get("module_id", "")
            if mod_id not in installed:
                continue

            local_version = installed[mod_id].version
            remote_version = remote_mod.get("version", "0.0.0")

            try:
                local_ver = Version(local_version)
                remote_ver = Version(remote_version)
                if remote_ver > local_ver:
                    updates.append(
                        {
                            "module_id": mod_id,
                            "current_version": local_version,
                            "available_version": remote_version,
                            "download_url": remote_mod.get(
                                "download_url",
                                self.get_download_url(mod_id, remote_version),
                            ),
                            "checksum_sha256": remote_mod.get("checksum_sha256", ""),
                            "name": remote_mod.get("name", {}),
                        }
                    )
            except Exception:
                # If version parsing fails, fall back to string comparison
                if remote_version != local_version:
                    updates.append(
                        {
                            "module_id": mod_id,
                            "current_version": local_version,
                            "available_version": remote_version,
                            "download_url": remote_mod.get("download_url", ""),
                            "checksum_sha256": remote_mod.get("checksum_sha256", ""),
                            "name": remote_mod.get("name", {}),
                        }
                    )

        updates.sort(key=lambda u: u["module_id"])
        return updates

    def install(
        self,
        module_id: str,
        source: str = "local",
        source_url: str | None = None,
    ) -> InstallationReport:
        """Install the instance."""
        if source == "url" and source_url:
            return self.installer.install_from_url(source_url)
        else:
            module_dir = self._resolve_module_dir(module_id)
            if not module_dir:
                raise FileNotFoundError(f"Module directory not found: {module_id}")
            return self.installer.install_from_directory(module_dir)

    def uninstall(self, module_id: str, force: bool = False) -> UninstallationReport:
        """Uninstall the instance."""
        if not force:
            return self.installer.uninstall(module_id)
        else:
            return self._force_uninstall(module_id)

    def update(self, module_id: str) -> InstallationReport:
        """Update the instance with new values."""
        return self.installer.update(module_id)

    def _force_uninstall(self, module_id: str) -> UninstallationReport:
        """Force uninstall the instance."""
        target_dir = self._resolve_module_dir(module_id)
        if not target_dir:
            return UninstallationReport(
                status="error",
                module_id=module_id,
                blocked_by=[f"Module directory not found: {module_id}"],
            )
        files_removed = 0
        if target_dir.exists():
            for f in target_dir.rglob("*"):
                if f.is_file():
                    files_removed += 1
            shutil.rmtree(target_dir)

        for bak in self.modules_dir.glob(f"{module_id}.bak.*"):
            if bak.is_dir():
                shutil.rmtree(bak)

        db_entries_removed = 0
        try:
            conn = self.installer._get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM module_translation_cache WHERE module_id = ?", (module_id,))
            db_entries_removed += cursor.rowcount
            cursor.execute("DELETE FROM module_registry WHERE id = ?", (module_id,))
            db_entries_removed += cursor.rowcount
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Database error during force uninstall of %s: %s", module_id, e)
            return UninstallationReport(
                status="error",
                module_id=module_id,
                blocked_by=[f"Database error: {e}"],
            )

        logger.info("Force-uninstalled module %s (%d files, %d DB entries)", module_id, files_removed, db_entries_removed)

        return UninstallationReport(
            status="ok",
            module_id=module_id,
            files_removed=files_removed,
            db_entries_removed=db_entries_removed,
        )

    @staticmethod
    def _derive_profile_format(profile_file: str, manifest_format: str | None) -> str | None:
        """Derive profile format the instance."""
        if manifest_format:
            return manifest_format
        ext = Path(profile_file).suffix.lower()
        return {"yaml": "yaml", "yml": "yaml", "json": "json", "md": "markdown"}.get(ext)

    def get_profile(self, module_id: str) -> dict[str, Any] | None:
        """Retrieve and return profile."""
        module_dir = self._resolve_module_dir(module_id)
        if not module_dir:
            return None
        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile_file = manifest.get("profile_file")
        profile_format = self._derive_profile_format(profile_file, manifest.get("profile_format"))

        if not profile_file:
            return None

        profile_path = module_dir / profile_file
        if not profile_path.exists():
            return None

        content = profile_path.read_text(encoding="utf-8")
        if profile_format == "yaml":
            return yaml.safe_load(content)
        elif profile_format == "json":
            return json.loads(content)
        elif profile_format == "markdown":
            return {"content": content}
        return None

    def update_profile(self, module_id: str, profile_data: dict[str, Any]) -> bool:
        """Update profile."""
        module_dir = self._resolve_module_dir(module_id)
        if not module_dir:
            return False
        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            return False

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile_file = manifest.get("profile_file")
        profile_format = self._derive_profile_format(profile_file, manifest.get("profile_format"))

        if not profile_file:
            return False

        # Fields that belong in manifest.json rather than the profile file
        manifest_fields = {"name", "description", "role", "tags", "language", "version"}
        manifest_dirty = False
        for key in manifest_fields:
            if key in profile_data:
                val = profile_data[key]
                # Wrap name/description into language dict if given as plain string
                if key in ("name", "description") and isinstance(val, str):
                    val = {"en": val}
                manifest[key] = val
                manifest_dirty = True

        if manifest_dirty:
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        safe_data = {k: v for k, v in profile_data.items() if k not in {"id"} | manifest_fields}

        profile_path = module_dir / profile_file
        if profile_format == "yaml":
            profile_path.write_text(yaml.dump(safe_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
        elif profile_format == "json":
            profile_path.write_text(json.dumps(safe_data, indent=2, ensure_ascii=False), encoding="utf-8")
        elif profile_format == "markdown":
            profile_path.write_text(safe_data.get("content", ""), encoding="utf-8")
        else:
            return False

        self._update_manifest_checksum(module_dir, manifest)
        return True

    def duplicate_module(self, module_id: str, new_id: str, new_name: str | None = None) -> dict[str, Any] | None:
        """Duplicate module the instance."""
        src_dir = self._resolve_module_dir(module_id)
        dst_dir = self.modules_dir / new_id

        if not src_dir or dst_dir.exists():
            return None

        shutil.copytree(src_dir, dst_dir)

        manifest_path = dst_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["module_id"] = new_id
        if "created_at" not in manifest:
            manifest["created_at"] = datetime.now(UTC).isoformat()
        manifest["updated_at"] = datetime.now(UTC).isoformat()
        if new_name:
            manifest["name"]["en"] = new_name
            manifest["name"]["de"] = new_name

        profile_file = manifest.get("profile_file")
        if profile_file:
            profile_path = dst_dir / profile_file
            if profile_path.exists():
                profile_format = manifest.get("profile_format")
                new_profile_id = uuid.uuid4().hex[:8]
                if profile_format == "yaml":
                    data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
                    data["id"] = new_profile_id
                    if new_name:
                        data["name"] = new_name
                    profile_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
                elif profile_format == "json":
                    data = json.loads(profile_path.read_text(encoding="utf-8"))
                    data["id"] = new_profile_id
                    if new_name:
                        data["name"] = new_name
                    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                elif profile_format == "markdown":
                    pass

        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        self.installer.install_from_directory(dst_dir)
        return self._dir_to_info(dst_dir)

    def translate(
        self,
        module_id: str,
        target_lang: str,
        force: bool = False,
        llm_profile_id: str | None = None,
        skip_back_translation: bool = False,
        auto_approve: bool = False,
        quality_threshold: float = 0.7,
    ) -> TranslationResult:
        """Translate the instance."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT file_path, source_hash FROM module_translation_cache WHERE module_id = ? AND (source_language = 'en' OR language = 'en')",
                (module_id,),
            )
            source_files = cursor.fetchall()

            if not source_files:
                conn.close()
                return TranslationResult(
                    module_id=module_id,
                    target_language=target_lang,
                    status="error",
                    errors=["No source (EN) content found for module"],
                )

            translated = 0
            skipped = 0
            quality_scores: dict[str, float] = {}

            for row in source_files:
                fpath = row["file_path"]
                source_hash = row["source_hash"]

                if not force:
                    cursor.execute(
                        "SELECT quality_score FROM module_translation_cache WHERE module_id = ? AND file_path = ? AND language = ?",
                        (module_id, fpath, target_lang),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        skipped += 1
                        quality_scores[fpath] = existing["quality_score"]
                        continue

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO module_translation_cache
                        (id, module_id, file_path, language,
                         translated_content, source_hash, quality_score,
                         generated_at, generated_by, approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{module_id}:{fpath}:{target_lang}",
                        module_id,
                        fpath,
                        target_lang,
                        None,
                        source_hash,
                        0.0,
                        datetime.now(UTC).isoformat(),
                        "system",
                        0,
                    ),
                )
                translated += 1
                quality_scores[fpath] = 0.0

            conn.commit()
            conn.close()

            status = "ok" if translated > 0 else "partial"
            return TranslationResult(
                module_id=module_id,
                target_language=target_lang,
                files_translated=translated,
                files_skipped=skipped,
                quality_scores=quality_scores,
                status=status,
            )

        except sqlite3.Error as e:
            return TranslationResult(
                module_id=module_id,
                target_language=target_lang,
                status="error",
                errors=[str(e)],
            )

    def _dir_to_info(self, module_dir: Path) -> ModuleInfo | None:
        """Dir to info the instance."""
        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        file_count = 0
        profile_preview = None

        profile_file = manifest_data.get("profile_file")
        profile_format = manifest_data.get("profile_format")
        if profile_file:
            profile_path = module_dir / profile_file
            if profile_path.exists():
                file_count = 1
                try:
                    content = profile_path.read_text(encoding="utf-8")
                    if profile_format == "yaml":
                        profile_preview = yaml.safe_load(content)
                    elif profile_format == "json":
                        profile_preview = json.loads(content)
                    elif profile_format == "markdown":
                        profile_preview = {"content": content[:500]}
                except Exception:
                    pass
        else:
            file_count = sum(1 for f in manifest_data.get("files", []) if (module_dir / f["path"]).exists())

        db_info = self._get_db_module_info(manifest_data["module_id"])
        parent = parent_dir_name(module_dir, self.modules_dir)
        module_id = manifest_data.get("module_id", module_dir.name)

        # Parse manifest timestamps, fall back to DB timestamps
        manifest_created = manifest_data.get("created_at")
        manifest_updated = manifest_data.get("updated_at")
        try:
            from datetime import datetime

            manifest_created = datetime.fromisoformat(manifest_created) if manifest_created else None
            manifest_updated = datetime.fromisoformat(manifest_updated) if manifest_updated else None
        except (ValueError, TypeError):
            manifest_created = None
            manifest_updated = None

        return ModuleInfo(
            module_id=module_id,
            name=manifest_data.get("name", {}),
            description=manifest_data.get("description", {}),
            version=manifest_data.get("version", "0.0.0"),
            type=manifest_data.get("type") or derive_module_type(parent, module_id),
            category=manifest_data.get("category") or derive_module_category(parent),
            author=manifest_data.get("author", {}),
            license=manifest_data.get("license", "CC-BY-4.0"),
            tags=manifest_data.get("tags", []),
            language=manifest_data.get("language", "en"),
            checksum=manifest_data.get("checksum", ""),
            role=manifest_data.get("role"),
            installed=True,
            enabled=bool(db_info.get("enabled", False)) if db_info else False,
            installed_at=db_info.get("installed_at") if db_info else None,
            created_at=manifest_created,
            updated_at=manifest_updated or (db_info.get("updated_at") if db_info else None),
            dependencies=manifest_data.get("dependencies", {}),
            file_count=file_count,
            profile_preview=profile_preview,
        )

    def _update_manifest_checksum(self, module_dir: Path, manifest: dict) -> None:
        """Update manifest checksum the instance."""
        import hashlib

        manifest_path = module_dir / "manifest.json"
        profile_file = manifest.get("profile_file")
        if profile_file:
            profile_path = module_dir / profile_file
            if profile_path.exists():
                content = profile_path.read_bytes()
                manifest["checksum"] = hashlib.sha256(content).hexdigest()

        manifest["updated_at"] = datetime.now(UTC).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def _get_db_module_info(self, module_id: str) -> dict[str, Any] | None:
        """Return (or lazily create) db module info."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT enabled, installed_at, updated_at, version, checksum FROM module_registry WHERE id = ?",
                (module_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return dict(row)
        except sqlite3.Error as e:
            logger.warning("Failed to read module registry for %s: %s", module_id, e)
        return None

    def _get_db_status_map(self) -> dict[str, dict[str, Any]]:
        """Return (or lazily create) db status map."""
        result: dict[str, dict[str, Any]] = {}
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, type, category, version, "
                "author_json, license, checksum, installed_at, updated_at, "
                "enabled, source_schema, tags_json, dependencies "
                "FROM module_registry"
            )
            for row in cursor.fetchall():
                raw_name = row["name"] or ""
                try:
                    parsed_name = json.loads(raw_name)
                except (json.JSONDecodeError, TypeError):
                    parsed_name = raw_name
                result[row["id"]] = {
                    "name": parsed_name,
                    "description": row["description"] or "",
                    "type": row["type"] or "custom",
                    "category": row["category"] or "custom",
                    "version": row["version"] or "0.0.0",
                    "author": json.loads(row["author_json"] or "{}"),
                    "license": row["license"] or "CC-BY-4.0",
                    "checksum": row["checksum"] or "",
                    "installed_at": row["installed_at"],
                    "updated_at": row["updated_at"],
                    "enabled": bool(row["enabled"]) if "enabled" in row.keys() else False,
                    "tags": json.loads(row["tags_json"] or "[]"),
                    "dependencies": json.loads(row["dependencies"] or "{}"),
                }
            conn.close()
        except sqlite3.Error as e:
            logger.error("Failed to read module registry: %s", e)
        return result
