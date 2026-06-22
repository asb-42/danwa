#!/usr/bin/env bats
#
# tests/scripts/libdanwa.bats — Unit tests for libdanwa.sh v1.0
#
# These tests follow TDD: they were written FIRST, before libdanwa.sh
# was implemented. Each test defines a contract that the library must
# fulfill. Tests are grouped by function family.
#
# Test coverage: ~30 tests targeting every exported function.
#
# Run with: bats tests/scripts/libdanwa.bats
# Or all script tests: bats tests/scripts/

# NOTE on bats sourcing: when setup() is defined in a sourced file,
# bats runs it in a subshell, so exported variables don't propagate
# to the test body. We inline the setup logic here. mocks.bash can
# still be sourced because it only defines functions.

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-test-XXXXXX)"
    export TEST_TMP
    PID_DIR="$TEST_TMP/pids"
    LOG_DIR="$TEST_TMP/logs"
    DANWA_LIB="$TEST_TMP/.lib"
    export PID_DIR LOG_DIR DANWA_LIB
    mkdir -p "$PID_DIR" "$LOG_DIR" "$DANWA_LIB"
    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH
}

teardown() {
    if [[ -n "${MOCK_PID:-}" ]]; then
        kill "$MOCK_PID" 2>/dev/null || true
        wait "$MOCK_PID" 2>/dev/null || true
        unset MOCK_PID
    fi
    if [[ -f "$PID_DIR/backend.pid" ]]; then
        local pid
        pid="$(cat "$PID_DIR/backend.pid" 2>/dev/null | tr -d '[:space:]')"
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    fi
    pkill -f "danwa-test-mock" 2>/dev/null || true
    [[ -n "${TEST_TMP:-}" ]] && rm -rf "$TEST_TMP"
}

source "${BATS_TEST_DIRNAME}/helpers/mocks.bash"

# ════════════════════════════════════════════════════════════════════════
# Library bootstrap + version guard
# ════════════════════════════════════════════════════════════════════════

@test "libdanwa.sh: file exists at scripts/libdanwa.sh" {
    [ -f "$LIBDANWA_PATH" ]
}

@test "libdanwa.sh: defines LIBDANWA_VERSION=v1.0.0" {
    run bash -c "source '$LIBDANWA_PATH' && echo \"\$LIBDANWA_VERSION\""
    [ "$status" -eq 0 ]
    [ "$output" = "v1.0.0" ]
}

@test "libdanwa.sh: is safe to source multiple times (no double-execution)" {
    run bash -c "source '$LIBDANWA_PATH'; source '$LIBDANWA_PATH'; echo \"\$LIBDANWA_VERSION\""
    [ "$status" -eq 0 ]
    [ "$output" = "v1.0.0" ]
}

@test "libdanwa.sh: requires bash >= 4.0 (no parse errors)" {
    run bash -c "source '$LIBDANWA_PATH' && echo ok"
    [ "$status" -eq 0 ]
    [ "$output" = "ok" ]
}

# ════════════════════════════════════════════════════════════════════════
# Logging functions
# ════════════════════════════════════════════════════════════════════════

@test "log_info: prints [INFO] prefix to stdout" {
    run bash -c "source '$LIBDANWA_PATH' && log_info 'hello'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"[INFO]"* ]]
    [[ "$output" == *"hello"* ]]
}

@test "log_ok: prints [OK] prefix to stdout" {
    run bash -c "source '$LIBDANWA_PATH' && log_ok 'success'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"[OK]"* ]]
    [[ "$output" == *"success"* ]]
}

@test "log_warn: prints [WARN] prefix to stdout" {
    run bash -c "source '$LIBDANWA_PATH' && log_warn 'careful'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"[WARN]"* ]]
}

@test "log_error: prints [ERROR] prefix and exits 1" {
    run bash -c "source '$LIBDANWA_PATH' && log_error 'boom'"
    [ "$status" -eq 1 ]
    [[ "$output" == *"boom"* ]]
}

@test "log_step: prints step marker" {
    run bash -c "source '$LIBDANWA_PATH' && log_step 'phase'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"phase"* ]]
}

