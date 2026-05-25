# Services Layer — tests

# Services Layer — Tests Module Documentation

## Overview

This module contains the unit test suites for three core services/components of the application: the internationalisation (i18n) service, the logging configuration module, and the report generator. The tests verify the correctness, edge‑case handling, and integration behaviour of these components in isolation, relying on pytest fixtures, mocking, and temporary filesystem environments.

The module consists of three test files:

- `test_i18n_service.py` – Tests for `UITranslationService`
- `test_logging_config.py` – Tests for `setup_logging` and `JSONFormatter`
- `test_report_generator.py` – Tests for `ReportGenerator`

Each test file exercises public APIs, fallback logic, error paths, and data integrity constraints of the corresponding source module.

---

## Test Files and Their Focus

### `test_i18n_service.py`

This file validates the **`UITranslationService`** (from `backend.services.ui_translation_service`). The service manages translation key/value pairs with support for multiple locales, fallback chains, namespaces, bulk imports, caching, and coverage reporting.

**Key test groups:**

| Test Class / Group | Purpose |
|-------------------|---------|
| `TestCRUD` | `set_translation`, `get_translation`, `delete_translation` – basic create, read, update, delete. Verifies that updating a key overwrites the previous value and that deleting a missing key returns `False`. |
| `TestFallback` | `resolve()` – fallback from a missing locale to English, then to the key itself. Tests the fallback chain order and that an existing locale is returned directly without fallback. |
| `TestBulkResolve` | `resolve_bulk()` – resolves multiple keys in one call, returns a dictionary. Missing keys fall back as per the resolve rules. |
| `TestNamespace` | Verifies that keys in different namespaces are isolated (e.g., `global` vs. `admin`). |
| `TestBulkImport` | `bulk_import()` – imports a nested dict of locales → keys → translations, returning the count of imported entries. |
| `TestCache` | Tests cache invalidation on updates and the `invalidate_cache()` method. |
| `TestStats` | `get_stats()` – returns a dict of locale → translation count. |
| `TestCoverage` | `get_coverage()` – returns coverage info per locale. |
| `TestConstants` | Validates module‑level constants: `DEFAULT_LOCALES`, `RTL_LOCALES`, `LOCALE_NAMES`, and `PLURAL_TAGS`. |

**Notable patterns:**
- A `svc` fixture creates an isolated SQLite database in a `tmp_path` (Pytest’s built‑in temporary directory). The database file is cleaned up after the test.
- Tests exercise both happy paths and edge cases (missing key, missing locale, empty keys list).

### `test_logging_config.py`

This file tests the **logging configuration** module (`src.core.logging_config`), specifically the `JSONFormatter` and the `setup_logging` function.

| Test | Focus |
|------|-------|
| `test_json_formatter` | Ensures the formatter produces a valid JSON string containing `ts`, `level`, `msg`, and `src` fields. |
| `test_json_formatter_with_exception` | Verifies that when an exception is attached to a log record, the output JSON includes an `exc` field. |
| `test_setup_logging_creates_logs_dir` | Checks that `setup_logging` attempts to create the logs directory (mocked `Path`). |
| `test_setup_logging_sets_level` | Confirms that `setup_logging` passes the given log level to `logging.basicConfig`. |
| `test_setup_logging_configures_litellm_level` | Ensures that the third‑party logger `litellm` is set to a specific level after configuration. |

**Notable patterns:**
- Extensive use of `unittest.mock.patch` to replace filesystem and logging internals.
- The tests verify side effects (function calls) rather than the actual behaviour of the production code, because the production code manipulates global logging state which is hard to assert deterministically.

### `test_report_generator.py`

This file tests the **`ReportGenerator`** (from `src.tools.report_generator`), which produces DOCX and PDF reports from a `DebateState` object.

