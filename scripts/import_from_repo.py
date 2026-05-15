#!/usr/bin/env python3
"""Import-Skript für Modul-Repository.

Lädt registry.json von einem Remote-Server, zeigt verfügbare Module
an und installiert sie.

Plan: 015 §6.2

Usage:
    python scripts/import_from_repo.py list                     # Verfügbare Module anzeigen
    python scripts/import_from_repo.py install danwa-prompts-base  # Modul installieren
    python scripts/import_from_repo.py install --all            # Alle verfügbaren Module installieren
    python scripts/import_from_repo.py --registry-url https://... # Custom Registry-URL
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tempfile
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("import_from_repo")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
DEFAULT_REGISTRY_URL = "https://raw.githubusercontent.com/danwa/modules/main/registry.json"


def fetch_registry(url: str) -> dict:
    """Lädt registry.json von der Remote-URL."""
    logger.info("Lade Registry von %s", url)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception as exc:
        logger.error("Registry nicht erreichbar: %s", exc)
        return {}


def download_file(url: str, dest: Path) -> bool:
    """Lädt eine Datei von einer URL herunter."""
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:
        logger.error("Download fehlgeschlagen: %s", exc)
        return False


def verify_checksum(file_path: Path, expected: str) -> bool:
    """Verifiziert die SHA-256-Checksumme einer Datei."""
    if not expected.startswith("sha256:"):
        return True
    expected_hash = expected[7:]
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected_hash:
        logger.error("Checksum mismatch: expected %s, got %s", expected_hash[:16], actual[:16])
        return False
    return True


def list_modules(registry: dict, installed_ids: set):
    """Zeigt verfügbare Module an."""
    modules = registry.get("modules", [])
    if not modules:
        logger.info("Keine Module in Registry gefunden.")
        return

    logger.info("=== Verfügbare Module (%d) ===", len(modules))
    for mod in modules:
        status = "installiert" if mod["module_id"] in installed_ids else "verfügbar"
        logger.info(
            "  %-30s v%-8s %-20s [%s]",
            mod["module_id"],
            mod["version"],
            mod.get("type", ""),
            status,
        )


def install_module(mod: dict, modules_dir: Path) -> bool:
    """Installiert ein einzelnes Modul aus dem Repository."""
    module_id = mod["module_id"]
    version = mod["version"]
    download_url = mod["download_url"]
    checksum = mod.get("checksum", "")

    logger.info("Installiere %s v%s ...", module_id, version)

    # ZIP herunterladen
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / f"{module_id}.zip"
        if not download_file(download_url, zip_path):
            return False

        # Checksum verifizieren
        if checksum and not verify_checksum(zip_path, checksum):
            logger.error("Checksum-Verifizierung fehlgeschlagen für %s", module_id)
            return False

        # ZIP entpacken
        import zipfile

        extract_dir = modules_dir / module_id
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

    logger.info("  %s v%s installiert nach %s", module_id, version, extract_dir)
    return True


def get_installed_ids() -> set:
    """Ermittle IDs aller installierten Module."""
    installed = set()
    if not MODULES_DIR.exists():
        return installed
    for mod_dir in sorted(MODULES_DIR.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("."):
            continue
        manifest_path = mod_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            installed.add(manifest.get("module_id", mod_dir.name))
    return installed


def main():
    parser = argparse.ArgumentParser(description="Module aus Repository importieren")
    parser.add_argument("command", nargs="?", default="list", choices=["list", "install"], help="Befehl")
    parser.add_argument("module_id", nargs="?", default=None, help="Modul-ID zum Installieren")
    parser.add_argument("--all", action="store_true", dest="install_all", help="Alle verfügbaren Module installieren")
    parser.add_argument("--registry-url", type=str, default=DEFAULT_REGISTRY_URL, help="Registry-URL")
    args = parser.parse_args()

    registry = fetch_registry(args.registry_url)
    if not registry:
        logger.error("Registry nicht verfügbar.")
        return

    installed_ids = get_installed_ids()

    if args.command == "list":
        list_modules(registry, installed_ids)
        return

    if args.command == "install":
        modules = registry.get("modules", [])

        if args.install_all:
            to_install = [m for m in modules if m["module_id"] not in installed_ids]
            if not to_install:
                logger.info("Alle Module bereits installiert.")
                return
            logger.info("Installiere %d Module ...", len(to_install))
            for mod in to_install:
                install_module(mod, MODULES_DIR)
        elif args.module_id:
            mod = next((m for m in modules if m["module_id"] == args.module_id), None)
            if not mod:
                logger.error("Modul '%s' nicht in Registry gefunden.", args.module_id)
                return
            if args.module_id in installed_ids:
                logger.info("Modul '%s' ist bereits installiert.", args.module_id)
                return
            install_module(mod, MODULES_DIR)
        else:
            logger.error("Bitte Modul-ID angeben oder --all verwenden.")


if __name__ == "__main__":
    main()
