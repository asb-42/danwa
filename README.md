# Danwa (だんわ)

**Auditable multi-agent debate platform.**

Danwa is an AI-powered deliberation system where multiple agents debate topics in configurable rounds, producing structured reports with full audit trails. Built with FastAPI (Python) and Svelte 5.

## Quick Start

```bash
bash setup.sh                    # install dependencies
bash manage.sh start             # start backend + auto-detect sibling frontends
bash manage.sh start fe          # start frontend only on http://localhost:5173
```

See [INSTALL.md](INSTALL.md) for detailed instructions.

## How It Works

Four AI agents — **Strategist**, **Critic**, **Optimizer**, and **Moderator** — are orchestrated by a LangGraph state machine. They debate in configurable rounds (1–20) with early stopping on consensus. Each agent can use a different LLM provider and argumentation style.

## Architecture

This repository is part of a multi-repo setup:

| Repository | Role | Port |
|------------|------|------|
| **danwa** (this repo) | End-user frontend (Svelte 5) | 5173 |
| **danwa-core** | FastAPI backend + orchestration | 8000 |
| **danwa-studio** | Admin/developer frontend | 5174 |
| **danwa-modules** | Shared modules, agents, workflows, translations | — |

### Sibling Setup

```
parent-dir/
  danwa-core/      # Backend
  danwa/           # User frontend (this repo)
  danwa-studio/    # Admin frontend
```

```bash
cd danwa-core && bash setup.sh && bash manage.sh start
```

This starts the backend and auto-detects sibling frontends.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Svelte 5, Vite 5, Tailwind CSS 3, @xyflow/svelte, Cytoscape.js |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| AI/LLM | LiteLLM, LangGraph, ChromaDB, tiktoken |
| Auth | JWT (python-jose), bcrypt, RBAC |
| Documents | PDFPlumber, python-docx, odfpy, PaddleOCR (optional) |
| Search | SearXNG, DuckDuckGo |
| Database | SQLite |
| Deployment | Docker Compose, Nginx, TLS |

## Key Features

- **Multi-agent deliberation** with configurable roles and argumentation patterns
- **Interactive mode** — real-time human-in-the-loop debates with action templates
- **Flexible LLM backend** via LiteLLM (OpenRouter, Anthropic, DeepSeek, Xiaomi, and more)
- **Utility LLM** — configurable background LLM for title generation, translations, and assistant
- **Document analysis** — PDF, DOCX, ODT, ODS, OCR (PaddleOCR/Tesseract/EasyOCR)
- **RAG pipeline** — hybrid retrieval (BM25 + vector search + re-ranking) via ChromaDB
- **Real-time streaming** via Server-Sent Events (SSE)
- **Audit trail** — every debate action logged in JSONL format
- **Report generation** — DOCX/PDF output with WeasyPrint
- **Web fact-checking** via SearXNG or DuckDuckGo
- **Multi-tenant** with JWT authentication and role-based access
- **i18n** — 14 languages (EN, DE, FR, ES, IT, PT, RU, ZH, JA, KO, SV, EL, AR, HE)
- **Module system** — extensible agent cores, workflows, LLM profiles, tone profiles (via `danwa-modules`)
- **Blueprint canvas** — visual workflow editor
- **A2A Protocol** — agent-to-agent discovery and communication
- **Input/Output composers** — modular pipeline for processing inputs and generating outputs
- **TTS** — text-to-speech via Edge TTS or custom renderers
- **Tone profiles** — adjust agent communication style per debate
- **Dark mode** — full dark theme support across all views
- **Backup** — automatic on shutdown, configurable retention
- **Prometheus metrics** and **structlog** for monitoring

## Project Structure

```
danwa/
├── backend/          # FastAPI application (routers, services, models)
├── frontend/         # Svelte 5 end-user frontend
│   └── src/
│       ├── views/    # 16 page-level views
│       ├── components/  # UI components (debate, interactive, inbox, etc.)
│       └── lib/      # API clients, stores, i18n, SSE, workflow logic
├── src/              # Shared Python core (legacy) — debate engine, DMS, LLM router
├── modules/          # Local module definitions
├── scripts/          # Shell management scripts (libdanwa.sh) and utilities
├── config/           # Application configuration and prompts
├── data/             # Database, DMS storage
├── tests/            # Backend (pytest) and script (BATS) tests
├── deploy/           # Docker Compose, deployment configs
├── docs/             # ADRs, architecture documentation
├── plans/            # Architecture plans and roadmaps
├── schemas/          # JSON schemas for module validation
├── templates/        # Workflow templates and document templates
├── profiles/         # User-facing profile configurations
├── repo-templates/   # Canonical setup/manage templates for all repos
├── skills/           # OpenCode skill definitions
├── manage.sh         # Management CLI (start, stop, status, dashboard)
├── setup.sh          # Dependency installer
└── pyproject.toml    # Python dependencies (uv)
```

## Docker Deployment

```bash
docker compose up -d                     # full stack
docker compose --profile celery up -d    # with Celery worker
docker compose up redis -d               # Redis only (local dev)
```

See `deploy/.env.example` for required environment variables.

## Configuration

Settings are loaded from environment variables (prefix `DANWA_*`), the `.env` file, and `config/settings.yaml`. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DANWA_DB_PATH` | `data/audit.db` | SQLite database path |
| `DANWA_JWT_SECRET_KEY` | — | **Required** for auth in production |
| `DANWA_AUTH_ENABLED` | `false` | Enable JWT authentication |
| `DANWA_RATE_LIMIT_DEFAULT` | `60/minute` | API rate limit |
| `DANWA_DEBUG` | `false` | Debug mode |

## Testing

```bash
# Backend
uv run pytest tests/

# Frontend (unit)
cd frontend && npm run test:unit

# Frontend (E2E)
cd frontend && npm run test:e2e

# Linting
uv run ruff check backend/
uv run ruff format backend/
```

## Useful Commands

```bash
bash manage.sh status        # overview of running components
bash manage.sh status --json # machine-readable status
bash manage.sh dashboard     # interactive dashboard
bash manage.sh logs fe       # tail frontend logs
bash manage.sh stop          # stop all components
```

## License

**GNU Affero General Public License v3.0** (AGPL-3.0). See [LICENSE](LICENSE) and <https://www.gnu.org/licenses/agpl-3.0.html>.

## Links

- [INSTALL.md](INSTALL.md) — detailed installation guide
- [CHANGELOG.md](CHANGELOG.md) — version history
- [API Documentation](http://localhost:8000/docs) — Swagger UI (when backend is running)
