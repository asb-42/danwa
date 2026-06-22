#!/usr/bin/env bash
# repo-templates/danwa/manage.sh
#
# CANONICAL MANAGE TEMPLATE for danwa (user-app).
#
# This file is the single source of truth for the danwa manage
# procedure, including:
#   - Local backend lifecycle (uvicorn via uv)
#   - Local frontend lifecycle (Vite user-app)
#   - Danwa Studio (admin/dev) lifecycle (sibling-dir lookup)
#   - Logs / status (human + --json) / clean / dashboard
#   - Doc commands: api, pdoc, architecture, update, all
#   - ADR commands: new, check
#   - Mirror strategy via repo-templates/
#
# Usage:
#     bash manage.sh                          # interactive dashboard
#     bash manage.sh help
#     bash manage.sh start [be|fe|studio|all]
#     bash manage.sh stop  [be|fe|studio|all]
#     bash manage.sh restart
#     bash manage.sh status [--json]
#     bash manage.sh logs [be|fe|st|all]
#     bash manage.sh clean
#     bash manage.sh doc
#     bash manage.sh doc-api | doc-pdoc | doc-architecture | doc-update | doc-all
#     bash manage.sh adr-new "Title"
#     bash manage.sh adr-check
#
# Env overrides:
#     DANWA_PROJECT_DIR=/path/to/project
#     DANWA_USE_MOCK=1                        # use mock backends (tests/CI)
#     DANWA_LIBDANWA_PATH=/path/to/lib
#     BACKEND_PORT=7860  FRONTEND_PORT=5173  STUDIO_PORT=5174
#     STUDIO_DIR=/path/to/danwa-studio

set -uo pipefail

# ───────────────────────────────────────────────────────────────────────
# Path resolution
# ───────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${DANWA_PROJECT_DIR:-$SCRIPT_DIR}"

LIB_DIR="$PROJECT_DIR/.lib"
LOG_DIR="${DANWA_LOG_DIR:-$PROJECT_DIR/logs}"
PID_DIR="${DANWA_PID_DIR:-$PROJECT_DIR/pids}"
CONFIG_FILE="$PROJECT_DIR/.danwa-config"
DOCS_DIR="$PROJECT_DIR/docs"
ADR_DIR="$DOCS_DIR/adr"
FE_DIR="${FE_DIR:-$PROJECT_DIR/frontend}"
STUDIO_DIR="${STUDIO_DIR:-$PROJECT_DIR/../danwa-studio}"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FE_PID_FILE="$PID_DIR/frontend.pid"
STUDIO_PID_FILE="$PID_DIR/studio.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FE_LOG="$LOG_DIR/frontend.log"
STUDIO_LOG="$LOG_DIR/studio.log"

BACKEND_PORT="${BACKEND_PORT:-7860}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STUDIO_PORT="${STUDIO_PORT:-5174}"

DANWA_USE_MOCK="${DANWA_USE_MOCK:-0}"
DANWA_VERSION="${DANWA_VERSION:-1.0.0}"

# Mock scripts (test-only — written into LOG_DIR so tests can stub uvicorn/npm)
MOCK_BACKEND_SCRIPT="$LOG_DIR/.mock-backend.sh"
MOCK_FRONTEND_SCRIPT="$LOG_DIR/.mock-frontend.sh"
MOCK_STUDIO_SCRIPT="$LOG_DIR/.mock-studio.sh"

# ───────────────────────────────────────────────────────────────────────
# Source libdanwa.sh
# ───────────────────────────────────────────────────────────────────────
LIBDANWA_RESOLVED=""
for candidate in \
    "${DANWA_LIBDANWA_PATH:-}" \
    "$LIB_DIR/libdanwa.sh" \
    "$PROJECT_DIR/scripts/libdanwa.sh"; do
    if [[ -n "$candidate" ]] && [[ -f "$candidate" ]]; then
        LIBDANWA_RESOLVED="$candidate"
        break
    fi
done
if [[ -z "$LIBDANWA_RESOLVED" ]]; then
    echo "ERROR: libdanwa.sh not found. Run setup.sh first." >&2
    exit 1
fi
# shellcheck disable=SC1090
source "$LIBDANWA_RESOLVED"

# Source .danwa-config if present (provides REPO_NAME, BACKEND_PORT, etc.)
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

ensure_dirs() {
    ensure_dir "$PID_DIR"
    ensure_dir "$LOG_DIR"
    ensure_dir "$DOCS_DIR/adr"
}

