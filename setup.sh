#!/usr/bin/env bash
# danwa/setup.sh — Thin shim that delegates to the canonical template.
#
# Canonical source of truth: repo-templates/danwa/setup.sh
# (This shim exists so `bash setup.sh` at the repo root keeps working
#  exactly as before, while the actual logic lives in the template.)
#
# Mirrors the strategy used by danwa-core and danwa-studio in earlier
# phases (Phase 2/3/6). See plans/2026-06-22_repo-setup-orchestration.md
# §3.2 step 8 for the refactoring rationale.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/repo-templates/danwa/setup.sh"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: canonical setup template not found at $TEMPLATE" >&2
    echo "Hint: git pull — repo-templates/danwa/setup.sh is the source of truth." >&2
    exit 1
fi

# Forward all env overrides (DANWA_PROJECT_DIR, DANWA_SKIP_NPM_INSTALL, …)
# Set DANWA_PROJECT_DIR to THIS script's dir (= repo root) unless the caller
# already supplied one. The template uses DANWA_PROJECT_DIR as the repo root
# (it falls back to its own SCRIPT_DIR otherwise, which would point at
# repo-templates/danwa/ and confuse the path resolution).
export DANWA_PROJECT_DIR="${DANWA_PROJECT_DIR:-$SCRIPT_DIR}"
exec bash "$TEMPLATE" "$@"