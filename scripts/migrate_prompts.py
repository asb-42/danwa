#!/usr/bin/env python3
"""Migrationsskript: profiles/prompts/ → modules/prompts-base/

Überträgt Prompt-Templates aus dem Legacy-Verzeichnis in das
neue Modulsystem und aktualisiert die Manifest-Checksummen.

Plan: 011 §2.5 + 012 §3.7
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
logger = logging.getLogger("migrate_prompts")

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


def migrate_default_prompts(prompts_base: Path) -> list[dict]:
    """Migriert profiles/prompts/default/ → modules/prompts-base/prompts/default/"""
    legacy_dir = PROFILES_DIR / "prompts" / "default"
    target_dir = prompts_base / "prompts" / "default"

    if not legacy_dir.exists():
        logger.warning("Legacy-Verzeichnis nicht gefunden: %s", legacy_dir)
        return []

    target_dir.mkdir(parents=True, exist_ok=True)
    files = []

    for md_file in sorted(legacy_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        target_path = target_dir / md_file.name
        target_path.write_text(content, encoding="utf-8")

        files.append(
            {
                "path": str(target_path.relative_to(prompts_base)).replace("\\", "/"),
                "format": "markdown",
                "checksum": compute_hash(content),
                "role_type_id": md_file.stem,
                "language": "de",
            }
        )
        logger.info("  Migriert: %s", md_file.name)

    # Englische Übersetzungen mit -en Suffix
    en_dir = PROFILES_DIR / "prompts"
    for md_file in sorted(en_dir.glob("*-en.md")):
        content = md_file.read_text(encoding="utf-8")
        target_path = target_dir / md_file.name
        target_path.write_text(content, encoding="utf-8")

        files.append(
            {
                "path": str(target_path.relative_to(prompts_base)).replace("\\", "/"),
                "format": "markdown",
                "checksum": compute_hash(content),
                "role_type_id": md_file.stem.replace("-en", ""),
                "language": "en",
            }
        )
        logger.info("  Migriert: %s", md_file.name)

    return files


def migrate_variant_prompts(prompts_base: Path) -> list[dict]:
    """Migriert profiles/prompts/variants/ → modules/prompts-base/prompts/"""
    variants_dir = PROFILES_DIR / "prompts" / "variants"
    target_prompts_dir = prompts_base / "prompts"
    files = []

    if not variants_dir.exists():
        logger.warning("Variants-Verzeichnis nicht gefunden: %s", variants_dir)
        return []

    for variant_dir in sorted(variants_dir.iterdir()):
        if not variant_dir.is_dir():
            continue

        variant_name = variant_dir.name
        variant_target = target_prompts_dir / variant_name
        variant_target.mkdir(parents=True, exist_ok=True)

        for md_file in sorted(variant_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            target_path = variant_target / md_file.name
            target_path.write_text(content, encoding="utf-8")

            rel_path = str(target_path.relative_to(prompts_base)).replace("\\", "/")
            is_en = md_file.stem.endswith("-en")
            base_name = md_file.stem.replace("-en", "")

            files.append(
                {
                    "path": rel_path,
                    "format": "markdown",
                    "checksum": compute_hash(content),
                    "role_type_id": base_name,
                    "language": "en" if is_en else "de",
                }
            )
            logger.info("  Migriert: variants/%s/%s", variant_name, md_file.name)

        # DEPRECATED.txt erstellen
        deprecated = variant_target / "DEPRECATED.txt"
        deprecated.write_text(
            f"# DEPRECATED\n\nDieses Verzeichnis wurde durch das Modulsystem {prompts_base.name} ersetzt.\n",
            encoding="utf-8",
        )

    return files


def update_manifest(prompts_base: Path, all_files: list[dict]) -> None:
    """Aktualisiert das Manifest mit neuen Checksummen."""
    manifest_path = prompts_base / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Manifest nicht gefunden: %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Checksummen aktualisieren
    for file_entry in manifest.get("files", []):
        file_path = prompts_base / file_entry["path"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            file_entry["checksum"] = compute_hash(content)

    # Module-Checksumme aktualisieren
    manifest["checksum"] = compute_module_checksum(prompts_base)
    manifest["updated_at"] = datetime.now(UTC).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Manifest aktualisiert: %s", manifest_path)


def main():
    logger.info("=== Prompt-Migration gestartet ===")

    prompts_base = MODULES_DIR / "prompts-base"
    if not prompts_base.exists():
        logger.error("Modul-Verzeichnis nicht gefunden: %s", prompts_base)
        sys.exit(1)

    # Dateien kopieren
    default_files = migrate_default_prompts(prompts_base)
    variant_files = migrate_variant_prompts(prompts_base)
    all_files = default_files + variant_files

    logger.info("%d Dateien migriert (%d default, %d varianten)", len(all_files), len(default_files), len(variant_files))

    # Manifest aktualisieren
    update_manifest(prompts_base, all_files)

    # DEPRECATED-Markierungen für übergeordnete Verzeichnisse
    deprecated_file = PROFILES_DIR / "prompts" / "DEPRECATED.txt"
    deprecated_file.write_text(
        "# DEPRECATED\n\nDieses Verzeichnis wurde durch modules/prompts-base ersetzt.\n",
        encoding="utf-8",
    )
    logger.info("DEPRECATED-Markierung erstellt: %s", deprecated_file)

    logger.info("=== Fertig! ===")


if __name__ == "__main__":
    main()
