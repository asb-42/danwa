# Installing & Running danwa

> **Quickstart guide** for the `danwa` user-facing app.
> For architecture, design decisions, and the full feature list see [`README.md`](README.md) (English) or [`README.zh.md`](README.zh.md) (中文).

This document is part of the multi-repo orchestration described in
[`plans/2026-06-22_repo-setup-orchestration.md`](plans/2026-06-22_repo-setup-orchestration.md)
(Phase 9).

---

## Prerequisites

| Tool | Min version | How to install |
|------|-------------|----------------|
| **Node.js** | 22.x | `nvm install 22` (or use your distro's package manager) |
| **npm** | bundled with Node | comes with Node.js |
| **curl** | any | usually pre-installed |
| **git** | any | usually pre-installed |

The Python backend lives in a sibling repository (`danwa-core`); you do
**not** need Python on this repo for the frontend-only workflow.

For the full backend experience (uvicorn + all routers) install the
sibling `danwa-core` repo, which additionally requires:

- **Python 3.11+**
- **uv** (Astral's Python package manager — `curl -LsSf https://astral.sh/uv/install.sh \| sh`)

---

## Quickstart

Three commands get you running from a fresh clone:

```bash
# 1. Install dependencies (Node 22, npm install, vendoring libdanwa.sh)
bash setup.sh

# 2. Start the user-app frontend (Vite, port 5173)
bash manage.sh start fe

# 3. Open the app
xdg-open http://localhost:5173  # or visit it in your browser
```

The frontend will start on **http://localhost:5173**. It will try to
talk to a backend on **http://localhost:7860** (the danwa-core default).
If you don't have `danwa-core` running, the frontend will show a
"backend not reachable" banner but still renders the UI.

For the **interactive dashboard** (start/stop components from a menu):

```bash
bash manage.sh dashboard
```

For a quick **status overview**:

```bash
bash manage.sh status              # human-readable
bash manage.sh status --json       # machine-readable (for danwa-studio)
```

---

## Sibling-Setup (Full Stack)

For the full debate / multi-agent experience you need three repositories
side-by-side:

```
parent-dir/
├── danwa-core/        # Backend (uvicorn + FastAPI)
├── danwa/             # User-frontend (Vite, port 5173)  ← THIS REPO
└── danwa-studio/      # Admin/dev-frontend (Vite, port 5174)
```

`danwa-core` is the **central orchestrator**: its `manage.sh` starts the
backend **and** any sibling frontends it detects in the parent directory.

### Recommended one-stop setup

```bash
# 1. Clone all three repos as siblings
mkdir ~/danwa-stack && cd ~/danwa-stack
git clone https://github.com/asb-42/danwa-core.git
git clone https://github.com/asb-42/danwa.git
git clone https://github.com/asb-42/danwa-studio.git

# 2. From danwa-core: bootstrap the whole stack
cd danwa-core
bash setup.sh        # installs uv, Python deps, vendors libdanwa.sh
bash manage.sh start # starts backend + auto-detects danwa + danwa-studio
```

`danwa-core/manage.sh` will print the URLs of every component it
started. Default ports:

| Component | Port | URL |
|-----------|------|-----|
| danwa-core backend (API + docs) | 8000 | http://localhost:8000/docs |
| danwa (user-app) | 5173 | http://localhost:5173 |
| danwa-studio (admin/dev) | 5174 | http://localhost:5174 |

### Standalone setup (this repo only)

If you only want the **frontend**:

```bash
cd danwa
bash setup.sh        # installs Node deps, vendors libdanwa.sh
bash manage.sh start fe
```

You'll see "no danwa-core sibling detected" — that's expected; start
the backend manually or clone `danwa-core` next to this repo.

---

## Shared Library — `libdanwa.sh`

All `setup.sh` and `manage.sh` scripts in the `danwa-*` repo family
source a shared bash library called **`libdanwa.sh`**
([`scripts/libdanwa.sh`](scripts/libdanwa.sh)). It provides:

- Colorised logging (`log_info`, `log_ok`, `log_warn`, `log_error`)
- Process management (`pid_running`, `kill_pid`, `wait_for_url`, `wait_for_port`)
- Toolchain checks (`check_node_version`, `check_python_version`, `check_uv_installed`)
- Repo-config loading (`load_repo_config`, `discover_siblings`)

**Current version:** **v1.0.0** (see `LIBDANWA_VERSION` at the top of
[`scripts/libdanwa.sh`](scripts/libdanwa.sh)).

On first `bash setup.sh`, the library is **vendored** into
[`.lib/libdanwa.sh`](.lib/libdanwa.sh) for offline operation. To update
to a newer release:

```bash
bash setup.sh            # re-vendors if the source-of-truth file changed
# or:
cp ../danwa-modules/scripts/libdanwa.sh .lib/libdanwa.sh
```

The `manage.sh` shim refuses to start if the vendored library is on an
incompatible major version (anything not matching `v1.*`).

---

## Studio → Backend Restart

If you use **danwa-studio** (the admin/dev frontend at port 5174), it
exposes a **graceful backend-restart button** in the
`SystemManagementView`. Under the hood it calls:

```
POST http://localhost:8000/api/v1/system/restart-backend
```

The endpoint (`backend/api/routers/system_control.py`) does **not**
restart itself — it sends `SIGTERM` to the running uvicorn process after
a 200 ms delay. The `danwa-core/manage.sh` watcher loop (enabled via
`BACKEND_WATCHER_ENABLED=1`) detects the death and respawns the backend.

This means: **do not kill the backend with `kill -9` from your
terminal** if the watcher is enabled — let the Studio restart button do
it gracefully so the watcher can bring it back up.

Other useful endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET  /api/v1/system/status` | Health + pids + uptime (always 200) |
| `POST /api/v1/system/stop-backend` | Graceful stop (no auto-respawn) |
| `POST /api/v1/system/restart-backend` | Graceful restart (with watcher) |
| `POST /api/v1/system/reload-config` | Reload LLM profiles / prompts |

---

## Troubleshooting

### `ERROR: libdanwa.sh not found. Run setup.sh first.`

You tried to run `manage.sh` before `setup.sh`. Fix:

```bash
bash setup.sh
```

If `setup.sh` itself can't find `libdanwa.sh`:

```bash
# Manual fallback: copy from the monorepo or fetch from danwa-modules
cp ../danwa-modules/scripts/libdanwa.sh .lib/libdanwa.sh
# or:
curl -L https://raw.githubusercontent.com/asb-42/danwa-modules/main/scripts/libdanwa.sh \
     -o .lib/libdanwa.sh
```

### `Backend läuft nicht` / frontend shows "backend not reachable"

The user-frontend (port 5173) needs the backend on port 7860 (or
whatever `BACKEND_PORT` is set to in `.danwa-config`). Either:

- Start the backend sibling: `cd ../danwa-core && bash manage.sh start be`, or
- Override `BACKEND_PORT` to point at an existing backend:
  `BACKEND_PORT=8000 bash manage.sh start fe`

### `Port 5173 already in use`

Another Vite dev-server (or another instance of danwa) is bound to the
port. Either stop the other instance or pick a different port:

```bash
FRONTEND_PORT=5273 bash manage.sh start fe
```

### `npm install` fails in `setup.sh`

Usually a Node version mismatch. Verify:

```bash
node --version    # must be v22.x or later
```

If you use `nvm`: `nvm use 22` (or `nvm install 22`).

### `manage.sh adr-new` writes to the wrong directory

`adr-new` creates files under `docs/adr/` relative to the repo root
(`DANWA_PROJECT_DIR`). If you ran `bash /some/other/path/manage.sh`,
set `DANWA_PROJECT_DIR` explicitly:

```bash
DANWA_PROJECT_DIR=/path/to/danwa bash /path/to/danwa/manage.sh adr-new "Title"
```

### Manage script: `Unbekannter Befehl`

You're calling a command that doesn't exist. Run `bash manage.sh help`
for the full list.

### How do I update an already-running backend without losing sessions?

Use the Studio UI restart button (graceful, watcher-aware), **not**
`kill -9`. See the "Studio → Backend Restart" section above.

---

## Files in this repo

| Path | Purpose |
|------|---------|
| [`setup.sh`](setup.sh) | Thin shim → [`repo-templates/danwa/setup.sh`](repo-templates/danwa/setup.sh) |
| [`manage.sh`](manage.sh) | Thin shim → [`repo-templates/danwa/manage.sh`](repo-templates/danwa/manage.sh) |
| [`repo-templates/danwa/manage.sh`](repo-templates/danwa/manage.sh) | Canonical manage template (single source of truth) |
| [`.danwa-config`](.danwa-config) | Repo metadata (BACKEND_PORT, FRONTEND_PORT, …) |
| [`scripts/libdanwa.sh`](scripts/libdanwa.sh) | Shared bash library v1.0.0 (sourced by all danwa-* scripts) |
| [`.lib/libdanwa.sh`](.lib/libdanwa.sh) | Vendored copy (created by `setup.sh`) |
| [`tests/scripts/`](tests/scripts/) | bats test suite (33 tests for manage+setup+install-doc) |

---

## See also

- [`README.md`](README.md) — project overview, features, architecture
- [`README.zh.md`](README.zh.md) — 中文版
- [`plans/2026-06-22_repo-setup-orchestration.md`](plans/2026-06-22_repo-setup-orchestration.md) — multi-repo orchestration plan (Phases 1–11)
- [`docs/adr/044-danwa-manage.sh-Refactoring.md`](docs/adr/044-danwa-manage.sh-Refactoring.md) — ADR for the Phase 8 manage.sh refactor
- `../danwa-core/INSTALL.md` — install guide for the backend repo (sibling)
- `../danwa-studio/INSTALL.md` — install guide for the admin/dev frontend (sibling)