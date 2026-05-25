# API Endpoints — api

# API Endpoints — api Module

The `backend.api` module implements the HTTP API for the Danwa debate platform. It uses FastAPI with `APIRouter` instances to group endpoints by functional area. Routes are registered in `backend/main.py` under configurable path prefixes and tags.

## Routing Structure

Each router file under `backend/api/routers/` defines an `APIRouter` instance that is mounted in the main application factory. The following table lists the available routers, their default prefix, and the tag used for OpenAPI grouping.

| Router file                  | Prefix / Base               | Tag(s)                        |
|------------------------------|-----------------------------|-------------------------------|
| `health.py`                  | `/api/v1/health`            | `system`                      |
| `config.py`                  | `/api/v1`                   | (various)                     |
| `blueprints.py`              | `/api/v1/blueprints`        | (various, via `APIRouter`)    |
| `canvas.py`                  | `/api/v1/blueprints`        | (part of blueprints group)    |
| `bundle_composer.py`         | `/api/v1/composer`          | (composer)                    |
| `argumentation_patterns.py`  | `/api/v1`                   | (argumentation-patterns)      |
| `profiles.py`                | `/api/v1/blueprints`        | (moved from blueprints)       |
| `role_definitions.py`        | `/api/v1/blueprints`        | (moved from blueprints)       |
| `workflow_definitions.py`    | `/api/v1/workflows`         | (workflows)                   |
| `workflow_exec.py`           | `/api/v1/workflow-exec`     | (workflow execution)          |
| `workflow_reports.py`        | `/api/v1/workflow-reports`  | (workflow reports)            |
| `workflow_templates.py`      | `/api/v1/workflow-templates`| (workflow templates)          |
| `debate.py`                  | `/api/v1/debates`           | (debates)                     |
| `debate_stream.py`           | `/api/v1/debates`           | (debate-stream)               |
| `assistant.py`               | `/api/v1/assistant`         | `assistant`                   |
| `audit.py`                   | `/api/v1/audit`             | (audit)                       |
| `dms.py`                     | `/api/v1/dms`               | (dms)                         |
| `input_composer.py`          | `/api/v1`                   | `input-composer`              |
| `a2a_discovery.py`           | `/api/v1/a2a`               | `a2a-discovery`               |
| `blueprint_events.py`        | `/api/v1/blueprints`        | (blueprint events)            |
| `modules.py`                 | `/api/v1/modules`           | (modules)                     |
| `sessions.py`                | `/api/v1/sessions`          | (sessions)                    |
| `translation.py`             | `/api/v1/translation`       | (translation)                 |
| `output_composer.py`         | `/api/v1/output`            | (output composition)          |
| `optimization_proposals.py`  | `/api/v1/optimization`      | (optimization proposals)      |
| `project.py`                 | `/api/v1/projects`          | (projects)                    |
| `rag_admin.py`               | `/api/v1/rag-admin`         | (RAG administration)          |
| `report_templates.py`        | `/api/v1/report-templates`  | (report templates)            |
| `search.py`                  | `/api/v1/search`            | (search)                      |
| `report.py`                  | `/api/v1/reports`           | (reports)                     |

> The prefix and tag assignments are defined in `backend/main.py`. Some routers (e.g., `config.py`) expose multiple endpoint groups under `/api/v1` by using path prefixes like `/language`, `/settings`, `/backup`, etc.

## Key Design Patterns

### Dependency Injection via FastAPI `Depends`

The module uses the `Depends` system for injecting shared objects. The file `backend/api/deps.py` provides factory functions such as:

- `get_blueprint_repository()` – returns a `BlueprintRepository` singleton per request
- `get_project_id()` – extracts the project ID from the `X-Project-Id` header
- `get_project_store()` – returns a `ProjectStore` instance
- `get_audit_service()` – returns an `AuditService` instance
- `get_debate_store_for_project(project_id, project_store)` – returns the correct `DebateStore` for a given project
- `get_profile_service()` – returns a `ProfileService` singleton
- `get_settings()` – returns the application settings object

```python
# Example from argumentation_patterns.py
@router.get("/argumentation-patterns", response_model=list[str])
def list_argumentation_patterns(
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[str]:
    ...
```

### Background Tasks for Long-Running Operations

Debate execution and workflow runs are launched as background tasks via FastAPI's `BackgroundTasks` to avoid blocking the HTTP response.

```python
# From debate.py
background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store, project_store)
```

