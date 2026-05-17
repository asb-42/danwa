"""Migration: Dissolve bundle modules into individual single-profile modules.

Reads existing bundle modules (v1 with files[]), creates individual
module directories for each profile file (v2 with profile_file),
then removes old bundle directories and cleans stale DB entries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("migrate_modules")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
DB_PATH = ROOT / "data" / "blueprints.db"

CATEGORY_PREFIX = {
    "llm-profiles": "llm",
    "agents": "agent",
    "role-types": "role",
    "tone-profiles": "tone",
    "workflows": "workflow",
    "workflow-variants": "variant",
    "prompts": "prompt",
}


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-").replace(".", "-")


def generate_module_id(category: str, profile_data: dict, file_stem: str) -> str:
    prefix = CATEGORY_PREFIX.get(category, "mod")
    profile_id = profile_data.get("id", "")
    if profile_id:
        return f"{prefix}-{profile_id}"
    return f"{prefix}-{slugify(file_stem)}"


def make_manifest(
    category: str,
    module_type: str,
    module_id: str,
    profile_data: dict,
    profile_format: str,
    author: dict,
    license: str,
    tags: list,
) -> dict:
    name_en = profile_data.get("name", module_id)
    desc_en = profile_data.get("description", "")

    manifest = {
        "schema_version": "2.0.0",
        "module_id": module_id,
        "name": {"en": name_en},
        "version": "1.0.0",
        "type": module_type,
        "category": category,
        "author": author or {"name": "Danwa Community"},
        "license": license or "CC-BY-4.0",
        "tags": tags or [],
        "language": "en",
        "profile_file": f"profile.{profile_format}",
        "profile_format": profile_format,
        "files": [],
    }

    if desc_en:
        manifest["description"] = {"en": desc_en}

    return manifest


def compute_checksum(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def migrate_bundle(bundle_dir: Path, db_path: Path) -> list[str]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        return []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    if not files:
        return []

    category = manifest.get("category", "custom")
    module_type = manifest.get("type", "custom")
    author = manifest.get("author", {})
    license = manifest.get("license", "CC-BY-4.0")
    created_new = []

    for file_entry in files:
        fpath = bundle_dir / file_entry["path"]
        if not fpath.exists():
            continue

        fmt = file_entry.get("format", "yaml")
        profile_format = "yaml" if fmt == "yaml" else "json"

        try:
            if profile_format == "yaml":
                profile_data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
            else:
                profile_data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Skipping %s: parse error: %s", fpath.name, e)
            continue

        if not isinstance(profile_data, dict):
            continue

        module_id = generate_module_id(category, profile_data, fpath.stem)
        target_dir = MODULES_DIR / module_id

        if target_dir.exists():
            logger.info("  Skip %s (already exists)", module_id)
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        profile_dst = target_dir / f"profile.{profile_format}"
        if profile_format == "yaml":
            profile_dst.write_text(yaml.dump(profile_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
        else:
            profile_dst.write_text(json.dumps(profile_data, indent=2, ensure_ascii=False), encoding="utf-8")

        tags = profile_data.get("tags", [])
        manifest_data = make_manifest(category, module_type, module_id, profile_data, profile_format, author, license, tags)
        manifest_path_dst = target_dir / "manifest.json"
        manifest_path_dst.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

        checksum = compute_checksum(profile_dst)
        manifest_data["checksum"] = checksum
        manifest_path_dst.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

        created_new.append(module_id)
        logger.info("  Created %s", module_id)

    return created_new


def clean_db(db_path: Path, old_ids: list[str]) -> int:
    removed = 0
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        for mid in old_ids:
            cursor.execute("DELETE FROM module_translation_cache WHERE module_id = ?", (mid,))
            removed += cursor.rowcount
            cursor.execute("DELETE FROM module_registry WHERE id = ?", (mid,))
            removed += cursor.rowcount
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.error("DB cleanup error: %s", e)
    return removed


def main():
    logger.info("Starting module migration (bundles → single-profile)")
    logger.info("Modules dir: %s", MODULES_DIR)

    if not MODULES_DIR.exists():
        logger.info("No modules directory found. Nothing to migrate.")
        return

    bundle_dirs = []
    for d in sorted(MODULES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        mp = d / "manifest.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        if m.get("files") and not m.get("profile_file"):
            bundle_dirs.append(d)

    if not bundle_dirs:
        logger.info("No bundle modules found. Migration not needed.")
        return

    logger.info("Found %d bundle modules to dissolve", len(bundle_dirs))

    all_new = []
    all_old_ids = []

    for bundle_dir in bundle_dirs:
        old_id = bundle_dir.name
        logger.info("Dissolving bundle: %s", old_id)
        all_old_ids.append(old_id)

        new_ids = migrate_bundle(bundle_dir, DB_PATH)
        all_new.extend(new_ids)

        shutil.rmtree(bundle_dir)
        logger.info("  Removed old bundle directory: %s", old_id)

    removed = clean_db(DB_PATH, all_old_ids)

    logger.info("=" * 60)
    logger.info("Migration complete:")
    logger.info("  Bundles dissolved: %d", len(bundle_dirs))
    logger.info("  New modules created: %d", len(all_new))
    logger.info("  Old DB entries removed: %d", removed)
    for nid in all_new:
        logger.info("    + %s", nid)
    for oid in all_old_ids:
        logger.info("    - %s", oid)


if __name__ == "__main__":
    main()
