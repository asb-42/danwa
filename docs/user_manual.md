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
14. [Backup System](#backup-system)
15. [Blueprint System](#blueprint-system)
16. [User Accounts & Authentication](#user-accounts--authentication)
17. [Tenant Management](#tenant-management)
18. [BYOK — Bring Your Own Key](#byok--bring-your-own-key)
19. [Cases & Tags](#cases--tags)
20. [Transactional Drafting](#transactional-drafting)
21. [Docker Deployment](#docker-deployment)
22. [Monitoring & Rate Limiting](#monitoring--rate-limiting)
23. [HITL (Human-in-the-Loop) System](#hitl-human-in-the-loop-system)
24. [Input/Output Composer](#inputoutput-composer)
25. [Real-Time Updates (SSE)](#real-time-updates-sse)
26. [Out-of-Band Inputs](#out-of-band-inputs)
27. [A2A Protocol Integration](#a2a-protocol-integration)
28. [Workflow Visualization](#workflow-visualization)
29. [Internationalization (i18n)](#internationalization-i18n)
30. [Privacy & Data Protection](#privacy--data-protection)
31. [Audit & Reproducibility](#audit--reproducibility)
32. [Advanced Configuration](#advanced-configuration)
33. [Development](#development)
34. [Troubleshooting](#troubleshooting)
35. [Unified Feedback System](#unified-feedback-system)
36. [Case-Space Workspace (Walkthrough)](#case-space-workspace-walkthrough)

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
- **A2A Protocol**: Agent-to-Agent communication for multi-agent workflows with external AI agents
- **Blueprint System**: Visual workflow editor for creating custom multi-agent workflows
- **HITL System**: Human-in-the-loop interactions for querying agents and providing feedback
- **Input/Output Composer**: Extensible plugin system for processing various input sources and generating multiple output formats (including TTS)
- **Tone Profiles**: Configure debate tone and style for different use cases
- **Role Definitions**: Define custom agent roles with specific behaviors

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
| **i18n** | Custom loaders + Backend API (14 languages + RTL) |

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

### Docker Deployment (Alternative)

Instead of the script-based setup, you can run Danwa in Docker containers:

```bash
# Quick start
docker compose up -d

# With Celery background worker
docker compose --profile celery up -d

# Using Makefile shortcuts
make docker-build
make docker-up
make docker-down
```

1. Copy `deploy/.env.example` to `deploy/.env` and configure your environment variables
2. The application is accessible at `http://localhost:8000`
3. Health check: `GET /health` shows service status (SQLite, Redis, Auth-DB)
4. For TLS, configure certificates in `deploy/nginx.conf`

See [Docker Deployment](#docker-deployment) for full details.

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
| `server.enabled` | Enable the A2A server (accepts incoming tasks from external agents) |
| `server.path` | JSON-RPC endpoint path (default: `/a2a`) |
| `external_agents` | List of external agent URLs for outgoing calls |

### Application Settings (`config/settings.yaml`)

```yaml
ui:
  language: en                   # Default UI language (de | en | fr | es | it | pt | ru | zh | ja | ko | sv | el | ar | he)

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
| **Language** | UI & debate language | 14 languages (de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he) |

### MVP Debate View

The MVP (Minimum Viable Product) debate view provides a lightweight, focused debate interface with real-time feedback:

```
┌─────────────────────────────────────────────────────┐
│  ⚡ MVP Debate [SSE ●]                              │
├─────────────────────────────────────────────────────┤
│  Topic: Analyze the impact of AI on education...   │
├─────────────────────────────────────────────────────┤
│  Round 1/3                                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🟢 Strategist (Claude 3.6 Sonnet)          │   │
│  │ ─────────────────────────────────────────── │   │
│  │ [Analysis output in Markdown...]            │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🔴 Critic (GPT-4o)                          │   │
│  │ ─────────────────────────────────────────── │   │
│  │ [Critique output in Markdown...]            │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🔵 Optimizer (Grok 4.2)                     │   │
│  │ ─────────────────────────────────────────── │   │
│  │ ⏳ Thinking...                              │   │
│  └─────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────┤
│  Consensus: ████████████░░░░░░ 62%                  │
│  Tokens: 1,245 in / 3,890 out                       │
└─────────────────────────────────────────────────────┘
```

**Key Features:**
- **Role-colored cards**: Each agent has a distinct color (green=strategist, red=critic, blue=optimizer, orange=moderator)
- **Activity strip**: Per-agent progress with role verb animation (Analyzing..., Critiquing..., Synthesizing..., Scoring...)
- **Thinking indicator**: Pulsing dot + bouncing dots while agent generates
- **Consensus bar**: Color-coded progress bar (red <50%, amber 50–80%, green ≥80%)
- **SSE indicator**: Green pulsing dot when connected to real-time stream
- **Markdown rendering**: Agent outputs rendered as formatted Markdown
- **Timer**: Processing timer per round/agent
- **Token counter**: Real-time token usage display

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

### Blueprint Canvas View

Visual workflow editor for creating custom multi-agent workflows:

```
┌─────────────────────────────────────────────────────┐
│  🎨 Blueprint Canvas                                │
├─────────────────────────────────────────────────────┤
│  [+ New Blueprint] [Load Layout] [Compile] [Run]   │
├─────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────┐   │
│  │  [Input] ──→ [Agent 1] ──→ [Agent 2]      │   │
│  │              ↓              ↓                │   │
│  │          [Gate] ──→ [Output]                │   │
│  └──────────────────────────────────────────────┘   │
│  Palette: [Agent] [Input] [Output] [Gate] [HITL]   │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Drag and drop nodes from palette
- Connect nodes to define execution flow
- Configure agent blueprints (LLM, role, prompt)
- Save and load canvas layouts
- Compile and validate workflows
- Execute workflows with real-time monitoring

### Input Composer View

Process various input sources for workflows:

```
┌─────────────────────────────────────────────────────┐
│  📥 Input Composer                                  │
├─────────────────────────────────────────────────────┤
│  Input Type: [Text ▼] | [Audio ▼] | [File ▼]       │
├─────────────────────────────────────────────────────┤
│  Configuration:                                     │
│  [Input parameters...]                              │
├─────────────────────────────────────────────────────┤
│  Target Workflow: [Select workflow ▼]              │
│  [Submit] [View Jobs]                               │
└─────────────────────────────────────────────────────┘
```

### Output Composer View

Generate various output formats from debate results:

```
┌─────────────────────────────────────────────────────┐
│  📤 Output Composer                                 │
├─────────────────────────────────────────────────────┤
│  Output Format: [DOCX ▼] | [PDF ▼] | [TTS ▼]       │
├─────────────────────────────────────────────────────┤
│  Source Artifact: [Select session ▼]                │
│  Configuration:                                     │
│  [Output parameters...]                             │
├─────────────────────────────────────────────────────┤
│  [Generate] [View Jobs] [Download]                  │
└─────────────────────────────────────────────────────┘
```

### Diff View

Compare two debate sessions or workflow states:

```
┌─────────────────────────────────────────────────────┐
│  🔍 Diff View                                       │
├─────────────────────────────────────────────────────┤
│  Compare:                                           │
│  Session A: [abc123...]  Session B: [def456...]     │
├─────────────────────────────────────────────────────┤
│  Round 1 - Strategist:                              │
│  - Added: "New insight..."                          │
│  - Removed: "Old argument..."                        │
│  - Modified: "Updated analysis..."                  │
└─────────────────────────────────────────────────────┘
```

### Replay View

Replay past debate sessions with timeline navigation:

```
┌─────────────────────────────────────────────────────┐
│  ▶️ Replay View                                     │
├─────────────────────────────────────────────────────┤
│  Session: abc123... | [Play] [Pause] [Step]        │
│  Timeline: [━━━━━━━━━━━━━━━━━━━━━━━●━━━━]          │
├─────────────────────────────────────────────────────┤
│  Current State: Round 2 - Critic                    │
│  [Agent output preview...]                          │
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

## Backup System

### What is the Backup System?

The Backup System protects your data by creating complete archives of all debates, projects, audit trails, and configuration files. It was introduced after a data loss incident to ensure you never lose your work.

### Key Features

- **ZIP Archives**: All data compressed into a single file with integrity verification
- **Manual Backups**: Create backups on demand with one click
- **Automatic Shutdown Backups**: Optional backup when you stop the application
- **Backup Verification**: Check that your backup is complete and uncorrupted
- **Full Restoration**: Recover all data from a backup (app must be stopped)
- **Configurable Retention**: Automatically delete old backups to save space

### Using the Backup System

#### Creating a Backup

1. Navigate to **Configuration** → **Backup** tab
2. Click **Create Backup**
3. The system creates a ZIP archive in the `backups/` directory
4. You'll see confirmation with the backup name and file count

#### Viewing Existing Backups

The Backup tab shows a table of all backups:
- **Date**: When the backup was created
- **Size**: Archive size in MB
- **Files**: Number of files included
- **Trigger**: `manual` or `shutdown`
- **Actions**: Files, Verify, Restore, Delete

#### Verifying a Backup

Click **Verify** next to any backup to check its integrity:
- Validates the ZIP archive structure
- Verifies SHA-256 checksums for all files
- Confirms metadata.json is present and valid

#### Restoring from a Backup

⚠️ **Warning**: Restoration overwrites existing data. Stop the application first.

1. Click **Restore** next to the backup you want to restore
2. Confirm the action when prompted
3. The system extracts all files to their original locations
4. Restart the application

#### Backup Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **Backups enabled** | Enable/disable backup functionality | Yes |
| **Automatic backup on shutdown** | Create backup when app stops | No (opt-in) |
| **Retention count** | Number of backups to keep (0 = unlimited) | 0 |
| **Encrypt backup** | Not yet implemented | No |

### What Gets Backed Up

| Path | Content |
|------|---------|
| `data/projects/*/debates/*.json` | All debate data |
| `data/projects/*/project.json` | Project definitions |
| `data/audit.db` | Audit trail |
| `data/projects/*/dms/dms.db` | DMS databases |
| `data/projects/*/dms/chroma_db/` | Vector embeddings |
| `data/a2a_tasks.db` | A2A task data |
| `data/blueprints.db` | Blueprint data |
| `config/settings.yaml` | App configuration |
| `config/a2a.json` | A2A configuration |
| `config/llm_profiles.yaml` | LLM profiles |

### What is NOT Backed Up

| Path | Reason |
|------|--------|
| `.env` | Contains secrets (backup separately) |
| `logs/` | Trace logs (not critical for recovery) |
| `memory/` | Runtime data (transient) |
| `.git/` | Version controlled |
| `frontend/dist/` | Build artifact (regenerable) |
| `backups/` | Backup files themselves (prevents recursion) |

### Backup File Format

Each backup is a ZIP file named: `danwa-backup-YYYY-MM-DDTHH-MM-SSZ.zip`

Contents:
- All backed-up files with their original directory structure
- `metadata.json`: Backup metadata (version, app version, commit hash, trigger)
- `SHA-256SUMS`: Checksums for all files (used for verification)

### API Endpoints

```
POST   /api/v1/config/backup              # Create backup
GET    /api/v1/config/backups             # List all backups
GET    /api/v1/config/backups/{id}        # Get backup metadata
GET    /api/v1/config/backups/{id}/files  # List files in backup
POST   /api/v1/config/backups/{id}/verify # Verify backup integrity
POST   /api/v1/config/backups/{id}/restore # Restore from backup
DELETE /api/v1/config/backups/{id}        # Delete a backup
GET    /api/v1/config/backup-settings     # Get backup settings
PUT    /api/v1/config/backup-settings     # Update backup settings
```

---

## Blueprint System

<!-- UPDATED -->

### What is the Blueprint System?

The Blueprint System is a visual workflow editor that allows you to create, manage, and execute custom multi-agent workflows through a graphical interface. The system has been updated with improved drag-and-drop, auto-layout, and state management features.

### Accessing the Blueprint Canvas

1. Click **Blueprints** in the main menu.
2. Click **New Blueprint** or select an existing one.

### Creating a Workflow

- **Add nodes**: Drag a node from the palette onto the canvas.
- **Connect nodes**: Click and drag from a node's output port to another node's input port.
- **Configure nodes**: Click a node to edit its properties.
- **Auto-layout**: Click the layout icon to automatically arrange nodes.
- **Save**: Your blueprint is automatically saved; you can also explicitly save with a name.

### Running a Blueprint

Once designed, click **Run** to execute the workflow. The result will appear in a new tab.

### Per-Agent LLM Parameters

Each agent blueprint can now specify **per-agent LLM inference overrides** that fine-tune generation behavior independently per agent in a workflow:

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `temperature` | float | Sampling temperature (0.0–2.0) | `0.9` for creative agents |
| `top_p` | float | Nucleus sampling threshold | `0.95` |
| `top_k` | int | Top-K sampling | `40` |
| `frequency_penalty` | float | Penalize repetition (-2.0–2.0) | `0.3` |
| `presence_penalty` | float | Penalize topic reuse (-2.0–2.0) | `0.2` |
| `seed` | int | Random seed for reproducibility | `42` |
| `stop` | string/list | Stop sequences | `["\n\n"]` |

These overrides are applied **per agent** at inference time — each agent in the same workflow can have different parameters. If left empty, the LLM profile defaults are used.

### Advanced Features

- **Drag-and-Drop**: Nodes can be freely repositioned on the canvas.
- **Undo/Redo**: Available via toolbar buttons.
- **Zoom and Pan**: Use mouse wheel and drag on empty canvas.
- **Persistent Storage**: Blueprints survive page reloads.
## Module System

<!-- UPDATED -->

### What is the Module System?

Danwa's module system allows you to extend the system with packaged agents, prompts, roles, tone systems, workflow templates, and LLM profiles. Each module is a self-contained directory with a `manifest.json` and profile file.

### Managing Modules

The **Module Manager** (accessible from Modules in the navigation) lets you:
- **Import** a module from a ZIP file or directory.
- **List** all installed modules with type and version.
- **Enable/Disable** modules.
- **View** module details.
- **Remove** modules.

### Recent Updates

- Improved module validation and type inference.
- New service backend for better performance.
- Updated frontend interface for easier management.

### Module Types

| Type | Description | File Pattern |
|------|-------------|--------------|
| Agent | Agent personae and behaviour | `agent-*.json` |
| Prompt | Prompt templates for agents | `prompt-*.json` |
| Role | User role definition | `role-*.json` |
| Tone | Tone system definitions | `tone-*.yaml` |
| Workflow Template | Pre-built workflow blueprints | `workflow-*.json` |
| LLM Profile | Language model configuration | `llm-*.yaml` |

## Assistant System

### What is the Assistant System?

The Assistant System provides an on-demand AI assistant that can help you with:
- Answering questions about the system or your data.
- Providing guidance on workflow design.
- Explaining debate results and metrics.
- Generating summaries or reports.

### Accessing the Assistant

- Click the **Assistant** icon in the top navbar.
- Or use the inline assistant button available in appropriate views.

### Using the Assistant

1. Type your question in the chat input.
2. The assistant processes it and returns a response.
3. You can ask follow-up questions within the same session.

### Configuration

- The assistant uses the system's default LLM profile (configurable in Settings > Assistant).
- You can enable/disable specific tools (e.g., web search, document retrieval) in the Assistant settings.
- Conversation history is retained for the duration of the session.

### Example Queries

- "How do I create a new blueprint?"
- "Explain the consensus score from my last debate."
- "What modules are installed?"

---

## User Accounts & Authentication

### Logging In

1. Navigate to `#/login` (the **LoginView**)
2. Enter your email and password
3. Click **Log In**

If no accounts exist yet, the first registered user is automatically assigned the **admin** role.

### Registering a New Account

1. On the login page, click **Register**
2. Enter your email, name, and password
3. Submit the form — the first user becomes admin automatically

### Default Admin Credentials

| Field | Value |
|-------|-------|
| Email | `admin@danwa.local` |
| Password | `changeme` |

> **Important**: You MUST change the default password on first login.

### Changing Your Password

1. Navigate to `#/profile` (the **Profile** view)
2. Enter your current password and your new password
3. Click **Save**

### Logging Out

Click your user avatar in the header and select **Log Out** from the dropdown menu.

### Disabling Authentication for Development

Set the environment variable `DANWA_AUTH_ENABLED=false` to bypass authentication entirely. This is intended for local development only.

---

## Tenant Management

### What Are Tenants?

Tenants are top-level organizational units in Danwa. Each tenant contains its own set of cases, users, and configuration. Users can belong to multiple tenants and switch between them.

### Switching Tenants

Use the **TenantSelector** dropdown in the header to switch between tenants you belong to. This changes the active context for all views.

### Inviting Users (Admin Only)

1. Navigate to `#/tenant-settings` (**Tenant Settings**)
2. Enter the user's email address
3. Assign a role (member or admin)
4. Click **Invite**

Only tenant admins can invite new users.

### Removing Users from a Tenant

1. Navigate to **Tenant Settings**
2. Find the user in the member list
3. Click **Remove** next to their name

### Tenant Quotas

Each tenant has resource quotas based on its plan:

| Resource | Description |
|----------|-------------|
| Projects | Maximum number of projects/cases |
| Debates | Maximum number of debates |
| Documents | Maximum number of uploaded documents |
| Storage | Maximum total storage in MB |

### Plans

| Plan | Projects | Debates | Documents | Storage |
|------|----------|---------|-----------|---------|
| **Free** | 3 | 50 | 100 | 500 MB |
| **Pro** | 20 | 500 | 1,000 | 5 GB |
| **Enterprise** | Unlimited | Unlimited | Unlimited | Unlimited |

---

## BYOK — Bring Your Own Key

### What is BYOK?

BYOK (Bring Your Own Key) allows you to use your own LLM API keys instead of the server-configured ones. This gives you direct control over LLM costs and provider selection.

### Adding a Key

1. Navigate to `#/my-keys` (**My API Keys**)
2. Select the provider (e.g., OpenRouter, OpenAI, Anthropic)
3. Enter your API key
4. Click **Save**

### Key Resolution Priority

When a debate runs, API keys are resolved in this order:

1. **Your personal key** (added via BYOK) — highest priority
2. **Server-configured key** (set by admin)
3. **Environment variable** (e.g., `OPENROUTER_API_KEY`) — lowest priority

### Deleting Keys

1. Navigate to `#/my-keys`
2. Click **Delete** next to the key you want to remove

### Key Privacy

Keys are stored per-user and are **not shared** with other users. Other tenant members cannot see or use your keys.

---

## Cases & Tags

### Cases

Cases replace projects as the primary organizational unit in Danwa. Each tenant has a collection of cases, and each case has its own independent DMS and debate storage.

#### Creating a Case

1. Navigate to **CasesView**
2. Click **+ New Case**
3. Enter a name and optional description
4. Click **Create**

#### Editing a Case

1. In **CasesView**, click on a case
2. Update the name or description
3. Click **Save**

#### Deleting a Case

1. In **CasesView**, select the case
2. Click **Delete** and confirm

> **Warning**: Deleting a case removes all associated debates and documents permanently.

### Tags

Tags are tenant-global labels for categorizing cases. They are shared across all cases within a tenant.

#### Managing Tags

1. Navigate to **Tag Manager**
2. Create, edit, or delete tags
3. Assign colors for visual distinction

#### Filtering Cases by Tags

In **CasesView**, use the tag filter dropdown to show only cases that match one or more selected tags.

---

## Transactional Drafting

### What is Transactional Drafting?

Transactional Drafting is a structured document creation workflow that uses multiple specialized agents in a collaborative pipeline to produce polished, well-reasoned documents.

### Starting a Transactional Drafting Session

1. Navigate to **Run** → **New Debate**
2. Select a **Transactional Drafting** template from the template list
3. Provide input context (topic, source documents)
4. Click **Start**

### Node Types

| Node | Role | Description |
|------|------|-------------|
| **Builder** | Creates | Generates initial draft content based on the input |
| **Pragmatist** | Evaluates | Reviews the draft for accuracy, completeness, and feasibility |
| **Angel's Advocate** | Constructive Critique | Provides constructive feedback and suggests improvements |
| **Moderator** | Consensus | Synthesizes all inputs and drives toward final consensus |

### Approval Gates

Decision edges in the workflow require explicit approval before the process can continue. When an approval gate is reached:

1. The workflow pauses
2. You review the current state
3. You approve, modify, or reject the output
4. The workflow resumes based on your decision

### Report Generation

Transactional Drafting produces structured output that can be exported using print templates:

1. Click **Generate Report** after the workflow completes
2. Choose a template and output format (DOCX or PDF)
3. Download the structured document

---

## Docker Deployment

### Quick Start

```bash
docker compose up -d
```

This starts the backend, frontend, and all required services.

### With Celery Worker

To enable background task processing (e.g., async report generation, long-running analyses):

```bash
docker compose --profile celery up -d
```

### Makefile Shortcuts

| Command | Description |
|---------|-------------|
| `make docker-build` | Build all Docker images |
| `make docker-up` | Start all containers |
| `make docker-down` | Stop and remove all containers |

### Environment Variables

1. Copy the example environment file:
   ```bash
   cp deploy/.env.example deploy/.env
   ```
2. Edit `deploy/.env` to configure API keys, database paths, and other settings

### Health Check

```bash
GET /health
```

Returns the status of all services (SQLite, Redis, Auth-DB). Use this for monitoring and load balancer configuration.

### TLS Configuration

To enable HTTPS:

1. Place your TLS certificate and key in a secure location
2. Edit `deploy/nginx.conf` to reference the certificate paths
3. Restart the nginx container

---

## Monitoring & Rate Limiting

### Health Endpoint

```
GET /health
```

Returns JSON with the status of each service:

```json
{
  "status": "ok",
  "services": {
    "sqlite": "ok",
    "redis": "ok",
    "auth_db": "ok"
  }
}
```

### Prometheus Metrics

```
GET /metrics
```

Exposes standard Prometheus-compatible metrics for scraping. Integrate with your monitoring stack (Grafana, Datadog, etc.).

### Rate Limits

| Resource | Limit | Window |
|----------|-------|--------|
| Global API | 60 requests | per minute |
| Debates | 10 requests | per hour |
| Uploads | 20 requests | per hour |
| Analysis | 5 requests | per hour |

### Handling 429 Errors

When you exceed the rate limit, the API returns a `429 Too Many Requests` response:

1. **Wait and retry** — respect the `Retry-After` header
2. **Upgrade your plan** — higher plans have higher limits

---

## HITL (Human-in-the-Loop) System

### What is HITL?

The Human-in-the-Loop (HITL) system enables direct interaction with running workflows, allowing you to:
- Query agents for clarification during execution
- Provide feedback or corrections mid-debate
- Interject at specific workflow points
- Monitor and control workflow execution in real-time

### Agent Queries

During a running workflow, you can submit queries to specific agents:

1. **Submit a Query**
   - Click **Query Agent** in the execution panel
   - Select the target agent
   - Enter your question or clarification request
   - Submit the query

2. **View Responses**
   - Agent responses appear in real-time
   - Responses are logged in the audit trail
   - You can ask follow-up questions

### Feedback Submission

Provide feedback to agents during execution:

1. **Submit Feedback**
   - Click **Provide Feedback** in the execution panel
   - Select the target agent or round
   - Enter your feedback or correction
   - Set priority (high/medium/low)

2. **Feedback Integration**
   - Feedback is injected into the agent's context
   - Agents can adjust their responses based on feedback
   - Feedback is logged for reproducibility

### Workflow Interjection

Interject at specific points in the workflow:

1. **Set Interjection Points**
   - Define interjection points in your blueprint
   - Configure interjection conditions
   - Set required human approval

2. **Respond to Interjections**
   - When workflow reaches an interjection point, it pauses
   - Review the current state
   - Approve, modify, or reject the current step
   - Workflow resumes based on your decision

### HITL Security

- **Authentication**: All HITL endpoints require authentication
- **Authorization**: Project-based access control
- **Validation**: All inputs are validated and sanitized
- **Rate Limiting**: Prevents abuse of agent queries

### API Endpoints

```
POST   /api/v1/hitl/query              # Submit agent query
GET    /api/v1/hitl/query/{id}         # Get query response
POST   /api/v1/hitl/feedback           # Submit workflow feedback
GET    /api/v1/hitl/round/{id}         # Get round status
POST   /api/v1/hitl/interject          # Interject in workflow
```

---

## Input/Output Composer

### What is the Input/Output Composer?

The Input/Output Composer is an extensible plugin system that allows you to:
- Process various input sources (audio, text, files)
- Generate multiple output formats (documents, audio, reports)
- Customize processing pipelines with plugins

### Input Composer

Access via the **Input Composer** view.

#### Supported Input Types

| Input Type | Description | Plugin |
|------------|-------------|--------|
| **Text** | Plain text input | Built-in |
| **Audio** | Speech-to-text conversion | STT Plugin |
| **File** | Document upload | Built-in |
| **API** | External API input | MCP Adapter |

#### Using the Input Composer

1. **Select Input Type**
   - Choose from available input plugins
   - Configure input parameters
   - Select target workflow

2. **Process Input**
   - Submit input job
   - Monitor processing status
   - View processed results

3. **Integration**
   - Processed input is automatically routed to workflows
   - Can be used with Blueprint system
   - Supports batch processing

### Output Composer

Access via the **Output Composer** view.

#### Supported Output Formats

| Output Type | Description | Plugin |
|-------------|-------------|--------|
| **DOCX** | Word document | Print Plugin |
| **PDF** | PDF document | Print Plugin |
| **ODF** | OpenDocument format | Print Plugin |
| **Audio (TTS)** | Text-to-speech audio | TTS Plugin |
| **Custom** | User-defined formats | Custom Plugins |

#### Using the Output Composer

1. **Select Output Format**
   - Choose from available output plugins
   - Configure output parameters
   - Select source artifact (debate session)

2. **Generate Output**
   - Submit render job
   - Monitor rendering progress
   - Download generated output

3. **TTS Features**
   - Multiple voice profiles
   - Adjustable speech rate and pitch
   - Multi-language support
   - Batch audio generation

### Print Plugin

The Print Plugin generates professional documents:

**Features:**
- Custom layouts via Jinja2 templates
- Multi-language support (German/English)
- Audit trail inclusion
- Metadata tables
- Styled formatting

**Configuration:**
```yaml
output:
  format: docx  # docx | pdf | odf
  template: default
  include_audit: true
  language: en
```

### TTS Plugin

The TTS Plugin converts text to speech:

**Renderers:**
- **MIMO TTS**: Multi-modal text-to-speech
- **Edge TTS**: Edge-based text-to-speech

**Features:**
- Voice profile management
- Script engine for custom TTS scripts
- Audio format selection (MP3, WAV)
- Batch processing

### API Endpoints

```
POST   /api/v1/input/compose           # Submit input job
GET    /api/v1/input/jobs/{id}        # Get input job status
POST   /api/v1/output/compose          # Submit output job
GET    /api/v1/output/jobs/{id}       # Get output job status
GET    /api/v1/output/plugins          # List output plugins
GET    /api/v1/input/plugins           # List input plugins
```

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

## A2A Protocol Integration

### What is A2A?

The A2A (Agent-to-Agent) protocol allows Danwa to communicate with external AI agents. This enables:

- **External agents as debate participants**: Add external AI agents to your debates alongside the built-in strategist, critic, optimizer, and moderator
- **Danwa as a service**: External agents can create and run debates on Danwa via the A2A protocol

### Using A2A Agents in Debates

When creating a debate, you can add external A2A agents in the **A2A Agents** section of the debate form:

1. Click **+ Add A2A Agent** in the debate configuration
2. Enter the **Agent URL** (e.g., `https://external-agent.example.com/a2a`)
3. Optionally set a **Role** (default: `external_reviewer`)
4. Optionally set a **Position** (default: `after:moderator`)

The position controls when the external agent participates:
- `after:moderator` — after all standard agents complete their rounds
- `after:strategist` — after the strategist agent
- `before:critic` — before the critic agent

### A2A in the Workflow Graph

When A2A agents are configured, the workflow graph shows a purple **A2A** node after the standard agent nodes. This node indicates when the external agent is being invoked and displays its status.

### A2A Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /.well-known/agent.json` | Agent Card discovery (A2A spec) |
| `POST /a2a` | JSON-RPC endpoint for task management |

### Connecting External Agents

To connect an external A2A agent:

1. Ensure the external agent supports the A2A protocol
2. Get the agent's A2A endpoint URL
3. Add it to your debate configuration or to `config/a2a.json`

For testing, you can use Danwa itself as an external agent by pointing to its `/.well-known/agent.json` endpoint.

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
| A2ANode | External A2A agent participation (purple-themed) |
| DecisionNode | Consensus check, round continuation |
| HistoryNode | Past round summaries |
| ArtifactNode | Final output, reports |
| UserActionNode | OOB input points |

---

## Unified Feedback System

Danwa provides a **unified, non-intrusive feedback system** that keeps you informed about what the backend is doing at every moment during workflow execution — without interrupting your work.

### What You See

#### Status Bar

When a workflow is running, a thin **status bar** appears below the header showing:
- 🔄 **Spinner** with color coding: amber for LLM calls, cyan for layout, blue for workflow
- **Current operation**: e.g., "LLM calling GPT-4o…"
- **Elapsed time** for the current operation
- A ⚠ **slow warning** appears if an operation exceeds 15 seconds

The status bar automatically disappears when the operation completes.

#### Agent Node Indicators

Each agent node in the workflow graph shows:
- A **spinning indicator** while waiting for an LLM response
- The **model name** being called (e.g., "gpt-4o")
- A **red error badge** (❌) if the agent fails
- A **red glow** on the node border for failed states

#### Error Panel

When errors occur (LLM failures, network issues), a **floating error panel** appears with:
- **Classified error type** with icon:
  - ⏱ **Rate Limit** — "Model is busy — switching to backup model…"
  - ⌛ **Timeout** — "LLM response took too long — retrying…"
  - 🛡 **Content Filter** — "Response was filtered — adjusting and retrying…"
  - 🌐 **Network** — "Connection issue — retrying…"
  - ⚠ **Unknown** — "Something went wrong — please try again"
- **Copy error details** button for debugging
- **Dismiss** button to remove individual errors or dismiss all

#### Activity Log Panel

A **collapsible activity log** at the bottom of the screen tracks all workflow events:

- **Toggle**: Click the activity log tab or press `Ctrl+Shift+L`
- **Filter by type**: LLM, workflow, node, system, or error
- **Auto-scrolls** to the latest entry
- **Export** to clipboard as JSON (includes request ID for debugging)
- **Clear** to reset the log

Each entry is automatically tagged with a **request ID** for correlation across the full workflow lifecycle.

#### Layout Feedback

When the workflow graph layout is being computed:
- A **spinner overlay** appears in the top-right corner of the canvas
- If layout computation fails, an **error overlay** with details is shown

### Error Classification

LLM errors are automatically classified and presented with actionable messages:

| Error Class | Icon | What It Means | What Happens |
|---|---|---|---|
| Rate Limit | ⏱ | Too many requests to the LLM provider | System retries or uses backup model |
| Timeout | ⌛ | LLM took too long to respond | System retries the request |
| Content Filter | 🛡 | Response was blocked by safety filters | System adjusts and retries |
| Network | 🌐 | Connection to LLM provider failed | System retries with backoff |
| Unknown | ⚠ | Unexpected error | Details available in error panel |

### Request ID Correlation

Every workflow run is assigned a **request ID** (UUID) that appears in:
- All SSE events from the backend
- Activity log entries
- Exported log JSON

This enables end-to-end traceability from the UI back to backend logs.

---

## Internationalization (i18n)

### Supported Languages

Danwa supports **14 languages** with full UI translation:

| Code | Language | Script | Direction |
|------|----------|--------|-----------|
| de | Deutsch | Latin | LTR |
| en | English | Latin | LTR |
| fr | Français | Latin | LTR |
| es | Español | Latin | LTR |
| it | Italiano | Latin | LTR |
| pt | Português (BR) | Latin | LTR |
| ru | Русский | Cyrillic | LTR |
| zh | 中文 (简体) | CJK | LTR |
| ja | 日本語 | CJK | LTR |
| ko | 한국어 | Hangul | LTR |
| sv | Svenska | Latin | LTR |
| el | Ελληνικά | Greek | LTR |
| ar | العربية | Arabic | RTL |
| he | עברית | Hebrew | RTL |

### Switching Languages

#### UI Language

Use the **Language Switcher** in the header to toggle between all 14 supported languages. The Language Switcher includes:
- Search field for quick language finding
- Display format: "Language Name (code)" e.g., "Deutsch (de)", "中文 (zh)"
- RTL languages are clearly marked
- Selection is persisted to `localStorage`

#### Debate Language

Set the debate language in the **Debate View** or **Config View**:
- Affects prompt templates used (e.g., `strategist.md` vs `strategist-en.md`)
- Affects LLM response language (instructed via prompt)

#### Per-Project Language

Each project can have its own default language setting:
- Go to **Projects** → Select project → **Settings**
- Set the default language for new debates in this project

### Translation Files

```
frontend/src/lib/i18n/loaders/
├── en.js           # English translations (808 keys)
├── de.js           # German translations (808 keys)
├── fr.js           # French translations (808 keys)
├── es.js           # Spanish translations (808 keys)
├── it.js           # Italian translations (808 keys)
├── pt.js           # Portuguese (BR) translations (808 keys)
├── ru.js           # Russian translations (808 keys)
├── zh.js           # Chinese (Simplified) translations (808 keys)
├── ja.js           # Japanese translations (808 keys)
├── ko.js           # Korean translations (808 keys)
├── sv.js           # Swedish translations (808 keys)
├── el.js           # Greek translations (808 keys)
├── ar.js           # Arabic translations (808 keys, RTL)
└── he.js           # Hebrew translations (808 keys, RTL)
```

### RTL (Right-to-Left) Support

Arabic (ar) and Hebrew (he) are RTL languages. The UI automatically:
- Mirrors the layout direction
- Uses CSS Logical Properties for proper spacing
- Adjusts text alignment
- Handles bidirectional text (BiDi) for mixed content

### Backend Translation Management

Danwa includes a backend translation API for managing translations:
- View translation coverage per language
- Add or edit translations manually
- Use LLM for bulk translation of missing keys
- Track translation source (manual, LLM-generated, reviewed)

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

## Missing Links (Features Not Yet in UI)

> **Note**: These are features fully implemented in the backend but **not yet accessible through the user interface**.
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

### Legacy Session History

The legacy `backend/api/routers/sessions.py` router provides endpoints (superseded by newer workflow_exec/workflow_reports routers):

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/sessions/` | List debate sessions (with filters) |
| `GET /api/v1/sessions/{id}` | Get single session |
| `DELETE /api/v1/sessions/{id}` | Delete session |
| `GET /api/v1/sessions/{id}/trace` | Get audit trace |

**What's missing**: No frontend API functions or UI for this legacy router. This is intentionally not exposed as it's superseded by newer routers.

### Report SSE Progress Stream

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/sessions/{session_id}/report/stream` | SSE progress stream for report generation |

**What's missing**: `createReportSSE()` exists in `api.js` but is not consumed in any view. Report generation is functional without this progress indicator.

### Project-Level Settings Override

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/config/settings/project/{id}` | Get project-overridden settings |

**What's missing**: No frontend API function or UI for project-level settings overrides. i18n string exists (`projects.configHint`) but no implementation.

### Summary Table

| Feature | Backend | API Client | UI | Status |
|---------|---------|------------|-----|--------|
| Legacy Session History | ✅ | ❌ Missing | ❌ Missing | **Not exposed (superseded)** |
| Report SSE Progress Stream | ✅ | ✅ Exists | ❌ Missing | **Not exposed (low priority)** |
| Project-Level Settings Override | ✅ | ❌ Missing | ❌ Missing | **Not exposed** |
| RAG Document Toggle | ✅ | ✅ | ✅ | Exposed |
| Debate Workflow | ✅ | ✅ | ✅ | Exposed |
| Config (LLM/Agents/Prompts) | ✅ | ✅ | ✅ | Exposed |
| HITL Interactions | ✅ | ✅ | ✅ | Exposed |
| A2A in Debates | ✅ | ✅ | ✅ | Exposed |
| Blueprint System | ✅ | ✅ | ✅ | Exposed |
| Input/Output Composer | ✅ | ✅ | ✅ | Exposed |
| Replay & Diff Views | ✅ | ✅ | ✅ | Exposed |

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

#### "429 Too Many Requests"

- **Cause**: Rate limit exceeded (global: 60/min, debates: 10/hour, uploads: 20/hour, analysis: 5/hour)
- **Fix**: Wait for the rate limit window to reset (check the `Retry-After` header), or upgrade your plan for higher limits

#### "401 Unauthorized"

- **Cause**: Session expired or invalid credentials
- **Fix**: Log in again at `#/login`. If using API tokens, generate a new one

#### "403 Forbidden"

- **Cause**: You are not a member of the requested tenant, or lack the required role
- **Fix**: Ask a tenant admin to invite you, or switch to a tenant you belong to

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

## Case-Space Workspace (Walkthrough)

The Case-Space redesign (released 2026-06-15) replaces the
previous six-fragment navigation with three coherent entry
points: **Workspace** (your active case), **Inbox** (open
tasks), and **Browse** (global overview with optional graph
view).  The technical structure (CasesView, DocumentsView,
TagManagerView, etc.) remains accessible for power users but
is no longer the default landing path.

### What's new for end users

- **Active Case is mandatory** — every action is anchored to
  one case.  The case selector in the header is highlighted
  in blue when active.
- **Welcome Card** for first-time users — three click paths
  (create case → upload docs → start debate), no modal wizard.
- **Workspace** shows a 3-card view of the active case: This
  Case, Suggested Next Steps, Recent Activity (with Phase +
  Round columns from the audit log).
- **Inbox** surfaces untagged debates, recently-completed
  debates, and stale running debates.  Bulk move/tag/archive
  actions.
- **Browse** has a List/Graph toggle — graph mode uses
  Cytoscape.js for the tenant-wide knowledge graph, list
  mode is the default.

### 90-second walkthrough script

A full walkthrough with voice-over annotations is available
in [`2026-06-15_case-space-walkthrough.md`](2026-06-15_case-space-walkthrough.md).
The document is structured as 7 film sequences that together
cover 80% of typical user paths in 90 seconds:

1. **First login** — Welcome Card appears for empty tenants
2. **Create your first case** — Inline form, auto-active
3. **Work in the Workspace** — Three cards: This Case, Suggested, Recent
4. **Disambiguated debate creation** — Modal forces a case choice
5. **Inbox as task list** — Tabs + bulk actions
6. **Browse with graph toggle** — Power-user view
7. **URL deep-linking** — Shareable workspace URLs

### Feature flags

All three case-space feature flags are `True` by default since
the rollout commit (2026-06-15).  To opt out (e.g. for a
legacy-only deployment), set the corresponding env var:

```bash
DANWA_ENABLE_CASE_SPACE=false          # disables workspace + inbox
DANWA_ENABLE_CASE_SPACE_INBOX=false    # disables inbox only
DANWA_ENABLE_CASE_SPACE_GRAPH=false    # disables graph view
```

### Related documents

- [2026-06-14_case-space-walkthrough.md](2026-06-15_case-space-walkthrough.md)
  — 90-second walkthrough script
- [2026-06-15_case-space-metrics.md](../plans/2026-06-15_case-space-metrics.md)
  — metrics catalogue (Phase 6.3)
- [plans/2026-06-14_case-space-workspace.md](../plans/2026-06-14_case-space-workspace.md)
  — original concept document
- [plans/2026-06-14_case-space-impl-todos.md](../plans/2026-06-14_case-space-impl-todos.md)
  — implementation todo with per-phase status

---

*Documentation generated for Danwa v2.3.0 — 2026-06-08*
*Updated 2026-06-15: Case-Space Walkthrough chapter added.*
