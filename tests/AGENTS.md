# DOX: tests/

## Purpose

Test suites for Danwa: backend unit/integration tests (pytest), frontend tests (Vitest/Playwright), shell script tests (BATS), and RAG regression tests.

## Ownership

- **Backend Tests**: `tests/backend/` — 140+ pytest test files
- **Frontend Tests**: `tests/frontend/` — regression tests
- **Script Tests**: `tests/scripts/` — BATS shell script tests
- **RAG Regression**: `tests/rag_regression/` — RAG pipeline regression tests
- **Manager Tests**: `tests/manager/` — manager module tests

## Local Contracts

- Backend tests use fixtures from `tests/backend/conftest.py`
- Script tests use BATS framework with helpers in `tests/scripts/helpers/`
- RAG regression tests use mock LLM contracts

## Work Guidance

- Add tests for new features and bug fixes
- Follow existing test patterns (naming, fixtures, assertions)
- Keep tests independent and idempotent
- Use fixtures for shared setup, not module-level state

## Verification

- Backend: `pytest tests/backend/ -v`
- Scripts: `bats tests/scripts/`
- All tests must pass before merge

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `tests/backend/` | Backend unit/integration tests (140+ files) |
| `tests/scripts/` | Shell script tests (BATS framework) |
| `tests/rag_regression/` | RAG pipeline regression tests |
