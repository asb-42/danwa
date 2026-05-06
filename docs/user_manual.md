# Danwa User Manual

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
12. [Project Management](#project-management)
13. [Document Management System (DMS)](#document-management-system-dms)
14. [Real-Time Updates (SSE)](#real-time-updates-sse)
15. [Out-of-Band Inputs](#out-of-band-inputs)
16. [Workflow Visualization](#workflow-visualization)
17. [Internationalization (i18n)](#internationalization-i18n)
18. [Privacy & Data Protection](#privacy--data-protection)
19. [Audit & Reproducibility](#audit--reproducibility)
20. [Advanced Configuration](#advanced-configuration)
21. [Development](#development)
22. [Troubleshooting](#troubleshooting)

---

## Overview

Danwa (formerly Debate-Agent) is an auditable multi-agent debate workflow system that uses multiple AI agents to analyze, critique, and optimize arguments around a given topic or problem. The system employs a structured debate process (Strategist → Critic → Optimizer → Moderator) orchestrated by a LangGraph state machine to arrive at well-reasoned conclusions with measurable consensus scores.

### Key Capabilities

- **Multi-Agent Deliberation**: Four specialized AI agents collaborate to produce high-quality analysis
- **LLM Flexibility**: Supports local models (via LM Studio, Ollama) and cloud providers (via LiteLLM)
- **Document Analysis**: Upload and analyze PDF, DOCX, ODT, ODS, and ODP files
- **Web Validation**: Optional fact-checking via SearXNG or DuckDuckGo integration (off/optional/required modes)
- **Semantic Memory**: ChromaDB-powered precedent retrieval from past debates
- **Audit Trail**: Complete JSONL trace logs for reproducibility
- **Report Generation**: Export results as DOCX or PDF
- **Privacy Protection**: Built-in PII redaction and data retention policies
- **Project Isolation**: SQLite-backed project system with isolated data storage
- **Modern Web UI**: Svelte 5 + Tailwind CSS + @xyflow/svelte with real-time updates
- **RESTful API**: FastAPI backend with comprehensive API endpoints
- **LangGraph Orchestration**: State machine workflow for debate management
- **Real-Time SSE**: Server-Sent Events for live debate progress visualization
- **Out-of-Band Inputs**: Inject additional context during running debates

### Technology Stack

| Component | Technology |
|-----------|-------------|
| **Language** | Python 3.11+ |
| **Backend Framework** | FastAPI + LangGraph |
| **UI Framework** | Svelte 5 + Tailwind CSS |
| **Workflow Visualization** | @xyflow/svelte + ELK.js |
| **Frontend Build** | Vite 5 |
| **LLM Integration** | LiteLLM (multi-provider routing) |
| **Vector Database** | ChromaDB |
| **Web Search** | SearXNG / DuckDuckGo |
| **Document Parsing** | pdfplumber, pypdf, python-docx, odfpy |
| **Report Generation** | python-docx, WeasyPrint |
| **Database** | SQLite (debates, sessions, projects) |
| **DMS Module** | Custom (SQLite + ChromaDB + PaddleOCR) |
| **OCR Engine** | PaddleOCR (optional) |
| **Package Manager (Python)** | uv |
| **Package Manager (Node)** | npm |
| **Testing (Backend)** | pytest 8+ |
| **Testing (Frontend)** | Playwright 1.59+ (e2e, visual, a11y, i18n) |
| **Linting** | ruff 0.4+ |
| **Validation** | Pydantic 2.7+ |
| **SSE Support** | sse-starlette |
| **i18n** | Custom loaders (German/English) |

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
id: openrouter-claude-3.6-sonnet
name: Claude 3.6 Sonnet (OpenRouter)
provider: openrouter          # openrouter | openai | anthropic | local | ollama
model: anthropic/claude-3.6-sonnet
api_base: "https://openrouter.ai/api/v1"
api_key_env: OPENROUTER_API_KEY
max_tokens: 4096
context_window: 200000
temperature: 0.7
timeout: 600
cost_per_1k_input: 0.003
cost_per_1k_output: 0.015
```

Available profiles:
- `profiles/llm/openrouter-claude.yaml`
- `profiles/llm/openrouter-gpt4.yaml`
- `profiles/llm/openrouter-grok.yaml`
- `profiles/llm/xiaomi-mimo.yaml`
- `profiles/llm/local-qwen.yaml`

### Agent Personas (`profiles/agents/*.yaml`)

Each agent persona defines role, system prompt, and linked LLM profile:

```yaml
# profiles/agents/strategist-default.yaml
id: strategist-default
name: Default Strategist
role: strategist              # strategist | critic | optimizer | moderator
system_prompt: |
  You are the Strategist agent in a multi-agent debate system.
  Your task is to analyze the input factually and develop a logical argumentation structure.
llm_profile_id: openrouter-claude-3.6-sonnet
max_rounds: 5
consensus_threshold: 0.9
tags: [default, balanced]
```

Default personas:
- `strategist-default.yaml`
- `critic-default.yaml`
- `optimizer-default.yaml`
- `moderator-default.yaml`
- `critic-stoic.yaml` (example)
- `strategist-german-law.yaml` (example)

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
└── variants/            # Named prompt variants
    ├── kantian/          # Kantian ethics variant
    │   ├── strategist.md
    │   └── critic.md
    └── steiner/          # Steiner variant
        ├── strategist.md
        └── critic.md
```

### Application Settings (`config/settings.yaml`)

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

- Backend: `http://localhost:8000` (FastAPI with interactive docs at `/docs`)
- Frontend development server: `http://localhost:5173`

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
2. Select or create a project via the Project Selector
3. Configure your settings via the Config view
4. Navigate to the Debate view
5. Type your topic or upload documents
6. Review the multi-agent analysis results
7. Download reports or view the audit trace

---

## User Interface Guide

### Dashboard View

The main dashboard displays project list, recent debates, and quick actions:

```
┌─────────────────────────────────────────────────────┐
│  📊 Danwa Dashboard                                 │
├─────────────────────────────────────────────────────┤
│  Project: [My Project ▼]  [New Debate]           │
├─────────────────────────────────────────────────────┤
│  Recent Debates:                                   │
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
| **LLM Profile** | Select LLM backend | `openrouter-claude` |
| **Max Rounds** | Number of debate rounds (1-20) | 3 |
| **Consensus Threshold** | Target consensus threshold (0.0-1.0) | 0.8 |
| **Web Validation** | Enable fact-checking | off / optional / required |
| **Precedent Memory** | Enable semantic memory | true |
| **Prompt Variant** | Prompt strategy | `default` |
| **Language** | UI & debate language | English / German |

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

### Projects View

Manage projects with isolated data storage:

```
┌─────────────────────────────────────────────────────┐
│  📁 Projects                                       │
├─────────────────────────────────────────────────────┤
│  [+ New Project]                                   │
│  ─────────────────────────────────────────────      │
│  ● My Project (active)                           │
│    3 debates, 12 documents                        │
│    [Settings] [Open] [Delete]                      │
│  ─────────────────────────────────────────────      │
│  ○ Research Project                             │
│    1 debate, 5 documents                         │
│    [Settings] [Open] [Delete]                      │
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

Set `max_rounds` (1-20) to control debate depth:
- **1 round**: Quick analysis
- **3 rounds**: Balanced (default)
- **5+ rounds**: Thorough deliberation

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
| Images (OCR) | `.png`, `.jpg` | PaddleOCR (optional) |
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

### Search Modes

| Mode | Behavior |
|------|-----------|
| `off` | No web search |
| `required` | Auto-search before LLM call, inject results into prompt |
| `optional` | Agents can request searches using `[SEARCH: query]` markers in their output |

### Search Engine Configuration

**Primary**: SearXNG (self-hosted, privacy-friendly)
**Fallback**: DuckDuckGo (no API key required)

```yaml
search:
  engine: "duckduckgo"
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

- **Storage Location**: `data/projects/{project_id}/dms/chroma/`
- **Collection**: Separate per project
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

## Project Management

### What is Project Isolation?

Danwa uses a **project isolation** system where each project has:
- Its own SQLite database for debates and audit events
- Its own ChromaDB collection for vector embeddings
- Its own DMS storage for documents
- Isolated configuration and settings

### Managing Projects

#### Create a Project

1. Click **Projects** in the navigation
2. Click **+ New Project**
3. Enter project name and description
4. Click **Create**

#### Switch Projects

Use the **Project Selector** in the header to switch between projects. This changes the active context for:
- Debate listing
- Document management
- Audit trails
- API requests (via `X-Project-Id` header)

#### Project Settings

Each project can have its own:
- LLM profile defaults
- Prompt variant preferences
- DMS configuration

### API Project Isolation

All API endpoints support project isolation via:
- **Header**: `X-Project-Id: {project_id}` (for most requests)
- **Query Param**: `project_id={project_id}` (for SSE, which can't send headers)

```bash
# List debates in a specific project
curl -H "X-Project-Id: proj_abc123" http://localhost:8000/api/v1/debate

# SSE stream (project_id as query param)
curl http://localhost:8000/api/v1/debate/abc123/stream?project_id=proj_abc123
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
POST   /api/v1/dms/documents         # Upload document
GET    /api/v1/dms/documents         # List documents
DELETE /api/v1/dms/documents/{id}     # Delete document
POST   /api/v1/dms/retrieve          # Retrieve relevant chunks (RAG)
POST   /api/v1/dms/documents/{id}/rag  # Add/remove from RAG
```

### RAG Pipeline

Retrieval-Augmented Generation flow:
1. **Document Processing**: Parse file → extract text
2. **OCR (if enabled)**: PaddleOCR for scanned PDFs/images
3. **Chunking**: Split text into 512-token chunks with overlap
4. **Embedding**: Generate vector embeddings for each chunk
5. **Indexing**: Store in ChromaDB + metadata index
6. **Retrieval**: Hybrid search (BM25 + Vector + Re-ranking)
7. **Formatting**: Build context string for LLM injection

### Hybrid Retrieval

Combines three retrieval methods:
- **BM25**: Keyword-based search
- **Vector Search**: Semantic similarity search
- **Re-ranking**: RRF (Reciprocal Rank Fusion) to merge results

---

## Real-Time Updates (SSE)

### What is SSE?

Server-Sent Events (SSE) push real-time debate progress to the frontend. The debate view updates live as agents work.

### SSE Event Types

| Event Type | Description | Data |
|-----------|-------------|------|
| `workflow_started` | Debate engine started | `{ type, message, debate_id }` |
| `agent_preparing` | Agent resolving profile/prompts | `{ round, role, phase }` |
| `agent_started` | LLM call about to start | `{ round, role, profile, model }` |
| `llm_call_started` | LLM generation in progress | `{ round, role, model, provider }` |
| `agent_output` | Agent response received | `{ round, role, content, tokens_used }` |
| `round_update` | Round completed | `{ round, consensus, agent_count }` |
| `status_change` | Debate completed/failed | `{ status, final_consensus }` |
| `oob_input` | Out-of-band input submitted | `{ type, oob_id, content, target }` |
| `oob_consumed` | OOB input consumed by agent | `{ type, oob_ids, by_agent, round }` |
| `web_search` | Search performed | `{ type, round, role, query, result_count }` |

### SSE Endpoint

```
GET /api/v1/debate/{debate_id}/stream?project_id={project_id}
```

The frontend automatically connects to this endpoint when starting a debate.

---

## Out-of-Band Inputs

### What are OOB Inputs?

Users can inject additional context during a running debate without stopping it. This is useful for:
- Correcting factual errors mid-debate
- Adding new information that becomes available
- Guiding specific agents with targeted input

### Submitting OOB Inputs

1. During a running debate, click **Add Input**
2. Enter your additional context
3. Select the target:
   - **Specific Agent**: Route to a specific agent role (strategist, critic, etc.)
   - **Next Agent**: Route to the agent after the current one
   - **All Future**: Route to all agents from a given round
   - **Current Active**: Route to the currently executing agent
4. Set urgency (high/medium/low)
5. Click **Submit**

### OOB Target Types

| Target Type | Description |
|------------|-------------|
| `specific_agent` | Routed to a specific agent role |
| `next_agent` | Routed to the agent after `current_agent_role` |
| `all_future` | Routed to all agents from `from_round` |
| `current_active` | Routed to the currently executing agent |

---

## Workflow Visualization

### Debate Graph

The debate process is visualized as an interactive graph using @xyflow/svelte and ELK.js layout:

```
┌─────────────────────────────────────────────────────┐
│  📊 Workflow Graph                                  │
├─────────────────────────────────────────────────────┤
│  [Input] ──→ [Strategist] ──→ [Critic]       │
│                    ↓              ↓                 │
│              [Optimizer] ──→ [Moderator]         │
│                    ↓                              │
│              [Complete] → END                    │
└─────────────────────────────────────────────────────┘
```

### Graph Features

- **Interactive Nodes**: Click to view agent details
- **Animated Edges**: Show data flow in real-time
- **Active Highlighting**: Current agent is highlighted
- **Timeline Panel**: View round-by-round history
- **Node Detail Panel**: View prompt, response, tokens used

### Node Types

| Node Type | Description |
|-----------|-------------|
| InputNode | Debate input and context |
| AgentNode | Strategist, Critic, Optimizer, Moderator |
| DecisionNode | Consensus check, round continuation |
| HistoryNode | Past round summaries |
| ArtifactNode | Final output, reports |
| UserActionNode | OOB input points |

---

## Internationalization (i18n)

### Supported Languages

- **English** (`en`) - Default for UI and debates
- **German** (`de`) - Full translation available

### Switching Languages

#### UI Language

Use the **Language Switcher** in the header to toggle between English and German UI.

#### Debate Language

Set the debate language in the **Debate View** or **Config View**:
- Affects prompt templates used (e.g., `strategist.md` vs `strategist-en.md`)
- Affects LLM response language (instructed via prompt)

### Translation Files

```
frontend/src/lib/i18n/loaders/
├── en.js           # English translations
└── de.js           # German translations
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

Set API keys as environment variables in `.env` file:

```bash
# .env file
OPENROUTER_API_KEY="your_openrouter_key"
ANTHROPIC_API_KEY="your_anthropic_key"
OPENAI_API_KEY="your_openai_key"
```

Environment variables use `DANWA_` prefix for application settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DANWA_APP_NAME` | `Debate-Agent` | Application name |
| `DANWA_HOST` | `0.0.0.0` | Server host |
| `DANWA_PORT` | `8000` | Server port |
| `DANWA_DEBUG` | `False` | Debug mode |
| `DANWA_CORS_ORIGINS` | `http://localhost:5173,http://localhost:8000` | CORS allowed origins |

---

## Development

### Running Tests

#### Backend tests (pytest)

```bash
# Run all tests
make test
# or
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/backend/test_debate_api.py -v
```

#### Frontend tests (Playwright)

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

- **Application logs**: `logs/debate-agent.log` (configured in `backend/main.py`)
- **Debate traces**: `logs/{session_id}.jsonl`
- **Frontend dev server**: Browser console

### Getting Help

1. Check the terminal output for Python tracebacks
2. Verify `config/settings.yaml` syntax
3. Ensure all dependencies are installed: `uv pip list`
4. Check API documentation at `http://localhost:8000/docs`

---

## Project Structure

```
danwa/
├── backend/                     # FastAPI + LangGraph backend
│   ├── main.py                  # App factory (uvicorn entry point)
│   ├── api/routers/             # API route handlers
│   ├── workflow/                # LangGraph state machine
│   ├── services/                # Business logic services
│   ├── core/                    # Core schemas and config
│   ├── models/                  # Pydantic schemas
│   ├── persistence/             # SQLite audit trail
│   └── migrations/              # Database migrations
├── frontend/                    # Svelte 5 SPA
│   ├── src/
│   │   ├── views/               # Dashboard, Debate, Audit, Config
│   │   ├── components/          # Reusable UI components
│   │   └── lib/                # Utilities and state management
│   └── package.json             # Node dependencies
├── profiles/                    # Profile configuration
│   ├── llm/                     # LLM profile definitions
│   ├── agents/                  # Agent persona definitions
│   └── prompts/                 # Prompt templates
├── config/                       # Application settings
├── data/                        # Runtime data (projects)
├── tests/                        # Pytest test suite
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
├── pyproject.toml               # Python project metadata
└── Makefile                     # Dev workflow
```

---

*Documentation generated for Danwa v2.0.0*
