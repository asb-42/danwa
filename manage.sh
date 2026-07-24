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
# Backend lifecycle — delegates to danwa-core
#
# The legacy backend in this repo is disabled. The backend now lives in
# danwa-core. These functions delegate to the danwa-core manage.sh so the
# user can start/stop the backend without leaving this directory.
# ───────────────────────────────────────────────────────────────────────
start_backend() {
    local core_script
    core_script="$PROJECT_DIR/../danwa-core/manage.sh"
    if [[ ! -f "$core_script" ]]; then
        log_error "danwa-core manage.sh not found at: $core_script"
        log_error "Ensure danwa-core is cloned as a sibling directory."
        return 1
    fi
    log_step "Starting backend via danwa-core..."
    export DANWA_LIBDANWA_PATH="${DANWA_LIBDANWA_PATH:-$LIBDANWA_RESOLVED}"
    bash "$core_script" start be
}

stop_backend() {
    local core_script
    core_script="$PROJECT_DIR/../danwa-core/manage.sh"
    if [[ ! -f "$core_script" ]]; then
        log_warn "danwa-core manage.sh not found — cannot stop backend"
        return 1
    fi
    log_step "Stopping backend via danwa-core..."
    export DANWA_LIBDANWA_PATH="${DANWA_LIBDANWA_PATH:-$LIBDANWA_RESOLVED}"
    bash "$core_script" stop be
}

# ───────────────────────────────────────────────────────────────────────
# Frontend lifecycle
# ───────────────────────────────────────────────────────────────────────

# ───────────────────────────────────────────────────────────────────────
# Frontend lifecycle
# ───────────────────────────────────────────────────────────────────────
start_frontend() {
    ensure_dirs
    if frontend_running > /dev/null 2>&1; then
        log_warn "Frontend already running (PID: $(frontend_running))"
        return 0
    fi
    if [[ ! -d "$FE_DIR" ]]; then
        log_error "Frontend directory not found: $FE_DIR"
        return 1
    fi
    if [[ ! -d "$FE_DIR/node_modules" ]] && [[ "$DANWA_USE_MOCK" != "1" ]]; then
        log_warn "node_modules missing in $FE_DIR — running 'npm install' …"
        (cd "$FE_DIR" && npm install) >> "$FE_LOG" 2>&1 || {
            log_error "npm install failed — check $FE_LOG"
            return 1
        }
    fi
    log_step "Frontend starting …"
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
        log_ok "Frontend started (PID: $pid) → http://localhost:$FRONTEND_PORT"
    elif [[ "$DANWA_USE_MOCK" == "1" ]]; then
        log_ok "Frontend started (MOCK, PID: $pid, log: $FE_LOG)"
    else
        log_warn "Frontend startup taking longer than expected — check logs with: ./manage.sh logs fe"
    fi
}

stop_frontend() {
    log_step "Stopping frontend …"
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
        log_ok "Frontend (PID: $pid) stopped"
    else
        log_warn "Frontend is not running"
    fi
    pkill -f "vite" 2>/dev/null || true
}

# ───────────────────────────────────────────────────────────────────────
# Danwa Studio (sibling-dir lookup, like the legacy behaviour)
# ───────────────────────────────────────────────────────────────────────
start_studio() {
    ensure_dirs
    if studio_running > /dev/null 2>&1; then
        log_warn "Danwa Studio already running (PID: $(studio_running))"
        return 0
    fi

    if [[ ! -d "$STUDIO_DIR" ]]; then
        log_error "Studio directory not found: $STUDIO_DIR"
        log_info "Setze STUDIO_DIR oder klone danwa-studio neben danwa."
        return 1
    fi

    if [[ ! -d "$STUDIO_DIR/node_modules" ]] && [[ "$DANWA_USE_MOCK" != "1" ]]; then
        log_warn "node_modules missing in $STUDIO_DIR — running 'npm install' …"
        (cd "$STUDIO_DIR" && npm install) >> "$STUDIO_LOG" 2>&1 || {
            log_error "npm install failed — check $STUDIO_LOG"
            return 1
        }
    fi

    log_step "Starting Danwa Studio …"
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
        log_ok "Danwa Studio started (PID: $pid) → http://localhost:$STUDIO_PORT"
    elif [[ "$DANWA_USE_MOCK" == "1" ]]; then
        log_ok "Studio started (MOCK, PID: $pid, log: $STUDIO_LOG)"
    else
        log_warn "Studio startup taking longer than expected — check logs with: ./manage.sh logs studio"
    fi
}

