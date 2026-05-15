#!/usr/bin/env python3
"""Stamp version from /version into build metadata.

Reads the single source of truth version file and writes a JSON
build-info file that can be consumed by the frontend at build time.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    version_file = project_root / "version"
    output_dir = project_root / "frontend" / "src" / "backend"

    if not version_file.exists():
        print("ERROR: /version file not found at", version_file, file=sys.stderr)
        sys.exit(1)

    version = version_file.read_text().strip()

    # Strip optional leading 'v'
    if version.startswith("v"):
        version = version[1:]

    build_info = {
        "version": version,
        "built_at": datetime.now(UTC).isoformat(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "_build_info.json"
    output_path.write_text(json.dumps(build_info, indent=2) + "\n")

    print(f"Stamped version {version} -> {output_path}")


if __name__ == "__main__":
    main()
