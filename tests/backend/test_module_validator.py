"""Tests for ModuleValidator — manifest validation, checksums, workflow DAGs."""

from __future__ import annotations

import pytest

from backend.modules.validation import ModuleValidator


class TestValidateManifest:
    """Test manifest schema validation."""

    def test_valid_manifest(self):
        """A well-formed manifest passes validation."""
        manifest = {
            "schema_version": "1.0.0",
            "module_id": "danwa-test-valid",
            "name": {"en": "Test Module", "de": "Testmodul"},
            "description": {"en": "A test module"},
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "author": {"name": "Test Author"},
            "license": "CC-BY-4.0",
            "checksum": "abc123",
            "files": [
                {"path": "prompts/default.md", "format": "markdown", "checksum": "abc123", "language": "en"},
            ],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is True
        assert len(result.issues) == 0

    def test_missing_module_id(self):
        """module_id is required."""
        manifest = {
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any(i.field == "module_id" for i in result.issues)

    def test_invalid_module_id_format(self):
        """module_id must be lowercase alphanumeric with hyphens/dots."""
        manifest = {
            "module_id": "Invalid_ID!",
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any("module_id" in i.field for i in result.issues)

    def test_missing_required_fields(self):
        """Missing name, version, type, category, or files are errors."""
        for field in ("name", "version", "type", "category", "files"):
            manifest = {
                "module_id": "danwa-test",
                "name": {"en": "Test"},
                "version": "1.0.0",
                "type": "argumentation-pattern",
                "category": "prompts",
                "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
            }
            del manifest[field]
            result = ModuleValidator().validate_manifest(manifest)
            assert result.valid is False, f"Missing '{field}' should be an error"
            assert any(i.field == field for i in result.issues), f"Expected error on field '{field}'"

    def test_invalid_version_format(self):
        """Version must follow semver X.Y.Z."""
        manifest = {
            "module_id": "danwa-test",
            "version": "1.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any(i.field == "version" for i in result.issues)

    def test_invalid_type(self):
        """Type must be a valid ModuleType enum value."""
        manifest = {
            "module_id": "danwa-test",
            "version": "1.0.0",
            "type": "invalid-type",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any(i.field == "type" for i in result.issues)

    def test_invalid_category(self):
        """Category must be a valid ModuleCategory enum value."""
        manifest = {
            "module_id": "danwa-test",
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "invalid-category",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any(i.field == "category" for i in result.issues)

    def test_empty_files_list(self):
        """Files list must not be empty."""
        manifest = {
            "module_id": "danwa-test",
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any(i.field == "files" for i in result.issues)

    def test_duplicate_file_paths(self):
        """Duplicate file paths in manifest should be flagged."""
        manifest = {
            "module_id": "danwa-test",
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [
                {"path": "prompts/default.md", "format": "markdown", "checksum": "a", "language": "en"},
                {"path": "prompts/default.md", "format": "markdown", "checksum": "b", "language": "en"},
            ],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is False
        assert any("Duplicate" in i.message for i in result.issues)

    def test_unusual_format_warning(self):
        """Non-standard format values produce warnings, not errors."""
        manifest = {
            "schema_version": "1.0.0",
            "module_id": "danwa-test",
            "name": {"en": "Test"},
            "description": {"en": "Test desc"},
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.txt", "format": "plaintext", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is True
        assert any("plaintext" in i.message for i in result.issues)

    def test_schema_version_warning(self):
        """Non-1.0.0 schema version produces a warning, not error."""
        manifest = {
            "schema_version": "0.9.0",
            "module_id": "danwa-test",
            "name": {"en": "Test"},
            "description": {"en": "Test desc"},
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "a", "language": "en"}],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.valid is True  # Warning only
        assert any("schema_version" in i.field for i in result.issues)

    def test_file_count_in_result(self):
        """ValidationResult.file_count matches manifest files."""
        manifest = {
            "schema_version": "1.0.0",
            "module_id": "danwa-test",
            "name": {"en": "Test"},
            "description": {"en": "Test desc"},
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [
                {"path": "a.md", "format": "markdown", "checksum": "a", "language": "en"},
                {"path": "b.md", "format": "markdown", "checksum": "b", "language": "en"},
                {"path": "c.yaml", "format": "yaml", "checksum": "c", "language": "en"},
            ],
        }
        result = ModuleValidator().validate_manifest(manifest)
        assert result.file_count == 3


class TestValidateFileContent:
    """Test file content validation."""

    def test_nonexistent_file(self, tmp_path):
        """Non-existent file returns error."""
        issues = ModuleValidator().validate_file_content(tmp_path / "nonexistent.md")
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "does not exist" in issues[0].message

    def test_empty_file(self, tmp_path):
        """Empty file returns error."""
        f = tmp_path / "empty.md"
        f.write_text("")
        issues = ModuleValidator().validate_file_content(f)
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "empty" in issues[0].message.lower()

    def test_short_markdown_warning(self, tmp_path):
        """Very short markdown gets a warning."""
        f = tmp_path / "short.md"
        f.write_text("# Hi")
        issues = ModuleValidator().validate_file_content(f)
        assert any("short" in i.message.lower() for i in issues)

    def test_valid_markdown(self, tmp_path):
        """Well-formed markdown has no issues."""
        f = tmp_path / "valid.md"
        f.write_text("# Strategy\n\nThis is a detailed strategic analysis.\n")
        issues = ModuleValidator().validate_file_content(f)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_invalid_yaml(self, tmp_path):
        """Invalid YAML produces error."""
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed")
        issues = ModuleValidator().validate_file_content(f, file_format="yaml")
        assert any(i.severity == "error" for i in issues)

    def test_valid_yaml(self, tmp_path):
        """Valid YAML has no issues."""
        f = tmp_path / "good.yaml"
        f.write_text("key: value\nlist:\n  - item1\n  - item2\n")
        issues = ModuleValidator().validate_file_content(f, file_format="yaml")
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_invalid_json(self, tmp_path):
        """Invalid JSON produces error."""
        f = tmp_path / "bad.json"
        f.write_text("{broken}")
        issues = ModuleValidator().validate_file_content(f, file_format="json")
        assert any(i.severity == "error" for i in issues)

    def test_valid_json(self, tmp_path):
        """Valid JSON has no issues."""
        f = tmp_path / "good.json"
        f.write_text('{"key": "value"}')
        issues = ModuleValidator().validate_file_content(f, file_format="json")
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_placeholder_detection(self, tmp_path):
        """Placeholder patterns in markdown produce warnings."""
        f = tmp_path / "todo.md"
        f.write_text("# Strategy\n\nTODO: implement this later.\nFIXME: broken\n")
        issues = ModuleValidator().validate_file_content(f)
        todo_issues = [i for i in issues if "TODO" in i.message or "placeholder" in i.message.lower()]
        assert len(todo_issues) > 0


class TestVerifyChecksums:
    """Test checksum verification."""

    def test_checksum_match(self, tmp_path):
        """Matching checksum returns True."""
        import hashlib

        f = tmp_path / "file.txt"
        f.write_text("hello world")
        h = hashlib.sha256(b"hello world").hexdigest()
        validator = ModuleValidator()
        ok, errors = validator.verify_checksums(tmp_path, {"files": [{"path": "file.txt", "checksum": h}]})
        assert ok is True
        assert len(errors) == 0

    def test_checksum_mismatch(self, tmp_path):
        """Mismatched checksum returns False with error."""
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        validator = ModuleValidator()
        ok, errors = validator.verify_checksums(
            tmp_path, {"files": [{"path": "file.txt", "checksum": "0000000000000000000000000000000000000000000000000000000000000000"}]}
        )
        assert ok is False
        assert len(errors) == 1
        assert "Checksum mismatch" in errors[0]

    def test_missing_file_checksum(self, tmp_path):
        """Missing file produces error."""
        validator = ModuleValidator()
        ok, errors = validator.verify_checksums(tmp_path, {"files": [{"path": "nonexistent.txt", "checksum": "abc"}]})
        assert ok is False
        assert any("missing" in e.lower() for e in errors)


class TestValidateWorkflowJSON:
    """Test workflow DAG validation."""

    def _make_validator(self):
        return ModuleValidator(module_base_dir="/tmp/nonexistent")

    def test_valid_workflow(self):
        """Valid workflow with nodes and edges passes."""
        data = {
            "name": "Test Workflow",
            "nodes": [
                {"id": "start", "type": "input"},
                {"id": "process", "type": "process"},
                {"id": "end", "type": "output"},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "process"},
                {"id": "e2", "source": "process", "target": "end"},
            ],
        }
        issues = self._make_validator().validate_workflow_json(data)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_missing_name(self):
        """Workflow without name gets error."""
        data = {"nodes": [{"id": "n1"}], "edges": []}
        issues = self._make_validator().validate_workflow_json(data)
        assert any(i.field == "name" for i in issues)

    def test_missing_nodes(self):
        """Workflow without nodes gets error."""
        data = {"name": "Test", "nodes": [], "edges": []}
        issues = self._make_validator().validate_workflow_json(data)
        assert any(i.field == "nodes" for i in issues)

    def test_edge_references_nonexistent_node(self):
        """Edge referencing non-existent node gets error."""
        data = {
            "name": "Test",
            "nodes": [{"id": "n1"}],
            "edges": [{"source": "n1", "target": "n2"}],
        }
        issues = self._make_validator().validate_workflow_json(data)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) > 0

    def test_cycle_detection(self):
        """Circular dependency is detected."""
        data = {
            "name": "Cyclic",
            "nodes": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c"},
            ],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"},
            ],
        }
        issues = self._make_validator().validate_workflow_json(data)
        assert any("cycle" in i.message.lower() for i in issues)

    def test_no_cycle_linear(self):
        """Linear workflow has no cycle."""
        data = {
            "name": "Linear",
            "nodes": [{"id": f"n{i}"} for i in range(5)],
            "edges": [{"source": f"n{i}", "target": f"n{i + 1}"} for i in range(4)],
        }
        issues = self._make_validator().validate_workflow_json(data)
        cycle_issues = [i for i in issues if "cycle" in i.message.lower()]
        assert len(cycle_issues) == 0

    def test_self_loop_detected(self):
        """Self-loop edge is a cycle."""
        data = {
            "name": "Self-loop",
            "nodes": [{"id": "a"}],
            "edges": [{"source": "a", "target": "a"}],
        }
        issues = self._make_validator().validate_workflow_json(data)
        assert any("cycle" in i.message.lower() for i in issues)


class TestModuleIdValidation:
    """Test module_id format validation in Pydantic model."""

    def _make_manifest(self, module_id: str) -> dict:
        return {
            "module_id": module_id,
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "files": [{"path": "f.md", "format": "markdown", "checksum": "abc", "language": "en"}],
        }

    def test_valid_danwa_prefixed(self):
        """Module IDs starting with 'danwa-' are accepted."""
        from backend.modules.models import ModuleManifest

        obj = ModuleManifest(**self._make_manifest("danwa-test-module"))
        assert obj.module_id == "danwa-test-module"

    def test_valid_core(self):
        """'danwa-core' is accepted."""
        from backend.modules.models import ModuleManifest

        obj = ModuleManifest(**self._make_manifest("danwa-core"))
        assert obj.module_id == "danwa-core"

    def test_third_party_module(self):
        """Non-danwa IDs with at least one hyphen are accepted."""
        from backend.modules.models import ModuleManifest

        obj = ModuleManifest(**self._make_manifest("my-module"))
        assert obj.module_id == "my-module"

    def test_invalid_short_id(self):
        """Too-short non-danwa ID is rejected by Pydantic validator."""
        from backend.modules.models import ModuleManifest

        with pytest.raises(Exception):  # ValidationError
            ModuleManifest(**self._make_manifest("short"))
