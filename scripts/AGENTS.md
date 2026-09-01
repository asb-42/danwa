# DOX: scripts/

## Purpose

Management and utility scripts for the danwa user-app repo.

## Ownership

- **Shell Library**: `scripts/libdanwa.sh` — shared shell functions (sourced by `manage.sh`; canonical twin lives in danwa-core/scripts)
- **Python backend scripts**: all live in **danwa-core/scripts** — this repo has no backend, so migration/seed/doc scripts were removed (review §3.1, 2026-08-31)

## Local Contracts

- `libdanwa.sh` must remain byte-identical to `danwa-core/scripts/libdanwa.sh` — it is sourced by `manage.sh` via the `.lib/` copy created by `setup.sh`

## Work Guidance

- New app-level scripts belong here only if they operate on frontend/docs data; anything backend-related belongs in danwa-core

## Verification

- `bash -n scripts/libdanwa.sh` parses
- BATS: `bats tests/scripts/` still passes

## Child DOX Index

| Child | Purpose |
|-------|---------|
| *(none)* | |
