# Sprint 1: Skeleton — "Debate Engine API v2.0"

## Goal
A runnable FastAPI backend with LangGraph state machine, SQLite persistence scaffold, and audit trail structure. No business logic — only the skeleton. Chainlit is not touched.

## Acceptance Criteria
- `curl http://localhost:8000/health` → `{"status": "ok", "version": "2.0.0"}`
- `curl -X POST http://localhost:8000/api/v1/debate` with `{"case": {"text": "Test"}}` → returns `debate_id`
- `curl http://localhost:8000/api/v1/debate/{id}` → shows status `"pending"`
- SQLite file exists with `audit_events` table
- LangGraph graph runs through (dummy nodes, no crash)
- `pytest` → all tests green
- `ruff check debate_engine/` → no lint errors
- API docs at http://localhost:8000/docs

## Package Structure

```
debate_engine/
├── __init__.py
├── core/
│   ├── __init__.py
│   └── config.py          # Settings (pydantic-settings)
├── models/
│   ├── __init__.py
│   └── schemas.py         # Pydantic models (Case, DebateRequest, etc.)
├── workflow/
│   ├── __init__.py
│   └── debate_graph.py    # LangGraph StateGraph + dummy nodes
├── api/
│   ├── __init__.py
│   ├── deps.py            # Dependency injection
│   └── routers/
│       ├── __init__.py
│       └── debate.py      # POST /debate, GET /debate/{id}, POST /debate/{id}/start
├── persistence/
│   ├── __init__.py
│   └── audit.py           # AuditService (SQLite, append-only)
└── main.py                # FastAPI app entry point

tests/
├── __init__.py
├── conftest.py
├── test_health.py
├── test_debate_api.py
└── test_workflow.py
```

## Implementation Order (dependency order)

1. `debate_engine/core/config.py` — Settings
2. `debate_engine/models/schemas.py` — Pydantic models
3. `debate_engine/persistence/audit.py` — AuditService
4. `debate_engine/workflow/debate_graph.py` — LangGraph + dummy nodes
5. `debate_engine/api/routers/debate.py` — API routes
6. `debate_engine/main.py` — FastAPI app
7. `tests/` — Tests
8. `pyproject.toml` — Add dependencies + tool config

## Dependencies to Add

```toml
langgraph>=0.2.0
langchain-core>=0.3.0
pydantic-settings>=2.0.0
jinja2>=3.1.0
```

## pyproject.toml Tool Config

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W", "UP"]
```

## Notes
- Port 8000 for FastAPI (Chainlit stays on 7860)
- In-memory dict for debate storage in Sprint 1 (SQLite persistence in Sprint 2)
- Dummy LLM provider — no real LLM calls in Sprint 1
- API versioned as `/api/v1/` from the start
- All nodes are async but do nothing — just update state
- `should_continue` uses simple round count check
