#!/usr/bin/env python3
"""Migrationsskript: templates/ → modules/workflow-templates/

Überträgt Workflow-Templates aus dem Legacy-Verzeichnis in das
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
logger = logging.getLogger("migrate_templates")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
DATA_DIR = ROOT / "data"


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_module_checksum(module_dir: Path) -> str:
    all_hashes = []
    for fpath in sorted(module_dir.rglob("*")):
        if fpath.is_file() and fpath.suffix in (".md", ".yaml", ".yml", ".json"):
            all_hashes.append(compute_hash(fpath.read_text(encoding="utf-8")))
    combined = "".join(sorted(all_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def migrate_templates(wf_templates: Path) -> list[dict]:
    """Migriert templates/*.json → modules/workflow-templates/workflows/"""
    legacy_dir = ROOT / "templates"
    target_dir = wf_templates / "workflows"

    if not legacy_dir.exists():
        logger.warning("Legacy-Verzeichnis nicht gefunden: %s", legacy_dir)
        return []

    target_dir.mkdir(parents=True, exist_ok=True)
    files = []

    json_files = list(sorted(legacy_dir.glob("*.json")))
    # templates/print/ enthält Renderer-Module, keine Workflow-Templates
    # print_dir = legacy_dir  # unused
    json_files = [f for f in json_files if not f.parent.name == "print"]

    for json_file in json_files:
        content = json_file.read_text(encoding="utf-8")
        target_path = target_dir / json_file.name
        target_path.write_text(content, encoding="utf-8")

        rel_path = str(target_path.relative_to(wf_templates)).replace("\\", "/")

        # Extrahiere Platzhalter aus dem Template
        try:
            data = json.loads(content)
            placeholders = get_placeholders(data)
        except json.JSONDecodeError:
            placeholders = []

        files.append(
            {
                "path": rel_path,
                "format": "json",
                "checksum": compute_hash(content),
                "placeholders_json": json.dumps(placeholders),
                "template_data_json": content,
            }
        )
        logger.info("  Migriert: %s", json_file.name)

    return files


def get_placeholders(template_data: dict) -> list[str]:
    """Rekursiv Platzhalter aus Workflow-Template-Daten extrahieren."""
    placeholders = []

    def _extract(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                _extract(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract(item)
        elif isinstance(obj, str):
            import re

            found = re.findall(r"\{\{(\w+)\}\}", obj)
            placeholders.extend(found)

    _extract(template_data)
    return sorted(set(placeholders))


def update_manifest(wf_templates: Path, files: list[dict]) -> None:
    """Aktualisiert das Manifest mit neuen Checksummen."""
    manifest_path = wf_templates / "manifest.json"
    if not manifest_path.exists():
        logger.warning("Manifest nicht gefunden: %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Vorhandene Datei-Einträge aktualisieren
    for file_entry in manifest.get("files", []):
        fpath = wf_templates / file_entry["path"]
        if fpath.exists():
            # .json-Templates haben kein language/role_type_id
            file_entry["checksum"] = compute_hash(fpath.read_text(encoding="utf-8"))

    # Neue Dateien hinzufügen (falls nicht bereits im Manifest)
    existing_paths = {f["path"] for f in manifest.get("files", [])}
    for f in files:
        if f["path"] not in existing_paths:
            # Neue Einträge für migrierte Templates
            rel_path = f["path"]
            manifest["files"].append(
                {
                    "path": rel_path,
                    "format": "json",
                    "checksum": f["checksum"],
                    "placeholders_json": f.get("placeholders_json", "[]"),
                    "template_data_json": f.get("template_data_json", ""),
                }
            )

    # Alte Einträge entfernen (z.B. self-reference fix)
    manifest["files"] = [f for f in manifest["files"] if not f.get("path", "").endswith("manifest.json")]

    manifest["checksum"] = compute_module_checksum(wf_templates)
    manifest["updated_at"] = datetime.now(UTC).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Manifest aktualisiert: %s", manifest_path)


def main():
    logger.info("=== Workflow-Template-Migration gestartet ===")

    wf_templates = MODULES_DIR / "workflow-templates"
    if not wf_templates.exists():
        logger.error("Modul-Verzeichnis nicht gefunden: %s", wf_templates)
        sys.exit(1)

    files = migrate_templates(wf_templates)
    logger.info("%d Workflow-Templates migriert", len(files))

    update_manifest(wf_templates, files)

    logger.info("=== Fertig! ===")


if __name__ == "__main__":
    main()
