#!/usr/bin/env bash
# repo-templates/danwa-studio/manage.sh
#
# CANONICAL MANAGE TEMPLATE for danwa-studio (Vite dev server).
#
# Single source of truth. Mirror it into a danwa-studio clone as
# `manage.sh` at the repo root.
#
# Usage:
#     bash manage.sh help
#     bash manage.sh start        # start Vite dev server
#     bash manage.sh stop
#     bash manage.sh restart
#     bash manage.sh status [--json]
#     bash manage.sh logs
#     bash manage.sh clean
#
# Env overrides:
#     DANWA_PROJECT_DIR=/path/to/project
#     DANWA_USE_MOCK=1
#     DANWA_LIBDANWA_PATH=/path/to/lib
#     STUDIO_PORT

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

STUDIO_PID_FILE="$PID_DIR/studio.pid"
STUDIO_LOG="$LOG_DIR/studio.log"

STUDIO_PORT="${STUDIO_PORT:-5174}"

MOCK_STUDIO_SCRIPT="${MOCK_STUDIO_SCRIPT:-$LOG_DIR/.mock-studio.sh}"

DANWA_USE_MOCK="${DANWA_USE_MOCK:-0}"

# Source libdanwa.sh
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

# Mock script for tests/CI
write_mock_script() {
    local path="$1"
    cat > "$path" <<'EOF'
#!/usr/bin/env bash
sleep 60
EOF
    chmod +x "$path"
}

# ───────────────────────────────────────────────────────────────────────
# Studio lifecycle
# ───────────────────────────────────────────────────────────────────────
start_studio() {
    ensure_dirs
    if pid_running "$STUDIO_PID_FILE" > /dev/null; then
        log_warn "Studio already running (PID $(pid_running "$STUDIO_PID_FILE"))"
        return 0
    fi
    log_step "Starting studio (port $STUDIO_PORT)..."
    if [[ "$DANWA_USE_MOCK" == "1" ]]; then
        write_mock_script "$MOCK_STUDIO_SCRIPT"
        nohup "$MOCK_STUDIO_SCRIPT" > "$STUDIO_LOG" 2>&1 &
    else
        if [[ ! -f "$PROJECT_DIR/package.json" ]]; then
            log_error "package.json missing — cannot start Vite"
            return 1
        fi
        (cd "$PROJECT_DIR" && nohup npm run dev -- --port "$STUDIO_PORT" --host 127.0.0.1 \
            > "$STUDIO_LOG" 2>&1 &)
    fi
    local pid=$!
    echo "$pid" > "$STUDIO_PID_FILE"
    log_ok "Studio started (PID $pid, log: $STUDIO_LOG)"
}

stop_studio() {
    if ! pid_running "$STUDIO_PID_FILE" > /dev/null; then
        log_info "Studio is not running"
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
    log_header "Starting danwa-studio"
    start_studio
    log_ok "Start complete. Run 'manage.sh status' to verify."
}

cmd_stop() {
    log_header "Stopping danwa-studio"
    stop_studio
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
  "studio": {
    "alive": $(pid_running "$STUDIO_PID_FILE" > /dev/null && echo true || echo false),
    "pid_file": "$STUDIO_PID_FILE",
    "log_file": "$STUDIO_LOG",
    "port": $STUDIO_PORT
  }
}
EOF
    else
        log_header "danwa-studio status"
        log_info "  studio: $(component_status "$STUDIO_PID_FILE")"
        log_info "  port:   $STUDIO_PORT"
    fi
}

cmd_logs() {
    tail -f "$STUDIO_LOG"
}

cmd_clean() {
    log_step "Cleaning log files..."
    rm -f "$STUDIO_LOG"
    log_ok "Logs cleaned"
}

cmd_help() {
    cat <<EOF
Usage: bash manage.sh <command> [args]

Commands:
  start              Start Vite dev server
  stop               Stop Vite dev server
  restart            Stop + start
  status [--json]    Show status (JSON for SystemManagementView)
  logs               Tail studio log
  clean              Remove log files
  help               This help

Env overrides:
  DANWA_PROJECT_DIR=/path/to/project
  DANWA_USE_MOCK=1                   Use mock backend (tests/CI only)
  DANWA_LIBDANWA_PATH=/path/to/lib   Override library location
  STUDIO_PORT                        Default: 5174
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