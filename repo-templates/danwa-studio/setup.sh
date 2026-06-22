#!/usr/bin/env bash
# repo-templates/danwa-studio/setup.sh
#
# CANONICAL SETUP TEMPLATE for danwa-studio.
#
# Single source of truth for the danwa-studio setup procedure. Mirror
# it (or symlink to it) into a danwa-studio clone as `setup.sh` at the
# repo root.
#
# Usage (from inside the cloned danwa-studio repo):
#     bash setup.sh
#
# Override:
#   DANWA_PROJECT_DIR=/path/to/project  bash setup.sh
#
# What it does:
#   1. Validates .danwa-config exists
#   2. Checks toolchain (node, npm)
#   3. Fetches libdanwa.sh into .lib/ if missing
#   4. Detects sibling repos (danwa-core) in parent dir (optional)
#   5. Runs npm install if package.json is present
#
# Idempotent: re-running is safe.

set -uo pipefail

# Path resolution: prefer $DANWA_PROJECT_DIR (for tests + mirror templates),
# otherwise default to the directory where setup.sh lives.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${DANWA_PROJECT_DIR:-$SCRIPT_DIR}"
LIB_DIR="$PROJECT_DIR/.lib"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"
CONFIG_FILE="$PROJECT_DIR/.danwa-config"

STUDIO_PORT="${STUDIO_PORT:-5174}"

# Find libdanwa.sh (priority order)
find_libdanwa() {
    if [[ -n "${DANWA_LIBDANWA_PATH:-}" ]] && [[ -f "$DANWA_LIBDANWA_PATH" ]]; then
        echo "$DANWA_LIBDANWA_PATH"
        return 0
    fi
    if [[ -f "$LIB_DIR/libdanwa.sh" ]]; then
        echo "$LIB_DIR/libdanwa.sh"
        return 0
    fi
    if [[ -f "$PROJECT_DIR/scripts/libdanwa.sh" ]]; then
        echo "$PROJECT_DIR/scripts/libdanwa.sh"
        return 0
    fi
    return 1
}

LIBDANWA_RESOLVED="$(find_libdanwa)" || {
    echo "ERROR: libdanwa.sh not found. Looked in:" >&2
    echo "  - \$DANWA_LIBDANWA_PATH env override" >&2
    echo "  - $LIB_DIR/libdanwa.sh" >&2
    echo "  - $PROJECT_DIR/scripts/libdanwa.sh" >&2
    echo "" >&2
    echo "Hint: fetch with 'curl -L <danwa-modules-raw-url>/scripts/libdanwa.sh -o .lib/libdanwa.sh'" >&2
    exit 1
}
# shellcheck disable=SC1090
source "$LIBDANWA_RESOLVED"

# ───────────────────────────────────────────────────────────────────────
# Step 1: Validate .danwa-config
# ───────────────────────────────────────────────────────────────────────
log_step "1/5: Validating .danwa-config"
if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error ".danwa-config not found at $CONFIG_FILE"
    log_info "Expected KEY=VALUE pairs: REPO_NAME, STUDIO_PORT, etc."
    exit 1
fi
log_ok "Found $CONFIG_FILE"

# ───────────────────────────────────────────────────────────────────────
# Step 2: Toolchain checks (Node + npm)
# ───────────────────────────────────────────────────────────────────────
log_step "2/5: Checking toolchain"
require_cmd node || exit 1
require_cmd npm || exit 1
log_ok "Node.js + npm present"

# ───────────────────────────────────────────────────────────────────────
# Step 3: Ensure .lib/libdanwa.sh is present
# ───────────────────────────────────────────────────────────────────────
log_step "3/5: Ensuring libdanwa.sh"
ensure_dir "$LIB_DIR"
if [[ ! -f "$LIB_DIR/libdanwa.sh" ]]; then
    cp "$LIBDANWA_RESOLVED" "$LIB_DIR/libdanwa.sh"
    log_ok "Copied libdanwa.sh into .lib/"
else
    log_ok "libdanwa.sh already in .lib/"
fi

# ───────────────────────────────────────────────────────────────────────
# Step 4: Detect sibling repos in parent directory
# ───────────────────────────────────────────────────────────────────────
log_step "4/5: Detecting sibling repos (looking for danwa-core)"
PARENT_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
if [[ -d "$PARENT_DIR/danwa-core" ]]; then
    log_ok "Found sibling: $PARENT_DIR/danwa-core"
else
    log_warn "No danwa-core sibling found in $PARENT_DIR (expected for normal use)"
    log_info "Studio can run standalone but expects danwa-core backend for API calls"
fi

# ───────────────────────────────────────────────────────────────────────
# Step 5: npm install
# ───────────────────────────────────────────────────────────────────────
log_step "5/5: Installing npm dependencies"
cd "$PROJECT_DIR"
if [[ -f "package.json" ]]; then
    npm install || {
        log_error "npm install failed"
        exit 1
    }
    log_ok "npm dependencies installed"
else
    log_warn "No package.json found — skipping npm install (expected for the mirror template)"
fi

# ───────────────────────────────────────────────────────────────────────
# Done
# ───────────────────────────────────────────────────────────────────────
ensure_dir "$LOG_DIR"
ensure_dir "$PID_DIR"
log_header "Setup complete!"
log_info "Next steps:"
log_info "  - Run 'bash manage.sh start' to start the Vite dev server (port $STUDIO_PORT)"
log_info "  - Run 'bash manage.sh status' to check status"
log_info "  - Run 'bash manage.sh help' for all commands"