write_mock_script() {
    local path="$1"
    cat > "$path" <<'EOF'
#!/usr/bin/env bash
sleep 60
EOF
    chmod +x "$path"
}

# Wrapper aliases — preserve legacy naming convention
backend_running()  { pid_running "$BACKEND_PID_FILE"; }
frontend_running() { pid_running "$FE_PID_FILE"; }
studio_running()   { pid_running "$STUDIO_PID_FILE"; }

# ───────────────────────────────────────────────────────────────────────
# Backend lifecycle
# ───────────────────────────────────────────────────────────────────────
start_backend() {
    ensure_dirs
    if backend_running > /dev/null 2>&1; then
        log_warn "Backend läuft bereits (PID: $(backend_running))"
        return 0
    fi
    log_step "Backend starten …"
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_BACKEND_SCRIPT"
        nohup "$MOCK_BACKEND_SCRIPT" > "$BACKEND_LOG" 2>&1 &
    else
        cd "$PROJECT_DIR"
        export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
        export UV_PYTHONPATH="${PROJECT_DIR}:${UV_PYTHONPATH:-}"
        export PATH="$HOME/.local/bin:$PATH"
        nohup uv run uvicorn backend.main:app \
            --host 0.0.0.0 \
            --port "$BACKEND_PORT" \
            --log-level info \
            > "$BACKEND_LOG" 2>&1 &
    fi
    local pid=$!
    echo "$pid" > "$BACKEND_PID_FILE"
    if [[ "$DANWA_USE_MOCK" != "1" ]] && wait_for_url "http://localhost:$BACKEND_PORT/docs" 120; then
        log_ok "Backend gestartet (PID: $pid) → http://localhost:$BACKEND_PORT"
    elif [[ "$DANWA_USE_MOCK" == "1" ]]; then
        log_ok "Backend started (MOCK, PID: $pid, log: $BACKEND_LOG)"
    else
        log_warn "Backend-Start dauert länger als erwartet — prüfe Logs mit: ./manage.sh logs be"
    fi
}

stop_backend() {
    log_step "Backend stoppen …"
    local pid
    pid="$(backend_running 2>/dev/null)" || true
    if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null && sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$BACKEND_PID_FILE"
        log_ok "Backend (PID: $pid) gestoppt"
    else
        log_warn "Backend läuft nicht"
    fi
    pkill -f "uvicorn backend.main" 2>/dev/null || true
}

# ───────────────────────────────────────────────────────────────────────
# Frontend lifecycle
# ───────────────────────────────────────────────────────────────────────
start_frontend() {
    ensure_dirs
    if frontend_running > /dev/null 2>&1; then
        log_warn "Frontend läuft bereits (PID: $(frontend_running))"
        return 0
    fi
    if [[ ! -d "$FE_DIR" ]]; then
        log_error "Frontend-Verzeichnis nicht gefunden: $FE_DIR"
        return 1
    fi
    if [[ ! -d "$FE_DIR/node_modules" ]] && [[ "$DANWA_USE_MOCK" != "1" ]]; then
        log_warn "node_modules fehlt in $FE_DIR — führe 'npm install' aus …"
        (cd "$FE_DIR" && npm install) >> "$FE_LOG" 2>&1 || {
            log_error "npm install fehlgeschlagen — prüfe $FE_LOG"
            return 1
        }
    fi
    log_step "Frontend starten …"
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_FRONTEND_SCRIPT"
        nohup "$MOCK_FRONTEND_SCRIPT" > "$FE_LOG" 2>&1 &
    else
        cd "$FE_DIR"
        nohup npm run dev -- --port "$FRONTEND_PORT" \
            > "$FE_LOG" 2>&1 &
    fi
    local pid=$!
    echo "$pid" > "$FE_PID_FILE"
    if [[ "$DANWA_USE_MOCK" != "1" ]] && wait_for_url "http://localhost:$FRONTEND_PORT" 60; then
        log_ok "Frontend gestartet (PID: $pid) → http://localhost:$FRONTEND_PORT"
    elif [[ "$DANWA_USE_MOCK" == "1" ]]; then
        log_ok "Frontend started (MOCK, PID: $pid, log: $FE_LOG)"
    else
        log_warn "Frontend-Start dauert länger als erwartet — prüfe Logs mit: ./manage.sh logs fe"
    fi
}