### Server-Sent Events (SSE) for Real-Time Updates

Two real-time streaming endpoints are provided:

- `GET /api/v1/blueprints/stream` – `blueprint_events.py` – streams workflow execution events (node updates, completion, errors) for the Blueprint Canvas.
- `GET /api/v1/debates/{debate_id}/stream` – `debate_stream.py` – streams debate round results and status changes.

Both use `sse_starlette.sse.EventSourceResponse` and an internal event bus (`backend.api.events`) based on `asyncio.Queue`. The `subscribe()` and `unsubscribe()` functions manage per-session queues.

```python
# From debate_stream.py
queue = subscribe(debate_id)
try:
    while True:
        event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
        yield {"event": event_type, "data": payload}
        if event_type == "status_change":
            data = json.loads(payload)
            if data.get("status") in ("completed", "failed"):
                break
finally:
    unsubscribe(debate_id, queue)
```

### Error Handling

Routers use custom exception classes that map to HTTP status codes. The main app registers exception handlers for these at startup:

| Exception                      | HTTP Status |
|--------------------------------|-------------|
| `BlueprintNotFoundError`       | 404         |
| `BlueprintConflictError`       | 409         |

Standard `HTTPException` is used for other cases (400, 403, 500, etc.).

```python
# From blueprints.py
existing = repo.get_blueprint(entity_id)
if existing is not None:
    raise BlueprintConflictError("AgentBlueprint", entity_id)
```

### Event Bus (`backend.api.events`)

The event bus is a lightweight publish/subscribe system implemented with `asyncio.Queue`. It is used primarily for SSE streaming:

- `subscribe(session_id)` – registers a queue for a session
- `unsubscribe(session_id, queue)` – removes the queue
- `publish_async(session_id, event_type, payload)` – publishes an event to all subscribers of a session

## Functional Areas

### Blueprint Canvas and Workflow

The Blueprint system manages agent templates, bundles, canvas layouts, and workflow definitions.

**Key endpoint groups:**

- **`/api/v1/blueprints/agent-blueprints`** – CRUD for `AgentBlueprint` entities
- **`/api/v1/blueprints/bundles`** – CRUD for `AgentBundle`, plus resolve, export, and import
- **`/api/v1/blueprints/prompt-templates`** – CRUD for `PromptTemplate`
- **`/api/v1/blueprints/llm-profiles`** – CRUD for LLM profiles (extracted to `profiles.py`)
- **`/api/v1/blueprints/role-definitions`** and **`role-types`** – role definitions (extracted to `role_definitions.py`)
- **`/api/v1/blueprints/layouts`** – Canvas layout CRUD (`canvas.py`)
- **`/api/v1/blueprints/layouts/{id}/to-workflow`** – Layout → WorkflowDefinition conversion (`canvas.py`)
- **`/api/v1/blueprints/stream`** – SSE for real-time blueprint/workflow events (`blueprint_events.py`)
- **`/api/v1/blueprints/import`** – Bulk import of all blueprint entities (`blueprints.py`)
- **`/api/v1/composer`** – Bundle Composer: modular bundle assembly from components (`bundle_composer.py`)
- **`/api/v1/workflows`** – WorkflowDefinition CRUD, compile, save as template
- **`/api/v1/workflow-exec`** – Start, pause, resume, cancel, and status of workflow executions
- **`/api/v1/workflow-reports`** – Report generation jobs (async) and download
- **`/api/v1/workflow-templates`** – Predefined workflow templates (from modules + DB)

**Dependencies:** `BlueprintRepository` (`backend.blueprints.repository`), `BundleResolver`, `CanvasToWorkflowConverter`, `BundleComposer`, `CompilerService`, `WorkflowRunner`.

### Debates

Debates are the core deliberation feature. Endpoints are in `debate.py` (CRUD, lifecycle) and `debate_stream.py` (SSE).

