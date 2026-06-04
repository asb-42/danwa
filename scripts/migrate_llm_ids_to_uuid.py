#!/usr/bin/env python3
"""Migrate LLM profile IDs from semantic names to UUIDs.

This script migrates all LLM profile IDs in:
  1. blueprint_llm_profiles table (PRIMARY KEY)
  2. agent_blueprints table (FK llm_profile_id)
  3. agent_bundles table (FK llm_profile_id)
  4. audit_log table (llm_profile_id column)
  5. debate_artifacts table (JSON data blob)
  6. module_registry table (id with llm- prefix)
  7. active_configurations / configuration_history in profiles.db
  8. modules/llm-profiles/ directory names
  9. manifest.json module_id fields

The mapping is saved to scripts/llm_id_mapping.json for use by
backend/frontend code updates.

Usage:
    python scripts/migrate_llm_ids_to_uuid.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINTS_DB = ROOT / "data" / "blueprints.db"
PROFILES_DB = ROOT / "data" / "profiles.db"
MODULES_DIR = ROOT / "modules" / "llm-profiles"
MAPPING_FILE = ROOT / "scripts" / "llm_id_mapping.json"
BACKUP_SUFFIX = f".bak.{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


# ── Helpers ──────────────────────────────────────────────────────────────


def is_uuid(value: str) -> bool:
    """Return True if *value* looks like a UUID4."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def update_json_values(obj: object, old_to_new: dict[str, str]) -> bool:
    """Recursively replace ``llm_profile_id`` values inside a JSON object.

    Returns True if any replacement was made.
    """
    changed = False
    if isinstance(obj, dict):
        for key in ("llm_profile_id", "fallback_llm_profile_id"):
            if key in obj and isinstance(obj[key], str) and obj[key] in old_to_new:
                obj[key] = old_to_new[obj[key]]
                changed = True
        for val in obj.values():
            if update_json_values(val, old_to_new):
                changed = True
    elif isinstance(obj, list):
        for item in obj:
            if update_json_values(item, old_to_new):
                changed = True
    return changed


# ── Core migration ───────────────────────────────────────────────────────


def generate_mapping(conn: sqlite3.Connection) -> dict[str, str]:
    """Build old_id → new_uuid mapping for every profile in blueprint_llm_profiles."""
    rows = conn.execute("SELECT id FROM blueprint_llm_profiles ORDER BY id").fetchall()
    return {row[0]: str(uuid.uuid4()) for row in rows}


def migrate_blueprints_db(conn: sqlite3.Connection, mapping: dict[str, str]) -> dict[str, int]:
    """Update all tables in blueprints.db.  Returns per-table row counts."""
    counts: dict[str, int] = {}

    # Disable FK enforcement for the migration window
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        # 1. blueprint_llm_profiles — update PK
        total = 0
        for old_id, new_id in mapping.items():
            cur = conn.execute(
                "UPDATE blueprint_llm_profiles SET id = ? WHERE id = ?",
                (new_id, old_id),
            )
            total += cur.rowcount
        counts["blueprint_llm_profiles"] = total

        # 2. agent_blueprints — FK
        total = 0
        for old_id, new_id in mapping.items():
            cur = conn.execute(
                "UPDATE agent_blueprints SET llm_profile_id = ? WHERE llm_profile_id = ?",
                (new_id, old_id),
            )
            total += cur.rowcount
        counts["agent_blueprints"] = total

        # 3. agent_bundles — FK
        total = 0
        for old_id, new_id in mapping.items():
            cur = conn.execute(
                "UPDATE agent_bundles SET llm_profile_id = ? WHERE llm_profile_id = ?",
                (new_id, old_id),
            )
            total += cur.rowcount
        counts["agent_bundles"] = total

        # 4. agent_blueprints — fallback_llm_profile_id (if column exists)
        try:
            total = 0
            for old_id, new_id in mapping.items():
                cur = conn.execute(
                    "UPDATE agent_blueprints SET fallback_llm_profile_id = ? WHERE fallback_llm_profile_id = ?",
                    (new_id, old_id),
                )
                total += cur.rowcount
            counts["agent_blueprints_fallback"] = total
        except sqlite3.OperationalError:
            pass

        # 5. audit_log — direct column
        total = 0
        for old_id, new_id in mapping.items():
            cur = conn.execute(
                "UPDATE audit_log SET llm_profile_id = ? WHERE llm_profile_id = ?",
                (new_id, old_id),
            )
            total += cur.rowcount
        counts["audit_log"] = total

        # 6. debate_artifacts — JSON data blob
        rows = conn.execute("SELECT session_id, data FROM debate_artifacts WHERE data LIKE '%llm_profile_id%'").fetchall()
        total = 0
        for session_id, data_str in rows:
            try:
                data = json.loads(data_str)
                if update_json_values(data, mapping):
                    conn.execute(
                        "UPDATE debate_artifacts SET data = ? WHERE session_id = ?",
                        (json.dumps(data), session_id),
                    )
                    total += 1
            except (json.JSONDecodeError, KeyError):
                continue
        counts["debate_artifacts"] = total

        # 7. module_registry — id has llm- prefix
        total = 0
        for old_id, new_id in mapping.items():
            old_module_id = f"llm-{old_id}"
            new_module_id = f"llm-{new_id}"
            cur = conn.execute(
                "UPDATE module_registry SET id = ? WHERE id = ?",
                (new_module_id, old_module_id),
            )
            total += cur.rowcount
        counts["module_registry"] = total

        # 8. module_translation_cache — module_id FK to module_registry
        total = 0
        for old_id, new_id in mapping.items():
            old_module_id = f"llm-{old_id}"
            new_module_id = f"llm-{new_id}"
            cur = conn.execute(
                "UPDATE module_translation_cache SET module_id = ? WHERE module_id = ?",
                (new_module_id, old_module_id),
            )
            total += cur.rowcount
        counts["module_translation_cache"] = total

        # 9. render_jobs, report_jobs — if they have llm_profile_id
        for table in ("render_jobs", "report_jobs"):
            try:
                total = 0
                for old_id, new_id in mapping.items():
                    cur = conn.execute(
                        f"UPDATE {table} SET llm_profile_id = ? WHERE llm_profile_id = ?",
                        (new_id, old_id),
                    )
                    total += cur.rowcount
                counts[table] = total
            except sqlite3.OperationalError:
                pass

        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    return counts


