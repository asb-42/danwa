# Danwa (だんわ / 談話)

Auditable multi-agent debate platform that uses AI agents to analyze, critique, and optimize arguments through structured deliberation. Now with **DMS (Document Management System)** featuring **PaddleOCR** integration, **RAG (Retrieval-Augmented Generation)** pipeline, **project isolation**, **A2A (Agent-to-Agent) Protocol** integration, and **real-time SSE updates**.

> **Architecture (post-Phase-2, 2026-06-20):** This repository (`danwa`) is the **end-user frontend only**. It contains the Svelte 5 app used to run debates, browse documents, view audit trails and manage personal settings. Admin/developer features (Blueprint Canvas, Module Manager, Translation Dashboard, User Management, Server Health, Workflow-Exec standalone view, etc.) live in the separate **`danwa-studio`** repository. The shared FastAPI backend lives in **`danwa-core`** and the re-usable module assets (agents, prompts, roles, tones, LLM profiles, i18n, workflow templates) in **`danwa-modules`**.
>
> **Sidebar sections (danwa):** `START` (workspace, case-list, tags) · `WORK` (active debate, MVP debate, documents, archive) · `RESULTS` (audit) · `ACCOUNT` (profile, my-keys, inbox, browse).
>
> **Coming next:** Shared `@danwa/*` npm packages, admin→`/studio` redirect, full deployment topology. See `plans/2026-06-15_danwa-studio.md` and `plans/2026-06-20_danwa-user-facing-migration.md`.

## Quick Start

```bash
# Quick setup (installs uv, creates venv, installs deps)
bash setup.sh

# Set up DMS dependencies (optional PaddleOCR)
bash scripts/setup_dms.sh

# Start the application (on-demand)
bash scripts/start.sh

# Check status
bash scripts/status.sh

# Stop when done
bash scripts/stop.sh
```

Open `http://localhost:8000` in your browser.

No systemd required - runs on-demand via simple scripts.

### Docker Deployment (Production)

```bash
cp deploy/.env.example deploy/.env  # Edit JWT_SECRET_KEY
docker compose up -d                # Start all services
# With Celery worker for parallel debates:
docker compose --profile celery up -d
```

## How It Works

Four specialized AI agents collaborate in a structured debate, orchestrated by a **LangGraph state machine**:

```
Input → [Strategist] → [Critic] → [Optimizer] → [Moderator]
         ↓              ↓             ↓              ↓
      Strategy      Critique      Synthesis      Consensus (0.0-1.0)
```

