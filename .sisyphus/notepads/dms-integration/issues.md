# Task 27 Issues

## Initial Test Failures (Fixed)
1. `test_prompt_manager_get`: Read real `config/prompts/strategist.md` which has no `version:` line, returning `unversioned`
   - Fix: Updated PromptManager to use `config_dir` instead of hardcoded `Path("config")`

2. `test_prompt_manager_get_variant_b`: `strategist_v2.md` not created in test fixture
   - Fix: Added `strategist_v2.md` and `moderator_v2.md` creation in fixture

3. `test_prompt_manager_hot_reload`: `time.sleep(0.1)` not sufficient for mtime change
   - Fix: Use `os.utime()` to explicitly set mtime

4. `test_assign_variant_no_variants`: `default_variant` not set on uninitialized PromptManager
   - Fix: Added `getattr(self, 'default_variant', 'A')` fallback in `assign_variant()`
