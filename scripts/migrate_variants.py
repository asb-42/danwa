#!/usr/bin/env python3
"""Migrationsskript: profiles/workflow-variants/ → modules/danma-workflow-variants/

Überträgt Workflow-Varianten aus dem Legacy-Verzeichnis in das
neue Modulsystem und aktualisiert die Manifest-Checksummen.

Plan: 011 §2.5
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate_variants")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
PROFILES_DIR = ROOT / "profiles"


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_module_checksum(module_dir: Path) -> str:
    all_hashes = []
    for fpath in sorted(module_dir.rglob("*")):
        if fpath.is_file() and fpath.suffix in (".md", ".yaml", ".yml", ".json"):
            all_hashes.append(compute_hash(fpath.read_text(encoding="utf-8")))
    combined = "".join(sorted(all_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def migrate_variants(variants_dir: Path) -> list[dict]:
    """Migriert profiles/workflow-variants/*/ → modules/danma-workflow-variants/variants/"""
    legacy_dir = PROFILES_DIR / "workflow-variants"

    if not legacy_dir.exists():
        logger.warning("Legacy-Verzeichnis nicht gefunden: %s", legacy_dir)
        return []

    files = []

    for variant_dir in sorted(legacy_dir.iterdir()):
        if not variant_dir.is_dir():
            continue

        variant_name = variant_dir.name
        target_variant_dir = variants_dir / variant_name
        target_variant_dir.mkdir(parents=True, exist_ok=True)

        for md_file in sorted(variant_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            target_path = target_variant_dir / md_file.name
            target_path.write_text(content, encoding="utf-8")

            rel_path = str(target_path.relative_to(variants_dir)).replace("\\", "/")
            files.append(
                {
                    "path": rel_path,
                    "format": "markdown",
                    "checksum": compute_hash(content),
                    "role_type_id": md_file.stem,
                    "language": "de",
                }
            )
            logger.info("  Migriert: %s/%s", variant_name, md_file.name)

    return files


def update_manifest(variants_dir: Path, files: list[dict]) -> None:
    """Aktualisiert das Manifest mit neuen Checksummen."""
    manifest_path = variants_dir / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Manifest nicht gefunden: %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Checksummen aktualisieren
    for file_entry in manifest.get("files", []):
        file_path = variants_dir / file_entry["path"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            file_entry["checksum"] = compute_hash(content)

    manifest["checksum"] = compute_module_checksum(variants_dir)
    manifest["updated_at"] = datetime.now(UTC).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Manifest aktualisiert: %s", manifest_path)


def main():
    logger.info("=== Workflow-Varianten-Migration gestartet ===")

    variants_dir = MODULES_DIR / "danma-workflow-variants"
    if not variants_dir.exists():
        logger.error("Modul-Verzeichnis nicht gefunden: %s", variants_dir)
        sys.exit(1)

    files = migrate_variants(variants_dir)
    logger.info("%d Workflow-Varianten migriert", len(files))

    update_manifest(variants_dir, files)

    deprecated_file = PROFILES_DIR / "workflow-variants" / "DEPRECATED.txt"
    deprecated_file.write_text(
        "# DEPRECATED\n\nDieses Verzeichnis wurde durch modules/danma-workflow-variants ersetzt.\n",
        encoding="utf-8",
    )
    logger.info("DEPRECATED-Markierung erstellt: %s", deprecated_file)

    logger.info("=== Fertig! ===")


if __name__ == "__main__":
    main()