**Key endpoints:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/v1/debates` | List debates (with status/search filter) |
| POST | `/api/v1/debates` | Create a pending debate |
| GET | `/api/v1/debates/{id}` | Get debate status & round data |
| DELETE | `/api/v1/debates/{id}` | Delete debate (if not running) |
| PATCH | `/api/v1/debates/{id}` | Move debate to another project |
| POST | `/api/v1/debates/{id}/start` | Start debate (runs as background task) |
| POST | `/api/v1/debates/{id}/cancel` | Cancel a running debate |
| POST | `/api/v1/debates/{id}/continue` | Continue from completed/failed debate |
| POST | `/api/v1/debates/{id}/fork` | Fork a debate with modifications (P4) |
| POST | `/api/v1/debates/{id}/fork-from-consensus` | Fork from consensus summary (P2) |
| POST | `/api/v1/debates/{id}/oob` | Submit out-of-band input to running debate |
| PUT | `/api/v1/debates/{id}/documents` | Assign documents to a pending debate |
| GET | `/api/v1/debates/{id}/forks` | List forks of a debate |
| GET | `/api/v1/debates/cross-project/running` | Find running debate across all projects |
| GET | `/api/v1/debates/{id}/stream` | SSE stream for real-time debate updates |
| POST | `/api/v1/debates/from-layout/{layout_id}` | Start debate from canvas layout |
| POST | `/api/v1/debates/from-workflow/{workflow_id}` | Start debate from workflow definition |
| POST | `/api/v1/debates/on-completed` | Post-completion hook (DMS document creation) |

**Dependencies:** `DebateStore`, `AuditService`, `ProjectStore`, `run_debate_workflow` (from `backend.services.debate_workflow`), event bus for SSE.

**Error handling:** Starting a non-pending debate returns 409. Cancelling a debate that is already completed is idempotent – it returns the current status without error.

### Assistant (Danwa Chat)

The assistant provides a conversational AI interface with session management.

**Endpoints:**

| Method | Path | Action |
|--------|------|--------|
| POST | `/api/v1/assistant/sessions` | Create session |
| GET | `/api/v1/assistant/sessions` | List sessions |
| GET | `/api/v1/assistant/sessions/{id}` | Get session with messages |
| DELETE | `/api/v1/assistant/sessions/{id}` | Delete session |
| POST | `/api/v1/assistant/sessions/{id}/chat` | Send message (returns new messages) |
| POST | `/api/v1/assistant/chat` | Quick chat (creates session if needed) |

**Dependencies:** `AssistantService` (singleton, initialized on first call).

### A2A Discovery

Enables inter-agent capability discovery via the A2A protocol.

**Endpoints:**

| Method | Path | Action |
|--------|------|--------|
| POST | `/api/v1/a2a/discover` | Fetch Agent Card from an A2A endpoint |
| POST | `/api/v1/a2a/capabilities/{profile_id}` | Store discovered capabilities in an LLM profile |

**Dependencies:** `A2AAdapter`, `validate_a2a_url`, `BlueprintRepository`.

### Document Management (DMS)

Manages project documents and RAG context.

**Endpoints:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/v1/dms/documents` | List documents |
| GET | `/api/v1/dms/documents/{id}` | Get document content |
| POST | `/api/v1/dms/documents` | Upload document (multipart) |
| DELETE | `/api/v1/dms/documents/{id}` | Delete document |
| POST | `/api/v1/dms/documents/{id}/rag` | Add to manual RAG context |
| DELETE | `/api/v1/dms/documents/{id}/rag` | Remove from RAG context |
| GET | `/api/v1/dms/rag/manual` | List manual RAG document IDs |
| GET | `/api/v1/dms/rag/search` | Search RAG chunks |
| GET | `/api/v1/dms/ocr-status` | Check available OCR engines |

**Dependencies:** `get_dms_for_project()` (returns a project-specific `DMS` instance), `ProjectStore`.

### Configuration and Settings

The `config.py` router provides endpoints for application-level settings, UI language, backup operations, and utility LLM management.

