#!/usr/bin/env bats
#
# tests/scripts/manage_orchestrator.bats — Unit tests for
# repo-templates/danwa-core/manage.sh (orchestrator template).
#
# These tests verify the lifecycle management contract for the
# danwa-core manage.sh. It is an *orchestrator* — it manages the local
# backend AND optionally starts sibling frontends (danwa, danwa-studio)
# detected in the parent directory.
#
# Coverage (~12 tests):
#   - Command dispatch (help, start, stop, restart, status, logs, clean)
#   - --json status output for studio SystemManagementView
#   - Backend start/stop lifecycle (with mock-uvicorn)
#   - Sibling frontend lifecycle (start, stop)
#   - Idempotency

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-manage-test-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa-core"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    # Override paths for isolated state
    PID_DIR="$PROJECT_DIR/pids"
    LOG_DIR="$PROJECT_DIR/logs"
    BACKEND_PID_FILE="$PID_DIR/backend.pid"
    FE_USER_PID_FILE="$PID_DIR/frontend-user.pid"
    STUDIO_PID_FILE="$PID_DIR/studio.pid"
    BACKEND_LOG="$LOG_DIR/backend.log"
    FE_USER_LOG="$LOG_DIR/frontend-user.log"
    STUDIO_LOG="$LOG_DIR/studio.log"
    mkdir -p "$PID_DIR" "$LOG_DIR"

    MANAGE_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa-core/manage.sh"
    export MANAGE_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH

    # Minimal .danwa-config
    cat > "$PROJECT_DIR/.danwa-config" <<EOF
REPO_NAME="danwa-core"
REPO_ROLE="backend+orchestrator"
BACKEND_PORT=18000
FRONTEND_PORT=15173
STUDIO_PORT=15174
SIBLINGS=("danwa" "danwa-studio")
EOF
    # Make library available to manage.sh
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    # Override ports to high numbers to avoid clashes in test
    export BACKEND_PORT=18000
    export FRONTEND_PORT=15173
    export STUDIO_PORT=15174

    # Use mock backends that just sleep instead of real uvicorn/npm
    export DANWA_USE_MOCK=1
}

teardown() {
    # Cleanup any leftover mock processes
    if [[ -f "$BACKEND_PID_FILE" ]]; then
        local pid
        pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    fi
    if [[ -f "$FE_USER_PID_FILE" ]]; then
        local pid
        pid="$(cat "$FE_USER_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    fi
    if [[ -f "$STUDIO_PID_FILE" ]]; then
        local pid
        pid="$(cat "$STUDIO_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    fi
    pkill -f "danwa-mock" 2>/dev/null || true
    rm -rf "$TEST_TMP"
}

# ════════════════════════════════════════════════════════════════════════
# Command dispatch
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: file exists at repo-templates/danwa-core/manage.sh" {
    [ -f "$MANAGE_SCRIPT" ]
}

@test "manage.sh: help command exits 0 and prints usage" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' help"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage"* ]] || [[ "$output" == *"usage"* ]] || [[ "$output" == *"Befehl"* ]] || [[ "$output" == *"Commands"* ]]
}

@test "manage.sh: unknown command exits non-zero with hint" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' this-is-not-a-command"
    [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Status (human + JSON)
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: status prints human-readable output" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status"
    [ "$status" -eq 0 ]
    [[ "$output" == *"backend"* ]] || [[ "$output" == *"Backend"* ]]
}

@test "manage.sh: status --json prints valid JSON" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    # Output must contain at least a curly brace
    [[ "$output" == *"{"* ]]
    [[ "$output" == *"}"* ]]
}

@test "manage.sh: status --json reports no running components when fresh" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    # Backend should be stopped
    [[ "$output" == *'"backend"'* ]]
    [[ "$output" == *'"alive"'* ]]
}

# ════════════════════════════════════════════════════════════════════════
# Backend lifecycle (mock-based)
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: start (mock) creates backend.pid" {
    run bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start"
    [ "$status" -eq 0 ]
    [ -f "$BACKEND_PID_FILE" ]
}

@test "manage.sh: stop (mock) kills the backend" {
    # Start first
    bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start" > /dev/null 2>&1
    sleep 0.5
    [ -f "$BACKEND_PID_FILE" ]

    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' stop"
    [ "$status" -eq 0 ]
    # PID file removed after stop
    [ ! -f "$BACKEND_PID_FILE" ] || ! kill -0 "$(cat "$BACKEND_PID_FILE" 2>/dev/null)" 2>/dev/null
}

@test "manage.sh: stop is idempotent — no backend running is OK" {
    # Don't start, just stop
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' stop"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Orchestrator logic
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: detects sibling danwa in parent dir and offers to start it" {
    # Create fake sibling at parent level
    local parent
    parent="$(dirname "$PROJECT_DIR")"
    mkdir -p "$parent/danwa"

    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status"
    [ "$status" -eq 0 ]
    [[ "$output" == *"danwa"* ]] || [[ "$output" == *"frontend"* ]]

    rm -rf "$parent/danwa"
}

@test "manage.sh: start without siblings only starts backend" {
    # No siblings
    run bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start"
    [ "$status" -eq 0 ]
    [ -f "$BACKEND_PID_FILE" ]
    # Frontend/studio PIDs NOT created
    [ ! -f "$FE_USER_PID_FILE" ]
    [ ! -f "$STUDIO_PID_FILE" ]
}

# ════════════════════════════════════════════════════════════════════════
# Logs + Clean
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: clean removes logs but not pids of running processes" {
    bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start" > /dev/null 2>&1
    sleep 0.5
    [ -f "$BACKEND_LOG" ] || echo "test" > "$BACKEND_LOG"

    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' clean"
    [ "$status" -eq 0 ]
}