stop_studio() {
    log_step "Stopping Danwa Studio …"
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
        log_ok "Danwa Studio (PID: $pid) stopped"
    else
        log_warn "Danwa Studio is not running"
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
            log_header "Backend logs (tail -f) — Ctrl+C to exit"
            tail -f "$BACKEND_LOG"
            ;;
        fe|frontend)
            log_header "Frontend logs (tail -f) — Ctrl+C to exit"
            tail -f "$FE_LOG"
            ;;
        st|studio)
            log_header "Danwa Studio logs (tail -f) — Ctrl+C to exit"
            tail -f "$STUDIO_LOG"
            ;;
        all|*)
            log_header "Live logs: Backend + Frontend + Studio (Ctrl+C to exit)"
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
    echo -e "  ${BOLD}Backend (via danwa-core):${RESET}"
    # Check if the danwa-core backend is running
    if curl -s "http://localhost:$BACKEND_PORT/health" 2>/dev/null | grep -q "ok\|healthy\|status"; then
        echo -e "    Status:  ${GREEN}running${RESET} (port $BACKEND_PORT)"
    else
        echo -e "    Status:  ${RED}stopped${RESET}  (start with: ./manage.sh start be)"
    fi
    echo -e "    Note: Backend runs in danwa-core"

    echo ""
    echo -e "  ${BOLD}Frontend:${RESET}"
    if frontend_running > /dev/null 2>&1; then
        local fp
        fp="$(frontend_running)"
        echo -e "    Status:  ${GREEN}running${RESET} (PID: $fp)"
        echo -e "    Port:    $FRONTEND_PORT"
        echo -e "    Log:     $FE_LOG"
    else
        echo -e "    Status:  ${RED}stopped${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Danwa Studio (admin / dev):${RESET}"
    if studio_running > /dev/null 2>&1; then
        local sp
        sp="$(studio_running)"
        echo -e "    Status:  ${GREEN}running${RESET} (PID: $sp)"
        echo -e "    Port:    $STUDIO_PORT"
        echo -e "    Log:     $STUDIO_LOG"
        echo -e "    Dir.:   $STUDIO_DIR"
    else
        echo -e "    Status:  ${RED}stopped${RESET}  (Port $STUDIO_PORT, Dir. $STUDIO_DIR)"
    fi

    echo ""
    echo -e "  ${BOLD}DMS OCR:${RESET}"
    if curl -s "http://localhost:$BACKEND_PORT/api/v1/dms/ocr-status" 2>/dev/null | grep -q '"available":true'; then
        echo -e "    Status:  ${GREEN}available${RESET}"
    else
        echo -e "    Status:  ${YELLOW}nicht available (OCR derunningiert oder nicht installiert)${RESET}"
    fi

    echo ""
    echo -e "  ${BOLD}Project directory:${RESET} $PROJECT_DIR"
    echo -e "  ${BOLD}Log directory:${RESET} $LOG_DIR"
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
    echo -e "  ${BOLD}1${RESET}) Backend   ${GREEN}start${RESET}"
    echo -e "  ${BOLD}2${RESET}) Backend   ${YELLOW}stop${RESET}"
    echo -e "  ${BOLD}3${RESET}) Frontend  ${GREEN}start${RESET}"
    echo -e "  ${BOLD}4${RESET}) Frontend  ${YELLOW}stop${RESET}"
    echo -e "  ${BOLD}5${RESET}) Studio    ${GREEN}start${RESET}  (admin / dev)"
    echo -e "  ${BOLD}6${RESET}) Studio    ${YELLOW}stop${RESET}"
    echo -e "  ${BOLD}7${RESET}) Both    ${GREEN}start${RESET}   (Backend + Frontend)"
    echo -e "  ${BOLD}8${RESET}) Both    ${YELLOW}stop${RESET}"
    echo -e "  ${BOLD}9${RESET}) Show status"
    echo -e "  ${BOLD}b${RESET}) Follow backend logs live"
    echo -e "  ${BOLD}f${RESET}) Follow frontend logs live"
    echo -e "  ${BOLD}s${RESET}) Follow studio logs live"
    echo -e "  ${BOLD}0${RESET}) Restart (both)"
    echo -e "  ${BOLD}q${RESET}) Quit"
    echo ""
    echo -n "  Choice: "
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
            *) log_warn "Invalid choice: $choice" ;;
        esac
        echo ""
        echo -n "  Press Enter …"
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
            log_ok "API reference generated: $DOCS_DIR/api-reference.md" || {
                log_error "API reference generation failed"
                return 1
            }
    else
        log_warn "scripts/export_openapi.py not found — skipping doc-api"
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
        log_ok "pdoc generated: $output_dir/index.html" || {
            log_error "pdoc failed"
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
                log_ok "GitNexus Wiki generated: $output_dir/"
            else
                log_warn "Wiki directory not found"
                return 1
            fi
        } || {
            log_error "GitNexus Wiki failed — LLM API key required"
            log_info "Setup: npx gitnexus wiki --provider <provider> --api-key <key>"
            return 1
        }
    else
        log_error "npx nicht available — bitte Node.js installieren"
        return 1
    fi
}

