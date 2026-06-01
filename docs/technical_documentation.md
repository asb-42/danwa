# Danwa (Debate-Agent) — Technical Documentation

> **Version**: 2.2.0  
> **Last Updated**: 2026-06-01  
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
10. [Backup System](#10-backup-system)
11. [Blueprint System](#11-blueprint-system)
12. [HITL (Human-in-the-Loop) System](#12-hitl-human-in-the-loop-system)
13. [Input/Output Plugin System](#13-inputoutput-plugin-system)
14. [Data Models & Schemas](#14-data-models--schemas)
15. [API Reference](#15-api-reference)
16. [Configuration](#16-configuration)
17. [A2A Protocol Integration](#17-a2a-protocol-integration)
18. [Development Guide](#18-development-guide)
19. [Deployment](#19-deployment)
20. [Multi-User & Authentication System](#20-multi-user--authentication-system)
21. [Multi-Tenant Architecture](#21-multi-tenant-architecture)
22. [BYOK (Bring Your Own Key)](#22-byok-bring-your-own-key)
23. [Transactional Drafting Workflow](#23-transactional-drafting-workflow)
24. [Angel's Advocate Node](#24-angels-advocate-node)
25. [Kitsune Agent & Assistant Tools](#25-kitsune-agent--assistant-tools)
26. [Task Queue & Concurrency](#26-task-queue--concurrency)
27. [Observability & Monitoring](#27-observability--monitoring)
28. [Rate Limiting](#28-rate-limiting)
29. [Docker Deployment](#29-docker-deployment)
30. [CI/CD Pipeline](#30-cicd-pipeline)

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
- **Internationalization**: Full i18n support for 14 languages (de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he) with RTL support and Translation Dashboard for managing translations
- **Module System**: Extensible module architecture with per-module directories (manifest.json + profile), supporting agents, prompts, roles, tone systems, workflow templates, and LLM profiles
- **A2A Protocol**: Agent-to-Agent communication via JSON-RPC 2.0 for multi-agent workflows

---

## 2. Architecture Overview

Danwa follows a **decoupled frontend-backend architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                              │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Svelte 5 SPA + Tailwind CSS + @xyflow/svelte          │  │
│  │  - Dashboard, Debate, Audit, Config, Projects, Modules,    │  │
│  │    Proposals, Translation, Manage, Blueprint Views         │  │
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
| **i18n (Frontend)** | Custom loaders + Backend Translation API | 14 languages + RTL (Arabic, Hebrew) |
| **State Management** | Svelte stores | Reactive state for UI |
| **HTTP Client** | httpx | Async HTTP for LLM calls and web search |
| **Environment** | python-dotenv | .env file loading |
| **Authentication** | python-jose, passlib, bcrypt | JWT token creation/validation and password hashing |
| **Task Queue** | Celery + Redis | Optional parallel debate execution |
| **Structured Logging** | structlog | JSON logging in production, console in dev |
| **Rate Limiting** | slowapi | Per-endpoint and global rate limiting |
| **Metrics** | prometheus-fastapi-instrumentator | Prometheus metrics endpoint |
| **WSGI Server** | gunicorn | Production-grade ASGI server with worker management |

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
│   │       └── optimization_proposals.py  # Optimization proposals API
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
│   │   └── profiles.py      # LLMProfile, AgentPersona, PromptVariant schemas
│   ├── models/
│   │   ├── schemas.py       # API request/response Pydantic models
│   │   ├── render_job.py    # Render job models
│   │   └── artifact.py      # Artifact models
│   ├── workflow/
│   │   ├── debate_graph.py  # LangGraph state machine builder
│   │   ├── nodes.py         # Node functions (initialize, run_agent, etc.)
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
│   ├── a2a/                   # A2A Protocol integration
│   │   ├── __init__.py
│   │   ├── schemas.py       # A2A data models (Task, Message, Part)
│   │   ├── config.py        # A2A configuration loader
│   │   ├── agent_card.py    # Agent Card for discovery
│   │   ├── task_manager.py  # SQLite-backed task persistence
│   │   ├── server.py        # A2A server (incoming tasks)
│   │   ├── client.py        # A2A client (outgoing calls)
│   │   ├── node.py          # LangGraph node for A2A agents
│   │   └── router.py        # FastAPI router (JSON-RPC + Agent Card)
│   ├── persistence/
│   │   ├── project_store.py # JSON file-based project storage
│   │   ├── debate_store.py  # SQLite debate storage
│   │   └── audit.py        # Audit event recording
│   ├── repositories/
│   │   ├── profile_repo.py # Profile repository
│   │   └── proposal_repo.py  # Proposal repository
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
│   │   │   ├── ArchiveView.svelte
│   │   │   ├── BlueprintCanvasView.svelte  # Blueprint canvas editor
│   │   │   ├── InputComposerView.svelte  # Input composer
│   │   │   ├── OutputComposerView.svelte  # Output composer
│   │   │   ├── DiffView.svelte  # Diff view
│   │   │   ├── ReplayView.svelte  # Replay view
│   │   │   ├── ModulesView.svelte  # Module management
│   │   │   ├── ProposalsView.svelte  # Optimization proposals (HITL)
│   │   │   ├── ManageView.svelte  # System management
│   │   │   └── TranslationDashboard.svelte  # Translation management
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
│   │   │   ├── blueprint/      # Blueprint components
│   │   │   ├── config/        # Config components
│   │   │   ├── debate/        # Debate components
│   │   │   ├── hitl/          # HITL components
│   │   │   ├── input/         # Input composer components
│   │   │   ├── output/        # Output composer components
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
│   │   │   │       ├── en.js, de.js, fr.js, es.js, it.js
│   │   │   │       ├── pt.js, ru.js, zh.js, ja.js, ko.js
│   │   │   │       └── sv.js, el.js, ar.js, he.js
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
├── modules/                     # Extensible module system (per-module directories)
│   ├── agent-*/                # Agent modules (manifest.json + profile.yaml)
│   ├── prompt-*/               # Prompt modules (manifest.json + profile.md)
│   ├── role-*/                 # Role definition modules (manifest.json + profile.json)
│   ├── tone-system-*/          # Tone profile modules (manifest.json + profile.json)
│   ├── workflow-tpl-*/         # Workflow template modules (manifest.json + profile.json)
│   └── llm-*/                  # LLM profile modules (manifest.json + profile.yaml)
│
├── profiles/                    # Legacy profile configuration (being migrated to modules)
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

The `generate()` method is the main entry point and supports **extra_kwargs** — a whitelist-based mechanism for per-call LLM parameter overrides from Agent Bundles:

```python
async def generate(
    self,
    prompt: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    extra_kwargs: dict[str, Any] | None = None,  # Per-call LLM overrides
) -> GenerationResult
```

The `extra_kwargs` dict is filtered against an **allowed whitelist** before being merged into the payload. Only explicitly permitted keys can override LLM profile defaults:

```python
allowed = {"temperature", "top_p", "top_k", "frequency_penalty",
           "presence_penalty", "seed", "stop"}
for k, v in extra_kwargs.items():
    if k in allowed and v is not None:
        payload[k] = v
```

This prevents arbitrary parameter injection through bundles while still allowing fine-grained control. The `temperature` key in `extra_kwargs` takes precedence over the dedicated `temperature` parameter (last write wins in kwargs merge).

The service supports the following routing modes:

#### 5.4.1 Local Providers (OpenAI-compatible endpoints)

Direct HTTP calls to local LLM servers (LM Studio, Ollama, etc.), passing `extra_kwargs` into the request payload:

```python
async def _generate_local(self, messages, temperature, max_tokens, extra_kwargs=None):
    url = f"{self._profile.api_base}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    # extra_kwargs merged into payload (whitelist-filtered)
    response = await httpx.AsyncClient().post(url, json=payload, headers=headers)
    return GenerationResult(content=..., tokens_in=..., tokens_out=...)
```

#### 5.4.2 Cloud Providers (via LiteLLM)

Uses LiteLLM for unified access to OpenRouter, OpenAI, Anthropic, etc.:

```python
async def _generate_litellm(self, messages, temperature, max_tokens, extra_kwargs=None):
    model_name = f"{provider}/{model}"  # e.g., "openrouter/anthropic/claude-3.5-sonnet"
    response = await litellm.acompletion(
        model=model_name,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv(self._profile.api_key_env),
        **(extra_kwargs or {}),  # Whitlelist-filtered overrides
    )
    return GenerationResult(...)
```

#### 5.4.3 Cloudflare Provider

Accepts `extra_kwargs` with the same whitelist mechanism.

#### 5.4.4 GenerationResult

```python
@dataclass
class GenerationResult:
    content: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""
```

**Note**: `generate_with_fallback()` does NOT pass `extra_kwargs` — A2A fallback calls use profile defaults only.

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
| MVP Debate | `MvpDebateView.svelte` | Lightweight debate view with role-colored cards, activity strip, consensus bar, SSE status |
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
| DebateActivityStrip | `DebateActivityStrip.svelte` | Per-agent activity progress, role verb animation, model/provider info, token counter |
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

Custom i18n system with language loaders and backend translation API:

```javascript
// i18n/index.js
import { en } from './loaders/en.js';
import { de } from './loaders/de.js';
// ... 12 more language loaders

const translations = { en, de, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he };

export function t(key, params = {}) {
    let text = translations[locale][key] || key;
    // Replace {param} placeholders...
    return text;
}
```

**Supported Languages** (14 total):

| Code | Language | Script | Direction |
|------|----------|--------|-----------|
| de | German | Latin | LTR |
| en | English | Latin | LTR |
| fr | French | Latin | LTR |
| es | Spanish | Latin | LTR |
| it | Italian | Latin | LTR |
| pt | Portuguese (BR) | Latin | LTR |
| ru | Russian | Cyrillic | LTR |
| zh | Chinese (Simplified) | CJK | LTR |
| ja | Japanese | CJK | LTR |
| ko | Korean | Hangul | LTR |
| sv | Swedish | Latin | LTR |
| el | Greek | Greek | LTR |
| ar | Arabic | Arabic | RTL |
| he | Hebrew | Hebrew | RTL |

**Language files** (850+ keys each):
- `loaders/en.js`: English translations
- `loaders/de.js`: German translations
- `loaders/fr.js`: French translations
- `loaders/es.js`: Spanish translations
- `loaders/it.js`: Italian translations
- `loaders/pt.js`: Portuguese (Brazilian) translations
- `loaders/ru.js`: Russian translations
- `loaders/zh.js`: Chinese (Simplified) translations
- `loaders/ja.js`: Japanese translations
- `loaders/ko.js`: Korean translations
- `loaders/sv.js`: Swedish translations
- `loaders/el.js`: Greek translations
- `loaders/ar.js`: Arabic translations (RTL)
- `loaders/he.js`: Hebrew translations (RTL)

**Translation Dashboard** (`frontend/src/views/TranslationDashboard.svelte`):
- Full-page UI for managing translations across all 14 languages
- Shows translation coverage statistics per language
- Supports LLM-powered bulk translation of missing keys
- Manual editing of individual translations
- Add new languages dynamically via "Add Language" dialog
- Real-time coverage visualization with progress bars

**Backend Translation API** (`/api/v1/i18n/`):
- `GET /locales` — List supported languages
- `GET /{locale}` — Get all translations for a language
- `GET /{locale}/{key}` — Get single translation
- `POST /{locale}` — Create/update translation
- `POST /translate` — LLM ad-hoc translation
- `POST /bulk-translate` — Batch LLM translation
- `DELETE /{locale}/{key}` — Delete translation

**RTL Support**:
- CSS Logical Properties for layout mirroring
- Dynamic `dir` attribute on `<html>` element
- `rtl.css` for RTL-specific styles
- BiDi text handling for mixed LTR/RTL content

**Language switching**:
- UI toggle via `LanguageSwitcher.svelte` with search
- Persisted to `localStorage`
- Sent to backend via `Accept-Language` header
- Per-project default language setting

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

## 10. Backup System

### 10.1 Overview

The Backup System provides automated and manual backup creation, verification, and restoration of all user data. It was introduced in response to a data loss incident where all debate data, audit trails, and DMS vector stores were accidentally deleted during a migration.

**Key Features**:
- ZIP archives with SHA-256 integrity verification
- Automatic shutdown backups (opt-in)
- Configurable retention policy
- Full data restoration with path safety checks
- UI integration for management

---

### 10.2 BackupService (`backend/persistence/backup.py`)

```python
class BackupService:
    """Erstellt, verwaltet und validiert Backup-Archive."""

    BACKUP_DIR = Path("backups")

    def create_backup(self, trigger: str = "manual") -> BackupResult:
        """Creates a ZIP archive with timestamp and checksums."""

    def list_backups(self) -> list[BackupMetadata]:
        """Lists all available backups sorted by date (newest first)."""

    def get_backup_file_list(self, backup_id: str) -> list[str]:
        """Returns the list of files contained in a backup."""

    def verify_backup(self, backup_id: str) -> VerificationResult:
        """Verifies integrity (ZIP checksum + SHA-256SUMS)."""

    @staticmethod
    def restore(backup_path: Path) -> RestoreResult:
        """Extracts and restores data from a backup.
        ⚠️ Overwrites existing data! App must be stopped."""
```

**Data Classes**:
- `BackupResult`: backup_id, path, size_bytes, file_count, created_at, sha256, duration_seconds
- `BackupMetadata`: backup_id, created_at, app_version, commit_hash, file_count, size_bytes, trigger, sha256
- `VerificationResult`: valid, errors, file_count_verified
- `RestoreResult`: success, message, restored_files

---

### 10.3 Backup Creation Process

1. **Timestamp**: UTC ISO format → `2026-05-15T02-30-00Z`
2. **Filename**: `danwa-backup-2026-05-15T02-30-00Z.zip`
3. **File Discovery**: Recursively walk include paths, skip exclude patterns
4. **SHA-256 Calculation**: Per-file hash → `SHA-256SUMS` file
5. **Metadata Generation**: JSON with app version, commit hash, trigger type
6. **ZIP Packaging**: ZIP64 for >4GB support
7. **ZIP Checksum**: SHA-256 of the entire archive
8. **Retention Cleanup**: Delete oldest backups if configured

**Include Paths** (default):
```python
INCLUDE_PATHS = [
    "data/projects",          # All project data
    "data/audit.db",          # Audit trail
    "data/a2a_tasks.db",      # A2A task manager
    "data/blueprints.db",     # Blueprint repository
    "config/settings.yaml",   # App configuration
    "config/a2a.json",        # A2A server config
    "config/llm_profiles.yaml", # LLM profiles with API keys
]
```

**Exclude Patterns**:
```python
EXCLUDE_PATTERNS = [
    ".git/", ".venv/", "node_modules/", "__pycache__/",
    "*.pyc", "logs/", "memory/", ".env", "frontend/dist/",
    "backups/", ".idea/", ".vscode/", "*.tmp", "*.bak",
    "*.swp", ".DS_Store", "Thumbs.db",
]
```

---

### 10.4 Backup Metadata

Each backup contains a `metadata.json` file:

```json
{
    "version": 1,
    "app_version": "2.0.0",
    "commit_hash": "7e40355...",
    "created_at": "2026-05-15T02:30:00Z",
    "created_by": "api-endpoint",
    "trigger": "manual",
    "file_count": 342,
    "total_bytes": 83886080,
    "paths_included": ["data/", "config/"],
    "db_schema_versions": {
        "audit.db": "v29",
        "blueprints.db": "v1"
    },
    "settings": {
        "backup_auto_on_shutdown": false,
        "backup_retention_count": 0,
        "backup_encrypt": false
    }
}
```

---

### 10.5 Backup Verification

Verification checks:
1. **ZIP Integrity**: `zf.testzip()` for corrupted files
2. **SHA-256SUMS**: Verify each file's hash matches the stored checksum
3. **Metadata Validation**: Ensure `metadata.json` exists and is valid JSON

```python
result = service.verify_backup("danwa-backup-2026-05-15T02-30-00Z.zip")
# VerificationResult(valid=True, errors=[], file_count_verified=342)
```

---

### 10.6 Backup Restoration

Restoration process:
1. **Integrity Check**: Verify ZIP before extraction
2. **Path Safety**: Ensure all extracted paths stay within project root
3. **Extraction**: Write files to their original locations
4. **Error Handling**: Report any files that failed to restore

```python
result = BackupService.restore(Path("backups/danwa-backup-2026-05-15T02-30-00Z.zip"))
# RestoreResult(success=True, message="Restore completed: 342 files restored", restored_files=342)
```

⚠️ **Warning**: Restoration overwrites existing data. The application should be stopped before restoring.

---

### 10.7 Backup Configuration

Settings in `backend/core/config.py`:

```python
class Settings(BaseSettings):
    # Backup settings
    backup_enabled: bool = True
    backup_auto_on_shutdown: bool = False     # Default: opt-in
    backup_retention_count: int = 0            # 0 = unlimited
    backup_encrypt: bool = False               # Not yet implemented
    backup_dir: str = "backups"
```

---

### 10.8 Shutdown Auto-Backup

Integrated into `backend/main.py` lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup logic ...
    yield

    # Shutdown backup (opt-in)
    if settings.backup_auto_on_shutdown:
        from backend.persistence.backup import BackupService
        service = BackupService()
        result = service.create_backup(trigger="shutdown")
        logger.info("Shutdown backup created: %s", result.path)
```

---

### 10.9 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/config/backup` | Create backup (`{"trigger": "manual|shutdown"}`) |
| `GET` | `/api/v1/config/backups` | List all backups with metadata |
| `GET` | `/api/v1/config/backups/{id}` | Get backup metadata |
| `GET` | `/api/v1/config/backups/{id}/files` | List files in backup |
| `POST` | `/api/v1/config/backups/{id}/verify` | Verify backup integrity |
| `POST` | `/api/v1/config/backups/{id}/restore` | Restore from backup |
| `DELETE` | `/api/v1/config/backups/{id}` | Delete a backup |
| `GET` | `/api/v1/config/backup-settings` | Get backup settings |
| `PUT` | `/api/v1/config/backup-settings` | Update backup settings |

---

### 10.10 Frontend Integration

**Stores** (`frontend/src/lib/stores.js`):
```javascript
export const backupConfig = persisted('danwa.backupConfig', {
    autoOnShutdown: false,
    retentionCount: 0,
    encrypt: false
});
export const backups = writable([]);
export const backupDetails = writable(null);
export const isLoadingBackups = writable(false);
```

**API Functions** (`frontend/src/lib/api.js`):
- `createBackup(trigger)`
- `getBackups()`
- `getBackup(backupId)`
- `getBackupFiles(backupId)`
- `verifyBackup(backupId)`
- `restoreBackup(backupId)`
- `deleteBackup(backupId)`
- `getBackupSettings()`
- `updateBackupSettings(settings)`

**UI** (`frontend/src/views/ConfigView.svelte`):
- Backup settings tab with checkboxes and number inputs
- Backup creation button with progress feedback
- Backup list table with actions (verify, restore, delete, view files)
- File list panel for backup contents

---

### 10.11 Testing

**Unit Tests** (`tests/backend/test_backup.py`):
- `TestBackupResult`, `TestBackupMetadata`, `TestVerificationResult`, `TestRestoreResult`
- `TestCreateBackup`: ZIP creation, metadata.json, SHA-256SUMS, project data, exclusions, triggers
- `TestListBackups`: Empty directory, sorted listing
- `TestVerifyBackup`: Valid backup, non-existent backup, invalid ZIP
- `TestRestore`: Restore from backup, non-existent file, invalid ZIP
- `TestGetBackupFileList`: File list, non-existent backup

**Integration Tests** (`tests/backend/test_backup_api.py`):
- `TestCreateBackupAPI`: Create backup with manual/shutdown triggers
- `TestListBackupsAPI`: Empty list, list after creation
- `TestGetBackupAPI`: Metadata retrieval, 404 handling
- `TestListBackupFilesAPI`: File listing
- `TestVerifyBackupAPI`: Valid backup verification
- `TestRestoreBackupAPI`: Full restore workflow
- `TestDeleteBackupAPI`: Backup deletion
- `TestBackupSettingsAPI`: Get/update settings

---

## 11. Blueprint System

<!-- UPDATED -->

### 11.1 Overview

The Blueprint System is a visual workflow editor that allows users to create, manage, and execute custom multi-agent workflows through a graphical interface. It provides a canvas-based editor for designing workflows with nodes and edges, which can then be compiled into executable LangGraph workflows.

### 11.2 Recent Updates

- **Workflow Models (`workflow_models.py`)**: Added new node types (condition, subgraph) and edge types.
- **Repository (`repository.py`)**: Introduced persistent storage for blueprints with CRUD operations.
- **Migration Support (`migrations.py`)**: Schema migration for blueprint data.
- **Canvas Compilation (`canvas_to_workflow.py`)**: Improved conversion logic with parallel execution support.
- **Frontend**: Enhanced `BlueprintCanvas.svelte` with drag-and-drop (`dnd.js`), auto-layout (`layout.js`), and a reactive store (`store.svelte.js`). Unit tests added.

### 11.3 Architecture (`backend/blueprints/`)

```
backend/blueprints/
├── __init__.py
├── bundle_io.py          # Bundle import/export (supports model_params)
├── canvas_to_workflow.py
├── compiler.py
├── importer.py
├── migrations.py         # Schema migrations (V29: model_params_json)
├── models.py             # AgentBundle, ResolvedBundle (with model_params)
├── repository.py         # CRUD with model_params_json serialization
├── resolver.py           # Resolves bundles (copies model_params → ResolvedBundle)
├── workflow_models.py
└── ...
```

### 11.4 Per-Bundle LLM Parameters (`model_params`)

Each `AgentBundle` can specify **per-bundle LLM inference overrides** via the `model_params` field. These override the LLM profile defaults at inference time for that specific agent, enabling fine-grained control of generation behavior per agent in a workflow.

#### 11.4.1 Data Flow

```
AgentBundle.model_params
    ↓
BundleResolver.resolve() → ResolvedBundle.model_params
    ↓
WorkflowCompiler → ResolvedAgentConfig.model_params
    ↓
agent_node_factory() → extra_kwargs
    ↓
LLMService.generate(extra_kwargs=...)
    ↓
_generate_local / _generate_litellm / _generate_cloudflare
    (whitelist-filtered into request payload)
```

#### 11.4.2 Supported Parameters

Only the following keys are allowed through the whitelist in `LLMService`:

| Key | Type | Description |
|-----|------|-------------|
| `temperature` | float | Sampling temperature (0.0–2.0) — overrides both the dedicated param and profile default |
| `top_p` | float | Nucleus sampling threshold (0.0–1.0) |
| `top_k` | int | Top-K sampling |
| `frequency_penalty` | float | Frequency penalty (-2.0–2.0) |
| `presence_penalty` | float | Presence penalty (-2.0–2.0) |
| `seed` | int | Random seed for reproducible generation |
| `stop` | str \| list[str] | Stop sequences |

Any other keys in `model_params` are silently ignored at the LLM layer.

#### 11.4.3 AgentBundle Model

```python
class AgentBundle(BaseModel):
    # ... standard fields ...
    model_params: dict = Field(
        default_factory=dict,
        description="LLM inference overrides (temperature, top_p, "
                    "top_k, frequency_penalty, presence_penalty, etc.)",
    )
```

#### 11.4.4 ResolvedAgentConfig

```python
@dataclass
class ResolvedAgentConfig:
    # ... standard fields ...
    model_params: dict = field(default_factory=dict)
```

#### 11.4.5 Bundle Profile JSON Format

When defining bundle profiles (e.g., in `modules/agent-*/` or via import/export), the `model_params` field is optional:

```json
{
    "id": "my-bundle",
    "name": "Creative Strategist",
    "model_params": {
        "temperature": 0.9,
        "top_p": 0.95,
        "frequency_penalty": 0.3
    }
}
```

If omitted or empty (`{}`), the LLM profile defaults are used with no overrides.

#### 11.4.6 Persistence

- **Database**: Stored as JSON text in the `model_params_json` column of `agent_bundles` (migration V29)
- **Repository**: `save_bundle()` serializes via `json.dumps()`, `_row_to_bundle()` deserializes via `json.loads()`
- **Import/Export**: `bundle_io.py` serializes `model_params` in export and reads `model_params` on import

#### 11.4.7 Workflow Paths

Both workflow paths pass `model_params` through to `LLMService.generate()`:

- **Old workflow** (`nodes.py`): `agent["model_params"]` → `extra_kwargs=agent.get("model_params")`
- **New workflow** (`node_functions.py`): `resolved_config["model_params"]` → `agent_node_factory()` extracts `model_params` and passes as `extra_kwargs` to `generate()`

#### 11.4.8 Important Notes

- `generate_with_fallback()` does NOT pass `extra_kwargs` — fallback calls use profile defaults
- `_generate_a2a()` does NOT accept `extra_kwargs` — A2A protocol nodes cannot receive per-bundle overrides (no A2A bundles exist yet)
- The `temperature` parameter via `extra_kwargs` takes precedence over both the dedicated `temperature` parameter and the LLM profile default

### 11.5 Usage

Blueprints can be created via the frontend or API. The API endpoints are defined in `backend/api/routers/blueprints.py` (not shown). For detailed API reference, see Section 16.
## 11b. Module System

<!-- UPDATED -->

### 11b.1 Overview

Danwa uses an extensible module system that allows packaging and distributing agents, prompts, roles, tone systems, workflow templates, and LLM profiles as self-contained modules. Each module is a directory with a `manifest.json` metadata file and a profile file (YAML, JSON, or Markdown depending on module type).

### 11b.2 Recent Updates

- **Models (`models.py`)**: Updated module and dependency models.
- **Service (`service.py`)**: Enhanced module loading, validation, and dependency resolution.
- **Type Derivation (`type_derivation.py`)**: Automatic type inference for module components.
- **API Router (`modules.py`)**: Extended endpoints for module management.
- **Frontend**: `ModuleManager.svelte` and `ModulesView.svelte` for graphical module management.

### 11b.3 Module Structure

```
module/
├── manifest.json    # Metadata (id, name, type, version, dependencies)
└── profile.yaml     # Module content (agent, prompt, etc.)
```

### 11b.4 Module Types

...

### 11b.5 API Endpoints

... (existing content)
## 12. HITL (Human-in-the-Loop) System

### 12.1 Overview

The HITL system enables human interaction with running workflows, allowing users to:
- Query agents for clarification
- Provide feedback or corrections
- Interject at specific workflow points
- Monitor and control workflow execution

### 11.2 Architecture (`backend/workflow/hitl/`)

```
backend/workflow/hitl/
├── api.py              # HITL API endpoints
├── contracts.py        # HITL contracts (request/response models)
├── graph.py            # HITL graph management
├── nodes.py            # HITL workflow nodes
├── round_manager.py    # HITL round management
├── security.py         # HITL security (authentication/authorization)
├── state.py            # HITL state management
└── agent_query.py      # Agent query handling
```

### 11.3 Core Components

#### AgentQuery
Query agents for clarification:
- `query_id`: Unique query identifier
- `agent_id`: Target agent
- `question`: User question
- `response`: Agent response
- `status`: Query status (pending, answered, failed)

#### HITLNode
Workflow node for human interaction:
- `node_id`: Node identifier
- `node_type`: Node type (query, feedback, approval)
- `config`: Node configuration
- `state`: Node state

#### RoundManager
Manages HITL interaction rounds:
- `round_id`: Round identifier
- `session_id`: Workflow session
- `queries`: List of queries in round
- `status`: Round status

### 11.4 Security (`security.py`)

HITL security features:
- Authentication for HITL endpoints
- Authorization checks (project-based)
- Query validation and sanitization
- Rate limiting for agent queries

### 11.5 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/hitl/query` | Submit agent query |
| GET | `/api/v1/hitl/query/{id}` | Get query response |
| POST | `/api/v1/hitl/feedback` | Submit workflow feedback |
| GET | `/api/v1/hitl/round/{id}` | Get round status |
| POST | `/api/v1/hitl/interject` | Interject in workflow |

---

## 13. Input/Output Plugin System

### 13.1 Overview

The Input/Output plugin system provides extensible architecture for:
- **Input plugins**: Process various input sources (audio, text, files)
- **Output plugins**: Generate various output formats (audio, documents, reports)

### 12.2 Input Plugin Architecture (`backend/services/input/`)

```
backend/services/input/
├── base.py              # Base plugin interface
├── input_engine.py      # Input engine orchestration
├── input_job_store.py   # Input job storage
├── input_store.py       # Input storage
├── plugin_manifest.py   # Plugin manifest
├── registry.py          # Plugin registry
├── mcp_adapter.py       # MCP (Model Context Protocol) adapter
└── plugins/             # Input plugins
```

**Base plugin interface:**
```python
class InputPlugin(ABC):
    @abstractmethod
    async def process(self, config: dict) -> InputResult:
        """Process input and return result."""
        pass
    
    @classmethod
    def validate_config(cls, config: dict) -> BaseModel:
        """Validate plugin configuration."""
        pass
```

**Supported input types:**
- Text input
- Audio input (via STT)
- File upload
- API-based input

### 12.3 Output Plugin Architecture (`backend/services/output/`)

```
backend/services/output/
├── base.py              # Base plugin interface
├── registry.py          # Plugin registry
└── plugins/             # Output plugins
    ├── print_plugin.py           # Print plugin (DOCX/PDF/ODF)
    ├── tts_plugin.py             # TTS plugin
    ├── mimo_tts_renderer.py      # MIMO TTS renderer
    ├── edge_tts_renderer.py      # Edge TTS renderer
    ├── print_layout_engine.py    # Print layout engine
    ├── print_models.py           # Print models
    ├── tts_models.py             # TTS models
    ├── tts_script_engine.py      # TTS script engine
    ├── audio_helpers.py          # Audio helpers
    └── voice_store.py            # Voice store
```

**Base plugin interface:**
```python
class OutputPlugin(ABC):
    @abstractmethod
    async def render(self, artifact: DebateArtifact, config: dict) -> RenderResult:
        """Render artifact to output format."""
        pass
    
    @classmethod
    def validate_config(cls, config: dict) -> BaseModel:
        """Validate plugin configuration."""
        pass
```

**Output plugins:**

1. **Print Plugin** (`print_plugin.py`)
   - Generates DOCX, PDF, ODF reports
   - Supports custom layouts via Jinja2 templates
   - Multi-language support (German/English)
   - Audit trail inclusion

2. **TTS Plugin** (`tts_plugin.py`)
   - Text-to-Speech generation
   - Multiple renderers:
     - MIMO TTS (multi-modal)
     - Edge TTS (edge-based)
   - Voice store for voice profiles
   - Script engine for TTS scripts

### 12.4 Render Engine (`render_engine.py`)

Orchestrates render job lifecycle:

**Job lifecycle:**
```
queued → running → completed
                → failed
```

**Render job:**
```python
class RenderJob:
    session_id: str
    status: RenderJobStatus
    plugin_key: str
    config: dict
    artifact_snapshot_hash: str
    output_path: str | None
    error: str | None
```

### 12.5 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/input/compose` | Submit input job |
| GET | `/api/v1/input/jobs/{id}` | Get input job status |
| POST | `/api/v1/output/compose` | Submit output job |
| GET | `/api/v1/output/jobs/{id}` | Get output job status |
| GET | `/api/v1/output/plugins` | List available output plugins |
| GET | `/api/v1/input/plugins` | List available input plugins |

---


## 14a. Assistant System

### 14a.1 Overview

The Assistant System provides an interactive AI assistant that helps users with tasks such as answering questions, providing explanations, and assisting with workflow configuration. It is implemented as a modular service with dedicated API endpoints.

### 14a.2 Architecture

```
backend/
├── api/routers/assistant.py       # REST endpoints for chat and streaming
├── services/assistant_service.py  # Core assistant logic (LLM interaction)
└── services/assistant_tools.py    # Tool set (web search, DMS, code generation)
```

### 14a.3 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/assistant/chat` | Send a message and receive a response |
| POST | `/api/v1/assistant/stream` | Streaming response (SSE) |
| GET | `/api/v1/assistant/tools` | List available assistant tools |
| POST | `/api/v1/assistant/tool/execute` | Execute a specific tool directly |

### 14a.4 Configuration

The assistant uses the default LLM profile from the system settings. Tools can be enabled or disabled per session. The assistant memory and context settings can be adjusted in the Assistant section of the Application Settings.
## 14. Data Models & Schemas

### 14.0 Blueprint Models (`backend/blueprints/models.py`)

#### 14.0.1 AgentBundle

The `AgentBundle` is the composite model that ties LLM profile, role type, prompt, and tone together for a single agent in a workflow. It now supports per-bundle LLM inference overrides:

```python
class AgentBundle(BaseModel):
    id: str
    name: str
    description: str = ""
    llm_profile_id: str
    role_type_id: str
    role_definition_id: str | None = None
    prompt_template_id: str | None = None
    tone_profile_id: str | None = None
    persona_id: str | None = None
    composition: BundleComposition | None = None
    model_params: dict = Field(
        default_factory=dict,
        description="LLM inference overrides (temperature, top_p, "
                    "top_k, frequency_penalty, presence_penalty, etc.)",
    )
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
```

#### 14.0.2 ResolvedBundle

Produced by `BundleResolver.resolve()` — contains all referenced entities inline, including resolved LLM parameters:

```python
class ResolvedBundle(BaseModel):
    bundle_id: str
    bundle_name: str
    llm_profile: BlueprintLLMProfile
    role_type: RoleType
    role_definition: RoleDefinition | None = None
    prompt_template: PromptTemplate | None = None
    tone_profile: ToneProfile | None = None
    system_prompt: str = ""
    model_params: dict = Field(
        default_factory=dict,
        description="LLM inference overrides (temperature, top_p, etc.)",
    )
```

#### 14.0.3 ResolvedAgentConfig

Used by the `WorkflowCompiler` to carry resolved configuration to agent node functions:

```python
@dataclass
class ResolvedAgentConfig:
    node_id: str
    blueprint_id: str
    blueprint_name: str
    llm_profile_id: str
    llm_model: str
    role_definition_id: str
    role: str
    prompt_template_id: str | None = None
    role_type_name: str = ""
    role_type_icon: str = "👤"
    role_type_color: str = "#8b5cf6"
    default_max_rounds: int = 5
    default_consensus_threshold: float = 0.9
    argumentation_pattern: str = ""
    mode: str = ""
    system_prompt: str = ""
    model_params: dict = field(default_factory=dict)
```

### 14.1 Pydantic Schemas (`backend/models/schemas.py`)

#### 13.1.1 Enums

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

#### 13.1.2 Request Models

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
    a2a_agents: list[A2AAgentConfig] = Field(default_factory=list)
```

#### 13.1.2a A2A Schemas (`backend/a2a/schemas.py`)

```python
class TaskStatus(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

class A2APart(BaseModel):
    type: str = "text"
    text: str = ""

class A2AMessage(BaseModel):
    role: str
    parts: list[A2APart]

class A2ATask(BaseModel):
    id: str
    status: TaskStatus = TaskStatus.SUBMITTED
    message: A2AMessage | None = None
    result: str | None = None
    error: str | None = None
    debate_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

class A2AAgentConfig(BaseModel):
    url: str
    role: str = "external_reviewer"
    position: str = "after:moderator"
```

#### 13.1.3 Response Models

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

### 13.2 Profile Schemas (`backend/core/profiles.py`)

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

## 15. API Reference

### 15.1 Debate Endpoints

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

### 14.2 Profile Endpoints

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

### 14.3 DMS Endpoints

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

### 14.4 Configuration Endpoints

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

### 14.5 A2A Endpoints

#### GET /.well-known/agent.json
Agent Card discovery endpoint (A2A spec).

**Response** (200):
```json
{
    "name": "Danwa Debate Agent",
    "description": "Multi-agent debate system with A2A protocol support",
    "url": "http://localhost:8000",
    "version": "2.0.0",
    "capabilities": { "streaming": false },
    "skills": [
        {
            "id": "debate",
            "name": "Debate",
            "description": "Run a multi-agent debate on a given topic"
        }
    ]
}
```

#### POST /a2a
JSON-RPC 2.0 endpoint for A2A protocol methods.

**Methods**:

| Method | Description |
|--------|-------------|
| `tasks/send` | Create a new A2A task (starts a debate) |
| `tasks/get` | Get task status and result |
| `tasks/cancel` | Cancel a running task |

**Request** (`tasks/send`):
```json
{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/send",
    "params": {
        "id": "task-abc",
        "message": {
            "role": "user",
            "parts": [{ "type": "text", "text": "Should we adopt microservices?" }]
        }
    }
}
```

**Response**:
```json
{
    "jsonrpc": "2.0",
    "id": "1",
    "result": {
        "id": "task-abc",
        "status": { "state": "submitted" }
    }
}
```

---

## 16. Configuration

### 16.1 Environment Variables

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

### 15.2 YAML Configuration (`config/settings.yaml`)

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

### 15.3 Profile YAML Examples

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

## 17. A2A Protocol Integration

### 17.1 Overview

Danwa implements the [A2A (Agent-to-Agent) protocol](https://github.com/google/A2A) for interoperability with external AI agents. The integration supports two modes:

1. **Danwa as A2A Server** (incoming): External agents can create debates via JSON-RPC `tasks/send`
2. **Danwa as A2A Client** (outgoing): Danwa can invoke external agents as additional debate participants

### 16.2 Module Architecture (`backend/a2a/`)

```
backend/a2a/
├── __init__.py          # Module exports
├── schemas.py           # A2A data models (Task, Message, Part, TaskStatus)
├── config.py            # Loads config/a2a.json
├── agent_card.py        # Generates /.well-known/agent.json
├── task_manager.py      # SQLite-backed task persistence
├── server.py            # Handles incoming A2A tasks → creates Danwa debates
├── client.py            # Calls external A2A agents via httpx
├── node.py              # LangGraph node for A2A agent participation
└── router.py            # FastAPI router (Agent Card + JSON-RPC endpoint)
```

### 16.3 Configuration (`config/a2a.json`)

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

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | `bool` | Enable/disable A2A integration globally |
| `server.enabled` | `bool` | Enable the A2A server (accepts incoming tasks) |
| `server.path` | `string` | JSON-RPC endpoint path (default: `/a2a`) |
| `external_agents` | `string[]` | List of external agent URLs for outgoing calls |

### 16.4 Task Lifecycle

A2A tasks follow this state machine:

```
submitted → working → completed
                   → failed
                   → canceled
```

Tasks are persisted in SQLite (`data/a2a_tasks.db`) and survive server restarts.

### 16.5 Using A2A in Debates

Include `a2a_agents` in the debate creation request:

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

The external agent is invoked after the standard agents (strategist, critic, optimizer, moderator) complete their rounds. The `position` field controls when the agent participates:
- `after:moderator` — after all standard agents (default)
- `after:strategist` — after the strategist
- `before:critic` — before the critic

### 16.6 Architecture

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

### 16.7 Testing

A2A integration has comprehensive test coverage:

| Test Suite | File | Tests |
|-----------|------|-------|
| TaskManager | `tests/backend/test_a2a_task_manager.py` | 20 |
| A2A Client | `tests/backend/test_a2a_client.py` | 16 |
| A2A Workflow | `tests/backend/test_a2a_workflow.py` | 16 |
| A2A E2E | `tests/backend/test_a2a_e2e.py` | 30 |

**Total**: 82 A2A-specific tests covering task lifecycle, JSON-RPC compliance, client discovery, workflow integration, and E2E protocol compliance.

---

## 18. Development Guide

### 18.1 Prerequisites

- **Python 3.11+**
- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 18+** and npm (for frontend development)
- **LM Studio** (optional, for local LLMs)
- **SearXNG** (optional, for web search)

---

### 17.2 Quick Setup

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

### 17.3 Frontend Setup

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

### 17.4 Running the Application

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

### 17.5 Testing

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

### 17.6 Linting and Formatting

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

### 17.7 Project Dependencies (`pyproject.toml`)

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

## 19. Deployment

### 19.1 Production Build

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

### 18.2 Docker Deployment (Optional)

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

### 18.3 Scripts

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

## 20. Multi-User & Authentication System

> **Added in v2.2.0** — Note: Sections 20–30 document new features since v2.1.0. Existing section numbering (11–19) was not renumbered to avoid breaking cross-references.

Danwa now supports multi-user authentication with JWT-based access control and role-based authorization.

### 20.1 Authentication Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Token creation/validation | python-jose | JWT access and refresh tokens |
| Password hashing | passlib + bcrypt | Secure password storage |
| User storage | SQLite | `data/auth.db` |

### 20.2 User Model

```python
class User:
    id: str                    # UUID
    email: str                 # Unique login identifier
    display_name: str          # Human-readable name
    role: str                  # "admin" | "editor" | "viewer"
    tenant_id: str             # Associated tenant UUID
    hashed_password: str       # bcrypt hash
    created_at: datetime
    updated_at: datetime
```

### 20.3 UserStore

- **Backend**: `backend/persistence/user_store.py`
- **Database**: SQLite at `data/auth.db`
- **Table**: `users` with unique constraint on `email`

### 20.4 Auth Router

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Create new user account |
| `/api/v1/auth/login` | POST | Authenticate and receive tokens |
| `/api/v1/auth/refresh` | POST | Refresh access token |
| `/api/v1/auth/me` | GET | Get current user profile |
| `/api/v1/auth/password` | PUT | Change password |

### 20.5 Security Module

- **Location**: `backend/core/security.py`
- `create_access_token(data, expires_delta)` — JWT with configurable expiry
- `create_refresh_token(data)` — Long-lived refresh token
- `decode_token(token)` — Validates and decodes JWT
- Password hashing via `passlib CryptContext(schemes=["bcrypt"])`

### 20.6 Seed Admin

On first startup, the system auto-creates a default admin account:

| Field | Value |
|-------|-------|
| Email | `admin@danwa.local` |
| Password | `admin` (must be changed on first login) |
| Role | `admin` |

### 20.7 Auth Dependencies

- `get_current_user(request)` — FastAPI dependency that validates JWT from `Authorization: Bearer <token>` header
- `require_role(*roles)` — Dependency factory for role-based access control

### 20.8 Disabling Auth

For development, authentication can be disabled:

```bash
DANWA_AUTH_ENABLED=false
```

When disabled, all requests are treated as authenticated with a default admin user.

### 20.9 Configuration

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| Secret key | `JWT_SECRET_KEY` | (required in production) | HMAC key for JWT signing |
| Algorithm | `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| Access token TTL | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| Refresh token TTL | `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |

---

## 21. Multi-Tenant Architecture

> **Added in v2.2.0**

Danwa supports multi-tenant isolation with per-tenant data scoping, membership management, and quota enforcement.

### 21.1 Tenant Model

```python
class Tenant:
    id: str                    # UUID
    name: str                  # Display name
    plan: str                  # "free" | "pro" | "enterprise"
    quotas: dict               # Per-resource limits
    created_at: datetime
```

### 21.2 TenantStore

- **Location**: `backend/persistence/tenant_store.py`
- **Database**: SQLite at `data/auth.db`
- **Table**: `tenants`

### 21.3 Membership Model

```python
class Membership:
    tenant_id: str
    user_id: str
    role: str                  # "owner" | "admin" | "editor" | "viewer"
    invited_by: str | None
    joined_at: datetime
```

### 21.4 MembershipStore

- **Location**: `backend/persistence/membership_store.py`
- **Database**: SQLite at `data/auth.db`
- **Table**: `memberships` with composite key `(tenant_id, user_id)`

### 21.5 Tenant Scoping

- `get_active_tenant(request)` — FastAPI dependency extracting tenant from JWT or header
- `get_tenant_context(request)` — Returns full tenant + user context

### 21.6 Case Model

Cases replace the previous project concept and are tenant-scoped:

```python
class Case:
    id: str                    # UUID
    tenant_id: str             # Owning tenant
    name: str
    description: str
    created_at: datetime
```

### 21.7 CaseStore

- **Location**: `backend/persistence/case_store.py`
- **Storage**: JSON files at `data/tenants/{tid}/cases/{cid}/case.json`

### 21.8 Tag Model

Tags are tenant-global with a flat hierarchy (parent_id reserved for future tree structure):

```python
class Tag:
    id: str
    tenant_id: str
    name: str
    parent_id: str | None      # Reserved for future hierarchy
```

### 21.9 TagStore

- **Location**: `backend/persistence/tag_store.py`
- **Storage**: JSON at `data/tenants/{tid}/tags.json`

### 21.10 Case-Scoped API

All resources are scoped under tenant and case:

```
/api/v1/tenants/{tid}/cases/{cid}/debates/
/api/v1/tenants/{tid}/cases/{cid}/dms/
/api/v1/tenants/{tid}/cases/{cid}/workflows/
```

### 21.11 Quota Enforcement

Quotas are checked before resource creation:

| Check Function | Resource | Description |
|----------------|----------|-------------|
| `check_debate_quota(tenant_id)` | Debates | Limits concurrent/completed debates |
| `check_document_quota(tenant_id)` | Documents | Limits DMS document count |
| `check_project_quota(tenant_id)` | Cases | Limits active cases |

---

## 22. BYOK (Bring Your Own Key)

> **Added in v2.2.0**

Users can provide their own LLM API keys, overriding tenant or environment defaults.

### 22.1 UserKeyStore

- **Location**: `backend/persistence/user_key_store.py`
- **Database**: SQLite at `data/auth.db`
- **Table**: `user_keys` with columns: `user_id`, `provider`, `api_key` (encrypted)

### 22.2 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/user-keys` | GET | List user's stored API keys |
| `/api/v1/user-keys` | PUT | Create or update an API key |
| `/api/v1/user-keys/{provider}` | DELETE | Remove a stored API key |

### 22.3 Key Resolution Priority

The LLM service resolves API keys in this order:

1. **Profile api_key** — Set directly on the LLM profile (highest priority)
2. **User key** — Per-user key from `user_keys` table
3. **Environment variable** — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. (lowest priority)

### 22.4 Implementation

- `LLMService._resolve_api_key(profile, user_id)` — Centralizes key resolution logic
- Called transparently during LLM invocation

### 22.5 Frontend

- **Component**: `frontend/src/lib/components/BYOKManager.svelte`
- **Route**: `#/my-keys`
- Allows users to add, view, and remove API keys per provider

---

## 23. Transactional Drafting Workflow

> **Added in v2.2.0**

A specialized multi-phase workflow for structured document creation with iterative refinement.

### 23.1 Workflow Template

- **Location**: `templates/transactional_drafting.json`
- Defines the graph structure, nodes, edges, and approval gates

### 23.2 Specialized Nodes

| Node | Role | Description |
|------|------|-------------|
| **Builder** | Creator | Structured document creation with iterative refinement |
| **Pragmatist** | Evaluator | Practical evaluation and feasibility assessment |
| **Angel's Advocate** | Optimizer | Constructive improvement suggestions |
| **Moderator** | Coordinator | Facilitates discussion and manages flow |

### 23.3 Transactional Model

- **Location**: `backend/models/transactional.py`
- Defines data structures for transactional drafting stages, approval states, and document versions

### 23.4 Edge Types

| Edge | Description |
|------|-------------|
| `decision` | Conditional routing based on evaluation outcome |
| `validates` | Approval gate — requires explicit approval to proceed |
| `builds-upon` | Iterative refinement — feeds output back to builder |

### 23.5 Report Generator

- **Location**: `backend/workflow/report_generator.py`
- Generates structured reports from transactional drafting workflow results

### 23.6 Print Templates

- **Location**: `templates/print/transactional_drafting.html`
- HTML template for rendering transactional drafting reports as printable documents

---

## 24. Angel's Advocate Node

> **Added in v2.2.0**

A constructive counterpart to the Devil's Advocate, focused on identifying strengths and opportunities.

### 24.1 Implementation

- **Location**: `backend/workflow/nodes/angels_advocate_nodes.py`
- Constructive advocacy: identifies strengths, opportunities, and positive aspects of proposals

### 24.2 Factory Function

```python
angels_advocate_node_factory() → Callable
```

Creates an Angel's Advocate node instance configured with the current LLM profile and prompts.

### 24.3 Workflow Registration

- Registered as `"wf-angels-advocate"` in the workflow compiler
- Can be added to any custom workflow via the Blueprint editor

### 24.4 Output Model

- Uses `AngelsAdvocateOutput` from `backend/models/transactional.py`
- Structured output with strengths, opportunities, and recommendations

---

## 25. Kitsune Agent & Assistant Tools

> **Added in v2.2.0**

An AI assistant agent with tool-calling capabilities for system introspection and knowledge retrieval.

### 25.1 Tool Registry

- **Location**: `backend/services/assistant_tools.py`
- Central registry mapping tool names to callable functions

### 25.2 Available Tools (6 read-only)

| Tool | Description |
|------|-------------|
| `get_system_status` | System health and resource usage |
| `list_debates` | List all debates with metadata |
| `get_debate_details` | Full details of a specific debate |
| `get_llm_profiles` | Available LLM profile configurations |
| `get_modules` | Installed modules and their status |
| `search_knowledge_base` | Search the Kitsune knowledge base |

### 25.3 Tool Execution Loop

- **Location**: `AssistantService.send_message()`
- Maximum 5 tool-call iterations per user message
- Implements OpenAI Function Calling protocol via litellm
- Each iteration: LLM generates tool calls → tools execute → results fed back to LLM

### 25.4 GenerationResult

- Extended with `tool_calls: list[ToolCall]` field
- Tracks which tools were called and their results

### 25.5 Knowledge Base

- **Location**: `config/prompts/kitsune/knowledge.txt`
- Auto-generated from system state (modules, profiles, capabilities)
- Updated on startup and after configuration changes

### 25.6 Prompt Translation

- Per-language prompt translation via `TranslationService`
- Kitsune responds in the user's preferred language

### 25.7 Frontend Integration

- Tool-call messages rendered in `AssistantMessageBubble.svelte`
- Shows tool name, arguments, and results in a collapsible UI

---

## 26. Task Queue & Concurrency

> **Added in v2.2.0**

Optional Celery + Redis integration for parallel debate execution and background task processing.

### 26.1 Architecture

```
┌─────────────┐     ┌───────────┐     ┌─────────────────┐
│  FastAPI     │────▶│  Redis    │────▶│  Celery Worker  │
│  (dispatch)  │     │  (broker) │     │  (debate exec)  │
└─────────────┘     └───────────┘     └─────────────────┘
```

### 26.2 Task Dispatch Layer

- **Location**: `backend/tasks/dispatch.py`
- Abstracts task submission: falls back to synchronous execution when Celery is disabled

### 26.3 Celery App Factory

- **Location**: `backend/tasks/celery_app.py`
- Lazy initialization — Celery is only imported when enabled
- Returns `None` when `CELERY_ENABLED=false`

### 26.4 Debate Task

- **Location**: `backend/tasks/debate.py`
- `execute_debate_task(debate_id, config)` — Runs a full debate workflow in a Celery worker

### 26.5 State Backends

| Backend | Description |
|---------|-------------|
| `InMemoryWorkflowState` | Default, single-process state storage |
| `RedisWorkflowState` | Redis-backed state for multi-worker setups |

### 26.6 Configuration

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| Redis URL | `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| Celery enabled | `CELERY_ENABLED` | `false` | Enable task queue |
| Worker concurrency | `CELERY_WORKER_CONCURRENCY` | `4` | Parallel workers |
| Max concurrent debates | `MAX_CONCURRENT_DEBATES_GLOBAL` | `10` | Global debate limit |

### 26.7 Docker

Start Celery worker with the dedicated profile:

```bash
docker compose --profile celery up
```

---

## 27. Observability & Monitoring

> **Added in v2.2.0**

Structured logging, request tracing, and Prometheus metrics for production observability.

### 27.1 Structured Logging

- **Location**: `backend/core/logging.py`
- Uses `structlog` for structured log output
- **Production**: JSON-formatted logs (machine-readable)
- **Development**: Console-formatted logs (human-readable with colors)

### 27.2 X-Request-ID Middleware

- Generates a unique `X-Request-ID` for each incoming request
- Propagates existing `X-Request-ID` headers from upstream proxies
- Included in all log entries and response headers for request tracing

### 27.3 Prometheus Metrics

- **Endpoint**: `GET /metrics`
- **Library**: `prometheus-fastapi-instrumentator`

### 27.4 Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests by method, status, endpoint |
| `debate_duration_seconds` | Histogram | Debate execution duration |
| `llm_call_duration_seconds` | Histogram | Individual LLM call latency |
| `active_debates_gauge` | Gauge | Currently running debates |

### 27.5 Prometheus Configuration

- **Location**: `deploy/prometheus.yml`
- Pre-configured scrape targets for the Danwa backend

---

## 28. Rate Limiting

> **Added in v2.2.0**

API rate limiting via `slowapi` with support for Redis or in-memory backends.

### 28.1 Integration

- **Library**: `slowapi` (Flask-Limiter port for FastAPI)
- **Backend**: Redis (when available) or in-memory fallback

### 28.2 Default Limits

| Scope | Limit | Description |
|-------|-------|-------------|
| Global | 60/minute per IP | Default for all endpoints |
| Debate creation | 10/hour | Debate API endpoints |
| File upload | 20/hour | DMS upload endpoints |
| Analysis | 5/hour | Document analysis endpoints |

### 28.3 Configuration

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| Enabled | `RATE_LIMIT_ENABLED` | `true` | Enable/disable rate limiting |
| Default limit | `RATE_LIMIT_DEFAULT` | `60/minute` | Global default |
| Debate limit | `RATE_LIMIT_DEBATE` | `10/hour` | Debate endpoints |
| Upload limit | `RATE_LIMIT_UPLOAD` | `20/hour` | Upload endpoints |
| Analysis limit | `RATE_LIMIT_ANALYSIS` | `5/hour` | Analysis endpoints |

### 28.4 Error Response

When rate limited, the API returns HTTP 429 with rate limit details:

```json
{
  "error": "Rate limit exceeded",
  "detail": "10 per 1 hour",
  "retry_after": 3421
}
```

---

## 29. Docker Deployment

> **Added in v2.2.0** — Replaces the hypothetical Docker examples from section 19.

### 29.1 Dockerfile.backend

```
Base: Python 3.12-slim
System deps: tesseract-ocr, espeak-ng, ffmpeg
Python deps: installed via uv from pyproject.toml
WSGI: gunicorn with uvicorn workers
Port: 8000
```

### 29.2 Dockerfile.frontend

```
Stage 1: Node 22 — npm install + npm run build
Stage 2: Nginx alpine — serves built SPA
Port: 80
```

### 29.3 docker-compose.yml

| Service | Description | Ports |
|---------|-------------|-------|
| `backend` | FastAPI application | 8000 |
| `frontend` | Nginx serving Svelte SPA | 80 |
| `redis` | Redis for caching/task queue | 6379 |
| `celery-worker` | Optional Celery worker (profile: celery) | — |

### 29.4 Nginx Configuration

- **Location**: `deploy/nginx.conf`
- TLS termination
- API proxy to backend (`/api/` → `backend:8000`)
- SSE support (`proxy_buffering off` for `/api/v1/debate/stream`)
- Security headers (CSP, HSTS, X-Frame-Options)

### 29.5 Environment Template

- **Location**: `deploy/.env.example`
- Required variables: `JWT_SECRET_KEY`, `REDIS_URL`, `CORS_ORIGINS`

### 29.6 Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `docker-build` | `docker compose build` | Build all images |
| `docker-up` | `docker compose up -d` | Start all services |
| `docker-down` | `docker compose down` | Stop all services |
| `docker-logs` | `docker compose logs -f` | Tail service logs |
| `docker-up-celery` | `docker compose --profile celery up -d` | Start with Celery worker |

### 29.7 Health Check

- **Endpoint**: `GET /health`
- Checks:
  - SQLite database connectivity
  - Redis connectivity (if configured)
  - Auth database connectivity
- Returns `200 OK` with component statuses, or `503` on failure

---

## 30. CI/CD Pipeline

> **Added in v2.2.0**

Automated test, build, and deploy pipeline via GitHub Actions.

### 30.1 Workflow

- **Location**: `.github/workflows/deploy.yml`
- **Stages**: test → build → deploy

| Stage | Description |
|-------|-------------|
| **Test** | Run pytest, ruff, frontend lint + tests |
| **Build** | Build Docker images with Buildx caching |
| **Deploy** | SSH deploy to production server |

### 30.2 Docker Buildx

- Uses GitHub Actions cache for Docker layer caching
- Multi-platform build support

### 30.3 Deployment

- SSH into production server
- Pull latest images
- Restart services via docker compose

### 30.4 Required Secrets

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Production server hostname/IP |
| `DEPLOY_USER` | SSH username |
| `DEPLOY_KEY` | SSH private key |
| `JWT_SECRET_KEY` | JWT signing secret for production |

---

## 16. Missing Links (Features Implemented but not UI-Exposed)

> **What are "Missing Links"?** These are features fully implemented in the backend and/or frontend API client, but **not yet accessible through the user interface**. Users cannot use these features without direct API calls or code changes.
>
> **Last audited**: 2026-05-17 — full codebase scan of all backend routers, frontend API clients, and UI views.
>
> **Recently exposed (wired up in prior sprints)**: The following features were previously listed as missing but have since been wired into the UI:
> - **Report Generation (async DOCX/PDF/ODF)** — download 500 error fixed. Now functional via "Bericht erstellen" in debate view.
> - **Application Settings Tab** — `getSettings()`/`updateSettings()` called in `ConfigView.svelte` + `ProjectSettings.svelte`
> - **Manual RAG Search** — `searchRAG()` wired in `DocumentsView.svelte`
> - **A2A Agent Discovery** — `discoverA2A()` wired + `A2ACapabilities.svelte` displayed in `DebateView.svelte`
> - **Session Soft-Delete / Restore** — `softDeleteSession()`/`restoreSession()` wired in `ArchiveView.svelte`
> - **Workflow-Exec Controls** — `pauseWorkflow()`/`resumeWorkflow()`/`cancelWorkflow()` wired in `ExecutionPanel.svelte`
> - **Workflow Interjection** — interjection UI in `ExecutionPanel.svelte`
> - **Workflow State Query** — `getWorkflowState()` wired in `ExecutionPanel.svelte`
> - **Workflow-Exec SSE Stream** — `createWorkflowSSE()` wired in `ExecutionPanel.svelte`
> - **Blueprint Compile & Clone** — `compileWorkflow()`/`cloneWorkflow()` wired in `BlueprintCanvasView.svelte`
> - **Canvas Layout CRUD** — `loadLayout()`/`saveLayout()`/`deleteLayout()` wired in Palette + BlueprintCanvas
> - **Role Types CRUD** — `createRoleType()`/`updateRoleType()`/`deleteRoleType()`/`listRoleTypes()` wired in `RoleTypeForm.svelte`, `RoleDefinitionForm.svelte`, and `ConfigView.svelte`
> - **Language API** — `setLanguage()` wired in `LanguageSwitcher.svelte`
> - **Modules Management** — `ModulesView.svelte` with full install/uninstall/validate UI
> - **Optimization Proposals** — `ProposalsView.svelte` with approve/reject HITL workflow
> - **Translation Dashboard** — Full i18n management UI with LLM bulk translation
> - **System Management** — `ManageView.svelte` for system-level operations
> - **Sidebar Restructuring** — Organized into RUN, BUILD, Configuration, Evolve sections

### 16.1 Legacy Session History — LOW IMPACT

**Status**: Legacy backend router exists, no frontend integration

The `backend/api/routers/sessions.py` router provides legacy endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sessions/` | GET | List debate sessions (with filters) |
| `/api/v1/sessions/{id}` | GET | Get single session |
| `/api/v1/sessions/{id}` | DELETE | Delete session |
| `/api/v1/sessions/{id}/trace` | GET | Get audit trace |
| `/api/v1/sessions/{id}/report/{fmt}` | GET | Download report (sync) |

**What's missing**: No frontend API functions and no UI for session history, trace download, or session deletion through this legacy router.

**Note**: This is a **legacy** router. The newer `workflow_exec.py` and `workflow_reports.py` routers supersede most of these endpoints and already have UI integration.

---

### 16.2 Report SSE Progress Stream — LOW IMPACT

**Status**: Backend + API client function exist, not consumed in any view

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/sessions/{session_id}/report/stream` | GET | SSE progress stream for report generation |

**API Client** (`frontend/src/lib/api.js`):
- `createReportSSE(sessionId)` — exists but **never called** from any `.svelte` view

**What's missing**: No frontend view consumes the report generation SSE stream for progress indication.

---

### 16.3 Project-Level Settings Override — LOW IMPACT

**Status**: Backend exists, no frontend API client or UI

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/config/settings/project/{id}` | GET | Get project-overridden settings |

**What's missing**: No frontend API function or UI for project-level settings overrides. i18n string exists (`projects.configHint`) but no implementation.

---

### 16.4 Summary Table

| # | Feature | Backend | API Client | UI | Status |
|--:|---------|---------|------------|-----|--------|
| 1 | Legacy Session History | ✅ | ❌ Missing | ❌ Missing | **Not exposed** |
| 2 | Report SSE Progress Stream | ✅ | ✅ Exists | ❌ Missing | **Not exposed** |
| 3 | Project-Level Settings Override | ✅ | ❌ Missing | ❌ Missing | **Not exposed** |

---

### 16.5 Recommendations (Priority Order)

1. **Legacy Session History** — Add frontend API functions and a session list view for the legacy `sessions.py` router, or document it as fully superseded.
2. **Report SSE Progress Stream** — Wire `createReportSSE()` into the debate view's report download flow for real-time progress feedback.
3. **Project-Level Settings Override** — Add API client function and wire into `ProjectSettings.svelte`.

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

*Documentation generated for Danwa (Debate-Agent) v2.2.0 | Last updated: 2026-06-01*