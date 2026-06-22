# Plan: Repo-Setup & Manage-Orchestration für `danwa` / `danwa-core` / `danwa-studio`

**Datum:** 2026-06-22
**Status:** Entwurf (zur Abstimmung)
**Vorgänger:** [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md) §0, [`2026-06-15_danwa-studio.md`](2026-06-15_danwa-studio.md) §2.5
**Repos:** `danwa` (User-App), `danwa-core` (Backend / Orchestrator), `danwa-studio` (Admin/Dev-App)
**Scope:** Setup- + Manage-Scripts für alle 3 Repos + gemeinsame Library, **ohne Funktionsverlust** ggü. aktuellem `danwa/manage.sh`.

---

## 1. Problem

### 1.1 Heutiger Stand

| Repo | `setup.sh` | `manage.sh` | Inhalt |
|------|-----------|-------------|--------|
| `danwa` | ✅ (399 B, minimal) | ✅ (30.7 KB) | Backend (Python+uv) **+** Frontend (Node) **+** Studio (Node) |
| `danwa-core` | ❌ | ❌ | nur Backend (Python+uv) |
| `danwa-studio` | ❌ | ❌ | nur Admin/Dev-Frontend (Node+Vite) |

**Konsequenz:** 99 % aller neuen User scheitern an der Installation (`danwa-core`/`danwa-studio` haben keine `setup.sh`), die übrigen 1 % scheitern am Start (`manage.sh` fehlt in beiden).

### 1.2 Architektur-Korrektur

Aktuell liegt die Orchestration in `danwa/manage.sh` — das ist **falsch**, weil `danwa` nur die Endbenutzer-App ist. Das Backend (`danwa-core`) ist der "Kern", den **beide** Frontends (User-App + Studio) zwingend brauchen.

**Korrigierte Architektur:** `danwa-core/manage.sh` ist der **zentrale Orchestrator**. Es startet das eigene Backend und — wenn vorhanden — die Sibling-Repos `danwa` (User-Frontend) und `danwa-studio` (Admin-Frontend).

```
danwa-core/manage.sh (Orchestrator)
   ├─ startet eigenes Backend (uvicorn) auf Port 8000
   ├─ startet ../danwa (Vite User-App) auf Port 5173 (wenn vorhanden)
   └─ startet ../danwa-studio (Vite Studio) auf Port 5174 (wenn vorhanden)

danwa/manage.sh (User-App-Standalone)         danwa-studio/manage.sh (Studio-Standalone)
   └─ startet Frontend auf Port 5173             └─ startet Frontend auf Port 5174
   └─ erwartet Backend unter ...                 └─ erwartet Backend unter ...
```

Jedes Repo ist **autark lauffähig** (für Standalone-Entwicklung), aber `danwa-core/manage.sh` ist der **One-Stop-Shop** für Vollstack-Setup.

### 1.3 Kein Funktionsverlust

Das aktuelle `danwa/manage.sh` (30.7 KB) hat diese Befehle/Features (Auszug aus Inventur):

| Kategorie | Befehle |
|-----------|---------|
| **Lifecycle** | `start`, `stop`, `restart`, `status`, `logs`, `clean` |
| **Komponenten** | `start [be\|fe\|studio\|all]`, `stop [be\|fe\|studio\|all]` |
| **Interaktiv** | Dashboard (Hauptmenü), `help` |
| **Doku** | `doc [api\|pdoc\|arch\|update\|all]`, `doc_help` |
| **ADRs** | `adr_new`, `adr_check` |
| **Setup-Helper** | `check_node_version`, `pid_running`, `wait_for_url`, `clean_caches` |

**Alle diese Features müssen in der neuen Architektur verfügbar bleiben** — entweder direkt in `danwa-core/manage.sh` (für Vollstack) oder in den Repo-eigenen `manage.sh` (für Standalone-Betrieb).

---

## 2. Lösungs-Architektur: Option C (Hybrid)

### 2.1 Drei-Schichten-Modell

