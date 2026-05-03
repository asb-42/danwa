# Debate-Agent

Auditable multi-agent debate workflow system that uses AI agents to analyze, critique, and optimize arguments through structured deliberation. Now with **DMS (Document Management System)** featuring **PaddleOCR** integration and **RAG (Retrieval-Augmented Generation)** pipeline.

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

Open `http://localhost:7860` in your browser.

No systemd required - runs on-demand via simple scripts.

## How It Works

Four specialized AI agents collaborate in a structured debate:

```
Input → [Strategist] → [Critic] → [Optimizer] → [Moderator]
         ↓              ↓             ↓              ↓
      Strategy      Critique      Synthesis      Consensus (0.0-1.0)
```

1. **Strategist** - Develops logical argumentation structure
2. **Critic** - Identifies weaknesses and risks (Devil's Advocate)
3. **Optimizer** - Synthesizes strategy and criticism into refined output
4. **Moderator** - Evaluates consensus and scores the result

The debate runs for configurable rounds (1-5) and stops early when consensus threshold is met.

## Features

- **Multi-Agent Deliberation** - Four specialized agents produce well-reasoned analysis
- **Flexible LLM Backend** - Local (LM Studio) or cloud (OpenRouter) via LiteLLM
- **Document Analysis** - Upload PDF, DOCX, ODT, ODS, ODP files
- **Web Fact-Checking** - Optional validation via SearXNG integration
- **Semantic Memory** - ChromaDB-powered precedent retrieval from past debates
- **Audit Trail** - Complete JSONL trace logs for reproducibility
- **Report Generation** - Export results as DOCX or PDF
- **Privacy Protection** - PII redaction (email, IP, phone) and configurable data retention
- **Session Management** - SQLite-backed sessions with dashboard UI
- **Document Management System (DMS)** - Project-wise document organization with SQLite
- **PaddleOCR Integration** - OCR for scanned PDFs alongside existing parsers
- **RAG Pipeline** - Automatic and manual document retrieval for debate context
- **Hybrid Retrieval** - BM25 + Vector search + Re-ranking
- **DMS Dashboard** - Project and document management UI

## Document Management System (DMS)

The DMS module provides project-wise document management with advanced retrieval capabilities:

- **Project-wise Document Management** - Organize documents into projects with SQLite-backed metadata
- **PaddleOCR Integration** - Process scanned PDFs and images using PaddleOCR for text extraction
- **RAG (Retrieval-Augmented Generation) Pipeline** - Enhance debates with relevant document context
- **Hybrid Retrieval** - Combine BM25 keyword search, vector similarity, and re-ranking for optimal results
- **Separate ChromaDB Collection** - Isolated vector storage for document embeddings
- **Integration** - Seamless integration with FastAPI/Svelte UI and core debate engine

## Technology Stack

| Component | Technology |
|-----------|-------------|
| Language | Python 3.11+ |
| UI Framework | [Svelte 5](https://svelte.dev) + [Tailwind CSS](https://tailwindcss.com) |
| Backend Framework | [FastAPI](https://fastapi.tiangolo.com) + [LangGraph](https://langchain-ai.github.io/langgraph/) |
| LLM Integration | [LiteLLM](https://litellm.ai) |
| Vector Database | [ChromaDB](https://www.trychroma.com) |
| Web Search | SearXNG / DuckDuckGo |
| Document Parsing | pdfplumber, pypdf, python-docx, odfpy |
| Report Generation | python-docx, [WeasyPrint](https://weasyprint.org) |
| Database | SQLite |
| DMS Module | Custom (SQLite + ChromaDB + PaddleOCR) |
| OCR Engine | [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| Package Manager | [uv](https://github.com/astral-sh/uv) |

## Project Structure

```
danwa/
├── src/
│   ├── core/                    # Business logic (legacy, being migrated)
│   │   ├── debate_engine.py     # Main orchestration
│   │   ├── llm_router.py        # LLM provider routing
│   │   ├── memory.py            # ChromaDB vector storage
│   │   ├── session_db.py        # SQLite persistence
│   │   ├── prompt_manager.py    # Prompt variant management
│   │   ├── privacy.py           # PII redaction & retention
│   │   └── trace_logger.py      # JSONL audit logs
│   ├── tools/                   # External integrations
│   │   ├── doc_parser.py       # Document parsing
│   │   ├── report_generator.py  # DOCX/PDF generation
│   │   └── web_search.py       # SearXNG search
│   └── dms/                   # Document Management System
│       ├── database.py        # SQLite schema
│       ├── project_manager.py # Project CRUD
│       ├── document_processor.py # PaddleOCR + parsers
│       ├── chunker.py        # Text chunking (512 tokens)
│       ├── rag_pipeline.py   # RAG pipeline
│       ├── vector_store.py   # ChromaDB interface
│       ├── hybrid_retriever.py # BM25 + Vector + Re-ranking
│       └── dms.py           # High-level DMS API
├── backend/                     # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   └── profiles.py          # Profile schemas (LLM, Agent, Prompt)
│   ├── services/
│   │   ├── profile_service.py   # YAML profile CRUD + validation
│   │   ├── prompt_service.py    # Prompt templates with hot-reload
│   │   └── llm_service.py       # LiteLLM integration
│   ├── api/routers/             # debate, audit, config, dms, sessions, profiles
│   ├── workflow/                # LangGraph state machine
│   ├── persistence/             # SQLite audit trail
│   ├── repositories/            # SQLite repos (profile_repo)
│   └── models/                  # Pydantic schemas
├── profiles/                    # Profile configuration (YAML + Markdown)
│   ├── llm/                     # LLM profile definitions
│   │   ├── openrouter-claude.yaml
│   │   ├── openrouter-gpt4.yaml
│   │   └── local-qwen.yaml
│   ├── agents/                  # Agent persona definitions
│   │   ├── strategist-default.yaml
│   │   ├── critic-default.yaml
│   │   ├── optimizer-default.yaml
│   │   └── moderator-default.yaml
│   └── prompts/                 # Prompt templates (Markdown)
│       ├── default/             # Default prompt variant
│       │   ├── strategist.md
│       │   ├── critic.md
│       │   ├── optimizer.md
│       │   └── moderator.md
│       └── variants/            # Named prompt variants
│           ├── kantian/
│           └── steiner/
├── frontend/                    # Svelte 5 SPA
│   ├── src/views/               # Dashboard, Debate, Audit, Config
│   └── src/components/          # Reusable UI components
├── config/                       # Application settings
│   └── settings.yaml           # App settings (search, privacy, DMS, UI)
├── tests/                        # Pytest test suite
│   └── backend/                 # Backend-specific tests
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
├── memory/                       # Runtime data
│   ├── debates.db              # SQLite database
│   └── chroma_db/              # ChromaDB vector store
├── logs/                         # Debate trace logs (JSONL)
├── reports/                      # Generated reports
├── pyproject.toml               # Project metadata & dependencies
├── Makefile                     # Dev workflow (install, test, lint, format)
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
provider: openrouter          # openrouter | openai | anthropic | local
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

Default personas: `strategist-default`, `critic-default`, `optimizer-default`, `moderator-default`. Example personas with `-example` suffix are also provided.

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
search:
  engine: "searxng"
  url: "http://127.0.0.1:8080"
  max_results: 5

privacy:
  strict_mode: false          # Block external calls
  redact_traces: true         # PII redaction in logs
  retention_days: 90          # Auto-cleanup old data
```

## Development

```bash
# Run tests
make test
# or
uv run pytest tests/ -v

# Lint and format
make lint
make format
# or
uv run ruff check .
uv run ruff format .

# Run CI checks (lint + test)
make check
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- (Optional) [LM Studio](https://lmstudio.ai) for local LLMs
- (Optional) [SearXNG](https://searxng.org) for web search

## Documentation

Full user manual available at `docs/user_manual.md` - covers all features, configuration options, privacy settings, and troubleshooting.

## License

[Add your license here]

---

*Debate-Agent v2.0.0 | Built with FastAPI + LangGraph + LiteLLM + Svelte*
