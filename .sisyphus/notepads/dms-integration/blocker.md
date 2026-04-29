# Blocker: Subagent LLM Misconfiguration

## Issue
- Sisyphus-Junior subagents (spawned via `category`) are trying to use "GPT 5.4 Mini" which is unavailable
- Available LLM: `hy3-preview-free` (opencode/hy3-preview-free)
- Subagents time out after 1800000ms (30 minutes) trying to call unavailable LLM APIs

## Affected Tasks
- **F3: Real Manual QA** - Requires playwright/browser automation (subagent-dependent)
- **F4: Scope Fidelity Check fix** - Requires fixing hardcoded path in `vector_store.py`

## Workaround Attempts
1. Tried `category="unspecified-high"` with explicit "Do NOT use external LLM" instructions - FAILED (timeout)
2. Tried `category="quick"` with minimal prompt - FAILED (timeout)
3. Tried `category="deep"` with local-only tools instruction - FAILED (timeout)
4. Tried resuming sessions with `session_id` - FAILED (timeout)

## Next Steps
- Try `subagent_type="build"` which might have different LLM configuration
- If that fails, document and present status to user
- User may need to fix subagent configuration system-wide

## Status as of 2026-04-29
- F1: COMPLETE (marked in plan)
- F2: COMPLETE (marked in plan)
- F3: BLOCKED (subagent misconfiguration + requires browser automation)
- F4: BLOCKED (subagent misconfiguration prevents fix)
