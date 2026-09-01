# DOX: tests/

## Purpose

Test suites for the danwa frontend-only repo: frontend regression tests (pytest structural checks), shell script tests (BATS).

## Ownership

- **Frontend Tests**: `tests/frontend/` — structural regression tests (pytest; Svelte source invariants, version consistency)
- **Script Tests**: `tests/scripts/` — BATS shell contract tests pinning manage.sh / setup.sh / repo templates
- **Backend + RAG tests**: live in **danwa-core/tests**

## Local Contracts

- Frontend tests read `frontend/src` as text (no Svelte compilation needed) — plain pytest, no server required
- Script tests use the BATS framework with helpers in `tests/scripts/helpers/`; they run the **repo-templates** manage.sh, not the root one
- `tests/frontend/test_version_consistency.py` pins `/version` ↔ `frontend/package.json` parity (ported from the removed backend suite)

## Work Guidance

- Add tests for new features and bug fixes
- Follow existing test patterns (naming, fixtures, assertions)
- Keep tests independent and idempotent
- Frontend unit/E2E tests (Vitest/Playwright) live in `frontend/` and run via `npm run test:unit` / `test:e2e`

## Verification

- Frontend + manager: `uv run pytest tests/ -v`
- Scripts: `bats tests/scripts/` (known env-dependent failure: setup_studio "node not available" when node is installed at a non-standard path)

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `tests/frontend/` | Frontend structural regression tests (pytest) |
| `tests/scripts/` | Shell script tests (BATS framework) |
