"""Module Validator — validates module manifests and file integrity."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from backend.modules.models import (
    ModuleCategory,
    ModuleType,
    ValidationIssue,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Allowed file extensions for module content
ALLOWED_EXTENSIONS = {".md", ".yaml", ".yml", ".json"}

# Placeholder patterns that should not appear in production content
PLACEHOLDER_PATTERNS = re.compile(
    r"(TODO|FIXME|HACK|XXX|PLACEHOLDER|REPLACE_ME|INSERT_HERE)",
    re.IGNORECASE,
)


class ModuleValidator:
    """Validates Danwa module manifests and content files."""

    def __init__(self, module_base_dir: Path | str = Path("modules")):
        """Initialise ModuleValidator."""
        self.module_base_dir = Path(module_base_dir)

    def validate_manifest(self, manifest: dict[str, Any]) -> ValidationResult:
        """Validate a raw manifest dict and return validation result.

        Args:
            manifest: Raw dict loaded from manifest.json

        Returns:
            ValidationResult with all issues found
        """
        issues: list[ValidationIssue] = []
        module_id = manifest.get("module_id", "<unknown>")

        # --- Schema version ---
        schema_version = manifest.get("schema_version", "1.0.0")
        is_v2 = schema_version in ("2.0.0", "3.0.0")
        if schema_version not in ("1.0.0", "2.0.0", "3.0.0"):
            issues.append(
                ValidationIssue(
                    severity="warning",
                    field="schema_version",
                    message=f"Schema version '{schema_version}' may not be supported. Expected '1.0.0', '2.0.0', or '3.0.0'",
                )
            )

        # v3: validate compatibility field
        if schema_version == "3.0.0":
            compat = manifest.get("compatibility", {})
            if compat.get("danwa_min_version") and not re.match(r"^\d+\.\d+\.\d+$", compat["danwa_min_version"]):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field="compatibility.danwa_min_version",
                        message=f"Invalid danwa_min_version '{compat['danwa_min_version']}': must follow semver X.Y.Z",
                    )
                )
            if compat.get("danwa_max_version") and not re.match(r"^\d+\.\d+\.\d+$", compat["danwa_max_version"]):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field="compatibility.danwa_max_version",
                        message=f"Invalid danwa_max_version '{compat['danwa_max_version']}': must follow semver X.Y.Z",
                    )
                )

        # v3: validate repository field structure
        if schema_version == "3.0.0":
            repo = manifest.get("repository", {})
            if repo:
                if repo.get("type") not in (None, "github"):
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            field="repository.type",
                            message=f"Unsupported repository type '{repo.get('type')}'. Currently only 'github' is supported.",
                        )
                    )

        # --- module_id format ---
        mid = manifest.get("module_id", "")
        if not mid:
            issues.append(ValidationIssue(severity="error", field="module_id", message="module_id is required"))
        elif not re.match(r"^[a-z][a-z0-9.-]*$", mid):
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="module_id",
                    message=f"Invalid module_id '{mid}': must be lowercase alphanumeric with hyphens/dots",
                )
            )

        # --- Required fields ---
        has_files = "files" in manifest and manifest["files"] is not None and len(manifest["files"]) > 0
        has_profile_file = "profile_file" in manifest and manifest["profile_file"] is not None
        required_fields = ["name", "version", "type", "category"]
        for field in required_fields:
            if field not in manifest or manifest[field] is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=field,
                        message=f"Required field '{field}' is missing",
                    )
                )

        # v1 requires files[], v2/v3 requires profile_file
        if schema_version == "1.0.0" and not has_files:
            issues.append(ValidationIssue(severity="error", field="files", message="Required field 'files' is missing (v1 format)"))
        if is_v2 and not has_profile_file and not has_files:
            issues.append(ValidationIssue(severity="error", field="profile_file", message="Required field 'profile_file' is missing (v2 format)"))

        # --- Version format ---
        version = manifest.get("version", "")
        if version and not re.match(r"^\d+\.\d+\.\d+$", version):
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="version",
                    message=f"Invalid version '{version}': must follow semver X.Y.Z",
                )
            )

        # --- Type validation ---
        valid_types = [e.value for e in ModuleType]
        if manifest.get("type") not in valid_types:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="type",
                    message=f"Invalid type '{manifest.get('type')}'. Must be one of: {valid_types}",
                )
            )

        # --- Category validation ---
        valid_categories = [e.value for e in ModuleCategory]
        if manifest.get("category") not in valid_categories:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="category",
                    message=f"Invalid category '{manifest.get('category')}'. Must be one of: {valid_categories}",
                )
            )

        # --- Files check ---
        files = manifest.get("files", [])
        profile_file = manifest.get("profile_file")

        if is_v2 and profile_file and not files:
            # v2 single-profile format: profile_file counts as the file
            fpath = self.module_base_dir / module_id / profile_file if module_id != "<unknown>" else None
            # We can't check existence here since module may not be installed yet
            # The installer will verify later
        elif not files and not profile_file:
            issues.append(ValidationIssue(severity="error", field="files", message="No files defined in manifest"))

        file_paths = set()
        for f in files:
            # Check for duplicate paths
            fpath = f.get("path", "")
            if fpath in file_paths:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=f"files[{fpath}]",
                        message=f"Duplicate file path: {fpath}",
                    )
                )
            file_paths.add(fpath)

            # Check format
            if f.get("format") not in ("markdown", "yaml", "json"):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field=f"files[{fpath}].format",
                        message=f"Unusual format '{f.get('format')}' for {fpath}",
                    )
                )

        return ValidationResult(
            module_id=module_id,
            valid=all(i.severity != "error" for i in issues),
            issues=issues,
            file_count=len(files),
        )

    def validate_file_content(
        self,
        file_path: Path,
        role_type_id: str | None = None,
        file_format: str = "markdown",
    ) -> list[ValidationIssue]:
        """Validate the content of a single module file.

        Args:
            file_path: Path to the file
            role_type_id: Expected role type for prompt files
            file_format: Expected format (markdown/yaml/json)

        Returns:
            List of validation issues found
        """
        issues: list[ValidationIssue] = []

        if not file_path.exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    field=str(file_path),
                    message=f"File does not exist: {file_path}",
                )
            )
            return issues

        if file_path.stat().st_size == 0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field=str(file_path),
                    message=f"File is empty: {file_path}",
                )
            )
            return issues

        content = file_path.read_text(encoding="utf-8")

        # --- Markdown-specific checks ---
        if file_format == "markdown":
            if len(content.strip()) < 50:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field=str(file_path),
                        message=f"Markdown content is very short ({len(content.strip())} chars). Minimum 50 chars recommended.",
                    )
                )

            # Check for unresolved placeholders
            matches = PLACEHOLDER_PATTERNS.findall(content)
            if matches:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        field=str(file_path),
                        message=f"Possible unresolved placeholders found: {', '.join(set(matches))}",
                    )
                )

            # Check for valid structure (at least a heading)
            if not content.strip().startswith("#"):
                issues.append(
                    ValidationIssue(
                        severity="info",
                        field=str(file_path),
                        message="Markdown file doesn't start with a heading (#)",
                    )
                )

        # --- YAML-specific checks ---
        elif file_format in ("yaml", "yml"):
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=str(file_path),
                        message=f"Invalid YAML: {e}",
                    )
                )

        # --- JSON-specific checks ---
        elif file_format == "json":
            try:
                __import__("json").loads(content)
            except ValueError as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=str(file_path),
                        message=f"Invalid JSON: {e}",
                    )
                )

        return issues

    def verify_checksums(
        self,
        base_dir: Path,
        manifest: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Verify all file checksums in a manifest against actual files.

        Args:
            base_dir: Base directory of the module
            manifest: Module manifest dict

        Returns:
            Tuple of (all_valid, error_messages)
        """
        errors: list[str] = []

        for file_entry in manifest.get("files", []):
            fpath = base_dir / file_entry["path"]
            expected_hash = file_entry.get("checksum", "")

            if not fpath.exists():
                errors.append(f"File missing: {file_entry['path']}")
                continue

            actual_hash = self._compute_file_hash(fpath)
            if actual_hash != expected_hash:
                errors.append(f"Checksum mismatch for {file_entry['path']}: expected {expected_hash[:16]}… got {actual_hash[:16]}…")

        return len(errors) == 0, errors

    def validate_workflow_json(self, data: dict[str, Any]) -> list[ValidationIssue]:
        """Validate a workflow template JSON structure.

        Checks:
        - Required fields (name, nodes, edges)
        - Node references in edges exist
        - No circular dependencies (topological check)

        Args:
            data: Workflow template dict

        Returns:
            List of validation issues
        """
        issues: list[ValidationIssue] = []

        if not data.get("name"):
            issues.append(ValidationIssue(severity="error", field="name", message="Workflow name is required"))

        nodes = data.get("nodes", [])
        node_ids = {n.get("id") for n in nodes if n.get("id")}

        if not nodes:
            issues.append(
                ValidationIssue(
                    severity="error",
                    field="nodes",
                    message="Workflow must define at least one node",
                )
            )

        edges = data.get("edges", [])
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and source not in node_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=f"edges.{edge.get('id', '?')}.source",
                        message=f"Edge references non-existent source node '{source}'",
                    )
                )
            if target and target not in node_ids:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field=f"edges.{edge.get('id', '?')}.target",
                        message=f"Edge references non-existent target node '{target}'",
                    )
                )

        # Topological cycle detection
        if nodes and edges:
            if self._has_cycle(node_ids, edges):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        field="edges",
                        message="Workflow contains a circular dependency (cycle detected)",
                    )
                )

        return issues

    @staticmethod
    def _has_cycle(node_ids: set[str], edges: list[dict]) -> bool:
        """Detect cycles using DFS.

        Args:
            node_ids: Set of all node IDs
            edges: List of edge dicts with 'source' and 'target'

        Returns:
            True if a cycle exists
        """
        adj: dict[str, list[str]] = {n: [] for n in node_ids}
        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            if src in adj and tgt in adj:
                adj[src].append(tgt)

        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in node_ids:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    @staticmethod
    def _compute_file_hash(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
