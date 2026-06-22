#!/usr/bin/env bash
# repo-templates/danwa/setup.sh
#
# CANONICAL SETUP TEMPLATE for danwa (user-app).
#
# This file is the single source of truth for the danwa setup
# procedure. Mirror it (or symlink to it) into a danwa clone as
# `setup.sh` at the repo root.
#
# Usage (from inside the cloned danwa repo):
#     bash setup.sh
#
# Override:
#   DANWA_PROJECT_DIR=/path/to/project  bash setup.sh
#   DANWA_SKIP_NPM_INSTALL=1            # skip npm install (tests/CI)
#   DANWA_SKIP_SIBLING_CLONE=1          # skip sibling detection (tests/CI)
#
# What it does:
#   1. Validates .danwa-config exists
#   2. Checks toolchain (node >= 22, npm)
#   3. Fetches libdanwa.sh into .lib/ if missing (offline-friendly)
#   4. Detects sibling repos (danwa-core) in parent dir
#   5. Runs npm install in frontend/ to install deps
#   6. Creates logs/ and pids/ directories
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
FE_DIR="$PROJECT_DIR/frontend"
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

# Validate REPO_NAME matches expected
# shellcheck disable=SC1090
( cd "$PROJECT_DIR" && load_repo_config "danwa" ) || {
    log_error "load_repo_config failed — REPO_NAME mismatch or invalid config"
    exit 1
}
log_ok "REPO_NAME matches (danwa)"

# ───────────────────────────────────────────────────────────────────────
# Step 2: Check toolchain
# ───────────────────────────────────────────────────────────────────────
log_step "2/5: Checking toolchain"
if ! check_node_version 22; then
    exit 1
fi
log_ok "Node.js $(node --version) >= 22"

if ! require_cmd npm; then
    exit 1
fi
log_ok "npm $(npm --version) found"

# ───────────────────────────────────────────────────────────────────────
# Step 3: Ensure libdanwa.sh is vendored into .lib/
# ───────────────────────────────────────────────────────────────────────
log_step "3/5: Vendoring libdanwa.sh into .lib/"
ensure_dir "$LIB_DIR"
if [[ ! -f "$LIB_DIR/libdanwa.sh" ]]; then
    cp "$LIBDANWA_PATH_RESOLVED" "$LIB_DIR/libdanwa.sh"
    log_ok "Vendored libdanwa.sh v${LIBDANWA_VERSION} → $LIB_DIR/libdanwa.sh"
else
    # Drift check — verify version is compatible (v1.x line)
    lib_version="$(grep -oE 'LIBDANWA_VERSION="v[0-9]+\.[0-9]+\.[0-9]+"' "$LIB_DIR/libdanwa.sh" | head -1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')"
    if [[ -z "$lib_version" ]]; then
        log_warn "Could not parse LIBDANWA_VERSION in .lib/libdanwa.sh — refetching"
        cp "$LIBDANWA_PATH_RESOLVED" "$LIB_DIR/libdanwa.sh"
    elif [[ ! "$lib_version" =~ ^v1\. ]]; then
        log_error "Vendored libdanwa.sh is $lib_version but manage.sh requires v1.x"
        exit 1
    else
        log_ok "Vendored libdanwa.sh $lib_version (compatible)"
    fi
fi

# ───────────────────────────────────────────────────────────────────────
# Step 4: Detect sibling repos (for orchestration hints)
# ───────────────────────────────────────────────────────────────────────
log_step "4/5: Detecting sibling repos"
if [[ "${DANWA_SKIP_SIBLING_CLONE:-0}" == "1" ]]; then
    log_info "DANWA_SKIP_SIBLING_CLONE=1 — skipping sibling detection"
elif [[ -d "$PROJECT_DIR/../danwa-core" ]]; then
    log_ok "Found sibling danwa-core at $PROJECT_DIR/../danwa-core"
    discover_siblings danwa-core 2>/dev/null || true
    log_info "Backend will be started by danwa-core/manage.sh (port ${BACKEND_PORT:-7860})"
else
    log_warn "No danwa-core sibling detected — backend must be started separately"
    log_info "Hint: clone danwa-core next to this repo, or run its manage.sh start"
fi

# ───────────────────────────────────────────────────────────────────────
# Step 5: Install npm dependencies
# ───────────────────────────────────────────────────────────────────────
log_step "5/5: Installing frontend dependencies"
if [[ ! -d "$FE_DIR" ]]; then
    log_error "frontend/ directory not found at $FE_DIR"
    exit 1
fi

if [[ "${DANWA_SKIP_NPM_INSTALL:-0}" == "1" ]]; then
    log_info "DANWA_SKIP_NPM_INSTALL=1 — skipping npm install"
elif [[ -d "$FE_DIR/node_modules" ]]; then
    log_ok "node_modules already present"
else
    log_step "Running npm install in $FE_DIR …"
    (cd "$FE_DIR" && npm install) || {
        log_error "npm install failed"
        exit 1
    }
    log_ok "npm install completed"
fi

# Create runtime dirs
ensure_dir "$LOG_DIR"
ensure_dir "$PID_DIR"
log_ok "Runtime dirs ready: logs/, pids/"

log_header "Setup complete"
log_info "Next steps:"
echo "  ./manage.sh start be    # start backend (requires danwa-core sibling or manual uvicorn)"
echo "  ./manage.sh start fe    # start frontend"
echo "  ./manage.sh dashboard   # interactive menu"