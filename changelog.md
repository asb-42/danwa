# Changelog

## 2026-06-12

- chore(workflow): remove dead `backend/workflow/nodes.py` (422 stmts, 0 % coverage)
  - Datei wurde durch das `backend/workflow/nodes/`-Subpackage ersetzt (siehe `node_functions.py` `_LAZY_IMPORT_MAP`)
  - Kein Backend-Code, kein Frontend, kein Plugin-Manifest und kein dynamischer Import verweist noch auf das Modul
  - Verifikation: statische Suche (alle `.py`/`.json`/`.yml`/`.toml`/`.md`) + Import-Blocker-Test (Backend startet ohne diese Datei)
- docs: Test-Coverage-Analyse `reports/2026-06-12_test-coverage-analysis.md` (Gesamt: 59,8 %)
- fix(blueprints): RENAME-Strategie in `bundle_io.import_bundle` speichert jetzt umbenannte Entitäten (LLM/Tone/Bundle)
  - Vorher: bei RENAME wurde die umbenannte Entität nicht persistiert → Export zeigte auf nicht existierende ID
  - Bedingung erweitert: `if not existing or strategy == OVERWRITE or resolved_id != raw["id"]`
- test(blueprints): Round-Trip- und Konflikt-Strategie-Tests für `bundle_io` (16 Tests, 91 % Coverage, vorher 0 %)
- test(persistence): CRUD-Tests für `UserKeyStore` (15 Tests, 100 % Coverage, vorher 0 %)
- fix(workflow): kaputten Lazy-Import `backend.blueprints.repo` in `report_generator.py` repariert (2 Vorkommen)
  - Korrektes Modul ist `backend.blueprints.repository`
  - Ohne diesen Fix würden alle Report-Generator-Pfade, die `_build_node_phase_map` nutzen, mit `ModuleNotFoundError` abstürzen
- test(workflow): Smoke-Tests für `report_generator` (29 Tests, 21 % Coverage, vorher 7 %)
- fix(audit): `UnboundLocalError` in `_transform_workflow_audit_events` behoben
  - `_format_audit_content` wurde nur im `if session_id:`-Zweig importiert, aber immer referenziert
  - Import auf Funktionsanfang verschoben + `_use_formatter`-Flag für Fallback
- fix(audit): `_resolve_debate_id` griff auf `d["debate_id"]` zu, aber `DebateStore.list_all()` liefert Dicts ohne dieses Feld
  - Neuer Helper `_iter_cached_debates` nutzt `store._cache.items()` (debate_id ist der Cache-Key)
  - Fallback auf `list_all()` mit `d.get("debate_id", "")` für Stores ohne `_cache`-Attribut
- test(audit): Router-Tests für `/api/v1/audit/{id}` + Helper (25 Tests, 91 % Coverage, vorher 15 %)
- test(case-scoped): Router-Tests für `/api/v1/tenants/{tid}/...` + Helper (51 Tests, 69 % Coverage, vorher 44 %)
  - Abdeckung: Helper (`_resolve_case_dir`, `_get_debate_store_for_case`, `_resolve_tags`, `_resolve_llm_model`, `_build_debate_item`), List/Create/Get/Delete/Cancel/Force-Reset Debate, OOB-Input, Forks, Case-Audit-Delegation
  - Verbleibende Lücken v.a. DMS- und Workflow-Delegation-Pfade (komplexe externe Abhängigkeiten)
- test(auth): Router-Tests für `/api/v1/auth/...` (31 Tests, 100 % Coverage, vorher 39 %)
  - Abdeckung: register (first-user-admin, duplicate, validation, internal error), login (success, unknown, wrong password, deactivated), refresh (success, invalid JWT, access token rejected, user not found, deactivated), /me (GET, PUT, PUT update-fails), /password (change, wrong current), /users (list, invite, duplicate, internal error, delete, self-delete guard, unknown), /my-tenants (dev-mode, membership-based), /select-tenant (dev-mode, membership-role, unknown+auth-enabled 403)
  - Eigene Fixtures `app_with_auth` / `app_empty_store` mit überschriebenen `get_user_store`/`get_membership_store`/`get_current_user`/`get_settings`-Dependencies (lru_cache-Reset zwischen Tests)

