# Danwa User Manual

## Introduction

Danwa is a multi-agent debate platform that enables you to orchestrate discussions between AI agents (Strategist, Critic, Optimizer, Moderator) to analyze cases, reach consensus, and produce well-reasoned conclusions.

This manual covers all user-facing features. For technical details, see [technical_documentation.md](./technical_documentation.md).

## Getting Started

### Prerequisites

- A running Danwa backend (typically at `http://localhost:8000`)
- A web browser (Chrome, Firefox, Edge, Safari)

### Initial Setup

1. Open the application in your browser
2. Create your first project via the **Projects** navigation item
3. Select the project from the dropdown in the sidebar
4. Optionally configure LLM profiles and agent personas in **Configuration**

## Navigation

The sidebar provides access to all main sections:

| Icon | Section | Purpose |
|------|---------|---------|
| 📊 | Dashboard | Overview, stats, recent debates |
| 💬 | Debate | Create and run debates |
| 🧩 | Blueprint Canvas | Visual workflow builder |
| 📄 | Documents | Upload and manage documents for RAG |
| 📚 | Archive | Browse completed debates |
| 📋 | Audit Trail | View event logs |
| 📁 | Projects | Manage projects |
| ⚙️ | Configuration | Configure LLM profiles, agents, prompts |

## Core Features

### 1. Creating a Debate

1. Navigate to **Debate** (💬)
2. Enter a case description in the text field
3. Optionally configure:
   - **Max Rounds**: Maximum discussion rounds (default: 5)
   - **Consensus Threshold**: Required agreement level (default: 90%)
   - **Search Mode**: Web search behavior (off/optional/required)
4. Click **Create Debate**
5. Click **Start Debate** to begin execution

### 2. Monitoring a Debate

During execution, the debate view shows:

- **Status**: Running, Paused, Completed, Failed
- **Current Round**: Progress indicator
- **Consensus Score**: Real-time agreement percentage
- **Timeline**: Chronological agent contributions
- **Live Feed**: Real-time updates via SSE

**Activity Indicators**:
- "🔍 Strategist analyzing..." - Agent processing
- "⚡ Optimizer optimizing..." - Agent responding
- "Round 2 completed — Consensus 85%" - Round summary

### 3. Human-in-the-Loop (HITL)

Inject context or interrupt during a debate:

1. Locate the **OOB Input** panel (or press keyboard shortcut)
2. Enter your input in the text field
3. Select target:
   - **Next agent**: Will be processed in next turn
   - **Strategist/Critic/Optimizer/Moderator**: Direct to specific role
   - **Currently active**: Immediate injection
4. Choose urgency:
   - **Append**: Queue for processing
   - **Inject now**: Interrupt current agent
5. Click **Insert into workflow** or press `Ctrl+Enter`

### 4. Document Management (RAG)

Upload documents to provide context for debates:

1. Navigate to **Documents** (📄)
2. Drag-and-drop files or click to browse
3. Supported formats: PDF, DOCX, ODT, TXT, MD, images (with OCR)
4. To enable RAG检索:
   - Click **Add to RAG** on a document
   - Or enable **Auto-retrieve relevant chunks** when creating a debate
5. Assign documents to a debate:
   - In Debate view, select documents from the RAG panel
   - Toggle **Auto-retrieve** for intelligent chunk selection

### 5. Blueprint Canvas

Create visual workflow blueprints:

1. Navigate to **Blueprint Canvas** (🧩)
2. Drag nodes from the **Palette** to the canvas
3. Connect nodes using **Edges**:
   - Drag from node handle to another node
   - Select edge type from popup

**Node Types**:

*Assets* (reusable definitions):
- **Agent Blueprint**: Complete agent definition
- **LLM Profile**: Model configuration
- **Role Definition**: Behavior constraints
- **Prompt Template**: Reusable prompt
- *Role Type*: Category configuration

*Workflow* (execution nodes):
- **Input**: Case input entry point
- **Initialize**: Setup operations
- **Strategist/Critic/Optimizer/Moderator**: Agent nodes
- **User Injection**: Human input point
- **Gate**: Conditional branching

**Edge Types**:
- **Uses LLM**: Connects agent to LLM profile
- **Implements Role**: Links to role definition
- **Prompted By**: Uses prompt template
- **Sequential**: Execution order
- **Conditional**: Branch based on condition
- **Interjection**: Human input interruption
- **Feedback**: Iteration loop

**Canvas Controls**:
- **Save Layout**: Save current arrangement
- **Load**: Restore saved layout
- **Auto-Layout**: Automatic arrangement via ELK
- **Mode Switcher**: Toggle Blueprint/Workflow view

### 6. Configuration

Manage profiles and settings:

#### LLM Profiles
1. Go to **Configuration** → **LLM Profiles** tab
2. Click **+ Create LLM Profile**
3. Configure:
   - **ID**: Unique identifier (lowercase, numbers, dots, hyphens)
   - **Name**: Display name
   - **Provider**: OpenRouter, OpenAI, Anthropic, Ollama, etc.
   - **Model**: Model identifier
   - **API Base**: Custom endpoint (optional)
   - **Temperature**, **Max Tokens**, etc.
