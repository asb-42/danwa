# UI/UX Hardening & Modernization Sprint (Sprints 1–26)

Systematische Behebung der im Audit gefundenen UI/UX-Befunde, plus
Modernisierung auf Svelte 5 Runes und Performance-Optimierung.

**Branch:** `fix/ui-ux` · **Commits:** 25 · **Files:** 118 (+1,965 / −1,916)
**Tests:** 108/108 grün · **Build:** OK in ~8s

---

## Summary

| Category | Fixes | Severity |
|----------|-------|----------|
| Critical bugs | 6 | XSS, tenant-switch, token-race, OOB-sync, edge-lookup |
| High-priority a11y | 14 | keyboard, aria, touch-targets, form-validation, contrast |
| High-priority UX | 8 | silent errors → toast, locale-aware formatting |
| Svelte 5 migration | 100+ files | `let` → `$state`, `$:` → `$derived`, `on:event` → `onevent` |
| i18n | 110 keys added; 70+ files | `tStore` pattern, no raw `i18n.t` in views |
| Performance | Initial bundle **2,816 KB → 321 KB** (−89%) | lazy view loading |
| Polish | 39 unused imports removed; 60 console calls DEV-guarded | dev noise reduction |
| A11y infra | 17 modals `aria-labelledby`; 12 `svelte-ignore` removed | a11y testing baseline |

---

## Sprint-by-Sprint Detail

### Critical Security / Correctness (Sprints 1, 20)
- **Sprint 1** — XSS via `innerHTML` (DOMPurify whitelist), tenant-switch leaks stale data, token-refresh race → singleton promise, `<Title>` klaartext leaks.
- **Sprint 20** — **2 production bugs found in workflow runtime**:
  - `graphReducer.js:303` looked up `FEEDBACK_LOOP.hasFeedbackLoop` in `graphEdges` Map but stored it on nodes → wrong key. Fixed.
  - `oob.js:117` `markOOBConsumed` desynced `oobQueueIndexByTarget` from the queue. Fixed via Map rebuild.
  - `oobRouter.routeOOB` migrated from module-level `get(runtime)` to explicit `(store, oob)` signature — required for tests.

### User-facing errors & locale (Sprints 2, 3, 8, 9, 10, 14, 15)
- **Sprint 3** — `window.confirm()` → `ConfirmDialog` component (focus-trap, Esc, i18n). 8 stille `catch {}` → toast.
- **Sprint 8** — 8 hardcoded auth-error fallbacks → `i18n.t('auth.errors.*')`.
- **Sprint 9–10** — 13 hardcoded English metric/form labels in `MvpDebateView`/`DebateSetupForm` → i18n.
- **Sprint 2** — `formatDate`/`formatNumber` now locale-aware; `error.set(null)` clears stale errors on route change.

### Network UX (Sprint 23)
- 6 stille User-Fehler jetzt sichtbar via `addToast`: DocumentUploader, CasesView save+delete, TagPicker create, BlueprintCanvasView start, CaseNavigator create.
- New `debounceToast(windowMs)` helper in `lib/stores.js` — module-scoped Map, key-based dedup (e.g. SSE reconnect spam).
- SSE event spam in `DebateView:209` + 4 `console.debug/log` calls behind `import.meta.env.DEV` gated.
- **5 new i18n keys** for the toast messages.

### Accessibility (Sprints 11, 12, 18, 24)
- **Sprint 11–12** — 17/17 modal dialogs now have `aria-labelledby` (id on inner heading).
- **Sprint 18** — 12 `svelte-ignore a11y_*` removed: Modal-Escape via `onkeydown` on `tabindex="-1"` div, dropdown click-outside via document-listener, **M19 disabled:hover** consistency on 73 buttons in 32 files.
- **Sprint 24** — 8 a11y findings closed:
  - `DiffView` CRITICAL keyboard bug: bare `click=`/`keydown=` (no `on`-prefix) → `onclick`/`onkeydown` with `preventDefault` on Space.
  - `AssistantChat` 4 resize-handles `touch-action: none`.
  - `UserManagement` invite-form `aria-invalid`/`aria-describedby`/`role="alert"` + 👁/🙈 password toggle + `min-h-[32px]` touch-target on remove button.
  - `TranslationDashboard` AddLocale: same form-validation pattern + `$effect` autofocus on code-input.
  - `LoginView` 👁/🙈 password toggle with `showPassword` + `aria-pressed` (both password fields toggle together).
  - `DebateView:598` separator `text-gray-300` → `text-gray-400` + `aria-hidden="true"`.
  - `InputComposerView:379` italic hint `text-gray-400` → `text-gray-500`.

