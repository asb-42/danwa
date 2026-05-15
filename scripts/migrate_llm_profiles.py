#!/usr/bin/env python3
"""Migrationsskript: profiles/llm/ → modules/llm-profiles/

Überträgt LLM-Profile aus dem Legacy-Verzeichnis in das
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
logger = logging.getLogger("migrate_llm_profiles")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
PROFILES_DIR = ROOT / "profiles"


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_module_checksum(module_dir: Path) -> str:
    all_hashes = []
    for fpath in sorted(module_dir.rglob("*")):
        if fpath.is_file() and fpath.suffix in (".yaml", ".yml", ".json"):
            all_hashes.append(compute_hash(fpath.read_text(encoding="utf-8")))
    combined = "".join(sorted(all_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def migrate_llm_profiles(llm_profiles: Path) -> list[dict]:
    """Migriert profiles/llm/*.yaml → modules/llm-profiles/llm/"""
    legacy_dir = PROFILES_DIR / "llm"
    target_dir = llm_profiles / "llm"

    if not legacy_dir.exists():
        logger.warning("Legacy-Verzeichnis nicht gefunden: %s", legacy_dir)
        return []

    target_dir.mkdir(parents=True, exist_ok=True)
    files = []

    for yaml_file in sorted(legacy_dir.glob("*.yaml")):
        content = yaml_file.read_text(encoding="utf-8")
        target_path = target_dir / yaml_file.name
        target_path.write_text(content, encoding="utf-8")

        rel_path = str(target_path.relative_to(llm_profiles)).replace("\\", "/")
        # Extrahiere provider/model aus YAML für role_type_id
        import yaml as yaml_lib

        try:
            data = yaml_lib.safe_load(content)
            profile_type = data.get("profile_type", "text")
        except Exception:
            profile_type = "text"

        files.append(
            {
                "path": rel_path,
                "format": "yaml",
                "checksum": compute_hash(content),
                "role_type_id": profile_type,
                "language": "en",
            }
        )
        logger.info("  Migriert: %s", yaml_file.name)

    return files


def update_manifest(llm_profiles: Path) -> None:
    """Aktualisiert das Manifest mit neuen Checksummen."""
    manifest_path = llm_profiles / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Manifest nicht gefunden: %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for file_entry in manifest.get("files", []):
        file_path = llm_profiles / file_entry["path"]
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            file_entry["checksum"] = compute_hash(content)

    manifest["checksum"] = compute_module_checksum(llm_profiles)
    manifest["updated_at"] = datetime.now(UTC).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Manifest aktualisiert: %s", manifest_path)


def main():
    logger.info("=== LLM-Profil-Migration gestartet ===")

    llm_profiles = MODULES_DIR / "llm-profiles"
    if not llm_profiles.exists():
        logger.error("Modul-Verzeichnis nicht gefunden: %s", llm_profiles)
        sys.exit(1)

    files = migrate_llm_profiles(llm_profiles)
    logger.info("%d LLM-Profile migriert", len(files))

    update_manifest(llm_profiles)

    deprecated_file = PROFILES_DIR / "llm" / "DEPRECATED.txt"
    deprecated_file.write_text(
        "# DEPRECATED\n\nDieses Verzeichnis wurde durch modules/llm-profiles ersetzt.\n",
        encoding="utf-8",
    )
    logger.info("DEPRECATED-Markierung erstellt: %s", deprecated_file)

    logger.info("=== Fertig! ===")


if __name__ == "__main__":
    main()