def migrate_profiles_db(mapping: dict[str, str]) -> dict[str, int]:
    """Update profiles.db if it has active_configurations / configuration_history."""
    counts: dict[str, int] = {}
    if not PROFILES_DB.exists():
        return counts

    conn = sqlite3.connect(str(PROFILES_DB))
    conn.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        for table in ("active_configurations", "configuration_history"):
            if table not in tables:
                continue
            # Check if column exists
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "llm_profile_id" not in cols:
                continue
            total = 0
            for old_id, new_id in mapping.items():
                cur = conn.execute(
                    f"UPDATE {table} SET llm_profile_id = ? WHERE llm_profile_id = ?",
                    (new_id, old_id),
                )
                total += cur.rowcount
            counts[table] = total
        conn.commit()
    except Exception as exc:
        print(f"  WARNING: profiles.db migration issue: {exc}", file=sys.stderr)
    finally:
        conn.close()

    return counts


def migrate_case_dbs(mapping: dict[str, str]) -> dict[str, int]:
    """Update per-case blueprint databases under data/tenants/."""
    counts: dict[str, int] = {}
    tenants_dir = ROOT / "data" / "tenants"
    if not tenants_dir.exists():
        return counts

    for db_path in tenants_dir.rglob("blueprints.db"):
        if db_path == BLUEPRINTS_DB:
            continue
        rel = db_path.relative_to(ROOT)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for table in tables:
                cols_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
                col_names = {row[1] for row in cols_info}
                if "llm_profile_id" not in col_names:
                    continue
                total = 0
                for old_id, new_id in mapping.items():
                    cur = conn.execute(
                        f"UPDATE {table} SET llm_profile_id = ? WHERE llm_profile_id = ?",
                        (new_id, old_id),
                    )
                    total += cur.rowcount
                counts[f"{rel}:{table}"] = total

            # Also handle JSON blobs in debate_artifacts
            if "debate_artifacts" in tables:
                da_rows = conn.execute("SELECT session_id, data FROM debate_artifacts WHERE data LIKE '%llm_profile_id%'").fetchall()
                total = 0
                for session_id, data_str in da_rows:
                    try:
                        data = json.loads(data_str)
                        if update_json_values(data, mapping):
                            conn.execute(
                                "UPDATE debate_artifacts SET data = ? WHERE session_id = ?",
                                (json.dumps(data), session_id),
                            )
                            total += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
                if total:
                    counts[f"{rel}:debate_artifacts_json"] = total

            conn.commit()
        except Exception as exc:
            print(f"  WARNING: {rel} migration issue: {exc}", file=sys.stderr)
        finally:
            conn.close()

    return counts


