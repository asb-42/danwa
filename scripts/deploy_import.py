#!/usr/bin/env python3
"""Deploy-Import-Skript für Danwa-Module.

Liest Module aus modules/ und importiert sie in die Datenbank.
EN-Dateien sind die einzige Quelle der Wahrheit (SSOT).
Vorhandene DE-Übersetzungen werden als initiale Cache-Einträge importiert.

Idempotent: Prüft Checksums und überspringt unveränderte Module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Projekt-Root ermitteln
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deploy_import")


def compute_file_hash(path: Path) -> str:
    """Berechnet SHA-256-Prüfsumme einer Datei."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_module_checksum(module_dir: Path) -> str:
    """Berechnet Gesamt-Prüfsumme aller Dateien im Modul."""
    all_hashes = []
    for fpath in sorted(module_dir.rglob("*")):
        if fpath.is_file() and fpath.suffix in (".md", ".yaml", ".yml", ".json"):
            all_hashes.append(compute_file_hash(fpath))
    combined = "".join(sorted(all_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def validate_manifest(manifest: dict, module_dir: Path) -> list[str]:
    """Validiert Manifest gegen Dateien im Modul."""
    errors = []

    for file_entry in manifest.get("files", []):
        file_path = module_dir / file_entry["path"]
        if not file_path.exists():
            errors.append(f"Datei fehlt: {file_entry['path']}")
            continue

        actual_hash = compute_file_hash(file_path)
        if actual_hash != file_entry.get("checksum"):
            errors.append(f"Checksum-Fehler: {file_entry['path']} (erwartet {file_entry['checksum']}, ist {actual_hash})")

    return errors


def import_module_to_db(
    manifest: dict,
    module_dir: Path,
    db_engine,
    overwrite: bool = False,
) -> dict:
    """Importiert ein Modul in die Datenbank.

    Returns:
        dict mit status ('ok' | 'skipped' | 'error'), details und stats.
    """

    module_id = manifest["module_id"]
    current_checksum = manifest.get("checksum", "")

    conn = db_engine if isinstance(db_engine, object) else None
    if conn is None:
        logger.error("DB-Engine nicht initialisiert (Import wird übersprungen)")
        return {"status": "skipped", "reason": "no_db_engine"}

    # Prüfe ob Modul bereits existiert und Checksum übereinstimmt
    existing = conn.execute(
        "SELECT checksum, installed_at FROM module_registry WHERE id = ?",
        (module_id,),
    ).fetchone()

    if existing:
        if existing["checksum"] == current_checksum:
            logger.info("Modul %s bereits importiert (Checksum identisch) — überspringe", module_id)
            return {"status": "skipped", "reason": "unchanged"}
        elif not overwrite:
            logger.info("Modul %s hat sich geändert, aber overwrite=False — überspringe", module_id)
            return {"status": "skipped", "reason": "changed_no_overwrite"}
        else:
            logger.info("Modul %s hat sich geändert — aktualisiere", module_id)

    # Transaktion starten
    cursor = conn.cursor()
    try:
        # Registry-Eintrag
        cursor.execute(
            """
            INSERT INTO module_registry
                (id, name, description, type, category, version,
                 author_json, license, checksum, installed_at,
                 updated_at, enabled, tags_json, dependencies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                version = excluded.version,
                author_json = excluded.author_json,
                checksum = excluded.checksum,
                updated_at = excluded.updated_at,
                tags_json = excluded.tags_json,
                dependencies = excluded.dependencies
            """,
            (
                module_id,
                json.dumps(manifest.get("name", {})),
                json.dumps(manifest["description"]) if isinstance(manifest.get("description"), dict) else manifest.get("description", ""),
                manifest.get("type", "custom"),
                manifest.get("category", "custom"),
                manifest.get("version", "0.0.0"),
                json.dumps(manifest.get("author", {})),
                manifest.get("license", "CC-BY-4.0"),
                current_checksum,
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
                1,
                json.dumps(manifest.get("tags", [])),
                json.dumps(manifest.get("dependencies", {})),
            ),
        )

        # Dateien in Übersetzungscache importieren
        imported = 0
        for file_entry in manifest.get("files", []):
            file_path = module_dir / file_entry["path"]
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding="utf-8")
            lang = file_entry.get("language", "en")

            cursor.execute(
                """
                INSERT INTO module_translation_cache
                    (id, module_id, file_path, language,
                     translated_content, source_hash, quality_score,
                     generated_at, approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(module_id, file_path, language)
                DO UPDATE SET
                    translated_content = excluded.translated_content,
                    source_hash = excluded.source_hash,
                    approved = excluded.approved
                """,
                (
                    f"{module_id}:{file_entry['path']}:{lang}",
                    module_id,
                    file_entry["path"],
                    lang,
                    content,  # EN-Content als initialen Cache
                    file_entry.get("checksum", ""),
                    1.0,  # Manuell erstellte EN-Datei = höchster Quality-Score
                    datetime.now(UTC).isoformat(),
                    1,  # Approved, da EN-Quelle
                ),
            )
            imported += 1

        conn.commit()
        logger.info(
            "Modul %s importiert: %d Dateien (Checksum: %s)",
            module_id,
            imported,
            current_checksum[:16] + "…",
        )
        return {
            "status": "ok",
            "module_id": module_id,
            "files_imported": imported,
            "checksum": current_checksum,
        }

    except Exception as e:
        conn.rollback()
        logger.error("Fehler beim Import von %s: %s", module_id, e)
        return {"status": "error", "module_id": module_id, "error": str(e)}


def main():
    """Hauptprogramm: Alle Module im modules/-Verzeichnis importieren."""
    modules_dir = ROOT / "modules"
    if not modules_dir.exists():
        logger.error("Verzeichnis modules/ nicht gefunden: %s", modules_dir)
        sys.exit(1)

    # Module finden (= Verzeichnisse mit manifest.json)
    module_dirs = sorted(d for d in modules_dir.iterdir() if d.is_dir() and not d.name.startswith(".") and (d / "manifest.json").exists())

    if not module_dirs:
        logger.warning("Keine Module gefunden (benötigt manifest.json)")
        return

    logger.info("Gefundene Module: %d", len(module_dirs))

    # DB initialisieren (ohne DB-Engine für dry-run)
    # Im Produktivbetrieb: von der App konfigurierte DB verwenden
    db_path = ROOT / "data" / "blueprints.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Migration v19 sicherstellen
    from backend.blueprints.migrations import run_migrations

    run_migrations(str(db_path))

    results = []
    for module_dir in module_dirs:
        manifest_path = module_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Validierung
        errors = validate_manifest(manifest, module_dir)
        if errors:
            logger.error("Validierungsfehler in %s:", module_dir.name)
            for err in errors:
                logger.error("  - %s", err)
            results.append(
                {
                    "module_id": manifest["module_id"],
                    "status": "validation_error",
                    "errors": errors,
                }
            )
            continue

        # Import
        result = import_module_to_db(manifest, module_dir, conn, overwrite=True)
        results.append(result)

    conn.close()

    # Zusammenfassung
    logger.info("=" * 60)
    logger.info("Import-Zusammenfassung:")
    for r in results:
        status = r.get("status", "?")
        module_id = r.get("module_id", "?")
        icon = "✅" if status == "ok" else "⏭️" if status == "skipped" else "❌"
        logger.info("  %s %s (%s)", icon, module_id, status)

    logger.info("=" * 60)
    logger.info("Fertig!")


if __name__ == "__main__":
    main()
