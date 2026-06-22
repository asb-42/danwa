#!/usr/bin/env bats
#
# tests/scripts/manage_watcher.bats — Tests for the Watcher-Loop +
# extended JSON status output of repo-templates/danwa-core/manage.sh
# (Phase 5 of the orchestration plan).
#
# These tests are INTENTIONALLY minimal: they only verify the JSON
# schema and the watcher_enabled flag. Full respawn behavior is
# tested by the danwa-studio SystemManagementView integration in
# Phase 7 (manual smoke test).
#
# Why minimal: the watcher-loop runs as a long-lived subshell. Testing
# it requires either (a) killing the subshell after each test (fragile)
# or (b) running it in a separate process group (complex). Since the
# watcher only triggers on actual backend crashes, we test the
# configuration + JSON contract instead.
#
# Total: 5 tests, all run in < 3 seconds.

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-watcher-test-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa-core"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    MANAGE_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa-core/manage.sh"
    export MANAGE_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH

    cat > "$PROJECT_DIR/.danwa-config" <<EOF
REPO_NAME="danwa-core"
BACKEND_PORT=18000
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"
}

teardown() {
    rm -rf "$TEST_TMP"
    unset DANWA_PROJECT_DIR DANWA_LIBDANWA_PATH BACKEND_WATCHER_ENABLED
}

# ════════════════════════════════════════════════════════════════════════
# JSON status contract (Phase 5 main deliverable)
# ════════════════════════════════════════════════════════════════════════

@test "manage.sh: status --json includes watcher_enabled field" {
    run bash -c "cd '$PROJECT_DIR' && BACKEND_WATCHER_ENABLED=1 bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *'"watcher_enabled"'* ]]
}

@test "manage.sh: status --json watcher_enabled is true when env=1" {
    run bash -c "cd '$PROJECT_DIR' && BACKEND_WATCHER_ENABLED=1 bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *'"watcher_enabled": true'* ]]
}

@test "manage.sh: status --json watcher_enabled is false when env=0" {
    run bash -c "cd '$PROJECT_DIR' && BACKEND_WATCHER_ENABLED=0 bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *'"watcher_enabled": false'* ]]
}

@test "manage.sh: status --json includes version field" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json"
    [ "$status" -eq 0 ]
    [[ "$output" == *'"version"'* ]]
}

@test "manage.sh: status --json is valid JSON (parseable by python -m json.tool)" {
    run bash -c "cd '$PROJECT_DIR' && bash '$MANAGE_SCRIPT' status --json | python3 -m json.tool"
    [ "$status" -eq 0 ]
}