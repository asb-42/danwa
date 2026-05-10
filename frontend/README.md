# Danwa - Multi-Agent Debate Platform

<div align="center">

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/danwa/frontend)
[![Svelte](https://img.shields.io/badge/Svelte-5-orange.svg)](https://svelte.dev)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A visual multi-agent debate platform for orchestrating discussions between AI agents.

</div>

## Overview

Danwa is a frontend application for a multi-agent debate system. It provides a visual interface for:

- Creating and running debates with multiple AI agents
- Visual workflow design with the Blueprint Canvas
- Document management with RAG (Retrieval-Augmented Generation) integration
- Real-time debate monitoring via Server-Sent Events (SSE)
- Human-in-the-loop (HITL) context injection
- A2A protocol support for external agents
- Session replay and diff analysis
- Project-based multi-tenancy

## Features

### Core Debate System
- Multi-agent debate orchestration (Strategist, Critic, Optimizer, Moderator)
- Configurable consensus thresholds and max rounds
- Web search integration (optional/required modes)
- Real-time status updates and timeline visualization

### Blueprint Canvas
- Visual node-based workflow builder
- Drag-and-drop interface with SvelteFlow
- Two modes: Blueprint (design) and Workflow (execution)
- Asset nodes: Agent Blueprints, LLM Profiles, Role Definitions, Prompt Templates
- Workflow nodes: Input, Initialize, Agent nodes, User Injection, Gates
- Edge types: Semantic (UsesLlm, ImplementsRole) and Control Flow (Sequential, Conditional, Interjection, Feedback)

### Configuration
- LLM profile management (OpenRouter, OpenAI, Anthropic, Ollama, etc.)
- Agent persona creation per role
- Prompt variant management
- Cost estimation calculator

### Document Management
- File upload (PDF, DOCX, ODT, TXT, MD, images with OCR)
- RAG indexing and retrieval
- Document assignment to debates

### Project Management
- Multi-project support
- Project-scoped configuration
- Language preferences

### Analysis & Debugging
- Audit trail viewer
- Session replay with step-through controls
- Session diff comparison
- Backend log viewer

## Tech Stack

- **Framework**: [Svelte 5](https://svelte.dev) (with runes: `$state`, `$derived`, `$effect`)
- **Styling**: [TailwindCSS](https://tailwindcss.com) 3.4 + @tailwindcss/typography
- **Flow Charts**: [@xyflow/svelte](https://xyflow.com) (SvelteFlow) 1.5.2
- **Auto-layout**: [ELKjs](https://github.com/kieler/elkjs) 0.11.1
- **Markdown**: [marked](https://marked.js.org) 18.0.3
- **Validation**: [zod](https://zod.dev) 4.4.2
- **Build**: [Vite](https://vitejs.dev) 5
- **Testing**: [Vitest](https://vitest.dev) + [Playwright](https://playwright.dev)

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+
- A running Danwa backend (default: `http://localhost:8000`)

### Installation

```bash
# Clone the repository
git clone https://github.com/danwa/frontend.git
cd frontend

# Install dependencies
npm install

# Create environment file
cp .env.example .env
# Edit .env and set VITE_API_URL to your backend URL
```

### Development

```bash
# Start development server
npm run dev

# Run tests
npm run test:unit        # Unit tests
npm run test:e2e         # E2E tests
npm run test:visual      # Visual regression
npm run test:a11y       # Accessibility
npm run test:i18n       # Internationalization
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── blueprint/        # Blueprint canvas components
│   ├── workflow/         # Workflow execution components
│   ├── hitl/            # Human-in-the-loop components
│   └── *.svelte         # Shared components
├── views/                # Page-level components (routes)
│   ├── Dashboard.svelte
│   ├── DebateView.svelte
│   ├── BlueprintCanvasView.svelte
│   └── ...
├── lib/                  # Core libraries
│   ├── api.js           # API client
│   ├── stores.js        # Svelte stores
│   ├── blueprint/       # Blueprint system
│   └── i18n/            # Internationalization
└── App.svelte           # Root component
```

## Navigation

| Route | Description |
|-------|-------------|
| `#/dashboard` | Overview with statistics |
| `#/debate` | Create and manage debates |
| `#/blueprint` | Visual workflow builder |
| `#/documents` | Document management & RAG |
| `#/archive` | Completed debates archive |
| `#/audit` | Audit trail viewer |
| `#/projects` | Project management |
| `#/config` | Configuration (profiles, agents) |
| `#/replay` | Session replay |
| `#/diff` | Session comparison |

## Internationalization

Supported languages:
- English (en)
- German (de) - default

Switch via URL parameter: `?lang=en` or `?lang=de`

## API Integration

The frontend communicates with the backend via REST API and SSE:

- **REST**: All CRUD operations
- **SSE**: Real-time debate updates
- **Project-scoped**: Automatic `X-Project-Id` header injection

## Missing Links

The following features exist in the codebase (API or components) but are not yet fully exposed in the UI:

### 1. Reports Generation
- **Status**: API implemented (`generateReport`, `getReportStatus`, `downloadReport`)
- **UI Status**: Not implemented - no dedicated Reports view
- **Location**: `src/lib/api.js` lines 385-398
- **Workaround**: Use API directly

### 2. A2A Agent Management Page
- **Status**: Component exists, no navigation entry
- **UI Status**: Partial - `A2ACapabilities.svelte` exists but not accessible via main UI
- **Location**: `src/components/blueprint/A2ACapabilities.svelte`
- **Workaround**: Configure via Blueprint Canvas when adding A2A nodes

### 3. Standalone Workflow Execution Panel
- **Status**: API and components implemented
- **UI Status**: Integrated into DebateView only
- **Location**: `src/components/workflow/ExecutionPanel.svelte`
- **Workaround**: Use DebateView during execution

### 4. Blueprint Layout Persistence
- **Status**: ELKjs auto-layout implemented
- **UI Status**: Partial - save/load exists but not fully persistent
- **Location**: `src/lib/blueprint/layout.js`
- **Workaround**: Use canvas toolbar save/load buttons

### 5. Session Archive Management UI
- **Status**: API implemented (`softDeleteSession`, `restoreSession`)
- **UI Status**: Partial - accessible via Replay/Diff only
- **Location**: `src/lib/api.js` lines 404-410
- **Workaround**: Access via Replay view

### 6. Dedicated Backend Logs View
- **Status**: API implemented (`getBackendLogs`)
- **UI Status**: Partial - only in Config → System tab
- **Location**: `src/views/ConfigView.svelte` (System tab)
- **Workaround**: Use Configuration → System → Backend Logs

### 7. Profile Hot-Reload with UI Feedback
- **Status**: API implemented (`reloadProfiles`)
- **UI Status**: Partial - only in Config → System tab
- **Location**: `src/views/ConfigView.svelte`
- **Workaround**: Use Configuration → System → Profile Reload

### 8. Multi-Profile Cost Comparison
- **Status**: API implemented (`estimateCost`)
- **UI Status**: Basic form exists, no comparison view
- **Location**: `src/views/ConfigView.svelte` (Cost tab)
- **Workaround**: Use Config → Cost tab and compare manually

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Related Documentation

- [Technical Documentation](docs/technical_documentation.md) - Detailed technical specs
- [User Manual](docs/user_manual.md) - End-user guide

---

*Danwa v2.0 - Built with Svelte 5*