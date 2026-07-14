# DOX: src/

## Purpose

Shared Python core library containing the debate engine, DMS (Document Management System), LLM router, and utility tools. This is the legacy monolith core being migrated into `backend/`.

## Ownership

- **Debate Engine**: `src/core/debate_engine.py` — core debate logic
- **LLM Router**: `src/core/llm_router.py` — LLM provider routing
- **DMS**: `src/dms/` — document processing, chunking, retrieval
- **Tools**: `src/tools/` — document parser, report generator, web search

## Local Contracts

- Modules here may be imported by both `backend/` and standalone scripts
- Keep backward compatibility during migration to `backend/`
- DMS interfaces must match `backend/services/dms/` contracts

## Work Guidance

- Prefer adding new code to `backend/services/` over `src/`
- When modifying shared interfaces, update both `src/` and `backend/` copies
- Mark deprecated code with `# DEPRECATED: use backend/services/...`

## Verification

- Run `pytest tests/backend/` for integration tests
- Check imports work from both `backend/` and standalone contexts

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `src/core/` | Debate engine, LLM router, prompt management |
| `src/dms/` | Document Management System (shared) |
| `src/tools/` | Utility tools (parser, reports, web search) |