stop_frontend() {
    log_step "Frontend stoppen …"
    local pid
    pid="$(frontend_running 2>/dev/null)" || true
    if [[ -n "$pid" ]]; then
        kill -- -"$pid" 2>/dev/null
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        rm -f "$FE_PID_FILE"
        log_ok "Frontend (PID: $pid) gestoppt"
    else
        log_warn "Frontend läuft nicht"
    fi
    pkill -f "vite" 2>/dev/null || true
}

# ───────────────────────────────────────────────────────────────────────
# Danwa Studio (sibling-dir lookup, like the legacy behaviour)
# ───────────────────────────────────────────────────────────────────────
start_studio() {
    ensure_dirs
    if studio_running > /dev/null 2>&1; then
        log_warn "Danwa Studio läuft bereits (PID: $(studio_running))"
        return 0
    fi

    if [[ ! -d "$STUDIO_DIR" ]]; then
        log_error "Studio-Verzeichnis nicht gefunden: $STUDIO_DIR"
        log_info "Setze STUDIO_DIR oder klone danwa-studio neben danwa."
        return 1
    fi

    if [[ ! -d "$STUDIO_DIR/node_modules" ]] && [[ "$DANWA_USE_MOCK" != "1" ]]; then
        log_warn "node_modules fehlt in $STUDIO_DIR — führe 'npm install' aus …"
        (cd "$STUDIO_DIR" && npm install) >> "$STUDIO_LOG" 2>&1 || {
            log_error "npm install fehlgeschlagen — prüfe $STUDIO_LOG"
            return 1
        }
    fi

    log_step "Danwa Studio starten …"
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_STUDIO_SCRIPT"
        nohup "$MOCK_STUDIO_SCRIPT" > "$STUDIO_LOG" 2>&1 &
    else
        cd "$STUDIO_DIR"
        nohup npm run dev -- --port "$STUDIO_PORT" \
            > "$STUDIO_LOG" 2>&1 &
    fi
    local pid=$!
    echo "$pid" > "$STUDIO_PID_FILE"
    if [[ "$DANWA_USE_MOCK" != "1" ]] && wait_for_url "http://localhost:$STUDIO_PORT" 90; then
        log_ok "Danwa Studio gestartet (PID: $pid) → http://localhost:$STUDIO_PORT"
    elif [[ "$DANWA_USE_MOCK" == "1" ]]; then
        log_ok "Studio started (MOCK, PID: $pid, log: $STUDIO_LOG)"
    else
        log_warn "Studio-Start dauert länger als erwartet — prüfe Logs mit: ./manage.sh logs studio"
    fi
}

stop_studio() {
    log_step "Danwa Studio stoppen …"
    local pid
    pid="$(studio_running 2>/dev/null)" || true
    if [[ -n "$pid" ]]; then
        kill -- -"$pid" 2>/dev/null
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        rm -f "$STUDIO_PID_FILE"
        log_ok "Danwa Studio (PID: $pid) gestoppt"
    else
        log_warn "Danwa Studio läuft nicht"
    fi
    pkill -f "vite" 2>/dev/null || true
}

# ───────────────────────────────────────────────────────────────────────
# Logs
# ───────────────────────────────────────────────────────────────────────
show_logs() {
    local target="${1:-all}"
    case "$target" in
        be|backend)
            log_header "Backend-Logs (tail -f) — Ctrl+C zum Beenden"
            tail -f "$BACKEND_LOG"
            ;;
        fe|frontend)
            log_header "Frontend-Logs (tail -f) — Ctrl+C zum Beenden"
            tail -f "$FE_LOG"
            ;;
        st|studio)
            log_header "Danwa-Studio-Logs (tail -f) — Ctrl+C zum Beenden"
            tail -f "$STUDIO_LOG"
            ;;
        all|*)
            log_header "Live-Logs: Backend + Frontend + Studio (Ctrl+C zum Beenden)"
            tail -f "$BACKEND_LOG" "$FE_LOG" "$STUDIO_LOG" || true
            ;;
    esac
}

# ───────────────────────────────────────────────────────────────────────
# Status (human + --json for studio SystemManagementView)
# ───────────────────────────────────────────────────────────────────────
status_json_field() {
    local pid_file="$1"
    local pid
    pid="$(pid_running "$pid_file" 2>/dev/null)" || pid=""
    if [[ -n "$pid" ]]; then
        printf '"pid": %s, "alive": true' "$pid"
    else
        printf '"pid": null, "alive": false'
    fi
}

