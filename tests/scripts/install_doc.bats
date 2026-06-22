#!/usr/bin/env bats
#
# tests/scripts/install_doc.bats — Documentation contract tests for
# INSTALL.md (Phase 9 of plans/2026-06-22_repo-setup-orchestration.md).
#
# Verifies that INSTALL.md exists at the repo root and contains every
# section the orchestration plan mandates:
#   - Quickstart (3-command setup)
#   - Sibling-Setup (danwa-core + danwa-studio detection)
#   - Link to libdanwa.sh version (with current version number)
#   - Studio-Backend-Restart hint (Phase 5 / system_control.py)
#   - Troubleshooting (at least one common issue + fix)
#
# Coverage: 6 tests
#   - File existence at repo root
#   - Mentions bash setup.sh
#   - Mentions bash manage.sh start
#   - Contains "## Quickstart" or "## Quick Start" section
#   - Contains "## Sibling" or "## Sibling-Setup" section
#   - Contains libdanwa version reference (v1.x)
#   - References Studio backend restart (POST /system/restart-backend OR
#     equivalent phrase)
#   - Has at least one ## Troubleshooting heading

setup() {
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    export REPO_ROOT
    export INSTALL_FILE="$REPO_ROOT/INSTALL.md"
}

teardown() {
    unset REPO_ROOT INSTALL_FILE
}

@test "INSTALL.md: exists at repo root" {
    [ -f "$INSTALL_FILE" ]
}

@test "INSTALL.md: contains 'bash setup.sh' quickstart command" {
    [ -f "$INSTALL_FILE" ]
    grep -q "bash setup.sh" "$INSTALL_FILE"
}

@test "INSTALL.md: contains 'bash manage.sh start' (or ./manage.sh start) quickstart command" {
    [ -f "$INSTALL_FILE" ]
    grep -qE "(bash|\\./) ?manage\\.sh start" "$INSTALL_FILE"
}

@test "INSTALL.md: has a 'Quickstart' or 'Quick Start' section" {
    [ -f "$INSTALL_FILE" ]
    grep -qE "^##+ +Quick[- ]?start" "$INSTALL_FILE"
}

@test "INSTALL.md: has a 'Sibling' section explaining danwa-core / danwa-studio detection" {
    [ -f "$INSTALL_FILE" ]
    grep -qiE "^##+ +sibling" "$INSTALL_FILE"
    # Should mention both sibling names
    grep -q "danwa-core" "$INSTALL_FILE"
    grep -q "danwa-studio" "$INSTALL_FILE"
}

@test "INSTALL.md: links to libdanwa.sh v1.x (current version)" {
    [ -f "$INSTALL_FILE" ]
    grep -qE "libdanwa.*v1\\." "$INSTALL_FILE"
}

@test "INSTALL.md: mentions Studio backend restart capability" {
    [ -f "$INSTALL_FILE" ]
    # Should reference either the HTTP endpoint or describe the feature
    grep -qiE "(studio.*restart|restart.*backend|system/restart-backend|system_control)" "$INSTALL_FILE"
}

@test "INSTALL.md: has a 'Troubleshooting' section" {
    [ -f "$INSTALL_FILE" ]
    grep -qiE "^##+ +troubleshoot" "$INSTALL_FILE"
}