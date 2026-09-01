"""Version consistency checks that stay valid in the frontend-only danwa repo.

Ported from tests/backend/test_version_consistency.py when the duplicated
legacy backend was removed (code review §3.1, 2026-08-31). The backend-side
checks (__init__.py, config default, agent card, /api/v1/config/version)
moved with the backend — they live in danwa-core now. What remains
repo-local is the single source of truth (/version) and the frontend
package.json that consumes it.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VERSION_FILE = PROJECT_ROOT / "version"


def read_version_file() -> str:
    """Read the single source of truth version file."""
    assert VERSION_FILE.exists(), f"Version file not found: {VERSION_FILE}"
    content = VERSION_FILE.read_text().strip()
    # Strip comments and whitespace
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert len(lines) >= 1, "Version file must contain at least one non-comment line"
    version = lines[-1].strip()
    assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid version format: {version}"
    return version


class TestVersionFile:
    """Tests for the /version single source of truth."""

    def test_version_file_exists(self):
        assert VERSION_FILE.exists()

    def test_version_format(self):
        version = read_version_file()
        assert re.match(r"^\d+\.\d+\.\d+$", version)

    def test_version_is_not_placeholder(self):
        version = read_version_file()
        assert version != "0.0.0-dev", "Version should not be a dev placeholder"


class TestPackageJson:
    """Tests that frontend/package.json version matches /version."""

    def test_version_matches(self):
        version = read_version_file()
        pkg_json = PROJECT_ROOT / "frontend" / "package.json"
        content = pkg_json.read_text()
        match = re.search(r'"version"\s*:\s*"([^"]+)"', content)
        assert match, "package.json should have a version field"
        pkg_version = match.group(1)
        assert pkg_version == version, f"package.json version {pkg_version} != /version {version}"
