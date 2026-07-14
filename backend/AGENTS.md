# DOX: backend/

## Purpose

Python FastAPI backend providing the API layer, business logic, persistence, workflow engine, and agent-to-agent protocol for Danwa.

## Ownership

- **Core Infrastructure**: `backend/core/` — config, security, logging, profiles
- **API Layer**: `backend/api/` — FastAPI routers, dependency injection, error handling
- **Business Logic**: `backend/services/` — domain services (LLM, debate, DMS, input/output pipelines)
- **Data Models**: `backend/models/` — Pydantic/SQLAlchemy schemas
- **Persistence**: `backend/persistence/` — database stores and repositories
- **Workflow Engine**: `backend/workflow/` — LangGraph-based workflow execution
- **A2A Protocol**: `backend/a2a/` — Agent-to-Agent communication
- **Blueprint System**: `backend/blueprints/` — visual workflow builder
- **Module System**: `backend/modules/` — module installation, validation, resolution
- **Migrations**: `backend/migrations/` — database schema migrations
- **State Management**: `backend/state/` — pub/sub, workflow state

## Local Contracts

- All routers must be registered in `backend/main.py`
- Services depend on persistence stores, not direct DB access
- Models define the contract between API and persistence layers
- Workflow nodes are pure functions with typed state

## Work Guidance

- Follow existing patterns when adding new routers or services
- Use dependency injection for service dependencies
- Keep business logic in services, not routers
- Write tests for new services and routers

## Verification

- Run `pytest tests/backend/` before committing
- Ensure type checking passes with `pyright`

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `backend/api/` | HTTP API layer with 41 routers |
| `backend/services/` | Business logic services (LLM, debate, DMS, I/O pipelines) |
| `backend/workflow/` | LangGraph-based workflow engine with HITL support |
| `backend/a2a/` | Agent-to-Agent protocol implementation |
| `backend/blueprints/` | Visual blueprint/workflow builder system |
| `backend/models/` | Data models and schemas |
| `backend/persistence/` | Database stores and repositories |
| `backend/modules/` | Module system (install, validate, resolve) |
| `backend/core/` | Core infrastructure (config, security, logging) |
| `backend/migrations/` | Database migration scripts |
