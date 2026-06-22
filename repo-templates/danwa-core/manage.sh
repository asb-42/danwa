#!/usr/bin/env bash
# repo-templates/danwa-core/manage.sh
#
# CANONICAL MANAGE TEMPLATE for danwa-core.
#
# This file is the single source of truth for the danwa-core manage
# procedure. Mirror it (or symlink to it) into a danwa-core clone as
# `manage.sh` at the repo root.
#
# Usage (from inside the cloned danwa-core repo):
#     bash manage.sh help           # show usage
#     bash manage.sh start          # start backend + (optional) sibling frontends
#     bash manage.sh stop           # stop all
#     bash manage.sh restart        # stop + start
#     bash manage.sh status         # human-readable status
#     bash manage.sh status --json  # machine-readable status (for danwa-studio)
#     bash manage.sh logs [be|fe|st] # tail logs
#     bash manage.sh clean          # remove log files
#
# Env overrides:
#     DANWA_PROJECT_DIR=/path/to/project  bash manage.sh ...
#     DANWA_USE_MOCK=1                   # use mock backends (for tests/CI)
#     BACKEND_PORT / FRONTEND_PORT / STUDIO_PORT

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

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FE_USER_PID_FILE="$PID_DIR/frontend-user.pid"
STUDIO_PID_FILE="$PID_DIR/studio.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FE_USER_LOG="$LOG_DIR/frontend-user.log"
STUDIO_LOG="$LOG_DIR/studio.log"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STUDIO_PORT="${STUDIO_PORT:-5174}"

# Mock script paths (overridable for tests)
MOCK_BACKEND_SCRIPT="${MOCK_BACKEND_SCRIPT:-$LOG_DIR/.mock-backend.sh}"
MOCK_FRONTEND_SCRIPT="${MOCK_FRONTEND_SCRIPT:-$LOG_DIR/.mock-frontend.sh}"
MOCK_STUDIO_SCRIPT="${MOCK_STUDIO_SCRIPT:-$LOG_DIR/.mock-studio.sh}"

DANWA_USE_MOCK="${DANWA_USE_MOCK:-0}"

# ───────────────────────────────────────────────────────────────────────
# Source libdanwa.sh (resolve via .lib/, scripts/, or env override)
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

# Source .danwa-config (if present) to override defaults
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

ensure_dirs() {
    ensure_dir "$PID_DIR"
    ensure_dir "$LOG_DIR"
}

# ───────────────────────────────────────────────────────────────────────
# Mock backends (for tests / CI without real uvicorn/npm)
# ───────────────────────────────────────────────────────────────────────
write_mock_script() {
    local path="$1"
    cat > "$path" <<'EOF'
#!/usr/bin/env bash
sleep 60
EOF
    chmod +x "$path"
}

# ───────────────────────────────────────────────────────────────────────
# Component lifecycle
# ───────────────────────────────────────────────────────────────────────
start_backend() {
    ensure_dirs
    if pid_running "$BACKEND_PID_FILE" > /dev/null; then
        log_warn "Backend already running (PID $(pid_running "$BACKEND_PID_FILE"))"
        return 0
    fi
    log_step "Starting backend (port $BACKEND_PORT)..."
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_BACKEND_SCRIPT"
        nohup "$MOCK_BACKEND_SCRIPT" > "$BACKEND_LOG" 2>&1 &
    else
        if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
            log_error "pyproject.toml missing — cannot start backend with uv"
            return 1
        fi
        (cd "$PROJECT_DIR" && nohup uv run uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
            > "$BACKEND_LOG" 2>&1 &)
    fi
    local pid=$!
    echo "$pid" > "$BACKEND_PID_FILE"
    log_ok "Backend started (PID $pid, log: $BACKEND_LOG)"
}

stop_backend() {
    if ! pid_running "$BACKEND_PID_FILE" > /dev/null; then
        log_info "Backend is not running"
        return 0
    fi
    log_step "Stopping backend..."
    kill_pid "$BACKEND_PID_FILE"
    rm -f "$BACKEND_PID_FILE"
    log_ok "Backend stopped"
}

start_frontend_user() {
    ensure_dirs
    if pid_running "$FE_USER_PID_FILE" > /dev/null; then
        log_warn "Frontend user-app already running"
        return 0
    fi
    local frontend_dir="${DANWA_SIBLING_danwa:-$PROJECT_DIR/../danwa}"
    if [[ ! -d "$frontend_dir" ]]; then
        log_warn "Frontend user-app sibling not found, skipping"
        return 0
    fi
    log_step "Starting frontend user-app (port $FRONTEND_PORT)..."
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_FRONTEND_SCRIPT"
        nohup "$MOCK_FRONTEND_SCRIPT" > "$FE_USER_LOG" 2>&1 &
    else
        (cd "$frontend_dir" && nohup npm run dev -- --port "$FRONTEND_PORT" > "$FE_USER_LOG" 2>&1 &)
    fi
    local pid=$!
    echo "$pid" > "$FE_USER_PID_FILE"
    log_ok "Frontend user-app started"
}

stop_frontend_user() {
    if ! pid_running "$FE_USER_PID_FILE" > /dev/null; then
        return 0
    fi
    log_step "Stopping frontend user-app..."
    kill_pid "$FE_USER_PID_FILE"
    rm -f "$FE_USER_PID_FILE"
    log_ok "Frontend user-app stopped"
}

