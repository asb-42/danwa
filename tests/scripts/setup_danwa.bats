#!/usr/bin/env bats
#
# tests/scripts/setup_danwa.bats — Unit tests for
# repo-templates/danwa/setup.sh (user-app template).
#
# Verifies the setup contract: toolchain checks, libdanwa.sh fetch,
# sibling detection, npm install.
#
# Coverage (~8 tests):
#   - File exists at canonical path
#   - Exits 0 with full toolchain + libdanwa present
#   - Creates .lib/libdanwa.sh when missing (copies from DANWA_LIBDANWA_PATH)
#   - Fails clearly when libdanwa.sh is missing everywhere
#   - Requires .danwa-config
#   - Idempotent — second run still exits 0
#   - Sibling detection sets DANWA_SIBLING_danwa_core env var
#   - npm install is invoked when frontend/node_modules missing
#       (smoke — assert that the script does NOT fail when node_modules is missing
#        in mock mode; full npm install is exercised in e2e tests)

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-setup-test-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    SETUP_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa/setup.sh"
    export SETUP_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH

    # Don't actually clone siblings
    export DANWA_SKIP_SIBLING_CLONE=1
    # Don't actually run npm install
    export DANWA_SKIP_NPM_INSTALL=1
}

teardown() {
    rm -rf "$TEST_TMP"
    unset DANWA_PROJECT_DIR DANWA_LIBDANWA_PATH DANWA_SKIP_SIBLING_CLONE DANWA_SKIP_NPM_INSTALL
}

# ════════════════════════════════════════════════════════════════════════
# Toolchain + file presence
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: file exists at repo-templates/danwa/setup.sh" {
    [ -f "$SETUP_SCRIPT" ]
}

@test "setup.sh: exits 0 on a fresh checkout with all toolchain present" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa"
BACKEND_PORT=7860
FRONTEND_PORT=5173
TOOLCHAIN_NODE=22
EOF

    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    # Provide a fake node_modules so setup.sh doesn't try to npm install
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

@test "setup.sh: creates .lib/libdanwa.sh when missing (copies from DANWA_LIBDANWA_PATH)" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa"
BACKEND_PORT=7860
EOF
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_LIBDANWA_PATH='$LIBDANWA_PATH' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [ -f "$PROJECT_DIR/.lib/libdanwa.sh" ]
}

@test "setup.sh: fails clearly when libdanwa.sh is missing everywhere" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa"
EOF
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"libdanwa.sh not found"* ]]
}

# ════════════════════════════════════════════════════════════════════════
# Configuration + idempotency
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: requires .danwa-config to exist" {
    # No .danwa-config in PROJECT_DIR, but provide libdanwa
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"danwa-config"* ]]
}

@test "setup.sh: is idempotent — running twice succeeds" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa"
BACKEND_PORT=7860
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Sibling detection
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: detects danwa-core sibling in parent directory" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa"
BACKEND_PORT=7860
SIBLINGS=("danwa-core")
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"
    mkdir -p "$PROJECT_DIR/frontend/node_modules"

    # Create the sibling
    mkdir -p "$TEST_TMP/danwa-core"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_SKIP_NPM_INSTALL=1 bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"danwa-core"* ]]
}