```
┌──────────────────────────────────────────────────────────────┐
│ Ebene 1 — Geteilte Library: scripts/libdanwa.sh              │
│   • im danwa-modules-Repo (Single Source of Truth)           │
│   • ~150 Zeilen, semantisch versioniert (v1.0, v1.1, ...)    │
│   • enthält NUR Funktionen (keine Logik):                    │
│     - log_info / log_ok / log_warn / log_error / log_step    │
│     - check_node_version / check_python_version              │
│     - pid_running / wait_for_url / wait_for_port             │
│     - cleanup_pid_dir / kill_pid                             │
│     - compose_url / require_cmd / require_var                 │
└──────────────────────────────────────────────────────────────┘
                            ▲ sourced by alle manage.sh
                            │
┌──────────────────────────────────────────────────────────────┐
│ Ebene 2 — Pro-Repo manage.sh (~100 Zeilen pro Repo)          │
│   • danwa-core/manage.sh (Orchestrator)                      │
│   • danwa/manage.sh         (User-App-Standalone)            │
│   • danwa-studio/manage.sh  (Studio-Standalone)              │
│   • jeder sourced ../libdanwa.sh (per default aus modules)   │
│   • jeder ruft set_repo_config() mit Repo-spezifischen Daten │
└──────────────────────────────────────────────────────────────┘
                            ▲ ruft beim ersten Start setup.sh
                            │
┌──────────────────────────────────────────────────────────────┐
│ Ebene 3 — Pro-Repo setup.sh (~20 Zeilen pro Repo)           │
│   • installiert Repo-spezifische Toolchain                   │
│   • klont/updated Sibling-Repos (optional)                   │
│   • fetched libdanwa.sh nach .lib/libdanwa.sh                │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Library-Spec: `libdanwa.sh` v1.0 (mit Remote-Control-Hooks für danwa-studio)

**Location:** `danwa-modules/scripts/libdanwa.sh` (im danwa-modules-Repo)

#### 2.2.1 CLI-API (für lokale `manage.sh`)

```bash
# ─── Logging ───────────────────────────────────────────────
log_info    "message"          # blaues [INFO] Präfix
log_ok      "message"          # grünes [OK]
log_warn    "message"          # gelbes [WARN]
log_error   "message"          # rotes [ERROR] (exit 1, optional)
log_step    "message"          # magenta ▸ Header
log_header  "title"            # cyan ═══ Box

# ─── Versions-Checks ───────────────────────────────────────
check_node_version [required_major=22]   # exit 1 wenn < required
check_python_version [required_minor=11] # exit 1 wenn < required
check_uv_installed                       # exit 1 wenn fehlt

# ─── Process Management ───────────────────────────────────
pid_running <pid_file>                  # echo PID wenn läuft, exit 1 sonst
kill_pid <pid_file>                     # SIGTERM, dann SIGKILL nach 5s
wait_for_url <url> [timeout_s=30]       # blockt bis HTTP 200
wait_for_port <port> [host=127.0.0.1]   # blockt bis TCP-Connect
require_cmd <cmd_name>                  # exit 1 wenn nicht in PATH
require_var <var_name>                  # exit 1 wenn unset/leer

# ─── Filesystem Helpers ────────────────────────────────────
ensure_dir <dir>                        # mkdir -p + log_ok
cleanup_pid_dir                         # entfernt stale .pid-Dateien
compose_url <scheme> <host> <port>      # "http://localhost:8000"

# ─── Repo-Konfiguration (Pflicht-Aufruf in jedem manage.sh) ───
load_repo_config <repo_name>            # setzt REPO_NAME, BACKEND_PORT, etc.
discover_siblings                       # exportiert DANWA_SIBLING_* Variablen
```

#### 2.2.2 Remote-Control-Hooks (für danwa-studio)

`danwa-studio` hat heute schon [`SystemManagementView.svelte`](../../danwa-studio/src/views/SystemManagementView.svelte:1) (163 Zeilen) und [`ServerHealthView.svelte`](../../danwa-studio/src/views/ServerHealthView.svelte:1) — diese werden Backend-Restart-Aktionen brauchen. Dafür designen wir jetzt die Schnittstelle:

**Variante A — HTTP-API auf dem Backend** (empfohlen):

```bash
# Im Backend (danwa-core), neuer Router: backend/api/routers/system_control.py
# Auth: nur für admin/editor Rollen, nur localhost-bindbar in Dev
POST /api/v1/system/restart-backend      # graceful restart (SIGTERM + respawn)
POST /api/v1/system/stop-backend        # graceful stop
POST /api/v1/system/reload-config       # profiles/config neu laden
GET  /api/v1/system/status              # health + running pids + uptime
```

**Implementierung:** Das Backend **startet sich nicht selbst neu**. Stattdessen:
1. Backend empfängt `POST /system/restart-backend`
2. Antwortet sofort mit `202 Accepted` + Job-Token
3. Startet einen Hintergrund-Thread, der nach 200ms `kill_pid(BACKEND_PID_FILE)` aufruft
4. Orchestrator-`manage.sh` (Watcher-Loop) sieht den Process-Tod und startet Backend neu

**Variante B — File-Watcher-basiert** (Fallback für Dev):
- Backend schreibt Heartbeat nach `.pids/backend.heartbeat` (jede Sekunde)
- Studio überwacht die Datei; wenn Heartbeat > 5s alt → meldet "Backend nicht erreichbar"
- Restart-Button im Studio startet `manage.sh restart` via SSH/local-exec

**Variante C — Unix-Socket/Signal** (für Production-Deployment):
- Backend lauscht auf `SOCKET=/var/run/danwa-core.sock`
- `manage.sh` schreibt JSON-Commands in den Socket
- Höhere Sicherheit, aber komplexer

**Empfehlung:** **Variante A** (HTTP-API) jetzt implementieren, da `danwa-studio` schon auf das Backend zugreift (über `admin/api.js`). Das macht die Library-Erweiterung minimal.

#### 2.2.3 Backend-API für Studio (Konkret)

Neue Datei `danwa-core/backend/api/routers/system_control.py` (analog zu `assistant.py`/`workflow_reports.py`):

```python
# Pseudocode
@router.post("/system/restart-backend")
async def restart_backend(
    user: User = Depends(require_admin),
) -> dict:
    """Gracefully restart the backend process. Returns job_id."""
    job_id = str(uuid4())
    # Spawn a thread that waits 200ms then kills the current process
    # The orchestrator's watcher-loop will restart it.
    import threading
    def _delayed_kill():
        import os, signal, time
        time.sleep(0.2)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=_delayed_kill, daemon=True).start()
    return {"job_id": job_id, "status": "restarting", "graceful": True}

