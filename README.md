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
│   ├── core/                    # Business logic
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
│   ├── dms/                   # Document Management System
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite schema
│   │   ├── config.py          # DMS configuration
│   │   ├── project_manager.py # Project CRUD
│   │   ├── document_processor.py # PaddleOCR + parsers
│   │   ├── chunker.py        # Text chunking (512 tokens)
│   │   ├── rag_pipeline.py   # RAG pipeline
│   │   ├── vector_store.py   # ChromaDB interface
│   │   ├── metadata_index.py # Fast metadata filtering
│   │   ├── hybrid_retriever.py # BM25 + Vector + Re-ranking
│   │   ├── rag_context_formatter.py # RAG context formatting
│   │   ├── dms.py           # High-level DMS API
│   │   └── dms_memory.py     # Manual RAG context
├── debate_engine/               # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── api/routers/             # debate, audit, config, dms, sessions
│   ├── workflow/                # LangGraph state machine
│   ├── persistence/             # SQLite audit trail
│   └── models/                  # Pydantic schemas
├── frontend/                    # Svelte 5 SPA
│   ├── src/views/               # Dashboard, Debate, Audit, Config
│   └── src/components/          # Reusable UI components
├── config/                       # Configuration files
│   ├── llm_profiles.yaml       # LLM backend definitions
│   ├── settings.yaml           # App settings (search, privacy)
│   ├── prompt_variants.yaml    # Prompt variant mappings
│   └── prompts/                # Agent prompt templates
│       ├── strategist.md
│       ├── critic.md
│       ├── optimizer.md
│       └── moderator.md
├── tests/                        # Pytest test suite
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

### LLM Profiles (`config/llm_profiles.yaml`)

```yaml
profiles:
  local_qwen:
    model: "qwen2.5-7b"
    base_url: "http://localhost:1234/v1"
    api_key_env: "LM_STUDIO_KEY"
  cloud_openrouter:
    model: "anthropic/claude-3-5-sonnet"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_KEY"
```

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

*Debate-Agent v0.1.0 | Built with Chainlit + LiteLLM + ChromaDB*
