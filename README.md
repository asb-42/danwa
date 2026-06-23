# Danwa (だんわ)

**Auditable multi-agent debate platform.**

Danwa is an AI-powered deliberation system where multiple agents debate topics in configurable rounds, producing structured reports with full audit trails. Built with FastAPI (Python) and Svelte 5.

## Quick Start

```bash
bash setup.sh                    # install dependencies
bash manage.sh start fe          # start frontend on http://localhost:5173
```

For the full experience (backend + frontend), see the [sibling setup](#sibling-setup) below or refer to [`INSTALL.md`](INSTALL.md) for detailed instructions.

## How It Works

Four AI agents -- **Strategist**, **Critic**, **Optimizer**, and **Moderator** -- are orchestrated by a LangGraph state machine. They debate in configurable rounds (1-20) with early stopping on consensus. Each agent can use a different LLM provider and argumentation style.

## Architecture

This repository is part of a multi-repo setup:

| Repository | Role | Port |
|------------|------|------|
| **danwa** (this repo) | User-facing frontend (Svelte 5) | 5173 |
| **danwa-core** | FastAPI backend + orchestration | 7860/8000 |
| **danwa-studio** | Admin/developer frontend | 5174 |
| **danwa-modules** | Shared assets, agents, workflows, language packs | -- |

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
- **Flexible LLM backend** via LiteLLM (OpenRouter, Anthropic, DeepSeek, Xiaomi, and more)
- **Document analysis** -- PDF, DOCX, ODT, ODS, OCR (PaddleOCR/Tesseract/EasyOCR)
- **RAG pipeline** -- hybrid retrieval (BM25 + vector search + re-ranking) via ChromaDB
- **Real-time streaming** via Server-Sent Events (SSE)
- **Audit trail** -- every debate action logged in JSONL format
- **Report generation** -- DOCX/PDF output with WeasyPrint
- **Web fact-checking** via SearXNG or DuckDuckGo
- **Multi-tenant** with JWT authentication and role-based access
- **i18n** -- 14 languages (EN, DE, FR, ES, IT, PT, RU, ZH, JA, KO, SV, EL, AR, HE)
- **Module system** -- extensible agent cores, workflows, LLM profiles, tone profiles, prompt modifiers
- **Blueprint canvas** -- visual workflow editor
- **A2A Protocol** -- agent-to-agent discovery and communication
- **HITL** (Human-in-the-Loop) -- pause, inject, and interact during debates
- **Input/Output composers** -- modular pipeline for processing inputs and generating outputs
- **TTS** -- text-to-speech via Edge TTS or custom renderers
- **Tone profiles** -- adjust agent communication style per debate
- **Backup** -- automatic on shutdown, configurable retention
- **Prometheus metrics** and **structlog** for monitoring

## Module System

Danwa ships with a modular architecture. Modules live in `modules/` and are categorized by type:

| Category | Description |
|----------|-------------|
| `agent-cores/` | Agent persona definitions (Strategist, Critic, etc.) |
| `agent-argumentation-patterns/` | Argumentation strategies |
| `agent-tone-profiles/` | Tone/voice profiles |
| `agent-bundles/` | Pre-configured agent groups |
| `workflows/` | Workflow templates |
| `llm-profiles/` | LLM connection/model configurations |
| `prompt-modifiers/` | Prompt modification modules |
| `lang-de/` | German language pack |

Each module has a `manifest.json` and a `profile.md` or `profile.json`.

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
| `DANWA_JWT_SECRET_KEY` | -- | **Required** for auth in production |
| `DANWA_AUTH_ENABLED` | `false` | Enable JWT authentication |
| `DANWA_RATE_LIMIT_DEFAULT` | `60/minute` | API rate limit |
| `DANWA_DEBUG` | `false` | Debug mode |

## Testing

```bash
# Backend
pytest tests/backend

# Frontend (unit)
npm run test:unit

# Frontend (E2E)
npm run test:e2e

# Linting
ruff check backend/
ruff format backend/
```

## Useful Commands

```bash
bash manage.sh status        # overview of running components
bash manage.sh status --json # machine-readable status
bash manage.sh dashboard     # interactive dashboard
bash manage.sh logs fe       # tail frontend logs
bash manage.sh stop          # stop all components
```

## Project Structure

```
danwa/
  backend/          # FastAPI application (routers, services, models)
  frontend/         # Svelte 5 frontend
  modules/          # Agent cores, workflows, LLM profiles, language packs
  scripts/          # Shared bash library (libdanwa.sh), seed scripts
  config/           # Application configuration
  data/             # Database, DMS storage
  tests/            # Backend (pytest) and script (bats) tests
  deploy/           # Docker Compose, deployment configs
  docs/             # ADRs, documentation
  plans/            # Architecture plans and roadmaps
  repo-templates/   # Canonical setup/manage templates for all repos
```

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

You may copy, distribute, and modify the software under the terms of the AGPL-3.0. If you run the software on a server and provide network access to its functionality, you must also make the source code available to those users.

See <https://www.gnu.org/licenses/agpl-3.0.html> for the full license text.

## Links

- [INSTALL.md](INSTALL.md) -- detailed installation guide
- [CHANGELOG.md](CHANGELOG.md) -- version history
- [API Documentation](http://localhost:8000/docs) -- Swagger UI (when backend is running)
