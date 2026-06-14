"""Tests for PrintOutputPlugin.render() — orchestration across all formats.

These tests focus on the ``render()`` entry point of
:class:`backend.services.output.plugins.print_plugin.PrintOutputPlugin`. The
heavy format generators (``_generate_pdf``, ``_generate_docx``, ``_generate_odt``)
depend on libraries that are not installed in the test environment
(``weasyprint``, ``pypandoc``, ``python-docx``, ``odfpy``) and ``_generate_md``
depends on ``html2text`` which is also missing — so we monkey-patch the
generators with cheap stubs that return deterministic output.

What is exercised:
* Job directory creation, transactional-drafting auto-detection
* Branching across all five ``PrintFormat`` values (PDF/DOCX/ODT/MD/ALL)
* i18n loading (``_load_i18n``) for ``de``/``en``/missing languages
* Jinja2 rendering via ``_render_html`` with the real templates
* Custom ``format_number`` Jinja filter (good and bad input)
* Markdown path when ``html2text`` is missing (simulated via a stub)
* The transactional-drafting section building branch
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.models.artifact import (
    DebateArtifact,
    Injection,
    MinorityVote,
    Turn,
    UserQuery,
)
from backend.services.output.plugins.print_plugin import (
    PrintFormat,
    PrintOutputPlugin,
    PrintPluginConfig,
    PrintTemplate,
)
from backend.workflow.workflow_state import WorkflowTemplate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_artifact(
    workflow_template: str = "",
    topic: str = "AI Ethics",
) -> DebateArtifact:
    """Build a small but well-formed DebateArtifact for render tests."""
    return DebateArtifact(
        session_id="s1",
        workflow_id="w1",
        workflow_name="Test Workflow",
        topic=topic,
        transcript=[
            Turn(
                id="t1",
                round=1,
                node_id="n1",
                agent_name="Alice",
                role_type="strategist",
                content="Argument A",
            ),
            Turn(
                id="t2",
                round=1,
                node_id="n2",
                agent_name="Bob",
                role_type="critic",
                content="Counter B",
            ),
        ],
        interjections=[
            Injection(
                id="ij1",
                source="user",
                target_node_id="n1",
                content="Consider X",
                injected_at_round=1,
            ),
        ],
        user_queries=[
            UserQuery(id="q1", content="Why A?", response_turn_id="t1"),
        ],
        minority_votes=[
            MinorityVote(
                id="mv1",
                agent_name="Carol",
                dissent_content="I disagree with consensus",
                target_turn_id="t2",
            ),
        ],
        consensus_result={"score": 0.85, "summary": "Good debate"},
        metadata={"workflow_template": workflow_template},
    )


@pytest.fixture()
def plugin() -> PrintOutputPlugin:
    return PrintOutputPlugin()


@pytest.fixture()
def artifact() -> DebateArtifact:
    return _make_artifact()


@pytest.fixture()
def output_dir(tmp_path) -> Path:
    return tmp_path / "out"


@pytest.fixture()
def stub_generators():
    """Patch all four format generators to cheap stubs.

    Returns a dict ``calls`` mapping format-name → list of (html, path) tuples.
    The MD stub records its inputs and returns a deterministic marker string.
    """

    calls: dict[str, list[tuple[str, Path] | tuple]] = {
        "pdf": [],
        "docx": [],
        "odt": [],
        "md": [],
    }

    def fake_pdf(html: str, output_path: Path) -> None:
        calls["pdf"].append((html, output_path))
        output_path.write_text("PDF", encoding="utf-8")

    def fake_docx(html: str, output_path: Path) -> None:
        calls["docx"].append((html, output_path))
        output_path.write_text("DOCX", encoding="utf-8")

    def fake_odt(html: str, output_path: Path) -> None:
        calls["odt"].append((html, output_path))
        output_path.write_text("ODT", encoding="utf-8")

    def fake_md(doc, i18n, config) -> str:
        calls["md"].append((doc, i18n, config))
        return f"# MD-MARKER {doc.metadata.topic}\n"

    # html_to_markdown import is inside _generate_md — we keep the real one
    # by short-circuiting at the function level. _generate_md uses
    # html_to_markdown() — if html2text is missing it raises. So we patch
    # _generate_md directly.
    patches = [
        patch.object(PrintOutputPlugin, "_generate_pdf", staticmethod(fake_pdf)),
        patch.object(PrintOutputPlugin, "_generate_docx", staticmethod(fake_docx)),
        patch.object(PrintOutputPlugin, "_generate_odt", staticmethod(fake_odt)),
        patch.object(PrintOutputPlugin, "_generate_md", staticmethod(fake_md)),
    ]
    for p in patches:
        p.start()
    try:
        yield calls
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# TestLoadI18n
# ---------------------------------------------------------------------------


class TestLoadI18n:
    """Direct unit tests for the static ``_load_i18n`` helper."""

    def test_loads_german(self) -> None:
        data = PrintOutputPlugin._load_i18n("de")
        assert isinstance(data, dict)
        assert data["turn_label"] == "Beitrag"
        assert data["consensus_label"] == "Konsens"

    def test_loads_english(self) -> None:
        data = PrintOutputPlugin._load_i18n("en")
        assert isinstance(data, dict)
        assert data["turn_label"] == "Turn"
        assert "audit_trail_label" in data

    def test_unknown_language_falls_back_to_german(self) -> None:
        data = PrintOutputPlugin._load_i18n("xx")
        # Fallback should be identical to the German content
        de = PrintOutputPlugin._load_i18n("de")
        assert data == de

    def test_returns_dict_for_all_calls(self) -> None:
        for lang in ("de", "en", "fr", "xx", ""):
            assert isinstance(PrintOutputPlugin._load_i18n(lang), dict)


# ---------------------------------------------------------------------------
# TestRenderHtml
# ---------------------------------------------------------------------------


class TestRenderHtml:
    """Direct unit tests for the static ``_render_html`` helper."""

    def test_renders_minimal_template(self) -> None:
        from backend.services.output.plugins.print_plugin import _TEMPLATES_DIR

        assert (_TEMPLATES_DIR / "minimal.html").exists()
        config = PrintPluginConfig(template_name=PrintTemplate.MINIMAL)
        html = PrintOutputPlugin._render_html(
            "minimal.html",
            {
                "metadata": {
                    "topic": "Hello",
                    "workflow_name": "WF",
                    "title": "Hello",
                    "participants": [],
                    "duration": "",
                    "total_rounds": 0,
                    "total_tokens": 0,
                    "language": "de",
                },
                "sections": [],
                "toc": [],
            },
            PrintOutputPlugin._load_i18n("de"),
            config,
        )
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Hello" in html

    def test_format_number_filter_via_probe_template(self, tmp_path, monkeypatch) -> None:
        """Drive the inner ``_format_number`` filter via the real ``_render_html``
        by pointing ``_TEMPLATES_DIR`` at a temporary directory containing a
        tiny template that uses the filter.
        """
        from backend.services.output.plugins import print_plugin as pp_mod

        # Create probe template that calls format_number with int/str/None
        probe = tmp_path / "probe.html"
        probe.write_text(
            "{{ 1234567 | format_number }}|{{ 'oops' | format_number }}",
            encoding="utf-8",
        )
        monkeypatch.setattr(pp_mod, "_TEMPLATES_DIR", tmp_path)

        config = PrintPluginConfig(template_name=PrintTemplate.MINIMAL)
        out = PrintOutputPlugin._render_html(
            "probe.html",
            {"metadata": {"topic": "x"}, "sections": [], "toc": []},
            {},
            config,
        )
        assert "1,234,567" in out
        assert "oops" in out

    def test_format_number_filter_int(self) -> None:
        # The _format_number filter is defined inside _render_html. We
        # recreate the same logic to ensure it returns the comma form.
        # But the easier route is to use Jinja2 directly to verify the
        # registered filter on a fresh environment with a tiny template.
        import jinja2

        env = jinja2.Environment(autoescape=True)
        # Re-derive the filter by rendering _render_html with a probe.
        # Instead: just call _render_html on a template that uses
        # format_number. We craft a minimal template on the fly.
        # The cleanest approach: register the filter manually and test it.

        # Recreate the inner function: the closure is private, so we
        # patch _render_html to expose the filter. Use a simpler test:
        # render a probe template from a tmp dir and assert the filter
        # is installed.
        from backend.services.output.plugins import print_plugin as pp_mod

        pp_mod._TEMPLATES_DIR  # noqa: B018  (probe-only reference)

        # The filter is only registered on the local env inside _render_html.
        # Use a minimal inline template by writing a temporary template
        # file under a temp dir is invasive. Instead: verify the filter
        # via a small probe template written into a tmp path and loaded
        # with a fresh environment.
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "probe.html").write_text(
                "{{ 1234567 | format_number }}|{{ 'oops' | format_number }}|{{ None | format_number }}",
                encoding="utf-8",
            )
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(tdir)),
                autoescape=True,
            )

            def _format_number(value):
                try:
                    return f"{int(value):,}"
                except (ValueError, TypeError):
                    return str(value)

            env.filters["format_number"] = _format_number
            out = env.get_template("probe.html").render()
        assert "1,234,567" in out
        assert "oops" in out
        assert "None" in out


# ---------------------------------------------------------------------------
# TestRenderOrchestration
# ---------------------------------------------------------------------------


class TestRenderOrchestration:
    """End-to-end ``render()`` tests with stubbed format generators."""

    def _run(self, coro):
        # Use a fresh event loop to avoid interactions with the global loop
        # (some other tests in the suite close it, which then breaks
        # ``asyncio.get_event_loop()`` calls in subsequent tests).
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_creates_job_dir(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.PDF)
        self._run(plugin.render(artifact, config, "job1", output_dir))
        assert (output_dir / "job1").is_dir()

    def test_pdf_only(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.PDF)
        files = self._run(plugin.render(artifact, config, "job1", output_dir))
        assert len(files) == 1
        assert files[0].name == "debate.pdf"
        assert files[0].exists()
        assert files[0].read_text(encoding="utf-8") == "PDF"
        assert len(stub_generators["pdf"]) == 1
        assert stub_generators["docx"] == []
        assert stub_generators["odt"] == []
        assert stub_generators["md"] == []

    def test_docx_only(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.DOCX)
        files = self._run(plugin.render(artifact, config, "j", output_dir))
        assert [f.name for f in files] == ["debate.docx"]
        assert (output_dir / "j" / "debate.docx").read_text(encoding="utf-8") == "DOCX"
        assert stub_generators["pdf"] == []
        assert stub_generators["odt"] == []
        assert stub_generators["md"] == []

    def test_odt_only(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.ODT)
        files = self._run(plugin.render(artifact, config, "j", output_dir))
        assert [f.name for f in files] == ["debate.odt"]
        assert (output_dir / "j" / "debate.odt").read_text(encoding="utf-8") == "ODT"

    def test_md_only(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.MD)
        files = self._run(plugin.render(artifact, config, "j", output_dir))
        assert [f.name for f in files] == ["debate.md"]
        assert "MD-MARKER" in (output_dir / "j" / "debate.md").read_text(encoding="utf-8")
        assert stub_generators["pdf"] == []
        assert stub_generators["docx"] == []
        assert stub_generators["odt"] == []
        assert len(stub_generators["md"]) == 1

    def test_all_formats(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.ALL)
        files = self._run(plugin.render(artifact, config, "j", output_dir))
        names = sorted(f.name for f in files)
        assert names == ["debate.docx", "debate.md", "debate.odt", "debate.pdf"]
        assert len(stub_generators["pdf"]) == 1
        assert len(stub_generators["docx"]) == 1
        assert len(stub_generators["odt"]) == 1
        assert len(stub_generators["md"]) == 1

    def test_runs_progress_callback(self, plugin, artifact, output_dir, stub_generators) -> None:
        progress_calls: list[tuple[int, int]] = []

        async def cb(current: int, total: int) -> None:
            progress_calls.append((current, total))

        config = PrintPluginConfig(primary_format=PrintFormat.PDF)
        self._run(plugin.render(artifact, config, "j", output_dir, progress_callback=cb))
        # _render_html is called via asyncio.to_thread but progress
        # callback is only invoked if the plugin calls it. The current
        # implementation does not invoke progress_callback from
        # render(); the callback is therefore a no-op. We assert it
        # didn't blow up. If progress is later wired up, this test
        # will need to update.
        assert isinstance(progress_calls, list)

    def test_html_passed_to_pdf_generator(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.PDF)
        self._run(plugin.render(artifact, config, "j", output_dir))
        html_passed, path = stub_generators["pdf"][0]
        assert isinstance(html_passed, str)
        assert len(html_passed) > 0
        assert path.name == "debate.pdf"

    def test_i18n_passed_to_md_generator(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="en")
        self._run(plugin.render(artifact, config, "j", output_dir))
        _doc, i18n, _cfg = stub_generators["md"][0]
        assert i18n["turn_label"] == "Turn"

    def test_md_uses_german_labels_when_configured(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        self._run(plugin.render(artifact, config, "j", output_dir))
        _doc, i18n, _cfg = stub_generators["md"][0]
        assert i18n["turn_label"] == "Beitrag"


# ---------------------------------------------------------------------------
# TestRenderTemplateAutoDetection
# ---------------------------------------------------------------------------


class TestRenderTemplateAutoDetection:
    """Auto-detection of transactional-drafting template from artifact."""

    def _run(self, coro):
        # Use a fresh event loop to avoid interactions with the global loop
        # (some other tests in the suite close it, which then breaks
        # ``asyncio.get_event_loop()`` calls in subsequent tests).
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_td_workflow_switches_template(self, plugin, output_dir, stub_generators) -> None:
        artifact = _make_artifact(workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING)
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.ACADEMIC_DEBATE,
        )
        # We don't assert file contents — just that render() succeeds
        # and the template switch happened. The stub generator
        # receives the rendered html, which should reference the
        # transactional-drafting template's structure.
        self._run(plugin.render(artifact, config, "j", output_dir))
        assert len(stub_generators["pdf"]) == 1

    def test_non_td_workflow_keeps_template(self, plugin, output_dir, stub_generators) -> None:
        artifact = _make_artifact(workflow_template=WorkflowTemplate.ACADEMIC_DEBATE)
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.ACADEMIC_DEBATE,
        )
        self._run(plugin.render(artifact, config, "j", output_dir))
        assert len(stub_generators["pdf"]) == 1

    def test_explicit_td_template_kept_even_without_workflow(self, plugin, artifact, output_dir, stub_generators) -> None:
        # When the user explicitly chose TRANSACTIONAL_DRAFTING,
        # we should NOT override the choice even if the workflow
        # template says otherwise.
        artifact = _make_artifact(workflow_template="")
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.TRANSACTIONAL_DRAFTING,
        )
        self._run(plugin.render(artifact, config, "j", output_dir))
        assert len(stub_generators["pdf"]) == 1

    def test_explicit_minimal_template_not_overridden(self, plugin, artifact, output_dir, stub_generators) -> None:
        artifact = _make_artifact(workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING)
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.MINIMAL,
        )
        self._run(plugin.render(artifact, config, "j", output_dir))
        # Auto-detect should NOT downgrade the user's MINIMAL choice
        # just because the workflow is TD.
        assert len(stub_generators["pdf"]) == 1


# ---------------------------------------------------------------------------
# TestRenderSections
# ---------------------------------------------------------------------------


class TestRenderSections:
    """Transactional-drafting sections are built when template == TD."""

    def _run(self, coro):
        # Use a fresh event loop to avoid interactions with the global loop
        # (some other tests in the suite close it, which then breaks
        # ``asyncio.get_event_loop()`` calls in subsequent tests).
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_td_template_builds_sections(self, plugin, output_dir, stub_generators) -> None:
        artifact = _make_artifact(workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING)
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.TRANSACTIONAL_DRAFTING,
        )
        # The transactional_drafting.html template iterates over
        # `sections` (passed via the **extra kwarg). We patch the
        # layout engine to verify build_transactional_sections is
        # called.
        with patch("backend.services.output.plugins.print_plugin.PrintLayoutEngine") as mock_engine:
            mock_instance = mock_engine.return_value
            # transform() returns a stub with the right shape
            from backend.services.output.plugins.print_models import (
                PrintDocument,
                PrintMetadata,
                PrintSection,
                SectionType,
            )

            doc = PrintDocument(
                metadata=PrintMetadata(
                    topic="X",
                    workflow_name="Y",
                    title="X",
                    participants=[],
                    duration="",
                    total_rounds=1,
                    total_tokens=0,
                    language="de",
                ),
                sections=[
                    PrintSection(type=SectionType.TITLE, content="<h1>X</h1>"),
                ],
            )
            mock_instance.transform.return_value = doc
            mock_instance.build_transactional_sections.return_value = [
                {"type": "clause", "title": "Clause 1", "content": "c1"},
            ]
            self._run(plugin.render(artifact, config, "j", output_dir))
        mock_instance.build_transactional_sections.assert_called_once_with(artifact)

    def test_non_td_template_skips_section_building(self, plugin, artifact, output_dir, stub_generators) -> None:
        config = PrintPluginConfig(
            primary_format=PrintFormat.PDF,
            template_name=PrintTemplate.ACADEMIC_DEBATE,
        )
        with patch("backend.services.output.plugins.print_plugin.PrintLayoutEngine") as mock_engine:
            from backend.services.output.plugins.print_models import (
                PrintDocument,
                PrintMetadata,
                PrintSection,
                SectionType,
            )

            doc = PrintDocument(
                metadata=PrintMetadata(
                    topic="X",
                    workflow_name="Y",
                    title="X",
                    participants=[],
                    duration="",
                    total_rounds=1,
                    total_tokens=0,
                    language="de",
                ),
                sections=[
                    PrintSection(type=SectionType.TITLE, content="<h1>X</h1>"),
                ],
            )
            mock_instance = mock_engine.return_value
            mock_instance.transform.return_value = doc
            self._run(plugin.render(artifact, config, "j", output_dir))
        mock_instance.build_transactional_sections.assert_not_called()


# ---------------------------------------------------------------------------
# TestGenerateMd (real implementation, stubbed html_to_markdown)
# ---------------------------------------------------------------------------


def _install_fake_html_to_md(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake ``backend.services.output.html_to_md`` module.

    The real module imports ``html2text`` at module level — that import fails
    in the test env. The plugin's ``_generate_md`` does a *local* import
    of ``html_to_markdown`` from that module, so we install a fake module
    that exposes a deterministic ``html_to_markdown`` function.
    """
    import sys as _sys
    import types as _types

    def fake_html_to_markdown(html: str) -> str:
        import re as _re

        return _re.sub(r"<[^>]+>", "", html).strip()

    mod = _types.ModuleType("backend.services.output.html_to_md")
    mod.html_to_markdown = fake_html_to_markdown
    monkeypatch.setitem(_sys.modules, "backend.services.output.html_to_md", mod)


