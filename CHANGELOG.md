# Changelog

All notable changes to this project will be documented in this file.
This project does **not** follow [Semantic Versioning](https://semver.org/)
strictly yet -- the major version has not reached 1.0.0.  The format is
roughly: `MAJOR.MINOR.PATCH`.

The convention: bump MAJOR for breaking changes (architecture, schema,
public API), MINOR for new features or visible user-facing changes, PATCH
for bug fixes and internal cleanups.  Multiple changes in a single
release are listed in chronological order under each version heading.

---

## [Unreleased]

### Architecture cleanup
- **Legacy `/api/v1/sessions` router retired.** The 5 endpoints
  (`GET ""`, `GET /{session_id}`, `DELETE /{session_id}`,
  `GET /{session_id}/trace`, `GET /{session_id}/report/{fmt}`)
  now return `HTTP 410 Gone` with a successor-pointer payload.
  This removes the last active cross-dependency on the legacy
  `src/{core,dms,tools}/` source tree in `danwa/backend/`. Clients
  should migrate to:
    - `GET /api/v1/tenants/{tid}/cases/{cid}/sessions/` (assistant router) for session CRUD
    - `GET /api/v1/workflow-exec/sessions` for session lists
    - `POST /api/v1/workflow-exec/sessions/{id}/report` for report generation
    - `GET /api/v1/workflow-exec/sessions/{id}/report/stream` for SSE progress
  See [`plans/2026-06-22_danwa-legacy-sessions-router-cleanup.md`](plans/2026-06-22_danwa-legacy-sessions-router-cleanup.md).

### Repo orchestration (Phase 1 of plan)
- **`libdanwa.sh v1.0.0` introduced** as shared bash library for the
  `danwa` / `danwa-core` / `danwa-studio` repo family. Currently lives
  in `danwa/scripts/libdanwa.sh` and will be mirrored to
  `danwa-modules/scripts/libdanwa.sh` for downstream consumption.
  Provides reusable primitives: `log_info/ok/warn/error/step/header`,
  `pid_running`, `kill_pid`, `wait_for_url`, `wait_for_port`,
  `require_cmd/var`, `ensure_dir`, `compose_url`, version checks,
  `load_repo_config`, `discover_siblings`.
- **bats test suite added** at `tests/scripts/libdanwa.bats` with
  33 tests (100 % coverage of the library). Runs via
  `bats tests/scripts/libdanwa.bats`.
- **Setup helper added** at `tests/scripts/helpers/mocks.bash` for
  reusable mock-uvicorn / mock-HTTP-server fixtures.


### Repo orchestration (Phase 2 of plan — danwa-core setup+manage)
- **`danwa-core` setup.sh + manage.sh mirror templates** at `repo-templates/danwa-core/`. These are the canonical reference for the orchestrator pattern (danwa-core manages backend + sibling frontends). To use: copy `setup.sh` and `manage.sh` into a danwa-core clone, then run `bash setup.sh` and `bash manage.sh start`.
- **Mirror strategy:** this repo (`danwa`) provides the Single Source of Truth (`repo-templates/danwa-core/`). The downstream `danwa-core` repo should fetch these templates via `curl -L https://raw.githubusercontent.com/asb-42/danwa/main/repo-templates/danwa-core/{setup,manage}.sh -o ./{setup,manage}.sh`.
- **bats test suite added** at `tests/scripts/{setup,manage_orchestrator}.bats` with 20 tests (8 setup + 12 manage). All green.
  Run: `bats tests/scripts/`

## [0.3.0] - 2026-06-20 -- Pre-architecture-refactor baseline

The last standing point before the planned architecture refactor.
Functional for daily use of the legacy- and MVP-debate pipelines,
but pre-alpha overall.  The previous v1.1.0 was aspirational and has
been corrected to reflect the actual maturity.

### Security
- **Workspace tenant-spillover fix** (sicherheitskritisch).  Switching
  tenants while the Workspace was open with a case selected no
  longer shows Tenant A's data on Tenant B's session -- the
  workspaceStore is now reset on tenant change, forcing the user
  to re-pick a case.

### Bug fixes
- **Inbox / Tags**
  - Tags in the Inbox row now display their human-readable label
    (e.g. "Krankenversicherung") instead of the raw UUID
    (e.g. "2e42ed74-...").  Added `tag_names: list[str]` to
    `InboxDebateItem`, populated by the backend via TagStore lookup.
  - Soft-deleted and archived debates no longer appear in the Inbox
    (filter `status in {"deleted", "archived"}` on the read path).
  - Inbox retention: as documented, the Inbox holds items indefinitely
    until the user explicitly deletes them.  No TTL is added in this
    version; the soft-delete just hides the row from the visible
    list.
- **Tag UI**
  - Tag-Picker modal: Cancel / "Add tags" buttons are now visible
    (modal widened to 720px / 90vh, action bar moved inside the
    modal-card, both modals unified on the same layout).
  - Tag-Picker: lowercase `onchange` prop binding matches the
    convention used by all other components -- previously the
    camelCase `onChange` was silently dropped, so picking a tag
    did nothing.
  - Tag-Picker: success toast added so creating a tag inside the
    modal gives visible feedback.
  - Tag-Picker: out-of-modal click no longer closes the modal --
    the explicit Cancel button is the only way out.
  - Tag-Picker: inside-modal `createTag` failure now surfaces an
    error toast.
  - LLM-Monitor: four pink `DBG:` debug markers removed from
    production UI (data-debug-component attribute retained as an
    e2e/smoke test anchor).
- **Browse view**
  - Orphan tenant tags (tags that exist in TagStore but are not
    yet attached to a case) now show up in the Browse graph.
    Previously the graph only added Tag nodes for tags that
    were referenced by a Case.
  - Browse entity clicks now navigate to the right management
    view (workspace / mvp-debate / documents / tags / users /
    audit) instead of just opening a passive info modal.
  - Browse grid auto-fits columns with `repeat(auto-fill,
    minmax(280px, 1fr))` so an empty Documents column does not
    leave an empty grid slot.
- **LLM-Monitor activity**
  - Stuck-record bug after task cancellation: the activity monitor
    could keep an "active" entry forever after `asyncio.CancelledError`
    propagated through `LLMService.generate` and `MimoTTSRenderer.render`.
    Fixed by switching the `try/except` in both call sites to
    `try/finally` so `end_call` always runs.
  - Stuck-record auto-eviction in the activity tracker: any active
    entry older than 30 minutes is now moved to the recent list
    with status "stuck" (defense in depth, in case a future
    regression reintroduces the leak).
  - `clear_session` now wired in the workflow runner on completion,
    cancel, and failure paths (previously defined but had zero
    callers -- the tag/monitor counter accumulated across debates).
- **MVP-Debate pipeline**
  - `dms_project_id` is now passed to `resolve_rag_context` so the
    case-scoped DMS is found -- without this, the RAG resolver
    raised "Project not found" and the debate ran without RAG
    context.
  - Cancel button on MVP-debate view terminates the workflow
    task and the SSE stream closes cleanly (was the
    long-standing cancel-doesn't-actually-terminate bug).

### Quality
- Pre-commit hook added (`.pre-commit-config.yaml` with `ruff` and
  `ruff-format`).  Every commit now runs lint+format locally
  before push.
- New regression tests in `tests/rag_regression/`:
  - `test_mvp_debate_passes_dms_project_id.py`
  - `test_llm_activity_end_call_on_cancel.py`
  - Updated `test_llm_monitor_regression.py` to match the marker
    cleanup (data-debug-component kept, human-readable label gone).

### Documentation
- Version corrected from 1.1.0 to 0.3.0 across:
  - `version` (single source of truth)
  - `pyproject.toml`
  - `frontend/package.json`
- `CHANGELOG.md` created (this file).
- `docs/adr/002-version-ssot.md` updated with the 0.3.0 entry and
  an honest note that the previous 1.1.0 was aspirational.

### Known issues (not fixed in 0.3.0)
- Tag-Modal: a tag created *inside* the picker (not on the Tags
  page) requires the user to first create the tag on the Tags
  page and then assign it in the Inbox -- the in-picker create
  flow is functional but the UX for it is rough.
- Inbox-Bulk-Action toasts were not part of this work.
- Browse shows soft-deleted debates intentionally (audit-trail
  use case) -- if you want them hidden, that's a separate UX
  decision.

### Migration notes
No schema changes. No data migration. The `tag_id` field on
`InboxDebateItem` is additive (default `[]`); clients that
read the old `tags` field only continue to work.

---

## [1.0.0] - 2026-05-15 -- Modularisierung: Module-Architektur + EN-SSOT

(Historical; the previous v1.1.0 has been collapsed into this
entry.  Real shipped state at this tag was the multi-tenant
data model and the per-tenant tag store; the
`WorkspaceRecentDebate` and `InboxSummary` Pydantic models
existed, but the Inbox was not actually wired into the
frontend.  Tests for the backend were the strong point.)

## [1.1.0] - 2026-05-15 -- i18n, Blueprint Pipeline, Versionierung

(Historical; this tag was aspirational.  Real shipped state
included i18n scaffolding (14 locales, EN SSOT) and the
Blueprint-canvas pipeline, but the Workspace / Browse views
were not yet functional, and the LLM-Activity monitor was
embedded in the header without a clear visual marker.)

[0.3.0]: https://github.com/asb-42/danwa/releases/tag/v0.3.0
