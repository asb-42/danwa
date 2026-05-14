"""Migration: Export/Import alter Debatte-Daten aus memory/debates.db.

Dieses Skript liest die alte sessions-Tabelle aus memory/debates.db
und exportiert die Daten als JSON-Dateien in data/projects/_default/debates/.

Hintergrund: Die alte DebateEngine speicherte Sessions nur in SQLite,
aber die neue Architektur nutzt JSON-Dateien pro Debate im Projektordner.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT_OLD_DB = Path("memory/debates.db")
_DEFAULT_PROJECT_DIR = Path("data/projects/_default")
_DEFAULT_DEBATES_DIR = _DEFAULT_PROJECT_DIR / "debates"


def migrate_debates(
    old_db_path: Path | str = _DEFAULT_OLD_DB,
    target_dir: Path | str = _DEFAULT_DEBATES_DIR,
) -> int:
    """Migrate debates from old SQLite to JSON files.

    Returns the number of debates migrated.
    """
    old_db = Path(old_db_path)
    target = Path(target_dir)

    if not old_db.exists():
        print(f"Alte Datenbank nicht gefunden: {old_db}")
        print("Keine Migration erforderlich.")
        return 0

    target.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(old_db))
    conn.row_factory = sqlite3.Row

    cursor = conn.execute(
        "SELECT session_id, created_at, profile, max_rounds, consensus, context_preview, trace_path, project_id, document_ids FROM sessions"
    )
    rows = cursor.fetchall()
    conn.close()

    migrated = 0
    skipped = 0

    for row in rows:
        session_id = row["session_id"]

        # Prüfe ob bereits migriert
        existing = target / f"{session_id}.json"
        if existing.exists():
            skipped += 1
            continue

        # Baue minimales Debate-JSON aus alten Daten
        try:
            doc_ids_raw = row["document_ids"]
            doc_ids = []
            if doc_ids_raw:
                if isinstance(doc_ids_raw, str):
                    doc_ids = json.loads(doc_ids_raw) if doc_ids_raw.strip() else []
                elif isinstance(doc_ids_raw, (list,)):
                    doc_ids = list(doc_ids_raw)

            created_raw = row["created_at"]
            if created_raw:
                try:
                    created_dt = datetime.fromisoformat(created_raw)
                except (ValueError, TypeError):
                    created_dt = datetime(2024, 1, 1, tzinfo=UTC)
            else:
                created_dt = datetime(2024, 1, 1, tzinfo=UTC)

            debate = {
                "debate_id": session_id,
                "status": "completed",
                "title": f"Migrated: {row['profile'] or 'unknown'}",
                "request": {
                    "case": {"text": row["context_preview"] or "Kein Kontext verfügbar (migriert)"},
                    "max_rounds": row["max_rounds"] or 3,
                    "enable_fact_check": False,
                    "enable_memory": False,
                    "prompt_variant": "default",
                    "agent_persona_ids": {},
                    "language": "de",
                    "document_ids": doc_ids,
                    "rag_auto_retrieve": False,
                    "search_mode": "off",
                    "agent_profile": [
                        {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
                        {"role": "critic", "llm_profile": "default", "temperature": 0.7},
                        {"role": "optimizer", "llm_profile": "default", "temperature": 0.7},
                        {"role": "moderator", "llm_profile": "default", "temperature": 0.7},
                    ],
                },
                "max_rounds": row["max_rounds"] or 3,
                "current_round": 0,
                "rounds": [],
                "created_at": created_dt.isoformat(),
                "updated_at": created_dt.isoformat(),
                "result": {
                    "final_consensus": float(row["consensus"]) if row["consensus"] else 0.0,
                    "anomalies": [],
                    "output": "",
                },
                "trace_path": row["trace_path"] or "",
                "_migrated": True,
                "_migrated_at": datetime.now(UTC).isoformat(),
            }

            target_path = target / f"{session_id}.json"
            target_path.write_text(
                json.dumps(debate, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            migrated += 1
            print(f"  Migriert: {session_id}")

        except Exception as e:
            print(f"  FEHLER bei {session_id}: {e}")
            skipped += 1

    print(f"\nMigration abgeschlossen: {migrated} migriert, {skipped} übersprungen")
    return migrated


if __name__ == "__main__":
    migrate_debates()