## 2026-05-12

- docs: update technical documentation with Blueprint System, HITL System, and Input/Output Composer
- docs: update user manual with new systems and views (Blueprint Canvas, Input/Output Composer, Diff, Replay)
- docs: move PADDLEOCR_COMPATIBILITY_REPORT.md to docs/
- chore: update README.md and README.zh.md with enhanced feature descriptions
- docs: update technical documentation with new systems
- chore: move frontend README files to archive
- ci: fix CI linting errors
- ci: fix CI test collection errors
- fix: configure Vite to listen on all interfaces
- a11y: fix remaining accessibility warning in TemplateInstantiateModal.svelte
- a11y: fix accessibility issues in Svelte components
- fix(dms): improve OCR error messages and fix version access issues
- fix(dms): fix PaddleX initialization conflicts in OCR functionality
- fix(dms): fix DMS upload regression: correct concurrent.futures exception handling
- fix(dms): fix PaddleOCR compatibility: downgrade PaddlePaddle to resolve PIR OneDNN bug
- fix(dms): DMS upload feedback + RAG button UX improvements
- feat(dms): PaddleOCR integration — fix silent image upload failures
- feat(a2a): Phase 3+4 — A2A polling, approval UI, default workflow selection
- feat(input-composer): Input Composer → Workflow Execution bridge (Phase 1+2)
- feat(blueprint): Blueprint → Debate Pipeline (Phase 1-4)
- fix(blueprint): layout loading, real-time node preview, save dialog
- fix(i18n): add t() keys for Palette entity section labels
- feat(blueprint): DB entities in Palette + color-coded ports
- fix(blueprint): edge handle IDs + connection state display
- fix(workflow-viz): Position enum casing + handle CSS + event API
- fix(blueprint): Position enum casing + SvelteFlow event API — canvas fully functional
- fix(blueprint): node handles not visible + canvas handle styles
- fix(blueprint): LLM Profile form — missing fields + null validation
- fix(blueprint): Palette shows empty — registry not populated
- fix(tts): VoiceMappingEditor visibility + Generate button
- fix(tts): auto-resolve MiMo config from LLM profile + WAV→MP3 + voice mapping UI
- fix(tts): MiMo silent failure + profile_type persistence
- fix(tts): profile_type persistence + MiMo TTS timeout
- fix(tts): MiMo TTS 401 — wrong env var name
- feat(tts): MiMo-V2.5-TTS integration with per-agent voice assignment
- fix(blueprint): Svelte 5 syntax errors in inspector forms
- feat(blueprint): Phase 3+4 — Compiler RoleType chain + Config UI badges
- feat(blueprint): Phase 2 — Inspector Panel Enhancements + ADR-001
- feat(blueprint): Phase 1 — Edge → Backend Wiring for canvas role assignment
- fix(config): Role Types — tab order, create error, seed defaults
- fix(config): LLM Profiles dropdown + restore missing table columns
- feat(config): LLM Profiles UI — profile_type, dropdown actions, search, sort
- feat(config): Agent Personas + Prompts → DB SSOT (blueprints.db)
- refactor: ProfileService LLM profiles → DB as Single Source of Truth
- chore: move duplicate Xiaomi LLM profile to archive
- chore: remove debug logging, downgrade format log to DEBUG
- fix: generic progress text + add /output/ to .gitignore
- fix(output): initialize config defaults from schema on plugin select
- feat(output): add Markdown (MD) output format + debug logging for format branching
- fix(output): resolve $ref in ConfigForm for enum fields (ODT/DOCX select)
- feat(pdf): add Table of Contents to PDF export

## 2026-05-10