| Test | Focus |
|------|-------|
| `test_generator_initialization` | The generator creates the output directory if it doesn’t exist. |
| `test_generate_docx` | Calls `generator.generate(state, fmt="docx")` and verifies that the underlying `Document.save()` was called. |
| `test_generate_pdf` | Calls `generate(..., fmt="pdf")` and checks that `HTML.write_pdf()` is invoked. |
| `test_generate_invalid_format` | An unsupported format raises `ValueError`. |
| `test_build_docx_content` | Verifies that `_build_docx` adds headings, paragraphs, and a table, and calls `save()`. |
| `test_build_pdf_content` | Verifies that `_build_pdf` calls `write_pdf()` and produces a valid argument. |
| `test_generate_creates_unique_filenames` | Two consecutive calls produce different output paths (timestamp‑based filenames). |
| `test_docx_includes_validation` | The generated document contains a heading related to facts/validation (matching the validation report data). |
| `test_docx_truncates_long_context` | When the context string exceeds a length limit, the document paragraph includes a `[gekürzt]` marker or is truncated. |

**Notable patterns:**
- The `generator` fixture uses a patched `Path` to control filesystem behaviour.
- `DebateState` is a dataclass (from `src.core.debate_engine`) that holds context, consensus, output, and validation/precedent data.
- Tests are marked `@pytest.mark.asyncio` because the public `generate()` method is async. The internal helper methods (`_build_docx`, `_build_pdf`) are synchronous.
- Mocking is applied at the library level (`python-docx`’s `Document`, and `weasyprint`’s `HTML`) to avoid real file generation and external dependencies.
- The `sample_state` fixture provides a realistic `DebateState` with sample data.

---

## Common Testing Patterns

### Fixtures and Isolation
- Every test file uses Pytest’s `tmp_path` (or a wrapped version) to create temporary directories and files, ensuring no cross‑test state pollution.
- The `svc` fixture in `test_i18n_service.py` creates a new SQLite database per test function.
- The `generator` fixture in `test_report_generator.py` creates a dedicated output directory.

### Mocking Strategy
- **External libraries** (e.g., `python-docx`, `weasyprint`, `Path`, `logging`) are mocked to avoid side effects and speed up tests.
- **Function/class references in the source module** are patched using `unittest.mock.patch`. For example, `setup_logging` tests mock `src.core.logging_config.logging` and `src.core.logging_config.Path`.
- The tests do *not* mock the service’s own internal logic; they test the real implementation of `UITranslationService` methods against a real (temporary) database.

### Async Testing
- `pytest.mark.asyncio` is used for tests that call the async `generate()` method. The event loop is managed by `pytest-asyncio`.

### Parameterisation
- Although not extensively used in the current tests, the i18n tests could be extended with parametrisation for different locales and keys. The existing structure is clean and ready for such expansion.

---

## Interconnections with Source Code

The test module validates the following source modules:

| Test File | Source Module | Dependency Type |
|-----------|---------------|-----------------|
| `test_i18n_service.py` | `backend.services.ui_translation_service` | Direct import & instantiation of `UITranslationService` |
| `test_logging_config.py` | `src.core.logging_config` | Direct import of `setup_logging`, `JSONFormatter` |
| `test_report_generator.py` | `src.tools.report_generator` | Direct import of `ReportGenerator` |
| `test_report_generator.py` | `src.core.debate_engine` | Import of `DebateState` used in test fixtures |

No external runtime services (databases, file systems, network) are required; all tests run completely offline and in memory.

---

## Running the Tests

The tests can be executed with Pytest:

```bash
# Run all service layer tests
pytest tests/test_i18n_service.py tests/test_logging_config.py tests/test_report_generator.py

# Run a specific test class
pytest tests/test_i18n_service.py::TestCache

# Run with verbose output
pytest -v tests/
```

All tests are designed to pass in a standard development environment without special configuration.

---

## Contributing to the Test Suite

When adding new tests or extending existing ones:

- **Use the established fixtures** (`svc`, `generator`, `sample_state`) to keep tests concise.
- **Keep tests independent** – each test should set up its own data and not rely on state left by other tests.
- **Mock aggressively** for external libraries and filesystem operations, but test real internal logic where possible.
- **Follow the naming conventions** – test classes describe the feature (`TestCache`, `TestFallback`), test methods describe the specific behaviour.
- **Add assertions for both positive and negative cases** (e.g., missing key returns `None`, invalid format raises `ValueError`).
- **Use `pytest.mark.asyncio`** for any `async def` test that awaits an async method.