manage_status_json() {
    cat <<EOF
{
  "backend":   { $(status_json_field "$BACKEND_PID_FILE"),  "port": ${BACKEND_PORT} },
  "frontend":  { $(status_json_field "$FE_PID_FILE"),       "port": ${FRONTEND_PORT} },
  "studio":    { $(status_json_field "$STUDIO_PID_FILE"),   "port": ${STUDIO_PORT} },
  "project_dir": "${PROJECT_DIR}",
  "log_dir":   "${LOG_DIR}",
  "version":   "${DANWA_VERSION}"
}
EOF
}

show_status() {
    local mode="${1:-human}"
    if [[ "$mode" == "--json" ]]; then
        manage_status_json
        return 0
    fi

    log_header "Danwa — Systemstatus"

    echo ""
    echo -e "  ${BOLD}Backend:${RESET}"
    if backend_running > /dev/null 2>&1; then
        local bp
        bp="$(backend_running)"
        echo -e "    Status:  ${GREEN}aktiv${RESET} (PID: $bp)"
        echo -e "    Port:    $BACKEND_PORT"
        echo -e "    Log:     $BACKEND_LOG"
    else
        echo -e "    Status:  ${RED}gestoppt${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Frontend:${RESET}"
    if frontend_running > /dev/null 2>&1; then
        local fp
        fp="$(frontend_running)"
        echo -e "    Status:  ${GREEN}aktiv${RESET} (PID: $fp)"
        echo -e "    Port:    $FRONTEND_PORT"
        echo -e "    Log:     $FE_LOG"
    else
        echo -e "    Status:  ${RED}gestoppt${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Danwa Studio (admin / dev):${RESET}"
    if studio_running > /dev/null 2>&1; then
        local sp
        sp="$(studio_running)"
        echo -e "    Status:  ${GREEN}aktiv${RESET} (PID: $sp)"
        echo -e "    Port:    $STUDIO_PORT"
        echo -e "    Log:     $STUDIO_LOG"
        echo -e "    Verz.:   $STUDIO_DIR"
    else
        echo -e "    Status:  ${RED}gestoppt${RESET}  (Port $STUDIO_PORT, Verz. $STUDIO_DIR)"
    fi

    echo ""
    echo -e "  ${BOLD}DMS OCR:${RESET}"
    if curl -s "http://localhost:$BACKEND_PORT/api/v1/dms/ocr-status" 2>/dev/null | grep -q '"available":true'; then
        echo -e "    Status:  ${GREEN}verfügbar${RESET}"
    else
        echo -e "    Status:  ${YELLOW}nicht verfügbar (OCR deaktiviert oder nicht installiert)${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Projektordner:${RESET} $PROJECT_DIR"
    echo -e "  ${BOLD}Log-Verzeichnis:${RESET} $LOG_DIR"
    echo ""
}

# ───────────────────────────────────────────────────────────────────────
# Interactive Dashboard (legacy feature, preserved 1:1)
# ───────────────────────────────────────────────────────────────────────
dashboard_menu() {
    log_header "Danwa Dashboard"
    echo ""
    echo -e "  ${CYAN}╔════════════════════════════════════╗${RESET}"
    echo -e "  ${CYAN}║     D A N W A   M A N A G E R     ║${RESET}"
    echo -e "  ${CYAN}╚════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "  ${BOLD}1${RESET}) Backend   ${GREEN}starten${RESET}"
    echo -e "  ${BOLD}2${RESET}) Backend   ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}3${RESET}) Frontend  ${GREEN}starten${RESET}"
    echo -e "  ${BOLD}4${RESET}) Frontend  ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}5${RESET}) Studio    ${GREEN}starten${RESET}  (admin / dev)"
    echo -e "  ${BOLD}6${RESET}) Studio    ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}7${RESET}) Beides    ${GREEN}starten${RESET}   (Backend + Frontend)"
    echo -e "  ${BOLD}8${RESET}) Beides    ${YELLOW}stoppen${RESET}"
    echo -e "  ${BOLD}9${RESET}) Status anzeigen"
    echo -e "  ${BOLD}b${RESET}) Backend-Logs live verfolgen"
    echo -e "  ${BOLD}f${RESET}) Frontend-Logs live verfolgen"
    echo -e "  ${BOLD}s${RESET}) Studio-Logs live verfolgen"
    echo -e "  ${BOLD}0${RESET}) Neustart (beides)"
    echo -e "  ${BOLD}q${RESET}) Beenden"
    echo ""
    echo -n "  Auswahl: "
}