### Critical/High Blockers (Sprint 22)
- **`<svelte:boundary>` um View-Switcher in `App.svelte`** mit `failed` Snippet (Retry + Back-to-Dashboard) — prevents one bad view from killing the whole app.
- `DocumentsView:3` — fehlender `i18n` Import verursachte `ReferenceError` in production.
- `ExecutionPanel` — duplicate `onNodeError` handler removed.
- 4× `change=` (ohne `on`-Präfix) → `onchange=` in ReplayView, DiffView×2, ReplayControls.
- `ServerHealthView` — 30s polling + `onDestroy` cleanup.
- `CasesView` — CSS-Typo `bg-red--50` → `bg-red-50`.

### Svelte 5 Runes Migration (Sprints 16–19)
- **tStore pattern** in 72/72 files: `import { i18n, tStore }` → `let t = $derived($tStore)`. Mass-migration via Node-script with brace-counting. No more direct `i18n.t` calls in components.
- **Sprint 17** — 17 edge-case files: forms mit inline-Pfeil, Workflow `$: _ = $i18n`, plus pre-existing `$: X = ...` → `$derived`. `export let` → `$props()`.
- **Sprint 18** — 12 `svelte-ignore a11y_*` removed.
- **Sprint 19** — 22 `on:event` → `onevent` (REVERSE iteration wegen shifting indices); 37 `let X = literal` → `let X = $state(literal)` in files with existing runes.

### Performance (Sprint 25)
- 27 eager view imports in `App.svelte` → dynamic `import()` inside `{#await}` blocks.
- **Initial bundle: 2,816 KB → 321 KB (−89%)**. Heavy chunks deferred:
  - `elk-service` 1,436 KB — only on `#/blueprint`
  - `BlueprintCanvasView` 212 KB (with `@xyflow/svelte`)
  - `style` 176 KB (xyflow CSS)
  - 24 view chunks 10–74 KB each
- Svelte's `{#await}` handles cancellation on re-render — rapid route changes don't leak state.

### Polish (Sprint 26)
- **39 unused named imports** removed across 19 files (audit via occurrence counting after import line removal).
- **60 `console.warn/error/log` calls** wrapped in `if (import.meta.env.DEV)` so production users don't see dev noise. Final sweep across remaining files; Sprints 22–24 already covered the critical paths.

---

## Test & Build Verification

```
$ npm run build
✓ built in 7.99s
dist/assets/index-*.js   321.05 kB │ gzip:  98.97 kB
dist/assets/elk-service  1436.27 kB │ gzip: 438.36 kB  (lazy)

$ npx vitest run
Test Files  8 passed (8)
Tests      108 passed (108)
```

---

## Follow-up Issues (out of scope)

- **Manual a11y audit** of all 18 views with screen reader (NVDA/VoiceOver) — automated axe-core passed for ARIA but live regions need human validation.
- **TypeScript migration** of component prop types — currently `$props()` without `let { x }: { x: string } = $props()`. Would catch typos in callers.
- **`<svelte:options runes={true}>` opt-in per-file** instead of relying on file pattern — current setup uses Svelte 5 default but the explicit annotation makes intent clear.
- **240+ `request()` callers in `lib/api/core.js`** — internal refactor only; current signature stable. Touches only in-sprint modifications.
- **Pre-existing untracked changes** (`AGENTS.md`, `CLAUDE.md`, deleted `backend/workflow/nodes.py`) — not included in this PR.

---

## Risk Assessment

- **App.svelte changes** — all routing logic preserved; only imports moved to dynamic.
- **tStore migration** — same call signature `(key, params) => string`; behavior identical.
- **Sprint 20 production bug fixes** — `graphReducer` and `oob` are pure functions; tests cover the new behavior.
- **Boundary in Sprint 22** — only fires on thrown errors; happy path unchanged.

Closes all 200+ findings from the 5 explore-subagent reports.
