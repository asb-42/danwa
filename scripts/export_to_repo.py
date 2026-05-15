#!/usr/bin/env python3
"""Export-Skript für Modul-Repository.

Erzeugt aus lokalen Modulen eine registry.json und ZIP-Artefakte
für ein externes Modul-Repository (z.B. GitHub).

Plan: 015 §6.2

Usage:
    python scripts/export_to_repo.py                  # registry.json + ZIPs erzeugen
    python scripts/export_to_repo.py --output-dir ../danwa-modules  # In anderes Verzeichnis
    python scripts/export_to_repo.py --dry-run        # Nur anzeigen, was exportiert würde
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("export_to_repo")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"


def sha256_file(path: Path) -> str:
    """Berechne SHA-256-Checksumme einer Datei."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir(dir_path: Path) -> str:
    """Berechne SHA-256-Checksumme eines Verzeichnisses (rekursiv)."""
    h = hashlib.sha256()
    for f in sorted(dir_path.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(dir_path).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def discover_modules() -> list[dict]:
    """Entdecke alle Module im modules/-Verzeichnis."""
    modules = []
    if not MODULES_DIR.exists():
        return modules

    for mod_dir in sorted(MODULES_DIR.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        manifest_path = mod_dir / "manifest.json"
        if not manifest_path.exists():
            logger.warning("Kein manifest.json in %s, übersprungen", mod_dir.name)
            continue

        manifest = json.loads(manifest_path.read_text())
        module_id = manifest.get("module_id", mod_dir.name)
        modules.append(
            {
                "module_id": module_id,
                "version": manifest.get("version", "0.0.0"),
                "name": manifest.get("name", module_id),
                "description": manifest.get("description", ""),
                "type": manifest.get("type", "unknown"),
                "category": manifest.get("category", "general"),
                "author": manifest.get("author", "unknown"),
                "license": manifest.get("license", "MIT"),
                "dependencies": manifest.get("dependencies", []),
                "language": manifest.get("language", "en"),
                "dir": mod_dir,
                "manifest": manifest,
            }
        )

    return modules


def export_module_zip(module: dict, output_dir: Path) -> Path:
    """Erzeuge ein ZIP-Artefakt für ein Modul."""
    zip_name = f"{module['module_id']}-{module['version']}.zip"
    zip_path = output_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(module["dir"].rglob("*")):
            if f.is_file():
                arcname = f.relative_to(module["dir"]).as_posix()
                zf.write(f, arcname)

    return zip_path


def build_registry(modules: list[dict], output_dir: Path) -> dict:
    """Erzeuge registry.json mit allen Modul-Metadaten."""
    registry_modules = []
    for mod in modules:
        zip_name = f"{mod['module_id']}-{mod['version']}.zip"
        zip_path = output_dir / zip_name
        checksum = sha256_file(zip_path) if zip_path.exists() else ""

        registry_modules.append(
            {
                "module_id": mod["module_id"],
                "version": mod["version"],
                "name": mod["name"],
                "description": mod["description"],
                "type": mod["type"],
                "category": mod["category"],
                "author": mod["author"],
                "license": mod["license"],
                "dependencies": mod["dependencies"],
                "language": mod["language"],
                "download_url": f"https://github.com/danwa/modules/releases/download/v{mod['version']}/{zip_name}",
                "checksum": f"sha256:{checksum}",
            }
        )

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "module_count": len(registry_modules),
        "modules": registry_modules,
    }


def main():
    parser = argparse.ArgumentParser(description="Module für Repository exportieren")
    parser.add_argument("--output-dir", type=str, default=None, help="Ausgabeverzeichnis (default: modules/.export)")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, was exportiert würde")
    args = parser.parse_args()

    modules = discover_modules()
    if not modules:
        logger.error("Keine Module mit manifest.json gefunden in %s", MODULES_DIR)
        return

    output_dir = Path(args.output_dir) if args.output_dir else MODULES_DIR / ".export"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        logger.info("=== Dry Run: %d Module würden exportiert ===", len(modules))
        for mod in modules:
            logger.info("  %s v%s (%s)", mod["module_id"], mod["version"], mod["type"])
        logger.info("Ausgabe: %s", output_dir)
        return

    logger.info("=== Export: %d Module ===", len(modules))

    # ZIPs erzeugen
    for mod in modules:
        zip_path = export_module_zip(mod, output_dir)
        logger.info("  ZIP: %s (%.1f KB)", zip_path.name, zip_path.stat().st_size / 1024)

    # registry.json erzeugen
    registry = build_registry(modules, output_dir)
    registry_path = output_dir / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("  registry.json: %d Module", registry["module_count"])

    logger.info("=== Fertig! Export nach: %s ===", output_dir)


if __name__ == "__main__":
    main()