**Key endpoints:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/v1/settings` | Get all YAML settings |
| PUT | `/api/v1/settings` | Update settings |
| GET | `/api/v1/settings/project/{project_id}` | Get project-specific settings (merged) |
| GET | `/api/v1/language` | Get current UI language |
| PUT | `/api/v1/language` | Set UI language |
| GET | `/api/v1/version` | App version, build, git commit |
| POST | `/api/v1/backup` | Create backup |
| GET | `/api/v1/backups` | List backups |
| GET | `/api/v1/backups/{id}` | Get backup metadata |
| DELETE | `/api/v1/backups/{id}` | Delete backup |
| GET | `/api/v1/backups/{id}/files` | List files in backup |
| POST | `/api/v1/backups/{id}/verify` | Verify backup integrity |
| POST | `/api/v1/backups/{id}/restore` | Restore from backup (destructive) |
| GET | `/api/v1/backup-settings` | Current backup settings |
| PUT | `/api/v1/backup-settings` | Update backup settings |
| GET | `/api/v1/service-llm` | Get utility LLM config |
| POST | `/api/v1/service-llm` | Set utility LLM profile |
| POST | `/api/v1/validate-service-llm` | Validate profile as utility LLM |

**Dependencies:** `BackupService`, `ProfileService`, `ProjectStore`, YAML file helpers (`_load_settings`, `_save_settings`).

### Input Composer and Plugins

Provides endpoints for listing input plugins, submitting input jobs, and managing A2A approval workflows.

**Endpoints:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/v1/input-plugins` | List available input plugins |
| POST | `/api/v1/input/submit` | Submit new input (creates job, triggers workflow) |
| GET | `/api/v1/input/jobs/{job_id}` | Get job status |
| DELETE | `/api/v1/input/jobs/{job_id}` | Delete job |
| POST | `/api/v1/input/stt/stream` | STT audio streaming (SSE) |
| POST | `/api/v1/input/a2a/{task_id}/approve` | Approve pending A2A request |
| POST | `/api/v1/input/a2a/{task_id}/reject` | Reject pending A2A request |
| POST | `/api/v1/mcp/tools/call` | (reserved for future MCP integration) |

**Dependencies:** `InputComposerService`, `InputJobStore`, `InputPluginRegistry`, `STTService`, `StateSnapshotStore`, `CompilerService`, `WorkflowRunner`.

### Audit

Allows querying audit events for debates.

**Endpoints:**

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/v1/audit/{debate_id_or_title}` | Get audit events for a debate (by ID or title) |
| GET | `/api/v1/audit/project/{project_id}` | Get audit events for a whole project |

**Dependencies:** `AuditService`, `DebateStore`, `ProjectStore`. The `_enrich_events_with_debate_data` function matches stored hashes to actual agent content from the debate store.

### Health

A simple health-check endpoint.

```python
@router.get("", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    ...
```

## Integration with the Codebase

The API module depends on several core layers:

```
┌──────────────────────────────────────────┐
│            FastAPI Routers                │
│  (blueprints, debate, assistant, ...)    │
└────────────────┬─────────────────────────┘
                 │ Depends()
                 ▼
┌──────────────────────────────────────────┐
│          Dependency Providers             │
│  (deps.py: get_blueprint_repository,     │
│   get_project_store, get_audit_service)  │
└────────────────┬─────────────────────────┘
                 │
    ┌────────────┼────────────┬──────────────┐
    ▼            ▼            ▼              ▼
┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐
│Blueprint│ │Debate-  │ │Audit-    │ │Services       │
│Repository│ │Store    │ │Service   │ │(Assistant,   │
│         │ │         │ │          │ │ Profile,     │
│         │ │         │ │          │ │ DMS, etc.)   │
└─────────┘ └─────────┘ └──────────┘ └──────────────┘
```

- **BlueprintRepository** – provides CRUD operations for blueprints, bundles, prompt templates, LLM profiles, role definitions, canvas layouts, and workflow definitions. All blueprint-related routers depend on it.
- **DebateStore** – per-project debate persistence. The `get_debate_store_for_project` helper returns the correct store instance.
- **AuditService** – stores and retrieves audit events (with content hashing).
- **ProfileService** – manages LLM profiles and agent personas.
- **AssistantService** – singleton managing chat sessions and LLM interactions.
- **InputComposerService** – orchestrates input submission and job tracking.
- **WorkflowRunner** – executes compiled LangGraph workflows as background tasks.
- **Event Bus** (`backend.api.events`) – decouples SSE producers (workflow steps, debate rounds) from consumers (SSE endpoints).

The `backend.api.errors` module defines `BlueprintNotFoundError` and `BlueprintConflictError`, which are mapped to HTTP status codes by global exception handlers in `main.py`.

## Extending the API

To add a new endpoint group:

1. Create a new file in `backend/api/routers/` with an `APIRouter` instance.
2. Define your endpoint functions, using `Depends` for dependencies.
3. Register the router in `backend/main.py` (or the appropriate app factory) with a prefix and tags.
4. If the endpoint requires new dependencies, add factory functions to `backend/api/deps.py`.
5. For background tasks, use FastAPI's `BackgroundTasks` or the event bus for real-time updates.

**Error handling patterns:**

- Use `BlueprintNotFoundError` / `BlueprintConflictError` for blueprint-related resources.
- Use standard `HTTPException` for other cases.
- Raise `HTTPException(status_code=409)` to handle state conflicts (e.g., running debate).