start_studio() {
    ensure_dirs
    if pid_running "$STUDIO_PID_FILE" > /dev/null; then
        log_warn "Studio already running"
        return 0
    fi
    local studio_dir="${DANWA_SIBLING_danwa_studio:-$PROJECT_DIR/../danwa-studio}"
    if [[ ! -d "$studio_dir" ]]; then
        log_warn "Studio sibling not found, skipping"
        return 0
    fi
    log_step "Starting studio (port $STUDIO_PORT)..."
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_STUDIO_SCRIPT"
        nohup "$MOCK_STUDIO_SCRIPT" > "$STUDIO_LOG" 2>&1 &
    else
        (cd "$studio_dir" && nohup npm run dev -- --port "$STUDIO_PORT" > "$STUDIO_LOG" 2>&1 &)
    fi
    local pid=$!
    echo "$pid" > "$STUDIO_PID_FILE"
    log_ok "Studio started"
}

stop_studio() {
    if ! pid_running "$STUDIO_PID_FILE" > /dev/null; then
        return 0
    fi
    log_step "Stopping studio..."
    kill_pid "$STUDIO_PID_FILE"
    rm -f "$STUDIO_PID_FILE"
    log_ok "Studio stopped"
}

# ───────────────────────────────────────────────────────────────────────
# Composite commands
# ───────────────────────────────────────────────────────────────────────
cmd_start() {
    log_header "Starting danwa-core (orchestrator mode)"
    discover_siblings danwa danwa-studio
    start_backend
    start_frontend_user
    start_studio
    log_ok "Start complete. Run 'manage.sh status' to verify."
}

cmd_stop() {
    log_header "Stopping danwa-core (orchestrator mode)"
    stop_studio
    stop_frontend_user
    stop_backend
    log_ok "Stop complete."
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

# ───────────────────────────────────────────────────────────────────────
# Status (human + JSON)
# ───────────────────────────────────────────────────────────────────────
component_status() {
    local pid_file="$1"
    local pid
    pid="$(pid_running "$pid_file" 2>/dev/null)" || pid=""
    if [[ -n "$pid" ]]; then
        echo "running (PID $pid)"
    else
        echo "stopped"
    fi
}

cmd_status() {
    local json_mode=0
    [[ "${1:-}" == "--json" ]] && json_mode=1

    if [[ $json_mode -eq 1 ]]; then
        cat <<EOF
{
  "backend":  { "alive": $(pid_running "$BACKEND_PID_FILE" > /dev/null && echo true || echo false), "pid_file": "$BACKEND_PID_FILE" },
  "frontend": { "alive": $(pid_running "$FE_USER_PID_FILE" > /dev/null && echo true || echo false), "pid_file": "$FE_USER_PID_FILE" },
  "studio":   { "alive": $(pid_running "$STUDIO_PID_FILE" > /dev/null && echo true || echo false), "pid_file": "$STUDIO_PID_FILE" }
}
EOF
    else
        log_header "danwa-core status"
        log_info "  backend:  $(component_status "$BACKEND_PID_FILE")"
        log_info "  frontend: $(component_status "$FE_USER_PID_FILE")"
        log_info "  studio:   $(component_status "$STUDIO_PID_FILE")"
    fi
}

cmd_logs() {
    local target="${1:-all}"
    case "$target" in
        be|backend)  tail -f "$BACKEND_LOG" ;;
        fe|frontend) tail -f "$FE_USER_LOG" ;;
        st|studio)   tail -f "$STUDIO_LOG" ;;
        all)
            log_info "Backend log:  $BACKEND_LOG"
            log_info "Frontend log: $FE_USER_LOG"
            log_info "Studio log:   $STUDIO_LOG"
            ;;
        *) log_error "Unknown log target: $target (use be|fe|st|all)"; return 1 ;;
    esac
}

cmd_clean() {
    log_step "Cleaning log files..."
    rm -f "$BACKEND_LOG" "$FE_USER_LOG" "$STUDIO_LOG"
    log_ok "Logs cleaned"
}

cmd_help() {
    cat <<EOF
Usage: bash manage.sh <command> [args]

Commands:
  start              Start backend + (optional) sibling frontends
  stop               Stop backend + siblings
  restart            Stop + start
  status [--json]    Show status (JSON for studio SystemManagementView)
  logs [be|fe|st|all] Tail logs
  clean              Remove log files
  help               This help

Env overrides:
  DANWA_PROJECT_DIR=/path/to/project
  DANWA_USE_MOCK=1                   Use mock backends (tests/CI only)
  DANWA_LIBDANWA_PATH=/path/to/lib   Override library location
  BACKEND_PORT / FRONTEND_PORT / STUDIO_PORT
EOF
}

# ───────────────────────────────────────────────────────────────────────
# Dispatch
# ───────────────────────────────────────────────────────────────────────
cmd="${1:-help}"
shift || true

case "$cmd" in
    start)        cmd_start "$@" ;;
    stop)         cmd_stop "$@" ;;
    restart)      cmd_restart "$@" ;;
    status)       cmd_status "$@" ;;
    logs)         cmd_logs "$@" ;;
    clean)        cmd_clean "$@" ;;
    help|--help|-h) cmd_help ;;
    *)
        log_error "Unknown command: $cmd"
        cmd_help
        exit 1
        ;;
esac