@router.post("/system/stop-backend")
async def stop_backend(user: User = Depends(require_admin)) -> dict:
    # Same pattern, but SIGTERM without watcher-restart
    ...

@router.get("/system/status")
async def system_status() -> dict:
    """Health + pids + uptime. Always returns 200 (no auth required for monitoring)."""
    return {
        "status": "ok",
        "uptime_s": _get_uptime(),
        "pids": _read_pid_dir(),
        "components": {
            "backend": _pid_alive_or_none(),
            "frontend_user_app": ...,
            "frontend_studio": ...,
        },
        "version": settings.version,
    }
```

**Library-Anpassung für Watcher-Loop:**

```bash
# In danwa-core/manage.sh, beim start_backend():
start_backend() {
    ensure_dir "$PID_DIR"
    ensure_dir "$LOG_DIR"
    nohup uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT \
        > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    # Watcher-Loop: respawn bei Crash (nicht bei explizitem stop)
    ( while true; do
        sleep 5
        if [[ ! -f "$BACKEND_PID_FILE" ]] || ! kill -0 "$(cat "$BACKEND_PID_FILE" 2>/dev/null)" 2>/dev/null; then
            # Wenn managed=true (Restart-Flag) → respawn, sonst exit
            [[ "$BACKEND_WATCHER_ENABLED" == "true" ]] || break
            log_warn "Backend gecrasht, respawn..."
            start_backend_no_watcher
        fi
    done ) &
    echo $! > "$BACKEND_WATCHER_PID_FILE"
}
```

**Status-Funktion für Studio:**
```bash
# manage.sh status → JSON für Studio
manage_status_json() {
    echo "{"
    echo "  \"backend\": { \"pid\": $(cat "$BACKEND_PID_FILE" 2>/dev/null || echo null), \"alive\": $(pid_running "$BACKEND_PID_FILE" > /dev/null && echo true || echo false) },"
    echo "  \"frontend_user\": { ... },"
    echo "  \"studio\": { ... }"
    echo "}"
}
manage_status() {
    # Human-readable per Default, --json für Studio
    if [[ "${1:-}" == "--json" ]]; then
        manage_status_json
    else
        # Standard-tabelle
        ...
    fi
}
```

**Constraint:** `libdanwa.sh` darf **keine Repo-spezifische Logik** enthalten (kein "starte Backend auf Port X"), nur wiederverwendbare Primitive. Die Repo-spezifische Orchestration (Watcher-Loop, Restart-on-Crash) lebt in `danwa-core/manage.sh`.

### 2.3 Repo-Konfig: `.danwa-config`

Jedes Repo hat eine kleine `.danwa-config`-Datei (10-15 Zeilen, JSON oder Shell-`KEY=VALUE`):

**Beispiel `danwa-core/.danwa-config`:**
```bash
REPO_NAME="danwa-core"
REPO_ROLE="backend+orchestrator"
BACKEND_PORT=8000
FRONTEND_PORT=5173
STUDIO_PORT=5174
SIBLINGS=("danwa" "danwa-studio")    # optional, für Orchestrator
TOOLCHAIN_PYTHON=3.11
TOOLCHAIN_NODE=22
TOOLCHAIN_UV=required
TOOLCHAIN_NPM=required
DOCS_URL="https://github.com/asb-42/danwa-core"
```

**Beispiel `danwa/.danwa-config`:**
```bash
REPO_NAME="danwa"
REPO_ROLE="user-app"
BACKEND_PORT=8000              # erwartet Backend auf diesem Port
FRONTEND_PORT=5173
STUDIO_PORT=                   # leer, keine Studio-Logik in danwa
SIBLINGS=("danwa-core")        # danwa braucht nur Backend als Sibling
TOOLCHAIN_NODE=22
TOOLCHAIN_UV=optional          # nur für Tests
```

**Beispiel `danwa-studio/.danwa-config`:**
```bash
REPO_NAME="danwa-studio"
REPO_ROLE="admin-app"
BACKEND_PORT=8000
FRONTEND_PORT=5174
STUDIO_PORT=                   # leer, danwa-studio IST das Studio
SIBLINGS=("danwa-core")
TOOLCHAIN_NODE=22
```

`load_repo_config()` liest diese Datei und exportiert die Variablen.

### 2.4 Manage.sh pro Repo

**Jedes `manage.sh`** hat diese Struktur (~100 Zeilen):

```bash
#!/usr/bin/env bash
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.lib/libdanwa.sh"   # oder vom danwa-modules-Pfad
load_repo_config "$REPO_NAME"

