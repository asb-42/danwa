#!/usr/bin/env bats
#
# tests/scripts/setup.bats — Unit tests for repo-templates/danwa-core/setup.sh
#
# These tests verify the contract of `setup.sh` for a danwa-core mirror
# template. The actual setup.sh is the canonical reference; consumers
# mirror it into their danwa-core clone.

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-setup-test-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa-core"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    SETUP_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa-core/setup.sh"
    export SETUP_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH

    export DANWA_SKIP_SIBLING_CLONE=1
}

teardown() {
    rm -rf "$TEST_TMP"
    unset DANWA_PROJECT_DIR DANWA_LIBDANWA_PATH
}

# ════════════════════════════════════════════════════════════════════════
# Toolchain checks
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: file exists at repo-templates/danwa-core/setup.sh" {
    [ -f "$SETUP_SCRIPT" ]
}

@test "setup.sh: exits 0 on a fresh checkout with all toolchain present" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
BACKEND_PORT=8000
TOOLCHAIN_PYTHON=3.11
TOOLCHAIN_UV=required
EOF

    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

@test "setup.sh: creates .lib/libdanwa.sh when missing (copies from DANWA_LIBDANWA_PATH)" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
BACKEND_PORT=8000
EOF

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_LIBDANWA_PATH='$LIBDANWA_PATH' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [ -f "$PROJECT_DIR/.lib/libdanwa.sh" ]
}

@test "setup.sh: fails clearly when libdanwa.sh is missing everywhere" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
EOF

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"libdanwa.sh not found"* ]]
}

# ════════════════════════════════════════════════════════════════════════
# Configuration + idempotency
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: requires .danwa-config to exist" {
    # No .danwa-config in PROJECT_DIR, but provide libdanwa
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_LIBDANWA_PATH='$LIBDANWA_PATH' bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"danwa-config"* ]]
}

@test "setup.sh: is idempotent — running twice succeeds" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
BACKEND_PORT=8000
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Sibling discovery (offline)
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: detects existing sibling repos in parent dir" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
BACKEND_PORT=8000
SIBLINGS=("danwa" "danwa-studio")
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    # Create fake sibling dirs at the same level as danwa-core
    local project_parent
    project_parent="$(dirname "$PROJECT_DIR")"
    mkdir -p "$project_parent/danwa" "$project_parent/danwa-studio"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]

    rm -rf "$project_parent/danwa" "$project_parent/danwa-studio"
}

@test "setup.sh: warns (but doesn't fail) when no siblings found" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-core"
BACKEND_PORT=8000
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"No sibling"* ]] || [[ "$output" == *"sibling"* ]]
}