4. Click **Save**

#### Agent Personas
1. Go to **Configuration** → **Agent Personas** tab
2. Select role tab (Strategist, Critic, Optimizer, Moderator)
3. Click **+ Create Persona**
4. Configure:
   - **ID**, **Name**
   - **System Prompt**: Agent instructions
   - **LLM Profile**: Model to use
   - **Max Rounds**, **Consensus Threshold**
   - **Tags**: Categorization
5. Click **Save**

#### Cost Estimation
1. Go to **Configuration** → **Cost Estimate** tab
2. Select LLM profile, number of agents, number of rounds
3. Click **Estimate Cost**
4. View estimated cost in USD

#### System Functions
- **Profile Reload**: Reload YAML profiles without backend restart
- **Backend Logs**: View recent backend logs with filtering

### 7. Projects

Create and manage projects for isolation:

1. Navigate to **Projects** (📁)
2. Click **Create Project**
3. Enter **Name** and **Description**
4. Configure project-specific settings:
   - **Language**: UI language preference
   - **Default Max Rounds**: For new debates
   - **Default Consensus Threshold**: For new debates
   - **Search Mode**: SearXNG configuration

### 8. Archive

Browse and manage completed debates:

1. Navigate to **Archive** (📚)
2. Filter by status (All, Completed, Failed)
3. Search by debate title or content
4. Click a debate to view details
5. Delete debates from the archive

### 9. Audit Trail

View detailed event logs:

1. Navigate to **Audit Trail** (📋)
2. Enter a debate ID
3. View events with:
   - Timestamp
   - Event type
   - Agent role
   - Model used
   - Token counts
   - Latency

### 10. Replay & Diff

Analyze past executions:

#### Replay
1. Navigate to **Replay** (#/replay)
2. Select a completed session
3. Use playback controls:
   - **Play/Pause**: Auto-advance
   - **Step Forward/Back**: Manual navigation
   - **Speed**: Playback rate
4. View node details: input, output, latency, tokens

#### Diff
1. Navigate to **Diff View** (#/diff)
2. Select two sessions to compare
3. View differences:
   - Node-by-node comparison
   - Latency comparison
   - Token comparison

## Internationalization

Switch between languages:

- **URL**: Add `?lang=en` or `?lang=de` to URL
- **UI**: Use language switcher in header
- **Persistence**: Saved to localStorage

Supported languages:
- English (en)
- German (de) - default

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Submit OOB input |
| `Ctrl+S` | Save (in applicable views) |
| `Escape` | Close modal/dialog |

## Troubleshooting

### Backend Unreachable
- Check backend is running
- Verify `VITE_API_URL` in environment
- Click **Refresh Health** on dashboard

### Debate Not Starting
- Verify LLM profiles are configured
- Check agent personas exist
- Review backend logs (Configuration → System → Backend Logs)

### RAG Not Working
- Ensure documents are uploaded
- Confirm documents are added to RAG
- Check RAG auto-retrieve is enabled

### Slow Performance
- Reduce max rounds
- Use smaller models
- Check network latency

## Missing Links

The following features exist in the codebase but are not yet fully accessible via the UI:

### 1. Reports Generation
**Status**: API implemented, UI not exposed
- Backend can generate JSON/PDF/CSV reports
- No dedicated Reports view in navigation
- **Workaround**: Use API directly or access via backend

### 2. Dedicated A2A Agent Management
**Status**: Partial - component exists
- External A2A agents can be configured
- No standalone management page
- **Workaround**: Configure via Blueprint Canvas (when adding A2A nodes)

### 3. Session Archive Management
**Status**: Partial - accessible via Replay/Diff
- Soft-delete and restore functionality exists
- No dedicated archive management UI
- **Workaround**: Access archived sessions via Replay view

### 4. Standalone Backend Logs View
**Status**: Partial - only in Config → System
- Full log access requires navigating to Configuration
- No dedicated System Logs page
- **Workaround**: Use Configuration → System → Backend Logs

### 5. Profile Hot-Reload UI
**Status**: Partial - only in Config → System
- Profile reload functionality exists
- No prominent reload button in main UI
- **Workaround**: Use Configuration → System → Profile Reload

### 6. LLM Cost Comparison View
**Status**: Basic form exists
- Cost estimation works per-profile
- No comparison view for multiple profiles
- **Workaround**: Use Config → Cost tab and compare manually

## Appendix

### Agent Roles

| Role | Purpose |
|------|---------|
| **Strategist** | Initial analysis, argument formation |
| **Critic** | Evaluation, challenge, quality control |
| **Optimizer** | Refinement, improvement, optimization |
| **Moderator** | Consensus building, direction |

### Consensus Calculation

Consensus is calculated as a weighted average of:
- Argument alignment (70%)
- Proposal similarity (20%)
- Confidence scores (10%)

Reached when score exceeds threshold (default: 90%)

### API Endpoints Reference

See [technical_documentation.md](./technical_documentation.md) for complete API reference.

### Support

For issues or questions:
- Check backend logs in Configuration
- Review audit trail for execution details
- Consult technical documentation