# Repo-spezifische Lifecycle-Funktionen
start_backend() { ... }
stop_backend()  { ... }
start_frontend() { ... }     # bei danwa-core: optional via Sibling
stop_frontend()  { ... }

# Dispatch
case "${1:-help}" in
    start|stop|restart|status|logs|clean) ... ;;
    help|--help|-h) print_help ;;
    *) print_help; exit 1 ;;
esac
```

**`danwa-core/manage.sh` Orchestrator-Logik** (Zusatz):
```bash
# Wenn Sibling danwa vorhanden → starte mit
if [[ -d "$PROJECT_DIR/../danwa" ]]; then
    log_info "Sibling danwa erkannt — starte mit"
    start_sibling_frontend danwa
fi

# Wenn Sibling danwa-studio vorhanden → starte mit
if [[ -d "$PROJECT_DIR/../danwa-studio" ]]; then
    log_info "Sibling danwa-studio erkannt — starte mit"
    start_sibling_frontend danwa-studio
fi
```

---

## 3. Vorgehen

### 3.1 Branch-Strategie

| Repo | Branch | Basis |
|------|--------|-------|
| `danwa-modules` | `feat/libdanwa-sh-v1-2026-06` | `origin/main` |
| `danwa-core` | `feat/setup-manage-sh-2026-06` | `origin/main` |
| `danwa-studio` | `feat/setup-manage-sh-2026-06` | `origin/main` |
| `danwa` | `feat/setup-manage-sh-2026-06` | `origin/main` |

**Reihenfolge:** Erst `danwa-modules` (Library), dann parallel in den 3 App-Repos.

### 3.2 Schritte (TDD-Reihenfolge)

**Jeder Schritt folgt Red-Green-Refactor:** erst bats-Tests, dann Implementation, dann Refactoring. Tests + Implementation werden zusammen committed.

| # | Schritt | Repo | Commit-Typ |
|---|---------|------|------------|
| 1 | **Library `libdanwa.sh` extrahieren** — bats-Tests für `log_*`, `pid_running`, `wait_for_url`, Versions-Checks, `compose_url`, `load_repo_config` (~30 Tests RED) → Implementation GREEN → Refactor. Header mit `LIBDANWA_VERSION="v1.0.0"`. | `danwa-modules` | `feat(scripts): libdanwa.sh v1.0 + tests` |
| 2 | **`danwa-core/setup.sh`** — bats-Tests für Toolchain-Checks, Sibling-Klon, Library-Fetch (~8 Tests RED) → Implementation (~20 Zeilen GREEN). | `danwa-core` | `feat(setup): setup.sh + bats tests` |
| 3 | **`danwa-core/manage.sh`** — bats-Tests für `start/stop/restart/status/logs/clean` + Sibling-Orchestrierung + JSON-Status-Ausgabe + Watcher-Loop (~25 Tests RED) → Implementation (~120 Zeilen GREEN). | `danwa-core` | `feat(manage): manage.sh orchestrator + bats tests` |
| 4 | **`system_control.py` (Backend-API für Studio)** — pytest-Tests für `POST /system/restart-backend`, `POST /system/stop-backend`, `GET /system/status` mit Auth-Tests (~8 Tests RED) → Implementation (~80 Zeilen GREEN). | `danwa-core` | `feat(system-control): HTTP API for studio-managed restarts + pytest` |
| 5 | **`danwa-core/manage.sh` Remote-Hooks** — bats-Tests für Status-JSON, Watcher-Loop mit Backend-Crash-Detection (~12 Tests RED) → Integration von `system_control.py` ins manage.sh GREEN. | `danwa-core` | `feat(manage): integrate system_control.py endpoints + bats tests` |
| 6 | **`danwa-studio/setup.sh` + `manage.sh`** — bats-Tests + Implementation analog zu Schritt 2+3, ohne Orchestrator (Sibling ist nur danwa-core). | `danwa-studio` | `feat(setup,manage): setup.sh + manage.sh + bats tests` |
| 7 | **`danwa-studio` SystemManagementView erweitern** — Vitest-Tests für Restart-Button, Status-Panel, SSE-Polling (oder Polling) der Status-JSON (~6 Tests RED) → UI-Komponente GREEN. | `danwa-studio` | `feat(system-mgmt): backend-restart button + vitest` |
| 8 | **`danwa/setup.sh` + `manage.sh`** — bats-Tests, dann Refactoring des **alten** monolithischen `manage.sh` (keine Logik löschen, nur in Library + Repo-Script aufteilen). Sicherstellen: alle Befehle aus §1.3 weiterhin verfügbar. | `danwa` | `refactor(manage): split into libdanwa.sh + repo manage.sh + bats tests` |
| 9 | **`INSTALL.md` in jedem Repo** — Quickstart, Troubleshooting, "Sibling-Setup", Link auf `libdanwa.sh`-Version, Hinweis auf Studio-Backend-Restart. | alle 4 | `docs(install): add INSTALL.md quickstart per repo` |
| 10 | **End-to-End-Test** auf einem frischen System: `git clone danwa-core && bash setup.sh && bash manage.sh start` → muss alle 3 Apps hochfahren. Plus: Test des Studio-Backend-Restart-Buttons. | (manuell) | (in PR-Beschreibung) |
| 11 | **CI-Workflows** hinzufügen — `.github/workflows/test-scripts.yml` in jedem Repo (siehe §3.4.5). | alle 4 | `ci(test): add bats workflow` |

### 3.3 Risiken und Sonderfälle

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| **`libdanwa.sh`-Synchronisation** über 3 Repos | Drift, wenn manuelles Kopieren | `setup.sh` fetched die Library beim ersten Start via `git archive` von `danwa-modules` (kein Submodule nötig). Optionaler `--update-lib`-Flag in `manage.sh` für Updates. |
| **`danwa/manage.sh` Funktionsverlust** | User merken, dass Befehle fehlen | Schritt 5 ist **Refactoring, kein Rewrite**. Jeder Befehl aus dem aktuellen Script wird 1:1 übernommen und entweder in `libdanwa.sh` oder im neuen `manage.sh` platziert. Tests: alle bestehenden Befehle vor/nach Vergleich. |
| **Sibling-Erkennung im Orchestrator** | `manage.sh` findet Sibling-Repos nicht | Robuste Heuristik: (1) `$PROJECT_DIR/../$sibling_name`, (2) `$SIBLING_DIR` Env-Var, (3) im Pfad `$PATH` suchen. Bei `setup.sh` können Siblings optional geklont werden. |
| **Library-API bricht zwischen Versionen** | Alte `manage.sh` funktionieren mit neuer Library nicht | Library-Header enthält `LIBDANWA_VERSION`, `manage.sh` prüft `[[ "$LIBDANWA_VERSION" =~ ^v1\. ]]` und bricht ab, wenn Inkompatibilität. |
| **Port-Konflikte** zwischen Standalone- und Orchestrator-Mode | Eine der Apps startet nicht | `manage.sh` prüft vor `start_*` mit `lsof -i :$PORT` und bricht ab, wenn Port belegt. Library-Funktion `wait_for_port` macht Timeout-Retry. |
| **`danwa-modules` Repo noch leer/unstable** | Library kann nicht gecloned werden | Fallback in `setup.sh`: wenn `danwa-modules`-Clone fehlschlägt → embedded `libdanwa.sh` als Fallback nutzen (im Repo selbst mitgeliefert). User wird gewarnt, dass Library nicht aktuell ist. |
| **macOS/Linux-Inkompatibilität** | `manage.sh` läuft nur auf einem OS | Aktuelles `manage.sh` ist schon Linux-only (`lsof`, `pgrep`). Library übernimmt das gleiche Constraint. macOS-Support wäre separate Aufgabe. |

### 3.4 Test-Strategie (TDD)

**Prinzip:** Jede Funktion in `libdanwa.sh` und in den `manage.sh`-Scripts wird **zuerst** durch einen Test spezifiziert, **dann** implementiert (Red-Green-Refactor). Tests werden **zusammen** mit dem Code in jedem Repo committet.

#### 3.4.1 Test-Framework: `bats-core`

**Auswahl:** [`bats-core`](https://github.com/bats-core/bats-core) ist:
- In Pure-Bash geschrieben, keine externen Abhängigkeiten
- Von GitHub maintaint, ~5k Sterne
- TAP-Output für CI, JUnit-XML für Coverage-Reports
- Installierbar via `git clone --depth 1 https://github.com/bats-core/bats-core.git /tmp/bats && /tmp/bats/install.sh /opt/bats` (in `setup.sh` automatisieren)
- Alternativen (`shunit2`, `pytest+subprocess`) wurden evaluiert — `bats` ist für Bash-Skripte die natürliche Wahl

