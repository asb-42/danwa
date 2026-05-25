# Workflow Engine — backend

# Workflow Engine — Backend

The Workflow Engine is the runtime core of the debate platform. It compiles workflow definitions into executable plans, orchestrates node execution (LLM agent calls, gates, interjections, moderation), maintains persistent state snapshots, logs all events for audit and replay, and supports human-in-the-loop interactions. This module also provides immutability guards for locked/archived sessions and a reporting job store.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                      FastAPI Application                    │
├────────────────────────────────────────────────────────────┤
│   Blueprint Repository  │  Debate Store  │  LLM Service    │
└───────────┬─────────────┴───────┬────────┴────────┬───────┘
            │                     │                  │
┌───────────▼─────────────────────▼──────────────────▼───────┐
│                  Workflow Engine (backend/workflow/)        │
│                                                             │
│  ┌─────────────────┐   ┌──────────────────┐               │
│  │ WorkflowCompiler │──▶│ Node Functions   │               │
│  └─────────────────┘   └────────┬─────────┘               │
│                                  │                          │
│  ┌──────────────────┐   ┌───────▼──────────┐               │
│  │ StateSnapshotStore│   │   AuditLogger    │               │
│  └──────────────────┘   └──────────────────┘               │
│                                                             │
│  ┌──────────────────┐   ┌────────────────────┐             │
│  │ InterjectionSvc  │   │ HITL Subsystem     │             │
│  └──────────────────┘   │ ┌────────────────┐ │             │
│                         │ │ Security Scanner│ │             │
│  ┌──────────────────┐   │ ├────────────────┤ │             │
│  │ Immutability      │   │ │ Agent Query    │ │             │
│  │ Guards            │   │ │ Analysis       │ │             │
│  └──────────────────┘   │ ├────────────────┤ │             │
│                         │ │ State Mgmt     │ │             │
│  ┌──────────────────┐   │ └────────────────┘ │             │
│  │ ReportJobStore    │   └────────────────────┘             │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Workflow Compiler

**File:** `backend/workflow/workflow_compiler.py`

Converts a workflow definition (`WorkflowDefinition`) into an executable plan (`CompiledWorkflow`). The compiler:

- Validates the workflow graph (node existence, edge source/target validity, no missing entry point).
- Resolves agent blueprints from the `BlueprintRepository` — for each agent node it loads the blueprint, LLM profile, and role definition.
- Performs topological sorting to produce a deterministic execution order (`node_sequence`).
- Accepts feedback edges (back edges for iterative rounds), interjection edges, and gate nodes with conditional routing.
- Detects non-feedback cycles and reports them as errors.

**Primary API:**

```python
compiler = WorkflowCompiler(blueprint_repository)
result: CompiledWorkflow = compiler.compile(workflow)
```

`CompiledWorkflow` exposes:
- `is_valid` — `True` if no errors.
- `errors` / `warnings` — lists of diagnostic messages.
- `graph` — internal representation of nodes and edges.
- `node_sequence` — ordered list of node IDs for execution.
- `resolved_agents` — list of `ResolvedAgentConfig` with blueprint name, LLM profile, model, role, etc.

### 2. Workflow Node Functions

**File:** `backend/workflow/node_functions.py`

Factory functions that produce async callables for each node type. Each node function receives the current `WorkflowState` (a dict) and returns an updated state. The engine calls these in the order given by `node_sequence`.

