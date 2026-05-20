#!/usr/bin/env python3
"""Generate a knowledge base for Danwa Kitsune from the codebase.

This script extracts key information about the Danwa system:
- API endpoints
- Configuration options
- Module structure
- Database tables
- Key classes and functions

The output is a plain-text knowledge base that can be included in the
Kitsune system prompt for accurate, code-aware responses.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

OUTPUT = Path("config/prompts/kitsune/knowledge.txt")
ROOT = Path(__file__).resolve().parent.parent


def extract_api_routes() -> str:
    """Extract all API routes from backend routers."""
    routes = []
    router_dir = ROOT / "backend" / "api" / "routers"
    for f in sorted(router_dir.glob("*.py")):
        content = f.read_text()
        # Find @router.get/post/put/delete patterns
        for m in re.finditer(r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', content):
            method = m.group(1).upper()
            path = m.group(2)
            # Get the function name
            func_match = re.search(
                rf'@router\.{method}\(["\']{re.escape(path)}["\'][^\)]*\)\s*async def (\w+)',
                content,
            )
            func_name = func_match.group(1) if func_match else "?"
            # Get docstring or comment above
            lines = content[: m.start()].split("\n")
            doc = ""
            for line in reversed(lines):
                line = line.strip()
                if line.startswith('"""') or line.startswith("'''"):
                    doc = line.strip("\"'")
                    break
                elif line.startswith("#"):
                    doc = line.lstrip("# ").strip()
                    break
                elif line and not line.startswith("@"):
                    break
            prefix = ""
            if f.name == "debate.py":
                prefix = "/api/v1/debate"
            elif f.name == "config.py":
                prefix = "/api/v1/config"
            elif f.name == "projects.py":
                prefix = "/api/v1/projects"
            elif f.name == "profiles.py":
                prefix = "/api/v1/profiles"
            elif f.name == "blueprints.py":
                prefix = "/api/v1/blueprints"
            elif f.name == "canvas.py":
                prefix = "/api/v1/canvas"
            elif f.name == "dms.py":
                prefix = "/api/v1/dms"
            elif f.name == "audit.py":
                prefix = "/api/v1/audit"
            elif f.name == "assistant.py":
                prefix = "/api/v1/assistant"
            elif f.name == "translation.py":
                prefix = "/api/v1/translation"
            elif f.name == "ui_i18n.py":
                prefix = "/api/v1/i18n"
            elif f.name == "workflow_exec.py":
                prefix = "/api/v1/debate"
            elif f.name == "modules.py":
                prefix = "/api/v1/modules"
            elif f.name == "output_composer.py":
                prefix = "/api/v1/output"
            elif f.name == "input_composer.py":
                prefix = "/api/v1/input"
            elif f.name == "system.py":
                prefix = "/api/v1/system"
            elif f.name == "health.py":
                prefix = "/health"
            elif f.name == "a2a_discovery.py":
                prefix = "/api/v1/a2a"
            elif f.name == "optimization_proposals.py":
                prefix = "/api/v1/proposals"
            elif f.name == "workflow_templates.py":
                prefix = "/api/v1/blueprints/workflows"
            elif f.name == "workflow_definitions.py":
                prefix = "/api/v1/blueprints/workflows"
            elif f.name == "role_definitions.py":
                prefix = "/api/v1/blueprints"
            elif f.name == "workflow_reports.py":
                prefix = "/api/v1/blueprints/workflows"
            elif f.name == "blueprint_events.py":
                prefix = "/api/v1/blueprint-events"
            elif f.name == "debate_stream.py":
                prefix = "/api/v1/debate"
            full_path = f"{prefix}{path}"
            routes.append(f"  {method:6s} {full_path:50s} → {func_name}  {doc}")
    return "\n".join(sorted(routes))


def extract_config_options() -> str:
    """Extract all configuration options from Settings class."""
    config_file = ROOT / "backend" / "core" / "config.py"
    content = config_file.read_text()
    options = []
    for m in re.finditer(r"(\w+):\s*(\S+)\s*=\s*(.+)", content):
        name = m.group(1)
        typ = m.group(2)
        default = m.group(3).strip()
        if name.startswith("_") or name in ("model_config",):
            continue
        if typ in ("SettingsConfigDict",):
            continue
        options.append(f"  {name:35s} ({typ:20s}) default={default}")
    return "\n".join(options)


def extract_module_info() -> str:
    """Extract information about installed modules."""
    modules_dir = ROOT / "modules"
    modules = []
    for d in sorted(modules_dir.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / "manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text())
            modules.append(f"  {data.get('id', d.name):40s} type={data.get('type', '?'):20s} v{data.get('version', '?')}")
        else:
            modules.append(f"  {d.name:40s} (no manifest)")
    return "\n".join(modules)


def extract_database_tables() -> str:
    """Extract database table info from migrations."""
    mig_file = ROOT / "backend" / "blueprints" / "migrations.py"
    content = mig_file.read_text()
    tables = []
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)", content):
        table = m.group(1)
        # Get columns
        start = m.end()
        end = content.find(")", start)
        cols = content[start:end]
        col_names = []
        for cm in re.finditer(r"(\w+)\s+(TEXT|INTEGER|REAL|BLOB)", cols):
            col_names.append(cm.group(1))
        tables.append(f"  {table:30s} columns: {', '.join(col_names[:8])}")
    return "\n".join(tables)


def extract_workflow_nodes() -> str:
    """Extract workflow node functions and their docstrings."""
    nodes_file = ROOT / "backend" / "workflow" / "nodes.py"
    content = nodes_file.read_text()
    nodes = []
    for m in re.finditer(
        r"(?:async\s+)?def\s+(\w+_node)\(.*?\):\s*\"\"\"(.*?)\"\"\"",
        content,
        re.DOTALL,
    ):
        name = m.group(1)
        doc = " ".join(m.group(2).split())
        nodes.append(f"  {name:30s} {doc[:80]}")
    return "\n".join(nodes)


def main() -> None:
    sections = []

    sections.append("# Danwa Knowledge Base")
    sections.append(f"Generated from codebase at: {ROOT}")
    sections.append("")

    sections.append("## API Endpoints")
    sections.append(extract_api_routes())
    sections.append("")

    sections.append("## Configuration Options (Settings class)")
    sections.append(extract_config_options())
    sections.append("")

    sections.append("## Installed Modules")
    sections.append(extract_module_info())
    sections.append("")

    sections.append("## Database Tables")
    sections.append(extract_database_tables())
    sections.append("")

    sections.append("## Workflow Nodes")
    sections.append(extract_workflow_nodes())
    sections.append("")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(sections), encoding="utf-8")
    print(f"Knowledge base written to {OUTPUT}")
    print(f"Size: {OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
