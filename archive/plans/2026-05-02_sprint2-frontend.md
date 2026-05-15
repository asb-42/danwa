# Sprint 2: Frontend Skeleton — "Debate UI v2.0"

## Goal
A runnable Svelte app (plain Svelte, no SvelteKit) with hash router that connects to the FastAPI backend from Sprint 1. No business logic — only the skeleton and navigation.

## Acceptance Criteria
- `npm run dev` starts dev server on localhost:5173
- `npm run build` produces `dist/` with `index.html`, `assets/`
- FastAPI serves `dist/` statically on `/`
- Hash router works: `/#dashboard`, `/#debate`, `/#audit`, `/#config`
- All 4 views are reachable and show dummy data
- SSE connection to `/api/v1/debate/{id}/events` is established (dummy handler)
- API calls to Sprint 1 backend work (CORS configured)

## Directory Structure

```
frontend/
├── package.json
├── vite.config.js
├── index.html
├── .env.example
├── public/
│   └── favicon.svg
├── src/
│   ├── main.js
│   ├── App.svelte
│   ├── lib/
│   │   ├── api.js              # FastAPI client
│   │   ├── stores.js           # Svelte writable stores
│   │   └── sse.js              # SSE connection manager
│   ├── components/
│   │   ├── Layout.svelte       # Sidebar + main area
│   │   ├── Sidebar.svelte      # Navigation
│   │   ├── Header.svelte       # Title + status
│   │   ├── WorkflowGraph.svelte  # Placeholder (ELK.js later)
│   │   ├── DebateTimeline.svelte # Placeholder
│   │   ├── ConsensusPanel.svelte # Placeholder
│   │   ├── AuditTrail.svelte   # Placeholder
│   │   └── DocumentUploader.svelte # Placeholder
│   └── views/
│       ├── Dashboard.svelte
│       ├── DebateView.svelte
│       ├── AuditView.svelte
│       └── ConfigView.svelte
├── dist/                       # Build output (gitignored)
└── tests/                      # Playwright later
    └── .gitkeep
```

## Implementation Order

1. `package.json` — dependencies (svelte, vite, tailwindcss, elkjs)
2. `vite.config.js` — Svelte plugin, build config, dev proxy
3. `index.html` — entry point
4. `src/main.js` — Svelte mount
5. `src/lib/api.js` — API client
6. `src/lib/stores.js` — Svelte stores
7. `src/lib/sse.js` — SSE manager with reconnect
8. `src/App.svelte` — Hash router
9. `src/components/Layout.svelte` — Sidebar + main
10. `src/components/Sidebar.svelte` — Navigation
11. `src/components/Header.svelte` — Title + status
12. `src/views/Dashboard.svelte` — Stats + health check
13. `src/views/DebateView.svelte` — Case input + debate status
14. `src/views/AuditView.svelte` — Audit trail table
15. `src/views/ConfigView.svelte` — Settings form
16. Placeholder components (WorkflowGraph, DebateTimeline, etc.)
17. FastAPI static file serving + CORS + SPA fallback

## Backend Changes for Sprint 2

- Add CORS middleware for dev mode (localhost:5173)
- Add SSE dummy endpoint: `GET /api/v1/debate/{id}/events`
- Add static file serving: `frontend/dist/`
- Add SPA fallback: 404 → `index.html`

## Deliverables

- [ ] `npm run dev` runs without errors
- [ ] `npm run build` produces `dist/`
- [ ] FastAPI serves `dist/` on `/`
- [ ] All 4 views navigable via hash
- [ ] API calls to backend work (health check, debate create)
- [ ] SSE connection established (dummy events flow)
- [ ] Tailwind styling consistent across all views
