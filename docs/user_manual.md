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
12. [Session Management Dashboard](#session-management-dashboard)
13. [Document Management System (DMS)](#document-management-system-dms)
14. [Privacy & Data Protection](#privacy--data-protection)
15. [Audit & Reproducibility](#audit--reproducibility)
16. [Advanced Configuration](#advanced-configuration)
17. [Troubleshooting](#troubleshooting)

---

## Overview

Debate-Agent is an auditable multi-agent debate workflow system that uses multiple AI agents to analyze, critique, and optimize arguments around a given topic or problem. The system employs a structured four-stage debate process (Strategist → Critic → Optimizer → Moderator) to arrive at well-reasoned conclusions with measurable consensus scores.

### Key Capabilities

- **Multi-Agent Deliberation**: Four specialized AI agents collaborate to produce high-quality analysis
- **LLM Flexibility**: Supports local models (via LM Studio) and cloud providers (via OpenRouter)
- **Document Analysis**: Upload and analyze PDF, DOCX, ODT, ODS, and ODP files
- **Web Validation**: Optional fact-checking via SearXNG integration
- **Semantic Memory**: ChromaDB-powered precedent retrieval from past debates
- **Audit Trail**: Complete JSONL trace logs for reproducibility
- **Report Generation**: Export results as DOCX or PDF
- **Privacy Protection**: Built-in PII redaction and data retention policies
- **Session Management**: SQLite-backed session storage with dashboard interface

### Technology Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.11+ |
| **UI Framework** | Chainlit |
| **LLM Integration** | LiteLLM (multi-provider routing) |
| **Vector Database** | ChromaDB |
| **Web Search** | SearXNG / DuckDuckGo |
| **Document Parsing** | pdfplumber, pypdf, python-docx, odfpy |
| **Report Generation** | python-docx, WeasyPrint |
| **Database** | SQLite |
| **Package Management** | uv |

---

## Installation & Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
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
3. Install all dependencies from `pyproject.toml`

### Manual Setup

If you prefer manual installation:

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -e .
```

### Verify Installation

```bash
uv run python -c "import chainlit, litellm, chromadb; print('All dependencies installed')"
```

---

## Configuration

The system uses YAML configuration files located in the `config/` directory.

### LLM Profiles (`config/llm_profiles.yaml`)

Defines available LLM backends:

```yaml
profiles:
  local_qwen:
    model: "qwen2.5-7b"
    base_url: "http://localhost:1234/v1"
    api_key_env: "LM_STUDIO_KEY"
    params: { temperature: 0.4, top_p: 0.9, seed: 42 }
  cloud_openrouter:
    model: "anthropic/claude-3-5-sonnet"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_KEY"
    params: { temperature: 0.6, top_p: 0.95, seed: null }
  cloud_qwen:
    model: "qwen/qwen-plus"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_KEY"
    params: { temperature: 0.5, top_p: 0.9, seed: 123 }
```

**Profile Parameters:**
- `model`: Model identifier (LiteLLM format)
- `base_url`: API endpoint
- `api_key_env`: Environment variable containing API key
- `params`: Model-specific parameters (temperature, top_p, seed)

### Application Settings (`config/settings.yaml`)

```yaml
search:
  engine: "searxng"
  url: "http://127.0.0.1:8080"
  max_results: 5

privacy:
  strict_mode: false          # true = blocks all external calls, local LLMs only
  redact_traces: true         # PII redaction in JSONL logs
  retention_days: 90          # Auto-cleanup old sessions/reports
```

### Prompt Variants (`config/prompt_variants.yaml`)

Configure different prompt strategies:

```yaml
default_variant: "A"
variants:
  A:
    strategist: "prompts/strategist.md"
    critic: "prompts/critic.md"
    optimizer: "prompts/optimizer.md"
    moderator: "prompts/moderator.md"
  B:
    strategist: "prompts/strategist_v2.md"
    critic: "prompts/critic.md"
    optimizer: "prompts/optimizer.md"
    moderator: "prompts/moderator_v2.md"
```

### Agent Prompts (`config/prompts/`)

Customize agent behavior by editing prompt files:
- `strategist.md` - Strategy development agent
- `critic.md` - Critical review agent
- `optimizer.md` - Synthesis and refinement agent
- `moderator.md` - Consensus evaluation agent

Prompts support versioning via a `version:` header in the file.

---

## Getting Started

### Starting the Application

```bash
cd /media/data/coding/danwa
uv run chainlit run src/ui/chainlit_app.py --port 7860
```

The application will be available at `http://localhost:7860`.

### First Run

1. Open your browser to `http://localhost:7860`
2. Configure your settings (see [User Interface Guide](#user-interface-guide))
3. Type your topic or upload documents
4. Review the multi-agent analysis results
5. Download reports or view the audit trace

---

## User Interface Guide

### Chat Interface

The main interface is a chat-based UI powered by Chainlit:

```
┌─────────────────────────────────────────────────────┐
│  🤝 Multi-Agent Debatten-System bereit.            │
│  [📊 Dashboard öffnen]                            │
└─────────────────────────────────────────────────────┘

You: Analyze the impact of AI on education...

🔄 agent: Strategist
🔄 agent: Critic
🔄 agent: Optimizer
🔄 tool: Web-Validierung
🔄 agent: Moderator

## Ergebnis (Variante: A, Konsens: 0.85)

[Analysis output...]

📄 Vollständiger Audit-Trace: [full_trace.json]
📥 Reports generiert: [report.docx] [report.pdf]
```

### Chat Settings

Access via the settings icon or automatically shown on start:

| Setting | Description | Default |
|---------|-------------|---------|
| **LLM-Profil** | Select LLM backend | `local_lm_studio` |
| **Max. Runden** | Number of debate rounds (1-5) | 3 |
| **Konsens-Schwelle** | Target consensus threshold (0.5-1.0) | 0.75 |
| **Web-Validierung aktivieren** | Enable fact-checking | true |
| **Präzedenz-Speicher aktivieren** | Enable semantic memory | true |
| **Prompt-Variante** | Prompt strategy (A/B/auto) | auto |

### Progress Indicators

During debate execution, you'll see real-time progress:

- `🔄 start: Initialisiere Debatte...`
- `🔄 round: Runde 1/3`
- `🔄 agent: Strategist`
- `🔄 agent: Critic`
- `🔄 agent: Optimizer`
- `🔄 tool: Web-Validierung`
- `🔄 agent: Moderator`

---

## Core Features

### Multi-Agent Debate Workflow

The system orchestrates four specialized agents in a structured debate:

```
Input → [Strategist] → [Critic] → [Optimizer] → [Moderator]
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

**Temperature**: 0.4 (balanced creativity)

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

**Temperature**: 0.8 (high creativity for diverse critiques)

### 3. Optimizer Agent

**Role**: Synthesis and precision specialist

**Tasks**:
- Integrate strategy and criticism
- Produce coherent, court-ready formulation
- Sharpen phrasing, remove redundancies
- Establish clear causalities
- Mark remaining uncertainties

**Output Format**: Final argumentation structure with clear organization, source references, and transparent residual risks.

**Temperature**: 0.3 (focused, precise)

### 4. Moderator Agent

**Role**: Neutral evaluation and control agent

**Tasks**:
- Verify optimized version addresses original problem
- Evaluate consensus between strategy and criticism
- Score on 0.0-1.0 scale

**Output**: Single decimal number (e.g., `0.85`)

**Temperature**: 0.2 (deterministic)

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

1. Click the file upload button in the chat
2. Select one or more documents (multiple supported)
3. The system will parse and extract text automatically
4. Parsed content is added to the debate context

### Text Extraction

- **PDF**: Extracts text from all pages using pdfplumber; falls back to pypdf
- **DOCX**: Extracts paragraph text
- **ODF**: Uses odfpy's teletype extraction
- **Others**: Reads as plain text with UTF-8 encoding

### Context Protection

- Maximum context length: **25,000 characters**
- Documents exceeding this limit are truncated with a warning
- Metadata includes: source filename, extension, page count, word count, character count

### Metadata Captured

```python
{
    "source": "document.pdf",
    "extension": ".pdf",
    "pages": 5,
    "word_count": 1250,
    "char_count": 7800,
    "truncated": false  # or true
}
```

---

## Web Search & Fact Checking

### Overview

When enabled, the system performs automated fact-checking by:
1. Extracting 3 key claims from the current draft
2. Searching the web for each claim
3. Returning evidence snippets for validation

### Search Engine Configuration

**Primary**: SearXNG (self-hosted, privacy-friendly)

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

### Claim Extraction

The system uses a dedicated LLM call to extract 3 verifiable claims:

```
Extrahiere aus folgendem Text maximal 3 konkrete, überprüfbare Behauptungen oder Fakten.
Antworte NUR mit einer JSON-Liste von Strings. Beispiel: ["Behauptung 1", "Behauptung 2"]
```

### Validation Report

Results are structured as:

```python
[
    {
        "claim": "AI improves learning outcomes by 30%",
        "evidence": [
            {"title": "...", "url": "...", "snippet": "...", "engine": "google"}
        ]
    }
]
```

### Error Handling

- Failed searches return empty results (non-blocking)
- Search errors are logged but don't stop the debate
- Configurable `max_results` per claim (default: 5)

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

### Precedent Search

When a new debate starts:

```python
precedents = memory.search_precedents(context, top_k=2)
```

Search considers:
- **Context relevance**: Semantic similarity to current topic
- **Consensus score**: Higher consensus precedents are more valuable
- **Recency**: Timestamp metadata available

### Precedent Injection

Relevant precedents are formatted and injected into the context:

```
Relevante Präzedenzfälle aus früheren Debatten:
1. Konsens: 0.85 | Relevanz: 0.92
   [Precedent text preview...]
2. Konsens: 0.75 | Relevanz: 0.88
   [Precedent text preview...]
```

### Storage Format

Each debate is stored with:

```python
{
    "documents": ["Thema/Kontext: ...\nKonsens-Score: ...\nErgebnis: ..."],
    "metadatas": [{
        "session_id": "abc123",
        "consensus": 0.85,
        "timestamp": "2024-01-15T10:30:00",
        "rounds": 3,
        "validated": true
    }],
    "ids": ["abc123"]
}
```

### Managing Memory

- Memory is automatically populated after each debate
- To clear: Delete `memory/chroma_db/` directory
- View stored count: Check logs for "📦 Memory geladen: N Präzedenzfälle"

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
2. **Metadata Table**:
   - Creation date
   - Rounds completed
   - Final consensus score
   - External validation status
   - Precedents consulted

3. **Sachverhalt (Input)**: First 1200 characters of input context

4. **Final Argumentation**: Complete optimized output

5. **External Fact Check** (if enabled):
   - Claims made
   - Evidence snippets (top 2 per claim)

6. **Audit Reference**:
   - Trace file location: `logs/{session_id}.jsonl`
   - Prompt versions used
   - Generation timestamp

### Automatic Generation

Reports are generated automatically after each debate and provided as downloadable files in the chat interface.

### Customization

**DOCX Styling** (in `report_generator.py`):
- Font: Calibri
- Headings: Numbered levels
- Metadata: 5×2 table

**PDF Styling** (CSS in `report_generator.py`):
- Font: DejaVu Sans / Segoe UI
- Margins: 2.5cm
- Color scheme: Dark blue headers (#1a365d)
- Footer: Audit trace reference

---

## Session Management Dashboard

### Accessing the Dashboard

Click "📊 Dashboard öffnen" at the start of a session, or trigger via the action button.

### Dashboard Features

```
## 📊 Sitzungsverwaltung (Seite 1)

**Einträge:** 10 | **Filter:** Alle

[📊 Session ab12cd... | 2024-01-15 10:30 | Konsens: 0.85 | local_qwen]
Input preview...

[📄 Trace] [🗑️ Löschen] [📥 Report]
```

### Session List

Displays up to 10 sessions per page:
- Session ID (truncated to 8 chars)
- Creation timestamp
- Consensus score
- LLM profile used
- Context preview (first 90 chars)

### Dashboard Actions

| Action | Description |
|--------|-------------|
| **📄 Trace** | Load and display the complete JSONL audit trace |
| **🗑️ Löschen** | Delete session from database and remove associated files |
| **📥 Report** | Download generated reports (DOCX, PDF) |
| **🔍 Nur ≥0.8** | Toggle filter to show only high-consensus sessions |
| **⬅️ Zurück** | Previous page |
| **➡️ Weiter** | Next page |
| **🗑️ Bereinigen** | Run cleanup: delete sessions >90 days old |

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
The Document Management System (DMS) provides project-wise document organization, intelligent chunking, and retrieval-augmented generation (RAG) capabilities. It allows you to create projects, upload documents (including scanned PDFs via OCR), and automatically retrieve relevant document context during debates.

### Creating Projects and Uploading Documents
1. Access the DMS Dashboard (see below)
2. Create a new project with name and optional description
3. Upload documents to the project (supports PDF, DOCX, ODT, ODS, ODP, TXT)
4. Documents are automatically chunked and indexed for RAG retrieval

Example DMS API usage:
```python
from src.dms.dms import DMS

dms = DMS()
project_id = dms.create_project(name="AI Research", description="Project for AI-related documents")
doc_id = dms.upload_document(project_id, "research_paper.pdf")
```

### RAG Context in Debates
During debates, the system automatically retrieves relevant document chunks from DMS projects to augment context. You can:
- Auto-retrieve context for debate topics
- Manually add specific documents to RAG context
- Retrieve top k relevant chunks for any query

Example RAG retrieval:
```python
# Retrieve context for a debate topic
chunks = dms.auto_retrieve_for_topic("AI in education", project_id=project_id, k=5)
for chunk in chunks:
    print(f"Source: {chunk['source']}, Preview: {chunk['text'][:100]}...")
```

### PaddleOCR Integration
For scanned documents or image-based PDFs, DMS supports PaddleOCR for text extraction. PaddleOCR is optional:
- Install CPU version: `bash scripts/setup_dms.sh`
- Install GPU version: `bash scripts/setup_dms.sh --gpu`
- Enable OCR in `config/settings.yaml`: `dms.ocr_enabled: true`

OCR is disabled by default to avoid unnecessary dependencies.

### DMS Dashboard
Access the DMS dashboard via Chainlit:
1. Start the app: `uv run chainlit run src/ui/chainlit_app.py --port 7860`
2. Click "📂 DMS Dashboard" in the chat interface
3. Features:
   - List/create/delete projects
   - Upload/list/delete project documents
   - View document metadata and chunk counts
   - Toggle OCR processing for uploads

### Configuration
Configure DMS in `config/settings.yaml` under the `dms:` section:
```yaml
dms:
  enabled: true                # Enable/disable DMS
  storage_path: "dms_storage"  # DMS data storage path
  chunk_size: 512              # Max characters per text chunk
  chunk_overlap: 51            # Chunk overlap for context preservation
  embedding_model: "intfloat/multilingual-e5-small"  # Embedding model
  ocr_enabled: false           # Enable PaddleOCR for scanned docs
  ocr_device: "cpu"            # OCR device (cpu/gpu)
  max_file_size_mb: 50         # Max upload file size (MB)
  chroma_collection: "document_chunks"  # ChromaDB collection name
```

**Config Parameters:**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `enabled` | Toggle DMS feature | `true` |
| `storage_path` | Path for DMS database and files | `dms_storage` |
| `chunk_size` | Max characters per text chunk | `512` |
| `chunk_overlap` | Overlap between chunks | `51` |
| `embedding_model` | Sentence-transformers embedding model | `intfloat/multilingual-e5-small` |
| `ocr_enabled` | Enable PaddleOCR | `false` |
| `ocr_device` | OCR processing device | `cpu` |
| `max_file_size_mb` | Maximum document size | `50` |
| `chroma_collection` | ChromaDB collection for DMS chunks | `document_chunks` |

---

## Privacy & Data Protection

### Privacy Guard Features

The `PrivacyGuard` class provides GDPR-compliant data protection:

### PII (Personally Identifiable Information) Redaction

Automatically redacts:
- **Email addresses**: `[REDACTED_EMAIL]`
- **IPv4 addresses**: `[REDACTED_IPV4]`
- **German phone numbers**: `[REDACTED_PHONE_DE]`
- **ID numbers** (passport/ID card): `[REDACTED_ID_NUMBER]`

Redaction is applied to:
- Trace logs (`logs/*.jsonl`)
- Enabled via `redact_traces: true` in settings

### Strict Mode

When `strict_mode: true` in `config/settings.yaml`:
- **All external calls blocked** (web search, cloud LLMs)
- Only local LLMs can be used
- Useful for sensitive data processing

### Data Retention Policy

Configured via `retention_days` (default: 90 days):

Automatically deletes:
- Log files older than retention period
- Report files older than retention period
- ChromaDB entries (requires manual cleanup)

### Manual Cleanup

Use the dashboard's "🗑️ Bereinigen" button or:

```python
from src.core.privacy import PrivacyGuard
PrivacyGuard(retention_days=90).enforce_retention()
```

This removes files from:
- `logs/`
- `reports/`
- `memory/chroma_db/`

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
    "prompt_variant": "A",
    "prompt_version": "v1.2",
    "prompt_hash": "a3f2b1c4d5e6f7a8",
    "prompt_preview": "Du bist ein erfahrener Strategie-Entwickler...",
    "response_preview": "1. Problemkern: ...",
    "metadata": {"tokens": 1250},
    "response_full": "Complete agent response..."
}
```

### Prompt Versioning

Each prompt file can include a version header:

```markdown
version: v1.2

Du bist ein erfahrener Strategie-Entwickler...
```

The system:
- Extracts version automatically via regex
- Computes SHA256 hash of prompt content
- Records both in trace logs
- Supports hot-reload on file modification (mtime-based)

### Variant Assignment

When `variant: "auto"` is selected:
- Session ID is hashed (MD5)
- Variant is assigned deterministically
- Same session ID always gets same variant
- Enables A/B testing of prompt strategies

### Trace Download

Traces are available for download after each debate:
- Click "📄 Vollständiger Audit-Trace:"
- JSON file opens in-browser or downloads
- Contains complete agent interactions for reproducibility

---

## Advanced Configuration

### Temperature by Role

Default temperatures (configurable in `debate_engine.py`):

```python
ROLE_TEMPS = {
    "strategist": 0.4,   # Balanced creativity
    "critic": 0.8,       # High creativity for diverse critiques
    "optimizer": 0.3,    # Focused precision
    "moderator": 0.2      # Deterministic scoring
}
```

### Prompt Hot-Reload

Prompts are cached with mtime tracking:
- Modified prompts are automatically reloaded
- No restart required
- Cache key: `{role}_{variant}`
- Thread-safe with reentrant lock

### Custom LLM Parameters

Override per-profile in `llm_profiles.yaml`:

```yaml
my_profile:
  model: "custom/model"
  base_url: "http://localhost:8000/v1"
  api_key_env: "MY_API_KEY"
  params:
    temperature: 0.5
    top_p: 0.9
    seed: 42
    max_tokens: 2048    # Additional LiteLLM parameters
    frequency_penalty: 0.1
```

### Environment Variables

Set API keys as environment variables:

```bash
export LM_STUDIO_KEY="your_key_here"
export OPENROUTER_KEY="your_openrouter_key"
```

---

## Troubleshooting

### Common Issues

#### "LiteLLM error: Connection refused"
- **Cause**: Local LLM (LM Studio) not running
- **Fix**: Start LM Studio and load a model, or switch to a cloud profile

#### "SearXNG request failed"
- **Cause**: SearXNG not running or wrong URL
- **Fix**: Verify `config/settings.yaml` has correct `search.url`, or disable fact-checking

#### "Prompt-Datei fehlt"
- **Cause**: Prompt file referenced in `prompt_variants.yaml` doesn't exist
- **Fix**: Check that all prompt paths in variants exist in `config/prompts/`

#### "Memory-Speicherung fehlgeschlagen"
- **Cause**: ChromaDB initialization error
- **Fix**: Delete `memory/chroma_db/` and restart (will be recreated)

#### "Parsing fehlgeschlagen"
- **Cause**: Unsupported file format or corrupted file
- **Fix**: Convert to supported format, or system falls back to plain text

### Logs

- **Application logs**: Check Chainlit output in terminal
- **File logs**: `logs/app.jsonl` (if configured)
- **Debate traces**: `logs/{session_id}.jsonl`

### Getting Help

1. Check the terminal output for Python tracebacks
2. Verify `config/settings.yaml` and `config/llm_profiles.yaml` syntax
3. Ensure all dependencies are installed: `uv pip list`
4. Check that LM Studio (if used) is running and has a model loaded

---

## Project Structure Reference

```
danwa/
├── src/
│   ├── core/                    # Business logic
│   │   ├── debate_engine.py     # Main orchestration
│   │   ├── llm_router.py        # LLM provider routing
│   │   ├── memory.py            # ChromaDB vector storage
│   │   ├── session_db.py        # SQLite persistence
│   │   ├── prompt_manager.py    # Prompt variant management
│   │   ├── prompt_registry.py   # Prompt registry
│   │   ├── privacy.py           # PII redaction & retention
│   │   ├── trace_logger.py      # JSONL audit logs
│   │   ├── custom_embedding.py  # Custom embeddings
│   │   └── logging_config.py    # Logging setup
│   ├── tools/                   # External integrations
│   │   ├── doc_parser.py       # PDF/Word/ODF parsing
│   │   ├── report_generator.py  # DOCX/PDF generation
│   │   └── web_search.py       # SearXNG/DuckDuckGo
│   └── ui/                      # Presentation layer
│       ├── chainlit_app.py      # Main Chainlit entry point
│       └── dashboard.py         # Session management UI
├── config/                       # Configuration files
│   ├── llm_profiles.yaml       # LLM backend definitions
│   ├── settings.yaml           # App settings
│   ├── prompt_variants.yaml    # Variant mappings
│   └── prompts/                # Agent prompt templates
│       ├── strategist.md
│       ├── critic.md
│       ├── optimizer.md
│       ├── moderator.md
│       ├── strategist_v2.md
│       └── moderator_v2.md
├── tests/                        # Pytest test suite
├── docs/                         # Documentation
├── scripts/                      # Utility scripts (start.sh, stop.sh, status.sh, cleanup.sh)
├── memory/                       # Runtime data
│   ├── debates.db               # SQLite database
│   └── chroma_db/              # ChromaDB vector store
├── logs/                         # Debate trace logs
├── reports/                      # Generated reports
├── pyproject.toml               # Project metadata & deps
├── Makefile                     # Dev workflow automation
└── setup.sh                     # Quick setup script
```

---

*Documentation generated for Debate-Agent v0.1.0*
