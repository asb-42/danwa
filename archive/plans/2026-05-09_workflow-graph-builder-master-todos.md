# Workflow Graph Builder — Master To-Do List

> **Purpose**: Granular task tracking for crash recovery. Each checkbox is a single, independently resumable unit of work.
>
> **Phase Sequence**: Phase 1 → Phase 2 → Phase 7 → Phase 8
>
> **Plan Documents**:
> - [Phase 1](workflow-graph-builder-phase1.md) — Backend Models, Frontend Nodes, Registry, Validation
> - [Phase 2](workflow-graph-builder-phase2.md) — Compilation, Execution Engine, SSE, State Snapshots
> - [Phase 7](workflow-graph-builder-phase7.md) — Audit, Traceability, Reporting, Immutability
> - [Phase 8](workflow-graph-builder-phase8.md) — A2A Integration, External Agents

---

## Phase 1: Backend Models, Frontend Nodes, Registry, Validation

### Group A: Backend Model Extension

- [ ] **A.1** Extend [`workflow_models.py`](../backend/blueprints/workflow_models.py) with `WorkflowNode`, `WorkflowEdge`, `TerminationCondition` models
  - [ ] A.1.1 Add `WorkflowNode` Pydantic model with type literal, agent_blueprint_id, config
  - [ ] A.1.2 Add `WorkflowEdge` Pydantic model with type literal, condition
  - [ ] A.1.3 Add `TerminationCondition` Pydantic model
  - [ ] A.1.4 Extend `WorkflowDefinition` with `nodes`, `edges`, `entry_point`, `termination_conditions`, `version`, `is_locked` fields
  - [ ] A.1.5 Add field validators: entry_point must reference valid node ID, agent nodes must have agent_blueprint_id
- [ ] **A.2** Add SQLite migration v4 for new columns on `workflow_definitions`
  - [ ] A.2.1 Add `nodes_json TEXT DEFAULT '[]'`
  - [ ] A.2.2 Add `edges_json TEXT DEFAULT '[]'`
  - [ ] A.2.3 Add `entry_point TEXT`
  - [ ] A.2.4 Add `termination_conditions_json TEXT DEFAULT '[]'`
  - [ ] A.2.5 Add `version INTEGER DEFAULT 1`
  - [ ] A.2.6 Add `is_locked INTEGER DEFAULT 0`
  - [ ] A.2.7 Bump `SCHEMA_VERSION` to 4
- [ ] **A.3** Update [`repository.py`](../backend/blueprints/repository.py) `save_workflow_definition` and `_row_to_workflow_definition`
  - [ ] A.3.1 Serialize new fields (nodes_json, edges_json, entry_point, termination_conditions_json, version, is_locked)
  - [ ] A.3.2 Deserialize new fields in `_row_to_workflow_definition`
- [ ] **A.4** Extend [`compiler.py`](../backend/blueprints/compiler.py) validation
  - [ ] A.4.1 Validate entry_point references a valid node
  - [ ] A.4.2 Validate all agent nodes have valid agent_blueprint_id references
  - [ ] A.4.3 Validate gate nodes have at least 2 outgoing edges
  - [ ] A.4.4 Validate no isolated nodes (every node must have at least one edge)
  - [ ] A.4.5 Detect cycles (warning, not error — feedback edges create intentional cycles)
  - [ ] A.4.6 Validate edge source/target reference valid node IDs
- [ ] **A.5** Add clone endpoint to [`blueprints.py`](../backend/api/routers/blueprints.py)
  - [ ] A.5.1 `POST /api/v1/blueprints/workflows/{wf_id}/clone` — deep-copy with new ID, incremented version, `is_locked=False`
- [ ] **A.6** Write backend tests for new models, migration, repository, API clone endpoint
  - [ ] A.6.1 Test `WorkflowNode` model validation (agent nodes require blueprint_id)
  - [ ] A.6.2 Test `WorkflowEdge` model validation (conditional edges require condition)
  - [ ] A.6.3 Test `TerminationCondition` model
  - [ ] A.6.4 Test extended `WorkflowDefinition` with nodes/edges/entry_point
  - [ ] A.6.5 Test migration v4 applies cleanly
  - [ ] A.6.6 Test repository roundtrip with new fields
  - [ ] A.6.7 Test clone endpoint (creates new ID, increments version)
  - [ ] A.6.8 Test compiler validation (missing entry_point, isolated nodes, invalid refs, gate outputs)

### Group B: Frontend Node Components

