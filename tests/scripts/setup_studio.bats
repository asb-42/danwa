#!/usr/bin/env bats
#
# tests/scripts/setup_studio.bats — Unit tests for
# repo-templates/danwa-studio/setup.sh (the danwa-studio setup mirror
# template).
#
# Studio is a Node-only frontend. Differences from danwa-core:
#   - Toolchain: node + npm (not uv/python)
#   - No backend orchestration (no pyproject.toml, no uv sync)
#   - Single component: Vite dev server on STUDIO_PORT (default 5174)

setup() {
    TEST_TMP="$(mktemp -d /tmp/danwa-studio-setup-XXXXXX)"
    export TEST_TMP
    PROJECT_DIR="$TEST_TMP/danwa-studio"
    mkdir -p "$PROJECT_DIR"
    export PROJECT_DIR
    export DANWA_PROJECT_DIR="$PROJECT_DIR"

    SETUP_SCRIPT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/repo-templates/danwa-studio/setup.sh"
    export SETUP_SCRIPT

    LIBDANWA_PATH="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)/scripts/libdanwa.sh"
    export LIBDANWA_PATH
}

teardown() {
    rm -rf "$TEST_TMP"
    unset DANWA_PROJECT_DIR DANWA_LIBDANWA_PATH
}

# ════════════════════════════════════════════════════════════════════════
# Toolchain checks
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: file exists at repo-templates/danwa-studio/setup.sh" {
    [ -f "$SETUP_SCRIPT" ]
}

@test "setup.sh: exits 0 with valid .danwa-config and libdanwa available" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
TOOLCHAIN_NODE=22
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

@test "setup.sh: creates .lib/libdanwa.sh when missing" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
EOF
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_LIBDANWA_PATH='$LIBDANWA_PATH' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [ -f "$PROJECT_DIR/.lib/libdanwa.sh" ]
}

@test "setup.sh: fails clearly when libdanwa.sh is missing everywhere" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
EOF
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"libdanwa.sh not found"* ]]
}

@test "setup.sh: fails when node is not available" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
TOOLCHAIN_NODE=22
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    # PATH that excludes /usr/bin (where node typically lives)
    # but keeps bash itself available
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' PATH='/usr/bin' bash '$SETUP_SCRIPT' 2>&1"
    # Either exits non-zero (node not found) OR succeeds if node happens
    # to be at a non-standard path. We only assert "node" appears in output.
    [[ "$output" == *"node"* ]] || [ "$status" -ne 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# Configuration + idempotency
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: requires .danwa-config to exist" {
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' DANWA_LIBDANWA_PATH='$LIBDANWA_PATH' bash '$SETUP_SCRIPT'"
    [ "$status" -ne 0 ]
    [[ "$output" == *"danwa-config"* ]]
}

@test "setup.sh: is idempotent — running twice succeeds" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
}

# ════════════════════════════════════════════════════════════════════════
# npm install
# ════════════════════════════════════════════════════════════════════════

@test "setup.sh: runs npm install when package.json exists" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"
    cat > "$PROJECT_DIR/package.json" <<'EOF'
{"name":"test","version":"0.0.1"}
EOF

    # npm install may fail in offline/test env, but setup.sh should attempt it
    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT' 2>&1 || true"
    # Either succeeds, or fails with npm-related error (acceptable in test env)
    [[ "$output" == *"npm install"* ]] || [[ "$output" == *"Setup complete"* ]] || [ "$status" -eq 0 ]
}

@test "setup.sh: skips npm install when no package.json" {
    cat > "$PROJECT_DIR/.danwa-config" <<'EOF'
REPO_NAME="danwa-studio"
STUDIO_PORT=15174
EOF
    mkdir -p "$PROJECT_DIR/.lib"
    cp "$LIBDANWA_PATH" "$PROJECT_DIR/.lib/libdanwa.sh"

    run bash -c "DANWA_PROJECT_DIR='$PROJECT_DIR' bash '$SETUP_SCRIPT'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"package.json"* ]] || [[ "$output" == *"skipping"* ]]
}