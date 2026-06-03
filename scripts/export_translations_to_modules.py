#!/usr/bin/env python3
"""Export updated UI translations from the local DB to danwa-modules repo.

Merges translations from ALL namespaces (global + langpack:*) and writes
the result back to the module's ui_strings.json in the danwa-modules repo.
Also updates the manifest.json checksum.

Usage:
    python scripts/export_translations_to_modules.py                          # Export all
    python scripts/export_translations_to_modules.py --locale es              # Export one locale
    python scripts/export_translations_to_modules.py --repo ../danwa-modules  # Custom repo path
    python scripts/export_translations_to_modules.py --dry-run                # Show what would be exported
    python scripts/export_translations_to_modules.py --release                # Export + auto-release (semver bump)
    python scripts/export_translations_to_modules.py --release --minor        # Export + bump minor version
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = ROOT.parent / "danwa-modules"

# Locate the UI i18n database (matches backend/modules/installer.py)
UI_I18N_DB = ROOT / "data" / "i18n" / "ui_translations.db"


def bump_patch_version(version: str) -> str:
    """Bump the patch component of a semver string.

    >>> bump_patch_version("1.0.0")
    '1.0.1'
    >>> bump_patch_version("2.3.9")
    '2.3.10'
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version.lstrip("v"))
    if not match:
        return version  # fallback: return as-is
    major, minor, patch = int(match[1]), int(match[2]), int(match[3])
    return f"{major}.{minor}.{patch + 1}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_merged_translations(conn: sqlite3.Connection, locale: str) -> dict[str, str]:
    """Merge translations from global + all langpack:* namespaces.

    Global namespace takes priority (contains LLM-generated translations),
    langpack:* fills in remaining keys (module-installed translations).
    """
    # 1. Get global translations
    rows = conn.execute(
        "SELECT key, value FROM ui_translations WHERE locale = ? AND namespace = 'global'",
        (locale,),
    ).fetchall()
    merged = {r["key"]: r["value"] for r in rows}

    # 2. Merge langpack:* translations (only for keys not in global)
    rows = conn.execute(
        "SELECT key, value FROM ui_translations WHERE locale = ? AND namespace LIKE 'langpack:%'",
        (locale,),
    ).fetchall()
    for r in rows:
        if r["key"] not in merged:
            merged[r["key"]] = r["value"]

    return merged


def get_installed_language_packs(conn: sqlite3.Connection) -> list[dict]:
    """Discover installed language-pack modules from the modules DB."""
    modules_db = ROOT / "data" / "modules.db"
    if not modules_db.exists():
        return []

    mconn = sqlite3.connect(str(modules_db), timeout=10.0)
    mconn.row_factory = sqlite3.Row
    try:
        rows = mconn.execute("SELECT module_id, language, version FROM installed_modules WHERE type = 'language-pack'").fetchall()
        return [dict(r) for r in rows]
    finally:
        mconn.close()


