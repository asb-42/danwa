"""Module Installer — handles installation, uninstallation, and updates.

This module provides the core installation logic for Danwa modules,
including directory-based and URL-based installation, uninstallation,
update, and rollback capabilities.

All database operations use fresh connections with WAL mode to avoid
locking issues. INSERT OR REPLACE is used for idempotent writes.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from backend.blueprints.migrations import run_migrations
from backend.modules.models import (
    InstallationReport,
    UninstallationReport,
    ValidationIssue,
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
UI_I18N_DIR = ROOT / "data" / "i18n"
UI_I18N_DB = UI_I18N_DIR / "ui_translations.db"


class InstallationError(Exception):
    """Raised when module installation fails."""


class UninstallationError(Exception):
    """Raised when module uninstallation fails."""


class ModuleInstaller:
    """Handles installation, uninstallation, and updating of Danwa modules."""

    def __init__(
        self,
        modules_dir: Path | str = MODULES_DIR,
        db_path: Path | str = DEFAULT_DB,
    ):
        """Initialise ModuleInstaller."""
        self.modules_dir = Path(modules_dir)
        self.modules_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self.validator = ModuleValidator(self.modules_dir)

    def _get_db(self) -> sqlite3.Connection:
        """Get a fresh database connection with WAL mode enabled."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(self.db_path)
        return conn

    def _register_in_db(self, module_id: str, manifest: dict[str, Any]) -> int:
        """Register a module and its files in the database.

        Returns the number of DB entries created.
        """
        db_entries = 0
        conn = self._get_db()
        cursor = conn.cursor()
        now = datetime.now(UTC).isoformat()
        checksum = manifest.get("checksum", "")
        try:
            # Preserve existing enabled state on re-install/update
            existing = cursor.execute(
                "SELECT enabled FROM module_registry WHERE id = ?",
                (module_id,),
            ).fetchone()
            enabled_value = existing["enabled"] if existing else 1

            cursor.execute(
                """
                INSERT OR REPLACE INTO module_registry
                    (id, name, description, type, category, version,
                     author_json, license, checksum, installed_at,
                     updated_at, enabled, source_url, source_schema,
                     tags_json, dependencies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    module_id,
                    json.dumps(manifest.get("name", {})),
                    json.dumps(manifest.get("description", {})),
                    manifest.get("type") or derive_module_type(parent_dir_name(self.modules_dir / module_id, self.modules_dir), module_id),
                    manifest.get("category") or derive_module_category(parent_dir_name(self.modules_dir / module_id, self.modules_dir)),
                    manifest.get("version", "0.0.0"),
                    json.dumps(manifest.get("author", {})),
                    manifest.get("license", "CC-BY-4.0"),
                    checksum,
                    now,
                    now,
                    enabled_value,
                    None,
                    manifest.get("schema_version", "1.0.0"),
                    json.dumps(manifest.get("tags", [])),
                    json.dumps(manifest.get("dependencies", {})),
                ),
            )
            db_entries += 1

            # Import files into translation cache
            for file_entry in manifest.get("files", []):
                fpath = self.modules_dir / module_id / file_entry["path"]
                if not fpath.exists():
                    continue
                content = fpath.read_text(encoding="utf-8")
                lang = file_entry.get("language", "en")

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO module_translation_cache
                        (id, module_id, file_path, source_language, language,
                         source_hash, source_content, translated_content,
                         quality_score, generated_at, approved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{module_id}:{file_entry['path']}:{lang}",
                        module_id,
                        file_entry["path"],
                        "en",
                        lang,
                        file_entry.get("checksum", ""),
                        content,
                        content,
                        1.0,
                        now,
                        1,
                    ),
                )
                db_entries += 1

            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Database error during registration of %s: %s", module_id, e)
            raise
        finally:
            conn.close()
        return db_entries

    def _register_ui_strings_in_db(self, module_id: str, module_dir: Path, manifest: dict[str, Any]) -> int:
        """Register UI strings from a language-pack module into ui_translations.db.

        Reads ui_strings.json from the module directory and inserts entries
        with namespace='langpack:{module_id}'.

        Returns the number of UI string entries created.
        """
        ui_strings_file = manifest.get("profile_file") or "ui_strings.json"
        ui_strings_path = module_dir / ui_strings_file
        if not ui_strings_path.exists():
            logger.warning("Language pack %s: ui_strings file not found at %s", module_id, ui_strings_path)
            return 0

        try:
            ui_strings = json.loads(ui_strings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Language pack %s: failed to parse ui_strings.json: %s", module_id, e)
            return 0

        if not isinstance(ui_strings, dict):
            logger.error("Language pack %s: ui_strings.json must be a key-value object", module_id)
            return 0

        locale = manifest.get("language", "en")
        namespace = f"langpack:{module_id}"
        now = datetime.now(UTC).isoformat()

        UI_I18N_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(UI_I18N_DB), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        entries = 0
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    locale TEXT NOT NULL,
                    value TEXT NOT NULL,
                    namespace TEXT DEFAULT 'global',
                    source TEXT DEFAULT 'manual',
                    confidence REAL,
                    version INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(key, locale, namespace)
                )
            """)

            for key, value in ui_strings.items():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO ui_translations
                        (key, locale, value, namespace, source, version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (key, locale, value, namespace, "bundle_imported", now, now),
                )
                entries += 1

            conn.commit()
            logger.info(
                "Language pack %s: registered %d UI strings in namespace '%s'",
                module_id,
                entries,
                namespace,
            )
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Database error during UI string registration for %s: %s", module_id, e)
            raise
        finally:
            conn.close()
        return entries

    def _uninstall_ui_strings(self, module_id: str) -> int:
        """Remove UI strings belonging to a language-pack module.

        Deletes all entries with namespace='langpack:{module_id}' from ui_translations.db.

        Returns the number of entries removed.
        """
        namespace = f"langpack:{module_id}"
        if not UI_I18N_DB.exists():
            return 0

        conn = sqlite3.connect(str(UI_I18N_DB), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        removed = 0
        try:
            cursor.execute(
                "DELETE FROM ui_translations WHERE namespace = ?",
                (namespace,),
            )
            removed = cursor.rowcount
            conn.commit()
            logger.info(
                "Language pack %s: removed %d UI strings from namespace '%s'",
                module_id,
                removed,
                namespace,
            )
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("Database error during UI string removal for %s: %s", module_id, e)
        finally:
            conn.close()
        return removed

    def install_from_directory(
        self,
        module_dir: Path | str,
        overwrite: bool = False,
    ) -> InstallationReport:
        """Install a module from a local directory.

        Args:
            module_dir: Path to the module directory (must contain manifest.json)
            overwrite: If True, overwrite existing module with same ID

        Returns:
            InstallationReport with status and details
        """
        module_dir = Path(module_dir)
        manifest_path = module_dir / "manifest.json"

        if not manifest_path.exists():
            return InstallationReport(
                status="error",
                module_id="<unknown>",
                version="0.0.0",
                errors=[f"Manifest not found: {manifest_path}"],
            )

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return InstallationReport(
                status="error",
                module_id="<unknown>",
                version="0.0.0",
                errors=[f"Failed to parse manifest: {e}"],
            )

        # Validate manifest
        validation = self.validator.validate_manifest(manifest_data)
        if not validation.valid:
            return InstallationReport(
                status="error",
                module_id=manifest_data.get("module_id", "<unknown>"),
                version=manifest_data.get("version", "0.0.0"),
                errors=[i.message for i in validation.issues if i.severity == "error"],
                warnings=[i.message for i in validation.issues if i.severity == "warning"],
            )

        # Verify checksums
        checksum_ok, checksum_errors = self.validator.verify_checksums(module_dir, manifest_data)
        if not checksum_ok:
            if not overwrite:
                return InstallationReport(
                    status="error",
                    module_id=manifest_data["module_id"],
                    version=manifest_data["version"],
                    errors=checksum_errors + ["Use overwrite=True to force installation"],
                    checksum_valid=False,
                )
            validation.issues.extend(ValidationIssue(severity="warning", field="checksum", message=e) for e in checksum_errors)

        module_id = manifest_data["module_id"]
        target_dir = self.modules_dir / module_id

        # Determine if this is an in-place install (source == target)
        source_resolved = str(module_dir.resolve())
        target_resolved = str(target_dir.resolve())
        is_in_place = source_resolved == target_resolved

        # Check existing installation via DB
        existing_manifest = self._read_installed_manifest(module_id)
        if existing_manifest and not overwrite:
            existing_ver = existing_manifest.get("version", "0.0.0")
            new_ver = manifest_data["version"]
            if existing_ver == new_ver:
                return InstallationReport(
                    status="skipped",
                    module_id=module_id,
                    version=new_ver,
                    warnings=[f"Module already installed at version {existing_ver}. Use overwrite=True to force."],
                )

        # Backup existing version (skip if source==target to avoid destruction)
        if not is_in_place and existing_manifest and target_dir.exists():
            existing_ver = existing_manifest.get("version", "0.0.0")
            backup_dir = self.modules_dir / f"{module_id}.bak.{existing_ver}"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.move(str(target_dir), str(backup_dir))

        # Copy files
        target_dir.mkdir(parents=True, exist_ok=True)
        files_installed = 0
        files_failed = 0

        for file_entry in manifest_data.get("files", []):
            src = module_dir / file_entry["path"]
            dst = target_dir / file_entry["path"]
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
                files_installed += 1
            except (OSError, shutil.Error) as e:
                files_failed += 1
                validation.issues.append(
                    ValidationIssue(
                        severity="error",
                        field=f"files[{file_entry['path']}]",
                        message=f"Failed to copy: {e}",
                    )
                )

        # Register in database
        db_entries_created = 0
        try:
            db_entries_created = self._register_in_db(module_id, manifest_data)
        except sqlite3.Error as e:
            return InstallationReport(
                status="partial",
                module_id=module_id,
                version=manifest_data.get("version", "0.0.0"),
                files_installed=files_installed,
                files_failed=files_failed,
                errors=[f"Database error: {e}"],
                warnings=[i.message for i in validation.issues if i.severity == "warning"],
            )

        # For language-pack modules, also register UI strings
        ui_entries_created = 0
        derived_t = manifest_data.get("type") or derive_module_type(parent_dir_name(module_dir, self.modules_dir), module_id)
        if derived_t == "language-pack":
            try:
                ui_entries_created = self._register_ui_strings_in_db(module_id, module_dir, manifest_data)
            except sqlite3.Error as e:
                return InstallationReport(
                    status="partial",
                    module_id=module_id,
                    version=manifest_data.get("version", "0.0.0"),
                    files_installed=files_installed,
                    files_failed=files_failed,
                    errors=[f"UI translation database error: {e}"],
                    warnings=[i.message for i in validation.issues if i.severity == "warning"],
                )

        # Copy manifest.json to target directory (only for cross-directory installs)
        if not is_in_place:
            manifest_src = module_dir / "manifest.json"
            if manifest_src.exists():
                shutil.copy2(str(manifest_src), str(target_dir / "manifest.json"))

        logger.info(
            "Installed module %s v%s (%d files, %d DB entries, %d UI strings)",
            module_id,
            manifest_data.get("version"),
            files_installed,
            db_entries_created,
            ui_entries_created,
        )

        return InstallationReport(
            status="ok",
            module_id=module_id,
            version=manifest_data.get("version", "0.0.0"),
            files_installed=files_installed,
            files_failed=files_failed,
            db_entries_created=db_entries_created + ui_entries_created,
            warnings=[i.message for i in validation.issues if i.severity == "warning"],
            checksum=manifest_data.get("checksum", ""),
            installed_at=datetime.now(UTC),
        )

    def install_from_url(self, url: str) -> InstallationReport:
        """Install a module from a ZIP URL.

        Args:
            url: URL to a ZIP archive containing the module

        Returns:
            InstallationReport with status and details
        """
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
        except Exception as e:
            return InstallationReport(
                status="error",
                module_id="<unknown>",
                version="0.0.0",
                errors=[f"Failed to download: {e}"],
            )

        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                tmp_dir = self.modules_dir / ".tmp_install"
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                tmp_dir.mkdir(parents=True, exist_ok=True)
                zf.extractall(tmp_dir)

                manifest_paths = list(tmp_dir.rglob("manifest.json"))
                if not manifest_paths:
                    return InstallationReport(
                        status="error",
                        module_id="<unknown>",
                        version="0.0.0",
                        errors=["No manifest.json found in ZIP"],
                    )

                module_dir = manifest_paths[0].parent
                return self.install_from_directory(module_dir)

        except zipfile.BadZipFile as e:
            return InstallationReport(
                status="error",
                module_id="<unknown>",
                version="0.0.0",
                errors=[f"Invalid ZIP file: {e}"],
            )
        except Exception as e:
            return InstallationReport(
                status="error",
                module_id="<unknown>",
                version="0.0.0",
                errors=[f"Installation failed: {e}"],
            )

    def uninstall(self, module_id: str, force: bool = False) -> UninstallationReport:
        """Uninstall a module.

        Args:
            module_id: The module ID to uninstall
            force: If True, skip dependency checks

        Returns:
            UninstallationReport with status and details
        """
        if not force:
            blockers = self._check_dependents(module_id)
            if blockers:
                return UninstallationReport(
                    status="blocked",
                    module_id=module_id,
                    blocked_by=blockers,
                )

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
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM module_translation_cache WHERE module_id = ?", (module_id,))
            db_entries_removed += cursor.rowcount
            cursor.execute("DELETE FROM module_registry WHERE id = ?", (module_id,))
            db_entries_removed += cursor.rowcount
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Database error during uninstall of %s: %s", module_id, e)
            return UninstallationReport(
                status="error",
                module_id=module_id,
                errors=[f"Database error: {e}"],
            )

        # Remove UI strings for language-pack modules
        ui_entries_removed = self._uninstall_ui_strings(module_id)
        db_entries_removed += ui_entries_removed

        logger.info(
            "Uninstalled module %s (%d files, %d DB entries, %d UI strings)",
            module_id,
            files_removed,
            db_entries_removed,
            ui_entries_removed,
        )

        return UninstallationReport(
            status="ok",
            module_id=module_id,
            files_removed=files_removed,
            db_entries_removed=db_entries_removed,
        )

    def update(self, module_id: str) -> InstallationReport:
        """Update a module to the latest available version.

        Currently re-installs from the local directory.
        Remote update support requires a registry URL.

        Args:
            module_id: The module ID to update

        Returns:
            InstallationReport with update results
        """
        module_dir = self.modules_dir / module_id
        if not module_dir.exists():
            return InstallationReport(
                status="error",
                module_id=module_id,
                version="0.0.0",
                errors=[f"Module directory not found: {module_dir}"],
            )

        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            return InstallationReport(
                status="error",
                module_id=module_id,
                version="0.0.0",
                errors=[f"No manifest.json in {module_dir}"],
            )

        return self.install_from_directory(module_dir, overwrite=True)

    def rollback(self, module_id: str, version: str) -> bool:
        """Rollback to a previous version from backup.

        Args:
            module_id: The module ID
            version: Target version to rollback to

        Returns:
            True if rollback succeeded
        """
        backup_dir = self.modules_dir / f"{module_id}.bak.{version}"
        if not backup_dir.exists():
            logger.warning("No backup found for %s version %s", module_id, version)
            return False

        target_dir = self.modules_dir / module_id
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.move(str(backup_dir), str(target_dir))

        # Re-register in DB
        manifest_path = target_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._register_in_db(module_id, manifest_data)
            except Exception as e:
                logger.error("Failed to re-register %s in DB: %s", module_id, e)

        logger.info("Rolled back %s to version %s", module_id, version)
        return True

    def _check_dependents(self, module_id: str) -> list[str]:
        """Check if other installed modules depend on this one.

        Args:
            module_id: The module to check

        Returns:
            List of module IDs that depend on this module
        """
        blockers: list[str] = []
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, dependencies FROM module_registry WHERE enabled = 1")
            for row in cursor.fetchall():
                deps_str = row["dependencies"] or "{}"
                try:
                    deps = json.loads(deps_str)
                    if module_id in deps:
                        blockers.append(row["id"])
                except json.JSONDecodeError:
                    continue
            conn.close()
        except sqlite3.Error as e:
            logger.warning(
                "Failed to check module blocker dependencies (module %s): %s",
                module_id,
                e,
            )
        return blockers

    def _read_installed_manifest(self, module_id: str) -> dict[str, Any] | None:
        """Read the manifest of an already installed module from the database."""
        try:
            conn = self._get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description, type, category, version, "
                "author_json, license, checksum, installed_at, updated_at, "
                "enabled, source_url, source_schema, tags_json, dependencies "
                "FROM module_registry WHERE id = ?",
                (module_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "module_id": row["id"],
                    "name": json.loads(row["name"] or "{}"),
                    "description": row["description"] or "",
                    "type": row["type"] or "custom",
                    "category": row["category"] or "custom",
                    "version": row["version"] or "0.0.0",
                    "author": json.loads(row["author_json"] or "{}"),
                    "license": row["license"] or "CC-BY-4.0",
                    "checksum": row["checksum"] or "",
                    "tags": json.loads(row["tags_json"] or "[]"),
                    "dependencies": json.loads(row["dependencies"] or "{}"),
                }
        except sqlite3.Error as e:
            logger.warning("Failed to read installed module manifest for %s: %s", module_id, e)
        return None
