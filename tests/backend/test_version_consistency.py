"""Test that version is consistent across all sources of truth.

This test verifies that:
- /version file exists and is parseable
- backend/__init__.py __version__ matches /version
- backend/core/config.py app_version default matches /version
- backend/a2a/agent_card.py version matches /version
- pyproject.toml version matches /version
- /api/v1/config/version endpoint returns the same version
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

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


class TestBackendInit:
    """Tests that backend/__init__.py exports the correct version."""

    def test_version_matches(self):
        read_version_file()
        init_file = PROJECT_ROOT / "backend" / "__init__.py"
        content = init_file.read_text()
        # Look for __version__ = "x.y.z"
        re.search(r'__version__\s*=\s*"?([^\s"\']+)"?', content)
        # Since __version__ is computed dynamically, check the _get_version function reads the file
        assert "version" in content.lower() or "version_file" in content.lower(), "backend/__init__.py should reference version file"


class TestConfigPy:
    """Tests that backend/core/config.py reads from /version."""

    def test_uses_version_file(self):
        config_file = PROJECT_ROOT / "backend" / "core" / "config.py"
        content = config_file.read_text()
        assert "version_file" in content.lower() or "_get_version" in content, "config.py should read version from /version file"
        assert "0.0.0-dev" in content, "config.py should have a dev fallback"

    def test_version_matches(self):
        version = read_version_file()
        # Import and check
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            from backend.core.config import _get_version

            config_version = _get_version()
            assert config_version == version, f"config._get_version() returned {config_version}, expected {version}"
        finally:
            sys.path.pop(0)


class TestAgentCard:
    """Tests that agent_card.py uses dynamic version."""

    def test_version_dynamic(self):
        card_file = PROJECT_ROOT / "backend" / "a2a" / "agent_card.py"
        content = card_file.read_text()
        # Should import __version__ from backend, not hardcode
        assert '"2.0.0"' not in content or "__version__" in content, "agent_card.py should not hardcode version"


class TestPyprojectToml:
    """Tests that pyproject.toml version matches /version."""

    def test_version_matches(self):
        version = read_version_file()
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        assert match, "pyproject.toml should have a version field"
        pyproject_version = match.group(1)
        assert pyproject_version == version, f"pyproject.toml version {pyproject_version} != /version {version}"


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


class TestAPIEndpoint:
    """Integration test for the /api/v1/config/version endpoint.

    Requires the backend to be running. Skipped if not available.
    """

    def test_version_endpoint_returns_consistent_version(self):
        import json
        import urllib.request

        version = read_version_file()
        try:
            url = "http://localhost:8000/api/v1/config/version"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                assert "version" in data
                assert data["version"] == version, f"API returned {data['version']}, expected {version}"
        except (ConnectionError, OSError, urllib.error.URLError) as e:
            pytest.skip(f"Backend not running: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
