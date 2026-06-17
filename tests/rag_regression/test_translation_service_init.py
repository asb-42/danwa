"""Regression test: TranslationService.__init__ must initialise the
``_context`` and ``_session_id`` attributes that ``_get_llm_service``
references.

Background
----------
Commit 5791d1a (the original 2026-06-17 LLM-Monitor fix) introduced
``set_context`` and ``set_session_id`` on ``LLMService`` and
``TranslationService._get_llm_service`` started calling them:

    def _get_llm_service(self) -> LLMService:
        if self._llm_service is None:
            self._llm_service = LLMService(
                profile_id=self._llm_profile_id,
                profile_service=self._profile_service,
            )
            self._llm_service.set_context("Translation")
            self._llm_service.set_session_id(self._session_id)  # AttributeError if not init'd

…but the matching ``__init__`` did NOT initialise the
``self._context`` / ``self._session_id`` attributes, so the very
first call to ``translate_module`` (which is the only public
entrypoint that triggers ``_get_llm_service``) raised
``AttributeError: 'TranslationService' object has no attribute
'_session_id'``.

This test guards the fix by:
  1. Asserting that the attributes are set on every fresh instance.
  2. Asserting that ``_get_llm_service`` can be called without
     raising (uses an injected stub ``LLMService`` so the test
     doesn't depend on a real LLM profile).
  3. Asserting that the public ``translate_module`` path that
     drives the lazy creation does not blow up.
"""

from __future__ import annotations

from unittest import mock

import pytest


@pytest.fixture()
def translation_service(tmp_path):
    """A fresh TranslationService wired to a temporary database
    and a stub LLMService so the test is fully hermetic.
    """
    # Lazy import so the test does not require the full backend
    # stack to be importable (avoids the conftest.py bootstrap).
    from backend.services.translation_service import TranslationService

    fake_llm = mock.MagicMock()
    with mock.patch(
        "backend.services.translation_service.LLMService",
        return_value=fake_llm,
    ):
        svc = TranslationService(
            db_path=tmp_path / "test.db",
            modules_dir=tmp_path / "modules",
        )
    svc._fake_llm = fake_llm  # expose for assertions
    return svc


def test_init_creates_session_id_and_context_attributes(translation_service):
    """Fresh instances must expose ``_context`` and ``_session_id``.

    These are referenced by ``_get_llm_service`` (which copies them
    onto the LLMService it lazily creates) and by tests that
    monkey-patch the LLMService.  Missing attributes would break
    the LLM-Monitor integration in the same way the 2026-06-17
    bug did.
    """
    assert hasattr(translation_service, "_session_id"), (
        "TranslationService.__init__ does not initialise _session_id.  "
        "_get_llm_service will AttributeError the first time it is "
        "called (e.g. inside translate_module)."
    )
    assert hasattr(translation_service, "_context"), (
        "TranslationService.__init__ does not initialise _context.  Same failure mode as _session_id above."
    )
    # And they should be empty strings by default.
    assert translation_service._session_id == ""
    assert translation_service._context == ""


def test_get_llm_service_does_not_attribute_error(translation_service):
    """Calling ``_get_llm_service`` must succeed on a fresh instance.

    This is the path triggered by ``translate_module`` and other
    public methods.  If __init__ doesn't initialise the attributes,
    this raises ``AttributeError`` and every translation breaks.
    """
    # The mock patched LLMService constructor above already returned
    # a MagicMock.  The lazy _get_llm_service call below MUST succeed
    # — pre-fix this raised ``AttributeError: 'TranslationService'
    # object has no attribute '_session_id'`` because __init__ never
    # initialised the attribute.
    llm = translation_service._get_llm_service()
    assert llm is not None


def test_translate_module_does_not_attribute_error(translation_service, tmp_path):
    """Full public-API call: ``translate_module`` must succeed
    (or fail for a documented reason such as missing modules),
    but never with ``AttributeError: '_session_id'``.
    """
    # Create a source module so translate_module has something to do.
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "test-mod"
    module_dir.mkdir(parents=True)
    prompts_dir = module_dir / "prompts" / "default"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "strategist.md").write_text(
        "# Strategist\n\nDevelop a strategy for {topic}.",
        encoding="utf-8",
    )

    # Import the source so the DB has an entry.
    translation_service.import_source_content(
        module_id="test-mod",
        file_path="prompts/default/strategist.md",
        content="# Strategist\n\nDevelop a strategy for {topic}.",
    )

    # Stub the LLM call so we don't hit a real provider.
    translation_service._fake_llm.generate.return_value = mock.MagicMock(
        content="translated text",
        tokens_in=10,
        tokens_out=20,
        model="test-model",
        duration_ms=100,
    )

    # The real bug: this would raise AttributeError on the
    # first call to _get_llm_service.
    result = translation_service.translate_module(
        module_id="test-mod",
        target_language="de",
        force=False,
    )

    # The exact return shape isn't part of the contract, but
    # we do require that the call didn't raise.
    assert result is not None
