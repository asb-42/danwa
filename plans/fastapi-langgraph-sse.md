# FastAPI + LangGraph + SSE + Svelte Migration Plan

## Revised Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Svelte SPA (compiled to vanilla JS)                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
│  │  │  Debate   │ │  Config  │ │   DMS    │ │ Sessions │ │  │
│  │  │  Stream   │ │  Forms   │ │  Views   │ │  List    │ │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │  │
│  │       │             │            │             │        │  │
│  │       └─────────────┴─────┬──────┴─────────────┘        │  │
│  │                           │                             │  │
│  │              SSE / HTTP   │                             │  │
│  └───────────────────────────┼─────────────────────────────┘  │
└──────────────────────────────┼───────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────┐
│  FastAPI Backend             │                               │
│  ┌───────────────────────────┴────────────────────────────┐  │
│  │  API Routers                                            │  │
│  │  ├── /api/debate/*   (SSE stream, start, result)       │  │
│  │  ├── /api/config/*   (CRUD LLM/agent/prompt)           │  │
│  │  ├── /api/dms/*      (projects, documents, RAG)        │  │
│  │  └── /api/sessions/* (list, delete, export)             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  LangGraph State Machine                                │  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐           │  │
│  │  │Strategist│──▶│  Critic  │──▶│Optimizer │──▶ ...    │  │
│  │  └──────────┘   └──────────┘   └──────────┘           │  │
│  │       │              │              │                   │  │
│  │       └──────────────┴──────────────┘                   │  │
│  │                      │                                  │  │
│  │              ┌───────▼───────┐                          │  │
│  │              │  Consensus   │                          │  │
│  │              │  Check       │                          │  │
│  │              └───────┬───────┘                          │  │
│  │                      │                                  │  │
│  │              ┌───────▼───────┐                          │  │
│  │              │  Complete /  │                          │  │
│  │              │  Next Round  │                          │  │
│  │              └──────────────┘                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Services Layer (new)                                   │  │
│  │  ├── LLMService        (wraps LLMRouter, injectable)   │  │
│  │  ├── PromptService     (Jinja2 template rendering)     │  │
│  │  ├── AuditService      (immutable SQLite audit trail)  │  │
│  │  └── Settings          (pydantic-settings + .env)      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Existing Backend (reused as-is)                        │  │
│  │  ├── ConfigManager   (src/core/config_manager.py)      │  │
│  │  ├── DMS             (src/dms/dms.py)                  │  │
│  │  ├── SessionDB       (src/core/session_db.py)          │  │
│  │  ├── ReportGenerator (src/tools/report_generator)      │  │
│  │  ├── TraceLogger     (src/core/trace_logger.py)        │  │
│  │  ├── PrivacyGuard    (src/core/privacy.py)             │  │
│  │  ├── DebateMemory    (src/core/memory.py)              │  │
│  │  └── WebSearchTool   (src/tools/web_search.py)         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | FastAPI | Async, auto OpenAPI docs |
| State machine | LangGraph | Graph-based workflow, checkpointing, streaming |
| Real-time | SSE | Simpler than WS, unidirectional, native EventSource |
| Frontend | Svelte 5 | Compiles to vanilla JS, no VDOM, minimal overhead |
| CSS | Tailwind CSS | Utility-first, no custom CSS needed |
| Config | pydantic-settings | Env vars + .env file, type-safe |
| Audit | SQLite (append-only) | Immutable audit trail, no deletes |
| Prompts | Jinja2 templates | External files, dynamic rendering |
| Logging | structlog or logging | JSON output, structured |

## File Structure

```
src/
├── server/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, mounts routers + static
│   ├── sse.py               # SSE broadcaster utility
│   └── routers/
│       ├── __init__.py
│       ├── debate.py        # POST /start, GET /stream/{id} (SSE), GET /{id}
│       ├── config.py        # CRUD for LLM/agent/prompt/settings
│       ├── dms.py           # Projects, documents, RAG
│       └── sessions.py      # Session history, traces, reports
├── debate/
│   ├── __init__.py
│   ├── state.py             # DebateState TypedDict
│   ├── graph.py             # LangGraph StateGraph definition
│   └── nodes.py             # Graph node functions (pure, injectable)
├── services/
│   ├── __init__.py
│   ├── llm_service.py       # LLMService wrapping LLMRouter (injectable)
│   ├── prompt_service.py    # Jinja2 prompt template rendering
│   ├── audit_service.py     # Immutable SQLite audit trail
│   └── settings.py          # pydantic-settings Settings class
├── core/                    # EXISTING — unchanged during migration
│   ├── llm_router.py        # Wrapped by LLMService
│   ├── config_manager.py
│   ├── session_db.py
│   ├── prompt_manager.py    # Kept for backward compat
│   ├── trace_logger.py
│   ├── privacy.py
│   ├── memory.py
│   └── debate_engine.py     # Kept for backward compat during migration
├── dms/                     # EXISTING — unchanged
│   └── dms.py
└── tools/                   # EXISTING — unchanged
    ├── report_generator.py
    ├── web_search.py
    └── doc_parser.py

static/                      # Svelte compiled output (gitignored)
├── index.html
└── assets/

frontend/                    # Svelte source (new)
├── src/
│   ├── App.svelte
│   ├── main.ts
│   ├── components/
│   │   ├── DebateStream.svelte
│   │   ├── ConfigForm.svelte
│   │   ├── DMSView.svelte
│   │   └── SessionList.svelte
│   └── stores.ts
├── index.html
├── package.json
├── svelte.config.js
├── vite.config.ts
└── tailwind.config.js

prompts/                     # Jinja2 prompt templates (new)
├── strategist.j2
├── critic.j2
├── optimizer.j2
├── moderator.j2
└── assistant.j2

tests/
├── test_debate_flow.py       # Integration test with real LLM calls
├── test_audit_trail.py       # Audit trail tests
└── test_api.py               # API endpoint tests
```

## Phase 1: Skeleton

### 1.1 Settings (`src/services/settings.py`)

```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # LLM
    llm_provider: str = "local"          # "local", "openrouter", "openai"
    llm_model: str = "qwen2.5-7b"
    llm_api_key: str = ""
    llm_base_url: str = "http://localhost:1234/v1"
    
    # Debate
    max_debate_rounds: int = 3
    consensus_threshold: float = 0.75
    
    # Storage
    db_path: str = "./data/debate.db"
    chroma_path: str = "./data/chroma"
    audit_db_path: str = "./data/audit.db"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 7861
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 1.2 LLMService (`src/services/llm_service.py`)

```python
"""Injectable LLM service — wraps LLMRouter for testability."""

from dataclasses import dataclass
from typing import Optional
from src.core.llm_router import LLMRouter

@dataclass
class LLMResponse:
    text: str
    tokens_used: int
    model: str
    finish_reason: str

class LLMService:
    """Pure async LLM service. No global state. Injectable."""
    
    def __init__(self, router: LLMRouter):
        self.router = router
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5,
        role: Optional[str] = None,
    ) -> LLMResponse:
        resp = await self.router.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temp_override=temperature,
            role=role,
        )
        return LLMResponse(
            text=resp["content"],
            tokens_used=resp["tokens_used"],
            model=resp["model"],
            finish_reason=resp["finish_reason"],
        )
```

### 1.3 PromptService (`src/services/prompt_service.py`)

```python
"""Jinja2 prompt template rendering."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROMPT_DIR = Path("prompts")

class PromptService:
    def __init__(self, prompt_dir: Path = PROMPT_DIR):
        self.env = Environment(loader=FileSystemLoader(str(prompt_dir)))
    
    def render(self, template_name: str, **kwargs) -> str:
        template = self.env.get_template(f"{template_name}.j2")
        return template.render(**kwargs)
```

### 1.4 AuditService (`src/services/audit_service.py`)

```python
"""Immutable SQLite audit trail — append-only, no updates, no deletes."""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

class AuditService:
    """Append-only audit log. Each event is immutable."""
    
    def __init__(self, db_path: str = "./data/audit.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                debate_id TEXT NOT NULL,
                round INTEGER NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                output_hash TEXT NOT NULL,
                llm_model TEXT,
                tokens_used INTEGER,
                latency_ms INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()
    
    def record(
        self,
        debate_id: str,
        round_num: int,
        agent: str,
        action: str,
        input_hash: str,
        output_hash: str,
        llm_model: str = "",
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> str:
        event_id = str(uuid.uuid4())
        self.conn.execute("""
            INSERT INTO audit_events 
            (id, debate_id, round, agent, action, input_hash, output_hash, 
             llm_model, tokens_used, latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, debate_id, round_num, agent, action,
            input_hash, output_hash, llm_model, tokens_used, latency_ms,
            datetime.utcnow().isoformat()
        ))
        self.conn.commit()
        return event_id
    
    def get_debate_events(self, debate_id: str) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT * FROM audit_events WHERE debate_id = ? ORDER BY round, created_at",
            (debate_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
```

### 1.5 DebateState (`src/debate/state.py`)

```python
"""LangGraph state definition."""

from typing import TypedDict, Annotated, List, Optional, Any
import operator

class AgentConfig(TypedDict):
    role: str
    llm_profile: str
    temperature: float

class AgentOutput(TypedDict):
    role: str
    content: str
    tokens_used: int

class RoundData(TypedDict):
    round: int
    consensus: float
    agent_outputs: List[AgentOutput]

class DebateState(TypedDict):
    # Input
    context: str
    agent_profile: List[AgentConfig]
    max_rounds: int
    threshold: float
    enable_fact_check: bool
    enable_memory: bool
    rag_context: str
    
    # Runtime
    session_id: str
    current_round: int
    current_agent_index: int
    
    # Accumulators (operator.add for list concatenation)
    rounds: Annotated[List[RoundData], operator.add]
    agent_outputs: Annotated[List[AgentOutput], operator.add]
    current_draft: str
    
    # Output
    final_consensus: float
    output: str
    validation_report: List[dict]
    used_variant: str
```

### 1.6 LangGraph Graph (`src/debate/graph.py`)

```python
"""LangGraph state machine for debate workflow."""

from langgraph.graph import StateGraph, END
from src.debate.state import DebateState

def build_graph() -> StateGraph:
    """Build the debate workflow graph."""
    graph = StateGraph(DebateState)
    
    # Nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("check_consensus", check_consensus_node)
    graph.add_node("complete", complete_node)
    
    # Edges
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "run_agent")
    graph.add_conditional_edges(
        "run_agent",
        should_continue_agents,
        {
            "next_agent": "run_agent",
            "check_consensus": "check_consensus",
        }
    )
    graph.add_conditional_edges(
        "check_consensus",
        should_continue_rounds,
        {
            "next_round": "run_agent",
            "complete": "complete",
        }
    )
    graph.add_edge("complete", END)
    
    return graph.compile()

def should_continue_agents(state: DebateState) -> str:
    """Check if more agents need to run in this round."""
    if state["current_agent_index"] < len(state["agent_profile"]) - 1:
        return "next_agent"
    return "check_consensus"

def should_continue_rounds(state: DebateState) -> str:
    """Check if consensus reached or max rounds exceeded."""
    if state["final_consensus"] >= state["threshold"]:
        return "complete"
    if state["current_round"] >= state["max_rounds"]:
        return "complete"
    return "next_round"

# Node implementations in nodes.py
from src.debate.nodes import initialize_node, run_agent_node, check_consensus_node, complete_node
```

### 1.7 LangGraph Nodes (`src/debate/nodes.py`)

```python
"""Pure node functions for LangGraph. All dependencies injected via config."""

import hashlib
import time
from typing import Any
from langchain_core.runnables import RunnableConfig
from src.debate.state import DebateState
from src.services.llm_service import LLMService
from src.services.prompt_service import PromptService
from src.services.audit_service import AuditService

async def initialize_node(state: DebateState, config: RunnableConfig) -> DebateState:
    """Initialize the debate: load prompts, validate, emit status."""
    broadcaster = config["configurable"].get("sse_broadcaster")
    if broadcaster:
        await broadcaster.emit("status", {"message": "Initializing debate..."})
    
    return {
        "current_round": 1,
        "current_agent_index": 0,
        "agent_outputs": [],
        "rounds": [],
        "final_consensus": 0.0,
    }

async def run_agent_node(state: DebateState, config: RunnableConfig) -> DebateState:
    """Run a single agent. Pure function — LLMService injected via config."""
    llm_service: LLMService = config["configurable"]["llm_service"]
    prompt_service: PromptService = config["configurable"]["prompt_service"]
    audit: AuditService = config["configurable"]["audit_service"]
    broadcaster = config["configurable"].get("sse_broadcaster")
    
    agent_config = state["agent_profile"][state["current_agent_index"]]
    role = agent_config["role"]
    temperature = agent_config["temperature"]
    
    if broadcaster:
        await broadcaster.emit("agent_start", {"role": role})
    
    # Build prompt
    system_prompt = prompt_service.render(role, context=state["context"])
    
    # Build user message from previous outputs
    prev_outputs = state["agent_outputs"]
    if prev_outputs:
        prev_text = "\n\n".join(f"### {o['role']}\n{o['content']}" for o in prev_outputs)
        user_prompt = f"Previous agents:\n{prev_text}\n\nYour turn as {role}:"
    else:
        user_prompt = f"Context:\n{state['context']}"
    
    # Call LLM
    start = time.time()
    response = await llm_service.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        role=role,
    )
    latency_ms = int((time.time() - start) * 1000)
    
    # Audit
    input_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:16]
    output_hash = hashlib.sha256(response.text.encode()).hexdigest()[:16]
    audit.record(
        debate_id=state["session_id"],
        round_num=state["current_round"],
        agent=role,
        action="generated",
        input_hash=input_hash,
        output_hash=output_hash,
        llm_model=response.model,
        tokens_used=response.tokens_used,
        latency_ms=latency_ms,
    )
    
    if broadcaster:
        await broadcaster.emit("agent_message", {
            "role": role,
            "content": response.text,
        })
    
    return {
        "agent_outputs": [{"role": role, "content": response.text, "tokens_used": response.tokens_used}],
        "current_agent_index": state["current_agent_index"] + 1,
        "current_draft": response.text,
    }

async def check_consensus_node(state: DebateState, config: RunnableConfig) -> DebateState:
    """Check consensus after all agents in a round have run."""
    broadcaster = config["configurable"].get("sse_broadcaster")
    
    # Simple heuristic: use last agent's output or a moderator call
    # For now, use a simple calculation
    round_num = state["current_round"]
    consensus = min(0.5 + round_num * 0.15, 1.0)
    
    if broadcaster:
        await broadcaster.emit("consensus", {"round": round_num, "value": consensus})
    
    return {
        "rounds": [{
            "round": round_num,
            "consensus": consensus,
            "agent_outputs": state["agent_outputs"][-len(state["agent_profile"]):],
        }],
        "final_consensus": consensus,
        "current_round": round_num + 1,
        "current_agent_index": 0,
    }

async def complete_node(state: DebateState, config: RunnableConfig) -> DebateState:
    """Finalize the debate."""
    broadcaster = config["configurable"].get("sse_broadcaster")
    
    if broadcaster:
        await broadcaster.emit("complete", {
            "session_id": state["session_id"],
            "consensus": state["final_consensus"],
            "output": state["current_draft"],
            "rounds": len(state["rounds"]),
        })
    
    return {
        "output": state["current_draft"],
    }
```

### 1.8 SSE Broadcaster (`src/server/sse.py`)

```python
"""SSE broadcaster utility."""

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Manages SSE connections for debate streaming."""
    
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
    
    async def emit(self, event: str, data: dict):
        if self._closed:
            return
        payload = json.dumps(data)
        await self._queue.put(f"event: {event}\ndata: {payload}\n\n")
    
    async def close(self):
        self._closed = True
        await self._queue.put(None)
    
    async def stream(self):
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                yield item
        except asyncio.CancelledError:
            pass
```

### 1.9 Debate Router with SSE (`src/server/routers/debate.py`)

```python
"""Debate API router — SSE streaming."""

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.config_manager import ConfigManager
from src.core.llm_router import LLMRouter
from src.debate.graph import build_graph
from src.server.sse import SSEBroadcaster
from src.services.llm_service import LLMService
from src.services.prompt_service import PromptService
from src.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()


class DebateStartRequest(BaseModel):
    context: str
    profile: Optional[str] = None
    agent_profile: Optional[str] = None
    max_rounds: int = 3
    threshold: float = 0.75
    enable_fact_check: bool = True
    enable_memory: bool = False
    variant_override: Optional[str] = None
    project_id: Optional[str] = None
    rag_context: Optional[str] = None


@router.post("/start")
async def start_debate(body: DebateStartRequest):
    """Start a debate. Returns session_id. Connect to /stream/{id} for SSE."""
    cm = ConfigManager()
    if body.agent_profile:
        profile = cm.get_agent_profile(body.agent_profile)
        if profile is None:
            raise HTTPException(400, f"Agent profile '{body.agent_profile}' not found")
    else:
        body.agent_profile = cm.get_default_agent_profile_name()
    
    session_id = str(uuid.uuid4())[:8]
    return {"session_id": session_id, "agent_profile": body.agent_profile}


@router.get("/stream/{session_id}")
async def stream_debate(session_id: str, request: Request):
    """SSE stream for debate progress. Client sends params via query or initial POST."""
    # For simplicity, store pending debate params in a dict
    # In production, use Redis or similar
    params = _pending_debates.pop(session_id, None)
    if not params:
        raise HTTPException(404, f"No pending debate for session {session_id}")
    
    broadcaster = SSEBroadcaster()
    
    async def run_debate():
        try:
            # Build services
            llm_router = LLMRouter(params.get("profile"))
            llm_service = LLMService(llm_router)
            prompt_service = PromptService()
            audit_service = AuditService()
            
            # Load agent profile
            cm = ConfigManager()
            agent_profile_data = cm.get_agent_profile(params["agent_profile"])
            agents = agent_profile_data.get("agents", [])
            
            # Build initial state
            initial_state = {
                "context": params["context"],
                "agent_profile": agents,
                "max_rounds": params.get("max_rounds", 3),
                "threshold": params.get("threshold", 0.75),
                "enable_fact_check": params.get("enable_fact_check", True),
                "enable_memory": params.get("enable_memory", False),
                "rag_context": params.get("rag_context", ""),
                "session_id": session_id,
            }
            
            graph = build_graph()
            config = {
                "configurable": {
                    "llm_service": llm_service,
                    "prompt_service": prompt_service,
                    "audit_service": audit_service,
                    "sse_broadcaster": broadcaster,
                }
            }
            
            await graph.ainvoke(initial_state, config=config)
        except Exception as e:
            logger.error("Debate error: %s", e, exc_info=True)
            await broadcaster.emit("error", {"message": str(e)})
        finally:
            await broadcaster.close()
    
    asyncio.create_task(run_debate())
    
    return StreamingResponse(
        broadcaster.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# Simple in-memory store for pending debate params
_pending_debates: dict = {}
```

### 1.10 Integration Test (`tests/test_debate_flow.py`)

```python
"""Integration test — real LLM calls, minimal rounds."""

import pytest
from src.debate.graph import build_graph
from src.services.llm_service import LLMService
from src.services.prompt_service import PromptService
from src.services.audit_service import AuditService
from src.core.llm_router import LLMRouter
from src.server.sse import SSEBroadcaster


@pytest.mark.asyncio
async def test_minimal_debate():
    """Test a 1-round debate with a single agent (chatbot profile)."""
    # Setup
    llm_router = LLMRouter("local_qwen")
    llm_service = LLMService(llm_router)
    prompt_service = PromptService()
    audit_service = AuditService(db_path=":memory:")
    broadcaster = SSEBroadcaster()
    
    # Single-agent profile (chatbot)
    agents = [{"role": "assistant", "llm_profile": "local_qwen", "temperature": 0.4}]
    
    initial_state = {
        "context": "What is 2+2?",
        "agent_profile": agents,
        "max_rounds": 1,
        "threshold": 0.75,
        "enable_fact_check": False,
        "enable_memory": False,
        "rag_context": "",
        "session_id": "test-001",
    }
    
    graph = build_graph()
    config = {
        "configurable": {
            "llm_service": llm_service,
            "prompt_service": prompt_service,
            "audit_service": audit_service,
            "sse_broadcaster": broadcaster,
        }
    }
    
    # Run
    result = await graph.ainvoke(initial_state, config=config)
    
    # Assert
    assert result["output"] is not None
    assert len(result["output"]) > 0
    assert result["final_consensus"] > 0
    assert len(result["rounds"]) == 1
    
    # Check audit trail
    events = audit_service.get_debate_events("test-001")
    assert len(events) >= 1  # At least 1 agent = 1 audit event
    assert events[0]["agent"] == "assistant"
    assert events[0]["round"] == 1
```

## Migration Strategy: Strangler Pattern

### Phase 1: Skeleton (Backend only, no UI changes)
**Goal**: FastAPI runs alongside Chainlit. Health check works. Empty LangGraph compiles.

1. Add `langgraph`, `langchain-core`, `jinja2`, `pydantic-settings` to `pyproject.toml`
2. Create `src/services/settings.py` — pydantic-settings
3. Create `src/services/llm_service.py` — injectable LLMService
4. Create `src/services/prompt_service.py` — Jinja2 templates
5. Create `src/services/audit_service.py` — immutable SQLite audit
6. Create `src/debate/state.py` — DebateState TypedDict
7. Create `src/debate/graph.py` — LangGraph StateGraph
8. Create `src/debate/nodes.py` — pure node functions
9. Create `src/server/sse.py` — SSE broadcaster
10. Update `src/server/routers/debate.py` — SSE instead of WebSocket
11. Test: `uv run uvicorn src.server.main:app --port 7861` → health check OK
12. **Chainlit still runs the main app on port 7860**

### Phase 2: Feature Migration (Full debate flow)
**Goal**: Debate runs through LangGraph + SSE. Chainlit still available.

1. Migrate prompt `.md` files to Jinja2 `.j2` templates
2. Implement full consensus logic (moderator LLM call)
3. Add web search validation node
4. Add RAG context integration
5. Run integration test: `pytest tests/test_debate_flow.py`
6. **Chainlit still runs the main app on port 7860**

### Phase 3: Minimal Frontend (Vanilla HTML + EventSource)
**Goal**: Ugly but functional HTML page that streams debate via SSE.

1. Create `static/index.html` — vanilla HTML with `<textarea>` and `<pre>` output
2. Use `EventSource` API to connect to SSE endpoint
3. Test: Open http://localhost:7861/ → type context → see debate stream
4. **Chainlit still runs the main app on port 7860**

### Phase 4: Svelte Frontend
**Goal**: Proper UI with Svelte components.

1. Initialize Svelte project in `frontend/` with Vite
2. Install Tailwind CSS
3. Create `DebateStream.svelte` — debate view with SSE
4. Create `ConfigForm.svelte` — LLM/agent profile forms
5. Create `DMSView.svelte` — project/document management
6. Create `SessionList.svelte` — session history
7. Build Svelte → output to `static/`
8. Test: Full UI works on port 7861

### Phase 5: Cutover
**Goal**: FastAPI UI is primary. Chainlit removed.

1. Update `scripts/start.sh` to run FastAPI instead of Chainlit
2. Remove `chainlit` from `pyproject.toml`
3. Delete `src/ui/chainlit_app.py`, `src/ui/dms_dashboard.py`, `src/ui/dashboard.py`
4. Delete `.chainlit/`, `chainlit.md`
5. Update README

## Anti-Patterns to Avoid

| Anti-Pattern | Instead |
|---|---|
| `global` variables for state | Dependency Injection, explicit parameters |
| Sync LLM calls in async code | `async def` + `await` everywhere |
| JSON as string parsing | Pydantic models, `model_validate_json()` |
| Hardcoded file paths | `pathlib.Path`, configurable |
| Print statements | `logging` with structured output |
| Deleting audit records | Append-only, no deletes |
| Monolithic functions | Small, pure, testable functions |

## Checklist

- [ ] `pytest tests/test_debate_flow.py` passes (integration test)
- [ ] `ruff check` passes
- [ ] `uvicorn src.server.main:app --port 7861` → health check OK
- [ ] `curl http://localhost:7861/health` → `{"status": "ok"}`
- [ ] Debate via API produces audit entries in SQLite
- [ ] SSE stream delivers events in correct order