dashboard_loop() {
    while true; do
        dashboard_menu
        read -r choice
        case "$choice" in
            1) start_backend ;;
            2) stop_backend ;;
            3) start_frontend ;;
            4) stop_frontend ;;
            5) start_studio ;;
            6) stop_studio ;;
            7) start_backend && start_frontend ;;
            8) stop_backend && stop_frontend ;;
            9) show_status ;;
            b|B) show_logs be ;;
            f|F) show_logs fe ;;
            s|S) show_logs st ;;
            0)
                stop_backend && stop_frontend
                sleep 1
                start_backend && start_frontend
                ;;
            q|Q|quit|exit) log_info "Bye!"; exit 0 ;;
            *) log_warn "Ungültige Auswahl: $choice" ;;
        esac
        echo ""
        echo -n "  Enter drücken …"
        read -r
        clear
    done
}

# ───────────────────────────────────────────────────────────────────────
# Documentation
# ───────────────────────────────────────────────────────────────────────
doc_api() {
    log_step "API-Referenz generieren (OpenAPI → Markdown) …"
    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
    if [[ -f "$PROJECT_DIR/scripts/export_openapi.py" ]]; then
        uv run python scripts/export_openapi.py --both 2>&1 && \
            log_ok "API-Referenz generiert: $DOCS_DIR/api-reference.md" || {
                log_error "API-Referenz fehlgeschlagen"
                return 1
            }
    else
        log_warn "scripts/export_openapi.py nicht gefunden — überspringe doc-api"
    fi
}

doc_pdoc() {
    log_step "Python API-Doku generieren (pdoc) …"
    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

    if ! uv run python -c "import pdoc" 2>/dev/null; then
        log_warn "pdoc nicht installiert — installiere …"
        uv add --dev pdoc 2>&1
    fi

    local output_dir="$DOCS_DIR/api"
    mkdir -p "$output_dir"
    uv run pdoc backend/ -o "$output_dir" --docformat google 2>&1 && \
        log_ok "pdoc generiert: $output_dir/index.html" || {
            log_error "pdoc fehlgeschlagen"
            return 1
        }
}

