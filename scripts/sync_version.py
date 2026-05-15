#!/usr/bin/env python3
"""Sync version from /version into pyproject.toml and frontend/package.json.

This script ensures that the single source of truth (/version) is propagated
to all package manager files. Run it after changing the version number.

Usage:
    python scripts/sync_version.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version"
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_JSON = ROOT / "frontend" / "package.json"


def get_version() -> str:
    """Read version from /version file, skipping comments and blank lines."""
    if not VERSION_FILE.exists():
        print("ERROR: /version file not found", file=sys.stderr)
        sys.exit(1)
    for line in VERSION_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if re.match(r"^\d+\.\d+\.\d+$", line):
                return line
    print("ERROR: No valid MAJOR.MINOR.PATCH version found in /version", file=sys.stderr)
    sys.exit(1)


def sync_pyproject(version: str) -> None:
    """Update version in pyproject.toml."""
    content = PYPROJECT.read_text()
    new_content = re.sub(
        r'(^version\s*=\s*)"[^"]+"',
        rf'\1"{version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content == content:
        # Version is already correct or pattern not found
        if f'version = "{version}"' in content:
            print(f"  pyproject.toml → {version} (already up to date)")
        else:
            print("WARNING: Could not find version line in pyproject.toml", file=sys.stderr)
        return
    PYPROJECT.write_text(new_content)
    print(f"  pyproject.toml → {version}")


def sync_package_json(version: str) -> None:
    """Update version in frontend/package.json."""
    content = PACKAGE_JSON.read_text()
    new_content = re.sub(
        r'("version"\s*:\s*)"[^"]+"',
        rf'\1"{version}"',
        content,
        count=1,
    )
    if new_content == content:
        if f'"version": "{version}"' in content:
            print(f"  frontend/package.json → {version} (already up to date)")
        else:
            print("WARNING: Could not find version line in package.json", file=sys.stderr)
        return
    PACKAGE_JSON.write_text(new_content)
    print(f"  frontend/package.json → {version}")


def main() -> None:
    version = get_version()
    print(f"Syncing version {version} from /version file...")
    sync_pyproject(version)
    sync_package_json(version)
    print("Done.")


if __name__ == "__main__":
    main()
