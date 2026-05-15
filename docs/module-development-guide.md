# Module Development Guide

## Overview

Danwa modules are self-contained units that extend the platform's capabilities. Each module can contain prompts, agent personas, LLM profiles, or workflow templates.

## Creating a Module

### 1. Directory Structure

```
modules/my-module/
├── manifest.json          # Required: Module metadata
├── prompts/               # Optional: Prompt files
│   └── strategist.md
├── personas/              # Optional: Agent persona YAML files
│   └── my-agent.yaml
└── workflows/             # Optional: Workflow template JSON files
    └── my-workflow.json
```

### 2. Manifest Schema

```json
{
  "module_id": "my-module",
  "name": {"en": "My Module", "de": "Mein Modul"},
  "description": {"en": "Description in English"},
  "version": "1.0.0",
  "type": "argumentation-pattern",
  "category": "prompts",
  "author": {"name": "Your Name", "email": "you@example.com"},
  "license": "MIT",
  "language": "en",
  "tags": ["tag1", "tag2"],
  "dependencies": {
    "danwa-prompts-base": ">=1.0.0"
  },
  "files": [
    {"path": "prompts/strategist.md", "type": "prompt", "checksum": "sha256:..."}
  ]
}
```

### Module Types

| Type | Description |
|------|-------------|
| `argumentation-pattern` | Prompt templates for debate roles |
| `agent-persona` | Agent behavior definitions (YAML) |
| `llm-profile` | LLM configuration profiles |
| `workflow-template` | Debate workflow definitions |
| `custom` | Any other content |

### Categories

| Category | Description |
|----------|-------------|
| `prompts` | Prompt-related modules |
| `agents` | Agent persona modules |
| `llm` | LLM profile modules |
| `workflows` | Workflow template modules |
| `general` | Other modules |

## Best Practices for Prompts

1. **Write in English** — English is the SSOT. Translations are cached in the DB.
2. **Use clear role definitions** — Each prompt should clearly define the agent's role.
3. **Keep it concise** — Shorter prompts are faster and cheaper to process.
4. **Use placeholders** — Use `{case_text}`, `{round}`, etc. for dynamic content.
5. **Test with multiple LLMs** — Ensure your prompts work with different models.

## Pre-Release Checklist

- [ ] `manifest.json` is valid JSON and contains all required fields
- [ ] `module_id` is unique and lowercase-with-hyphens
- [ ] Version follows semantic versioning (MAJOR.MINOR.PATCH)
- [ ] All files listed in `manifest.files` exist
- [ ] No executable files (.py, .sh, .js) in the module
- [ ] No API keys or secrets in any files
- [ ] Dependencies are correctly specified
- [ ] Module validates with `ModuleValidator`

## Installing a Module

```bash
# From local modules/ directory (auto-discovered)
python scripts/deploy_import.py

# From remote repository
python scripts/import_from_repo.py install my-module

# List available modules
python scripts/import_from_repo.py list
```

## Exporting a Module

```bash
# Export all modules to registry.json + ZIPs
python scripts/export_to_repo.py

# Dry run (preview only)
python scripts/export_to_repo.py --dry-run
```