def migrate_module_dirs(mapping: dict[str, str], dry_run: bool = False) -> list[str]:
    """Rename module directories and update manifest.json files."""
    actions: list[str] = []
    if not MODULES_DIR.exists():
        return actions

    for old_id, new_id in mapping.items():
        old_dir = MODULES_DIR / f"llm-{old_id}"
        new_dir = MODULES_DIR / f"llm-{new_id}"

        if not old_dir.exists():
            actions.append(f"  SKIP (not found): llm-{old_id}")
            continue

        if old_dir == new_dir:
            actions.append(f"  SKIP (same): llm-{old_id}")
            continue

        # Update manifest.json
        manifest_path = old_dir / "manifest.json"
        if manifest_path.exists() and not dry_run:
            with open(manifest_path) as f:
                manifest = json.load(f)
            manifest["module_id"] = f"llm-{new_id}"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
                f.write("\n")

        # Update profile.yaml id field (if present and matches old pattern)
        profile_yaml = old_dir / "profile.yaml"
        if profile_yaml.exists() and not dry_run:
            content = profile_yaml.read_text()
            # Replace 'id: old_id' at the start of a line
            import re

            new_content = re.sub(
                rf"^id:\s*{re.escape(old_id)}\s*$",
                f"id: {new_id}",
                content,
                flags=re.MULTILINE,
            )
            if new_content != content:
                profile_yaml.write_text(new_content)

        # Rename directory
        if dry_run:
            actions.append(f"  WOULD RENAME: llm-{old_id} → llm-{new_id}")
        else:
            if new_dir.exists():
                shutil.rmtree(new_dir)
            old_dir.rename(new_dir)
            actions.append(f"  RENAMED: llm-{old_id} → llm-{new_id}")

    return actions


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate LLM profile IDs to UUIDs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    print("=" * 60)
    print("  LLM Profile ID → UUID Migration")
    print("=" * 60)

    if not BLUEPRINTS_DB.exists():
        print(f"\nERROR: Database not found at {BLUEPRINTS_DB}")
        return 1

    # ── 1. Generate mapping ──────────────────────────────────────────────
    conn = sqlite3.connect(str(BLUEPRINTS_DB))
    conn.row_factory = sqlite3.Row

    # Check if already migrated
    sample = conn.execute("SELECT id FROM blueprint_llm_profiles LIMIT 1").fetchone()
    if sample and is_uuid(sample[0]):
        print("\nWARNING: Profiles appear to already be UUIDs. Aborting.")
        print("  (Delete the existing profiles first if you want to re-migrate.)")
        conn.close()
        return 1

    mapping = generate_mapping(conn)
    print(f"\nGenerated UUID mapping for {len(mapping)} profiles:\n")
    for old_id, new_id in sorted(mapping.items()):
        print(f"  {old_id:50s} → {new_id}")

    # ── 2. Backup ────────────────────────────────────────────────────────
    if not args.dry_run:
        backup_path = BLUEPRINTS_DB.with_suffix(BLUEPRINTS_DB.suffix + BACKUP_SUFFIX)
        shutil.copy2(BLUEPRINTS_DB, backup_path)
        print(f"\n  Backup: {backup_path.name}")

        if PROFILES_DB.exists():
            bp_backup = PROFILES_DB.with_suffix(PROFILES_DB.suffix + BACKUP_SUFFIX)
            shutil.copy2(PROFILES_DB, bp_backup)
            print(f"  Backup: {bp_backup.name}")

        # Save mapping
        MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MAPPING_FILE, "w") as f:
            json.dump(mapping, f, indent=2)
        print(f"  Mapping: {MAPPING_FILE.relative_to(ROOT)}")

    # ── 3. Migrate blueprints.db ─────────────────────────────────────────
    print("\n── Migrating blueprints.db ──")
    if args.dry_run:
        print("  (dry-run — skipping)")
    else:
        counts = migrate_blueprints_db(conn, mapping)
        for table, count in counts.items():
            print(f"  {table}: {count} rows updated")

    conn.close()

    # ── 4. Migrate profiles.db ───────────────────────────────────────────
    print("\n── Migrating profiles.db ──")
    if args.dry_run:
        print("  (dry-run — skipping)")
    else:
        counts = migrate_profiles_db(mapping)
        if counts:
            for table, count in counts.items():
                print(f"  {table}: {count} rows updated")
        else:
            print("  (no tables to migrate)")

    # ── 5. Migrate per-case DBs ──────────────────────────────────────────
    print("\n── Migrating per-case databases ──")
    if args.dry_run:
        print("  (dry-run — skipping)")
    else:
        counts = migrate_case_dbs(mapping)
        if counts:
            for key, count in counts.items():
                print(f"  {key}: {count} rows updated")
        else:
            print("  (no per-case DBs found)")

    # ── 6. Migrate module directories ────────────────────────────────────
    print("\n── Migrating module directories ──")
    actions = migrate_module_dirs(mapping, dry_run=args.dry_run)
    if actions:
        for action in actions:
            print(action)
    else:
        print("  (no module directories found)")

    # ── 7. Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if args.dry_run:
        print("  DRY RUN COMPLETE — no changes applied")
    else:
        print("  MIGRATION COMPLETE")
        print(f"  Mapping saved to: {MAPPING_FILE.relative_to(ROOT)}")
        print("  Backups created with suffix:", BACKUP_SUFFIX)
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
