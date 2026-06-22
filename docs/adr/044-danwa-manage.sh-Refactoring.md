# ADR-044: danwa manage.sh Refactoring

**Status:** Accepted
**Date:** 2026-06-22
**Context:** What was the problem?

<!-- Beschreibe den Hintergrund und das Problem, das diese Entscheidung erfordert hat -->

The legacy `danwa/manage.sh` was a 799-line monolith that mixed shared
bash primitives (logging, PID handling, version checks, URL polling) with
repository-specific orchestration (backend/frontend/studio lifecycle,
doc generation, ADR management, interactive dashboard). It had no
tests and no separation of concerns.

After Phases 1–7 of [`plans/2026-06-22_repo-setup-orchestration.md`](../../plans/2026-06-22_repo-setup-orchestration.md)
shipped a shared `libdanwa.sh` v1.0.0 and dedicated manage/setup
templates for `danwa-core` (Phase 3) and `danwa-studio` (Phase 6), the
user-app `danwa` was the only repository still running on the old
single-file pattern.

The refactor brings `danwa` into the family so:

1. All three repos share the same bash library (`scripts/libdanwa.sh`),
   ensuring `log_info`, `pid_running`, `kill_pid`, `wait_for_url`,
   `check_node_version`, `load_repo_config`, `discover_siblings`, etc.
   behave identically across the family.
2. The repo-specific lifecycle (Vite user-app + sibling danwa-studio
   + uvicorn backend via `uv`) lives in a single canonical template
   (`repo-templates/danwa/manage.sh`) that is mirrored into the actual
   repo clone.
3. The legacy 23 commands (`start [be|fe|studio|all]`, `stop`,
   `restart`, `status [--json]`, `logs [be|fe|st|all]`, `clean`,
   `dashboard`, `doc*`, `adr-new`, `adr-check`, …) are preserved 1:1
   to guarantee no functional regression.

**Decision:** What was decided?

<!-- Beschreibe die getroffene Entscheidung -->

We adopt the same template + shim strategy already used by `danwa-core`
(Phase 3 commit `ec367a9`) and `danwa-studio` (Phase 6 commit
`a0b8dbb`):

1. **Canonical template:** [`repo-templates/danwa/manage.sh`](../../repo-templates/danwa/manage.sh)
   and [`repo-templates/danwa/setup.sh`](../../repo-templates/danwa/setup.sh)
   are the single source of truth. All future edits go there.

2. **Root shims:** [`../../manage.sh`](../../manage.sh) and
   [`../../setup.sh`](../../setup.sh) at the danwa repo root become
   thin ~25-line executables that `exec bash` the template. They
   explicitly export `DANWA_PROJECT_DIR` to the repo root so the
   template's path resolution stays correct when invoked from a
   different working directory.

3. **Library reuse:** The template sources `libdanwa.sh` from
   `.lib/libdanwa.sh` (vendored by `setup.sh`) or `scripts/libdanwa.sh`
   (the monorepo's canonical copy) — same priority chain as the
   sibling repos.

4. **No command removed:** Every command documented in §1.3 of the
   orchestration plan is present and behaves identically. `status
   --json` is added (parity with `danwa-core` Phase 5 commit `dba6851`).

5. **Test pyramid:** 26 bats tests in
   [`tests/scripts/manage_danwa.bats`](../../tests/scripts/manage_danwa.bats)
   cover the full command surface; 7 bats tests in
   [`tests/scripts/setup_danwa.bats`](../../tests/scripts/setup_danwa.bats)
   cover toolchain checks, libdanwa fetch, sibling detection, and
   idempotency. The full `tests/scripts/` suite now reports 110/111
   pass — the one failure (`setup_studio.bats: fails when node is not
   available`) is a pre-existing Phase 6 issue unrelated to this
   refactor.

**Consequences:** What are the consequences?

<!-- Beschreibe die positiven und negativen Konsequenzen -->

Positive:

- **No functional regression.** Every command preserved 1:1; smoke
  test confirms `help`, `status`, `start be`, `stop be`, `status
  --json`, `adr-new` all work through the root shim.
- **Test coverage** for the first time: 33 new bats tests pin the
  legacy CLI surface so future refactors can't break it silently.
- **Single source of truth** for `danwa` lifecycle logic — easier to
  audit, easier to update (one file in `repo-templates/`).
- **Library parity** with `danwa-core` and `danwa-studio` —
  consistent logging colours, consistent exit codes, consistent
  `--json` schema for studio consumption.
- **Path safety:** all PID/log paths now derive from
  `DANWA_PROJECT_DIR` rather than the script's own location, fixing
  the long-standing "shim-in-subdir" bug.

Negative:

- **One extra indirection:** contributors now edit
  `repo-templates/danwa/manage.sh` rather than `manage.sh`. Mitigated
  by the shim's error message which points to the template when
  missing.
- **No CWD portability without `DANWA_PROJECT_DIR`** if invoked via
  `bash /path/to/manage.sh`. Mitigated by the shim's default
  `DANWA_PROJECT_DIR=$SCRIPT_DIR`.

**Affected Files:**

<!-- Liste der betroffenen Dateien -->

- `repo-templates/danwa/manage.sh` — NEW canonical template (≈520 lines)
- `repo-templates/danwa/setup.sh` — NEW canonical template (≈135 lines)
- `manage.sh` — REPLACED with thin shim (25 lines, was 799)
- `setup.sh` — REPLACED with thin shim (23 lines, was 14)
- `.danwa-config` — NEW (12 lines, mirrors §2.3 of orchestration plan)
- `tests/scripts/manage_danwa.bats` — NEW (26 bats tests)
- `tests/scripts/setup_danwa.bats` — NEW (7 bats tests)
- `.lib/libdanwa.sh` — vendored by `setup.sh` (committed by setup, not
  in git)
- `docs/adr/044-danwa-manage.sh-Refactoring.md` — this file

**Alternatives Considered:**

<!-- Welche Alternativen wurden geprüft und warum verworfen? -->

1. **Leave `manage.sh` as-is, just write tests.** Rejected: doesn't
   solve the lack of library reuse; the plan mandates split.
2. **Use git submodules** to import libdanwa.sh. Rejected: same
   rationale as Phase 1 (`libdanwa.sh` is small and stable; submodules
   add complexity without benefit).
3. **Inline `libdanwa.sh`** into `manage.sh` (single-file approach).
   Rejected: defeats the purpose of the shared library; bloats
   `manage.sh` again.
4. **Move `danwa/manage.sh` to `scripts/manage.sh`.** Rejected: breaks
   the user-facing CLI surface (`./manage.sh start be` at the repo root).
