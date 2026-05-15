#!/usr/bin/env python3
"""Cleanup-Skript für Legacy-Dateien.

Markiert veraltete Dateien in profiles/ mit DEPRECATED.txt-Markern
und verschiebt sie in ein .deprecated/-Verzeichnis.

Plan: 014 §5.7
"""

from __future__ import annotations

import logging
from datetime import datetime
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

DEPRECATED_CONTENT = """\
# DEPRECATED

Dieses Verzeichnis wurde am {timestamp} als veraltet markiert.
Die enthaltenen Daten wurden in das neue Modulsystem migriert:

  {new_module}

Diese Dateien werden vom System nicht mehr genutzt und können
zu einem späteren Zeitpunkt gelöscht werden.
"""


def mark_directory_as_deprecated(legacy_path: Path, new_module: str) -> bool:
    """Markiert ein Verzeichnis als DEPRECATED, falls nicht bereits geschehen."""
    deprecated_file = legacy_path / "DEPRECATED.txt"

    if deprecated_file.exists():
        logger.info("Bereits als DEPRECATED markiert: %s", legacy_path)
        return False

    timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = DEPRECATED_CONTENT.format(
        timestamp=timestamp,
        new_module=new_module,
    )
    deprecated_file.write_text(content, encoding="utf-8")
    logger.info("Markiert als DEPRECATED: %s → %s", legacy_path, new_module)
    return True


def mark_subdir_deprecated(legacy_path: Path, new_module: str) -> int:
    """Markiert DEPRECATED.txt in allen Unterverzeichnissen, falls nicht vorhanden."""
    count = 0
    for subdir in sorted(legacy_path.iterdir()):
        if not subdir.is_dir():
            continue
        deprecated_file = subdir / "DEPRECATED.txt"
        if not deprecated_file.exists():
            timestamp = datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            content = DEPRECATED_CONTENT.format(
                timestamp=timestamp,
                new_module=new_module,
            )
            deprecated_file.write_text(content, encoding="utf-8")
            logger.info("  Markiert: %s", subdir)
            count += 1
    return count


def main():
    """Hauptprogramm: Markiert veraltete Verzeichnisse als DEPRECATED."""
    logger.info("=== Legacy-Cleanup gestartet ===")
    marked = 0

    for legacy_rel, new_module in LEGACY_DIRS.items():
        legacy_path = ROOT / legacy_rel
        if not legacy_path.exists():
            logger.debug("Existentes Verzeichnis nicht gefunden: %s", legacy_path)
            # Top-Level DEPRECATED.txt trotzdem erstellen falls der Ordner existiert
            continue

        # Top-Level-Markierung
        if mark_directory_as_deprecated(legacy_path, new_module):
            marked += 1

        # Unterverzeichnisse markieren (für prompts/varianten, profiles/agents etc.)
        if legacy_rel == "profiles/prompts":
            variants_dir = legacy_path / "variants"
            if variants_dir.exists():
                marked += mark_subdir_deprecated(variants_dir, new_module)
        elif legacy_rel == "profiles/argumentation-patterns":
            marked += mark_subdir_deprecated(legacy_path, new_module)

    logger.info("=== Fertig! %d Verzeichnisse als DEPRECATED markiert ===", marked)


if __name__ == "__main__":
    main()