- refactor: extract routers/services, fix report generation, restructure debate UI
- fix: report download + title generation + docs: Missing Links rewrite
- fix: report download 500 error + docs: rewrite Missing Links section + add code review
- feat: Reflection UI — Reflect button + ProposalsPanel in BlueprintCanvas
- fix: implement plan gaps for Output Composer and Input Composer
- Merge branch 'input-composer-input-plugin-architektur' into main
- feat: Input Composer frontend — views, components, i18n, route wiring
- feat: Input Composer & Input-Plugin-Architektur
- Merge branch 'output-composer-render-pipeline' into main
- feat: Output Composer & Render Pipeline
- chore: move plans/* to archive/plans/*
- feat: redesign Prompt Variants tab with role-based tiles + create variant

## 2026-05-09

- fix: ConfigView settings tab infinite loading loop
- feat: wire up 5 remaining low-impact missing-link features
- feat: wire up 8 missing-link features to UI
- feat: implement ToneProfileNode (Global Config Node)
- feat: implement Workflow Templates for Visual Pipeline Builder
- Merge branch 'workflow-graph-builder' into main
- feat(workflow-graph-builder): Phase 7+8 complete, a11y fixes, RoleType refactor

## 2026-05-08

- feat(blueprint-canvas): add RoleType as first-class canvas entity
- feat: add debate title generation via LLM with animated UI display

## 2026-05-07

- chore: ignore .roo directory
- feat: A2A Protocol Integration (Phases 1-9)
- fix(workflow-viz): fix overlapping nodes and add missing SSE mappings

## 2026-05-06

- fix: HITL inject context not reaching target agent + UI feedback improvements
- docs: add Missing Links sections to documentation
- Merge branch 'feature/bidirectional-workflows' into main — workflow viz reactivity fixes
- fix(workflow-viz): fix reactivity bugs preventing cumulative graph rendering
- fix(workflow-viz): cumulative graph rendering with proper Svelte reactivity
- fix(frontend): export request helper from api.js for HITL module
- feat(hitl): implement bidirectional HITL workflows
- fix: document_ids validation, textarea resize, suppress noisy loggers
- docs: add comprehensive technical documentation and update README/user manual
- Merge branch 'feature/workflow-visualization' into main
- feat: workflow visualization, a11y fixes, project context reactivity

## 2026-05-05

- docs: update workflow visualization plan with state management + OOB handler
- docs: add workflow visualization implementation plan
- feat(dms): DMS/OCR/RAG migration — Phases 1-7 complete
- fix: show failed debates in archive + fix activity strip for rounds 2+
- feat: wire up project isolation in UI
- test: add SSE endpoint regression tests for project_id query param
- fix: SSE 422 — pass project_id as query param (EventSource cannot send headers)
- fix: SSE endpoint subscribes to event bus for pending debates
- fix: cancel debate race condition — make endpoint idempotent
- feat: project isolation + enhanced debate feedback + migration fix

## 2026-05-04

- fix(debate): mark failed debates as 'failed' + allow cancel for pending debates
- fix(web-search): publish agent_started before search + add type field to web_search SSE
- feat: web search integration (SearXNG + DuckDuckGo fallback)
- feat: enhanced debate feedback — Activity Strip with real tokens, duration, progress dots
- revert: remove DebateTimeline 2.0 and AgentCard, keep language fix + model info
- feat: language consistency fix + DebateTimeline 2.0 with AgentCard

## 2026-05-03

- fix: extract reasoning_content from thinking models (OpenRouter)
- ci: fix lint/format errors and scope CI to active codebase
- fix: cancel SSE events + localStorage persistence for model selection
- fix: parse datetime strings on JSON load in DebateStore
- fix: NoneType guard, cancel debate, extend provider dropdown
- fix(llm): auto-prepend provider prefix for litellm model routing
- fix: load .env API keys into os.environ via python-dotenv
- feat(frontend): add form-based CRUD editing for profiles
- fix: SSE reconnect after debate completion + stale PID cleanup
- fix: add missing formatDate import in DebateView.svelte
- feat: comprehensive UI/UX improvements for debate views
- feat: debate archive page (Option B) — search, filter, pagination
- feat: debate archive — clickable Dashboard links → DebateView read-only mode
- fix: prompt service (language-aware) takes priority over persona fallback
- security: exclude profile configs from git, add sanitized examples
- feat: debate persistence, history list, and language-aware prompts
- feat: render agent outputs as Markdown with typography plugin
- feat: redesign debate UI with chat-bubble layout, full content, expand/collapse
- fix: bypass litellm for local providers — use direct httpx HTTP calls
- fix: auto-assign dummy API key for local providers (litellm requires it)
- fix: auto-prefix local provider models with openai/ for litellm
- fix: correct IP address in local-gemma profile (278 → 178)
- fix: real-time SSE streaming, background debate execution, UI progress
- feat: add logging, profile reload, and log viewer
- fix: wire LLM profile selection from ConfigView to DebateView
- chore: archive legacy config files, clean up .gitignore
- chore: relocate archived docs to project root archive/
- docs: update user manual for v2.0 architecture and archive legacy files

## 2026-05-02

- fix(frontend): use Promise.allSettled in ConfigView for partial failure resilience
- fix(frontend): clear stale error on ConfigView mount, show actual error details
- feat(sprint3): configuration & profile management system
- fix: align frontend proxy target with backend default port 7860
- refactor: extract health endpoint into backend/api/routers/health.py
- refactor: move tests_backend/ into tests/backend/
- refactor: rename debate_engine → backend, tests_debate_engine → tests_backend
- refactor: consolidate src/server/ routers into debate_engine/
- chore: archive OhMyOpencode (Sisyphus plans) and artifacts from completed sprints
- Integrate Sprint 1-2: FastAPI/LangGraph backend + Svelte frontend
- refactor: add Chainlit cleanup script, archive remaining remnants
- refactor: remove all Chainlit remnants — migrate to FastAPI/Svelte
- docs: add strangler fig migration audit report (Chainlit → FastAPI/Svelte)
- feat(sprint2e): i18n — DE/EN translations, locale formatting, API isolation, 134/134 tests
- Sprint 2d: Accessibility Tests — WCAG 2.1 AA compliance
- Sprint 2c: Extended Tests — API contract tests + visual regression
- Sprint 2b: Playwright E2E tests — 38/38 passing
- feat: Sprint 2 — Debate UI v2.0 (Svelte + Tailwind frontend)
- feat: Sprint 1 — Debate Engine API v2.0 backend skeleton
- fix: spawn AskUserMessage flows as background tasks from action callbacks
- fix: complete UI rewrite with AskUserMessage, navigation, chatbot mode
- fix: eliminate hardcoded 'local_lm_studio' default that broke entire app
- refactor: replace AskUserMessage with state-machine pattern for config/DMS flows
- fix: AskUserMessage response handling for Chainlit 2.x

## 2026-05-01

- Make number of debating agents configurable via agent profiles
- Add config example files and secure sensitive configs
- Add i18n/l10n language switch feature (placeholder)
- Translate UI files to English
- fix: migrate all cl.Action() to Chainlit 2.x API (name/payload instead of id/value)
- fix: register action callbacks with explicit names, fix dms_dashboard routing
- chore: update boulder config, remove systemd/logrotate files, update setup scripts
- feat: Add ConfigManager and UI for app configuration
- feat: on-demand replacement - add start/stop/status/cleanup scripts
- feat(dms): update README/manual, add missing tests, fix lint

## 2026-04-29

- fix(dms): complete Task 27 & 31 - create missing tests, fix broken tests
- docs: update README with DMS and OCR features, move systemd/etc-logrotate.d to docs/
- feat(dms): complete DMS integration with PaddleOCR and RAG pipeline

## 2026-04-28

- feat(dms): add DocumentProcessor (PaddleOCR+existing) and DMSVectorStore
- feat(dms): extend SessionDB with project_id/document_ids linkage
- feat(dms): add ProjectManager, module structure, PaddleOCR optional dep
- feat(dms): add DMS config loader (settings.yaml gitignored)
- feat(dms): add database schema for projects, documents, chunks
- 🧨 KRITISCHE BUGFIXES & DOKUMENTATION: Alle Code-Fehler behoben, TDD-Testsuite erstellt, umfassende Dokumentation verfasst

## 2026-04-23

- Fix imports and chainlit UI: resolve circular memory import, add package init files, fix action component syntax and decorator
- Fix setup.sh: replace 'source /home/asb/.local/bin/env' with exporting PATH to include /home/asb/.local/bin
- Initial commit: Multi-Agent Debate System with Prompt Registry, Privacy Controls, Session Management, and Report Generation
- Add .gitignore to exclude build artifacts, virtual environments, logs, and other non-source files
