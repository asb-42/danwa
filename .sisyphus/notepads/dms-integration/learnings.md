# Task 27 Learnings

## PromptManager Path Handling
- Original PromptManager hardcoded `Path("config")` for prompt file resolution, causing tests to read real files instead of test fixtures
- Fixed by storing `self.config_dir = config_path.parent` in `__init__` and using `self.config_dir / rel_path` instead of `Path("config") / rel_path`

## DMS Variant Support
- Added `dms` variant to `config/prompt_variants.yaml` mapping all roles to `prompts/dms_context.md`
- Modified `get_system_prompt()` to automatically use `dms` variant when RAG context is present (if `dms` variant exists)
- Created `config/prompts/dms_context.md` with DMS-specific prompt instructions

## Test Fixes
- Fixed `_parse_prompt` missing `self` parameter (was already present in actual file, initial read was incorrect)
- Fixed `test_prompt_manager_hot_reload` by using `os.utime()` to force mtime change instead of relying on `time.sleep()`
- Fixed `assign_variant` to use `getattr(self, 'default_variant', 'A')` fallback for uninitialized instances
- Simplified test fixture to properly use `config_dir` from PromptManager instead of patching

## Lint Fixes
- Removed unused imports: `unittest.mock.patch`, `unittest.mock.MagicMock`, `pathlib.Path`, `tempfile`, `time`