def find_module_dir(repo: Path, module_id: str) -> Path | None:
    """Find the module directory in the repo by module_id."""
    for manifest_path in repo.rglob("manifest.json"):
        if any(p in manifest_path.parts for p in (".git", ".github", "schemas", "plans", "scripts")):
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("module_id") == module_id:
                return manifest_path.parent
        except (json.JSONDecodeError, OSError):
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Export translations to danwa-modules repo")
    parser.add_argument("--repo", type=str, default=str(DEFAULT_REPO), help="Path to danwa-modules repo")
    parser.add_argument("--locale", type=str, nargs="+", default=None, help="Export specific locale(s) (e.g. --locale de es fr)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be exported")
    parser.add_argument("--release", action="store_true", help="Auto-release after export: commit, bump semver tag, push")
    bump_group = parser.add_mutually_exclusive_group()
    bump_group.add_argument("--major", action="store_true", help="Bump major version (requires --release)")
    bump_group.add_argument("--minor", action="store_true", help="Bump minor version (requires --release)")
    bump_group.add_argument("--patch", action="store_true", help="Bump patch version (default, requires --release)")
    parser.add_argument("--no-push", action="store_true", help="Tag locally but don't push (requires --release)")
    args = parser.parse_args()

    repo = Path(args.repo)
    if not repo.exists():
        print(f"ERROR: Repo not found: {repo}", file=sys.stderr)
        sys.exit(1)

    if not UI_I18N_DB.exists():
        print(f"ERROR: Database not found: {UI_I18N_DB}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(UI_I18N_DB), timeout=10.0)
    conn.row_factory = sqlite3.Row

    try:
        # Find all locales that have translations in the DB
        if args.locale:
            locales = args.locale
        else:
            rows = conn.execute("SELECT DISTINCT locale FROM ui_translations WHERE namespace LIKE 'langpack:%'").fetchall()
            locales = [r["locale"] for r in rows]

        if not locales:
            print("No language-pack locales found in database.")
            return

        print(f"=== Exporting {len(locales)} locale(s) to {repo} ===\n")
        exported = 0

        for locale in sorted(locales):
            merged = get_merged_translations(conn, locale)
            if not merged:
                print(f"  {locale}: no translations found, skipped")
                continue

            module_id = f"lang-{locale}"
            module_dir = find_module_dir(repo, module_id)

            if not module_dir:
                print(f"  {locale}: module dir not found in repo (lang-{locale}), skipped")
                continue

            ui_strings_path = module_dir / "ui_strings.json"
            manifest_path = module_dir / "manifest.json"

            if args.dry_run:
                existing_count = 0
                if ui_strings_path.exists():
                    try:
                        existing_count = len(json.loads(ui_strings_path.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError):
                        pass
                diff = len(merged) - existing_count
                sign = "+" if diff > 0 else ""
                print(f"  {locale}: {len(merged)} strings (existing: {existing_count}, diff: {sign}{diff})")
                continue

            # Write ui_strings.json
            ui_strings_path.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            # Update manifest.json: bump version, checksum, string_count, timestamp
            version_info = ""
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    old_version = manifest.get("version", "1.0.0")
                    new_version = bump_patch_version(old_version)
                    manifest["version"] = new_version
                    manifest["checksum"] = sha256_file(ui_strings_path)
                    manifest["string_count"] = len(merged)
                    manifest["updated_at"] = datetime.now(UTC).isoformat()
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    version_info = f" (v{old_version} → v{new_version})"
                except (json.JSONDecodeError, OSError) as exc:
                    print(f"  WARNING: Could not update manifest for {locale}: {exc}")

            print(f"  {locale}: exported {len(merged)} strings → {module_dir.relative_to(repo)}{version_info}")
            exported += 1

        print(f"\nDone! {exported} locale(s) exported.")

        # Auto-release if requested
        if args.release and exported > 0 and not args.dry_run:
            import subprocess

            release_script = repo / "scripts" / "release.py"
            if not release_script.exists():
                print(f"\nERROR: release.py not found at {release_script}", file=sys.stderr)
                sys.exit(1)

            release_cmd = [sys.executable, str(release_script)]
            release_cmd.extend(["-m", f"chore: update {exported} language pack(s) with LLM-translated strings"])
            if args.major:
                release_cmd.append("--major")
            elif args.minor:
                release_cmd.append("--minor")
            else:
                release_cmd.append("--patch")
            if args.no_push:
                release_cmd.append("--no-push")

            print("\n--- Running release ---")
            print(f"  cmd: {' '.join(release_cmd)}")
            result = subprocess.run(release_cmd, cwd=repo)
            if result.returncode != 0:
                print(f"\nERROR: release.py exited with code {result.returncode}", file=sys.stderr)
                sys.exit(result.returncode)
        elif args.release and exported == 0:
            print("\nNothing exported — skipping release.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
