# Danwa (Debate-Agent) — Technical Documentation

> **Version**: 2.0.0  
> **Last Updated**: 2026-05-06  
> **Authors**: Development Team  

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Backend Architecture](#5-backend-architecture)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Core Features](#7-core-features)
8. [Profile System](#8-profile-system)
9. [Document Management System (DMS)](#9-document-management-system-dms)
10. [Data Models & Schemas](#10-data-models--schemas)
11. [API Reference](#11-api-reference)
12. [Configuration](#12-configuration)
13. [Development Guide](#13-development-guide)
14. [Deployment](#14-deployment)

---

## 1. Introduction

**Danwa** (formerly Debate-Agent) is an auditable multi-agent debate workflow system that uses AI agents to analyze, critique, and optimize arguments through structured deliberation. The system employs four specialized AI agents working in a LangGraph-orchestrated state machine to arrive at well-reasoned conclusions with measurable consensus scores.

### Key Capabilities

- **Multi-Agent Deliberation**: Four specialized AI agents collaborate to produce high-quality analysis
- **LLM Flexibility**: Supports local models (via LM Studio, Ollama) and cloud providers (via LiteLLM)
- **Document Analysis**: Upload and analyze PDF, DOCX, ODT, ODS, and ODP files
- **Web Validation**: Optional fact-checking via SearXNG or DuckDuckGo integration
- **Semantic Memory**: ChromaDB-powered precedent retrieval from past debates
- **Audit Trail**: Complete JSONL trace logs for reproducibility
- **Report Generation**: Export results as DOCX or PDF
- **Privacy Protection**: Built-in PII redaction and data retention policies
- **Project Isolation**: SQLite-backed project system with isolated data storage
- **Document Management System (DMS)**: Project-wise document organization with RAG pipeline
- **PaddleOCR Integration**: OCR for scanned PDFs and images
- **Hybrid Retrieval**: BM25 + Vector search + Re-ranking for optimal document retrieval
- **Real-time Updates**: Server-Sent Events (SSE) for live debate progress
- **Internationalization**: Full i18n support (German/English)

---

## 2. Architecture Overview

Danwa follows a **decoupled frontend-backend architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                              │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Svelte 5 SPA + Tailwind CSS + @xyflow/svelte          │  │
│  │  - Dashboard, Debate, Audit, Config, Projects Views      │  │
│  │  - Workflow Graph Visualization (ELK layout)              │  │
│  │  - SSE Client for Real-time Updates                     │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                           │ HTTP/JSON + SSE                    │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│  Backend (FastAPI)      │                                     │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  API Routers (FastAPI)                               │  │
│  │  - /api/v1/debate  (debate CRUD + SSE stream)      │  │
│  │  - /api/v1/profiles (LLM, agents, prompts)          │  │
│  │  - /api/v1/dms      (document management)            │  │
│  │  - /api/v1/projects (project isolation)              │  │
│  │  - /api/v1/audit    (audit trails)                  │  │
│  │  - /api/v1/config   (application settings)           │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  LangGraph Workflow Engine                           │  │
│  │  - State machine: initialize → run_agent → consensus  │  │
│  │  - Nodes: initialize, run_agent, check_consensus,    │  │
│  │           complete                                   │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  Services Layer                                      │  │
│  │  - LLMService (LiteLLM + local HTTP)                 │  │
│  │  - ProfileService (YAML profile management)           │  │
│  │  - PromptService (Markdown template rendering)        │  │
│  │  - WebSearchTool (SearXNG / DuckDuckGo)            │  │
│  │  - DMS Service (document processing + RAG)          │  │
│  └──────────────────────┬──────────────────────────────────┘  │
│                         │                                     │
│  ┌──────────────────────▼──────────────────────────────────┐  │
│  │  Persistence Layer                                   │  │
│  │  - SQLite (debates, sessions, projects)              │  │
│  │  - ChromaDB (vector embeddings for memory + DMS)    │  │
│  │  - JSONL (audit trace logs)                         │  │
│  │  - JSON files (project configs)                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Profile-Driven Configuration**: All LLM, agent, and prompt configurations are externalized to YAML/Markdown files for hot-reloading
2. **Project Isolation**: Each project has its own SQLite DB, ChromaDB collection, and DMS storage
3. **Event-Driven Updates**: Server-Sent Events (SSE) push real-time debate progress to the frontend
4. **Graceful Degradation**: LLM failures are handled gracefully with anomaly tracking
5. **Audit-First**: Every debate generates a complete, reproducible audit trail

---

## 3. Technology Stack

| Layer | Technology | Purpose |
|-------|-------------|---------|
| **Language** | Python 3.11+ | Backend development |
| **Backend Framework** | FastAPI 0.115+ | REST API + SSE endpoints |
| **Workflow Orchestration** | LangGraph 0.2+ | State machine for debate workflow |
| **LLM Integration** | LiteLLM | Multi-provider LLM routing (OpenRouter, OpenAI, Anthropic, local) |
| **Frontend Framework** | Svelte 5 | Reactive UI with runes |
| **UI Styling** | Tailwind CSS 3.4+ | Utility-first CSS framework |
| **Workflow Visualization** | @xyflow/svelte + ELK.js | Interactive debate graph rendering |
| **Frontend Build** | Vite 5 | Fast dev server and production builds |
| **Vector Database** | ChromaDB 0.5+ | Semantic search for memory + DMS |
| **Relational Database** | SQLite | Debates, sessions, projects, DMS metadata |
| **Document Parsing** | pdfplumber, pypdf, python-docx, odfpy | Multi-format document extraction |
| **OCR Engine** | PaddleOCR 3.5+ (optional) | Scanned PDF and image text extraction |
| **Report Generation** | python-docx, WeasyPrint | DOCX and PDF report exports |
| **Web Search** | SearXNG / DuckDuckGo | Fact-checking integration |
| **Package Manager (Python)** | uv | Fast Python package management |
| **Package Manager (Node)** | npm | Frontend dependency management |
| **Testing (Backend)** | pytest 8+ | Unit and integration tests |
| **Testing (Frontend)** | Playwright 1.59+ | E2E, visual, a11y, i18n tests |
| **Linting** | ruff 0.4+ | Fast Python linting and formatting |
| **Validation** | Pydantic 2.7+ | Type validation for API and configs |
| **SSE Support** | sse-starlette | Server-Sent Events for real-time updates |
| **i18n (Frontend)** | Custom loaders | German/English translation support |
| **State Management** | Svelte stores | Reactive state for UI |
| **HTTP Client** | httpx | Async HTTP for LLM calls and web search |
| **Environment** | python-dotenv | .env file loading |

---

## 4. Project Structure

```
danwa/
├── backend/                     # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── api/
│   │   ├── deps.py            # Dependency injection (get_project_id, stores)
│   │   ├── events.py          # SSE event bus (publish/subscribe)
│   │   └── routers/           # API route handlers
│   │       ├── debate.py      # Debate CRUD + SSE stream
│   │       ├── profiles.py    # LLM, agent, prompt management
│   │       ├── dms.py        # Document Management System
│   │       ├── projects.py   # Project isolation
│   │       ├── audit.py      # Audit trail access
│   │       ├── config.py     # Application settings
│   │       ├── sessions.py   # Session management
│   │       ├── health.py     # Health check endpoint
│   │       └── system.py     # System operations (reload, logs)
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars)
│   │   └── profiles.py      # LLMProfile, AgentPersona, PromptVariant schemas
│   ├── models/
│   │   └── schemas.py       # API request/response Pydantic models
│   ├── workflow/
│   │   ├── debate_graph.py  # LangGraph state machine builder
│   │   ├── nodes.py         # Node functions (initialize, run_agent, etc.)
│   │   └── state.py        # DebateState TypedDict definition
│   ├── services/
│   │   ├── llm_service.py  # LLM calls (LiteLLM + local HTTP)
│   │   ├── profile_service.py # YAML profile CRUD + validation
│   │   ├── prompt_service.py # Markdown template rendering
│   │   ├── web_search.py   # SearXNG / DuckDuckGo integration
│   │   └── dms/           # Document Management System services
│   │       ├── service.py   # DMS facade (orchestrator)
│   │       ├── database.py  # SQLite schema for DMS
│   │       ├── project_manager.py # Project CRUD
│   │       ├── document_processor.py # File parsing + OCR
│   │       ├── chunker.py   # Text chunking (512 tokens)
│   │       ├── vector_store.py # ChromaDB interface
│   │       ├── metadata_index.py # Chunk metadata indexing
│   │       ├── rag_pipeline.py # RAG pipeline
│   │       ├── hybrid_retriever.py # BM25 + Vector + Re-ranking
│   │       ├── rag_context_formatter.py # RAG context formatting
│   │       └── config.py    # DMS configuration
│   ├── persistence/
│   │   ├── project_store.py # JSON file-based project storage
│   │   ├── debate_store.py  # SQLite debate storage
│   │   └── audit.py        # Audit event recording
│   └── migrations/
│       └── migrate_projects.py # Project isolation migration
│
├── frontend/                    # Svelte 5 SPA
│   ├── src/
│   │   ├── main.js           # Entry point
│   │   ├── App.svelte       # Root component with hash routing
│   │   ├── views/           # Page-level components
│   │   │   ├── Dashboard.svelte
│   │   │   ├── DebateView.svelte
│   │   │   ├── AuditView.svelte
│   │   │   ├── ConfigView.svelte
│   │   │   ├── ProjectsView.svelte
│   │   │   ├── DocumentsView.svelte
│   │   │   └── ArchiveView.svelte
│   │   ├── components/       # Reusable UI components
│   │   │   ├── Layout.svelte
│   │   │   ├── Sidebar.svelte
│   │   │   ├── Header.svelte
│   │   │   ├── WorkflowGraph.svelte
│   │   │   ├── DebateTimeline.svelte
│   │   │   ├── AuditTrail.svelte
│   │   │   ├── DocumentUploader.svelte
│   │   │   ├── ConsensusPanel.svelte
│   │   │   ├── MarkdownRenderer.svelte
│   │   │   ├── LanguageSwitcher.svelte
│   │   │   ├── ProjectSelector.svelte
│   │   │   ├── ProjectSettings.svelte
│   │   │   └── workflow/      # Workflow visualization components
│   │   │       ├── WorkflowCanvas.svelte
│   │   │       ├── nodes/     # AgentNode, InputNode, etc.
│   │   │       ├── edges/     # FlowEdge, FeedbackEdge, etc.
│   │   │       └── panels/   # TimelinePanel, NodeDetailPanel
│   │   ├── lib/              # Utilities and state management
│   │   │   ├── api.js        # API client (fetch wrapper)
│   │   │   ├── stores.js     # Svelte writable stores
│   │   │   ├── sse.js        # SSE client for real-time updates
│   │   │   ├── i18n/        # Internationalization
│   │   │   │   ├── index.js
│   │   │   │   ├── config.js
│   │   │   │   └── loaders/
│   │   │   │       ├── en.js
│   │   │   │       └── de.js
│   │   │   └── workflow/     # Workflow state management
│   │   │       ├── store.js  # Graph/runtime/history stores
│   │   │       ├── events.js # Event types and dispatch
│   │   │       ├── mapper.js # SSE → workflow state mapper
│   │   │       ├── graphReducer.js
│   │   │       ├── runtimeReducer.js
│   │   │       ├── snapshot.js
│   │   │       ├── layout.js # ELK layout engine
│   │   │       └── oob.js   # Out-of-band input handling
│   │   └── tests/
│   │       └── e2e/          # Playwright E2E tests
│   │           ├── contracts/
│   │           ├── visual/
│   │           ├── a11y/
│   │           └── i18n/
│   ├── public/                # Static assets
│   ├── package.json          # Node dependencies
│   ├── vite.config.js        # Vite configuration
│   ├── tailwind.config.js    # Tailwind CSS config
│   └── postcss.config.js     # PostCSS config
│
├── src/                         # Legacy core (being migrated)
│   ├── core/
│   │   ├── debate_engine.py   # Legacy orchestration
│   │   ├── llm_router.py     # Legacy LLM routing
│   │   ├── memory.py         # ChromaDB vector storage
│   │   ├── session_db.py     # SQLite persistence
│   │   ├── prompt_manager.py # Prompt variant management
│   │   ├── privacy.py       # PII redaction & retention
│   │   ├── trace_logger.py  # JSONL audit logs
│   │   └── custom_embedding.py # Custom embedding functions
│   ├── tools/
│   │   ├── doc_parser.py    # Document parsing
│   │   ├── report_generator.py # DOCX/PDF generation
│   │   └── web_search.py   # SearXNG search
│   └── dms/                 # Legacy DMS (migrated to backend/services/dms/)
│
├── profiles/                    # Profile configuration (YAML + Markdown)
│   ├── llm/                     # LLM profile definitions
│   │   ├── openrouter-claude.yaml
│   │   ├── openrouter-gpt4.yaml
│   │   ├── openrouter-grok.yaml
│   │   ├── xiaomi-mimo.yaml
│   │   └── local-qwen.yaml
│   ├── agents/                  # Agent persona definitions
│   │   ├── strategist-default.yaml
│   │   ├── critic-default.yaml
│   │   ├── optimizer-default.yaml
│   │   ├── moderator-default.yaml
│   │   ├── critic-stoic.yaml
│   │   └── strategist-german-law.yaml
│   └── prompts/                 # Prompt templates (Markdown)
│       ├── default/             # Default variant
│       │   ├── strategist.md
│       │   ├── strategist-en.md
│       │   ├── critic.md
│       │   ├── critic-en.md
│       │   ├── optimizer.md
│       │   ├── optimizer-en.md
│       │   ├── moderator.md
│       │   └── moderator-en.md
│       └── variants/            # Named prompt variants
│           ├── kantian/          # Kantian ethics variant
│           │   ├── strategist.md
│           │   └── critic.md
│           └── steiner/          # Steiner variant
│               ├── strategist.md
│               └── critic.md
│
├── config/                       # Application settings
│   └── settings.yaml           # App settings (search, privacy, DMS, UI)
│
├── data/                        # Runtime data (created at runtime)
│   ├── audit.db                # SQLite database for audit events
│   └── projects/              # Per-project data
│       ├── _default/           # System default project
│       │   ├── project.json    # Project config
│       │   ├── debates/       # Debate data
│       │   └── dms/          # DMS storage
│       └── {project_id}/
│
├── logs/                         # Debate trace logs (JSONL)
│   └── debate-agent.log         # Application log file
│
├── reports/                      # Generated reports
│
├── tests/                        # Pytest test suite
│   ├── backend/
│   │   ├── test_debate_api.py
│   │   ├── test_dms_api.py
│   │   ├── test_workflow.py
│   │   ├── test_llm_service.py
│   │   ├── test_profiles.py
│   │   ├── test_rag_integration.py
│   │   ├── test_project_isolation.py
│   │   └── conftest.py
│   ├── test_debate_engine.py
│   ├── test_dms_*.py
│   └── ...
│
├── docs/                         # Documentation
│   ├── user_manual.md          # User-facing manual
│   └── technical_documentation.md # This file
│
├── scripts/                      # Utility scripts
│   ├── setup.sh                # Quick setup (uv, venv, deps)
│   ├── start.sh                # Start application
│   ├── stop.sh                # Stop application
│   └── status.sh              # Check application status
│
├── plans/                       # Development plans and sprint docs
├── archive/                     # Archived plans and configs
│
├── pyproject.toml               # Python project metadata & dependencies
├── Makefile                     # Dev workflow (install, test, lint, format)
├── setup.sh                     # Quick setup script
├── .env                         # Environment variables (gitignored)
└── README.md                    # Project overview
```

---

## 5. Backend Architecture

### 5.1 Application Factory (`backend/main.py`)

The FastAPI application uses an **application factory pattern** with lifespan management:

```python
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    
    # CORS middleware
    app.add_middleware(CORSMiddleware, ...)
    
    # API routers
    app.include_router(debate.router, prefix="/api/v1/debate")
    app.include_router(profiles.router, prefix="/api/v1/profiles")
    app.include_router(dms.router, prefix="/api/v1/dms")
    # ... more routers
    
    # Static file serving (production mode)
    if _FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(...))
        app.mount("/", StaticFiles(html=True))
    
    return app
```

#### Key Features:
- **Lifespan Management**: Startup runs project migration (`migrate_to_projects()`)
- **CORS Configuration**: Configurable via `DANWA_CORS_ORIGINS` environment variable
- **Static File Serving**: In production, serves the built Svelte frontend from `frontend/dist/`

---

### 5.2 API Routers

#### 5.2.1 Debate Router (`backend/api/routers/debate.py`)

The core debate API manages debate lifecycle and real-time streaming.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/debate` | List debates (with status/search filters) |
| POST | `/api/v1/debate` | Create a new debate (status: pending) |
| GET | `/api/v1/debate/{id}` | Get debate status and progress |
| POST | `/api/v1/debate/{id}/start` | Start a pending debate (background task) |
| DELETE | `/api/v1/debate/{id}` | Delete a debate and its audit events |
| POST | `/api/v1/debate/{id}/cancel` | Cancel a running debate |
| PUT | `/api/v1/debate/{id}/documents` | Assign documents to a debate |
| POST | `/api/v1/debate/{id}/oob` | Submit out-of-band input |
| GET | `/api/v1/debate/{id}/stream` | SSE endpoint for real-time updates |

**Debate Flow**:
1. **Create**: `POST /api/v1/debate` → returns `debate_id`, status `pending`
2. **Start**: `POST /api/v1/debate/{id}/start` → launches `background_tasks.add_task(_run_debate_workflow)`
3. **Stream**: `GET /api/v1/debate/{id}/stream` → SSE events: `workflow_started`, `agent_preparing`, `agent_started`, `llm_call_started`, `agent_output`, `round_update`, `status_change`
4. **Complete**: Workflow finishes → status changes to `completed` or `failed`

#### 5.2.2 Profiles Router (`backend/api/routers/profiles.py`)

Manages LLM profiles, agent personas, and prompt variants.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/profiles/llm` | List all LLM profiles |
| POST | `/api/v1/profiles/llm` | Create LLM profile |
| PUT | `/api/v1/profiles/llm/{id}` | Update LLM profile |
| DELETE | `/api/v1/profiles/llm/{id}` | Delete LLM profile |
| GET | `/api/v1/profiles/agents` | List agent personas (`?role=` filter) |
| POST | `/api/v1/profiles/agents` | Create agent persona |
| PUT | `/api/v1/profiles/agents/{id}` | Update agent persona |
| DELETE | `/api/v1/profiles/agents/{id}` | Delete agent persona |
| GET | `/api/v1/profiles/prompts` | List prompt variants |
| GET | `/api/v1/profiles/prompts/{id}/preview` | Preview prompt for agent role |
| DELETE | `/api/v1/profiles/prompts/{id}` | Delete prompt variant |
| GET | `/api/v1/profiles/cost-estimate` | Estimate debate cost |

#### 5.2.3 DMS Router (`backend/api/routers/dms.py`)

Document Management System API for project-wise document handling.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dms/documents` | List documents in active project |
| POST | `/api/v1/dms/documents` | Upload document |
| DELETE | `/api/v1/dms/documents/{id}` | Delete document |
| GET | `/api/v1/dms/projects` | List DMS projects |
| POST | `/api/v1/dms/retrieve` | Retrieve relevant chunks (RAG) |
| POST | `/api/v1/dms/documents/{id}/rag` | Add/remove document from RAG |

#### 5.2.4 Other Routers

- **Projects** (`projects.py`): Project CRUD with isolation
- **Audit** (`audit.py`): Audit trail access and export
- **Config** (`config.py`): Application settings management
- **Sessions** (`sessions.py`): Session management (legacy)
- **Health** (`health.py`): Health check endpoint
- **System** (`system.py`): System operations (reload profiles, view logs)

---

### 5.3 LangGraph Workflow (`backend/workflow/`)

#### 5.3.1 State Definition (`state.py`)

The debate state is defined as a TypedDict with accumulators:

```python
class DebateState(TypedDict, total=False):
    # Input
    context: str
    agent_profile: list[AgentConfigState]
    max_rounds: int
    threshold: float
    enable_fact_check: bool
    enable_memory: bool
    rag_context: str
    
    # Profile configuration
    llm_profile_id: str
    prompt_variant: str
    agent_persona_ids: dict[str, str]
    
    # Language
    language: str  # 'de' or 'en'
    
    # Project isolation
    project_id: str
    
    # Runtime
    session_id: str
    current_round: int
    current_agent_index: int
    
    # Accumulators (Annotated[..., operator.add])
    rounds: Annotated[list[RoundDataState], operator.add]
    agent_outputs: Annotated[list[AgentOutputState], operator.add]
    
    # Output
    final_consensus: float
    output: str
    validation_report: list[dict]
    anomalies: Annotated[list[str], operator.add]
```

#### 5.3.2 Graph Builder (`debate_graph.py`)

```python
def build_graph() -> StateGraph:
    graph = StateGraph(DebateState)
    
    # Nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("check_consensus", check_consensus_node)
    graph.add_node("complete", complete_node)
    
    # Edges
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "run_agent")
    
    # Conditional: more agents?
    graph.add_conditional_edges("run_agent", should_continue_agents, {
        "next_agent": "run_agent",
        "check_consensus": "check_consensus",
    })
    
    # Conditional: more rounds?
    graph.add_conditional_edges("check_consensus", should_continue_rounds, {
        "next_round": "run_agent",
        "complete": "complete",
    })
    
    graph.add_edge("complete", END)
    return graph.compile()
```

**Flow Diagram**:
```
initialize → run_agent ⟲ (next_agent / check_consensus)
                    ↓
              check_consensus ⟲ (next_round / complete)
                    ↓
                 complete → END
```

#### 5.3.3 Node Functions (`nodes.py`)

**Key node functions**:

1. **initialize_node**: Sets up initial runtime state (`current_round=1`, `current_agent_index=0`)
2. **run_agent_node**: Executes LLM call for the current agent
   - Resolves system prompt from PromptService (language-aware)
   - Builds user prompt with context, RAG, previous outputs
   - Handles OOB (out-of-band) input injection
   - Performs web search (required/optional mode)
   - Publishes SSE events: `agent_preparing`, `agent_started`, `llm_call_started`, `agent_output`
3. **check_consensus_node**: Evaluates consensus score
   - Linear progression: `consensus = min(threshold, current_round / max_rounds * threshold * 1.2)`
   - Caps at 0.0 if LLM failures occurred
4. **complete_node**: Finalizes the debate, publishes `status_change` event

**Conditional edge functions**:
- `should_continue_agents`: Returns `"next_agent"` or `"check_consensus"`
- `should_continue_rounds`: Returns `"next_round"` or `"complete"`

---

### 5.4 LLM Service (`backend/services/llm_service.py`)

The LLM service supports two routing modes:

#### 5.4.1 Local Providers (OpenAI-compatible endpoints)

Direct HTTP calls to local LLM servers (LM Studio, Ollama, etc.):

```python
async def _generate_local(self, messages, temperature, max_tokens):
    url = f"{self._profile.api_base}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = await httpx.AsyncClient().post(url, json=payload, headers=headers)
    return GenerationResult(content=..., tokens_in=..., tokens_out=...)
```

#### 5.4.2 Cloud Providers (via LiteLLM)

Uses LiteLLM for unified access to OpenRouter, OpenAI, Anthropic, etc.:

```python
async def _generate_litellm(self, messages, temperature, max_tokens):
    model_name = f"{provider}/{model}"  # e.g., "openrouter/anthropic/claude-3.5-sonnet"
    response = await litellm.acompletion(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv(self._profile.api_key_env),
    )
    return GenerationResult(...)
```

#### 5.4.3 GenerationResult

```python
@dataclass
class GenerationResult:
    content: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""
```

---

### 5.5 Profile Service (`backend/services/profile_service.py`)

Manages YAML-based LLM profiles, agent personas, and prompt variants.

**Key methods**:
- `list_llm_profiles()`, `get_llm_profile(id)`, `save_llm_profile(profile)`, `delete_llm_profile(id)`
- `list_agent_personas(role=None)`, `get_agent_persona(id)`, `save_agent_persona(persona)`, `delete_agent_persona(id)`
- `list_prompt_variants()`, `preview_prompt(variant_id, agent_role)`
- `estimate_debate_cost(llm_profile_id, num_agents, num_rounds)`

**Profile storage**: YAML files in `profiles/llm/`, `profiles/agents/`, `profiles/prompts/`

---

### 5.6 Prompt Service (`backend/services/prompt_service.py`)

Renders Markdown prompt templates with variable substitution.

**Template resolution priority**:
1. Project-specific: `{project_dir}/prompts/{variant}/{role}.md`
2. Global: `profiles/prompts/{variant}/{role}.md`
3. Language override: `{role}-en.md` for English debates
4. Persona fallback: `system_prompt` from agent persona YAML
5. Generic default: Hardcoded fallback prompt

**Rendering**: Uses Jinja2 for variable substitution (e.g., `{{ context }}`, `{{ language }}`)

---

### 5.7 Web Search (`backend/services/web_search.py`)

Supports two search backends:

1. **SearXNG** (primary): Self-hosted, privacy-friendly meta-search engine
2. **DuckDuckGo** (fallback): No API key required

**Search modes**:
- `off`: No web search
- `required`: Auto-search before LLM call, inject results into prompt
- `optional`: Agents can request searches using `[SEARCH: query]` markers

**Helper functions**:
- `extract_search_queries(context, role)`: Extract 3 key claims for auto-search
- `extract_search_markers(content)`: Find `[SEARCH: ...]` markers
- `format_search_results(results, language)`: Format results for prompt injection

---

### 5.8 Persistence Layer

#### 5.8.1 Project Store (`backend/persistence/project_store.py`)

JSON file-based storage for project metadata:

```
data/projects/{project_id}/project.json
```

**Features**:
- Thread-safe via `threading.Lock()`
- In-memory cache with `_cache: dict[str, Project]`
- Auto-creates project subdirectories: `debates/`, `dms/`
- System projects (e.g., `_default`) cannot be deleted

#### 5.8.2 Debate Store (`backend/persistence/debate_store.py`)

SQLite-based storage for debate state:

```sql
CREATE TABLE debates (
    debate_id TEXT PRIMARY KEY,
    status TEXT,
    request_json TEXT,
    result_json TEXT,
    current_round INTEGER,
    max_rounds INTEGER,
    created_at TEXT,
    updated_at TEXT
)
```

#### 5.8.3 Audit Service (`backend/persistence/audit.py`)

Records audit events to SQLite:

```sql
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    debate_id TEXT,
    round INTEGER,
    agent TEXT,
    action TEXT,
    input_hash TEXT,
    output_hash TEXT,
    llm_model TEXT,
    tokens_used INTEGER,
    timestamp TEXT
)
```

---

## 6. Frontend Architecture

### 6.1 Svelte 5 Components

The frontend is built with **Svelte 5** using runes (`$state`, `$derived`, `$effect`) for reactivity.

#### 6.1.1 Views (Page-level components)

| View | File | Purpose |
|------|------|---------|
| Dashboard | `Dashboard.svelte` | Session history, quick actions, stats |
| Debate | `DebateView.svelte` | New debate form, live workflow visualization, results |
| Audit | `AuditView.svelte` | Audit trail viewer, timeline, raw JSONL |
| Config | `ConfigView.svelte` | LLM profiles, agent personas, prompt variants |
| Projects | `ProjectsView.svelte` | Project management, isolation settings |
| Documents | `DocumentsView.svelte` | DMS document management |
| Archive | `ArchiveView.svelte` | Past debates read-only view |

#### 6.1.2 Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Layout | `Layout.svelte` | App shell with sidebar and header |
| WorkflowGraph | `WorkflowGraph.svelte` | Interactive debate graph visualization |
| ConsensusPanel | `ConsensusPanel.svelte` | Real-time consensus score display |
| DebateTimeline | `DebateTimeline.svelte` | Round-by-round timeline |
| AuditTrail | `AuditTrail.svelte` | Audit event list with filtering |
| DocumentUploader | `DocumentUploader.svelte` | Drag-and-drop file upload |
| MarkdownRenderer | `MarkdownRenderer.svelte` | Renders Markdown with `marked` |
| LanguageSwitcher | `LanguageSwitcher.svelte` | Toggle DE/EN |
| ProjectSelector | `ProjectSelector.svelte` | Switch active project |
| ProjectSettings | `ProjectSettings.svelte` | Per-project configuration |

---

### 6.2 State Management (`frontend/src/lib/stores.js`)

Uses Svelte writable stores for global state:

```javascript
// Routing
export const route = writable('dashboard');
export const routeParams = writable([]);

// Backend
export const healthStatus = writable({ status: 'unknown', version: '' });
export const currentDebate = writable(null);
export const debates = writable([]);
export const auditEvents = writable([]);

// Connection
export const sseConnected = writable(false);

// UI
export const error = writable(null);
export const loading = writable(false);

// Persistence (localStorage)
export const activeProject = persisted('danwa.activeProject', null);
export const selectedLLMProfile = persisted('danwa.selectedLLMProfile', 'openrouter-claude');
export const selectedPromptVariant = persisted('danwa.selectedPromptVariant', 'default');
export const selectedPersonas = persisted('danwa.selectedPersonas', {
    strategist: 'strategist-default',
    critic: 'critic-default',
    optimizer: 'optimizer-default',
    moderator: 'moderator-default',
});
```

**`persisted()` helper**: Wraps a writable store with `localStorage` serialization.

---

### 6.3 API Client (`frontend/src/lib/api.js`)

Fetch-based API client with:
- Automatic `X-Project-Id` header injection from `activeProject` store
- `Accept-Language: en` header for i18n
- Backend error message translation via `ERROR_MAP`
- Comprehensive endpoint coverage: debates, profiles, DMS, projects, config, system

```javascript
async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const projectId = get(activeProject)?.id;
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            'Accept-Language': 'en',
            ...(projectId ? { 'X-Project-Id': projectId } : {}),
            ...options.headers,
        },
        ...options,
    });
    // Error handling with i18n translation...
    return response.json();
}
```

---

### 6.4 SSE Client (`frontend/src/lib/sse.js`)

Real-time Server-Sent Events client for debate progress:

```javascript
export function createSSE(url, handlers) {
    const eventSource = new EventSource(url);
    eventSource.onmessage = (event) => { /* handle SSE events */ };
    return { close: () => eventSource.close() };
}
```

**Event types handled**:
- `workflow_started`: Initial connection established
- `agent_preparing`: Agent resolving profile/prompts
- `agent_started`: LLM call about to start
- `llm_call_started`: LLM generation in progress
- `agent_output`: Agent response received
- `round_update`: Round completed with consensus score
- `status_change`: Debate completed/failed
- `oob_input`: Out-of-band input submitted
- `oob_consumed`: OOB input consumed by agent
- `web_search`: Search performed with results

---

### 6.5 Workflow Visualization

#### 6.5.1 Workflow State Store (`frontend/src/lib/workflow/store.js`)

Three layers of state:

1. **Graph (Topology)**: `graphNodes`, `graphEdges` — who is connected to whom
2. **Runtime (Active State)**: `runtime` — who is active, current round
3. **History (Snapshots)**: `roundSnapshots`, `eventLog` — timeline & audit

```javascript
export const graphNodes = writable(new Map());   // Map<nodeId, WorkflowNode>
export const graphEdges = writable(new Map());   // Map<edgeId, WorkflowEdge>

export const runtime = writable({
    status: 'idle',             // 'idle' | 'running' | 'waiting_for_user' | 'completed'
    currentRound: 0,
    activeNodeId: null,
    activeEdgeId: null,
    executionPath: [],          // Chronological Node-IDs
});

export const roundSnapshots = writable([]);  // RoundSnapshot[]
export const eventLog = writable([]);        // WorkflowEvent[]
```

#### 6.5.2 Svelte Flow Integration

Uses `@xyflow/svelte` for rendering the debate graph:

```svelte
<!-- WorkflowGraph.svelte -->
<script>
    import { SvelteFlow, Background, Controls, MiniMap } from '@xyflow/svelte';
    import { flowNodes, flowEdges } from '../lib/workflow/store.js';
</script>

<SvelteFlow nodes={$flowNodes} edges={$flowEdges}>
    <Background />
    <Controls />
    <MiniMap />
</SvelteFlow>
```

**Node types**: `InputNode`, `AgentNode`, `DecisionNode`, `HistoryNode`, `ArtifactNode`, `UserActionNode`

**Edge types**: `FlowEdge`, `FeedbackEdge`, `OOBEdge`, `UserEdge`

#### 6.5.3 ELK Layout Engine (`frontend/src/lib/workflow/layout.js`)

Uses `elkjs` for automatic graph layout:

```javascript
export async function layoutGraph(nodes, edges) {
    const elk = new ELK();
    const graph = { children: [...], edges: [...] };
    const layouted = await elk.layout(graph, { layoutOptions });
    return { nodes: layouted.children, edges: layouted.edges };
}
```

---

### 6.6 Internationalization (`frontend/src/lib/i18n/`)

Custom i18n system with language loaders:

```javascript
// i18n/index.js
import { en } from './loaders/en.js';
import { de } from './loaders/de.js';

const translations = { en, de };

export function t(key, params = {}) {
    let text = translations[locale][key] || key;
    // Replace {param} placeholders...
    return text;
}
```

**Language files**:
- `loaders/en.js`: English translations
- `loaders/de.js`: German translations

**Language switching**:
- UI toggle via `LanguageSwitcher.svelte`
- Persisted to `localStorage`
- Sent to backend via `Accept-Language` header

---

## 7. Core Features

### 7.1 Multi-Agent Debate Workflow

Four specialized agents collaborate in a structured debate:

```
Input → [Strategist] → [Critic] → [Optimizer] → [Moderator]
         ↓              ↓             ↓              ↓
      Strategy      Critique      Synthesis      Consensus (0.0-1.0)
```

#### 7.1.1 Agent Roles

| Agent | Role | Output |
|-------|------|--------|
| **Strategist** | Develops logical argumentation structure | Problem core, strategy, assumptions, open points |
| **Critic** | Identifies weaknesses and risks (Devil's Advocate) | Critique points, risk assessment, missing evidence |
| **Optimizer** | Synthesizes strategy and criticism | Refined, court-ready formulation with clear causalities |
| **Moderator** | Evaluates consensus | Single decimal number (0.0-1.0) |

#### 7.1.2 Debate Configuration

- **Max Rounds**: 1-20 (default: 3)
- **Consensus Threshold**: 0.0-1.0 (default: 0.8)
- **Early Stop**: Debate ends when threshold is reached

#### 7.1.3 Consensus Scoring

Linear progression formula:
```python
consensus = min(threshold, current_round / max_rounds * threshold * 1.2)
```

If LLM failures occurred in a round, consensus is capped at 0.0.

---

### 7.2 Document Processing

Supported formats and libraries:

| Format | Extension | Library |
|--------|-----------|---------|
| PDF | `.pdf` | pdfplumber (preferred), pypdf (fallback) |
| Word | `.docx` | python-docx |
| OpenDocument Text | `.odt` | odfpy |
| OpenDocument Spreadsheet | `.ods` | odfpy |
| OpenDocument Presentation | `.odp` | odfpy |
| Images (OCR) | `.png`, `.jpg` | PaddleOCR (optional) |
| Plain Text | `.txt`, `.md` | Native read |

**Context Protection**:
- Maximum context length: **25,000 characters**
- Documents exceeding this limit are truncated with a warning
- Metadata includes: source filename, extension, page count, word count

---

### 7.3 Web Search Integration

#### 7.3.1 Search Modes

| Mode | Behavior |
|------|-----------|
| `off` | No web search |
| `required` | Auto-search 3 key claims before LLM call, inject results into prompt |
| `optional` | Agents can request searches using `[SEARCH: query]` markers in their output |

#### 7.3.2 Search Backends

1. **SearXNG** (primary): `http://localhost:8080`
   - Self-hosted via Docker: `docker run -d -p 8080:8080 searxng/searxng`
2. **DuckDuckGo** (fallback): No API key required

---

### 7.4 Semantic Memory (ChromaDB)

Past debates are stored as vector embeddings for precedent retrieval:

- **Storage Location**: `memory/chroma_db/`
- **Collection**: `debate_precedents`
- **Similarity Metric**: Cosine distance
- **Embedding Model**: Default sentence-transformers (via chromadb)

When enabled (`enable_memory: true`):
1. Searches for similar past debates
2. Injects relevant precedent insights into current context
3. Stores completed debates for future reference

---

### 7.5 Out-of-Band (OOB) Inputs

Users can inject additional context during a running debate:

```javascript
// Submit OOB input
const response = await submitOOBInput(debateId, {
    content: "Consider the new policy update...",
    target: {
        type: "specific_agent",  // or "next_agent", "all_future", "current_active"
        agent_role: "critic",
        round: 2,
    },
    urgency: "high",
});
```

**Target types**:
- `specific_agent`: Routed to a specific agent role
- `next_agent`: Routed to the agent after `current_agent_role`
- `all_future`: Routed to all agents from a given round
- `current_active`: Routed to the currently executing agent

---

## 8. Profile System

### 8.1 LLM Profiles (`profiles/llm/*.yaml`)

Configuration for LLM endpoints:

```yaml
# profiles/llm/openrouter-claude.yaml
id: openrouter-claude-3.6-sonnet
name: Claude 3.6 Sonnet (OpenRouter)
provider: openrouter          # openrouter | openai | anthropic | local | ollama
model: anthropic/claude-3.6-sonnet
api_base: https://openrouter.ai/api/v1
api_key_env: OPENROUTER_API_KEY
max_tokens: 4096
context_window: 200000
temperature: 0.7
timeout: 600
cost_per_1k_input: 0.003
cost_per_1k_output: 0.015
```

**Supported providers** (enum `LLMProvider`):
- `openrouter`, `openai`, `anthropic`
- `local`, `ollama`, `opencode-zen`, `opencode-go`, `xiaomi`

---

### 8.2 Agent Personas (`profiles/agents/*.yaml`)

Defines agent behavior and linked LLM profile:

```yaml
# profiles/agents/strategist-default.yaml
id: strategist-default
name: Default Strategist
role: strategist              # strategist | critic | optimizer | moderator
system_prompt: |
    You are the Strategist agent in a multi-agent debate system.
    Your task is to analyze the input and develop a logical argumentation structure.
llm_profile_id: openrouter-claude-3.6-sonnet
max_rounds: 5
consensus_threshold: 0.9
tags: [default, balanced]
```

---

### 8.3 Prompt Variants (`profiles/prompts/`)

Markdown templates organized by variant, with optional language overrides:

```
profiles/prompts/
├── default/              # Default variant
│   ├── strategist.md     # German
│   ├── strategist-en.md  # English override
│   ├── critic.md
│   ├── critic-en.md
│   ├── optimizer.md
│   ├── optimizer-en.md
│   ├── moderator.md
│   └── moderator-en.md
└── variants/
    ├── kantian/          # Kantian ethics variant
    │   ├── strategist.md
    │   └── critic.md
    └── steiner/          # Steiner variant
        ├── strategist.md
        └── critic.md
```

**Template variables**: `{{ context }}`, `{{ language }}`, `{{ round }}`, etc. (rendered via Jinja2)

---

## 9. Document Management System (DMS)

### 9.1 Overview

The DMS module provides project-wise document organization with advanced retrieval capabilities:

- **Project-wise Storage**: Each project has isolated DMS data
- **Multi-format Support**: PDF, DOCX, ODT, ODS, ODP, images (OCR)
- **Intelligent Chunking**: 512 tokens per chunk with 51-token overlap
- **Hybrid Retrieval**: BM25 keyword + Vector similarity + Re-ranking
- **Separate ChromaDB Collection**: Isolated vector storage for document embeddings

---

### 9.2 DMS Service Architecture (`backend/services/dms/service.py`)

```python
class DMS:
    def __init__(self, db_path, chroma_path):
        self.db = DMSDB(db_path=db_path)
        self.document_processor = DocumentProcessor()
        self.text_chunker = TextChunker()
        self.vector_store = DMSVectorStore(chroma_path=chroma_path)
        self.metadata_index = MetadataIndex(self.vector_store)
        self.rag_pipeline = RAGPipeline(...)
        self.hybrid_retriever = HybridRetriever(...)
        self.rag_formatter = RAGContextFormatter()
```

**Key operations**:
- `upload_document(project_id, file_path, original_filename)`: Process and index
- `list_documents(project_id)`: List all documents
- `get_document_content(document_id)`: Retrieve document with chunks
- `delete_document(document_id)`: Remove document and index
- `auto_retrieve_for_topic(topic, k=10)`: Automatic RAG retrieval
- `manual_retrieve(query, document_ids, k=5)`: Manual RAG retrieval

---

### 9.3 RAG Pipeline (`backend/services/dms/rag_pipeline.py`)

Retrieval-Augmented Generation flow:

1. **Document Processing**: Parse file → extract text
2. **OCR (if enabled)**: PaddleOCR for scanned PDFs/images
3. **Chunking**: Split text into 512-token chunks with overlap
4. **Embedding**: Generate vector embeddings for each chunk
5. **Indexing**: Store in ChromaDB + metadata index
6. **Retrieval**: Hybrid search (BM25 + Vector + Re-ranking)
7. **Formatting**: Build context string for LLM injection

---

### 9.4 Hybrid Retriever (`backend/services/dms/hybrid_retriever.py`)

Combines three retrieval methods:

```python
class HybridRetriever:
    def retrieve(self, query, k=5):
        # 1. BM25 keyword search
        bm25_results = self.metadata_index.bm25_search(query, k=k)
        
        # 2. Vector similarity search
        vector_results = self.vector_store.search(query, k=k)
        
        # 3. Re-ranking (RRF - Reciprocal Rank Fusion)
        merged = self._rrf_merge(bm25_results, vector_results, k)
        
        return merged
```

---

## 10. Data Models & Schemas

### 10.1 Pydantic Schemas (`backend/models/schemas.py`)

#### 10.1.1 Enums

```python
class DebateStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AgentRole(StrEnum):
    STRATEGIST = "strategist"
    CRITIC = "critic"
    OPTIMIZER = "optimizer"
    MODERATOR = "moderator"

class SearchMode(StrEnum):
    OFF = "off"
    OPTIONAL = "optional"
    REQUIRED = "required"
```

#### 10.1.2 Request Models

```python
class DebateRequest(BaseModel):
    case: CaseInput
    agent_profile: list[AgentConfig] = Field(default_factory=lambda: [...])
    max_rounds: int = Field(default=3, ge=1, le=20)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    enable_fact_check: bool = False
    enable_memory: bool = False
    search_mode: SearchMode = SearchMode.OFF
    llm_profile_id: str = "openrouter-claude"
    prompt_variant: str = "default"
    agent_persona_ids: dict[str, str] = Field(default_factory=dict)
    language: str = "de"
    document_ids: list[str] = Field(default_factory=list)
    rag_auto_retrieve: bool = False
```

#### 10.1.3 Response Models

```python
class DebateStatusResponse(BaseModel):
    debate_id: str
    status: DebateStatus
    current_round: int = 0
    max_rounds: int = 3
    consensus_score: float | None = None
    rounds: list[RoundData] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    case_text: str = ""
    language: str = "de"
    llm_profile_id: str = ""
    anomalies: list[str] = Field(default_factory=list)
    project_id: str = ""
    project_name: str = ""
    rag_enabled: bool = False
    rag_document_count: int = 0
    rag_context_preview: str = ""
```

---

### 10.2 Profile Schemas (`backend/core/profiles.py`)

```python
class LLMProfile(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    provider: LLMProvider
    model: str
    api_base: str | None = None
    api_key_env: str = "OPENROUTER_API_KEY"
    max_tokens: int = 4096
    context_window: int | None = None
    temperature: float = 0.7
    timeout: int = 600
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None

class AgentPersona(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    role: Literal["strategist", "critic", "optimizer", "moderator"]
    system_prompt: str
    llm_profile_id: str
    max_rounds: int = 5
    consensus_threshold: float = 0.9
    description: str | None = None
    tags: list[str] = []

class PromptVariant(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    base_path: str
    overrides: dict[str, str] = Field(default_factory=dict)
    description: str | None = None
    parent_variant: str | None = None
```

---

## 11. API Reference

### 11.1 Debate Endpoints

#### POST /api/v1/debate
Create a new debate.

**Request body**:
```json
{
    "case": { "text": "Analyze the impact of AI on education..." },
    "max_rounds": 3,
    "consensus_threshold": 0.8,
    "llm_profile_id": "openrouter-claude",
    "prompt_variant": "default",
    "agent_persona_ids": {
        "strategist": "strategist-default",
        "critic": "critic-default",
        "optimizer": "optimizer-default",
        "moderator": "moderator-default"
    },
    "language": "en",
    "document_ids": ["doc-123"],
    "rag_auto_retrieve": false
}
```

**Response** (201):
```json
{
    "debate_id": "abc123...",
    "status": "pending",
    "created_at": "2026-05-06T10:30:00Z"
}
```

#### POST /api/v1/debate/{id}/start
Start a pending debate (returns immediately, runs in background).

**Response** (200):
```json
{
    "debate_id": "abc123...",
    "status": "running",
    "current_round": 0,
    "max_rounds": 3
}
```

#### GET /api/v1/debate/{id}/stream
SSE endpoint for real-time updates.

**Query params**: `project_id` (required, as query param because EventSource cannot send headers)

**Event types**:
- `workflow_started`: `{"type": "workflow_started", "message": "...", "debate_id": "..."}`
- `agent_preparing`: `{"type": "agent_preparing", "round": 1, "role": "strategist", "phase": "resolving_profile"}`
- `agent_started`: `{"type": "agent_started", "round": 1, "role": "strategist", "profile": "openrouter-claude", "model": "..."}`
- `llm_call_started`: `{"type": "llm_call_started", "round": 1, "role": "strategist", "model": "..."}`
- `agent_output`: `{"round": 1, "role": "strategist", "content": "...", "tokens_used": 150}`
- `round_update`: `{"round": 1, "consensus": 0.25, "agent_count": 4, "total_tokens": 600}`
- `status_change`: `{"status": "completed", "final_consensus": 0.85}`
- `oob_input`: `{"type": "oob_input", "oob_id": "...", "content": "...", "target": {...}}`
- `oob_consumed`: `{"type": "oob_consumed", "oob_ids": [...], "by_agent": "critic", "round": 1}`
- `web_search`: `{"type": "web_search", "round": 1, "role": "strategist", "query": "...", "result_count": 5}`

---

### 11.2 Profile Endpoints

#### GET /api/v1/profiles/llm
List all LLM profiles.

**Response** (200): Array of `LLMProfile` objects.

#### POST /api/v1/profiles/llm
Create a new LLM profile.

**Request body**: `LLMProfile` schema.

**Response** (201): Created `LLMProfile`.

#### GET /api/v1/profiles/agents?role=strategist
List agent personas (optional role filter).

**Response** (200): Array of `AgentPersona` objects.

#### GET /api/v1/profiles/prompts/default/preview?agent_role=strategist
Preview a prompt template for a specific agent role.

**Response** (200):
```json
{
    "variant_id": "default",
    "agent_role": "strategist",
    "content": "You are the Strategist agent...\n\n## Case\n{{ context }}\n..."
}
```

---

### 11.3 DMS Endpoints

#### POST /api/v1/dms/documents
Upload a document to the active project.

**Request**: `multipart/form-data` with `file` field.

**Response** (200):
```json
{
    "status": "ok",
    "document_id": "doc-456...",
    "filename": "report.pdf"
}
```

#### POST /api/v1/dms/retrieve
Retrieve relevant chunks for RAG.

**Request body**:
```json
{
    "query": "AI education impact",
    "document_ids": ["doc-456"],
    "k": 5
}
```

**Response** (200): Array of chunk objects with text, metadata, and relevance scores.

---

### 11.4 Configuration Endpoints

#### GET /api/v1/config/settings
Get current application settings.

**Response** (200):
```json
{
    "ui": { "language": "en" },
    "search": { "engine": "duckduckgo", "max_results": 5 },
    "privacy": { "strict_mode": false, "redact_traces": true, "retention_days": 90 }
}
```

#### PUT /api/v1/config/settings
Update application settings.

**Request body**: Partial settings object (only fields to update).

**Response** (200): Updated settings object.

---

## 12. Configuration

### 12.1 Environment Variables

Prefix: `DANWA_` (configured in `backend/core/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DANWA_APP_NAME` | `Debate-Agent` | Application name |
| `DANWA_APP_VERSION` | `2.0.0` | Application version |
| `DANWA_DEBUG` | `False` | Debug mode |
| `DANWA_HOST` | `0.0.0.0` | Server host |
| `DANWA_PORT` | `8000` | Server port |
| `DANWA_DB_PATH` | `data/audit.db` | SQLite database path |
| `DANWA_DEFAULT_MAX_ROUNDS` | `3` | Default max debate rounds |
| `DANWA_DEFAULT_CONSENSUS_THRESHOLD` | `0.8` | Default consensus threshold |
| `DANWA_DEFAULT_AGENT_PROFILE` | `default` | Default agent profile |
| `DANWA_SEARXNG_URL` | `http://localhost:8080` | SearXNG instance URL |
| `DANWA_SEARXNG_MAX_RESULTS` | `5` | Max search results |
| `DANWA_SEARXNG_REGION` | `de-de` | Search region |
| `DANWA_CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:8000"]` | CORS allowed origins |
| `OPENROUTER_API_KEY` | (none) | OpenRouter API key |
| `ANTHROPIC_API_KEY` | (none) | Anthropic API key |
| `OPENAI_API_KEY` | (none) | OpenAI API key |

---

### 12.2 YAML Configuration (`config/settings.yaml`)

```yaml
# Application settings
# Managed via /api/v1/config/settings API and Config UI

ui:
  language: en                   # Default UI language

search:
  engine: duckduckgo             # searxng | duckduckgo
  max_results: 5

privacy:
  strict_mode: false             # Block all external calls
  redact_traces: true            # PII redaction in logs
  retention_days: 90             # Auto-cleanup old data
```

---

### 12.3 Profile YAML Examples

#### LLM Profile (`profiles/llm/openrouter-claude.yaml`)

```yaml
id: openrouter-claude-3.6-sonnet
name: Claude 3.6 Sonnet (OpenRouter)
provider: openrouter
model: anthropic/claude-3.6-sonnet
api_base: https://openrouter.ai/api/v1
api_key_env: OPENROUTER_API_KEY
max_tokens: 4096
context_window: 200000
temperature: 0.7
timeout: 600
cost_per_1k_input: 0.003
cost_per_1k_output: 0.015
```

#### Agent Persona (`profiles/agents/strategist-default.yaml`)

```yaml
id: strategist-default
name: Default Strategist
role: strategist
system_prompt: |
    You are the Strategist agent in a multi-agent debate system.
    Your task is to analyze the input factually and develop a logical argumentation structure.
    
    ## Your Output Format
    1. Problem core
    2. Strategy
    3. Key assumptions
    4. Open points
llm_profile_id: openrouter-claude-3.6-sonnet
max_rounds: 5
consensus_threshold: 0.9
tags: [default, balanced]
```

---

## 13. Development Guide

### 13.1 Prerequisites

- **Python 3.11+**
- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 18+** and npm (for frontend development)
- **LM Studio** (optional, for local LLMs)
- **SearXNG** (optional, for web search)

---

### 13.2 Quick Setup

```bash
cd /media/data/coding/danwa

# Run the setup script (installs uv, creates venv, installs deps)
bash setup.sh

# Set up DMS dependencies (optional, for PaddleOCR)
bash scripts/setup_dms.sh

# Set environment variables
export OPENROUTER_API_KEY="your_key_here"
```

---

### 13.3 Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server (http://localhost:5173)
npm run dev

# Build for production (outputs to frontend/dist/)
npm run build

# Preview production build
npm run preview
```

---

### 13.4 Running the Application

#### Development Mode

```bash
# Terminal 1: Start backend
bash scripts/start.sh

# Terminal 2: Start frontend (optional)
cd frontend && npm run dev
```

- Backend: `http://localhost:8000` (FastAPI with interactive docs at `/docs`)
- Frontend: `http://localhost:5173`

#### Production Mode

```bash
# Build frontend
cd frontend && npm run build

# Start backend (serves frontend static files)
cd ..
bash scripts/start.sh
```

Access at `http://localhost:8000`.

---

### 13.5 Testing

#### Backend Tests (pytest)

```bash
# Run all tests
make test
# or
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/backend/test_debate_api.py -v

# Run with asyncio mode
uv run pytest tests/backend/ -v --asyncio-mode=auto
```

#### Frontend Tests (Playwright)

```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run with UI mode
npm run test:e2e:ui

# Run with headed browser
npm run test:e2e:headed

# Run specific test suites
npm run test:contracts    # API contract tests
npm run test:visual       # Visual regression tests
npm run test:a11y          # Accessibility tests
npm run test:i18n          # Internationalization tests
```

---

### 13.6 Linting and Formatting

#### Backend (ruff)

```bash
# Lint
make lint
# or
uv run ruff check .

# Format
make format
# or
uv run ruff format .

# Run CI checks (lint + test)
make check
```

#### Frontend

```bash
cd frontend

# Lint (if configured)
npm run lint

# Format (if configured)
npm run format
```

---

### 13.7 Project Dependencies (`pyproject.toml`)

```toml
[project]
name = "debate-agent"
version = "2.0.0"
requires-python = ">=3.11"

[dependencies]
litellm>=1.40.0
pydantic>=2.7.0
pydantic-settings>=2.0.0
pyyaml>=6.0.0
httpx>=0.27.0
duckduckgo-search>=6.0.0
pdfplumber>=0.10.0
pypdf>=4.0.0
python-docx>=1.1.0
odfpy>=1.4.1
chromadb>=0.5.0
weasyprint>=61.0
tiktoken>=0.7.0
rank_bm25>=0.2.1
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
langgraph>=0.2.0
langchain-core>=0.3.0
jinja2>=3.1.0
sse-starlette>=2.0.0
python-dotenv>=1.0.0

[project.optional-dependencies]
dms = ["paddlepaddle>=3.0", "paddleocr>=3.5.0"]
test = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.4"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests/backend"]
```

---

## 14. Deployment

### 14.1 Production Build

```bash
# Build frontend
cd frontend
npm run build
cd ..

# Start backend (serves frontend from frontend/dist/)
bash scripts/start.sh
```

The FastAPI app automatically detects `frontend/dist/` and serves static files.

---

### 14.2 Docker Deployment (Optional)

While Danwa doesn't include Dockerfiles by default, you can create them:

**Backend Dockerfile**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile**:
```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

**Docker Compose** (with SearXNG):
```yaml
version: '3.8'
services:
  backend:
    build: .
    ports: ["8000:8000"]
    env_file: [".env"]
  frontend:
    build: ./frontend
    ports: ["80:80"]
  searxng:
    image: searxng/searxng
    ports: ["8080:8080"]
```

---

### 14.3 Scripts

#### `scripts/setup.sh`
Initial setup: install uv, create venv, install dependencies.

#### `scripts/start.sh`
Start the application (on-demand, no systemd required):
```bash
#!/bin/bash
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

#### `scripts/stop.sh`
Stop the application (kills uvicorn process).

#### `scripts/status.sh`
Check application status (port 8000 check).

#### `scripts/setup_dms.sh`
Set up DMS dependencies (PaddleOCR):
```bash
uv pip install ".[dms]"
```

---

## Appendix A: Troubleshooting

### Common Issues

#### "Connection refused" when accessing backend
- **Cause**: Backend not running
- **Fix**: Run `bash scripts/start.sh`

#### "LiteLLM error: Connection refused"
- **Cause**: Local LLM (LM Studio) not running
- **Fix**: Start LM Studio and load a model, or switch to a cloud profile

#### "SearXNG request failed"
- **Cause**: SearXNG not running or wrong URL
- **Fix**: Update `config/settings.yaml` or disable web search

#### "Profile not found"
- **Cause**: LLM profile or agent persona doesn't exist
- **Fix**: Check `profiles/llm/` and `profiles/agents/` directories

#### "Parsing failed"
- **Cause**: Unsupported file format or corrupted file
- **Fix**: Convert to supported format, or system falls back to plain text

---

### Logs

- **Application logs**: `logs/debate-agent.log` (configured in `backend/main.py`)
- **Debate traces**: `logs/{session_id}.jsonl`
- **Frontend dev server**: Browser console

---

## Appendix B: Migration Notes

### Legacy Core (`src/`) → New Backend (`backend/`)

The project is in the process of migrating from:
- `src/core/debate_engine.py` → `backend/workflow/` (LangGraph)
- `src/core/llm_router.py` → `backend/services/llm_service.py`
- `src/dms/` → `backend/services/dms/`

The legacy code is still present in `src/` but is being phased out.

---

## Appendix C: References

- **FastAPI**: https://fastapi.tiangolo.com
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **LiteLLM**: https://litellm.ai
- **Svelte 5**: https://svelte.dev
- **Tailwind CSS**: https://tailwindcss.com
- **ChromaDB**: https://www.trychroma.com
- **PaddleOCR**: https://github.com/PaddlePaddle/PaddleOCR
- **uv**: https://github.com/astral-sh/uv
- **SearXNG**: https://searxng.org

---

*Documentation generated for Danwa (Debate-Agent) v2.0.0*