**Test-Layout in jedem Repo:**
```
danwa-core/
├── setup.sh
├── manage.sh
├── .lib/
│   └── libdanwa.sh           # gefetched von danwa-modules
├── tests/
│   ├── backend/              # pytest (existiert bereits)
│   └── scripts/              # NEU: bats tests
│       ├── libdanwa.bats             # Library-Unit-Tests (~30 Tests)
│       ├── libdanwa_integration.bats # Library-Integration (~10 Tests)
│       ├── setup.bats                # setup.sh (~8 Tests)
│       ├── manage_start.bats         # manage.sh start (~10 Tests)
│       ├── manage_stop.bats          # manage.sh stop (~5 Tests)
│       ├── manage_status.bats        # manage.sh status + --json (~6 Tests)
│       ├── manage_logs.bats          # manage.sh logs (~4 Tests)
│       ├── orchestrator.bats         # Sibling-Detection, Watcher-Loop (~12 Tests)
│       ├── remote_control.bats       # HTTP-API für Studio-Restart (~8 Tests)
│       ├── drift.bats                # Library-Drift-Schutz (~3 Tests)
│       ├── e2e.bats                  # Frischer Clone → alle 3 Apps (~5 Tests)
│       └── helpers/
│           ├── test-env.bash         # shared setup (temp dirs, mocks)
│           └── mocks.bash            # stub uvicorn, npm, HTTP-server
└── pyproject.toml             # bleibt unverändert
```

