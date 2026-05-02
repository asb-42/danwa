# Debate-Agent User Manual

## Table of Contents

1. [Overview](#overview)
2. [Installation & Setup](#installation--setup)
3. [Configuration](#configuration)
4. [Getting Started](#getting-started)
5. [User Interface Guide](#user-interface-guide)
6. [Core Features](#core-features)
7. [Multi-Agent Debate Workflow](#multi-agent-debate-workflow)
8. [Document Processing](#document-processing)
9. [Web Search & Fact Checking](#web-search--fact-checking)
10. [Memory & Precedents](#memory--precedents)
11. [Report Generation](#report-generation)
12. [Session Management](#session-management)
13. [Document Management System (DMS)](#document-management-system-dms)
14. [Privacy & Data Protection](#privacy--data-protection)
15. [Audit & Reproducibility](#audit--reproducibility)
16. [Advanced Configuration](#advanced-configuration)
17. [Development](#development)
18. [Troubleshooting](#troubleshooting)

---

## Overview

Debate-Agent is an auditable multi-agent debate workflow system that uses multiple AI agents to analyze, critique, and optimize arguments around a given topic or problem. The system employs a structured debate process (Strategist → Critic → Optimizer → Moderator) to arrive at well-reasoned conclusions with measurable consensus scores.

### Key Capabilities

- **Multi-Agent Deliberation**: Four specialized AI agents collaborate to produce high-quality analysis
- **LLM Flexibility**: Supports local models (via LM Studio) and cloud providers (via LiteLLM)
- **Document Analysis**: Upload and analyze PDF, DOCX, ODT, ODS, and ODP files
- **Web Validation**: Optional fact-checking via SearXNG or DuckDuckGo integration
- **Semantic Memory**: ChromaDB-powered precedent retrieval from past debates
- **Audit Trail**: Complete JSONL trace logs for reproducibility
- **Report Generation**: Export results as DOCX or PDF
- **Privacy Protection**: Built-in PII redaction and data retention policies
- **Session Management**: SQLite-backed session storage with dashboard interface
- **Modern Web UI**: Svelte 5 + Tailwind CSS frontend with real-time updates
- **RESTful API**: FastAPI backend with comprehensive API endpoints
- **LangGraph Orchestration**: State machine workflow for debate management

### Technology Stack

| Component | Technology |
|-----------|-------------|
| **Language** | Python 3.11+ |
| **Backend Framework** | FastAPI + LangGraph |
| **UI Framework** | Svelte 5 + Tailwind CSS |
| **LLM Integration** | LiteLLM (multi-provider routing) |
| **Vector Database** | ChromaDB |
| **Web Search** | SearXNG / DuckDuckGo |
| **Document Parsing** | pdfplumber, pypdf, python-docx, odfpy |
| **Report Generation** | python-docx, WeasyPrint |
| **Database** | SQLite |
| **DMS Module** | Custom (SQLite + ChromaDB + PaddleOCR) |
| **OCR Engine** | PaddleOCR (optional) |
| **Package Manager** | uv |
| **Frontend Build** | Vite |
| **Testing** | Pytest (backend), Playwright (frontend e2e) |

---

## Installation & Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Node.js 18+ and npm (for frontend development)
- (Optional) LM Studio for local LLM hosting
- (Optional) SearXNG for web search validation

### Quick Setup

Run the provided setup script:

```bash
cd /media/data/coding/danwa
bash setup.sh
```

This script will:
1. Install `uv` if not present
2. Create a Python virtual environment
3. Install all Python dependencies from `pyproject.toml`

### Frontend Setup

For frontend development:

```bash
cd frontend
npm install
npm run dev  # Starts Vite dev server on http://localhost:5173
```

### Manual Setup

If you prefer manual installation:

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -e ".[test]"

# Install DMS dependencies (optional, for PaddleOCR)
uv pip install -e ".[dms]"

# Install frontend dependencies
cd frontend && npm install
```

### Verify Installation

```bash
# Backend dependencies
uv run python -c "import fastapi, langgraph, litellm, chromadb; print('Backend dependencies installed')"

# Frontend dependencies
cd frontend && npm list svelte vite tailwindcss
```

---

## Configuration

The system uses YAML configuration files located in the `profiles/` and `config/` directories.

### LLM Profiles (`profiles/llm/*.yaml`)

Each LLM profile is a separate YAML file with typed fields:

```yaml
# profiles/llm/openrouter-claude.yaml
id: openrouter-claude
name: OpenRouter Claude 3.5 Sonnet
provider: openrouter
model: anthropic/claude-3.5-sonnet
api_base: "https://openrouter.ai/api/v1"
api_key_env: OPENROUTER_API_KEY
max_tokens: 4096
temperature: 0.7
cost_per_1k_input: 0.003
cost_per_1k_output: 0.015
```

Available profiles:
- `profiles/llm/openrouter-claude.yaml`
- `profiles/llm/openrouter-gpt4.yaml`
- `profiles/llm/local-qwen.yaml`

### Agent Personas (`profiles/agents/*.yaml`)

Each agent persona defines role, system prompt, and temperature:

```yaml
# profiles/agents/strategist-default.yaml
id: strategist-default
name: Default Strategist
role: strategist
system_prompt: "You are a strategic analyst..."
temperature: 0.7
tags: [default]
```

Available personas:
- `strategist-default.yaml`
- `critic-default.yaml`
- `optimizer-default.yaml`
- `moderator-default.yaml`
- `critic-stoic.yaml`
- `strategist-german-law.yaml`

### Prompt Variants (`profiles/prompts/`)

Prompt templates are Markdown files organized by variant:

```
profiles/prompts/
├── default/          # Default variant
│   ├── strategist.md
│   ├── critic.md
│   ├── optimizer.md
│   └── moderator.md
├── variants/
│   ├── kantian/      # Kantian ethics variant
│   │   ├── strategist.md
│   │   └── critic.md
│   └── steiner/      # Steiner variant
│       ├── strategist.md
│       └── critic.md
```

### Application Settings (`config/settings.yaml`)

```yaml
search:
  engine: "searxng"
  url: "http://127.0.0.1:8080"
  max_results: 5

privacy:
  strict_mode: false
  redact_traces: true
  retention_days: 90

dms:
  enabled: true
  storage_path: "dms_storage"
  chunk_size: 512
  chunk_overlap: 51
  embedding_model: "intfloat/multilingual-e5-small"
  ocr_enabled: false
  ocr_device: "cpu"
  max_file_size_mb: 50
  chroma_collection: "document_chunks"
  memory_dir: "memory"

ui:
  language: "en"
```

---

## Getting Started

### Starting the Application

#### Development Mode

```bash
# Terminal 1: Start backend
cd /media/data/coding/danwa
bash scripts/start.sh

# Terminal 2: Start frontend (optional, for development)
cd /media/data/coding/danwa/frontend
npm run dev
```

The backend will be available at `http://localhost:8000` (FastAPI with interactive docs at `/docs`).
The frontend development server will be available at `http://localhost:5173`.

#### Production Mode

Build and serve the frontend:

```bash
cd /media/data/coding/danwa/frontend
npm run build  # Outputs to frontend/dist/

# Start backend (serves frontend static files)
cd ..
bash scripts/start.sh
```

Access the application at `http://localhost:8000`.

### First Run

1. Open your browser to `http://localhost:8000`
2. Configure your settings via the Config view
3. Navigate to the Debate view
4. Type your topic or upload documents
5. Review the multi-agent analysis results
6. Download reports or view the audit trace

---

## User Interface Guide

### Dashboard View

The main dashboard displays session history and quick actions:

```
┌─────────────────────────────────────────────────────┐
│  📊 Debate-Agent Dashboard                        │
├─────────────────────────────────────────────────────┤
│  [New Debate]  [View Audit]  [Configure]          │
├─────────────────────────────────────────────────────┤
│  Recent Sessions:                                  │
│  ─────────────────────────────────────────────      │
│  Session abc123... | 2024-01-15 | Consensus: 0.85 │
│  [View] [Trace] [Delete]                           │
│  ─────────────────────────────────────────────      │
│  Session def456... | 2024-01-14 | Consensus: 0.92 │
│  [View] [Trace] [Delete]                           │
└─────────────────────────────────────────────────────┘
```

### Debate View

The debate interface provides real-time updates during agent deliberation:

```
┌─────────────────────────────────────────────────────┐
│  💬 New Debate                                     │
├─────────────────────────────────────────────────────┤
│  Topic: Analyze the impact of AI on education...   │
│  [Document Upload] [Settings]                      │
├─────────────────────────────────────────────────────┤
│  🔄 Initializing debate...                         │
│  🔄 Round 1/3                                      │
│     ├─ 🤖 Strategist: Analyzing...                 │
│     ├─ 🤖 Critic: Reviewing...                     │
│     ├─ 🤖 Optimizer: Synthesizing...               │
│     └─ 🤖 Moderator: Scoring... (0.85)            │
├─────────────────────────────────────────────────────┤
│  ## Result (Consensus: 0.85)                       │
│  [Analysis output...]                              │
│  [Download DOCX] [Download PDF] [View Trace]      │
└─────────────────────────────────────────────────────┘
```

### Configuration View

Access via the Config navigation item:

| Setting | Description | Default |
|---------|-------------|---------|
| **LLM Profile** | Select LLM backend | `local-qwen` |
| **Max Rounds** | Number of debate rounds (1-5) | 3 |
| **Consensus Threshold** | Target consensus threshold (0.5-1.0) | 0.75 |
| **Web Validation** | Enable fact-checking | true |
| **Precedent Memory** | Enable semantic memory | true |
| **Prompt Variant** | Prompt strategy | `default` |

### Audit View

View complete audit trails for past sessions:

```
┌─────────────────────────────────────────────────────┐
│  📋 Audit Trail: abc123...                         │
├─────────────────────────────────────────────────────┤
│  Session ID: abc123...                              │
│  Created: 2024-01-15 10:30:00                     │
│  Consensus: 0.85                                    │
│  Rounds: 3                                          │
├─────────────────────────────────────────────────────┤
│  [Timeline View] [Raw JSONL] [Download]            │
│  ─────────────────────────────────────────────      │
│  Round 1 - Strategist                              │
│  Prompt: [preview...]                               │
│  Response: [preview...]                             │
│  ─────────────────────────────────────────────      │
│  Round 1 - Critic                                   │
│  ...                                               │
└─────────────────────────────────────────────────────┘
```

---

## Core Features

### Multi-Agent Debate Workflow

The system orchestrates four specialized agents in a structured debate using LangGraph state machine:

```
Input → [Initialize] → [Strategist] → [Critic] → [Optimizer] → [Moderator]
                     ↓              ↓             ↓              ↓
                  Strategy      Critique      Synthesis      Consensus
```

Each round produces:
1. **Strategy** - Initial analysis and argumentation structure
2. **Critique** - Identification of weaknesses and risks
3. **Optimization** - Refined synthesis addressing critiques
4. **Moderation** - Consensus scoring (0.0 to 1.0)

### Configurable Rounds

Set `max_rounds` (1-5) to control debate depth:
- **1 round**: Quick analysis
- **3 rounds**: Balanced (default)
- **5 rounds**: Thorough deliberation

Debate stops early if consensus threshold is reached.

### Consensus Threshold

The moderator scores each round's output (0.0-1.0). If the score meets or exceeds the threshold, the debate concludes early.

---

## Multi-Agent Debate Workflow

### 1. Strategist Agent

**Role**: Experienced strategy developer

**Tasks**:
- Analyze the input factually
- Structure the central problem
- Develop logical, step-by-step argumentation
- Mark explicit assumptions

**Output Format**:
1. Problem core
2. Strategy
3. Key assumptions
4. Open points

### 2. Critic Agent

**Role**: Tough, factual examiner (Devil's Advocate)

**Tasks**:
- Find at least 3 fundamental weaknesses
- Identify logical breaks or unsubstantiated assumptions
- Evaluate risks of false conclusions
- Check for citation gaps or implicit bias

**Output Format**:
1. Critique points
2. Risk assessment
3. Missing evidence
4. Revision recommendations

### 3. Optimizer Agent

**Role**: Synthesis and precision specialist

**Tasks**:
- Integrate strategy and criticism
- Produce coherent, court-ready formulation
- Sharpen phrasing, remove redundancies
- Establish clear causalities
- Mark remaining uncertainties

**Output Format**: Final argumentation structure with clear organization, source references, and transparent residual risks.

### 4. Moderator Agent

**Role**: Neutral evaluation and control agent

**Tasks**:
- Verify optimized version addresses original problem
- Evaluate consensus between strategy and criticism
- Score on 0.0-1.0 scale

**Output**: Single decimal number (e.g., `0.85`)

---

## Document Processing

### Supported Formats

| Format | Extension | Library Used |
|--------|-----------|--------------|
| PDF | `.pdf` | pdfplumber (preferred), pypdf (fallback) |
| Word | `.docx` | python-docx |
| OpenDocument Text | `.odt` | odfpy |
| OpenDocument Spreadsheet | `.ods` | odfpy |
| OpenDocument Presentation | `.odp` | odfpy |
| Plain Text | `.txt`, `.md`, etc. | Native read |

### Upload Process

1. Navigate to the Debate view
2. Click the file upload button or drag-and-drop files
3. Select one or more documents (multiple supported)
4. The system will parse and extract text automatically
5. Parsed content is added to the debate context

### Text Extraction

- **PDF**: Extracts text from all pages using pdfplumber; falls back to pypdf
- **DOCX**: Extracts paragraph text
- **ODF**: Uses odfpy's teletype extraction
- **Others**: Reads as plain text with UTF-8 encoding

### Context Protection

- Maximum context length: **25,000 characters**
- Documents exceeding this limit are truncated with a warning
- Metadata includes: source filename, extension, page count, word count, character count

---

## Web Search & Fact Checking

### Overview

When enabled, the system performs automated fact-checking by:
1. Extracting 3 key claims from the current draft
2. Searching the web for each claim
3. Returning evidence snippets for validation

### Search Engine Configuration

**Primary**: SearXNG (self-hosted, privacy-friendly)
**Fallback**: DuckDuckGo (no API key required)

```yaml
search:
  engine: "searxng"
  url: "http://127.0.0.1:8080"
  max_results: 5
```

### Setting Up SearXNG

For local deployment:

```bash
# Using Docker
docker run -d -p 8080:8080 searxng/searxng

# Or use the provided setup script
bash scripts/setup_searxng.sh
```

---

## Memory & Precedents

### Overview

The system maintains a semantic memory of past debates using ChromaDB vector storage. When enabled, it:
1. Searches for similar past debates
2. Injects relevant precedent insights into the current context
3. Stores completed debates for future reference

### ChromaDB Integration

- **Storage Location**: `memory/chroma_db/`
- **Collection**: `debate_precedents`
- **Similarity Metric**: Cosine distance
- **Embedding Model**: Default sentence-transformers (via chromadb)

---

## Report Generation

### Available Formats

| Format | Extension | Library | Features |
|--------|-----------|---------|----------|
| Word Document | `.docx` | python-docx | Tables, styling, structured layout |
| PDF | `.pdf` | WeasyPrint | Print-ready, CSS styling |

### Report Contents

Both formats include:
1. **Title**: Debate analysis with session ID
2. **Metadata Table**: Creation date, rounds, consensus, validation status, precedents
3. **Sachverhalt (Input)**: First 1200 characters of input context
4. **Final Argumentation**: Complete optimized output
5. **External Fact Check** (if enabled)
6. **Audit Reference**: Trace file location, prompt versions, timestamp

---

## Session Management

### API Endpoints

Sessions are managed via RESTful API:

```
GET    /api/v1/sessions        # List sessions
GET    /api/v1/sessions/{id}   # Get session details
DELETE /api/v1/sessions/{id}   # Delete session
POST   /api/v1/debate          # Start new debate
GET    /api/v1/debate/{id}     # Get debate status
```

### Database Schema

Sessions stored in `memory/debates.db`:

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT,
    profile TEXT,
    max_rounds INTEGER,
    consensus REAL,
    context_preview TEXT,
    trace_path TEXT,
    report_docx TEXT,
    report_pdf TEXT,
    validated INTEGER
)
```

---

## Document Management System (DMS)

### What is DMS?

The Document Management System (DMS) provides project-wise document organization, intelligent chunking, and retrieval-augmented generation (RAG) capabilities.

### DMS API Endpoints

```
POST   /api/v1/dms/projects           # Create project
GET    /api/v1/dms/projects           # List projects
DELETE /api/v1/dms/projects/{id}      # Delete project
POST   /api/v1/dms/projects/{id}/documents  # Upload document
GET    /api/v1/dms/projects/{id}/documents  # List documents
DELETE /api/v1/dms/documents/{id}     # Delete document
POST   /api/v1/dms/retrieve           # Retrieve relevant chunks
```

---

## Privacy & Data Protection

### PII Redaction

Automatically redacts:
- **Email addresses**: `[REDACTED_EMAIL]`
- **IPv4 addresses**: `[REDACTED_IPV4]`
- **German phone numbers**: `[REDACTED_PHONE_DE]`
- **ID numbers**: `[REDACTED_ID_NUMBER]`

### Strict Mode

When `strict_mode: true` in `config/settings.yaml`:
- **All external calls blocked** (web search, cloud LLMs)
- Only local LLMs can be used

### Data Retention Policy

Configured via `retention_days` (default: 90 days).

---

## Audit & Reproducibility

### Trace Logging

Every debate generates a complete audit trail in JSONL format.

**Location**: `logs/{session_id}.jsonl`

**Format** (one JSON object per line):
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "step": "R1",
  "agent": "strategist",
  "prompt_variant": "default",
  "prompt_version": "v1.2",
  "prompt_hash": "a3f2b1c4d5e6f7a8",
  "prompt_preview": "You are a strategic analyst...",
  "response_preview": "1. Problem core: ...",
  "metadata": {"tokens": 1250},
  "response_full": "Complete agent response..."
}
```

### API Audit Endpoints

```
GET  /api/v1/audit/{session_id}           # Get audit trail
GET  /api/v1/audit/{session_id}/export    # Export as JSON/MD
```

---

## Advanced Configuration

### Profile Management API

```
GET    /api/v1/profiles/llm              # List LLM profiles
GET    /api/v1/profiles/llm/{id}         # Get LLM profile
POST   /api/v1/profiles/llm              # Create LLM profile
PUT    /api/v1/profiles/llm/{id}         # Update LLM profile
DELETE /api/v1/profiles/llm/{id}         # Delete LLM profile
```

### Environment Variables

Set API keys as environment variables:

```bash
export OPENROUTER_API_KEY="your_openrouter_key"
export LM_STUDIO_KEY="your_lm_studio_key"
```

---

## Development

### Running Tests

```bash
# Backend tests (pytest)
make test
# or
uv run pytest tests/ -v

# Frontend e2e tests (Playwright)
cd frontend
npm run test:e2e

# Specific test suites
npm run test:contracts    # API contract tests
npm run test:visual       # Visual regression tests
npm run test:a11y          # Accessibility tests
npm run test:i18n          # Internationalization tests
```

### Linting and Formatting

```bash
# Backend linting (ruff)
make lint
make format
# or
uv run ruff check .
uv run ruff format .
```

### CI Checks

```bash
make check  # Runs lint + test
```

### Project Structure

```
danwa/
├── backend/                     # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── api/routers/             # API routers
│   ├── workflow/                # LangGraph state machine
│   ├── services/                # Business logic services
│   ├── core/                    # Core schemas and config
│   ├── repositories/            # Data access layer
│   ├── models/                  # Pydantic schemas
│   └── persistence/             # Audit trail storage
├── frontend/                    # Svelte 5 SPA
│   ├── src/
│   │   ├── views/               # Dashboard, Debate, Audit, Config
│   │   ├── components/          # Reusable UI components
│   │   └── main.js              # Entry point
│   ├── tests/e2e/              # Playwright e2e tests
│   └── package.json             # Node dependencies
├── src/                         # Legacy core (being migrated)
│   ├── core/                    # Business logic
│   ├── tools/                   # External integrations
│   └── dms/                     # Document Management System
├── profiles/                    # Profile configuration
│   ├── llm/                     # LLM profile definitions
│   ├── agents/                  # Agent persona definitions
│   └── prompts/                 # Prompt templates
├── config/                       # Application settings
├── tests/                        # Pytest test suite
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
├── memory/                       # Runtime data
├── logs/                         # Debate trace logs (JSONL)
├── reports/                      # Generated reports
├── pyproject.toml               # Project metadata & dependencies
├── Makefile                     # Dev workflow
└── setup.sh                     # Quick setup script
```

---

## Troubleshooting

### Common Issues

#### "Connection refused" when accessing backend

- **Cause**: Backend not running
- **Fix**: Run `bash scripts/start.sh`

#### "LiteLLM error: Connection refused"

- **Cause**: Local LLM (LM Studio) not running
- **Fix**: Start LM Studio and load a model, or switch to a cloud profile

#### "SearXNG request failed"

- **Cause**: SearXNG not running or wrong URL
- **Fix**: Verify `config/settings.yaml` has correct `search.url`, or disable fact-checking

#### "Profile not found"

- **Cause**: LLM profile or agent persona doesn't exist
- **Fix**: Check that profile files exist in `profiles/llm/` and `profiles/agents/`

#### "Parsing failed"

- **Cause**: Unsupported file format or corrupted file
- **Fix**: Convert to supported format, or system falls back to plain text

### Logs

- **Application logs**: Check terminal output when running `uvicorn`
- **Debate traces**: `logs/{session_id}.jsonl`
- **Frontend dev server**: Check browser console

### Getting Help

1. Check the terminal output for Python tracebacks
2. Verify `config/settings.yaml` syntax
3. Ensure all dependencies are installed: `uv pip list`
4. Check API documentation at `http://localhost:8000/docs`

---

*Documentation generated for Debate-Agent v2.0.0*
