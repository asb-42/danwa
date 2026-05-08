# Blueprint Canvas — Phase 2: API Layer & CRUD Endpoints

## 1. Overview

Phase 2 adds the FastAPI REST layer on top of the Phase 1 domain models and
repository. It introduces centralized error handling, dependency injection for
the `BlueprintRepository`, pagination support, and three new routers exposing
all Blueprint Canvas entities via HTTP.

### Goals

- Custom exception → HTTP status code mapping (404, 409, 422)
- Singleton `BlueprintRepository` via FastAPI `Depends()`
- Limit/offset pagination on all list endpoints
- CRUD endpoints for LLM Profiles, Prompt Templates, Role Definitions,
  Agent Blueprints, and Canvas Layouts
- Import endpoint (`POST /import`) for idempotent YAML/MD import
- SSE stub endpoint for future real-time canvas updates
- 62 API tests covering all endpoints, error cases, and pagination

---

## 2. Architecture Decisions

### 2.1 Dependency Injection

The `BlueprintRepository` is registered as a singleton via `@lru_cache` in
[`backend/api/deps.py`](../backend/api/deps.py). All routers import
`get_blueprint_repository` from `deps.py` and use `Depends()`:

```python
@lru_cache
def get_blueprint_repository() -> BlueprintRepository:
    """Singleton BlueprintRepository instance."""
    return BlueprintRepository()
```

This enables test isolation — tests override the dependency with a
temp-database-backed repository.

### 2.2 Error Handling

Three custom exceptions in [`backend/api/errors.py`](../backend/api/errors.py):

| Exception | HTTP Status | Use Case |
|-----------|-------------|----------|
| `BlueprintNotFoundError` | 404 | Entity not found by ID |
| `BlueprintConflictError` | 409 | Duplicate ID on create |
| `BlueprintValidationError` | 422 | Business validation failure |

`register_error_handlers(app)` maps each exception to the appropriate JSON
response with `{"detail": "..."}`.

### 2.3 Pagination

All list endpoints accept `limit` (default 50) and `offset` (default 0)
query parameters. The repository methods use `LIMIT ? OFFSET ?` in SQL.

### 2.4 Router Structure

| Router | Prefix | Entities |
|--------|--------|----------|
| `blueprints.py` | `/api/v1/blueprints` | LLM Profiles, Prompt Templates, Role Definitions, Agent Blueprints, Import |
| `canvas.py` | `/api/v1/canvas` | Canvas Layouts |
| `blueprint_events.py` | `/api/v1/blueprint-events` | SSE stream (stub) |

---

## 3. Files Changed/Created

### 3.1 New Files

| File | Purpose |
|------|---------|
| [`backend/api/errors.py`](../backend/api/errors.py) | Custom exceptions + `register_error_handlers()` |
| [`backend/api/routers/blueprints.py`](../backend/api/routers/blueprints.py) | CRUD router for all blueprint entities + import |
| [`backend/api/routers/canvas.py`](../backend/api/routers/canvas.py) | CRUD router for canvas layouts |
| [`backend/api/routers/blueprint_events.py`](../backend/api/routers/blueprint_events.py) | SSE stub router |
| [`tests/backend/test_blueprint_api.py`](../tests/backend/test_blueprint_api.py) | 62 API tests |

### 3.2 Modified Files

| File | Change |
|------|--------|
| [`backend/api/deps.py`](../backend/api/deps.py) | Added `get_blueprint_repository()` with `@lru_cache` |
| [`backend/blueprints/repository.py`](../backend/blueprints/repository.py) | Added `limit`/`offset` pagination to all 5 `list_*` methods |
| [`backend/main.py`](../backend/main.py) | Registered 3 new routers + error handlers |

---

## 4. API Endpoints

### 4.1 LLM Profiles — `/api/v1/blueprints/llm-profiles`

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/` | 200 | List all (paginated) |
| GET | `/{profile_id}` | 200/404 | Get by ID |
| POST | `/` | 201/409/422 | Create |
| PUT | `/{profile_id}` | 200/404/422 | Update |
| DELETE | `/{profile_id}` | 200/404 | Delete |

### 4.2 Prompt Templates — `/api/v1/blueprints/prompt-templates`

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/` | 200 | List (filterable by `role`, `variant`) |
| GET | `/{template_id}` | 200/404 | Get by ID |
| POST | `/` | 201/409/422 | Create |
| PUT | `/{template_id}` | 200/404/422 | Update |
| DELETE | `/{template_id}` | 200/404 | Delete |