doc_architecture() {
    log_step "Architektur-Doku generieren (GitNexus Wiki) …"

    if ! check_node_version 22; then
        return 1
    fi

    cd "$PROJECT_DIR"

    local output_dir="$DOCS_DIR/architecture"
    mkdir -p "$output_dir"

    if command -v npx &>/dev/null; then
        if ! npx gitnexus status 2>&1 | grep -q "indexed"; then
            log_warn "Index nicht vorhanden — erstelle …"
            npx gitnexus analyze 2>&1
        fi

        npx gitnexus wiki -f 2>&1 && {
            if [[ -d ".gitnexus/wiki" ]]; then
                cp -r .gitnexus/wiki/* "$output_dir/" 2>/dev/null || true
                log_ok "GitNexus Wiki generiert: $output_dir/"
            else
                log_warn "Wiki-Verzeichnis nicht gefunden"
                return 1
            fi
        } || {
            log_error "GitNexus Wiki fehlgeschlagen — LLM API Key erforderlich"
            log_info "Setup: npx gitnexus wiki --provider <provider> --api-key <key>"
            return 1
        }
    else
        log_error "npx nicht verfügbar — bitte Node.js installieren"
        return 1
    fi
}

doc_update() {
    local mode="${1:-all}"
    local dry_run="${2:-false}"

    log_step "Dokumentation aktualisieren (LLM-basiert) …"

    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

    if [[ ! -f "$PROJECT_DIR/scripts/doc_update.py" ]]; then
        log_warn "scripts/doc_update.py nicht gefunden — überspringe doc-update"
        return 0
    fi

    local args=""
    case "$mode" in
        tech) args="--tech" ;;
        user) args="--user" ;;
        all|"") args="--all" ;;
    esac

    if [[ "$dry_run" == "true" ]]; then
        args="$args --dry-run"
    fi

    uv run python scripts/doc_update.py $args 2>&1 && \
        log_ok "Dokumentation aktualisiert" || {
            log_error "Dokumentation-Update fehlgeschlagen"
            return 1
        }
}

doc_all() {
    log_header "Alle Dokumentation generieren"
    doc_api
    doc_pdoc
    doc_architecture
    log_ok "Alle Dokumentation generiert"
}

doc_help() {
    log_header "Dokumentation Commands"
    echo ""
    echo "  ./manage.sh doc              Übersicht aller Doc-Commands"
    echo "  ./manage.sh doc-api          OpenAPI → docs/api-reference.md"
    echo "  ./manage.sh doc-pdoc         Python Docstrings → docs/api/"
    echo "  ./manage.sh doc-architecture GitNexus Wiki → docs/architecture/"
    echo "  ./manage.sh doc-update       LLM-basierte Doc-Updates"
    echo "  ./manage.sh doc-update tech  Nur technische Doku"
    echo "  ./manage.sh doc-update user  Nur User Manual"
    echo "  ./manage.sh doc-update --dry-run Vorschau ohne Änderungen"
    echo "  ./manage.sh doc-all          Alle Doc-Generierungen"
    echo "  ./manage.sh adr-new \"Titel\"  Neue ADR erstellen"
    echo "  ./manage.sh adr-check        Prüfen ob ADRs fehlen"
    echo ""
}

# ───────────────────────────────────────────────────────────────────────
# ADR (Architecture Decision Records)
# ───────────────────────────────────────────────────────────────────────
adr_new() {
    local title="${1:-}"
    if [[ -z "$title" ]]; then
        log_error "Titel erforderlich: ./manage.sh adr-new \"Titel\""
        return 1
    fi

    mkdir -p "$ADR_DIR"

    local max_num=0
    for f in "$ADR_DIR"/[0-9]*.md; do
        local bname
        bname="$(basename "$f")"
        if [[ "$bname" =~ ^[0-9]{3,4}-[a-zA-Z] ]]; then
            local num="${bname%%-*}"
            num=$((10#$num))
            if [[ "$num" -gt "$max_num" ]]; then
                max_num="$num"
            fi
        fi
    done
    local next_num=$(( max_num + 1 ))
    local padded
    padded="$(printf "%03d" "$next_num")"
    local filename="$ADR_DIR/${padded}-${title// /-}.md"

    if [[ -f "$filename" ]]; then
        log_error "ADR existiert bereits: $filename"
        return 1
    fi

    cat > "$filename" <<EOF
# ADR-${padded}: ${title}

**Status:** Proposed
**Date:** $(date -I)
**Context:** Was war das Problem?

<!-- Beschreibe den Hintergrund und das Problem, das diese Entscheidung erfordert hat -->

**Decision:** Was wurde entschieden?

<!-- Beschreibe die getroffene Entscheidung -->

**Consequences:** Was sind die Folgen?

<!-- Beschreibe die positiven und negativen Konsequenzen -->

**Affected Files:**

<!-- Liste der betroffenen Dateien -->

**Alternatives Considered:**

<!-- Welche Alternativen wurden geprüft und warum verworfen? -->
EOF

    log_ok "ADR erstellt: $filename"
}

adr_check() {
    log_step "Prüfe fehlende ADRs …"

    local core_dirs=(
        "backend/api/routers"
        "backend/services"
        "backend/blueprints"
        "backend/modules"
        "backend/models"
        "backend/config"
    )

    local last_adr_check="$DOCS_DIR/.last-adr-check"
    local since="HEAD~20"
    if [[ -f "$last_adr_check" ]]; then
        since="$(cat "$last_adr_check")"
    fi

    local changes_found=false
    for dir in "${core_dirs[@]}"; do
        local changed
        changed="$(git diff "$since" --name-only -- "${dir}/*.py" 2>/dev/null)" || true
        if [[ -n "$changed" ]]; then
            changes_found=true
            log_warn "Architektur-Änderungen in: $dir"
            echo "$changed" | while read -r f; do
                echo "  - $f"
            done
        fi
    done

    if [[ "$changes_found" == "false" ]]; then
        log_ok "Keine Architektur-Änderungen seit letztem Check"
    else
        log_warn "Prüfe ob neue ADRs für diese Änderungen erforderlich sind …"
        log_info "Erstelle bei Bedarf eine neue ADR: ./manage.sh adr-new \"Titel\""
    fi

    date -Iseconds > "$last_adr_check"
}

# ───────────────────────────────────────────────────────────────────────
# Clean
# ───────────────────────────────────────────────────────────────────────
clean_caches() {
    log_step "Caches aufräumen …"
    find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$FE_DIR/node_modules/.cache" -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -type d -name "*.pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    log_ok "Caches gelöscht"
}

# ───────────────────────────────────────────────────────────────────────
# Command dispatch
# ───────────────────────────────────────────────────────────────────────
cmd="${1:-}"
shift || true

case "$cmd" in
    start)
        what="${1:-all}"
        case "$what" in
            be|backend) start_backend ;;
            fe|frontend) start_frontend ;;
            st|studio) start_studio ;;
            all|"") start_backend && start_frontend ;;
        esac
        ;;
    stop)
        what="${1:-all}"
        case "$what" in
            be|backend) stop_backend ;;
            fe|frontend) stop_frontend ;;
            st|studio) stop_studio ;;
            all|"") stop_backend && stop_frontend ;;
        esac
        ;;
    restart|reload)
        stop_backend
        stop_frontend
        sleep 1
        find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
        start_backend
        start_frontend
        # Studio wird bewusst NICHT mit-restartet — Admin-Tool, unabhängiger Lifecycle.
        ;;
    status|st)
        show_status "${1:-human}"
        ;;
    logs)
        show_logs "${1:-all}"
        ;;
    dashboard|dash|d)
        dashboard_loop
        ;;
    clean)
        clean_caches
        ;;
    doc)
        doc_help
        ;;
    doc-api)
        doc_api
        ;;
    doc-pdoc)
        doc_pdoc
        ;;
    doc-architecture)
        doc_architecture
        ;;
    doc-update)
        mode="${1:-all}"
        dry="false"
        if [[ "$mode" == "--dry-run" ]]; then
            dry="true"
            mode="all"
        fi
        doc_update "$mode" "$dry"
        ;;
    doc-all)
        doc_all
        ;;
    adr-new)
        adr_new "${1:-}"
        ;;
    adr-check)
        adr_check
        ;;
    test)
        log_step "Tests ausführen …"
        cd "$PROJECT_DIR"
        export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
        export UV_PYTHONPATH="${PROJECT_DIR}:${UV_PYTHONPATH:-}"
        uv run pytest tests/backend/test_dms_ocr.py tests/backend/test_dms_api.py tests/test_paddleocr_integration.py tests/test_dms_document_processor.py -v 2>&1
        ;;
    help|--help|-h)
        echo "Danwa Manager (refactored — Phase 8, repo-templates/danwa/manage.sh)"
        echo ""
        echo "  ./manage.sh                  interaktives Dashboard"
        echo "  ./manage.sh start            Backend + Frontend starten"
        echo "  ./manage.sh start be         nur Backend starten"
        echo "  ./manage.sh start fe         nur Frontend starten"
        echo "  ./manage.sh start studio     nur Danwa Studio starten (admin / dev)"
        echo "  ./manage.sh stop             alles stoppen (Backend + Frontend)"
        echo "  ./manage.sh stop studio      nur Studio stoppen"
        echo "  ./manage.sh restart          Backend + Frontend neu starten (Studio bleibt)"
        echo "  ./manage.sh status           Status anzeigen (Backend + Frontend + Studio)"
        echo "  ./manage.sh status --json    JSON-Status (für Studio SystemManagementView)"
        echo "  ./manage.sh logs             Live-Logs (alle drei)"
        echo "  ./manage.sh logs be          Backend-Logs"
        echo "  ./manage.sh logs fe          Frontend-Logs"
        echo "  ./manage.sh logs st          Studio-Logs"
        echo "  ./manage.sh clean            Caches aufräumen"
        echo "  ./manage.sh test             Tests ausführen"
        echo "  ./manage.sh doc              Dokumentation Commands"
        echo "  ./manage.sh doc-api          OpenAPI → Markdown"
        echo "  ./manage.sh doc-pdoc         Docstrings → HTML"
        echo "  ./manage.sh doc-architecture GitNexus Wiki"
        echo "  ./manage.sh doc-update       LLM-basierte Updates"
        echo "  ./manage.sh doc-all          Alle Docs generieren"
        echo "  ./manage.sh adr-new          Neue ADR erstellen"
        echo "  ./manage.sh adr-check        ADR-Check"
        ;;
    *)
        log_error "Unbekannter Befehl: '$cmd'. Versuche: ./manage.sh help"
        exit 1
        ;;
esac