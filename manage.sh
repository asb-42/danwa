#!/usr/bin/env bash
# danwa/manage.sh — Thin shim that delegates to the canonical template.
#
# Canonical source of truth: repo-templates/danwa/manage.sh
# (This shim exists so `bash manage.sh <cmd>` at the repo root keeps
#  working exactly as before, while the actual logic — and tests —
#  live in the template.)
#
# Mirrors the strategy used by danwa-core and danwa-studio in earlier
# phases (Phase 3/5/6). See plans/2026-06-22_repo-setup-orchestration.md
# §3.2 step 8 for the refactoring rationale.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/repo-templates/danwa/manage.sh"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: canonical manage template not found at $TEMPLATE" >&2
    echo "Hint: git pull — repo-templates/danwa/manage.sh is the source of truth." >&2
    exit 1
fi

# Forward all env overrides (DANWA_PROJECT_DIR, DANWA_USE_MOCK, BACKEND_PORT, …)
# and all CLI arguments unchanged. See setup.sh for the same rationale.
export DANWA_PROJECT_DIR="${DANWA_PROJECT_DIR:-$SCRIPT_DIR}"
exec bash "$TEMPLATE" "$@"