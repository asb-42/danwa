# DOX: scripts/

## Purpose

Management, migration, and utility scripts for Danwa. Includes shell scripts for service management and Python scripts for data migration and maintenance.

## Ownership

- **Shell Management**: `scripts/manage.sh`, `start.sh`, `stop.sh`, `status.sh` — service lifecycle
- **Shell Library**: `scripts/libdanwa.sh` — shared shell functions
- **Setup Scripts**: `scripts/setup_dms.sh`, `scripts/setup_searxng.sh` — initial setup
- **Python Migrations**: `scripts/migrate_*.py` — data migration scripts
- **Seed Scripts**: `scripts/seed_*.py` — seed data generators
- **Export/Import**: `scripts/export_*.py`, `scripts/import_*.py` — data export/import

## Local Contracts

- Shell scripts source `scripts/libdanwa.sh` for shared functions
- Python scripts use the project's Python environment (via `uv run`)
- Migration scripts must be idempotent where possible

## Work Guidance

- Keep scripts focused on single responsibility
- Add error handling and logging to scripts
- Document usage in script docstrings
- Test scripts with BATS when modifying shell scripts

## Verification

- Test shell scripts with `bats tests/scripts/`
- Verify Python scripts run without errors

## Child DOX Index

| Child | Purpose |
|-------|---------|
| (flat structure, no significant subdirectories) |