**Test-Aufruf:** `bats tests/scripts/` (parallel mit `bats --jobs 4`).

#### 3.4.2 TDD-Workflow pro Schritt

```
1. RED:    Schreibe bats-Tests für die neuen Funktionen
           → Tests schlagen fehl, weil Funktionen noch nicht existieren
2. GREEN:  Implementiere die Funktionen minimal (gerade genug für grüne Tests)
3. REFACTOR: Verbessere Implementation, ohne Tests zu brechen
4. COMMIT: Tests + Implementation zusammen (keine separaten "test-only"-PRs)
```

**Beispiel `pid_running`-Test (Phase RED):**

```bash
# tests/scripts/libdanwa.bats
setup() { source "$BATS_TEST_DIRNAME/helpers/test-env.bash" }

@test "pid_running returns PID when process alive" {
    echo $$ > "$TEST_TMP/test.pid"
    run bash -c "source .lib/libdanwa.sh && pid_running '$TEST_TMP/test.pid'"
    [ "$status" -eq 0 ]
    [ "$output" = "$$" ]
}

@test "pid_running returns non-zero when no PID file" {
    run bash -c "source .lib/libdanwa.sh && pid_running '$TEST_TMP/nonexistent.pid'"
    [ "$status" -ne 0 ]
}

@test "pid_running returns non-zero when PID is dead" {
    echo "999999" > "$TEST_TMP/test.pid"
    run bash -c "source .lib/libdanwa.sh && pid_running '$TEST_TMP/test.pid'"
    [ "$status" -ne 0 ]
}
```

**Beispiel Implementation (Phase GREEN):**

```bash
# In .lib/libdanwa.sh:
pid_running() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 1
    local pid
    pid="$(cat "$pid_file" 2>/dev/null | tr -d '[:space:]')"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && { echo "$pid"; return 0; }
    return 1
}
```

#### 3.4.3 Test-Kategorien + Anzahl

| Kategorie | Was wird getestet | Anzahl Tests |
|-----------|-------------------|--------------|
| **Library-Unit** | `log_*`, `pid_running`, `kill_pid`, `wait_for_url`, `wait_for_port`, `check_*_version`, `compose_url`, `load_repo_config`, `discover_siblings` | ~30 |
| **Library-Integration** | Funktionen interagieren korrekt: `pid_running + kill_pid`, `wait_for_url + retry`, `load_repo_config + discover_siblings` | ~10 |
| **Setup** | `setup.sh` klont Siblings, fetched libdanwa, prüft Toolchain, gibt klare Fehler bei fehlender Toolchain | ~8 |
| **Manage-Lifecycle** | `start`/`stop`/`restart`/`status`/`logs`/`clean` für jede Komponente | ~25 |
| **Orchestrator** | Sibling-Erkennung, restart-on-crash, JSON-status-Ausgabe, Watcher-Loop | ~12 |
| **Remote-Control** | `POST /api/v1/system/restart-backend` killt nach 200ms, Watcher respawnt, Status zeigt neuen PID | ~8 |
| **Library-Drift** | Inkompatible LIBDANWA_VERSION → klare Fehlermeldung | ~3 |
| **Smoke-E2E** | Frisches Clone → setup.sh → manage.sh start → alle 3 Apps healthy → stop | ~5 |

**Gesamt: ~100 bats-Tests** pro Repo (passend zur bestehenden Backend-Pytest-Suite von ~150 Tests).

#### 3.4.4 Test-Fixtures & Mocks

**Constraint:** Tests dürfen **keine echten Prozesse starten oder echte Ports belegen** (außer E2E-Tests mit Temp-Ports > 50000). Deshalb:

```bash
# tests/scripts/helpers/test-env.bash
setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-test-XXXXXX)"
    export PID_DIR="$TEST_TMP/pids"
    export LOG_DIR="$TEST_TMP/logs"
    export DANWA_LIB="$TEST_TMP/.lib"
    mkdir -p "$PID_DIR" "$LOG_DIR" "$DANWA_LIB"
}

teardown() {
    rm -rf "$TEST_TMP"
    pkill -f "mock-uvicorn" 2>/dev/null || true
    pkill -f "mock-npm-dev" 2>/dev/null || true
}

# tests/scripts/helpers/mocks.bash
mock_uvicorn() {
    # Erzeugt ein Script, das nur "läuft" (sleep) — für pid_running-Tests
    cat > "$TEST_TMP/mock-uvicorn" <<'EOF'
#!/usr/bin/env bash
sleep 30
EOF
    chmod +x "$TEST_TMP/mock-uvicorn"
}

start_mock_http_server() {
    # Python-HTTP-Server auf zufälligem Port für wait_for_url-Tests
    local port="$1"
    python3 -c "
import http.server, socketserver, sys, time
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *args): pass
with socketserver.TCPServer(('127.0.0.1', $port), Handler) as s:
    s.serve_forever()
" &
    MOCK_PID=$!
    sleep 0.3
}
```

