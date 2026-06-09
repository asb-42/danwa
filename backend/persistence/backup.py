"""Backup-Service — erstellt, verwaltet und validiert Backup-Archive."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.config import settings as app_settings

logger = logging.getLogger(__name__)

# ── Standard-Include-Pfade ──────────────────────────────────────────────
INCLUDE_PATHS: list[str] = [
    # ── Multi-tenant data (JSON file tree) ──────────────────────────────
    "data/projects",  # legacy project store
    "data/tenants",  # tenant-cased structure (cases, tags, debates, DMS)
    # ── SQLite databases ───────────────────────────────────────────────
    "data/auth.db",  # users, tenants, memberships
    "data/audit.db",  # audit trail
    "data/a2a_tasks.db",  # A2A task queue
    "data/blueprints.db",  # blueprints & workflow templates
    "data/modules.db",  # module registry
    "data/profiles.db",  # profile configurations
    # ── i18n translations ──────────────────────────────────────────────
    "data/i18n",  # UI translation database
    # ── Application config ─────────────────────────────────────────────
    "config/settings.yaml",
    "config/a2a.json",
    "config/llm_profiles.yaml",
]

# ── Standard-Exclude-Muster (relativ zu Projekt-Root) ───────────────────
EXCLUDE_PATTERNS: list[str] = [
    ".git/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    "logs/",
    "memory/",
    ".env",
    "frontend/dist/",
    "backups/",  # Backups nicht rekursiv sichern
    ".idea/",
    ".vscode/",
    "*.tmp",
    "*.bak",
    "*.swp",
    ".DS_Store",
    "Thumbs.db",
]


class BackupResult:
    """Ergebnis einer Backup-Erstellung."""

    def __init__(
        self,
        backup_id: str,
        path: str,
        size_bytes: int,
        file_count: int,
        created_at: datetime,
        sha256: str,
        duration_seconds: float,
    ):
        """Initialise BackupResult."""
        self.backup_id = backup_id
        self.path = path
        self.size_bytes = size_bytes
        self.file_count = file_count
        self.created_at = created_at
        self.sha256 = sha256
        self.duration_seconds = duration_seconds

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "backup_id": self.backup_id,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "created_at": self.created_at.isoformat(),
            "sha256": self.sha256,
            "duration_seconds": round(self.duration_seconds, 3),
        }


class BackupMetadata:
    """Metadaten eines Backups."""

    def __init__(
        self,
        backup_id: str,
        created_at: datetime,
        app_version: str,
        commit_hash: str,
        file_count: int,
        size_bytes: int,
        trigger: str,
        sha256: str,
    ):
        """Initialise BackupMetadata."""
        self.backup_id = backup_id
        self.created_at = created_at
        self.app_version = app_version
        self.commit_hash = commit_hash
        self.file_count = file_count
        self.size_bytes = size_bytes
        self.trigger = trigger
        self.sha256 = sha256

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at.isoformat(),
            "app_version": self.app_version,
            "commit_hash": self.commit_hash,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "trigger": self.trigger,
            "sha256": self.sha256,
        }


class VerificationResult:
    """Ergebnis einer Integritätsprüfung."""

    def __init__(self, valid: bool, errors: list[str], file_count_verified: int):
        """Initialise VerificationResult."""
        self.valid = valid
        self.errors = errors
        self.file_count_verified = file_count_verified

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "valid": self.valid,
            "errors": self.errors,
            "file_count_verified": self.file_count_verified,
        }


class RestoreResult:
    """Ergebnis einer Wiederherstellung."""

    def __init__(self, success: bool, message: str, restored_files: int = 0):
        """Initialise RestoreResult."""
        self.success = success
        self.message = message
        self.restored_files = restored_files


class BackupService:
    """Erstellt, verwaltet und validiert Backup-Archive."""

    BACKUP_DIR = Path("backups")

    def __init__(self, *, include_paths: list[str] | None = None, settings: Settings | None = None, project_root: Path | None = None):
        """Initialise BackupService."""
        self.include_paths = include_paths or INCLUDE_PATHS
        self.settings = settings or app_settings
        self._project_root = project_root

    def _should_exclude(self, rel_path: str) -> bool:
        """Prüft, ob ein relativer Pfad ausgeschlossen werden soll."""
        for pattern in EXCLUDE_PATTERNS:
            if pattern.endswith("/"):
                if rel_path.startswith(pattern) or f"/{pattern}" in rel_path:
                    return True
            elif "*" in pattern:
                import fnmatch

                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                    return True
            else:
                if rel_path == pattern or rel_path.startswith(pattern + "/"):
                    return True
        return False

    @staticmethod
    def _sha256_file(filepath: Path) -> str:
        """Berechnet SHA-256 einer Datei."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        """Berechnet SHA-256 von Bytes."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _get_commit_hash() -> str:
        """Versucht, den aktuellen Git-Commit-Hash zu ermitteln."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    @staticmethod
    def _get_db_schema_version(db_path: Path) -> str:
        """Liest die Schema-Version aus einer SQLite-DB."""
        if not db_path.exists():
            return "n/a"
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("PRAGMA user_version")
            version = cursor.fetchone()[0]
            conn.close()
            return f"v{version}"
        except Exception:
            return "unknown"

    def create_backup(self, trigger: str = "manual") -> BackupResult:
        """Erstellt ein ZIP-Backup mit Zeitstempel und Checksummen.

        Args:
            trigger: 'manual' oder 'shutdown'

        Returns:
            BackupResult mit Metadaten zur erstellten Datei
        """
        import time

        start_time = time.monotonic()
        project_root = self._project_root or Path(__file__).resolve().parent.parent.parent
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC)
        timestamp_str = timestamp.strftime("%Y-%m-%dT%H-%M-%SZ")
        backup_filename = f"danwa-backup-{timestamp_str}.zip"
        backup_path = self.BACKUP_DIR / backup_filename

        files_added: list[str] = []
        file_hashes: dict[str, str] = {}
        total_bytes = 0

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path_str in self.include_paths:
                abs_path = project_root / rel_path_str
                if not abs_path.exists():
                    logger.debug("Pfad nicht gefunden, übersprungen: %s", rel_path_str)
                    continue

                if abs_path.is_file():
                    if self._should_exclude(rel_path_str):
                        continue
                    data = abs_path.read_bytes()
                    zf.writestr(rel_path_str, data)
                    files_added.append(rel_path_str)
                    file_hashes[rel_path_str] = self._sha256_bytes(data)
                    total_bytes += len(data)

                elif abs_path.is_dir():
                    for root, _dirs, files in os.walk(abs_path):
                        root_path = Path(root)
                        for fname in files:
                            fpath = root_path / fname
                            try:
                                rel = str(fpath.relative_to(project_root))
                            except ValueError:
                                continue
                            if self._should_exclude(rel):
                                continue
                            try:
                                data = fpath.read_bytes()
                                # Pfad innerhalb des ZIP relativ zum Projekt-Root
                                zf.writestr(rel, data)
                                files_added.append(rel)
                                file_hashes[rel] = self._sha256_bytes(data)
                                total_bytes += len(data)
                            except OSError as exc:
                                logger.warning("Datei konnte nicht gelesen werden: %s — %s", fpath, exc)

            # Metadata erzeugen und ins ZIP aufnehmen
            commit_hash = self._get_commit_hash()
            db_schema_versions = {
                "audit.db": self._get_db_schema_version(project_root / "data" / "audit.db"),
                "blueprints.db": self._get_db_schema_version(project_root / "data" / "blueprints.db"),
            }
            metadata = {
                "version": 1,
                "app_version": self.settings.app_version,
                "commit_hash": commit_hash,
                "created_at": timestamp.isoformat(),
                "created_by": "api-endpoint",
                "trigger": trigger,
                "file_count": len(files_added),
                "total_bytes": total_bytes,
                "paths_included": self.include_paths,
                "db_schema_versions": db_schema_versions,
            }
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))

            # SHA-256SUMS-Datei
            sums_lines = [f"{h}  {f}" for f, h in sorted(file_hashes.items())]
            sums_text = "\n".join(sums_lines) + "\n"
            zf.writestr("SHA-256SUMS", sums_text)

        # ZIP-Checksumme
        zip_hash = self._sha256_file(backup_path)

        duration = time.monotonic() - start_time
        logger.info(
            "Backup erstellt: %s (%d Dateien, %d Bytes, %.2fs)",
            backup_path.name,
            len(files_added),
            total_bytes,
            duration,
        )

        return BackupResult(
            backup_id=backup_filename,
            path=str(backup_path),
            size_bytes=total_bytes,
            file_count=len(files_added),
            created_at=timestamp,
            sha256=zip_hash,
            duration_seconds=duration,
        )

    def list_backups(self) -> list[BackupMetadata]:
        """Listet alle verfügbaren Backups, sortiert nach Datum (neueste zuerst)."""
        if not self.BACKUP_DIR.exists():
            return []

        results: list[BackupMetadata] = []
        for fpath in sorted(self.BACKUP_DIR.glob("*.zip"), reverse=True):
            try:
                with zipfile.ZipFile(fpath, "r") as zf:
                    metadata_str = zf.read("metadata.json").decode("utf-8")
                    meta = json.loads(metadata_str)

                mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=UTC)
                results.append(
                    BackupMetadata(
                        backup_id=fpath.name,
                        created_at=mtime,
                        app_version=meta.get("app_version", "?"),
                        commit_hash=meta.get("commit_hash", "?"),
                        file_count=meta.get("file_count", 0),
                        size_bytes=fpath.stat().st_size,
                        trigger=meta.get("trigger", "unknown"),
                        sha256=self._sha256_file(fpath),
                    )
                )
            except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
                logger.warning("Backup konnte nicht gelesen werden (%s): %s", fpath.name, exc)
                continue

        return results

    def get_backup_file_list(self, backup_id: str) -> list[str]:
        """Gibt die Liste der in einem Backup enthaltenen Dateien zurück."""
        backup_path = self.BACKUP_DIR / backup_id
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup nicht gefunden: {backup_id}")

        with zipfile.ZipFile(backup_path, "r") as zf:
            return [name for name in zf.namelist() if not name.endswith("/")]

    def verify_backup(self, backup_id: str) -> VerificationResult:
        """Prüft die Integrität eines Backups (ZIP-Checksum + SHA-256SUMS)."""
        backup_path = self.BACKUP_DIR / backup_id
        errors: list[str] = []
        file_count = 0

        if not backup_path.exists():
            return VerificationResult(
                valid=False,
                errors=[f"Backup nicht gefunden: {backup_id}"],
                file_count_verified=0,
            )

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                # Test-Integrität des ZIP-Archivs
                bad_file = zf.testzip()
                if bad_file:
                    errors.append(f"Beschädigte Datei im ZIP: {bad_file}")

                # SHA-256SUMS verifizieren
                try:
                    sums_content = zf.read("SHA-256SUMS").decode("utf-8")
                except KeyError:
                    errors.append("SHA-256SUMS nicht im Backup gefunden")
                    sums_content = ""

                expected_hashes: dict[str, str] = {}
                for line in sums_content.strip().splitlines():
                    parts = line.strip().split("  ", 1)
                    if len(parts) == 2:
                        expected_hashes[parts[1]] = parts[0]

                for name in zf.namelist():
                    if name.endswith("/") or name in ("metadata.json", "SHA-256SUMS"):
                        continue
                    file_count += 1
                    data = zf.read(name)
                    actual_hash = self._sha256_bytes(data)
                    if name in expected_hashes and expected_hashes[name] != actual_hash:
                        errors.append(f"Hash-Mismatch: {name} (erwartet {expected_hashes[name]}, tatsächlich {actual_hash})")

                # metadata.json prüfen
                try:
                    meta_str = zf.read("metadata.json").decode("utf-8")
                    json.loads(meta_str)
                except KeyError:
                    errors.append("metadata.json nicht im Backup gefunden")
                except json.JSONDecodeError:
                    errors.append("metadata.json ist kein gültiges JSON")

        except zipfile.BadZipFile as exc:
            errors.append(f"Ungültiges ZIP-Archiv: {exc}")
        except Exception as exc:
            errors.append(f"Fehler bei Verifizierung: {exc}")

        return VerificationResult(
            valid=len(errors) == 0,
            errors=errors,
            file_count_verified=file_count,
        )

    @staticmethod
    def restore(backup_path: Path) -> RestoreResult:
        """Entpackt und stellt Daten wieder her.

        ⚠️ VORSICHT: Überschreibt vorhandene Daten!
        ⚠️ Die Applikation muss vor dem Restore gestoppt sein.

        Args:
            backup_path: Pfad zur ZIP-Datei

        Returns:
            RestoreResult
        """
        if not backup_path.exists():
            return RestoreResult(
                success=False,
                message=f"Backup nicht gefunden: {backup_path}",
            )

        project_root = backup_path.parent.parent
        restored_count = 0
        errors: list[str] = []

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                # Zuerst Integrität prüfen
                bad_file = zf.testzip()
                if bad_file:
                    return RestoreResult(
                        success=False,
                        message=f"Beschädigtes ZIP: {bad_file}",
                    )

                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    # Sicherstellen, dass der Pfad innerhalb des Projekt-Roots bleibt
                    target = project_root / name
                    if not str(target.resolve()).startswith(str(project_root.resolve())):
                        errors.append(f"Pfad außerhalb des Projekt-Roots übersprungen: {name}")
                        continue
                    try:
                        data = zf.read(name)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        restored_count += 1
                    except OSError as exc:
                        errors.append(f"Fehler beim Wiederherstellen von {name}: {exc}")

            if errors:
                return RestoreResult(
                    success=False,
                    message=f"Restore mit Fehlern abgeschlossen: {len(errors)} Fehler",
                    restored_files=restored_count,
                )
            return RestoreResult(
                success=True,
                message=f"Restore abgeschlossen: {restored_count} Dateien wiederhergestellt",
                restored_files=restored_count,
            )
        except zipfile.BadZipFile as exc:
            return RestoreResult(
                success=False,
                message=f"Ungültiges ZIP-Archiv: {exc}",
            )
        except Exception as exc:
            return RestoreResult(
                success=False,
                message=f"Restore fehlgeschlagen: {exc}",
            )
