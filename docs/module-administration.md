# Module Administration Guide

## Overview

Danwa's module system allows you to install, update, and manage extensions that add prompts, agent personas, LLM profiles, and workflow templates.

## Installing Modules

### From Local Directory

Modules in the `modules/` directory are auto-discovered on startup. To install a local module:

1. Place the module folder in `modules/`
2. Ensure it has a valid `manifest.json`
3. Restart the application (or use the Module Manager UI)

### From Remote Repository

```bash
# List available modules
python scripts/import_from_repo.py list

# Install a specific module
python scripts/import_from_repo.py install danwa-prompts-base

# Install all available modules
python scripts/import_from_repo.py install --all
```

### Via UI

1. Go to **Configuration → Modules**
2. Switch to the **Available** tab
3. Click **Install** next to the desired module
4. Confirm the installation

## Updating Modules

### Via UI

1. Go to **Configuration → Modules**
2. Switch to the **Updates** tab
3. Click **Update** next to the module

### Via API

```bash
curl -X PUT http://localhost:8000/api/v1/modules/{module_id}/update
```

## Uninstalling Modules

### Via UI

1. Go to **Configuration → Modules**
2. Find the installed module
3. Click **Uninstall**
4. Confirm the action

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/modules/{module_id}/uninstall
```

### Via CLI

```bash
# The ModuleService handles uninstallation
python -c "
from backend.modules.service import ModuleService
svc = ModuleService()
report = svc.uninstall('my-module')
print(report)
"
```

## Managing Translations

### View Translation Status

1. Go to **Configuration → Translations** (Translation Dashboard)
2. Select a module
3. View translation status per language (✅ translated, ⚠️ pending, ❌ missing)

### Trigger Translation

```bash
curl -X POST http://localhost:8000/api/v1/modules/{module_id}/translate \
  -H "Content-Type: application/json" \
  -d '{"target_language": "de", "auto_approve": true}'
```

### Manual Editing

Translations are stored in the database (`module_translation_cache` table). You can edit them directly via the Translation Dashboard UI.

## Legacy Cleanup

Old files in `profiles/` are marked with `DEPRECATED.txt` markers. To clean them up:

```bash
# Preview what would be deleted
python scripts/cleanup_legacy.py --dry-run

# Actually delete (creates backup first)
python scripts/cleanup_legacy.py --remove
```

## Troubleshooting

### Module Not Showing Up

- Check that `manifest.json` is valid JSON
- Ensure `module_id` matches the directory name
- Check logs for validation errors

### Translation Not Working

- Ensure the source language is English (SSOT)
- Check that an LLM profile is configured
- Verify the `module_translation_cache` table exists (migration V19+)

### Dependency Errors

- Install required dependencies first
- Check the `dependencies` field in `manifest.json`
- Use `GET /api/v1/modules/{module_id}` to see dependency status
