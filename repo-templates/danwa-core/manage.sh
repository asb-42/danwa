#!/usr/bin/env bash
# repo-templates/danwa-core/manage.sh
#
# CANONICAL MANAGE TEMPLATE for danwa-core (with Watcher-Loop + JSON-status).
#
# This file is the single source of truth for the danwa-core manage
# procedure, including:
#   - Local backend lifecycle
#   - Sibling frontends (danwa, danwa-studio) auto-start
#   - Watcher-Loop: auto-respawn after backend crash (opt-in)
#   - system_control.py endpoints: status --json for studio
#   - Mirror strategy via repo-templates/
#
# Usage:
#     bash manage.sh help
#     bash manage.sh start
#     bash manage.sh stop
#     bash manage.sh restart
#     bash manage.sh status [--json]
#     bash manage.sh logs [be|fe|st]
#     bash manage.sh clean
#
# Env overrides:
#     DANWA_PROJECT_DIR=/path/to/project
#     DANWA_USE_MOCK=1                   # use mock backends (tests/CI)
#     DANWA_LIBDANWA_PATH=/path/to/lib
#     BACKEND_PORT / FRONTEND_PORT / STUDIO_PORT
#     BACKEND_WATCHER_ENABLED=1          # auto-respawn on crash (default: 0)
#     BACKEND_WATCHER_INTERVAL=2        # poll interval seconds (default: 2)

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
WATCHER_PID_FILE="$PID_DIR/backend.watcher.pid"
LAST_RESTART_FILE="$PID_DIR/backend.last_restart"

BACKEND_LOG="$LOG_DIR/backend.log"
FE_USER_LOG="$LOG_DIR/frontend-user.log"
STUDIO_LOG="$LOG_DIR/studio.log"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STUDIO_PORT="${STUDIO_PORT:-5174}"
BACKEND_WATCHER_ENABLED="${BACKEND_WATCHER_ENABLED:-0}"
BACKEND_WATCHER_INTERVAL="${BACKEND_WATCHER_INTERVAL:-2}"

MOCK_BACKEND_SCRIPT="${MOCK_BACKEND_SCRIPT:-$LOG_DIR/.mock-backend.sh}"
MOCK_FRONTEND_SCRIPT="${MOCK_FRONTEND_SCRIPT:-$LOG_DIR/.mock-frontend.sh}"
MOCK_STUDIO_SCRIPT="${MOCK_STUDIO_SCRIPT:-$LOG_DIR/.mock-studio.sh}"

DANWA_USE_MOCK="${DANWA_USE_MOCK:-0}"
DANWA_VERSION="${DANWA_VERSION:-1.0.0}"

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

# Source .danwa-config
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

ensure_dirs() {
    ensure_dir "$PID_DIR"
    ensure_dir "$LOG_DIR"
}

write_mock_script() {
    local path="$1"
    cat > "$path" <<'EOF'
#!/usr/bin/env bash
sleep 60
EOF
    chmod +x "$path"
}

# ───────────────────────────────────────────────────────────────────────
# Backend lifecycle
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

# ───────────────────────────────────────────────────────────────────────
# Watcher loop
# ───────────────────────────────────────────────────────────────────────
start_watcher() {
    ensure_dirs
    if pid_running "$WATCHER_PID_FILE" > /dev/null; then
        log_warn "Watcher already running (PID $(pid_running "$WATCHER_PID_FILE"))"
        return 0
    fi
    log_step "Starting backend watcher (interval=${BACKEND_WATCHER_INTERVAL}s)..."

    (
        # Subshell to isolate vars
        while true; do
            sleep "$BACKEND_WATCHER_INTERVAL"
            # Check if backend is alive
            if [[ ! -f "$BACKEND_PID_FILE" ]] || ! kill -0 "$(cat "$BACKEND_PID_FILE" 2>/dev/null | tr -d '[:space:]')" 2>/dev/null; then
                # Respawn
                log_warn "Watcher: backend not running, respawning..."
                start_backend_no_watcher
                # Record respawn timestamp
                date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAST_RESTART_FILE" 2>/dev/null || \
                    echo "$(date +%s)" > "$LAST_RESTART_FILE"
            fi
        done
    ) &
    local watcher_pid=$!
    echo "$watcher_pid" > "$WATCHER_PID_FILE"
    log_ok "Watcher started (PID $watcher_pid, pid file: $WATCHER_PID_FILE)"
}

