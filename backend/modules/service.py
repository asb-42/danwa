"""Module Service — discover, list, and manage installed/available modules."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.modules.installer import ModuleInstaller
from backend.modules.models import (
    InstallationReport,
    ModuleInfo,
    ModuleManifest,
    ModuleType,
    ModuleCategory,
    TranslationResult,
    UninstallationReport,
    ValidationResult,
)
from backend.modules.validation import ModuleValidator

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = ROOT / "modules"
DEFAULT_DB = ROOT / "data" / "blueprints.db"


class ModuleService:
    """Main service for discovering, listing, and managing Danwa modules."""

    def __init__(
        self,
        modules_dir: Path | str = MODULES_DIR,
        db_path: Path | str = DEFAULT_DB,
    ):
        self.modules_dir = Path(modules_dir)
        self.db_path = Path(db_path)
        self.validator = ModuleValidator(self.modules_dir)
        self.installer = ModuleInstaller(self.modules_dir, self.db_path)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_local(self) -> list[ModuleInfo]:
        """Scan the modules directory for installed modules.

        Returns:
            List of ModuleInfo for all discovered modules
        """
        modules: list[ModuleInfo] = []
        if not self.modules_dir.exists():
            return modules

        for module_dir in sorted(self.modules_dir.iterdir()):
            if not module_dir.is_dir():
                continue
            if module_dir.name.startswith("."):
                continue
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
        """Discover modules with DB status enrichment.

        Returns:
            List of dicts with module info + DB status
        """
        modules = self.discover_local()
        db_status = self._get_db_status_map()

        result = []
        for mod in modules:
            db_info = db_status.get(mod.module_id, {})
            result.append({
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
                "enabled": db_info.get("enabled", True),
                "installed_at": db_info.get("installed_at"),
                "updated_at": db_info.get("updated_at"),
                "dependencies": mod.dependencies,
                "file_count": mod.file_count,
            })

        # Also include DB-only modules (not on disk)
        for mid, db_info in db_status.items():
            if not any(m.module_id == mid for m in modules):
                result.append({
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
                    "updated_at": db_info.get("updated_at"),
                    "dependencies": db_info.get("dependencies", {}),
                    "file_count": db_info.get("file_count", 0),
                    "on_disk": False,
                })

        return result

    def get(self, module_id: str) -> ModuleInfo | None:
        """Get info for a single module by ID."""
        module_dir = self.modules_dir / module_id
        if module_dir.exists():
            return self._dir_to_info(module_dir)
        return None

    def list_all(self, category: str | None = None) -> list[ModuleInfo]:
        """List all installed modules, optionally filtered by category.

        Args:
            category: Filter by category (e.g. 'prompts', 'agents')

        Returns:
            List of ModuleInfo
        """
        modules = self.discover_local()
        if category:
            modules = [m for m in modules if m.category.value == category]
        return modules

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install(
        self,
        module_id: str,
        source: str = "local",
        source_url: str | None = None,
    ) -> InstallationReport:
        """Install a module.

        Args:
            module_id: The module ID to install
            source: "local" (from modules_dir) or "url"
            source_url: URL for remote installation (when source="url")

        Returns:
            InstallationReport
        """
        if source == "url" and source_url:
            return self.installer.install_from_url(source_url)
        else:
            module_dir = self.modules_dir / module_id
            if not module_dir.exists():
                raise FileNotFoundError(
                    f"Module directory not found: {module_dir}"
                )
            return self.installer.install_from_directory(module_dir)

    def uninstall(self, module_id: str, force: bool = False) -> UninstallationReport:
        """Uninstall a module.

        Args:
            module_id: The module ID to uninstall
            force: If True, ignore dependency checks

        Returns:
            UninstallationReport
        """
        if not force:
            return self.installer.uninstall(module_id)
        else:
            # Force: skip dependency check by directly removing
            return self._force_uninstall(module_id)

    def update(self, module_id: str) -> InstallationReport:
        """Update a module to the latest version.

        Args:
            module_id: The module ID to update

        Returns:
            InstallationReport
        """
        return self.installer.update(module_id)

    def _force_uninstall(self, module_id: str) -> UninstallationReport:
        """Force-uninstall a module, skipping dependency checks.

        Args:
            module_id: The module ID to uninstall

        Returns:
            UninstallationReport with status and details
        """
        target_dir = self.modules_dir / module_id
        files_removed = 0
        if target_dir.exists():
            for f in target_dir.rglob("*"):
                if f.is_file():
                    files_removed += 1
            shutil.rmtree(target_dir)

        # Remove backup directories for this module
        for bak in self.modules_dir.glob(f"{module_id}.bak.*"):
            if bak.is_dir():
                shutil.rmtree(bak)

        # Remove from database
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
                errors=[f"Database error: {e}"],
            )

        logger.info("Force-uninstalled module %s (%d files, %d DB entries)", module_id, files_removed, db_entries_removed)

        return UninstallationReport(
            status="ok",
            module_id=module_id,
            files_removed=files_removed,
            db_entries_removed=db_entries_removed,
        )

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate(
        self,
        module_id: str,
        target_lang: str,
        force: bool = False,
    ) -> TranslationResult:
        """Translate a module's content to a target language.

        This marks entries for translation; actual LLM-based translation
        would be triggered asynchronously (Sprint 3).

        Args:
            module_id: The module to translate
            target_lang: Target language code (e.g. "de")
            force: Force re-translation even if cache exists

        Returns:
            TranslationResult with status
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all files for this module
            cursor.execute(
                "SELECT file_path, source_hash FROM module_translation_cache "
                "WHERE module_id = ? AND language = 'en'",
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
                    # Check if translation already exists and is current
                    cursor.execute(
                        "SELECT quality_score FROM module_translation_cache "
                        "WHERE module_id = ? AND file_path = ? AND language = ?",
                        (module_id, fpath, target_lang),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        skipped += 1
                        quality_scores[fpath] = existing["quality_score"]
                        continue

                # Placeholder: mark as pending translation
                # (Actual LLM translation happens in Sprint 3)
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
                        None,  # Pending
                        source_hash,
                        0.0,
                        datetime.now(timezone.utc).isoformat(),
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

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _dir_to_info(self, module_dir: Path) -> ModuleInfo | None:
        """Convert a module directory to ModuleInfo."""
        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        # Count valid files
        file_count = sum(
            1 for f in manifest_data.get("files", [])
            if (module_dir / f["path"]).exists()
        )

        # Get DB status
        db_info = self._get_db_module_info(manifest_data["module_id"])

        return ModuleInfo(
            module_id=manifest_data.get("module_id", module_dir.name),
            name=manifest_data.get("name", {}),
            description=manifest_data.get("description", {}),
            version=manifest_data.get("version", "0.0.0"),
            type=manifest_data.get("type", "custom"),
            category=manifest_data.get("category", "custom"),
            author=manifest_data.get("author", {}),
            license=manifest_data.get("license", "CC-BY-4.0"),
            tags=manifest_data.get("tags", []),
            language=manifest_data.get("language", "en"),
            checksum=manifest_data.get("checksum", ""),
            installed=True,
            enabled=db_info.get("enabled", True) if db_info else True,
            installed_at=db_info.get("installed_at") if db_info else None,
            updated_at=db_info.get("updated_at") if db_info else None,
            dependencies=manifest_data.get("dependencies", {}),
            file_count=file_count,
        )

    def _get_db_module_info(self, module_id: str) -> dict[str, Any] | None:
        """Fetch module metadata from the database."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT enabled, installed_at, updated_at, version, checksum "
                "FROM module_registry WHERE id = ?",
                (module_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return dict(row)
        except sqlite3.Error:
            pass
        return None

    def _get_db_status_map(self) -> dict[str, dict[str, Any]]:
        """Get all module registry entries as a dict keyed by module_id."""
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
                result[row["id"]] = {
                    "name": json.loads(row["name"] or "{}"),
                    "description": row["description"] or "",
                    "type": row["type"] or "custom",
                    "category": row["category"] or "custom",
                    "version": row["version"] or "0.0.0",
                    "author": json.loads(row["author_json"] or "{}"),
                    "license": row["license"] or "CC-BY-4.0",
                    "checksum": row["checksum"] or "",
                    "installed_at": row["installed_at"],
                    "updated_at": row["updated_at"],
                    "enabled": bool(row["enabled"]) if "enabled" in row.keys() else True,
                    "tags": json.loads(row["tags_json"] or "[]"),
                    "dependencies": json.loads(row["dependencies"] or "{}"),
                }
            conn.close()
        except sqlite3.Error:
            pass
        return result