doc_update() {
    local mode="${1:-all}"
    local dry_run="${2:-false}"

    log_step "Updating documentation (LLM-based) ..."

    cd "$PROJECT_DIR"
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"

    if [[ ! -f "$PROJECT_DIR/scripts/doc_update.py" ]]; then
        log_warn "scripts/doc_update.py not found — skipping doc-update"
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
        log_ok "Documentation updated" || {
            log_error "Documentation update failed"
            return 1
        }
}

doc_all() {
    log_header "Generate all documentation"
    doc_api
    doc_pdoc
    doc_architecture
    log_ok "All documentation generated"
}

doc_help() {
    log_header "Documentation commands"
    echo ""
    echo "  ./manage.sh doc              Overview of all doc commands"
    echo "  ./manage.sh doc-api          OpenAPI → docs/api-reference.md"
    echo "  ./manage.sh doc-pdoc         Python Docstrings → docs/api/"
    echo "  ./manage.sh doc-architecture GitNexus Wiki → docs/architecture/"
    echo "  ./manage.sh doc-update       LLM-basierte Doc-Updates"
    echo "  ./manage.sh doc-update tech  Nur technische Doku"
    echo "  ./manage.sh doc-update user  Nur User Manual"
    echo "  ./manage.sh doc-update --dry-run Vorschau ohne Änderungen"
    echo "  ./manage.sh doc-all          Alle Doc-Generierungen"
    echo "  ./manage.sh adr-new \"Title\"  Create new ADR"
    echo "  ./manage.sh adr-check        Check for missing ADRs"
    echo ""
}

# ───────────────────────────────────────────────────────────────────────
# ADR (Architecture Decision Records)
# ───────────────────────────────────────────────────────────────────────
adr_new() {
    local title="${1:-}"
    if [[ -z "$title" ]]; then
        log_error "Title required: ./manage.sh adr-new \"Title\""
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

<!-- Which alternatives were considered and why rejected?? -->
EOF

    log_ok "ADR erstellt: $filename"
}

adr_check() {
    log_step "Checking for missing ADRs …"

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
            log_warn "Architecture changes in: $dir"
            echo "$changed" | while read -r f; do
                echo "  - $f"
            done
        fi
    done

    if [[ "$changes_found" == "false" ]]; then
        log_ok "No architecture changes since last check"
    else
        log_warn "Checking if new ADRs are required for these changes ..."
        log_info "Create if needed eine neue ADR: ./manage.sh adr-new \"Title\""
    fi

    date -Iseconds > "$last_adr_check"
}

# ───────────────────────────────────────────────────────────────────────
# Clean
# ───────────────────────────────────────────────────────────────────────
clean_caches() {
    log_step "Cleaning caches …"
    find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$FE_DIR/node_modules/.cache" -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_DIR" -type d -name "*.pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    log_ok "Caches cleaned"
}

# ───────────────────────────────────────────────────────────────────────
# Sibling discovery & delegation
# ───────────────────────────────────────────────────────────────────────
find_sibling_manage() {
    local name="$1"
    discover_siblings "$name" 2>/dev/null || true
    local var="DANWA_SIBLING_${name//-/_}"
    local dir="${!var:-}"
    if [[ -z "$dir" ]]; then
        dir="$PROJECT_DIR/../$name"
    fi
    if [[ -d "$dir" ]] && [[ -f "$dir/manage.sh" ]]; then
        echo "$dir/manage.sh"
        return 0
    fi
    return 1
}

