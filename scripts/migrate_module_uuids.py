#!/usr/bin/env python3
"""Module ID → UUID Migration Script.

Generates deterministic UUIDs for all module IDs and renames directories
to follow the new ``{type-prefix}-{uuid}/`` convention.

Usage:
    python scripts/migrate_module_uuids.py --modules-dir ./modules [--dry-run]
    python scripts/migrate_module_uuids.py --modules-dir /media/data/coding/danwa-modules [--dry-run]

The script is idempotent: modules already matching the UUID pattern
(e.g. ``llm-0d14655f-...``) are skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Deterministic namespace UUID — same across all environments
DANWA_NAMESPACE = uuid.UUID("d4f1c6a0-7b2e-4a9d-8f3c-1e5b9a0d7c6f")

# Module type → short prefix
TYPE_PREFIX: dict[str, str] = {
    "agent-core": "ac",
    "workflow-template": "wt",
    "tone-profile": "tp",
    "argumentation-pattern": "ap",
    "prompt-variant": "ap",  # alias used in older manifests
    "prompt-modifier": "pm",
    "language-pack": "lp",
    "kitsune-assistant": "ka",
    "bundle": "bd",
    "role-type": "rt",
    "llm-profile": "llm",
    "ui-translation": "lp",  # alias
}

# Parent directory names to scan for nested modules
CATEGORY_DIRS = {
    "agent-cores",
    "agent-argumentation-patterns",
    "agent-tone-profiles",
    "agent-prompt-modifiers",
    "agent-bundles",
    "workflows",
    "kitsune-assistant",
    "llm-profiles",
    "prompt-modifiers",
    "prompt-modifier-text-only",
    "ui-translations",
}


def is_uuid_module_id(module_id: str) -> bool:
    """Check if a module_id already follows the UUID pattern."""
    # llm-{uuid} pattern
    parts = module_id.split("-", 1)
    if len(parts) == 2:
        try:
            uuid.UUID(parts[1])
            return True
        except ValueError:
            pass
    return False


def compute_profile_checksum(module_dir: Path, manifest: dict) -> str:
    """Compute SHA-256 checksum of the profile file (non-manifest files)."""
    all_files = sorted(f for f in module_dir.rglob("*") if f.is_file() and f.name != "manifest.json")
    if not all_files:
        return ""
    h = hashlib.sha256()
    for f in all_files:
        h.update(f.read_bytes())
    return h.hexdigest()


def compute_manifest_checksum(module_dir: Path) -> str:
    """Compute SHA-256 of all non-manifest files (manifest.checksum value)."""
    all_files = sorted(f for f in module_dir.rglob("*") if f.is_file() and f.name != "manifest.json")
    if not all_files:
        return ""
    h = hashlib.sha256()
    for f in all_files:
        h.update(f.read_bytes())
    return h.hexdigest()


def generate_uuid(old_module_id: str) -> str:
    """Generate a deterministic UUID5 from the old module_id."""
    return str(uuid.uuid5(DANWA_NAMESPACE, old_module_id))


def discover_modules(modules_dir: Path) -> list[tuple[Path, dict]]:
    """Discover all module directories with manifest.json files.

    Returns list of (module_dir, manifest_dict) tuples.
    """
    results: list[tuple[Path, dict]] = []

    if not modules_dir.exists():
        return results

    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue

        manifest_path = entry / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                results.append((entry, manifest))
            except (json.JSONDecodeError, OSError) as e:
                print(f"  WARN: Cannot parse {manifest_path}: {e}", file=sys.stderr)
        else:
            # Check one level of subdirectories
            for sub in sorted(entry.iterdir()):
                if not sub.is_dir() or sub.name.startswith((".", "_")):
                    continue
                sub_manifest = sub / "manifest.json"
                if sub_manifest.exists():
                    try:
                        manifest = json.loads(sub_manifest.read_text(encoding="utf-8"))
                        results.append((sub, manifest))
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"  WARN: Cannot parse {sub_manifest}: {e}", file=sys.stderr)

    return results


def determine_prefix(manifest: dict) -> str | None:
    """Determine the UUID prefix from the manifest type field."""
    manifest_type = manifest.get("type", "")
    if manifest_type in TYPE_PREFIX:
        return TYPE_PREFIX[manifest_type]
    # Try category-based fallback
    category = manifest.get("category", "")
    category_map = {
        "agents": "ac",
        "workflows": "wt",
        "tone-profiles": "tp",
        "prompts": "ap",
        "prompt-modifiers": "pm",
        "bundles": "bd",
        "translations": "lp",
        "kitsune": "ka",
        "llm-profiles": "llm",
    }
    if category in category_map:
        return category_map[category]
    return None


def migrate_module(
    module_dir: Path,
    manifest: dict,
    dry_run: bool = False,
) -> tuple[str, str] | None:
    """Migrate a single module to UUID-based ID.

    Returns (old_module_id, new_module_id) or None if skipped.
    """
    # Use manifest module_id if present, otherwise directory name
    old_module_id = manifest.get("module_id", module_dir.name)

    # Skip if already UUID-based
    if is_uuid_module_id(old_module_id):
        print(f"  SKIP (already UUID): {module_dir.name} → {old_module_id}")
        return None

    prefix = determine_prefix(manifest)
    if prefix is None:
        print(f"  SKIP (unknown type): {module_dir.name} (type={manifest.get('type')}, category={manifest.get('category')})")
        return None

    new_uuid = generate_uuid(old_module_id)
    new_module_id = f"{prefix}-{new_uuid}"
    new_dir_name = new_module_id  # Directory name = module_id

    print(f"  {module_dir.name}")
    print(f"    old module_id: {old_module_id}")
    print(f"    new module_id: {new_module_id}")
    print(f"    dir rename:    {module_dir.name} → {new_dir_name}")

    if dry_run:
        return (old_module_id, new_module_id)

    # Update manifest
    manifest["module_id"] = new_module_id
    # Remove profile_id — no longer needed
    manifest.pop("profile_id", None)
    # Update timestamps
    manifest["updated_at"] = datetime.now(UTC).isoformat()

    # Recompute checksum after manifest changes
    # (checksum is of non-manifest files, so it doesn't change from manifest edits)
    # But let's keep the checksum computation consistent
    checksum = compute_manifest_checksum(module_dir)
    manifest["checksum"] = checksum

    # Write updated manifest
    manifest_path = module_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Rename directory
    parent = module_dir.parent
    new_dir = parent / new_dir_name
    if new_dir.exists() and new_dir != module_dir:
        print(f"    WARN: Target directory already exists: {new_dir}", file=sys.stderr)
        return None

    module_dir.rename(new_dir)
    print(f"    OK: renamed to {new_dir_name}")

    return (old_module_id, new_module_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate module IDs to UUIDs")
    parser.add_argument(
        "--modules-dir",
        type=Path,
        required=True,
        help="Path to the modules directory (e.g. ./modules or ../danwa-modules)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    modules_dir = args.modules_dir.resolve()
    if not modules_dir.exists():
        print(f"ERROR: Directory not found: {modules_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Module UUID Migration {'(DRY RUN)' if args.dry_run else ''}")
    print(f"Modules directory: {modules_dir}")
    print()

    modules = discover_modules(modules_dir)
    print(f"Discovered {len(modules)} modules\n")

    migrated = 0
    skipped = 0
    errors = 0
    id_map: dict[str, str] = {}  # old_id → new_id

    for module_dir, manifest in modules:
        try:
            result = migrate_module(module_dir, manifest, dry_run=args.dry_run)
            if result:
                old_id, new_id = result
                id_map[old_id] = new_id
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR migrating {module_dir.name}: {e}", file=sys.stderr)
            errors += 1

    print(f"\n{'=' * 60}")
    print(f"Migration {'preview' if args.dry_run else 'complete'}:")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")

    if id_map:
        print(f"\nID mapping ({len(id_map)} entries):")
        for old_id, new_id in sorted(id_map.items()):
            print(f"  {old_id} → {new_id}")

    # Write ID mapping file for downstream use (e.g. regenerating index)
    if id_map and not args.dry_run:
        map_path = modules_dir / ".uuid_migration_map.json"
        map_path.write_text(
            json.dumps(id_map, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nID mapping written to: {map_path}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