- [ ] **B.1** Create [`InputNode.svelte`](../frontend/src/components/blueprint/nodes/InputNode.svelte) — Blue (#3b82f6), 📥, RIGHT handle only, data-testid="node-wf-input"
- [ ] **B.2** Create [`InitializeNode.svelte`](../frontend/src/components/blueprint/nodes/InitializeNode.svelte) — Cyan (#06b6d4), 🚀, LEFT+RIGHT handles, data-testid="node-wf-initialize"
- [ ] **B.3** Create [`StrategistNode.svelte`](../frontend/src/components/blueprint/nodes/StrategistNode.svelte) — Purple (#8b5cf6), 🧠, LEFT+RIGHT, shows AgentBlueprint name, data-testid="node-wf-strategist"
- [ ] **B.4** Create [`CriticNode.svelte`](../frontend/src/components/blueprint/nodes/CriticNode.svelte) — Red (#ef4444), 🔍, LEFT+RIGHT, shows AgentBlueprint name, data-testid="node-wf-critic"
- [ ] **B.5** Create [`OptimizerNode.svelte`](../frontend/src/components/blueprint/nodes/OptimizerNode.svelte) — Amber (#f59e0b), ⚡, LEFT+RIGHT, shows AgentBlueprint name, data-testid="node-wf-optimizer"
- [ ] **B.6** Create [`ModeratorNode.svelte`](../frontend/src/components/blueprint/nodes/ModeratorNode.svelte) — Green (#10b981), 🎯, LEFT+RIGHT+BOTTOM feedback, data-testid="node-wf-moderator"
- [ ] **B.7** Create [`UserInjectionNode.svelte`](../frontend/src/components/blueprint/nodes/UserInjectionNode.svelte) — Indigo (#6366f1), 👤, LEFT+RIGHT+BOTTOM interjection, data-testid="node-wf-user-injection"
- [ ] **B.8** Create [`GateNode.svelte`](../frontend/src/components/blueprint/nodes/GateNode.svelte) — Rose (#f43f5e), 🔀, LEFT+RIGHT true+BOTTOM false, data-testid="node-wf-gate"

### Group C: Frontend Edge Component

- [ ] **C.1** Create [`FeedbackEdge.svelte`](../frontend/src/components/blueprint/edges/FeedbackEdge.svelte) — Green (#10b981), dash-dot stroke, getBezierPath with offset, "feedback" label, data-testid="edge-feedback"

### Group D: Registry & Validation Updates

- [ ] **D.1** Update [`registerAll.js`](../frontend/src/lib/blueprint/registerAll.js)
  - [ ] D.1.1 Remove 5 placeholder workflow node registrations (lines 127-200)
  - [ ] D.1.2 Register 8 new specialized node types with `active: true`
  - [ ] D.1.3 Register `feedback` edge type with `FeedbackEdge` component
  - [ ] D.1.4 Import all new components
- [ ] **D.2** Update [`validation.js`](../frontend/src/lib/blueprint/validation.js)
  - [ ] D.2.1 Add `WORKFLOW_CONNECTION_RULES` map defining allowed connections per node type
  - [ ] D.2.2 Add `feedback` to `EDGE_STYLES`
  - [ ] D.2.3 Update `validateControlFlowConnection()` with specific rules per node type
  - [ ] D.2.4 Add `getWorkflowEdgeType(sourceType, targetType, data?)` function
- [ ] **D.3** Update [`store.svelte.js`](../frontend/src/lib/blueprint/store.svelte.js) `loadFromLayout()`
  - [ ] D.3.1 Add new workflow node types to `nodeTypeMap`
  - [ ] D.3.2 Handle `role-type` in the map
- [ ] **D.4** Update [`layout.js`](../frontend/src/lib/blueprint/layout.js)
  - [ ] D.4.1 Add `NODE_DIMENSIONS` entries for all 8 workflow node types
  - [ ] D.4.2 Add `feedbackEdges: true` to elkOptions
  - [ ] D.4.3 Add `elk.layered.feedbackEdges: 'true'` option

### Group E: Inspector Forms

- [ ] **E.1** Create [`WorkflowNodeForm.svelte`](../frontend/src/components/blueprint/forms/WorkflowNodeForm.svelte)
  - [ ] E.1.1 Generic form for all workflow node types (label, node type, linked AgentBlueprint)
  - [ ] E.1.2 Agent nodes: AgentBlueprint selector dropdown
  - [ ] E.1.3 Gate nodes: condition text input
  - [ ] E.1.4 User-injection nodes: input_type selector
  - [ ] E.1.5 Save updates node data via `canvasStore.updateNodeData()`
- [ ] **E.2** Update [`Inspector.svelte`](../frontend/src/components/blueprint/Inspector.svelte)
  - [ ] E.2.1 Add routing for all 8 workflow node types → `WorkflowNodeForm`
  - [ ] E.2.2 Import `WorkflowNodeForm`

### Group F: Palette & Mode Updates

- [ ] **F.1** Update [`Palette.svelte`](../frontend/src/components/blueprint/Palette.svelte)
  - [ ] F.1.1 In workflow mode: hide asset nodes section, show only workflow nodes
  - [ ] F.1.2 Add "Workflow Definition" section with workflow-level controls
- [ ] **F.2** Update [`BlueprintCanvas.svelte`](../frontend/src/components/blueprint/BlueprintCanvas.svelte)
  - [ ] F.2.1 Add "Validate" button to toolbar (visible only in workflow mode)
  - [ ] F.2.2 Implement DFS-based client-side validation (entry point, reachability, isolated nodes, gate outputs, agent blueprint_id)
  - [ ] F.2.3 Display validation results in toast/panel
  - [ ] F.2.4 Add "Clone Workflow" button
  - [ ] F.2.5 Update MiniMap `nodeColor` function for new node types

### Group G: API Client & i18n

- [ ] **G.1** Update [`api.js`](../frontend/src/lib/blueprint/api.js)
  - [ ] G.1.1 Add `cloneWorkflow(wfId)` function
  - [ ] G.1.2 Add `validateWorkflow(wfId)` function (optional)
- [ ] **G.2** Update [`en.js`](../frontend/src/lib/i18n/loaders/en.js) and [`de.js`](../frontend/src/lib/i18n/loaders/de.js)
  - [ ] G.2.1 Add palette labels/descriptions for all 8 workflow node types
  - [ ] G.2.2 Add edge labels for `feedback`
  - [ ] G.2.3 Add form labels for workflow node inspector
  - [ ] G.2.4 Add validation result messages
  - [ ] G.2.5 Add clone/validate button labels

### Group H: Integration & Testing

- [ ] **H.1** Update [`dnd.js`](../frontend/src/lib/blueprint/dnd.js) — ensure `createDraftNode()` handles new workflow node types
- [ ] **H.2** Run all backend tests — verify 190+ tests pass
- [ ] **H.3** Run frontend build — verify no compilation errors
- [ ] **H.4** Manual smoke test: create workflow with all 8 node types, connect with all 4 edge types, validate, clone

---

## Phase 2: Compilation, Execution Engine, SSE, State Snapshots

### Group A: WorkflowState & Compiler Extension

- [ ] **A.1** Create [`backend/workflow/workflow_state.py`](../backend/workflow/workflow_state.py)
  - [ ] A.1.1 Define `WorkflowNodeOutput`, `WorkflowState` TypedDicts
  - [ ] A.1.2 Use `Annotated[list, operator.add]` for `node_outputs`, `messages`, `consumed_interjections`
- [ ] **A.2** Create [`backend/workflow/workflow_compiler.py`](../backend/workflow/workflow_compiler.py)
  - [ ] A.2.1 `WorkflowCompiler` class taking `WorkflowDefinition` + `BlueprintRepository`
  - [ ] A.2.2 `compile() → CompiledWorkflow` method: validate blueprints, topological sort, build StateGraph, add nodes/edges, set entry point, compile
  - [ ] A.2.3 `CompiledWorkflow` dataclass: `graph`, `resolved_agents`, `node_sequence`, `errors`, `warnings`
  - [ ] A.2.4 Handle feedback edges as conditional back-edges with round guard
  - [ ] A.2.5 Handle interjection edges by inserting `interjection_node` between source and target
- [ ] **A.3** Create [`backend/workflow/node_functions.py`](../backend/workflow/node_functions.py)
  - [ ] A.3.1 `input_node(state) → dict` — extracts context, no LLM call
  - [ ] A.3.2 `initialize_wf_node(state) → dict` — sets `current_round=1`, resets accumulators
  - [ ] A.3.3 `agent_node_factory(node_id, resolved_agent) → Callable` — resolves prompts, calls LLMService.generate(), publishes SSE, returns partial state
  - [ ] A.3.4 `gate_node_factory(node_id, condition_expr) → Callable` — evaluates condition, returns routing key
  - [ ] A.3.5 `interjection_node(state) → dict` — checks `interjection_queue`, if empty sets `is_paused=True`
  - [ ] A.3.6 `moderator_node_factory(node_id, resolved_agent, threshold) → Callable` — agent call + consensus evaluation
  - [ ] A.3.7 `complete_wf_node(state) → dict` — final output assembly
- [ ] **A.4** Create [`backend/workflow/workflow_routers.py`](../backend/workflow/workflow_routers.py)
  - [ ] A.4.1 `route_sequential(state) → str` — always returns next node
  - [ ] A.4.2 `route_conditional(state, conditions) → str` — evaluates condition expressions
  - [ ] A.4.3 `route_feedback(state, max_rounds) → str` — returns "continue" or "exit"
  - [ ] A.4.4 `route_after_interjection(state) → str` — returns next node after interjection
- [ ] **A.5** Extend [`backend/blueprints/compiler.py`](../backend/blueprints/compiler.py)
  - [ ] A.5.1 Add `compile_to_langgraph(workflow, repo) → CompiledWorkflow` method
  - [ ] A.5.2 Keep existing `compile()` method for validation-only use
  - [ ] A.5.3 Update `POST /api/v1/blueprints/workflows/{id}/compile` to optionally return compiled graph metadata

### Group B: Interjection Service

- [ ] **B.1** Create [`backend/workflow/interjection.py`](../backend/workflow/interjection.py)
  - [ ] B.1.1 `InterjectionService` class with `submit()`, `consume()`, `get_pending()`, `clear()`
  - [ ] B.1.2 In-memory queue per session, thread-safe with `asyncio.Lock`
- [ ] **B.2** Create interjection API endpoint
  - [ ] B.2.1 `POST /api/v1/workflow-exec/{session_id}/interject`
  - [ ] B.2.2 Request body: `{content, source, metadata}`
  - [ ] B.2.3 Calls `InterjectionService.submit()`, publishes SSE event `interjection.received`

### Group C: Execution Engine

- [ ] **C.1** Create [`backend/api/routers/workflow_exec.py`](../backend/api/routers/workflow_exec.py)
  - [ ] C.1.1 `POST /{workflow_id}/start` — loads WorkflowDefinition, compiles, builds initial state, launches background task
  - [ ] C.1.2 `GET /{session_id}/state` — returns current execution state from SQLite snapshot
  - [ ] C.1.3 `POST /{session_id}/pause` — sets `is_paused=True`
  - [ ] C.1.4 `POST /{session_id}/resume` — sets `is_paused=False`, signals `pause_event`
  - [ ] C.1.5 `POST /{session_id}/cancel` — adds to `_cancelled_sessions` set
  - [ ] C.1.6 `GET /{session_id}/stream` — SSE endpoint, subscribes to event bus
- [ ] **C.2** Create [`backend/workflow/workflow_runner.py`](../backend/workflow/workflow_runner.py)
  - [ ] C.2.1 `run_workflow_background()` async function
  - [ ] C.2.2 Publish `workflow.started` SSE event
  - [ ] C.2.3 Call `compiled_workflow.graph.ainvoke(initial_state)`
  - [ ] C.2.4 Between each node: check `is_paused`, check `_cancelled_sessions`
  - [ ] C.2.5 After each node: save state snapshot to SQLite
  - [ ] C.2.6 On completion: publish `workflow.complete`, update session status
  - [ ] C.2.7 On error: publish `node.error`, update session status to FAILED
  - [ ] C.2.8 Pause/resume via shared `asyncio.Event` in state
- [ ] **C.3** Create [`backend/workflow/state_snapshot.py`](../backend/workflow/state_snapshot.py)
  - [ ] C.3.1 `StateSnapshotStore` class with `save()`, `get_latest()`, `get_history()`, `get_by_node()`
  - [ ] C.3.2 Uses same SQLite connection pattern as `BlueprintRepository`

### Group D: Migration & Registration

- [ ] **D.1** Add migration v4 to [`backend/blueprints/migrations.py`](../backend/blueprints/migrations.py)
  - [ ] D.1.1 Create `workflow_state_snapshots` table
  - [ ] D.1.2 Create `workflow_sessions` table with indexes
  - [ ] D.1.3 Bump `SCHEMA_VERSION` to 4
- [ ] **D.2** Register new router in [`backend/main.py`](../backend/main.py)
  - [ ] D.2.1 Import and register `workflow_exec` router at `/api/v1/workflow-exec`
- [ ] **D.3** Update [`backend/api/routers/blueprint_events.py`](../backend/api/routers/blueprint_events.py)
  - [ ] D.3.1 Replace stub with real SSE endpoint subscribing to workflow event bus

### Group E: Frontend Integration

- [ ] **E.1** Create [`frontend/src/lib/workflowExec.js`](../frontend/src/lib/workflowExec.js)
  - [ ] E.1.1 API client: `startWorkflow()`, `getWorkflowState()`, `pauseWorkflow()`, `resumeWorkflow()`, `cancelWorkflow()`, `submitInterjection()`
- [ ] **E.2** Create [`frontend/src/lib/workflowSSE.js`](../frontend/src/lib/workflowSSE.js)
  - [ ] E.2.1 `createWorkflowSSE(sessionId, handlers)` — SSE connection for workflow execution
  - [ ] E.2.2 Handle named events: `workflow.started`, `node.start`, `node.complete`, `node.error`, `interjection.received`, `consensus.reached`, `workflow.complete`, `workflow.paused`, `workflow.resumed`
- [ ] **E.3** Update [`BlueprintCanvas.svelte`](../frontend/src/components/blueprint/BlueprintCanvas.svelte)
  - [ ] E.3.1 Add "Execute" button (visible in workflow mode when valid)
  - [ ] E.3.2 On click: call `startWorkflow()`, open SSE connection
  - [ ] E.3.3 On `node.start`: set node visual to "running" state (pulsing animation)
  - [ ] E.3.4 On `node.complete`: set node visual to "completed" state (green checkmark)
  - [ ] E.3.5 On `node.error`: set node visual to "error" state (red border)
  - [ ] E.3.6 On `workflow.complete`: show completion toast
- [ ] **E.4** Update [`WorkflowNode.svelte`](../frontend/src/components/blueprint/nodes/WorkflowNode.svelte)
  - [ ] E.4.1 Add `executionStatus` prop: `'idle' | 'running' | 'completed' | 'failed' | 'paused'`
  - [ ] E.4.2 Visual states: idle (default), running (pulsing border), completed (green border), failed (red border), paused (yellow border)
- [ ] **E.5** Create [`frontend/src/components/blueprint/ExecutionPanel.svelte`](../frontend/src/components/blueprint/ExecutionPanel.svelte)
  - [ ] E.5.1 Shows: current node, round counter, consensus score, elapsed time
  - [ ] E.5.2 Buttons: Pause/Resume, Cancel
  - [ ] E.5.3 Interjection input: text field + submit button
  - [ ] E.5.4 Node output log: scrollable list of completed node outputs

### Group F: i18n & API Client

- [ ] **F.1** Update [`en.js`](../frontend/src/lib/i18n/loaders/en.js) and [`de.js`](../frontend/src/lib/i18n/loaders/de.js)
  - [ ] F.1.1 Add execution keys: start, pause, resume, cancel, running, completed, failed, paused
  - [ ] F.1.2 Add node event keys: start, complete, error
  - [ ] F.1.3 Add interjection keys: title, placeholder, submit
  - [ ] F.1.4 Add panel keys: title, currentNode, round, consensus
  - [ ] F.1.5 Add toast keys: started, completed, failed, paused, resumed
- [ ] **F.2** Update [`frontend/src/lib/blueprint/api.js`](../frontend/src/lib/blueprint/api.js)
  - [ ] F.2.1 Add `startWorkflowExecution()`, `getWorkflowExecutionState()`, `pauseWorkflowExecution()`, `resumeWorkflowExecution()`, `cancelWorkflowExecution()`, `submitWorkflowInterjection()`

### Group G: Tests

- [ ] **G.1** Create [`tests/backend/test_workflow_compiler.py`](../tests/backend/test_workflow_compiler.py)
  - [ ] G.1.1 Test `WorkflowCompiler.compile()` with valid workflow → produces compiled graph
  - [ ] G.1.2 Test compilation with missing blueprint → error
  - [ ] G.1.3 Test compilation with invalid edge source → error
  - [ ] G.1.4 Test compilation with feedback edge → conditional back-edge
  - [ ] G.1.5 Test compilation with interjection edge → inserts interjection node
  - [ ] G.1.6 Test compilation with gate node → conditional routing
  - [ ] G.1.7 Test topological sort with complex graph
  - [ ] G.1.8 Test compilation with cycle detection (non-feedback)
- [ ] **G.2** Create [`tests/backend/test_workflow_nodes.py`](../tests/backend/test_workflow_nodes.py)
  - [ ] G.2.1 Test `input_node()` sets context correctly
  - [ ] G.2.2 Test `initialize_wf_node()` resets state
  - [ ] G.2.3 Test `agent_node_factory()` with mock LLM → produces output
  - [ ] G.2.4 Test `gate_node_factory()` with true/false conditions
  - [ ] G.2.5 Test `interjection_node()` with empty queue → pauses
  - [ ] G.2.6 Test `interjection_node()` with queued items → consumes and continues
  - [ ] G.2.7 Test `moderator_node_factory()` consensus evaluation
- [ ] **G.3** Create [`tests/backend/test_workflow_exec_api.py`](../tests/backend/test_workflow_exec_api.py)
  - [ ] G.3.1 Test `POST /{workflow_id}/start` → returns session_id
  - [ ] G.3.2 Test `GET /{session_id}/state` → returns current state
  - [ ] G.3.3 Test `POST /{session_id}/pause` → pauses execution
  - [ ] G.3.4 Test `POST /{session_id}/resume` → resumes execution
  - [ ] G.3.5 Test `POST /{session_id}/cancel` → cancels execution
  - [ ] G.3.6 Test `POST /{session_id}/interject` → queues interjection
  - [ ] G.3.7 Test `GET /{session_id}/stream` → SSE events
  - [ ] G.3.8 Test start with invalid workflow → 400 error
  - [ ] G.3.9 Test state query for non-existent session → 404
- [ ] **G.4** Create [`tests/backend/test_state_snapshot.py`](../tests/backend/test_state_snapshot.py)
  - [ ] G.4.1 Test `save()` and `get_latest()` roundtrip
  - [ ] G.4.2 Test `get_history()` returns ordered snapshots
  - [ ] G.4.3 Test `get_by_node()` returns correct snapshot
  - [ ] G.4.4 Test multiple sessions are isolated
- [ ] **G.5** Create [`tests/backend/test_interjection_service.py`](../tests/backend/test_interjection_service.py)
  - [ ] G.5.1 Test `submit()` and `consume()` roundtrip
  - [ ] G.5.2 Test `get_pending()` returns queued items
  - [ ] G.5.3 Test `clear()` removes all items
  - [ ] G.5.4 Test concurrent access (multiple sessions)
- [ ] **G.6** Run full test suite — verify no regressions

---

## Phase 7: Audit, Traceability & Reporting

### Group A: Schema Extension & Migration

- [ ] **A.1** Add migration v5 to [`backend/blueprints/migrations.py`](../backend/blueprints/migrations.py)
  - [ ] A.1.1 Create `audit_log` table with indexes (session_id, workflow_id, event_type, timestamp)
  - [ ] A.1.2 Add `is_locked INTEGER DEFAULT 0` and `is_archived INTEGER DEFAULT 0` to `workflow_sessions`
  - [ ] A.1.3 Add `is_locked INTEGER DEFAULT 0` to `workflow_state_snapshots`
  - [ ] A.1.4 Bump `SCHEMA_VERSION` to 5
- [ ] **A.2** Create Pydantic models in [`backend/models/schemas.py`](../backend/models/schemas.py)
  - [ ] A.2.1 `AuditLogEntry` model with all fields from the table
  - [ ] A.2.2 `AuditLogQuery` model for filtering (session_id, workflow_id, event_type, date range)
  - [ ] A.2.3 `ReportJobStatus` model (job_id, status, format, file_path, created_at, completed_at, error)

### Group B: AuditLogger Backend Service

- [ ] **B.1** Create [`backend/workflow/audit_logger.py`](../backend/workflow/audit_logger.py)
  - [ ] B.1.1 `AuditLogger` class with `__init__(db_path)`, `_init_db()`, `_connect()`
  - [ ] B.1.2 `log_node_execution()` — computes SHA-256 hashes, inserts into `audit_log`
  - [ ] B.1.3 `log_interjection()` — logs interjection events
  - [ ] B.1.4 `log_workflow_event()` — logs lifecycle events (started, completed, failed, paused, resumed)
  - [ ] B.1.5 `get_audit_log(session_id, filters) → list[dict]` — query with sorting/filtering
  - [ ] B.1.6 `get_audit_log_for_replay(session_id) → list[dict]` — ordered by timestamp
  - [ ] B.1.7 `_compute_hash(data) → str` — SHA-256 hash helper
- [ ] **B.2** Integrate `AuditLogger` into [`backend/workflow/node_functions.py`](../backend/workflow/node_functions.py)
  - [ ] B.2.1 Wrap each node function with audit logging (before: record start time, compute input hash; after: compute output hash, record latency, write audit entry)
  - [ ] B.2.2 Use decorator pattern: `@audit_decorator(audit_logger, node_id, actor)`
- [ ] **B.3** Integrate `AuditLogger` into interjection endpoint
  - [ ] B.3.1 In `workflow_exec.py`, add audit logging to `POST /{session_id}/interject`
- [ ] **B.4** Integrate `AuditLogger` into workflow lifecycle
  - [ ] B.4.1 In `workflow_runner.py`: log `workflow.started` at beginning
  - [ ] B.4.2 Log `workflow.completed` or `workflow.failed` at end
  - [ ] B.4.3 Log `workflow.paused` and `workflow.resumed` on state changes

### Group C: Immutability & Soft Delete

- [ ] **C.1** Implement auto-locking in [`backend/workflow/workflow_runner.py`](../backend/workflow/workflow_runner.py)
  - [ ] C.1.1 On session status → `completed` or `failed`: set `is_locked = 1` on session, snapshots, audit log
  - [ ] C.1.2 Locked records cannot be modified or deleted
- [ ] **C.2** Implement soft delete for sessions
  - [ ] C.2.1 Modify `DELETE /api/v1/sessions/{id}` to set `is_archived = 1` instead of physical DELETE
  - [ ] C.2.2 Add `is_archived` filter to `GET /api/v1/sessions` (exclude archived by default, `?include_archived=true`)
  - [ ] C.2.3 Add `POST /api/v1/sessions/{id}/restore` to un-archive
  - [ ] C.2.4 Apply same pattern to workflow sessions
- [ ] **C.3** Add immutability guards
  - [ ] C.3.1 Create [`backend/workflow/immutability.py`](../backend/workflow/immutability.py) with `guard_locked()` and `guard_not_archived()`
  - [ ] C.3.2 Apply guards to all mutation endpoints (interject, pause, resume, cancel)

### Group D: Report Generation Extension

- [ ] **D.1** Create [`backend/workflow/report_generator.py`](../backend/workflow/report_generator.py)
  - [ ] D.1.1 `WorkflowReportGenerator` class with `generate(session_id, fmt) → Path`
  - [ ] D.1.2 Load session data, audit log, state snapshots
  - [ ] D.1.3 Template: workflow name/version, timestamp, participants, message history, consensus, audit trail
  - [ ] D.1.4 DOCX generation via `python-docx`
  - [ ] D.1.5 PDF generation via `WeasyPrint`
  - [ ] D.1.6 ODF generation via `odfpy`
- [ ] **D.2** Create [`backend/workflow/report_jobs.py`](../backend/workflow/report_jobs.py)
  - [ ] D.2.1 `ReportJobStore` class with `create_job()`, `update_job()`, `get_job()`
  - [ ] D.2.2 `report_jobs` table (add to migration v5)
- [ ] **D.3** Create [`backend/api/routers/workflow_reports.py`](../backend/api/routers/workflow_reports.py)
  - [ ] D.3.1 `POST /api/v1/sessions/{id}/report` — creates async report job
  - [ ] D.3.2 `GET /api/v1/reports/{job_id}/status` — returns job status
  - [ ] D.3.3 `GET /api/v1/reports/{job_id}/download` — downloads generated report
  - [ ] D.3.4 SSE endpoint: `GET /api/v1/sessions/{id}/report/stream` — streams progress
- [ ] **D.4** Register new router in [`backend/main.py`](../backend/main.py)
  - [ ] D.4.1 `app.include_router(workflow_reports.router, prefix="/api/v1", tags=["reports"])`

### Group E: Replay View (Frontend)

- [ ] **E.1** Create [`frontend/src/lib/workflow/auditApi.js`](../frontend/src/lib/workflow/auditApi.js)
  - [ ] E.1.1 `getAuditLog(sessionId, filters?)`, `getWorkflowSessions(workflowId?, options?)`, `getSessionForReplay(sessionId)`
- [ ] **E.2** Create [`frontend/src/views/ReplayView.svelte`](../frontend/src/views/ReplayView.svelte)
  - [ ] E.2.1 Session selector dropdown
  - [ ] E.2.2 Load workflow graph of selected session's workflow version
  - [ ] E.2.3 Render graph in read-only mode
  - [ ] E.2.4 Time slider with interjection markers (rose color)
  - [ ] E.2.5 On slider change: highlight active node, show node detail panel, dim/brighten nodes
  - [ ] E.2.6 Playback controls: Play/Pause, Step Forward, Step Back, Speed selector
- [ ] **E.3** Create [`frontend/src/components/workflow/ReplayControls.svelte`](../frontend/src/components/workflow/ReplayControls.svelte)
  - [ ] E.3.1 Time slider with interjection markers
  - [ ] E.3.2 Play/Pause, Step Forward/Back buttons
  - [ ] E.3.3 Speed selector (0.5x, 1x, 2x, 4x)
  - [ ] E.3.4 Current timestamp display, event counter
- [ ] **E.4** Create [`frontend/src/components/workflow/ReplayNodeDetail.svelte`](../frontend/src/components/workflow/ReplayNodeDetail.svelte)
  - [ ] E.4.1 Node ID, type, actor, input/output hash, input/output preview, latency, token usage, LLM profile, timestamp
- [ ] **E.5** Add route for Replay view in [`frontend/src/App.svelte`](../frontend/src/App.svelte)
  - [ ] E.5.1 Add `{:else if $route === 'replay'}` route
  - [ ] E.5.2 Support `#/replay` and `#/replay/{sessionId}`

### Group F: Diff Mode (Frontend)

- [ ] **F.1** Create [`frontend/src/views/DiffView.svelte`](../frontend/src/views/DiffView.svelte)
  - [ ] F.1.1 Two session selectors (Session A, Session B) filtered to same workflow
  - [ ] F.1.2 Load both audit logs, align by node_id
  - [ ] F.1.3 Side-by-side canvas showing workflow graph
  - [ ] F.1.4 Per-node diff panel with text diff highlighting
  - [ ] F.1.5 Color coding: green (matching), yellow (minor diff), red (significant diff)
- [ ] **F.2** Create [`frontend/src/components/workflow/DiffNodeDetail.svelte`](../frontend/src/components/workflow/DiffNodeDetail.svelte)
  - [ ] F.2.1 Split panel: Session A output (left), Session B output (right)
  - [ ] F.2.2 Text diff highlighting
  - [ ] F.2.3 Metadata comparison table (latency, tokens, LLM profile)
- [ ] **F.3** Add route for Diff view in [`frontend/src/App.svelte`](../frontend/src/App.svelte)
  - [ ] F.3.1 Add `{:else if $route === 'diff'}` route
  - [ ] F.3.2 Support `#/diff` and `#/diff/{sessionA}/{sessionB}`

### Group G: Audit Tab (Frontend)

- [ ] **G.1** Enhance [`frontend/src/components/AuditTrail.svelte`](../frontend/src/components/AuditTrail.svelte)
  - [ ] G.1.1 Replace placeholder with full audit log table (columns: Timestamp, Event Type, Node ID, Actor, Latency, Tokens, Hashes)
  - [ ] G.1.2 Sorting: click column headers ascending/descending
  - [ ] G.1.3 Filtering: dropdown for event_type, text search for actor/node_id
  - [ ] G.1.4 Pagination: configurable page size (25, 50, 100)
  - [ ] G.1.5 Row click: expand to show full details
- [ ] **G.2** Create [`frontend/src/components/workflow/SessionAuditTab.svelte`](../frontend/src/components/workflow/SessionAuditTab.svelte)
  - [ ] G.2.1 Tab component wrapping `AuditTrail` for a specific session
  - [ ] G.2.2 Summary stats: total events, total tokens, total latency, event type distribution
  - [ ] G.2.3 Export button: download audit log as CSV
- [ ] **G.3** Integrate Audit Tab into session detail views
  - [ ] G.3.1 Add "Audit" tab alongside existing tabs in DebateView or session detail component

### Group H: i18n

- [ ] **H.1** Update [`en.js`](../frontend/src/lib/i18n/loaders/en.js) and [`de.js`](../frontend/src/lib/i18n/loaders/de.js)
  - [ ] H.1.1 Replay keys: title, selectSession, play, pause, stepForward, stepBack, speed, nodeDetail, interjectionMarker
  - [ ] H.1.2 Diff keys: title, selectSessionA, selectSessionB, noDifferences, differencesFound, nodeDetail
  - [ ] H.1.3 Audit keys: tab title, columns, filter, export, summary
  - [ ] H.1.4 Report keys: title, generate, format, status, download
  - [ ] H.1.5 Session keys: softDelete, restore, archived

### Group I: API Client Updates

- [ ] **I.1** Update [`frontend/src/lib/api.js`](../frontend/src/lib/api.js)
  - [ ] I.1.1 `getAuditLog(sessionId, filters?)`, `generateReport(sessionId, format)`, `getReportStatus(jobId)`, `downloadReport(jobId)`
  - [ ] I.1.2 `softDeleteSession(sessionId)`, `restoreSession(sessionId)`
  - [ ] I.1.3 `getSessionsForReplay(workflowId?)`, `getSessionsForDiff(workflowId)`

### Group J: Tests

- [ ] **J.1** Create [`tests/backend/test_audit_logger.py`](../tests/backend/test_audit_logger.py)
  - [ ] J.1.1 Test `log_node_execution()` inserts correct record with hashes
  - [ ] J.1.2 Test `log_interjection()` inserts correct record
  - [ ] J.1.3 Test `log_workflow_event()` inserts correct record
  - [ ] J.1.4 Test `get_audit_log()` with filters
  - [ ] J.1.5 Test `get_audit_log_for_replay()` returns ordered entries
  - [ ] J.1.6 Test `_compute_hash()` produces consistent SHA-256 hashes
  - [ ] J.1.7 Test concurrent writes (thread safety)
- [ ] **J.2** Create [`tests/backend/test_immutability.py`](../tests/backend/test_immutability.py)
  - [ ] J.2.1 Test auto-lock on session completion
  - [ ] J.2.2 Test auto-lock on session failure
  - [ ] J.2.3 Test soft delete: `is_archived = 1`
  - [ ] J.2.4 Test restore: `is_archived = 0`
  - [ ] J.2.5 Test `guard_locked` raises 403 on mutation of locked session
  - [ ] J.2.6 Test `guard_not_archived` raises 404 on archived session
  - [ ] J.2.7 Test `include_archived` query parameter
- [ ] **J.3** Create [`tests/backend/test_report_jobs.py`](../tests/backend/test_report_jobs.py)
  - [ ] J.3.1 Test `create_job()` returns job_id
  - [ ] J.3.2 Test `update_job()` updates status correctly
  - [ ] J.3.3 Test `get_job()` returns job details
  - [ ] J.3.4 Test `POST /report` creates job and returns job_id
  - [ ] J.3.5 Test `GET /report/{job_id}/status` returns correct status
  - [ ] J.3.6 Test `GET /report/{job_id}/download` returns file
  - [ ] J.3.7 Test DOCX generation with audit trail
  - [ ] J.3.8 Test PDF generation with audit trail
  - [ ] J.3.9 Test ODF generation with audit trail
- [ ] **J.4** Create [`tests/backend/test_migration_v5.py`](../tests/backend/test_migration_v5.py)
  - [ ] J.4.1 Test migration v5 applies cleanly
  - [ ] J.4.2 Test `audit_log` table created with correct schema
  - [ ] J.4.3 Test `is_locked` and `is_archived` columns added to `workflow_sessions`
  - [ ] J.4.4 Test `is_locked` column added to `workflow_state_snapshots`
  - [ ] J.4.5 Test `report_jobs` table created
  - [ ] J.4.6 Test migration is idempotent
- [ ] **J.5** Run full test suite — verify no regressions

---

## Phase 8: A2A Integration & External Agents

### Group A: Model Extension

- [ ] **A.1** Extend [`LLMProfile`](../backend/core/profiles.py) with A2A fields
  - [ ] A.1.1 Add `protocol: Literal["litellm", "a2a"] = "litellm"`
  - [ ] A.1.2 Add `a2a_endpoint: str | None = None`
  - [ ] A.1.3 Add `a2a_timeout: int = 120`
  - [ ] A.1.4 Add `fallback_llm_profile_id: str | None = None`
- [ ] **A.2** Extend [`BlueprintLLMProfile`](../backend/blueprints/models.py) with matching fields
  - [ ] A.2.1 Add `protocol`, `a2a_endpoint`, `a2a_timeout`, `fallback_llm_profile_id` fields
  - [ ] A.2.2 Add `a2a_config: dict = Field(default_factory=dict)` for discovered capabilities
  - [ ] A.2.3 Update `from_legacy()` and `to_legacy()` methods
- [ ] **A.3** Add SQLite migration v6 to [`backend/blueprints/migrations.py`](../backend/blueprints/migrations.py)
  - [ ] A.3.1 Add columns to `blueprint_llm_profiles`: `protocol`, `a2a_endpoint`, `a2a_timeout`, `fallback_llm_profile_id`, `a2a_config_json`
  - [ ] A.3.2 Bump `SCHEMA_VERSION` to 6
- [ ] **A.4** Update [`backend/blueprints/repository.py`](../backend/blueprints/repository.py) serialization
  - [ ] A.4.1 Serialize/deserialize new A2A fields in `save_blueprint_llm_profile()` and `_row_to_blueprint_llm_profile()`
- [ ] **A.5** Add `A2A_ALLOW_PRIVATE_IPS` setting to [`backend/core/config.py`](../backend/core/config.py)
  - [ ] A.5.1 `a2a_allow_private_ips: bool = False` from `DANWA_A2A_ALLOW_PRIVATE_IPS` env var

### Group B: A2AAdapter Service

- [ ] **B.1** Create [`backend/a2a/adapter.py`](../backend/a2a/adapter.py)
  - [ ] B.1.1 `A2AAdapter` class with `__init__(a2a_endpoint, timeout, allow_private_ips)`
  - [ ] B.1.2 `async invoke(messages, config) → GenerationResult` — validate URL, build payload, send task, poll, extract response
  - [ ] B.1.3 `async discover(endpoint) → dict` — validate URL, call A2AClient.discover(), return capabilities
  - [ ] B.1.4 `_validate_url(url) → bool` — check scheme, parse hostname, check private IP
  - [ ] B.1.5 `_build_task_payload(messages, config) → str` — convert messages to structured prompt
  - [ ] B.1.6 `_extract_response(result) → str` — extract text from A2A task result artifacts
- [ ] **B.2** Create [`backend/a2a/exceptions.py`](../backend/a2a/exceptions.py)
  - [ ] B.2.1 `A2AError(Exception)` base class
  - [ ] B.2.2 `A2ATimeoutError`, `A2AConnectionError`, `A2AProtocolError`, `A2AValidationError`, `A2AAgentError`
  - [ ] B.2.3 Each exception carries structured data: endpoint, task_id, error_code, message
- [ ] **B.3** Create [`backend/a2a/url_validator.py`](../backend/a2a/url_validator.py)
  - [ ] B.3.1 `validate_a2a_url(url, allow_private_ips) → str` — scheme check, hostname parsing, private IP check
  - [ ] B.3.2 Support IPv4 and IPv6
  - [ ] B.3.3 Block file://, ftp://, javascript: schemes

### Group C: LLMService Integration

- [ ] **C.1** Modify [`LLMService.generate()`](../backend/services/llm_service.py) to route by protocol
  - [ ] C.1.1 Check `self._profile.protocol`: if `"a2a"` → delegate to `A2AAdapter.invoke()`, if `"litellm"` → existing routing
  - [ ] C.1.2 Import `A2AAdapter` lazily to avoid circular imports
- [ ] **C.2** Add fallback logic to `LLMService`
  - [ ] C.2.1 New method `generate_with_fallback()`: try primary, on A2AError check fallback_llm_profile_id, retry with fallback
  - [ ] C.2.2 Update `agent_node_factory()` in `node_functions.py` to use `generate_with_fallback()` when protocol is `a2a`
- [ ] **C.3** Refactor [`backend/a2a/node.py`](../backend/a2a/node.py) `run_a2a_agent_node()`
  - [ ] C.3.1 Use `A2AAdapter` instead of directly using `A2AClient`
  - [ ] C.3.2 Add fallback support
  - [ ] C.3.3 Add structured error handling with `A2AError` hierarchy
  - [ ] C.3.4 Publish `node.error` SSE event on failure
  - [ ] C.3.5 Log errors to audit trail (Phase 7 integration)

### Group D: A2A Discovery API

- [ ] **D.1** Create [`backend/api/routers/a2a_discovery.py`](../backend/api/routers/a2a_discovery.py)
  - [ ] D.1.1 `POST /api/v1/a2a/discover` — validate URL, call A2AAdapter.discover(), return capabilities
  - [ ] D.1.2 Error responses: 400 (invalid URL), 403 (private IP blocked), 502 (unreachable), 504 (timeout)
- [ ] **D.2** Create capability storage endpoint
  - [ ] D.2.1 `POST /api/v1/a2a/capabilities/{profile_id}` — store discovered capabilities in BlueprintLLMProfile.a2a_config
- [ ] **D.3** Register new router in [`backend/main.py`](../backend/main.py)
  - [ ] D.3.1 `app.include_router(a2a_discovery.router, prefix="/api/v1/a2a", tags=["a2a-discovery"])`

### Group E: Frontend — Inspector & Discovery

- [ ] **E.1** Update [`LLMProfileForm.svelte`](../frontend/src/components/blueprint/forms/LLMProfileForm.svelte)
  - [ ] E.1.1 Add `protocol` selector dropdown (litellm, a2a)
  - [ ] E.1.2 When `protocol === 'a2a'`: show a2a_endpoint URL input, a2a_timeout, fallback_llm_profile_id dropdown, Discover button
  - [ ] E.1.3 Discover button: call `POST /api/v1/a2a/discover`, display capabilities, loading state
  - [ ] E.1.4 Show discovered capabilities as read-only list
- [ ] **E.2** Update [`LLMProfileNode.svelte`](../frontend/src/components/blueprint/nodes/LLMProfileNode.svelte)
  - [ ] E.2.1 Show "A2A" badge when `data?.protocol === 'a2a'`
  - [ ] E.2.2 Show "Remote" badge with different color/styling
  - [ ] E.2.3 Show discovered agent name if available
  - [ ] E.2.4 Tooltip with agent description on hover
- [ ] **E.3** Create [`frontend/src/components/blueprint/A2ACapabilities.svelte`](../frontend/src/components/blueprint/A2ACapabilities.svelte)
  - [ ] E.3.1 Read-only display: agent name, description, skills list, input/output modes, version
  - [ ] E.3.2 Styled as collapsible section in Inspector
- [ ] **E.4** Create [`frontend/src/lib/a2aApi.js`](../frontend/src/lib/a2aApi.js)
  - [ ] E.4.1 `discoverA2A(endpointUrl)`, `saveA2ACapabilities(profileId, capabilities)`

### Group F: Frontend — Workflow Canvas Integration

- [ ] **F.1** Update workflow node components to show A2A badge
  - [ ] F.1.1 When linked AgentBlueprint has A2A LLMProfile, show "Remote" badge (cyan #06b6d4, 🛰️)
  - [ ] F.1.2 Tooltip: "External A2A Agent: {agent_name}"
- [ ] **F.2** Update [`WorkflowNode.svelte`](../frontend/src/components/blueprint/nodes/WorkflowNode.svelte)
  - [ ] F.2.1 For agent-type workflow nodes: check if linked AgentBlueprint → LLMProfile has `protocol === 'a2a'`
  - [ ] F.2.2 If yes, show "A2A" badge, dashed border for remote nodes
- [ ] **F.3** Update execution status display for A2A nodes
  - [ ] F.3.1 In `ExecutionPanel.svelte`: show "Calling external agent..." for A2A nodes
  - [ ] F.3.2 Show A2A-specific error messages (timeout, connection failed)
  - [ ] F.3.3 Show fallback indicator when fallback LLM is used

### Group G: Payload Translation

- [ ] **G.1** Create [`backend/a2a/payload_translator.py`](../backend/a2a/payload_translator.py)
  - [ ] G.1.1 `translate_to_a2a(messages, context, role, round_num) → str` — convert local format to A2A task message
  - [ ] G.1.2 `translate_from_a2a(result) → dict` — convert A2A result to GenerationResult format, estimate tokens if not provided
- [ ] **G.2** Integrate translator into `A2AAdapter.invoke()`
  - [ ] G.2.1 Use `translate_to_a2a()` for building task payload
  - [ ] G.2.2 Use `translate_from_a2a()` for extracting response

### Group H: i18n

- [ ] **H.1** Update [`en.js`](../frontend/src/lib/i18n/loaders/en.js) and [`de.js`](../frontend/src/lib/i18n/loaders/de.js)
  - [ ] H.1.1 Protocol keys: label, litellm, a2a
  - [ ] H.1.2 Endpoint keys: label, placeholder
  - [ ] H.1.3 Timeout, fallback keys
  - [ ] H.1.4 Discover keys: button, loading, success, error
  - [ ] H.1.5 Capabilities keys: title, skills, inputModes, outputModes, version
  - [ ] H.1.6 Badge keys: remote, tooltip
  - [ ] H.1.7 Error keys: timeout, connectionFailed, invalidUrl, privateIpBlocked, protocolError
  - [ ] H.1.8 Fallback keys: activated, profile

### Group I: Tests

- [ ] **I.1** Create [`tests/backend/test_a2a_adapter.py`](../tests/backend/test_a2a_adapter.py)
  - [ ] I.1.1 Test `invoke()` with mock A2A agent → returns GenerationResult
  - [ ] I.1.2 Test `discover()` with mock agent card → returns capabilities
  - [ ] I.1.3 Test `_validate_url()` with valid URLs → passes
  - [ ] I.1.4 Test `_validate_url()` with private IPs and `allow_private_ips=False` → raises A2AValidationError
  - [ ] I.1.5 Test `_validate_url()` with invalid schemes → raises A2AValidationError
  - [ ] I.1.6 Test `_build_task_payload()` converts messages correctly
  - [ ] I.1.7 Test `_extract_response()` handles various A2A result formats
- [ ] **I.2** Create [`tests/backend/test_a2a_url_validator.py`](../tests/backend/test_a2a_url_validator.py)
  - [ ] I.2.1 Test valid HTTP/HTTPS URLs → pass
  - [ ] I.2.2 Test private IPv4 ranges (10.x, 172.16.x, 192.168.x, 127.x) → blocked by default
  - [ ] I.2.3 Test private IPv6 (::1, fc00::) → blocked by default
  - [ ] I.2.4 Test private IPs with `allow_private_ips=True` → pass
  - [ ] I.2.5 Test invalid schemes (file://, ftp://, javascript:) → blocked
  - [ ] I.2.6 Test malformed URLs → blocked
  - [ ] I.2.7 Test public IPs and domains → pass
- [ ] **I.3** Create [`tests/backend/test_a2a_exceptions.py`](../tests/backend/test_a2a_exceptions.py)
  - [ ] I.3.1 Test each exception type carries correct structured data
  - [ ] I.3.2 Test exception hierarchy (all inherit from A2AError)
- [ ] **I.4** Create [`tests/backend/test_a2a_discovery_api.py`](../tests/backend/test_a2a_discovery_api.py)
  - [ ] I.4.1 Test `POST /api/v1/a2a/discover` with valid endpoint → returns capabilities
  - [ ] I.4.2 Test with invalid URL → 400
  - [ ] I.4.3 Test with private IP → 403
  - [ ] I.4.4 Test with unreachable endpoint → 502
  - [ ] I.4.5 Test with timeout → 504
  - [ ] I.4.6 Test `POST /api/v1/a2a/capabilities/{profile_id}` → stores capabilities
- [ ] **I.5** Create [`tests/backend/test_a2a_fallback.py`](../tests/backend/test_a2a_fallback.py)
  - [ ] I.5.1 Test `generate_with_fallback()` with A2A failure + valid fallback → uses fallback
  - [ ] I.5.2 Test with A2A failure + no fallback → raises error
  - [ ] I.5.3 Test with A2A success → no fallback used
  - [ ] I.5.4 Test fallback also fails → raises original A2A error
- [ ] **I.6** Create [`tests/backend/test_a2a_payload_translator.py`](../tests/backend/test_a2a_payload_translator.py)
  - [ ] I.6.1 Test `translate_to_a2a()` produces correct message format
  - [ ] I.6.2 Test `translate_from_a2a()` extracts content from various result formats
  - [ ] I.6.3 Test roundtrip: local → A2A → local preserves content
- [ ] **I.7** Create [`tests/backend/test_migration_v6.py`](../tests/backend/test_migration_v6.py)
  - [ ] I.7.1 Test migration v6 applies cleanly
  - [ ] I.7.2 Test new columns added to `blueprint_llm_profiles`
  - [ ] I.7.3 Test default values are correct
  - [ ] I.7.4 Test migration is idempotent
- [ ] **I.8** Run full test suite — verify no regressions

---

## Summary Statistics

| Phase | Groups | Tasks | Subtasks |
|-------|--------|-------|----------|
| Phase 1 | 8 (A-H) | 24 | 52 |
| Phase 2 | 7 (A-G) | 22 | 56 |
| Phase 7 | 10 (A-J) | 31 | 68 |
| Phase 8 | 9 (A-I) | 28 | 62 |
| **Total** | **34** | **105** | **238** |