### 4.3 Role Definitions — `/api/v1/blueprints/role-definitions`

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/` | 200 | List (filterable by `role`) |
| GET | `/{role_id}` | 200/404 | Get by ID |
| POST | `/` | 201/409/422 | Create |
| PUT | `/{role_id}` | 200/404/422 | Update |
| DELETE | `/{role_id}` | 200/404 | Delete |

### 4.4 Agent Blueprints — `/api/v1/blueprints/agent-blueprints`

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/` | 200 | List (filterable by `active_only`) |
| GET | `/{blueprint_id}` | 200/404 | Get by ID |
| POST | `/` | 201/409/422 | Create (FK: requires existing LLM profile + role) |
| PUT | `/{blueprint_id}` | 200/404/422 | Update |
| DELETE | `/{blueprint_id}` | 200/404 | Delete |

### 4.5 Import — `POST /api/v1/blueprints/import`

Triggers idempotent import from `profiles/` and `archive/config/` directories.

```json
// Request (optional)
{"dry_run": true}

// Response
{"created": 42, "updated": 0, "skipped": 0, "errors": []}
```

### 4.6 Canvas Layouts — `/api/v1/canvas/layouts`

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `/` | 200 | List (filterable by `project_id`) |
| GET | `/{layout_id}` | 200/404 | Get by ID |
| POST | `/` | 201/409/422 | Create |
| PUT | `/{layout_id}` | 200/404/422 | Update |
| DELETE | `/{layout_id}` | 200/404 | Delete |

### 4.7 SSE Stream — `GET /api/v1/blueprint-events/stream`

Stub SSE endpoint that sends a ping every 30 seconds. Will be extended in
Phase 3/4 for real-time canvas collaboration.

---

## 5. Test Coverage

62 tests in [`tests/backend/test_blueprint_api.py`](../tests/backend/test_blueprint_api.py):

| Test Class | Count | Coverage |
|------------|-------|----------|
| `TestLLMProfileAPI` | 11 | CRUD, pagination, 404, 409 |
| `TestPromptTemplateAPI` | 10 | CRUD, role/variant filtering, pagination |
| `TestRoleDefinitionAPI` | 9 | CRUD, role filtering, pagination |
| `TestAgentBlueprintAPI` | 8 | CRUD, active_only filter, FK prerequisites |
| `TestCanvasLayoutAPI` | 9 | CRUD, project filter, blueprint refs roundtrip |
| `TestImportAPI` | 3 | Result shape, dry_run, idempotency |
| `TestErrorHandling` | 8 | 404/409/422 detail messages |
| `TestBlueprintHealth` | 2 | Route registration smoke tests |

---

## 6. Implementation Order

1. ✅ `backend/api/errors.py` — Custom exceptions + error handlers
2. ✅ `backend/api/deps.py` — `get_blueprint_repository()` singleton
3. ✅ `backend/blueprints/repository.py` — Pagination in all list methods
4. ✅ `backend/api/routers/blueprints.py` — Blueprint CRUD + import
5. ✅ `backend/api/routers/canvas.py` — Canvas layout CRUD
6. ✅ `backend/api/routers/blueprint_events.py` — SSE stub
7. ✅ `backend/main.py` — Router + error handler registration
8. ✅ `tests/backend/test_blueprint_api.py` — 62 API tests
9. ✅ Ruff + pytest pass
10. ✅ This README

---

## 7. Key Design Patterns

### FK Constraint Enforcement

The `agent_blueprints` table has FOREIGN KEY constraints on
`llm_profile_id` → `blueprint_llm_profiles.id` and
`role_definition_id` → `role_definitions.id`. The API returns 500
(IntegrityError) if prerequisites don't exist. Tests use
`_seed_prerequisites()` to create the required entities first.

### Test Isolation

Each test gets a fresh `BlueprintRepository` backed by a temp SQLite database
(via `tmp_path`). The `get_blueprint_repository` dependency is overridden in
the test app fixture, ensuring no state leaks between tests.

### Import Endpoint

The import endpoint reads from the real filesystem (`profiles/` and
`archive/config/`). It uses `BlueprintImporter` from Phase 1, which is
idempotent — running it twice produces `created == 0` on the second run.