1. **Strategist** - Develops logical argumentation structure
2. **Critic** - Identifies weaknesses and risks (Devil's Advocate)
3. **Optimizer** - Synthesizes strategy and criticism into refined output
4. **Moderator** - Evaluates consensus and scores the result

The debate runs for configurable rounds (1-20) and stops early when consensus threshold is met.

## Key Features

- **Multi-Agent Deliberation** - Four specialized agents produce well-reasoned analysis
- **Flexible LLM Backend** - Local (LM Studio, Ollama) or cloud (OpenRouter, OpenAI, Anthropic) via LiteLLM
- **Document Analysis** - Upload PDF, DOCX, ODT, ODS, ODP files with OCR support
- **Web Fact-Checking** - Optional validation via SearXNG or DuckDuckGo integration (off/optional/required modes)
- **Semantic Memory** - ChromaDB-powered precedent retrieval from past debates
- **Audit Trail** - Complete JSONL trace logs for reproducibility
- **Report Generation** - Export results as DOCX or PDF
- **Privacy Protection** - PII redaction (email, IP, phone) and configurable data retention
- **Project Isolation** - SQLite-backed project system with isolated data storage per project
- **Document Management System (DMS)** - Project-wise document organization with SQLite + ChromaDB
- **PaddleOCR Integration** - OCR for scanned PDFs and images
- **RAG Pipeline** - Automatic and manual document retrieval for debate context
- **Hybrid Retrieval** - BM25 + Vector search + Re-ranking for optimal results
- **Real-Time Updates** - Server-Sent Events (SSE) for live debate progress visualization
- **Unified Feedback System** - Real-time status bar, activity log panel, classified error display, and node execution indicators during workflow runs
- **Modern Web UI** - Svelte 5 + Tailwind CSS + @xyflow/svelte workflow graph
- **Internationalization** - Full i18n support for 14 languages (de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he) with RTL support and Translation Dashboard
- **Module System** - Extensible module architecture for agents, prompts, roles, LLM profiles, and workflow templates
- **Out-of-Band Inputs** - Inject additional context during running debates
- **A2A Protocol** - Agent-to-Agent communication via JSON-RPC 2.0 (server + client)
- **External Agent Integration** - Include external AI agents as debate participants
- **Agent Card Discovery** - Standard `/.well-known/agent.json` endpoint for A2A clients
- **Blueprint System** - Visual workflow editor for creating custom multi-agent workflows with drag-and-drop canvas
- **HITL System** - Human-in-the-loop interactions for querying agents and providing feedback during execution
- **Input/Output Composer** - Extensible plugin system for processing various input sources (audio, text, files) and generating multiple output formats (documents, audio, reports)
- **Text-to-Speech (TTS)** - Convert debate results to audio with multiple voice profiles and renderers
- **Tone Profiles** - Configure debate tone and style for different use cases
- **Role Definitions** - Define custom agent roles with specific behaviors and constraints
- **Workflow Templates** - Pre-built workflow templates for common use cases
- **Per-Agent LLM Parameters** - Override temperature, top_p, top_k, frequency_penalty, presence_penalty per agent in a blueprint
- **Diff & Replay Views** - Compare debate sessions and replay past executions with timeline navigation
- **Multi-User Authentication** - JWT-based auth with role-based access control (admin/editor/viewer)
- **Multi-Tenant Architecture** - Isolated tenants with cases, tags, and quotas
- **BYOK (Bring Your Own Key)** - Per-user LLM API key overrides
- **Transactional Drafting** - Structured document creation with Builder, Pragmatist, and Angel's Advocate nodes
- **Angel's Advocate** - Constructive advocacy workflow node
- **Kitsune Agent Tools** - 6 read-only tools for system queries via the assistant
- **Rate Limiting** - Configurable per-endpoint rate limits with slowapi
- **Prometheus Metrics** - /metrics endpoint for monitoring
- **Structured Logging** - JSON logging in production via structlog
- **Optional Celery Task Queue** - Parallel debate execution with Redis
- **Docker Deployment** - Production-ready Dockerfiles and docker-compose

## Technology Stack

| Component | Technology |
|-----------|-------------|
| Language | Python 3.11+ |
| Backend Framework | [FastAPI](https://fastapi.tiangolo.com) + [LangGraph](https://langchain-ai.github.io/langgraph/) |
| LLM Integration | [LiteLLM](https://litellm.ai) |
| UI Framework | [Svelte 5](https://svelte.dev) + [Tailwind CSS](https://tailwindcss.com) |
| Workflow Visualization | [@xyflow/svelte](https://svelteflow.dev) + [ELK.js](https://github.com/kieler/elkjs) |
| Frontend Build | [Vite](https://vitejs.dev) 5 |
| Vector Database | [ChromaDB](https://www.trychroma.com) |
| Web Search | SearXNG / DuckDuckGo |
| Document Parsing | pdfplumber, pypdf, python-docx, odfpy |
| Report Generation | python-docx, [WeasyPrint](https://weasyprint.org) |
| Database | SQLite (debates, sessions, projects) |
| DMS Module | Custom (SQLite + ChromaDB + PaddleOCR) |
| OCR Engine | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) (optional) |
| Package Manager (Python) | [uv](https://github.com/astral-sh/uv) |
| Package Manager (Node) | npm |
| Testing (Backend) | pytest 8+ |
| Testing (Frontend) | [Playwright](https://playwright.dev) 1.59+ (e2e, visual, a11y, i18n) |
| Linting | [ruff](https://github.com/astral-sh/ruff) 0.4+ |
| Validation | [Pydantic](https://docs.pydantic.dev) 2.7+ |
| SSE Support | [sse-starlette](https://github.com/syroegkin/sse-starlette) |
| i18n (Frontend) | Custom loaders (14 languages + RTL) |
| A2A Protocol | [Google A2A](https://github.com/google/A2A) (JSON-RPC 2.0 over HTTP) |
| A2A HTTP Client | [httpx](https://www.python-httpx.org) |
| Authentication | python-jose (JWT), passlib (bcrypt) |
| Task Queue | Celery + Redis (optional) |
| Logging | structlog (JSON) |
| Monitoring | prometheus-fastapi-instrumentator |
| Rate Limiting | slowapi |
| WSGI | Gunicorn with Uvicorn workers |

## Project Structure

```
danwa/
├── backend/                     # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── api/
│   │   ├── deps.py            # Dependency injection (get_project_id, stores)
│   │   ├── events.py          # SSE event bus (publish/subscribe)
│   │   ├── quota.py           # Tenant quota enforcement
│   │   ├── rate_limit.py      # Rate limiting (slowapi)
│   │   └── routers/           # API route handlers
│   │       ├── debate.py      # Debate CRUD + SSE stream
│   │       ├── profiles.py    # LLM, agent, prompt management
│   │       ├── dms.py        # Document Management System
│   │       ├── projects.py   # Project isolation
│   │       ├── audit.py      # Audit trail access
│   │       ├── config.py     # Application settings
│   │       ├── sessions.py   # Session management
│   │       ├── health.py     # Health check endpoint
│   │       ├── system.py     # System operations (reload, logs)
│   │       ├── blueprints.py  # Blueprint CRUD
│   │       ├── canvas.py     # Canvas layout management
│   │       ├── workflow_exec.py  # Workflow execution API
│   │       ├── workflow_reports.py  # Workflow report generation
│   │       ├── workflow_templates.py  # Workflow templates
│   │       ├── workflow_definitions.py  # Workflow definitions
│   │       ├── input_composer.py  # Input composer API
│   │       ├── output_composer.py  # Output composer API
│   │       ├── role_definitions.py  # Role definitions API
│   │       ├── tone_profiles.py  # Tone profiles API
│   │       ├── llm_profiles.py  # LLM profiles API
│   │       ├── auth.py          # Authentication endpoints
│   │       ├── tenants.py       # Multi-tenant management
│   │       ├── cases.py         # Case management
│   │       ├── tags.py          # Tag management
│   │       ├── case_scoped.py   # Case-scoped endpoints
│   │       └── user_keys.py     # User API key management
│   ├── blueprints/              # Blueprint system (visual workflow editor)
│   │   ├── models.py         # Blueprint data models
│   │   ├── repository.py     # Blueprint repository
│   │   ├── compiler.py       # Blueprint compiler
│   │   ├── canvas_to_workflow.py  # Canvas to workflow conversion
│   │   ├── importer.py       # Blueprint importer
│   │   ├── migrations.py     # Blueprint database migrations
│   │   └── workflow_models.py  # Workflow models
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars)
│   │   ├── profiles.py      # LLMProfile, AgentPersona, PromptVariant schemas
│   │   ├── security.py      # JWT & auth utilities
│   │   └── logging.py       # Structured logging (structlog)
│   ├── models/
│   │   ├── schemas.py       # API request/response Pydantic models
│   │   ├── render_job.py    # Render job models
│   │   ├── artifact.py      # Artifact models
│   │   ├── user.py          # User models
│   │   ├── tenant.py        # Tenant models
│   │   ├── case.py          # Case models
│   │   ├── tag.py           # Tag models
│   │   ├── membership.py    # Membership models
│   │   └── transactional.py # Transactional drafting models
│   ├── workflow/
│   │   ├── debate_graph.py  # LangGraph state machine builder
│   │   ├── nodes.py         # Node functions (initialize, run_agent, etc.)
│   │   ├── nodes/           # Specialized workflow nodes
│   │   │   ├── angels_advocate_nodes.py  # Angel's Advocate workflow
│   │   │   ├── builder_nodes.py          # Builder workflow nodes
│   │   │   └── pragmatist_nodes.py       # Pragmatist workflow nodes
│   │   ├── state.py        # DebateState TypedDict definition
│   │   ├── hitl/           # Human-in-the-loop system
│   │   │   ├── api.py       # HITL API endpoints
│   │   │   ├── contracts.py # HITL contracts
│   │   │   ├── graph.py     # HITL graph management
│   │   │   ├── nodes.py     # HITL nodes
│   │   │   ├── round_manager.py  # HITL round management
│   │   │   ├── security.py  # HITL security
│   │   │   ├── state.py     # HITL state
│   │   │   └── agent_query.py  # HITL agent queries
│   │   ├── debate_workflow.py  # Debate workflow orchestration
│   │   ├── immutability.py  # Workflow immutability
│   │   ├── interjection.py  # Workflow interjection
│   │   ├── report_generator.py  # Report generation
│   │   ├── report_jobs.py   # Report job management
│   │   ├── state_snapshot.py  # State snapshot management
│   │   ├── workflow_compiler.py  # Workflow compilation
│   │   ├── workflow_routers.py  # Workflow API routers
│   │   ├── workflow_runner.py  # Workflow execution
│   │   ├── workflow_state.py  # Workflow state management
│   │   └── audit_logger.py  # Audit logging
│   ├── services/
│   │   ├── llm_service.py  # LLM calls (LiteLLM + local HTTP)
│   │   ├── profile_service.py # YAML profile CRUD + validation
│   │   ├── prompt_service.py # Markdown template rendering
│   │   ├── web_search.py   # SearXNG / DuckDuckGo integration
│   │   ├── dms/           # Document Management System services
│   │   │   ├── service.py   # DMS facade (orchestrator)
│   │   │   ├── database.py  # SQLite schema for DMS
│   │   │   ├── project_manager.py # Project CRUD
│   │   │   ├── document_processor.py # File parsing + OCR
│   │   │   ├── chunker.py   # Text chunking (512 tokens)
│   │   │   ├── vector_store.py # ChromaDB interface
│   │   │   ├── metadata_index.py # Chunk metadata indexing
│   │   │   ├── rag_pipeline.py # RAG pipeline
│   │   │   ├── hybrid_retriever.py # BM25 + Vector + Re-ranking
│   │   │   ├── rag_context_formatter.py # RAG context formatting
│   │   │   └── config.py    # DMS configuration
│   │   ├── input/         # Input plugin system
│   │   │   ├── base.py     # Base plugin interface
│   │   │   ├── input_engine.py  # Input engine
│   │   │   ├── input_job_store.py  # Input job storage
│   │   │   ├── input_store.py  # Input storage
│   │   │   ├── plugin_manifest.py  # Plugin manifest
│   │   │   ├── registry.py  # Plugin registry
│   │   │   ├── mcp_adapter.py  # MCP adapter
│   │   │   └── plugins/    # Input plugins
│   │   ├── output/        # Output plugin system
│   │   │   ├── base.py     # Base plugin interface
│   │   │   ├── registry.py  # Plugin registry
│   │   │   └── plugins/    # Output plugins
│   │   │       ├── print_plugin.py  # Print plugin (DOCX/PDF/ODF)
│   │   │       ├── tts_plugin.py  # TTS plugin
│   │   │       ├── mimo_tts_renderer.py  # MIMO TTS renderer
│   │   │       ├── edge_tts_renderer.py  # Edge TTS renderer
│   │   │       ├── print_layout_engine.py  # Print layout engine
│   │   │       ├── print_models.py  # Print models
│   │   │       ├── tts_models.py  # TTS models
│   │   │       ├── tts_script_engine.py  # TTS script engine
│   │   │       ├── audio_helpers.py  # Audio helpers
│   │   │       └── voice_store.py  # Voice store
│   │   ├── artifact_store.py  # Artifact storage
│   │   ├── doc_parser.py  # Document parsing
│   │   ├── meta_workflow.py  # Meta workflow management
│   │   ├── render_engine.py  # Render engine orchestration
│   │   ├── render_job_store.py  # Render job storage
│   │   ├── stt_service.py  # Speech-to-Text service
│   │   └── tone_prompt_injector.py  # Tone prompt injection
│   ├── a2a/                    # A2A Protocol (Agent-to-Agent)
│   │   ├── schemas.py        # A2A JSON-RPC schemas (Task, Message, Part)
│   │   ├── config.py         # A2A configuration loader
│   │   ├── agent_card.py     # Agent Card for discovery
│   │   ├── task_manager.py   # SQLite-backed task persistence
│   │   ├── server.py         # A2A Server (incoming tasks)
│   │   ├── router.py         # FastAPI router (JSON-RPC + Agent Card)
│   │   ├── client.py         # A2A Client (outgoing calls)
│   │   └── node.py           # LangGraph node for A2A agents
│   ├── tasks/                  # Celery task queue
│   │   ├── celery_app.py      # Celery application setup
│   │   ├── debate.py          # Debate task definitions
│   │   ├── dispatch.py        # Task dispatch logic
│   │   └── workflow.py        # Workflow task definitions
│   ├── state/
│   │   └── workflow_state.py  # Workflow state management
│   ├── persistence/
│   │   ├── project_store.py # JSON file-based project storage
│   │   ├── debate_store.py  # SQLite debate storage
│   │   ├── audit.py        # Audit event recording
│   │   ├── user_store.py   # User storage
│   │   ├── tenant_store.py # Tenant storage
│   │   ├── case_store.py   # Case storage
│   │   ├── tag_store.py    # Tag storage
│   │   ├── membership_store.py # Membership storage
│   │   └── user_key_store.py # User key storage (BYOK)
│   ├── repositories/
│   │   ├── profile_repo.py # Profile repository
│   │   └── proposal_repo.py  # Proposal repository
│   └── migrations/
│       └── migrate_projects.py # Project isolation migration
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
│   │   │   ├── ArchiveView.svelte
│   │   │   ├── BlueprintCanvasView.svelte  # Blueprint canvas editor
│   │   │   ├── InputComposerView.svelte  # Input composer
│   │   │   ├── OutputComposerView.svelte  # Output composer
│   │   │   ├── DiffView.svelte  # Diff view
│   │   │   └── ReplayView.svelte  # Replay view
│   │   ├── components/       # Reusable UI components
│   │   │   ├── Layout.svelte
│   │   │   ├── Sidebar.svelte
│   │   │   ├── WorkflowGraph.svelte
│   │   │   ├── DebateTimeline.svelte
│   │   │   ├── ConsensusPanel.svelte
│   │   │   ├── blueprint/      # Blueprint components
│   │   │   ├── config/        # Config components
│   │   │   ├── debate/        # Debate components
│   │   │   ├── hitl/          # HITL components
│   │   │   ├── input/         # Input composer components
│   │   │   ├── output/        # Output composer components
│   │   │   └── workflow/      # Workflow visualization
│   │   │       ├── WorkflowCanvas.svelte
│   │   │       ├── nodes/     # AgentNode, InputNode, etc.
│   │   │       ├── edges/     # FlowEdge, FeedbackEdge, etc.
│   │   │       └── panels/   # TimelinePanel, NodeDetailPanel
│   │   ├── lib/              # Utilities and state management
│   │   │   ├── api.js        # API client (fetch wrapper)
│   │   │   ├── stores.js     # Svelte writable stores
│   │   │   ├── sse.js        # SSE client for real-time updates
│   │   │   ├── i18n/        # Internationalization
│   │   │   └── workflow/     # Workflow state management
│   │   └── tests/           # Playwright E2E tests
│   ├── package.json          # Node dependencies
│   ├── vite.config.js        # Vite configuration
│   ├── tailwind.config.js    # Tailwind CSS config
│   └── postcss.config.js     # PostCSS config
├── modules/                     # Extensible module system (per-module directories)
│   ├── agent-*/                # Agent modules (manifest.json + profile.yaml)
│   ├── prompt-*/               # Prompt modules (manifest.json + profile.md)
│   ├── role-*/                 # Role definition modules (manifest.json + profile.json)
│   ├── tone-system-*/          # Tone profile modules (manifest.json + profile.json)
│   ├── workflow-tpl-*/         # Workflow template modules (manifest.json + profile.json)
│   └── llm-*/                  # LLM profile modules (manifest.json + profile.yaml)
├── profiles/                    # Profile configuration (YAML + Markdown, being migrated to modules)
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
│           └── steiner/          # Steiner variant
├── config/                       # Application settings
│   ├── settings.yaml           # App settings (search, privacy, DMS, UI)
│   └── prompts/
│       └── kitsune/            # Kitsune agent prompt templates
├── data/                        # Runtime data (created at runtime)
│   ├── audit.db                # SQLite database for audit events
│   └── projects/              # Per-project data
│       ├── _default/           # System default project
│       └── {project_id}/
├── logs/                         # Debate trace logs (JSONL)
│   └── debate-agent.log         # Application log file
├── tests/                        # Pytest test suite
│   ├── backend/                 # Backend-specific tests
│   └── ...
├── docs/                         # Documentation
│   ├── user_manual.md          # User-facing manual
│   └── technical_documentation.md # Technical documentation
├── scripts/                      # Utility scripts
│   ├── setup.sh                # Quick setup (uv, venv, deps)
│   ├── start.sh                # Start application
│   ├── stop.sh                # Stop application
│   └── status.sh              # Check application status
├── plans/                       # Development plans and sprint docs
├── pyproject.toml               # Python project metadata & dependencies
├── Makefile                     # Dev workflow (install, test, lint, format)
├── Dockerfile.backend           # Backend Docker image
├── Dockerfile.frontend          # Frontend Docker image
├── docker-compose.yml           # Multi-service Docker Compose
├── deploy/                      # Deployment configs
│   ├── nginx.conf               # Nginx reverse proxy
│   ├── .env.example             # Environment template
│   └── prometheus.yml           # Prometheus config
├── .dockerignore                # Docker ignore rules
└── setup.sh                     # Quick setup script
```

## Configuration

The profile system uses typed Pydantic schemas with YAML files. All profiles are managed via the `/api/v1/profiles/` API and the Config UI.

### LLM Profiles (`profiles/llm/*.yaml`)

Each LLM profile is a separate YAML file with typed fields:

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

Available LLM profiles: `openrouter-claude`, `openrouter-gpt4`, `openrouter-grok-4.2`, `xiaomi-mimo-v2.5-pro`, and several local models.

### Agent Personas (`profiles/agents/*.yaml`)

Each agent persona defines role, system prompt, and linked LLM profile:

```yaml
# profiles/agents/strategist-default.yaml
id: strategist-default
name: Default Strategist
role: strategist              # strategist | critic | optimizer | moderator
system_prompt: |
  You are the Strategist agent in a multi-agent debate system.
  ...
llm_profile_id: openrouter-claude-3.6-sonnet
max_rounds: 5
consensus_threshold: 0.9
tags: [default, balanced]
```

Default personas: `strategist-default`, `critic-default`, `optimizer-default`, `moderator-default`. Additional personas with `-example` suffix are also provided.

### Prompt Variants (`profiles/prompts/`)

Prompt templates are Markdown files organized by variant, with optional language-specific overrides (`*-en.md`):

```
profiles/prompts/
├── default/              # Default variant
│   ├── strategist.md     # German
│   ├── strategist-en.md  # English
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

### Profile API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/profiles/llm` | List all LLM profiles |
| GET | `/api/v1/profiles/llm/{id}` | Get specific LLM profile |
| POST | `/api/v1/profiles/llm` | Create LLM profile |
| PUT | `/api/v1/profiles/llm/{id}` | Update LLM profile |
| DELETE | `/api/v1/profiles/llm/{id}` | Delete LLM profile |
| GET | `/api/v1/profiles/agents` | List agent personas (`?role=` filter) |
| GET | `/api/v1/profiles/agents/{id}` | Get specific persona |
| POST | `/api/v1/profiles/agents` | Create agent persona |
| PUT | `/api/v1/profiles/agents/{id}` | Update agent persona |
| DELETE | `/api/v1/profiles/agents/{id}` | Delete agent persona |
| GET | `/api/v1/profiles/prompts` | List prompt variants |
| GET | `/api/v1/profiles/prompts/{id}/preview` | Preview prompt for agent role |
| POST | `/api/v1/profiles/prompts` | Create prompt variant |
| DELETE | `/api/v1/profiles/prompts/{id}` | Delete prompt variant |

### App Settings (`config/settings.yaml`)

```yaml
ui:
  language: en                   # Default UI language (en | de)

search:
  engine: duckduckgo             # searxng | duckduckgo (default: duckduckgo)
  max_results: 5

privacy:
  strict_mode: false             # Block all external calls
  redact_traces: true            # PII redaction in logs
  retention_days: 90             # Auto-cleanup old data
```

### A2A Configuration (`config/a2a.json`)

The A2A (Agent-to-Agent) protocol enables Danwa to participate in multi-agent workflows with external AI agents.

```json
{
  "enabled": false,
  "server": {
    "enabled": true,
    "path": "/a2a"
  },
  "external_agents": []
}
```

| Field | Description |
|-------|-------------|
| `enabled` | Enable/disable A2A integration globally |
| `server.enabled` | Enable the A2A server (accepts incoming tasks) |
| `server.path` | JSON-RPC endpoint path (default: `/a2a`) |
| `external_agents` | List of external agent URLs for outgoing calls |

#### A2A Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/.well-known/agent.json` | Agent Card discovery (A2A spec) |
| POST | `/a2a` | JSON-RPC endpoint (`tasks/send`, `tasks/get`, `tasks/cancel`) |

#### Using A2A in Debates

When creating a debate, include `a2a_agents` in the request body:

```json
{
  "case": { "text": "Should we adopt microservices?" },
  "a2a_agents": [
    {
      "url": "https://external-agent.example.com/a2a",
      "role": "external_reviewer",
      "position": "after:moderator"
    }
  ]
}
```

The external agent will be invoked as an additional debate participant after the standard agents (strategist, critic, optimizer, moderator) complete their rounds.

#### A2A Architecture

```
Danwa as Server (incoming):          Danwa as Client (outgoing):
┌─────────────┐                      ┌─────────────┐
│ External A2A │──tasks/send──▶      │   Danwa     │
│   Client     │◀──result────        │  Workflow   │
└─────────────┘                      │   Engine    │
       │                             └──────┬──────┘
       ▼                                    │
┌─────────────┐                      ┌──────▼──────┐
│  Danwa A2A  │                      │  A2A Client │
│   Server    │──creates──▶         │  (httpx)    │──tasks/send──▶
│  (FastAPI)  │  debate              └─────────────┘  External Agent
└─────────────┘
```

### JWT Authentication

| Variable | Description |
|----------|-------------|
| `DANWA_JWT_SECRET_KEY` | Secret key for JWT token signing |
| `DANWA_AUTH_ENABLED` | Enable/disable authentication (default: `false`) |

### Rate Limiting

| Variable | Description |
|----------|-------------|
| `DANWA_RATE_LIMIT_ENABLED` | Enable/disable rate limiting (default: `false`) |
| `DANWA_RATE_LIMIT_DEFAULT` | Default rate limit (e.g., `60/minute`) |

### Redis / Celery

| Variable | Description |
|----------|-------------|
| `DANWA_REDIS_URL` | Redis connection URL (e.g., `redis://localhost:6379/0`) |
| `DANWA_CELERY_ENABLED` | Enable Celery task queue for parallel debates (default: `false`) |

### Prometheus

| Variable | Description |
|----------|-------------|
| `DANWA_PROMETHEUS_ENABLED` | Enable Prometheus metrics endpoint (default: `false`) |

## Development

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Node.js 18+ and npm (for frontend development)
- (Optional) [LM Studio](https://lmstudio.ai) for local LLM hosting
- (Optional) [SearXNG](https://searxng.org) for web search

### Quick Setup

```bash
# Clone/download the project
cd /media/data/coding/danwa

# Run the setup script (installs uv, creates venv, installs deps)
bash setup.sh

# Set up DMS dependencies (optional, for PaddleOCR)
bash scripts/setup_dms.sh
```

### Frontend Setup

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

### Running the Application

#### Development Mode

```bash
# Terminal 1: Start backend
cd /media/data/coding/danwa
bash scripts/start.sh

# Terminal 2: Start frontend (optional, for development)
cd /media/data/coding/danwa/frontend
npm run dev
```

- Backend: `http://localhost:8000` (FastAPI with interactive docs at `/docs`)
- Frontend development server: `http://localhost:5173`

#### Production Mode

```bash
# Build frontend
cd /media/data/coding/danwa/frontend
npm run build

# Start backend (serves frontend static files)
cd ..
bash scripts/start.sh
```

Access the application at `http://localhost:8000`.

### Testing

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

### Linting and Formatting

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

## Project Dependencies (`pyproject.toml`)

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
rank-bm25>=0.2.1
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
langgraph>=0.2.0
langchain-core>=0.3.0
jinja2>=3.1.0
sse-starlette>=2.0.0
python-dotenv>=1.0.0

[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.4"]
dms = ["paddlepaddle>=3.0,<3.3.0", "paddleocr>=3.5.0"]
```

**Important Note**: PaddlePaddle 3.3.0+ has known PIR compatibility issues with OneDNN that cause OCR crashes. The version constraint `<3.3.0` ensures stable OCR operations. See [ADR-2024-05-12](docs/adr/2024-05-12-paddlepaddle-downgrade.md) for details.

## Documentation

- **User Manual**: `docs/user_manual.md` - Covers all features, configuration options, privacy settings, and troubleshooting
- **Technical Documentation**: `docs/technical_documentation.md` - Comprehensive in-depth technical documentation for developers

---

## Missing Links (Features Not Yet in UI)

> **What are "Missing Links"?** These are features fully implemented in the backend but **not yet accessible through the user interface**.
>
> **Last audited**: 2026-05-17 — full codebase scan.
>
> **Recently exposed (wired up in prior sprints)**:
> - Report Generation — download 500 error fixed, now functional
> - Application Settings — wired in ConfigView + ProjectSettings
> - Manual RAG Search — wired in DocumentsView
> - A2A Agent Discovery — wired in DebateView
> - Session Archive/Restore — wired in ArchiveView
> - Workflow-Exec Controls — wired in ExecutionPanel
> - Blueprint Compile/Clone — wired in BlueprintCanvasView
> - Canvas Layout CRUD — wired in Palette + BlueprintCanvas
> - Role Types CRUD — wired in RoleTypeForm + ConfigView
> - Language API — wired in LanguageSwitcher
> - Blueprint System — fully exposed in BlueprintCanvasView
> - HITL System — fully exposed in ExecutionPanel
> - Input/Output Composer — fully exposed in InputComposerView and OutputComposerView
> - Replay & Diff Views — fully exposed in ReplayView and DiffView
> - **Modules Management** — fully exposed in ModulesView
> - **Optimization Proposals** — fully exposed in ProposalsView (HITL approve/reject)
> - **Translation Dashboard** — fully exposed with LLM bulk translation support
> - **System Management** — fully exposed in ManageView
> - **Sidebar Restructuring** — organized into RUN, BUILD, Configuration, Evolve sections

### Legacy Session History — LOW IMPACT
- **Backend**: Legacy `backend/api/routers/sessions.py` router (superseded by newer routers)
- **Missing**: No frontend API functions or UI for legacy session list/detail/trace endpoints
- **Status**: Intentionally not exposed as it's superseded by newer routers

### Report SSE Progress Stream — LOW IMPACT
- **Backend**: `GET /api/v1/sessions/{session_id}/report/stream`
- **API Client**: `createReportSSE()` exists in `api.js` but **never called**
- **Missing**: No view consumes the report generation SSE stream for progress indication
- **Status**: Report generation is functional without this progress indicator

### Project-Level Settings Override — LOW IMPACT
- **Backend**: `GET /api/v1/config/settings/project/{id}`
- **Missing**: No frontend API function or UI for project-level settings overrides
- **Status**: i18n string exists (`projects.configHint`) but no implementation

### Summary Table

| Feature | Backend | API Client | UI | Status |
|---------|---------|------------|-----|--------|
| Legacy Session History | ✅ | ❌ Missing | ❌ Missing | **Not exposed (superseded)** |
| Report SSE Progress Stream | ✅ | ✅ Exists | ❌ Missing | **Not exposed (low priority)** |
| Project-Level Settings Override | ✅ | ❌ Missing | ❌ Missing | **Not exposed** |
| Debate Workflow | ✅ | ✅ | ✅ | Exposed |
| HITL Interactions | ✅ | ✅ | ✅ | Exposed |
| A2A in Debates | ✅ | ✅ | ✅ | Exposed |
| Blueprint System | ✅ | ✅ | ✅ | Exposed |
| Input/Output Composer | ✅ | ✅ | ✅ | Exposed |
| Replay & Diff Views | ✅ | ✅ | ✅ | Exposed |

*For full details, see the "Missing Links" sections in `docs/technical_documentation.md` and `docs/user_manual.md`.*

---

## License

This project is licensed under the **GNU Affero General Public License (AGPL)**.
See the [LICENSE](LICENSE) file for details.

---

*Danwa v2.2.0 | Built with FastAPI + LangGraph + LiteLLM + Svelte 5 + @xyflow/svelte*