#### 3.4.5 CI-Integration

**In jedem Repo** `.github/workflows/test-scripts.yml`:

```yaml
name: Test setup/manage scripts
on: [push, pull_request]
jobs:
  bats:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install bats
        run: git clone --depth 1 https://github.com/bats-core/bats-core.git /tmp/bats && /tmp/bats/install.sh /opt/bats
      - name: Run bats tests
        run: /opt/bats/bin/bats --jobs 4 tests/scripts/
      - name: Upload TAP results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: bats-results
          path: tests/scripts/results.tap
```

**Coverage-Messung** (Bonus, nicht blocking):
```bash
# kcov misst Bash-Coverage, sammelt HTML-Report
kcov --include-pattern='libdanwa.sh|manage.sh' coverage/ /opt/bats/bin/bats tests/scripts/
```

#### 3.4.6 Test-Coverage-Ziel

| Skript | Coverage-Ziel |
|--------|---------------|
| `libdanwa.sh` | ≥ 100 % (jede exportierte Funktion hat ≥ 1 Test) |
| `manage.sh` (jedes Repo) | ≥ 80 % (kritische Pfade: start/stop/status, weniger wichtig: doc, adr) |
| `setup.sh` | ≥ 90 % (alle Error-Pfade müssen getestet sein) |
| `system_control.py` (neu, in danwa-core) | ≥ 95 % (Backend-Restart ist sicherheitskritisch) |

### 3.5 Verifikationskriterien

| Kriterium | Test |
|-----------|------|
| `libdanwa.sh v1.0` ist semantisch versioniert + dokumentiert | Header enthält `LIBDANWA_VERSION="v1.0.0"` |
| Library-Coverage ≥ 100 % | `kcov --include-pattern='libdanwa.sh' coverage/ bats tests/scripts/libdanwa.bats` |
| Alle aktuellen `danwa/manage.sh`-Befehle weiterhin verfügbar | `diff <(bash danwa/manage.sh help) <(bash danwa-orig/manage.sh help)` zeigt 0 Unterschiede |
| Frisches Setup funktioniert: `git clone danwa-core && bash setup.sh && bash manage.sh start` | manuelle Verifikation: alle 3 Apps hochfahren, URLs erreichbar |
| Sibling-Erkennung im Orchestrator | `manage.sh start` in `danwa-core` ohne Sibling → nur Backend läuft; mit Sibling → Backend + Frontend |
| Standalone-Mode für `danwa` und `danwa-studio` | `manage.sh start` in `danwa` ohne `danwa-core` → Fehlermeldung mit klarem Hinweis auf fehlendes Backend |
| Library-Drift-Schutz | Setup einer alten `manage.sh` mit brandneuer Library → klare Fehlermeldung, kein Silent-Failure |
| Remote-Control-Hooks (HTTP-API) | `curl -X POST /api/v1/system/restart-backend` → 202, Backend restartet in 5s, neuer PID in Status |
| `danwa-studio` SystemManagementView zeigt Backend-Restart-Button | manueller UI-Test oder Vitest-Komponenten-Test |
| `manage.sh status --json` Output valide JSON | `jq -e .manage-status-output.json` exit 0 |
| Bestehende 144 Backend-Tests + 220 Vitest + 111 Playwright grün | `pytest`, `npm run build`, `npx playwright test` exit 0 |
| Neue ~100 bats-Tests grün | `bats tests/scripts/` exit 0 |
| `system_control.py` Endpoint mit Auth | Test ruft ohne Auth → 403, mit admin-Auth → 202 |

---

## 4. Commit-Reihenfolge

```
# 1) Library extrahieren
danwa-modules: feat(scripts): extract libdanwa.sh v1.0 from danwa/manage.sh

# 2) Backend + Orchestrator aufsetzen
danwa-core:    feat(setup,manage): add setup.sh + manage.sh orchestrator (lib v1.0)
danwa-core:    docs(install): add INSTALL.md quickstart

# 3) Studios aufsetzen
danwa-studio:  feat(setup,manage): add setup.sh + manage.sh (lib v1.0)
danwa-studio:  docs(install): add INSTALL.md quickstart

# 4) danwa refaktorisieren (kein Funktionsverlust)
danwa:         refactor(manage): split into libdanwa.sh + repo manage.sh
danwa:         docs(install): add INSTALL.md quickstart

# 5) PRs + Review + Merge
```

---

## 5. Erfolgskriterien

