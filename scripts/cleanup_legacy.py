#!/usr/bin/env python3
"""Cleanup-Skript für Legacy-Dateien.

Markiert veraltete Dateien in profiles/ mit DEPRECATED.txt-Markern
und kann sie optional in ein .deprecated/-Verzeichnis verschieben
oder endgültig löschen.

Plan: 014 §5.8

Usage:
    python scripts/cleanup_legacy.py              # Nur markieren
    python scripts/cleanup_legacy.py --dry-run    # Anzeigen, was gelöscht würde
    python scripts/cleanup_legacy.py --remove     # Dateien löschen
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanup_legacy")

ROOT = Path(__file__).resolve().parent.parent

# Legacy-Verzeichnisse, die bereits durch Module ersetzt wurden
LEGACY_DIRS = {
    "profiles/prompts": "modules/prompts-base",
    "profiles/agents": "modules/agents-base",
    "profiles/llm": "modules/llm-profiles",
    "profiles/workflow-variants": "modules/danma-workflow-variants",
    "profiles/argumentation-patterns": "modules/prompts-base",
    "templates": "modules/workflow-templates",
}

# Dateitypen, die als sicher zum Löschen gelten (keine Config/Keys)
SAFE_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}

DEPRECATED_CONTENT = """\
# DEPRECATED

Dieses Verzeichnis wurde am {timestamp} als veraltet markiert.
Die enthaltenen Daten wurden in das neue Modulsystem migriert:

  {new_module}

Diese Dateien werden vom System nicht mehr genutzt und können
zu einem späteren Zeitpunkt gelöscht werden.
"""


def list_legacy_files() -> list[dict]:
    """Listet alle Legacy-Dateien mit Metadaten."""
    files = []
    for legacy_rel, new_module in LEGACY_DIRS.items():
        legacy_path = ROOT / legacy_rel
        if not legacy_path.exists():
            continue
        for f in sorted(legacy_path.rglob("*")):
            if not f.is_file():
                continue
            if f.name == "DEPRECATED.txt":
                continue
            files.append(
                {
                    "path": str(f.relative_to(ROOT)),
                    "size": f.stat().st_size,
                    "extension": f.suffix,
                    "is_safe": f.suffix in SAFE_EXTENSIONS,
                    "new_module": new_module,
                }
            )
    return files


def mark_directory_as_deprecated(legacy_path: Path, new_module: str) -> bool:
    """Markiert ein Verzeichnis als DEPRECATED, falls nicht bereits geschehen."""
    deprecated_file = legacy_path / "DEPRECATED.txt"
    if deprecated_file.exists():
        return False
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = DEPRECATED_CONTENT.format(timestamp=timestamp, new_module=new_module)
    deprecated_file.write_text(content, encoding="utf-8")
    logger.info("Markiert als DEPRECATED: %s → %s", legacy_path, new_module)
    return True


def mark_subdir_deprecated(legacy_path: Path, new_module: str) -> int:
    """Markiert DEPRECATED.txt in allen Unterverzeichnissen."""
    count = 0
    for subdir in sorted(legacy_path.iterdir()):
        if not subdir.is_dir():
            continue
        deprecated_file = subdir / "DEPRECATED.txt"
        if not deprecated_file.exists():
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            content = DEPRECATED_CONTENT.format(timestamp=timestamp, new_module=new_module)
            deprecated_file.write_text(content, encoding="utf-8")
            logger.info("  Markiert: %s", subdir)
            count += 1
    return count


def do_mark():
    """Nur DEPRECATED-Marker setzen (sicherer Standard)."""
    logger.info("=== Legacy-Cleanup: Markieren ===")
    marked = 0
    for legacy_rel, new_module in LEGACY_DIRS.items():
        legacy_path = ROOT / legacy_rel
        if not legacy_path.exists():
            continue
        if mark_directory_as_deprecated(legacy_path, new_module):
            marked += 1
        if legacy_rel == "profiles/prompts":
            variants_dir = legacy_path / "variants"
            if variants_dir.exists():
                marked += mark_subdir_deprecated(variants_dir, new_module)
        elif legacy_rel == "profiles/argumentation-patterns":
            marked += mark_subdir_deprecated(legacy_path, new_module)
    logger.info("=== Fertig! %d Verzeichnisse als DEPRECATED markiert ===", marked)


def do_dry_run():
    """Anzeigen, was gelöscht werden würde."""
    files = list_legacy_files()
    safe = [f for f in files if f["is_safe"]]
    unsafe = [f for f in files if not f["is_safe"]]

    logger.info("=== Dry Run: %d Legacy-Dateien gefunden ===", len(files))
    logger.info("  Sicher zum Löschen: %d", len(safe))
    logger.info("  Überprüfung nötig:  %d", len(unsafe))
    logger.info("")

    if unsafe:
        logger.info("Dateien mit unbekannter Endung (müssen geprüft werden):")
        for f in unsafe:
            logger.info("  %s (%d bytes)", f["path"], f["size"])
        logger.info("")

    total_size = sum(f["size"] for f in files)
    logger.info("Gesamtgröße: %.1f KB", total_size / 1024)


def do_remove():
    """Legacy-Dateien löschen (mit Backup)."""
    files = list_legacy_files()
    if not files:
        logger.info("Keine Legacy-Dateien gefunden.")
        return

    # Backup erstellen
    backup_dir = ROOT / "backups" / "legacy-cleanup" / datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    safe = [f for f in files if f["is_safe"]]
    unsafe = [f for f in files if not f["is_safe"]]

    logger.info("=== Legacy-Cleanup: Entfernen ===")
    logger.info("Backup nach: %s", backup_dir.relative_to(ROOT))

    # Backup und Löschen der sicheren Dateien
    removed = 0
    for f in safe:
        src = ROOT / f["path"]
        dest = backup_dir / f["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        src.unlink()
        removed += 1
        logger.info("  Gelöscht: %s", f["path"])

    # Unsichere Dateien nur melden
    if unsafe:
        logger.warning("%d Dateien mit unbekannter Endung NICHT gelöscht:", len(unsafe))
        for f in unsafe:
            logger.warning("  %s", f["path"])

    # Manifest schreiben
    manifest = {
        "timestamp": datetime.now(UTC).isoformat(),
        "removed_count": removed,
        "skipped_count": len(unsafe),
        "backup_dir": str(backup_dir.relative_to(ROOT)),
        "files": [f["path"] for f in safe],
    }
    manifest_path = backup_dir / "cleanup-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("=== Fertig! %d Dateien gelöscht, %d übersprungen ===", removed, len(unsafe))
    logger.info("Backup: %s", manifest_path)


def main():
    parser = argparse.ArgumentParser(description="Legacy-Dateien bereinigen")
    parser.add_argument("--dry-run", action="store_true", help="Anzeigen, was gelöscht würde")
    parser.add_argument("--remove", action="store_true", help="Dateien tatsächlich löschen")
    args = parser.parse_args()

    if args.remove:
        answer = input("WARNUNG: Legacy-Dateien werden gelöscht (mit Backup). Fortfahren? [j/N] ")
        if answer.lower() != "j":
            logger.info("Abgebrochen.")
            return
        do_remove()
    elif args.dry_run:
        do_dry_run()
    else:
        do_mark()


if __name__ == "__main__":
    main()