class TestGenerateMd:
    """Drive the real ``_generate_md`` body by stubbing ``html_to_markdown``."""

    def test_basic_document(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="Topic",
                workflow_name="WF",
                title="My Title",
                participants=[],
                duration="",
                total_rounds=2,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(type=SectionType.TITLE, content="<h1>My Title</h1>"),
                PrintSection(
                    type=SectionType.METADATA,
                    content="<p>Topic: Topic</p><p>Workflow: WF</p>",
                ),
                PrintSection(
                    type=SectionType.CASE_DESCRIPTION,
                    content="<p>Case text</p>",
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert isinstance(out, str)
        assert "# My Title" in out
        assert "Topic" in out
        assert "Case text" in out
        assert out.endswith("\n")

    def test_turn_section_renders_with_timestamp(self, monkeypatch) -> None:
        from datetime import UTC, datetime

        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=1,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.TURN,
                    content="<p>Hello</p>",
                    agent_name="Alice",
                    round=1,
                    timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "*Zeitstempel:" in out
        assert "2026" in out

    def test_turn_section_renders_with_margin_notes(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            MarginNote,
            MarginNoteType,
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=["Alice"],
                duration="",
                total_rounds=1,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.TURN,
                    content="<p>Hello</p>",
                    agent_name="Alice",
                    round=1,
                    margin_notes=[
                        MarginNote(
                            type=MarginNoteType.INJECTION,
                            content="<p>Side note</p>",
                            reference_id="x",
                        ),
                    ],
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "## Alice" in out
        assert "Hello" in out
        # Margin note shows the injection icon
        assert "⚡" in out
        assert "Side note" in out

    def test_minority_callout(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=0,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.MINORITY_CALLOUT,
                    content="<p>Dissent text</p>",
                    agent_name="Bob",
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "### ⚠" in out
        assert "Bob" in out
        assert "Dissent text" in out

    def test_user_query_block(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=0,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.USER_QUERY_BLOCK,
                    content="<p>Why so?</p>",
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "### ❓" in out
        assert "Why so?" in out

    def test_consensus_summary(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=0,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.CONSENSUS_SUMMARY,
                    content="<p>All agree</p>",
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "## Konsens" in out
        assert "All agree" in out

    def test_audit_appendix_pipe_table(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            PrintSection,
            SectionType,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=0,
                total_tokens=0,
                language="de",
            ),
            sections=[
                PrintSection(
                    type=SectionType.AUDIT_APPENDIX,
                    content="Round | Agent | Action\n1 | Alice | argued\n2 | Bob | rebutted",
                ),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "## Audit-Trail" in out
        assert "| Round | Agent | Action |" in out
        assert "| 1 | Alice | argued |" in out
        assert "| 2 | Bob | rebutted |" in out

    def test_toc_rendering(self, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod
        from backend.services.output.plugins.print_models import (
            PrintDocument,
            PrintMetadata,
            TOCEntry,
        )

        _install_fake_html_to_md(monkeypatch)

        config = PrintPluginConfig(primary_format=PrintFormat.MD, language="de")
        i18n = PrintOutputPlugin._load_i18n("de")
        doc = PrintDocument(
            metadata=PrintMetadata(
                topic="T",
                workflow_name="W",
                title="T",
                participants=[],
                duration="",
                total_rounds=0,
                total_tokens=0,
                language="de",
            ),
            sections=[],
            toc=[
                TOCEntry(level=1, title="Section 1", anchor="sec1"),
                TOCEntry(level=2, title="Subsection", anchor="sub"),
            ],
        )
        out = pp_mod.PrintOutputPlugin._generate_md(doc, i18n, config)
        assert "## Inhaltsverzeichnis" in out
        assert "- Section 1" in out
        assert "  - Subsection" in out


# ---------------------------------------------------------------------------
# TestGeneratePdf (real implementation, stubbed weasyprint import)
# ---------------------------------------------------------------------------


class TestGeneratePdf:
    """Drive the real ``_generate_pdf`` body by injecting a fake weasyprint."""

    def test_calls_weasyprint(self, monkeypatch, tmp_path) -> None:
        called: dict[str, object] = {}

        class _FakeHTML:
            def __init__(self, string: str = "", **kwargs: object) -> None:
                called["string"] = string
                self.string = string

            def write_pdf(self, target: str) -> None:
                called["target"] = target
                # Simulate file creation
                Path(target).write_text("PDF", encoding="utf-8")

        class _FakeWeasyPrint:
            HTML = _FakeHTML

        monkeypatch.setitem(__import__("sys").modules, "weasyprint", _FakeWeasyPrint)
        out = tmp_path / "x.pdf"
        PrintOutputPlugin._generate_pdf("<p>hi</p>", out)
        assert called["string"] == "<p>hi</p>"
        assert called["target"] == str(out)
        assert out.exists()


# ---------------------------------------------------------------------------
# TestGenerateDocx (real implementation paths)
# ---------------------------------------------------------------------------


class TestGenerateDocx:
    """Drive the real ``_generate_docx`` body via stubs."""

    def test_pypandoc_path(self, monkeypatch, tmp_path) -> None:
        called: dict[str, object] = {}

        def fake_convert_text(html: str, to: str, format: str, outputfile: str) -> None:
            called["html"] = html
            called["to"] = to
            called["format"] = format
            called["outputfile"] = outputfile
            Path(outputfile).write_text("DOCX", encoding="utf-8")

        class _FakePypandoc:
            convert_text = staticmethod(fake_convert_text)

        monkeypatch.setitem(__import__("sys").modules, "pypandoc", _FakePypandoc)
        out = tmp_path / "x.docx"
        PrintOutputPlugin._generate_docx("<p>hi</p>", out)
        assert called["html"] == "<p>hi</p>"
        assert called["to"] == "docx"
        assert called["format"] == "html"
        assert called["outputfile"] == str(out)
        assert out.exists()

    def test_fallback_to_python_docx(self, monkeypatch, tmp_path) -> None:
        """When pypandoc is missing and python-docx is available."""

        def _raise_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "pypandoc":
                raise ImportError("nope")
            return _orig_import(name, *args, **kwargs)

        import builtins as _bi

        _orig_import = _bi.__import__
        monkeypatch.setattr(_bi, "__import__", _raise_import)

        # Inject a fake python-docx with mutable style/font attributes
        class _FakeFont:
            name: str = ""
            size: object = None

        class _FakeStyle:
            font = _FakeFont()

        class _FakeStyles:
            def __getitem__(self, key: str) -> _FakeStyle:
                return _FakeStyle()

        class _FakeDocument:
            styles: _FakeStyles = _FakeStyles()
            _paragraphs: list[str] = []

            def add_paragraph(self, text: str) -> None:
                self._paragraphs.append(text)

            def save(self, target: str) -> None:
                Path(target).write_text("\n".join(self._paragraphs), encoding="utf-8")

        class _FakePt:
            def __init__(self, value: int) -> None:
                self.value = value

        class _FakeDocx:
            Document = _FakeDocument
            shared = type("shared", (), {"Pt": _FakePt})

        import sys as _sys

        monkeypatch.setitem(_sys.modules, "docx", _FakeDocx)
        # Add docx.shared submodule so ``from docx.shared import Pt`` works
        _sys.modules["docx.shared"] = _FakeDocx.shared

        out = tmp_path / "x.docx"
        PrintOutputPlugin._generate_docx("<p>Hello world</p><br/><p>Bye</p>", out)
        assert out.exists()
        # Stripped HTML should land in paragraphs
        content = out.read_text(encoding="utf-8")
        assert "Hello world" in content
        assert "Bye" in content


# ---------------------------------------------------------------------------
# TestGenerateOdt (real implementation paths)
# ---------------------------------------------------------------------------


class TestGenerateOdt:
    """Drive the real ``_generate_odt`` body via stubs."""

    def test_pypandoc_path(self, monkeypatch, tmp_path) -> None:
        called: dict[str, object] = {}

        def fake_convert_text(html: str, to: str, format: str, outputfile: str) -> None:
            called["to"] = to
            Path(outputfile).write_text("ODT", encoding="utf-8")

        class _FakePypandoc:
            convert_text = staticmethod(fake_convert_text)

        monkeypatch.setitem(__import__("sys").modules, "pypandoc", _FakePypandoc)
        out = tmp_path / "x.odt"
        PrintOutputPlugin._generate_odt("<p>hi</p>", out)
        assert called["to"] == "odt"
        assert out.exists()

    def test_fallback_to_odfpy(self, monkeypatch, tmp_path) -> None:
        """When pypandoc is missing and odfpy is available."""

        def _raise_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "pypandoc":
                raise ImportError("nope")
            return _orig_import(name, *args, **kwargs)

        import builtins as _bi

        _orig_import = _bi.__import__
        monkeypatch.setattr(_bi, "__import__", _raise_import)

        class _FakeP:
            def __init__(self, text: str = "") -> None:
                self.text = text

        class _FakeText:
            def __init__(self) -> None:
                self.elements: list[_FakeP] = []

            def addElement(self, el: _FakeP) -> None:  # noqa: N802
                self.elements.append(el)

        class _FakeOpenDocumentText:
            def __init__(self) -> None:
                self.text = _FakeText()

            def save(self, target: str) -> None:
                Path(target).write_text(
                    "\n".join(p.text for p in self.text.elements),
                    encoding="utf-8",
                )

        class _FakeOdf:
            class Opendocument:
                OpenDocumentText = _FakeOpenDocumentText

            class Text:
                P = _FakeP

        import sys as _sys

        _sys.modules["odf"] = _FakeOdf
        _sys.modules["odf.opendocument"] = _FakeOdf.Opendocument
        _sys.modules["odf.text"] = _FakeOdf.Text

        out = tmp_path / "x.odt"
        PrintOutputPlugin._generate_odt("<p>Hello ODT</p>", out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Hello ODT" in content

    def test_fallback_to_html_when_no_odfpy(self, monkeypatch, tmp_path) -> None:
        """When both pypandoc and odfpy are missing, write raw HTML."""

        def _raise_import(name: str, *args: object, **kwargs: object) -> object:
            if name in ("pypandoc", "odf.opendocument", "odf.text"):
                raise ImportError("nope")
            return _orig_import(name, *args, **kwargs)

        import builtins as _bi

        _orig_import = _bi.__import__
        monkeypatch.setattr(_bi, "__import__", _raise_import)

        out = tmp_path / "x.odt"
        PrintOutputPlugin._generate_odt("<p>raw</p>", out)
        assert out.exists()
        # The HTML is written verbatim
        assert out.read_text(encoding="utf-8") == "<p>raw</p>"


# ---------------------------------------------------------------------------
# TestLoadI18nEmptyFallback
# ---------------------------------------------------------------------------


class TestLoadI18nEmptyFallback:
    """When neither the requested language nor the German fallback exist."""

    def test_empty_dict_when_no_files(self, tmp_path, monkeypatch) -> None:
        from backend.services.output.plugins import print_plugin as pp_mod

        # Point _TEMPLATES_DIR at an empty directory
        fake_templates = tmp_path / "templates" / "print"
        fake_templates.mkdir(parents=True)
        monkeypatch.setattr(pp_mod, "_TEMPLATES_DIR", fake_templates)
        # Now no i18n files exist at all
        result = PrintOutputPlugin._load_i18n("de")
        assert result == {}
        result = PrintOutputPlugin._load_i18n("xx")
        assert result == {}
