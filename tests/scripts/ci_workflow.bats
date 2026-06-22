#!/usr/bin/env bats
#
# tests/scripts/ci_workflow.bats — Contract tests for
# .github/workflows/test-scripts.yml (Phase 11 of
# plans/2026-06-22_repo-setup-orchestration.md).
#
# Verifies the CI workflow file exists, is valid YAML, and contains
# the required jobs/steps from plan §3.4.5:
#   - Trigger on push + pull_request
#   - Job runs on ubuntu-latest
#   - Steps: actions/checkout@v4, install bats, run bats, upload TAP
#
# Coverage: 7 tests

setup() {
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
    export REPO_ROOT
    export WORKFLOW="$REPO_ROOT/.github/workflows/test-scripts.yml"
}

teardown() {
    unset REPO_ROOT WORKFLOW
}

@test "CI workflow: file exists at .github/workflows/test-scripts.yml" {
    [ -f "$WORKFLOW" ]
}

@test "CI workflow: is valid YAML (parseable)" {
    [ -f "$WORKFLOW" ]
    command -v python3 >/dev/null || command -v python >/dev/null || skip "no python"
    run python3 -c "import yaml, sys; yaml.safe_load(open('$WORKFLOW'))"
    [ "$status" -eq 0 ]
}

@test "CI workflow: triggers on push and pull_request" {
    [ -f "$WORKFLOW" ]
    grep -q "push:" "$WORKFLOW"
    grep -q "pull_request:" "$WORKFLOW"
}

@test "CI workflow: runs on ubuntu-latest" {
    [ -f "$WORKFLOW" ]
    grep -q "ubuntu-latest" "$WORKFLOW"
}

@test "CI workflow: uses actions/checkout@v4" {
    [ -f "$WORKFLOW" ]
    grep -q "actions/checkout@v4" "$WORKFLOW"
}

@test "CI workflow: installs bats from bats-core" {
    [ -f "$WORKFLOW" ]
    grep -q "bats-core" "$WORKFLOW"
}

@test "CI workflow: runs the bats suite with --jobs parallel" {
    [ -f "$WORKFLOW" ]
    grep -q "bats --jobs" "$WORKFLOW"
    grep -q "tests/scripts" "$WORKFLOW"
}

@test "CI workflow: uploads TAP results as artifact" {
    [ -f "$WORKFLOW" ]
    grep -q "upload-artifact" "$WORKFLOW"
}