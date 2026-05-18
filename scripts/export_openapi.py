#!/usr/bin/env python3
"""Export FastAPI OpenAPI specification and convert to Markdown.

Usage:
    python scripts/export_openapi.py              # Export OpenAPI JSON
    python scripts/export_openapi.py --markdown   # Export as Markdown
    python scripts/export_openapi.py --both        # Export both JSON and Markdown
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app  # noqa: E402

DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUT_JSON = DOCS_DIR / "api-reference.json"
OUTPUT_MD = DOCS_DIR / "api-reference.md"


def export_json() -> dict:
    """Export OpenAPI specification as JSON."""
    spec = app.openapi()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(spec, indent=2, ensure_ascii=False))
    print(f"[OK] OpenAPI JSON exported: {OUTPUT_JSON}")
    return spec


def spec_to_markdown(spec: dict) -> str:
    """Convert OpenAPI specification to Markdown documentation."""
    lines: list[str] = []

    info = spec.get("info", {})
    lines.append(f"# API Reference — {info.get('title', 'API')}")
    lines.append("")
    lines.append(f"> **Version**: {info.get('version', 'unknown')}")
    if info.get("description"):
        lines.append(f"> **Description**: {info['description']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Base URL
    servers = spec.get("servers", [])
    if servers:
        lines.append("## Base URL")
        lines.append("")
        for server in servers:
            url = server["url"]
            desc = server.get("description", "")
            if desc:
                lines.append(f"- `{url}` — {desc}")
            else:
                lines.append(f"- `{url}`")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Table of Contents
    paths = spec.get("paths", {})
    tags = spec.get("tags", [])
    tag_descriptions = {t["name"]: t.get("description", "") for t in tags}

    # Group paths by tags
    tag_paths: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in sorted(paths.items()):
        for method, operation in sorted(methods.items()):
            if method in ("get", "post", "put", "delete", "patch"):
                op_tags = operation.get("tags", ["untagged"])
                for tag in op_tags:
                    tag_paths.setdefault(tag, [])
                    tag_paths[tag].append((path, method.upper(), operation))

    lines.append("## Table of Contents")
    lines.append("")
    for tag in sorted(tag_paths.keys()):
        anchor = tag.lower().replace(" ", "-").replace("/", "")
        lines.append(f"- [{tag}](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Security schemes
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    if security_schemes:
        lines.append("## Authentication")
        lines.append("")
        for name, scheme in security_schemes.items():
            scheme_type = scheme.get("type", "unknown")
            if scheme_type == "http":
                lines.append(f"- **{name}**: HTTP {scheme.get('scheme', 'bearer')} authentication")
            elif scheme_type == "apiKey":
                location = scheme.get("in", "header")
                param_name = scheme.get("name", "unknown")
                lines.append(f"- **{name}**: API Key in {location} (`{param_name}`)")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Schemas reference
    schemas = spec.get("components", {}).get("schemas", {})
    if schemas:
        lines.append("## Data Models")
        lines.append("")
        for schema_name in sorted(schemas.keys()):
            anchor = schema_name.lower()
            lines.append(f"- [{schema_name}](#data-model-{anchor})")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Endpoints by tag
    for tag in sorted(tag_paths.keys()):
        lines.append(f"## {tag}")
        lines.append("")
        if tag in tag_descriptions and tag_descriptions[tag]:
            lines.append(tag_descriptions[tag])
            lines.append("")

        for path, method, operation in tag_paths[tag]:
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            operation_id = operation.get("operationId", "")

            lines.append(f"### `{method}` `{path}`")
            lines.append("")
            if summary:
                lines.append(f"**{summary}**")
                lines.append("")
            if description:
                lines.append(description)
                lines.append("")
            if operation_id:
                lines.append(f"*Operation ID*: `{operation_id}`")
                lines.append("")

            # Parameters
            parameters = operation.get("parameters", [])
            if parameters:
                lines.append("**Parameters:**")
                lines.append("")
                lines.append("| Name | In | Type | Required | Description |")
                lines.append("|------|----|------|----------|-------------|")
                for param in parameters:
                    name = param.get("name", "")
                    location = param.get("in", "")
                    required = "✓" if param.get("required", False) else ""
                    desc = param.get("description", "")
                    schema = param.get("schema", {})
                    param_type = schema.get("type", "string")
                    if schema.get("enum"):
                        param_type = f"enum({', '.join(str(v) for v in schema['enum'])})"
                    lines.append(f"| `{name}` | {location} | {param_type} | {required} | {desc} |")
                lines.append("")

            # Request body
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                if "application/json" in content:
                    body_schema = content["application/json"].get("schema", {})
                    required_fields = body_schema.get("required", [])
                    properties = body_schema.get("properties", {})

                    lines.append("**Request Body:**")
                    lines.append("")
                    if properties:
                        lines.append("| Field | Type | Required | Description |")
                        lines.append("|-------|------|----------|-------------|")
                        for field_name, field_schema in sorted(properties.items()):
                            field_type = field_schema.get("type", "string")
                            field_required = "✓" if field_name in required_fields else ""
                            field_desc = field_schema.get("description", "")
                            lines.append(f"| `{field_name}` | {field_type} | {field_required} | {field_desc} |")
                        lines.append("")

            # Responses
            responses = operation.get("responses", {})
            if responses:
                lines.append("**Responses:**")
                lines.append("")
                lines.append("| Status | Description |")
                lines.append("|--------|-------------|")
                for status_code in sorted(responses.keys()):
                    response = responses[status_code]
                    desc = response.get("description", "")
                    lines.append(f"| `{status_code}` | {desc} |")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Detailed schema definitions
    if schemas:
        lines.append("## Schema Definitions")
        lines.append("")

        for schema_name in sorted(schemas.keys()):
            schema = schemas[schema_name]
            anchor = schema_name.lower()

            lines.append(f"### Data Model: `{schema_name}`")
            lines.append("")

            if schema.get("description"):
                lines.append(schema["description"])
                lines.append("")

            if schema.get("type") == "object":
                properties = schema.get("properties", {})
                required_fields = schema.get("required", [])

                if properties:
                    lines.append("| Field | Type | Required | Description |")
                    lines.append("|-------|------|----------|-------------|")
                    for field_name, field_schema in sorted(properties.items()):
                        field_type = field_schema.get("type", "string")
                        if "$ref" in field_schema:
                            ref = field_schema["$ref"].split("/")[-1]
                            field_type = f"[{ref}](#data-model-{ref.lower()})"
                        elif field_schema.get("type") == "array":
                            items = field_schema.get("items", {})
                            if "$ref" in items:
                                ref = items["$ref"].split("/")[-1]
                                field_type = f"array[[{ref}](#data-model-{ref.lower()})]"
                            else:
                                field_type = f"array[{items.get('type', 'any')}]"
                        elif field_schema.get("enum"):
                            field_type = f"enum({', '.join(str(v) for v in field_schema['enum'])})"

                        field_required = "✓" if field_name in required_fields else ""
                        field_desc = field_schema.get("description", "")
                        lines.append(f"| `{field_name}` | {field_type} | {field_required} | {field_desc} |")
                    lines.append("")
            elif schema.get("enum"):
                lines.append(f"**Values**: `{', '.join(str(v) for v in schema['enum'])}`")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def export_markdown(spec: dict | None = None) -> str:
    """Export OpenAPI specification as Markdown."""
    if spec is None:
        spec = app.openapi()

    md = spec_to_markdown(spec)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"[OK] Markdown exported: {OUTPUT_MD}")
    return md


def main():
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI spec")
    parser.add_argument("--markdown", action="store_true", help="Export as Markdown")
    parser.add_argument("--json", action="store_true", help="Export as JSON")
    parser.add_argument("--both", action="store_true", help="Export both JSON and Markdown")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of file")
    args = parser.parse_args()

    # Default: both if no flag specified
    if not args.markdown and not args.json and not args.both and not args.stdout:
        args.both = True

    spec = app.openapi()

    if args.stdout:
        if args.markdown:
            print(spec_to_markdown(spec))
        else:
            print(json.dumps(spec, indent=2, ensure_ascii=False))
        return

    if args.json or args.both:
        export_json()

    if args.markdown or args.both:
        export_markdown(spec)

    print(f"\n[OK] Done. Files written to {DOCS_DIR}/")


if __name__ == "__main__":
    main()
