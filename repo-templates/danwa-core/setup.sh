#!/usr/bin/env bash
# repo-templates/danwa-core/setup.sh
#
# CANONICAL SETUP TEMPLATE for danwa-core.
#
# This file is the single source of truth for the danwa-core setup
# procedure. Mirror it (or symlink to it) into a danwa-core clone as
# `setup.sh` at the repo root.
#
# Usage (from inside the cloned danwa-core repo):
#     bash setup.sh
#
# Override:
#   DANWA_PROJECT_DIR=/path/to/project  bash setup.sh
#
# What it does:
#   1. Validates .danwa-config exists
#   2. Checks toolchain (uv, python3)
#   3. Fetches libdanwa.sh into .lib/ if missing (offline-friendly)
#   4. Detects sibling repos (danwa, danwa-studio) in parent dir
#   5. Runs uv sync to install Python deps
#
# Idempotent: re-running is safe.

set -uo pipefail
# NOTE: -u is unsafe because some env vars may be unset on first run.

# Resolve paths: prefer $DANWA_PROJECT_DIR (for tests + mirror templates),
# otherwise default to the directory where setup.sh lives.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${DANWA_PROJECT_DIR:-$SCRIPT_DIR}"
LIB_DIR="$PROJECT_DIR/.lib"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"
CONFIG_FILE="$PROJECT_DIR/.danwa-config"

# Find libdanwa.sh (in priority order):
#   1. $DANWA_LIBDANWA_PATH env override (for tests + mirror templates)
#   2. ./.lib/libdanwa.sh (preferred — local install)
#   3. ./scripts/libdanwa.sh (when this repo IS danwa, used as source)
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

# Source the library (tries find_libdanwa, exits if not found)
LIBDANWA_PATH_RESOLVED="$(find_libdanwa)" || {
    echo "ERROR: libdanwa.sh not found. Looked in:" >&2
    echo "  - \$DANWA_LIBDANWA_PATH env override" >&2
    echo "  - $LIB_DIR/libdanwa.sh" >&2
    echo "  - $PROJECT_DIR/scripts/libdanwa.sh" >&2
    echo "" >&2
    echo "Hint: fetch with 'curl -L <danwa-modules-raw-url>/scripts/libdanwa.sh -o .lib/libdanwa.sh'" >&2
    echo "or copy from the danwa monorepo: cp ../danwa/scripts/libdanwa.sh .lib/libdanwa.sh" >&2
    exit 1
}
# shellcheck disable=SC1090
source "$LIBDANWA_PATH_RESOLVED"

# ───────────────────────────────────────────────────────────────────────
# Step 1: Validate .danwa-config
# ───────────────────────────────────────────────────────────────────────
log_step "1/5: Validating .danwa-config"
if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error ".danwa-config not found at $CONFIG_FILE"
    log_info "Expected KEY=VALUE pairs: REPO_NAME, BACKEND_PORT, etc."
    exit 1
fi
log_ok "Found $CONFIG_FILE"

# ───────────────────────────────────────────────────────────────────────
# Step 2: Toolchain checks
# ───────────────────────────────────────────────────────────────────────
log_step "2/5: Checking toolchain"
require_cmd python3 || exit 1
require_cmd uv || {
    log_info "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
}
log_ok "Python 3 + uv present"

# ───────────────────────────────────────────────────────────────────────
# Step 3: Ensure .lib/libdanwa.sh is present
# ───────────────────────────────────────────────────────────────────────
log_step "3/5: Ensuring libdanwa.sh"
ensure_dir "$LIB_DIR"
if [[ ! -f "$LIB_DIR/libdanwa.sh" ]]; then
    cp "$LIBDANWA_PATH_RESOLVED" "$LIB_DIR/libdanwa.sh"
    log_ok "Copied libdanwa.sh into .lib/"
else
    log_ok "libdanwa.sh already in .lib/"
fi

# ───────────────────────────────────────────────────────────────────────
# Step 4: Detect sibling repos in parent directory
# ───────────────────────────────────────────────────────────────────────
log_step "4/5: Detecting sibling repos"
PARENT_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
SIBLINGS_FOUND=0
for sibling_name in danwa danwa-studio; do
    if [[ -d "$PARENT_DIR/$sibling_name" ]]; then
        log_ok "Found sibling: $PARENT_DIR/$sibling_name"
        SIBLINGS_FOUND=$((SIBLINGS_FOUND + 1))
    fi
done
if [[ $SIBLINGS_FOUND -eq 0 ]]; then
    log_warn "No sibling repos found in $PARENT_DIR (expected: danwa, danwa-studio)"
    log_info "Orchestrator mode requires both; standalone mode works without."
else
    log_ok "Found $SIBLINGS_FOUND sibling(s)"
fi

# ───────────────────────────────────────────────────────────────────────
# Step 5: Install Python deps via uv sync
# ───────────────────────────────────────────────────────────────────────
log_step "5/5: Installing Python dependencies (uv sync)"
cd "$PROJECT_DIR"
if [[ -f "pyproject.toml" ]]; then
    uv sync || {
        log_error "uv sync failed"
        exit 1
    }
    log_ok "Python dependencies installed"
else
    log_warn "No pyproject.toml found — skipping uv sync (expected for the mirror template)"
fi

# ───────────────────────────────────────────────────────────────────────
# Done
# ───────────────────────────────────────────────────────────────────────
ensure_dir "$LOG_DIR"
ensure_dir "$PID_DIR"
log_header "Setup complete!"
log_info "Next steps:"
log_info "  - Run 'bash manage.sh start' to start the backend (and sibling apps if present)"
log_info "  - Run 'bash manage.sh status' to check status"
log_info "  - Run 'bash manage.sh help' for all commands"