delegate_to() {
    local name="$1"; shift
    local script
    if script="$(find_sibling_manage "$name")"; then
        log_step "Delegating to $name: $*"
        export DANWA_LIBDANWA_PATH="${DANWA_LIBDANWA_PATH:-$LIBDANWA_RESOLVED}"
        bash "$script" "$@"
    else
        log_warn "Sibling '$name' not found — skipping"
        return 1
    fi
}

# ───────────────────────────────────────────────────────────────────────
# Command dispatch
# ───────────────────────────────────────────────────────────────────────
cmd="${1:-}"
shift || true

case "$cmd" in
    start)
        what="${1:-fe}"
        case "$what" in
            be|backend) start_backend ;;
            fe|frontend|"") start_frontend ;;
            st|studio) start_studio ;;
            all) start_backend && start_frontend ;;
        esac
        ;;
    stop)
        what="${1:-fe}"
        case "$what" in
            be|backend) stop_backend ;;
            fe|frontend|"") stop_frontend ;;
            st|studio) stop_studio ;;
            all) stop_backend && stop_frontend ;;
        esac
        ;;
    restart|reload)
        stop_frontend
        sleep 1
        find "$PROJECT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
        start_frontend
        # Studio is intentionally NOT restarted — admin tool, independent lifecycle.
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
        log_step "Running tests …"
        cd "$PROJECT_DIR"
        export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
        export UV_PYTHONPATH="${PROJECT_DIR}:${UV_PYTHONPATH:-}"
        uv run pytest tests/backend/test_dms_ocr.py tests/backend/test_dms_api.py tests/test_paddleocr_integration.py tests/test_dms_document_processor.py -v 2>&1
        ;;
    # Cross-repo shortcuts
    backend|be)   delegate_to danwa-core "${1:-status}" ;;
    studio|st)    delegate_to danwa-studio "${1:-status}" ;;
    all)
        sub="${1:-status}"
        delegate_to danwa-core "$sub" || true
        delegate_to danwa-studio "$sub" || true
        ;;
    help|--help|-h)
        echo "Danwa Manager (refactored — Phase 8, repo-templates/danwa/manage.sh)"
        echo ""
        echo "  ./manage.sh                  interrunninges Dashboard"
        echo "  ./manage.sh start            Frontend starting (end-user UI)"
        echo "  ./manage.sh start be         Backend start (via danwa-core)"
        echo "  ./manage.sh start fe         nur Frontend starting"
        echo "  ./manage.sh start studio     nur Starting Danwa Studio (admin / dev)"
        echo "  ./manage.sh start all        Backend + Frontend starting"
        echo "  ./manage.sh stop             Stopping frontend"
        echo "  ./manage.sh stop be          Backend stop (via danwa-core)"
        echo "  ./manage.sh stop studio      nur Studio stop"
        echo "  ./manage.sh restart          Frontend neu start"
        echo "  ./manage.sh status           Show status (Backend + Frontend + Studio)"
        echo "  ./manage.sh status --json    JSON status (for Studio SystemManagementView)"
        echo "  ./manage.sh logs             Live-Logs (alle drei)"
        echo "  ./manage.sh logs be          Backend-Logs"
        echo "  ./manage.sh logs fe          Frontend-Logs"
        echo "  ./manage.sh logs st          Studio-Logs"
        echo "  ./manage.sh clean            Cleaning caches"
        echo "  ./manage.sh test             Running tests"
        echo "  ./manage.sh doc              Documentation commands"
        echo "  ./manage.sh doc-api          OpenAPI → Markdown"
        echo "  ./manage.sh doc-pdoc         Docstrings → HTML"
        echo "  ./manage.sh doc-architecture GitNexus Wiki"
        echo "  ./manage.sh doc-update       LLM-basierte Updates"
        echo "  ./manage.sh doc-all          Alle Docs generieren"
        echo "  ./manage.sh adr-new          Create new ADR"
        echo "  ./manage.sh adr-check        ADR-Check"
        ;;
    *)
        log_error "Unbekannter Befehl: '$cmd'. Versuche: ./manage.sh help"
        exit 1
        ;;
esac