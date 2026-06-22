#!/usr/bin/env bats
#
# tests/scripts/manage_studio.bats — Unit tests for
# repo-templates/danwa-studio/manage.sh (the danwa-studio Vite
# standalone manage template).
#
# Studio is simpler than danwa-core:
#   - Single component: Vite dev server
#   - No orchestration (no sibling startup)
#   - No backend management
#
# Tests verify lifecycle, status (JSON for the SystemManagementView
# in danwa-studio's own UI), logs, clean, and help.

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-studio-manage-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa-studio"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    PID_DIR="$PROJECT_DIR/pids"
    LOG_DIR="$PROJECT_DIR/logs"
    STUDIO_PID_FILE="$PID_DIR/studio.pid"
    STUDIO_LOG="$LOG_DIR/studio.log"
    mkdir -p "$PID_DIR" "$LOG_DIR"

    MANAGE_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa-studio/manage.sh"
    export MANAGE_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH

    cat > "$PROJECT_DIR/.danwa-config" <<EOF
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
EOF

    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    export STUDIO_PORT=15174
    export DANWA_USE_MOCK=1
}

teardown() {
    if [[ -f "$STUDIO_PID_FILE" ]]; then
        local pid
        pid="$(cat "$STUDIO_PID_FILE" 2>/dev/null | tr -d '[:space:]')"
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    fi
    pkill -f "danwa-mock-studio" 2>/dev/null || true
    rm -rf "$TEST_TMP"
}

# ════════════════════════════════════════════════════════════════════════
# Command dispatch
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: file exists at repo-templates/danwa-studio/manage.sh" {
    [ -f "$MANAGE_SCRIPT" ]
}

@test "manage.sh: help command exits 0 and prints usage" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' help"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage"* ]] || [[ "$output" == *"Commands"* ]]
}

@test "manage.sh: unknown command exits non-zero" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' this-is-not-a-command"
    [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Status (human + JSON)
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: status prints human-readable output" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status"
    [ "$status" -eq 0 ]
    [[ "$output" == *"studio"* ]] || [[ "$output" == *"Studio"* ]]
}

@test "manage.sh: status --json prints valid JSON" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"{"* ]]
    [[ "$output" == *"}"* ]]
}

@test "manage.sh: status --json reports studio not running when fresh" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *'"studio"'* ]]
    [[ "$output" == *'"alive"'* ]]
}

# ════════════════════════════════════════════════════════════════════════
# Lifecycle (mock-based)
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: start (mock) creates studio.pid" {
    run bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start"
    [ "$status" -eq 0 ]
    [ -f "$STUDIO_PID_FILE" ]
}

@test "manage.sh: stop (mock) kills the studio" {
    bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start" > /dev/null 2>&1
    sleep 0.5
    [ -f "$STUDIO_PID_FILE" ]

    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' stop"
    [ "$status" -eq 0 ]
    [ ! -f "$STUDIO_PID_FILE" ] || ! kill -0 "$(cat "$STUDIO_PID_FILE" 2>/dev/null)" 2>/dev/null
}

@test "manage.sh: stop is idempotent — no studio running is OK" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' stop"
    [ "$status" -eq 0 ]
}

@test "manage.sh: start is idempotent — running studio reports already-running" {
    bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start" > /dev/null 2>&1
    sleep 0.3
    run bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start"
    [ "$status" -eq 0 ]
    [[ "$output" == *"already running"* ]]
}

# ════════════════════════════════════════════════════════════════════════
# Logs + Clean
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: clean removes logs" {
    bash -c "cd '$PROJECT_DIR' && DANWA_USE_MOCK=1 bash '$MANAGE_SCRIPT' start" > /dev/null 2>&1
    sleep 0.3
    [ -f "$STUDIO_LOG" ] || echo "test" > "$STUDIO_LOG"

    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' clean"
    [ "$status" -eq 0 ]
    [ ! -f "$STUDIO_LOG" ]
}