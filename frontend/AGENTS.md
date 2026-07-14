# DOX: frontend/

## Purpose

Svelte 5 + Vite + TailwindCSS single-page application providing the user interface for Danwa. Includes debate management, workflow visualization, interactive debate mode, and AI assistant integration.

## Ownership

- **Entry Point**: `frontend/src/main.js` — app bootstrap
- **Root Component**: `frontend/src/App.svelte` — routing and layout
- **Views**: `frontend/src/views/` — 15 page-level view components
- **Components**: `frontend/src/components/` — 29 component groups
- **Libraries**: `frontend/src/lib/` — API clients, stores, utilities
- **i18n**: `frontend/src/lib/i18n/` — internationalization system
- **Stores**: `frontend/src/lib/stores/` — Svelte stores for global state
- **API Clients**: `frontend/src/lib/api/` — domain-specific API modules
- **Tests**: `frontend/tests/` — Vitest unit + Playwright E2E tests

## Local Contracts

- All API calls go through `frontend/src/lib/api/core.js` `request()` helper
- Views are routed via `App.svelte` route definitions
- Components use Svelte 5 runes (`$state`, `$derived`, `$effect`)
- Stores follow Svelte store contract with `subscribe`/`update`

## Work Guidance

- Use Svelte 5 runes syntax, not Svelte 4 `$:` reactive statements
- Keep components focused; extract reusable pieces to `components/`
- Follow existing patterns for new views (see `views/Dashboard.svelte`)
- Add i18n keys for all user-facing strings

## Verification

- Run `npm run check` for type checking
- Run `npm run test` for unit tests
- Run `npm run build` to verify production build

## Child DOX Index

| Child | Purpose |
|-------|---------|
| `frontend/src/views/` | Page-level view components (15 views) |
| `frontend/src/components/` | Reusable UI components (29 groups) |
| `frontend/src/lib/` | Shared libraries, API clients, stores |
| `frontend/tests/` | Unit and E2E tests |
