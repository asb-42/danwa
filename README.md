# Debate-Agent

Auditable multi-agent debate workflow system that uses AI agents to analyze, critique, and optimize arguments through structured deliberation.

## Quick Start

```bash
# Quick setup (installs uv, creates venv, installs deps)
bash setup.sh

# Start the application
uv run chainlit run src/ui/chainlit_app.py --port 7860
```

Open `http://localhost:7860` in your browser.

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

## Technology Stack

| Component | Technology |
|-----------|-------------|
| Language | Python 3.11+ |
| UI Framework | [Chainlit](https://chainlit.io) |
| LLM Integration | [LiteLLM](https://litellm.ai) |
| Vector Database | [ChromaDB](https://www.trychroma.com) |
| Web Search | SearXNG / DuckDuckGo |
| Document Parsing | pdfplumber, pypdf, python-docx, odfpy |
| Report Generation | python-docx, [WeasyPrint](https://weasyprint.org) |
| Database | SQLite |
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
│   └── ui/                      # Presentation layer
│       ├── chainlit_app.py      # Main entry point
│       └── dashboard.py         # Session management UI
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