# Backend start without re-triggering the watcher (used inside the watcher loop)
start_backend_no_watcher() {
    if pid_running "$BACKEND_PID_FILE" > /dev/null; then
        return 0
    fi
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_BACKEND_SCRIPT"
        nohup "$MOCK_BACKEND_SCRIPT" > "$BACKEND_LOG" 2>&1 &
    else
        if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
            return 1
        fi
        (cd "$PROJECT_DIR" && nohup uv run uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" \
            > "$BACKEND_LOG" 2>&1 &)
    fi
    echo $! > "$BACKEND_PID_FILE"
}

stop_watcher() {
    if ! pid_running "$WATCHER_PID_FILE" > /dev/null; then
        return 0
    fi
    log_step "Stopping watcher..."
    kill_pid "$WATCHER_PID_FILE"
    rm -f "$WATCHER_PID_FILE"
    log_ok "Watcher stopped"
}

# ───────────────────────────────────────────────────────────────────────
# Sibling frontends (unchanged from Phase 2)
# ───────────────────────────────────────────────────────────────────────
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
    if [[ "$BACKEND_WATCHER_ENABLED" == "1" ]]; then
        start_watcher
    fi
    log_ok "Start complete. Run 'manage.sh status' to verify."
}

cmd_stop() {
    log_header "Stopping danwa-core (orchestrator mode)"
    stop_watcher
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
# Status (human + JSON, extended with watcher info)
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

    local backend_pid backend_alive
    backend_pid="$(pid_running "$BACKEND_PID_FILE" 2>/dev/null)" || backend_pid=""
    if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
        backend_alive=true
    else
        backend_alive=false
    fi

    local watcher_alive=false
    if pid_running "$WATCHER_PID_FILE" > /dev/null; then
        watcher_alive=true
    fi

    local last_restart_at="null"
    if [[ -f "$LAST_RESTART_FILE" ]]; then
        local raw
        raw="$(cat "$LAST_RESTART_FILE" 2>/dev/null | tr -d '[:space:]')"
        if [[ -n "$raw" ]]; then
            # Try ISO 8601 format first, else treat as epoch
            if [[ "$raw" =~ ^[0-9]+$ ]]; then
                last_restart_at="\"$(date -u -d "@$raw" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "$raw")\""
            else
                last_restart_at="\"$raw\""
            fi
        fi
    fi

    if [[ $json_mode -eq 1 ]]; then
        cat <<EOF
{
  "version": "$DANWA_VERSION",
  "watcher_enabled": $([[ "$BACKEND_WATCHER_ENABLED" == "1" ]] && echo true || echo false),
  "last_restart_at": $last_restart_at,
  "components": {
    "backend": {
      "alive": $backend_alive,
      "pid": ${backend_pid:-null},
      "pid_file": "$BACKEND_PID_FILE",
      "log_file": "$BACKEND_LOG",
      "port": $BACKEND_PORT
    },
    "watcher": {
      "alive": $watcher_alive,
      "pid_file": "$WATCHER_PID_FILE"
    },
    "frontend": {
      "alive": $(pid_running "$FE_USER_PID_FILE" > /dev/null && echo true || echo false),
      "pid_file": "$FE_USER_PID_FILE",
      "port": $FRONTEND_PORT
    },
    "studio": {
      "alive": $(pid_running "$STUDIO_PID_FILE" > /dev/null && echo true || echo false),
      "pid_file": "$STUDIO_PID_FILE",
      "port": $STUDIO_PORT
    }
  }
}
EOF
    else
        log_header "danwa-core status"
        log_info "  version:  $DANWA_VERSION"
        log_info "  backend:  $(component_status "$BACKEND_PID_FILE")"
        log_info "  watcher:  $(component_status "$WATCHER_PID_FILE") (enabled=$([[ "$BACKEND_WATCHER_ENABLED" == "1" ]] && echo yes || echo no))"
        log_info "  frontend: $(component_status "$FE_USER_PID_FILE")"
        log_info "  studio:   $(component_status "$STUDIO_PID_FILE")"
        if [[ -n "$last_restart_at" ]] && [[ "$last_restart_at" != "null" ]]; then
            log_info "  last_restart: $last_restart_at"
        fi
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
  start              Start backend + (optional) sibling frontends + watcher
  stop               Stop watcher + backend + siblings
  restart            Stop + start
  status [--json]    Show status (JSON for studio SystemManagementView)
  logs [be|fe|st|all] Tail logs
  clean              Remove log files
  help               This help

Env overrides:
  DANWA_PROJECT_DIR=/path/to/project
  DANWA_USE_MOCK=1                   Use mock backends (tests/CI only)
  DANWA_LIBDANWA_PATH=/path/to/lib   Override library location
  BACKEND_WATCHER_ENABLED=1          Auto-respawn backend on crash (default: 0)
  BACKEND_WATCHER_INTERVAL=2        Poll interval in seconds (default: 2)
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