| Function               | Node Type           | Purpose                                                                                                                                     |
|------------------------|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `input_node`           | `wf-input`          | Sets `current_draft` to the debate context, publishes `node.start` and `node.complete` events, reports zero tokens.                        |
| `initialize_wf_node`   | `wf-initialize`     | Resets `current_round` to 1, clears `current_draft` (`""`), resets `final_consensus` to `0.0`.                                              |
| `agent_node_factory`   | `wf-strategist`, `wf-critic`, `wf-optimizer` | Creates an LLM call via `LLMService.generate`. Appends output to `current_draft`. On failure sets `status: "failed"` with an error message. |
| `gate_node_factory`    | `wf-gate`           | Evaluates a Python expression (e.g. `"current_round >= 3"`) against the state. Stores the boolean result as a node output.                 |
| `interjection_node`    | `wf-interjection`   | If the interjection queue is empty, sets `is_paused=True`. Otherwise consumes all items, appends their content to `current_draft`.          |
| `moderator_node_factory` | `wf-moderator`    | Calls LLM to produce a consensus score (`0.0–1.0`), stores it in `final_consensus`, publishes `consensus.reached`.                         |
| `complete_wf_node`     | `wf-complete`       | Copies `current_draft` to `output`, sets `status` to `"completed"`, publishes `workflow.complete`.                                         |

All node functions publish lifecycle events via `publish_async` (Redis pub/sub) for real-time UI updates.

### 3. State Snapshot Store

**File:** `backend/workflow/state_snapshot.py`

Persistent storage of workflow state snapshots in a SQLite database. Snapshots record the entire state dict at each node execution, enabling replay and debugging.

| Method            | Description                                                 |
|-------------------|-------------------------------------------------------------|
| `save(...)`       | Inserts a new snapshot with session, workflow, node, state dict, and auto-generated `created_at`. |
| `get_latest(session_id)` | Returns the most recent snapshot for the session.        |
| `get_history(session_id)` | Returns all snapshots ordered chronologically.            |
| `get_by_node(session_id, node_id)` | Returns the latest snapshot for a specific node (handles repeated node executions). |

Session isolation is enforced — queries for one session never leak into another.

### 4. Audit Logger

**File:** `backend/workflow/audit_logger.py`

Records every significant event during workflow execution: node completions, interjections, workflow start/stop events. The schema includes `input_hash`/`output_hash` (SHA‑256) plus `input_content`/`output_content` (truncated to 50 KB) for traceability.

| Method                    | Event Type (`event_type`)        | Used For                          |
|---------------------------|----------------------------------|-----------------------------------|
| `log_node_execution`      | `node_completed`                 | Tracks each node after LLM call.  |
| `log_interjection`        | `interjection_submitted`         | User injection during workflow.   |
| `log_workflow_event`      | `workflow_started`, `workflow_completed`, etc. | High‑level workflow lifecycle. |

Retrieval:

- `get_audit_log(session_id, query=None)` — filterable by event type with pagination (`limit`, `offset`).
- `get_audit_log_for_replay(session_id)` — ordered by timestamp, includes content fields.
- `count_events(session_id)` — total events for a session.

### 5. Interjection Service

**File:** `backend/workflow/interjection.py`

Manages the queue of human-injected messages (interjections) that can be fed into running workflows.

| Method                    | Description                                                   |
|---------------------------|---------------------------------------------------------------|
| `submit(session_id, content, source, metadata)` | Adds an interjection, returns an ID (`inj-...`).    |
| `consume(session_id)`    | Returns and marks all pending interjections as consumed.       |
| `get_pending(session_id)` | Lists pending interjections without consuming them.           |
| `clear(session_id)`      | Removes all interjections for a session.                      |

Interjections are stored in‑memory (can be backed by Redis in production). Sessions are isolated.

### 6. HITL (Human‑in‑the‑Loop) Subsystem

**Directory:** `backend/workflow/hitl/`

Provides bidirectional human‑agent interaction loops: prompt injection scanning, agent query generation, pause/resume, and a REST API.

#### 6.1 Security Scanner

**File:** `hitl/security.py` — `scan_for_injection(content) → ScanResult`

Detects prompt injection attempts using pattern matching for:

| Category                     | Risk Level | Action              |
|------------------------------|------------|---------------------|
| `system_override`            | high       | Block (422)         |
| `role_hijack`                | high       | Block               |
| `jailbreak_keyword`          | high       | Block               |
| `prompt_extraction`          | high       | Block               |
| `delimiter_injection`        | high       | Block               |
| `token_injection`            | high       | Block               |
| `system_override_de` (German)| high       | Block               |
| `roleplay_attempt`           | medium     | Warn only (`should_warn=True`) |
| `xml_injection`              | medium     | Warn only           |

