# Task 27 Decisions

## Path Handling Strategy
**Decision**: Use `config_path.parent` as base directory for prompt files instead of hardcoded `Path("config")`
**Rationale**: Makes PromptManager more flexible and testable, as it resolves paths relative to the config file location rather than CWD

## DMS Variant Selection Logic
**Decision**: In `get_system_prompt()`, automatically use `dms` variant when RAG context is present (if available)
**Rationale**: Task 27 specifies "If RAG context present → use `dms` variant", so this is the required behavior

## Test Fixture Design
**Decision**: Simplify test fixture to rely on PromptManager's `config_dir` instead of patching `Path`
**Rationale**: Patching `Path` was fragile and only applied during initialization; using `config_dir` is more robust
