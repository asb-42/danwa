# Agent-to-Agent Protocol — a2a

# A2A (Agent-to-Agent) Protocol Module

The `a2a` module implements the [Agent-to-Agent Protocol](https://github.com/google/A2A) for the Danwa debate engine. It provides **both** an A2A client (Danwa can invoke external A2A agents as debate participants) and an A2A server (external A2A agents can ask Danwa to run debates). The module is designed as a **pluggable transport layer** that integrates seamlessly with the existing LangGraph workflow and LLM service abstractions.

## Architecture Overview

The module is split into two independent layers that share the same protocol primitives (schemas, exceptions, URL validation):

```mermaid
flowchart LR
    subgraph ClientSide["A2A Client (outbound)"]
        Adapter[A2AAdapter]
        Client[A2AClient]
        Node[run_a2a_agent_node]
    end

    subgraph ServerSide["A2A Server (inbound)"]
        Router[FastAPI Router]
        Server[A2AServer]
        TaskManager[TaskManager]
        AgentCard[Agent Card endpoint]
    end

    subgraph Common["Shared Primitives"]
        Exceptions[A2AError hierarchy]
        Schemas[Pydantic models]
        URLValidator[url_validator]
        Config[a2a configuration]
    end

    ClientSide --> LLMService[LLMService .generate()]
    ServerSide --> DebateWorkflow[debate_workflow]

    Adapter -.-> Client
    Node -.-> Adapter
    Router -.-> Server
    Server -.-> TaskManager
```

## Client-Side Components (Outbound)

When Danwa needs to call an external A2A agent as a debate participant, the flow goes through three layers:

### 1. A2AAdapter (`backend/a2a/adapter.py`)

The primary entry point for outbound A2A calls. It presents the same interface as `LLMService.generate()` so that the LangGraph workflow can treat A2A agents transparently.

```python
adapter = A2AAdapter("http://agent:8080", timeout=120, allow_private_ips=False)
result: GenerationResult = await adapter.invoke(messages=[...], config={...})
```

The `invoke` method:
1. Validates the endpoint URL via `validate_a2a_url`.
2. Builds a structured prompt from messages and config (context, role, round number, previous outputs) using `_build_task_payload`.
3. Calls `A2AClient.send_task()` with appropriate metadata.
4. Handles timeouts, connection errors, and protocol errors by mapping them to the A2A exception hierarchy.
5. Extracts the response text and estimates token counts via `_extract_response`.

The adapter also provides a `discover()` method that fetches the external agent’s Agent Card and returns a normalized dictionary.

### 2. A2AClient (`backend/a2a/client.py`)

Raw HTTP client using `httpx` that implements the A2A JSON-RPC protocol. It supports two patterns:

- **Synchronous task completion** (`send_task`): sends a `tasks/send` request and returns the result directly if the agent responds synchronously.
- **Async polling** (`send_task` + `get_task`): if the response status is `submitted` or `working`, it falls back to polling via `_poll_for_result`.

High-level integration is available via `invoke_agent()`, which builds a debate-structured prompt from context, role, round number, and previous outputs, then returns the agent’s text response.

### 3. LangGraph Node (`backend/a2a/node.py`)

`run_a2a_agent_node` is a LangGraph node that integrates with the debate workflow state machine. It:

- Reads A2A configuration from the state (per-debate config) or global config.
- Determines the agent URL from config or the first external agent entry.
- Creates an `A2AAdapter` and calls `invoke()` with messages built from the current state (context, previous agent outputs).
- **Publishes SSE events** (`agent_preparing`, `agent_output`, `node.error`) for real-time UI updates.
- **Audit logging**: failures are logged via `get_audit_logger().log_node_failed()`.
- **Fallback support**: if the A2A call fails and a `fallback_llm_profile_id` is configured, it falls back to a local LLM profile. If the fallback also fails, both errors are published.

```python
async def run_a2a_agent_node(state: dict) -> dict:
    # ... reads config, creates adapter, handles errors with fallback
```

## Server-Side Components (Inbound)

External A2A agents can send debate requests to Danwa. The server flow is handled by:

### 1. FastAPI Router (`backend/a2a/router.py`)

Exposes two endpoints:

- `GET /.well-known/agent.json` — the Agent Card, decorated with dynamic project and language lists.
- `POST /a2a` — the JSON-RPC endpoint that dispatches to `tasks/send`, `tasks/get`, or `tasks/cancel` based on the `method` field.

The router uses lazy-initialized singletons for the `TaskManager` and `A2AServer`.

### 2. A2AServer (`backend/a2a/server.py`)

Processes incoming JSON-RPC requests:

- **`handle_task_send`**: extracts the topic from the message, creates a task in the `TaskManager` with status `submitted`, then launches a background coroutine (`_run_debate`) that creates and runs a full Danwa debate. Returns immediately with the task ID.
- **`handle_task_get`**: returns the current status and (if completed) the artifacts.
- **`handle_task_cancel`**: marks the task as `canceled`.

Background debate execution (`_run_debate`):
1. Resolves the best LLM profile via `_resolve_a2a_llm_profile` (prefers the active service profile, then local providers like Ollama, then any eligible provider).
2. Creates a `DebateRequest` and a debate entry in the project's debate store.
3. Launches `run_debate_workflow` as an async task.
4. Polls the debate store (`_wait_for_completion`) until the debate finishes or times out.
5. Formats the result using `_format_debate_result`.

### 3. TaskManager (`backend/a2a/task_manager.py`)

SQLite-backed persistent store for A2A tasks, following the same pattern as `backend.persistence.audit.AuditService`. It is thread-safe via a `threading.Lock` and supports:

- `create_task` / `update_task` / `get_task` / `list_tasks`
- `cleanup_old_tasks` (removes tasks older than `max_age_hours`)

Tasks go through states: `submitted → working → completed/failed/canceled`.

### 4. Agent Card (`backend/a2a/agent_card.py`)

Provides the static `AGENT_CARD` dictionary that describes Danwa’s capabilities. The router dynamically adds available projects and languages at runtime.

## Shared Primitives

### Exceptions (`backend/a2a/exceptions.py`)

A structured hierarchy with context about the endpoint, task ID, and error code:

```
A2AError (base)
  ├── A2ATimeoutError
  ├── A2AConnectionError
  ├── A2AProtocolError
  ├── A2AValidationError
  └── A2AAgentError
```

### Schemas (`backend/a2a/schemas.py`)

Pydantic models for the A2A protocol: `A2ATextPart`, `A2AMessage`, `A2ATask`, `A2ATaskStatus`, `A2AResponse`.

### URL Validator (`backend/a2a/url_validator.py`)

Ensures only `http`/`https` schemes are allowed and blocks private IP ranges by default (configurable via `allow_private_ips`).

### Configuration (`backend/a2a/config.py`)

Loads `config/a2a.json` from the project root. Example structure:

```json
{
    "enabled": true,
    "server": {
        "enabled": true,
        "path": "/a2a"
    },
    "external_agents": [
        {
            "url": "http://agent:8080",
            "role": "critic",
            "timeout": 120
        }
    ]
}
```

Helper functions `get_external_agents()` and `get_agent_for_role()` are used by the node and router.

### Payload Translator (`backend/a2a/payload_translator.py`)

Bidirectional conversion between local message format and A2A task strings. Used primarily within the adapter but separated for testing and reuse.

## Usage Examples

### Outbound: Invoke an external agent in a debate workflow

```python
from backend.a2a.node import run_a2a_agent_node

# In a LangGraph node function:
state = {
    "context": "Should remote work be mandatory?",
    "current_agent_index": 0,
    "current_round": 1,
    "agent_outputs": [],
    "a2a_config": {
        "enabled": True,
        "agent_url": "http://external-agent:5000",
        "role": "strategist",
        "timeout": 120,
        "fallback_llm_profile_id": "local-qwen"
    }
}
new_state = await run_a2a_agent_node(state)
```

### Inbound: External client starts a debate via JSON-RPC

```bash
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": 1,
    "params": {
      "id": "task-123",
      "message": {
        "role": "user",
        "parts": [
          {"type": "text", "text": "Should companies adopt a 4-day work week?"}
        ]
      },
      "metadata": {
        "project_id": "_default",
        "language": "en"
      }
    }
  }'
```

Poll for the result:

```bash
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/get",
    "id": 2,
    "params": {"id": "task-123"}
  }'
```

## Integration Points

| Component | Connects to | Purpose |
|-----------|-------------|---------|
| `run_a2a_agent_node` | `backend.api.events.publish_async` | Publish SSE events for UI |
| `run_a2a_agent_node` | `backend.workflow.audit_logger` | Log node failures |
| `run_a2a_agent_node` | `backend.services.llm_service.LLMService` | Fallback on A2A failure |
| `A2AServer` | `backend.api.deps.get_debate_store_for_project` | Persist and poll debates |
| `A2AServer` | `backend.api.deps.get_audit_service` | Audit trail |
| `A2AServer` | `backend.services.debate_workflow.run_debate_workflow` | Start debate execution |
| `A2AServer` | `backend.core.config.is_service_llm_eligible` | Choose LLM profile |
| `Router` | `backend.api.deps.get_project_store` | Enrich Agent Card |
| `Config` | `backend.core.config` | `a2a_allow_private_ips` setting |
| `A2AAdapter` | `backend.services.llm_service` | Replacement for `LLMService.generate()` |