| Kriterium | Messbar |
|-----------|---------|
| Alle 3 Repos haben `setup.sh` + `manage.sh` | `ls setup.sh manage.sh` exit 0 in jedem Repo |
| `libdanwa.sh v1.0` in `danwa-modules` vorhanden | `head -1 .lib/libdanwa.sh` zeigt LIBDANWA_VERSION |
| `danwa-core/manage.sh start` orchestriert alle 3 Apps | Backend + Frontend + Studio hochfahren, `/health`, `/`, `/studio` jeweils 200 |
| `danwa/manage.sh` hat gleiche Feature-Menge wie heute | Vergleich `bash manage.sh help` vor/nach — keine gelöschten Befehle |
| Frischer Clone + Setup funktioniert in < 5 Minuten | `time bash setup.sh` < 300s |
| Library-Version in jedem Repo dokumentiert | `INSTALL.md` zeigt: "libdanwa.sh v1.0 von danwa-modules" |

---

## 6. Nicht-Ziele

- **macOS-Support** — aktuell Linux-only, bleibt so
- **Windows-Support** — WSL-Hinweis in INSTALL.md, kein nativer Windows-Support
- **Docker-Compose als primärer Setup-Pfad** — `docker-compose.yml` bleibt für Production-Deployment, nicht für Development-Setup
- **Automatische Library-Updates** via Cron oder Watchdog — manuelle `bash manage.sh --update-lib`
- **Multi-User-Server-Setup** (systemd-Units, etc.) — eigenes Thema
- **CI/CD-Integration** der neuen Scripts — eigenes Thema

---

## 7. Zeitplan (Schätzung, mit TDD)

```
Schritt 1: Library-Extraktion (RED+GREEN+Refactor):  6-8 Stunden   (inkl. ~30 Tests)
Schritt 2: danwa-core/setup.sh (TDD):                 2-3 Stunden   (inkl. ~8 Tests)
Schritt 3: danwa-core/manage.sh (TDD):               5-7 Stunden   (inkl. ~25 Tests + Watcher-Loop)
Schritt 4: system_control.py (TDD):                   3-4 Stunden   (inkl. ~8 pytest-Tests)
Schritt 5: Remote-Hooks-Integration (TDD):           2-3 Stunden   (inkl. ~12 Tests)
Schritt 6: danwa-studio setup+manage (TDD):          2-3 Stunden   (inkl. ~15 Tests)
Schritt 7: Studio SystemManagementView erweitern:    2-3 Stunden   (inkl. ~6 Vitest-Tests)
Schritt 8: danwa Refactor (TDD, Sorgfalt!):          6-8 Stunden   (alle Befehle aus §1.3 erhalten, ~20 neue Tests)
Schritt 9: INSTALL.md × 4 Repos:                     2-3 Stunden
Schritt 10: E2E-Test auf frischem Clone:             2-3 Stunden
Schritt 11: CI-Workflows × 4 Repos:                  1-2 Stunden   (meist Copy-Paste)

Gesamt: ~34-47 Stunden (4-6 Arbeitstage)
```

**Aufschlüsselung nach Disziplin:**
- **Test-Schreiben (alle Schritte):** ~12-15 Stunden (~40 %)
- **Implementation (alle Schritte):** ~14-19 Stunden (~40 %)
- **Refactoring + Integration + Doku:** ~8-13 Stunden (~20 %)

**TDD-Disziplin:** Bei jedem Schritt **erst Tests, dann Code** — kein "später Tests schreiben". Tests sind Teil der Definition-of-Done.

---

## 8. Vorbedingungen

1. ✅ Architektur-Migration aus [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md) abgeschlossen
2. ✅ Branch `chore/remove-legacy-sessions-router-2026-06` lokal gemerged (nicht gepusht)
3. ✅ Working-Tree in `danwa`, `danwa-core`, `danwa-studio` clean
4. ✅ `danwa-modules`-Repo-Struktur ist geeignet (existierende `scripts/` oder neue `scripts/`-Dir anlegen)

---

## 9. Offene Fragen (finalisiert)

| Frage | Entscheidung |
|-------|--------------|
| **Library-Location:** `danwa-modules` oder `danwa-core`? | `danwa-modules/scripts/libdanwa.sh` — `danwa-modules` ist als **gemeinsamer Modul-Storage** konzipiert (siehe `plans/2026-06-15_danwa-studio.md` §2.1) |
| **Sync-Mechanismus:** Submodule, npm, oder git-archive-Fetch? | `git archive` Fetch per `setup.sh` — keine Submodule-Komplexität |
| **Library-Versionierung:** SemVer? | Ja, SemVer (v1.0.0) + Header-Variable `LIBDANWA_VERSION` |
| **Standalone vs Orchestrator priorisieren?** | Orchestrator zuerst (danwa-core), dann Standalone (danwa, danwa-studio) |
| **Was passiert mit altem `danwa/manage.sh`?** | Wird **refaktoriert** (nicht gelöscht) — alle Befehle bleiben, nur Code-Aufteilung ändert sich |
| **`danwa-modules` Fallback wenn Clone fehlt?** | Embedded Fallback im Repo (Warnung, nicht Silent-Failure) |
| **Library-Drift-Erkennung?** | `LIBDANWA_VERSION`-Check in jedem `manage.sh` |