`ScanResult` has `is_safe`, `risk_level`, `should_block`, `should_warn`, `detections`, and `to_dict()`.

#### 6.2 Agent Query Analysis

**File:** `hitl/agent_query.py` — `analyze_for_query(...) → QueryAnalysisResult`

Decides whether an agent’s output should trigger a human interruption. Configurable via `auto_query_threshold` (0–1). Detection triggers:

- **Explicit marker** (`[NEEDS_CLARIFICATION]`, German clarification phrases)
- **High uncertainty** (words like “not sure”, “unclear”, “insufficient”)
- **High question density** (≥3 questions in output)
- **Minimal output** (very short answer)
- **Loop detection** (repetition compared to previous outputs)

`QueryAnalysisResult` includes `should_query`, `confidence`, `trigger_type`, `detection_details`, and optionally `suggested_question`.

#### 6.3 State Management

**File:** `hitl/api.py` (in‑memory state)

Per‑debate in‑memory data structures (also accessible via exported helpers):

- `_hitl_config` — per‑debate HITL settings (enabled, mode, thresholds).
- `_active_interrupts` — agent‑raised queries awaiting human response.
- `_paused_debates` — debates that have been paused.
- `_interaction_log` — ordered history of all HITL interactions.

Key functions:

| Function                          | Purpose                                                      |
|-----------------------------------|--------------------------------------------------------------|
| `set_hitl_config / get_hitl_config` | Manage per‑debate HITL configuration.                     |
| `is_paused`                       | Return `True` if debate is paused.                           |
| `register_agent_query`            | Create an interrupt (status `"waiting"`), log `agent_to_user` interaction. |
| `resolve_interrupt`               | Mark interrupt as `"answered"`, log `user_to_agent` response, remove from active. |
| `get_pending_injects`             | List inject interactions with status `"pending"`.            |
| `consume_inject / consume_all_pending_injects` | Mark injects as `"consumed"`.                                |
| `cleanup_hitl_state`              | Reset config, interrupts, and pause state (preserves interaction log). |

#### 6.4 API Endpoints

**Routed via** `POST /api/v1/debate/{id}/inject`, `POST /api/v1/debate/{id}/respond`, `POST /api/v1/debate/{id}/pause`, `GET /api/v1/debate/{id}/hitl/status`, `GET /api/v1/debate/{id}/interactions`.

All endpoints enforce security scanning on user‑supplied content, return 422 when blocked. They check debate existence (404) and valid state (e.g. cannot inject into pending debate → 409).

#### 6.5 Contract Models

**File:** `hitl/contracts.py`

Pydantic models for request/response validation:

- `InjectRequest` — content (1–5000 chars), optional `target_agent`, `target_round`, `priority`.
- `RespondRequest` — `interrupt_id` + `response` (non‑empty).
- `PauseRequest` — `action` (`"pause"` / `"resume"`), optional `reason`.
- `HITLStatusResponse` — debate id, HITL mode, pause state, active interrupt info, interaction counts.
- `InterruptInfo` — interrupt id, agent role, question, status (`waiting`/`answered`), elapsed time.
- `InteractionResponse` — interaction type, direction, source, target, content, timestamp, status.

### 7. Immutability & Soft Delete

**File:** `backend/workflow/immutability.py`

Prevents modification of completed/finalised sessions (for audit and compliance).

| Function             | Purpose                                                                 |
|----------------------|-------------------------------------------------------------------------|
| `lock_session(id, db)` | Set `is_locked = 1` on the session and all its state snapshots.       |
| `archive_session(id, db)` | Set `is_archived = 1` on the session, returns `True`/`False`.     |
| `restore_session(id, db)` | Un‑archive (set `is_archived = 0`), returns `True`/`False`.         |
| `guard_locked(id, db)` | Raises 403 if session is locked.                                      |
| `guard_not_archived(id, db)` | Raises 404 if session is archived.                                |
| `guard_mutable(id, db)` | Raises on either locked or archived.                                  |