@test "log_header: prints box marker" {
    run bash -c "source '$LIBDANWA_PATH' && log_header 'title'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"title"* ]]
}

# ════════════════════════════════════════════════════════════════════════
# pid_running — process management
# ════════════════════════════════════════════════════════════════════════

@test "pid_running: returns 0 + PID when process is alive" {
    # Use the current test process as a known-alive PID
    echo "$$" > "$PID_DIR/test.pid"
    run bash -c "source '$LIBDANWA_PATH' && pid_running '$PID_DIR/test.pid'"
    [ "$status" -eq 0 ]
    [ "$output" = "$$" ]
}

@test "pid_running: returns non-zero when pid file does not exist" {
    run bash -c "source '$LIBDANWA_PATH' && pid_running '$PID_DIR/nonexistent.pid'"
    [ "$status" -ne 0 ]
    [ -z "$output" ]
}

@test "pid_running: returns non-zero when PID is dead" {
    echo "999999" > "$PID_DIR/test.pid"
    run bash -c "source '$LIBDANWA_PATH' && pid_running '$PID_DIR/test.pid'"
    [ "$status" -ne 0 ]
}

@test "pid_running: tolerates trailing whitespace in pid file" {
    echo "  $$  " > "$PID_DIR/test.pid"
    run bash -c "source '$LIBDANWA_PATH' && pid_running '$PID_DIR/test.pid'"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# kill_pid — graceful process termination
# ════════════════════════════════════════════════════════════════════════

@test "kill_pid: terminates a running mock process" {
    local mock_script
    mock_script="$(mock_uvicorn 30)"
    "$mock_script" &
    local pid=$!
    echo "$pid" > "$PID_DIR/mock.pid"
    sleep 0.2

    run bash -c "source '$LIBDANWA_PATH' && kill_pid '$PID_DIR/mock.pid'"
    sleep 0.3
    # After SIGTERM the process should be gone
    ! kill -0 "$pid" 2>/dev/null
}

@test "kill_pid: returns 0 even when pid file does not exist (idempotent)" {
    run bash -c "source '$LIBDANWA_PATH' && kill_pid '$PID_DIR/nonexistent.pid'"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# wait_for_url — health-check polling
# ════════════════════════════════════════════════════════════════════════

@test "wait_for_url: returns 0 immediately when URL already healthy" {
    local mock_port=18871
    MOCK_PORT=$mock_port start_mock_http_server
    run bash -c "source '$LIBDANWA_PATH' && wait_for_url 'http://127.0.0.1:$mock_port/' 5"
    [ "$status" -eq 0 ]
    kill_mock_process
}

@test "wait_for_url: returns non-zero when timeout exceeded" {
    # Port 1 is reserved + unlikely to have a listener
    run bash -c "source '$LIBDANWA_PATH' && wait_for_url 'http://127.0.0.1:1/' 1"
    [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# wait_for_port — TCP-connect polling
# ════════════════════════════════════════════════════════════════════════

@test "wait_for_port: returns 0 when port is open" {
    local mock_port=18872
    MOCK_PORT=$mock_port start_mock_http_server
    run bash -c "source '$LIBDANWA_PATH' && wait_for_port $mock_port 127.0.0.1 5"
    [ "$status" -eq 0 ]
    kill_mock_process
}

@test "wait_for_port: returns non-zero when port closed + timeout" {
    run bash -c "source '$LIBDANWA_PATH' && wait_for_port 1 127.0.0.1 1"
    [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# require_cmd / require_var — pre-condition guards
# ════════════════════════════════════════════════════════════════════════

@test "require_cmd: returns 0 for available command" {
    run bash -c "source '$LIBDANWA_PATH' && require_cmd bash"
    [ "$status" -eq 0 ]
}

@test "require_cmd: exits 1 for missing command" {
    run bash -c "source '$LIBDANWA_PATH' && require_cmd this-command-does-not-exist-1234567890"
    [ "$status" -eq 1 ]
}

@test "require_var: returns 0 for set non-empty variable" {
    run bash -c "source '$LIBDANWA_PATH' && FOO=bar require_var FOO"
    [ "$status" -eq 0 ]
}

@test "require_var: exits 1 for unset variable" {
    run bash -c "source '$LIBDANWA_PATH' && unset DANWA_NONEXISTENT_VAR_XYZ && require_var DANWA_NONEXISTENT_VAR_XYZ"
    [ "$status" -eq 1 ]
}

# ════════════════════════════════════════════════════════════════════════
# ensure_dir / compose_url — filesystem + URL helpers
# ════════════════════════════════════════════════════════════════════════

@test "ensure_dir: creates directory if missing" {
    local target="$TEST_TMP/newdir"
    run bash -c "source '$LIBDANWA_PATH' && ensure_dir '$target'"
    [ "$status" -eq 0 ]
    [ -d "$target" ]
}

@test "ensure_dir: no-op if directory already exists" {
    mkdir -p "$TEST_TMP/existing"
    run bash -c "source '$LIBDANWA_PATH' && ensure_dir '$TEST_TMP/existing'"
    [ "$status" -eq 0 ]
    [ -d "$TEST_TMP/existing" ]
}

@test "compose_url: returns correct URL string" {
    run bash -c "source '$LIBDANWA_PATH' && compose_url http localhost 8000"
    [ "$status" -eq 0 ]
    [ "$output" = "http://localhost:8000" ]
}

@test "compose_url: handles custom scheme" {
    run bash -c "source '$LIBDANWA_PATH' && compose_url https danwa.example.com 443"
    [ "$status" -eq 0 ]
    [ "$output" = "https://danwa.example.com:443" ]
}

# ════════════════════════════════════════════════════════════════════════
# Version checks
# ════════════════════════════════════════════════════════════════════════

@test "check_node_version: returns 0 if node available and meets minimum" {
    if ! command -v node &>/dev/null; then
        skip "node not installed in test env"
    fi
    run bash -c "source '$LIBDANWA_PATH' && check_node_version 1"
    [ "$status" -eq 0 ]
}

@test "check_python_version: returns 0 if python3 available and meets minimum" {
    if ! command -v python3 &>/dev/null; then
        skip "python3 not installed in test env"
    fi
    run bash -c "source '$LIBDANWA_PATH' && check_python_version 3"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# load_repo_config — load .danwa-config
# ════════════════════════════════════════════════════════════════════════

@test "load_repo_config: loads .danwa-config and exports variables" {
    cat > "$TEST_TMP/.danwa-config" <<'EOF'
REPO_NAME="testrepo"
BACKEND_PORT=9000
FRONTEND_PORT=4000
TOOLCHAIN_NODE=22
EOF
    run bash -c "source '$LIBDANWA_PATH' && cd '$TEST_TMP' && load_repo_config testrepo && echo \"\$REPO_NAME \$BACKEND_PORT \$FRONTEND_PORT \$TOOLCHAIN_NODE\""
    [ "$status" -eq 0 ]
    [ "$output" = "testrepo 9000 4000 22" ]
}

@test "load_repo_config: returns non-zero when .danwa-config missing" {
    run bash -c "source '$LIBDANWA_PATH' && load_repo_config this-repo-does-not-exist"
    [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# discover_siblings — find Sibling-Repos
# ════════════════════════════════════════════════════════════════════════

@test "discover_siblings: detects sibling repos in parent directory" {
    # Create a fake sibling layout relative to TEST_TMP's parent.
    # We use a fixed name (not $$) so the value is predictable across
    # the bats test runner and the subshell `run bash -c ...`.
    local parent_dir
    parent_dir="$(dirname "$TEST_TMP")"
    local fake_name="danwa-test-fake-sibling"
    local fake_dir="$parent_dir/$fake_name"
    mkdir -p "$fake_dir"

    run bash -c "
        source '$LIBDANWA_PATH'
        cd '$TEST_TMP'
        discover_siblings '$fake_name'
        env | grep '^DANWA_SIBLING_' || echo NO_SIBLING
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"$fake_dir"* ]]

    rm -rf "$fake_dir"
}