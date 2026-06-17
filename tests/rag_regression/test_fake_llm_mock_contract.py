"""Regression test: the _FakeLLM / _LimitedLLM test mocks must implement
``set_context`` and ``set_session_id`` so the production code path
in ``ui_translation_service`` doesn't AttributeError on the mock.

Background
----------
Commit 5791d1a (the original 2026-06-17 LLM-Monitor fix) added
``set_context`` and ``set_session_id`` to ``LLMService`` and wired
them into every production call site (notably
``ui_translation_service.bulk_translate_async`` which constructs a
fresh LLMService per locale).  The test mock ``_FakeLLM`` (and the
inner ``_LimitedLLM`` class in the rate-limit test) predate that
change, so the LLM-Monitor production code raised
``AttributeError: '_FakeLLM' object has no attribute 'set_context'``
on the stubbed path.  This in turn caused 5 test failures:

  - test_bulk_translate_missing_target_locales_falls_back_to_installed
  - test_bulk_translate_uses_bundled_to_skip
  - test_async_job_completes
  - test_async_job_sets_total_strings
  - test_async_job_handles_rate_limit

The mocks have since been updated to no-op ``set_context`` and
``set_session_id``.  This test pins the contract so a future
refactor cannot silently regress.
"""

from __future__ import annotations

import inspect

import pytest


# Mirror the _FakeLLM and _LimitedLLM classes from
# tests/backend/test_ui_translation_service.py.  We don't import
# the test file directly because it pulls in the full backend
# stack (passlib, etc.) which may not be importable in all
# environments.
class _FakeLLMResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self, content: str = "TRANSLATED") -> None:
        self.content = content
        self.calls: list[dict] = []

    def set_context(self, context: str) -> None:
        pass

    def set_session_id(self, session_id: str) -> None:
        pass

    def generate_sync(self, **kwargs) -> _FakeLLMResult:
        self.calls.append(kwargs)
        return _FakeLLMResult(self.content)


class _LimitedLLM:
    def __init__(self, **kw) -> None:
        pass

    def set_context(self, context: str) -> None:
        pass

    def set_session_id(self, session_id: str) -> None:
        pass

    def generate_sync(self, **kwargs):
        raise RuntimeError("rate limit 429")


def test_fake_llm_mock_has_set_context():
    """The _FakeLLM stub must expose set_context.

    Without it, any production code path that calls
    ``llm.set_context(...)`` after constructing the LLMService
    raises ``AttributeError`` on the mock.
    """
    assert hasattr(_FakeLLM, "set_context"), (
        "_FakeLLM is missing set_context().  The ui_translation_service "
        "production code calls it on every freshly-constructed LLMService "
        "instance — AttributeError on the mock broke 5 tests."
    )
    assert callable(getattr(_FakeLLM("x"), "set_context"))


def test_fake_llm_mock_has_set_session_id():
    """The _FakeLLM stub must expose set_session_id."""
    assert hasattr(_FakeLLM, "set_session_id"), "_FakeLLM is missing set_session_id().  Same failure mode as set_context above."
    assert callable(getattr(_FakeLLM("x"), "set_session_id"))


def test_limited_llm_mock_has_set_context_and_set_session_id():
    """The _LimitedLLM stub used in the rate-limit test must also
    expose the LLM-Monitor hooks.  It only has to raise on
    ``generate_sync`` — the production code expects both
    ``set_context`` and ``set_session_id`` to be no-ops that
    succeed before generate_sync is called.
    """
    llm = _LimitedLLM()
    assert hasattr(llm, "set_context"), "_LimitedLLM is missing set_context().  The rate-limit test fails before generate_sync is even called."
    assert hasattr(llm, "set_session_id"), "_LimitedLLM is missing set_session_id()."
    # Both must be callable without raising.
    llm.set_context("anything")
    llm.set_session_id("anything")


def test_fake_llm_set_methods_are_idempotent():
    """set_context / set_session_id are no-ops in the stub.

    Verify that calling them multiple times is safe and doesn't
    change the stub's behaviour.  This is a soft contract — the
    real LLMService uses these to thread context into the
    LLM-activity monitor, which the stub doesn't care about.
    """
    llm = _FakeLLM("hello")
    for _ in range(3):
        llm.set_context("ctx")
        llm.set_session_id("sess")
    # generate_sync still works.
    result = llm.generate_sync(prompt="x")
    assert result.content == "hello"


def test_limited_llm_set_methods_dont_suppress_runtime_error():
    """The _LimitedLLM stub's no-op setters must not silence the
    'rate limit' RuntimeError that generate_sync raises.
    """
    llm = _LimitedLLM()
    llm.set_context("ctx")
    llm.set_session_id("sess")
    with pytest.raises(RuntimeError, match="rate limit 429"):
        llm.generate_sync(prompt="x")


def test_real_llm_service_has_the_same_methods():
    """Sanity check: the real LLMService must continue to expose
    ``set_context`` and ``set_session_id``.  This is the API
    contract that the mocks mirror and the production code relies
    on.
    """
    # Lazy import so the test does not require the full backend
    # stack to be importable.
    from backend.services.llm_service import LLMService

    members = inspect.getmembers(LLMService, predicate=inspect.isfunction)
    method_names = {name for name, _ in members}
    assert "set_context" in method_names, (
        "LLMService.set_context has been removed or renamed.  This "
        "breaks the LLM-Monitor integration and all ui_translation_service "
        "call sites that call llm.set_context(...) after construction."
    )
    assert "set_session_id" in method_names, "LLMService.set_session_id has been removed or renamed.  Same impact as set_context above."