Guards are idempotent for nonexistent sessions (they pass silently, allowing other error handling to take precedence).

### 8. Report Job Store

**File:** `backend/workflow/report_jobs.py` — `ReportJobStore`

Manages asynchronous report generation jobs (PDF, DOCX) in a SQLite table.

| Method              | Description                                                     |
|---------------------|-----------------------------------------------------------------|
| `create_job(session_id, format)` | Inserts a job with status `"pending"`, returns the job ID. |
| `update_job(id, status, file_path, error)` | Updates status, optionally sets `file_path` or `error`. Sets `completed_at` on completion/failure. |
| `get_job(id)`       | Returns a single job dict or `None`.                             |
| `list_jobs(session_id=None)` | Lists all jobs (newest first), optionally filtered by session. |

---

## Data Flows

### Workflow Execution Flow

1. **Compile** – `WorkflowCompiler.compile()` validates the workflow, resolves agents, and produces a `node_sequence`.
2. **State Initialization** – `StateSnapshotStore.save()` stores the initial state.
3. **Node Loop** – For each node in `node_sequence`:
   - The corresponding node function is called with the current `WorkflowState`.
   - The function updates the state (e.g., calling `LLMService`, evaluating gates, consuming interjections).
   - `AuditLogger.log_node_execution()` records the I/O hashes and content.
   - `StateSnapshotStore.save()` persists the updated state.
   - Lifecycle events are published via `publish_async`.
4. **Completion** – `complete_wf_node` sets `output` and `status = "completed"`. The session may be locked or archived.

### HITL Interaction Flow

```
User                                                                       Workflow
 │                                                                          │
 │  POST /inject (content)                                                  │
 │───▶ Security Scanner ──▶ blocked → 422                                   │
 │                          passes → interjection queued                     │
 │                                                                          │
 │  (On interjection node)                                                  │
 │                            ◀── consumes pending interjections            │
 │                                                                          │
 │  Agent output triggers query                                             │
 │                            ──▶ analyze_for_query() → should_query = True │
 │                            ──▶ register_agent_query() (interrupt created)│
 │                                                                          │
 │  GET /hitl/status                                                        │
 │◀─── active_interrupt present                                             │
 │                                                                          │
 │  POST /respond (interrupt_id, response)                                  │
 │───▶ Security Scanner ──▶ blocked → 422                                   │
 │                          passes → resolve_interrupt() → active cleared   │
 │                                                                          │
 │  Workflow resumes with the answer injected into context.                 │
```

---

## Integration with the Rest of the Codebase

| Component            | Depends On / Integrates With                                     |
|----------------------|-------------------------------------------------------------------|
| WorkflowCompiler     | `BlueprintRepository`, `AgentBlueprint`, `WorkflowDefinition`     |
| Node Functions       | `LLMService` (via `LLMService.generate`), `publish_async`, `StateSnapshotStore` (indirectly) |
| StateSnapshotStore   | SQLite database (same connection pattern as other stores)         |
| AuditLogger          | SQLite `audit_log` table; called by workflow executor             |
| InterjectionService  | Called by node functions and HITL API endpoints                   |
| HITL API             | `DebateStore` (to check/update debate status), security scanner, agent query analyzer, `InterjectionService` |
| ReportJobStore       | SQLite `report_jobs` table; used by asynchronous report generator |
| Immutability Guards  | Called by mutation endpoints before writing; refer to `workflow_sessions` and `state_snapshots` tables |

All data stores (`DebateStore`, `BlueprintRepository`, `AuditLogger`, `StateSnapshotStore`, `ReportJobStore`) use a common SQLite pattern and can be instantiated with the same project-scoped database path. The HITL subsystem currently uses in‑memory state (extensible to Redis). The workflow engine does not own the HTTP layer directly — endpoints are provided by the FastAPI router and delegate to the engine through the HITL API helpers and by invoking workflows as background tasks.