import asyncio
import chainlit as cl
import yaml
import json
import logging
from pathlib import Path
from src.core.debate_engine import DebateEngine
from src.tools.doc_parser import DocumentParser
from src.tools.report_generator import ReportGenerator
from src.core.session_db import SessionDB
from src.ui.dashboard import render_dashboard
from src.core.prompt_manager import PromptManager
from src.core.logging_config import setup_logging
from src.ui import dms_dashboard
from src.dms.dms import DMS
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)
setup_logging("INFO")

config_manager = ConfigManager()
PROFILES = config_manager.get_llm_profiles().get("profiles", {})

parser = DocumentParser()


# ── Helpers ──────────────────────────────────────────────────────────────

def _action(name: str, label: str, value: str = "", tooltip: str = "") -> cl.Action:
    """Helper to create a Chainlit 2.x compatible Action."""
    return cl.Action(name=name, label=label, payload={"value": value}, tooltip=tooltip)


def _get_value(action: cl.Action, default: str = "") -> str:
    """Extract value from action.payload (Chainlit 2.x)."""
    if isinstance(action.payload, dict):
        return action.payload.get("value", default)
    return default


def _home_actions() -> list:
    """Standard navigation buttons shown on every message."""
    return [
        _action("go_home", "🏠 Home", "home", "Back to start"),
        _action("open_dash", "📊 Dashboard", "init", "Session Management"),
        _action("open_dms", "📁 DMS", "dms_init", "Document Management"),
        _action("open_config", "⚙️ Config", "config_init", "Configuration"),
    ]


async def _ask(content: str, author: str = "Config", timeout: int = 120) -> str | None:
    """Ask user a question with inline input field. Returns response text or None on timeout/cancel."""
    try:
        logger.info(f"AskUserMessage: sending prompt (author={author})")
        res = await cl.AskUserMessage(
            content=content,
            author=author,
            timeout=timeout,
        ).send()
        logger.info(f"AskUserMessage: got response type={type(res)}, value={res!r}")
        if res is None:
            logger.warning("AskUserMessage returned None (timeout or cancel)")
            return None
        if isinstance(res, dict):
            output = res.get("output", "").strip()
            logger.info(f"AskUserMessage: output='{output}'")
            return output if output else None
        # Handle StepDict-like objects
        output = getattr(res, "output", None)
        if output:
            return str(output).strip()
        logger.warning(f"AskUserMessage: unexpected response format: {res}")
        return None
    except Exception as e:
        logger.warning(f"AskUserMessage failed: {type(e).__name__}: {e}", exc_info=True)
        return None


async def _ask_int(content: str, default: int = 0, author: str = "Config") -> int:
    """Ask for an integer value with inline input field."""
    text = await _ask(content, author=author)
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return default


async def _ask_float(content: str, default: float = 0.0, author: str = "Config") -> float:
    """Ask for a float value with inline input field."""
    text = await _ask(content, author=author)
    if text is None:
        return default
    try:
        return float(text)
    except ValueError:
        return default


# ── Chat Start ───────────────────────────────────────────────────────────

@cl.on_chat_start
async def start():
    try:
        profile_names = list(PROFILES.keys())
        default_profile = profile_names[0] if profile_names else ""

        # Initialize session database
        db = SessionDB()
        cl.user_session.set("session_db", db)
        cl.user_session.set("dash_page", 0)
        cl.user_session.set("dash_filter", False)

        # Initialize prompt manager
        pm = PromptManager()
        variant_opts = list(pm.variants_config.get("variants", {}).keys())

        dms = DMS()
        cl.user_session.set("dms", dms)
        cl.user_session.set("selected_project_id", None)
        cl.user_session.set("selected_document_id", None)

        projects = dms.list_projects()
        project_items = {proj["name"]: proj["id"] for proj in projects} if projects else {"No projects": ""}
        initial_project = None if projects else ""

        cl.user_session.set("prompt_manager", pm)

        # Build agent profile options
        agent_profiles_cfg = config_manager.get_agent_profiles()
        default_agent_profile = config_manager.get_default_agent_profile_name()
        agent_profile_items = {
            f"{name} — {cfg.get('description', '')}": name
            for name, cfg in agent_profiles_cfg.get("profiles", {}).items()
        } if agent_profiles_cfg.get("profiles") else {"No profiles": ""}

        # Single ChatSettings panel
        settings = await cl.ChatSettings(
            [
                cl.input_widget.Select(
                    id="profile",
                    label="LLM Profile",
                    values=profile_names,
                    initial_value=default_profile,
                ),
                cl.input_widget.Select(
                    id="agent_profile",
                    label="🤖 Agent Profile",
                    items=agent_profile_items,
                    initial_value=default_agent_profile,
                ),
                cl.input_widget.Slider(
                    id="max_rounds", label="Max. Rounds", min=1, max=5, step=1, initial=3
                ),
                cl.input_widget.Slider(
                    id="threshold",
                    label="Consensus Threshold",
                    min=0.5,
                    max=1.0,
                    step=0.05,
                    initial=0.75,
                ),
                cl.input_widget.Checkbox(
                    id="enable_fact_check", label="Enable Web Validation", value=True
                ),
                cl.input_widget.Checkbox(
                    id="enable_memory", label="Enable Precedent Memory", value=True
                ),
                cl.input_widget.Select(
                    id="variant",
                    label="Prompt Variant",
                    values=variant_opts + ["auto"],
                    initial_value="auto",
                ),
                cl.input_widget.Select(
                    id="selected_project_id",
                    label="📁 Active Project",
                    items=project_items,
                    initial_value=initial_project,
                ),
            ]
        ).send()

        cl.user_session.set("settings", settings)

        # Welcome message
        await cl.Message(
            content="🤝 **Multi-Agent Debate System** ready.\n\n"
                    "💡 **How to use:**\n"
                    "- **Start a debate:** Type a question or topic in the chat input below.\n"
                    "- **Configure:** Click ⚙️ Config below to add LLM profiles, agent profiles, etc.\n"
                    "- **Documents:** Click 📁 DMS to manage projects and documents.\n"
                    "- **Settings:** Use the ⚙️ gear icon (top-right) for quick settings.\n\n"
                    "All configuration dialogs have **inline input fields** — just type and press Enter.",
            actions=_home_actions(),
            author="System",
        ).send()
        logger.info("Chat started successfully")
    except Exception as e:
        logger.exception("Failed to initialize chat session")
        await cl.Message(
            content=f"❌ **Initialization Error:** {type(e).__name__}: {e}\n\n"
                    "Please reload the page. If this persists, check the logs.",
            author="System",
        ).send()


# ── Message Handler ──────────────────────────────────────────────────────

@cl.on_message
async def main(message: cl.Message):
    settings = cl.user_session.get("settings")
    if not settings:
        await cl.Message(
            content="⚠️ Settings not initialized. Please reload the page.",
            author="System",
            actions=_home_actions(),
        ).send()
        return

    pm = cl.user_session.get("prompt_manager")
    variant = settings["variant"] if settings.get("variant") != "auto" else None
    agent_profile = settings.get("agent_profile")

    try:
        engine = DebateEngine(
            profile_name=settings.get("profile") or None,
            max_rounds=int(settings.get("max_rounds", 3)),
            threshold=float(settings.get("threshold", 0.75)),
            enable_fact_check=settings.get("enable_fact_check", True),
            enable_memory=settings.get("enable_memory", True),
            agent_profile_name=agent_profile if agent_profile else None,
        )
    except KeyError as e:
        available = list(PROFILES.keys())
        await cl.Message(
            content=f"❌ **LLM Profile Error:** Profile `{e}` not found.\n\n"
                    f"Available profiles: {', '.join(f'`{p}`' for p in available) if available else 'none'}\n\n"
                    f"Please select a valid profile in ⚙️ **Chat Settings** (gear icon) or add one via ⚙️ **Config**.",
            author="System",
            actions=_home_actions(),
        ).send()
        return
    except Exception as e:
        logger.exception("Failed to initialize DebateEngine")
        await cl.Message(
            content=f"❌ **Error initializing debate engine:** {type(e).__name__}: {e}",
            author="System",
            actions=_home_actions(),
        ).send()
        return

    context = message.content
    parsed_docs = []

    if message.elements:
        await cl.Message(
            content=f"📄 Processing {len(message.elements)} document(s)...",
            author="System",
        ).send()
        for elem in message.elements:
            try:
                doc = await parser.parse_file(elem.path)
                parsed_docs.append(
                    {"name": elem.name, "text": doc["text"], "metadata": doc["metadata"]}
                )
            except Exception as e:
                logger.warning(f"Failed to parse {elem.name}: {e}")
                await cl.Message(
                    content=f"⚠️ Could not parse `{elem.name}`: {e}",
                    author="System",
                ).send()

    # Build context
    rag_context = cl.user_session.get("rag_context")
    if parsed_docs:
        doc_context = "\n\n".join(
            [
                f"### Document: {d['name']}\n"
                f"Metadata: {json.dumps(d['metadata'], ensure_ascii=False)}\n"
                f"Content:\n{d['text']}"
                for d in parsed_docs
            ]
        )
        if rag_context:
            combined = f"## Parsed Documents\n{doc_context}\n\n## RAG Context\n{rag_context}"
            context += f"\n\n{combined}"
        else:
            context += f"\n\n[Analyzed Documents]\n{doc_context}"
    elif rag_context:
        context += f"\n\n## RAG Context\n{rag_context}"

    async def progress(step: str, detail: str):
        await cl.Message(
            content=f"🔄 {step}: {detail}", author="System", type="info"
        ).send()

    try:
        with cl.Step(name="Debate", type="run") as run_step:
            state = await engine.run(
                context, progress_callback=progress, variant_override=variant
            )
    except Exception as e:
        logger.exception("Debate engine failed")
        await cl.Message(
            content=f"❌ **Debate Error:** {type(e).__name__}: {e}\n\n"
                    "Check that your LLM backend is running and accessible.",
            author="System",
            actions=_home_actions(),
        ).send()
        return

    # Privacy enforcement
    engine.privacy.enforce_retention()

    await cl.Message(
        content="🛡️ Privacy: PII is masked in traces. External calls only for SearXNG & configured LLMs.",
        author="System",
        type="info",
    ).send()

    variant_info = (
        f"`{state.used_variant or variant or 'auto'}`"
        if state.used_variant or variant
        else "`auto`"
    )
    agent_profile_info = f"`{state.used_agent_profile}`" if state.used_agent_profile else "`default`"
    final_msg = (
        f"## Result (Variant: {variant_info}, Agent Profile: {agent_profile_info}, "
        f"Consensus: {state.final_consensus:.2f})\n\n{state.output}"
    )
    await cl.Message(content=final_msg, author="Moderator", actions=_home_actions()).send()

    trace_data = engine.logger.get_session_log()
    elements = [
        cl.Text(
            name="full_trace.json",
            content=json.dumps(trace_data, indent=2, ensure_ascii=False),
            display="inline",
        )
    ]
    await cl.Message(
        content="📄 Full Audit Trace:", elements=elements, author="System"
    ).send()

    gen = ReportGenerator()
    report_path_docx = await gen.generate(state, fmt="docx")
    report_path_pdf = await gen.generate(state, fmt="pdf")

    await cl.Message(
        content="📥 Reports generated:",
        elements=[
            cl.File(
                name=report_path_docx.name, path=str(report_path_docx), display="inline"
            ),
            cl.File(
                name=report_path_pdf.name, path=str(report_path_pdf), display="inline"
            ),
        ],
        author="System",
    ).send()

    # Save session
    trace_path = f"logs/{state.session_id}.jsonl"
    docx_path = str(report_path_docx)
    pdf_path = str(report_path_pdf)

    db = cl.user_session.get("session_db")
    project_id = cl.user_session.get("selected_project_id")
    selected_doc_id = cl.user_session.get("selected_document_id")
    document_ids = [selected_doc_id] if selected_doc_id else []
    db.save_session(
        state,
        settings["profile"],
        trace_path,
        docx_path,
        pdf_path,
        project_id=project_id,
        document_ids=document_ids,
    )


# ── Action Callback Handler ──────────────────────────────────────────────

_DMS_ACTIONS = {
    "create_project", "refresh_projects", "view_documents", "delete_project",
    "upload_document", "back_to_projects", "confirm_delete", "add_to_rag", "remove_from_rag",
}


@cl.action_callback("go_home")
@cl.action_callback("open_dash")
@cl.action_callback("dash_filter")
@cl.action_callback("dash_page")
@cl.action_callback("dash_cleanup")
@cl.action_callback("sess_trace")
@cl.action_callback("sess_delete")
@cl.action_callback("sess_report")
@cl.action_callback("open_dms")
@cl.action_callback("open_config")
@cl.action_callback("config_settings")
@cl.action_callback("config_llm_profiles")
@cl.action_callback("config_prompt_variants")
@cl.action_callback("config_save_settings")
@cl.action_callback("config_add_profile")
@cl.action_callback("config_delete_profile")
@cl.action_callback("config_add_variant")
@cl.action_callback("config_delete_variant")
@cl.action_callback("config_language")
@cl.action_callback("config_agent_profiles")
@cl.action_callback("config_add_agent_profile")
@cl.action_callback("config_delete_agent_profile")
@cl.action_callback("config_edit_agent_profile")
@cl.action_callback("config_set_default_agent_profile")
@cl.action_callback("create_project")
@cl.action_callback("refresh_projects")
@cl.action_callback("view_documents")
@cl.action_callback("delete_project")
@cl.action_callback("upload_document")
@cl.action_callback("back_to_projects")
@cl.action_callback("confirm_delete")
@cl.action_callback("add_to_rag")
@cl.action_callback("remove_from_rag")
async def handle_action(action: cl.Action):
    try:
        db = cl.user_session.get("session_db")
        page = cl.user_session.get("dash_page", 0)
        filt = cl.user_session.get("dash_filter", False)

        name = action.name
        value = _get_value(action)
        logger.info(f"Action triggered: name={name}, value={value!r}")

        # ── Home ──
        if name == "go_home":
            await _render_home()
            return

        # ── DMS actions ──
        if name in _DMS_ACTIONS:
            await dms_dashboard.handle_action(action)
            return

        # ── Dashboard ──
        if name == "open_dash":
            await render_dashboard(db, page, filt)
        elif name == "dash_filter":
            filt = not filt
            cl.user_session.set("dash_filter", filt)
            await render_dashboard(db, 0, filt)
        elif name == "dash_page":
            page = int(value) if value else 0
            cl.user_session.set("dash_page", page)
            await render_dashboard(db, page, filt)
        elif name == "dash_cleanup":
            await cl.Message(content="🔄 Cleanup running...", author="System").send()
            from src.core.privacy import PrivacyGuard
            PrivacyGuard(retention_days=90).enforce_retention()
            deleted_db = db.cleanup_old_entries(days=90)
            await cl.Message(
                content=f"✅ Cleanup complete. {deleted_db} DB entries removed.",
                author="System",
                actions=_home_actions(),
            ).send()
            await render_dashboard(db, 0, filt)

        # ── Session actions ──
        elif name == "sess_trace":
            trace_file = Path("logs") / f"{value}.jsonl"
            if trace_file.exists():
                await cl.Message(
                    content=f"📄 Trace: `{value[:8]}...`",
                    elements=[
                        cl.Text(
                            name=trace_file.name, path=str(trace_file), display="inline"
                        )
                    ],
                    author="Trace",
                    actions=_home_actions(),
                ).send()
            else:
                await cl.Message(content="⚠️ Trace file not found.", actions=_home_actions()).send()

        elif name == "sess_delete":
            sid = value
            db.delete_session(sid)
            Path("logs", f"{sid}.jsonl").unlink(missing_ok=True)
            for f in Path("reports").glob(f"debate_{sid}*"):
                f.unlink(missing_ok=True)
            await cl.Message(
                content=f"✅ Session `{sid[:8]}...` completely deleted.", author="System"
            ).send()
            await render_dashboard(db, page, filt)

        elif name == "sess_report":
            sid = value
            reports = list(Path("reports").glob(f"debate_{sid}*"))
            if reports:
                elements = [
                    cl.File(name=r.name, path=str(r), display="inline") for r in reports
                ]
                await cl.Message(
                    content=f"📥 Reports: `{sid[:8]}...`",
                    elements=elements,
                    author="Export",
                    actions=_home_actions(),
                ).send()
            else:
                await cl.Message(
                    content="⚠️ No report found. Please generate again.",
                    actions=_home_actions(),
                ).send()

        # ── DMS entry ──
        elif name == "open_dms":
            await dms_dashboard.start()

        # ── Configuration ──
        elif name == "open_config":
            await render_config_menu()

        elif name == "config_settings":
            await render_settings_editor()

        elif name == "config_llm_profiles":
            await render_llm_profiles_editor()

        elif name == "config_prompt_variants":
            await render_prompt_variants_editor()

        elif name == "config_save_settings":
            await cl.Message(
                content="⚙️ Please edit `config/settings.yaml` directly for now.",
                author="System",
                actions=_home_actions(),
            ).send()

        elif name == "config_add_profile":
            asyncio.create_task(_flow_add_llm_profile())

        elif name == "config_delete_profile":
            profile_name = value
            if config_manager.delete_llm_profile(profile_name):
                await cl.Message(content=f"✅ Profile '{profile_name}' deleted.", author="System").send()
            else:
                await cl.Message(content=f"❌ Profile '{profile_name}' not found.", author="System").send()
            await render_llm_profiles_editor()

        elif name == "config_add_variant":
            asyncio.create_task(_flow_add_prompt_variant())

        elif name == "config_delete_variant":
            variant_name = value
            if config_manager.delete_prompt_variant(variant_name):
                await cl.Message(content=f"✅ Variant '{variant_name}' deleted.", author="System").send()
            else:
                await cl.Message(content=f"❌ Variant '{variant_name}' not found.", author="System").send()
            await render_prompt_variants_editor()

        elif name == "config_language":
            if value:
                lang_name = ConfigManager.SUPPORTED_LANGUAGES.get(value, value)
                await cl.Message(
                    content=f"🌐 **Language Switch**\n\n"
                            f"Selected: `{value}` ({lang_name})\n\n"
                            f"⚠️ *This feature is not yet implemented.*",
                    author="Config",
                    actions=_home_actions(),
                ).send()
            else:
                await render_language_settings()

        # ── Agent Profile Actions ──
        elif name == "config_agent_profiles":
            await render_agent_profiles_editor()

        elif name == "config_add_agent_profile":
            asyncio.create_task(_flow_add_agent_profile())

        elif name == "config_delete_agent_profile":
            profile_name = value
            if config_manager.delete_agent_profile(profile_name):
                await cl.Message(content=f"✅ Agent profile '{profile_name}' deleted.", author="System").send()
            else:
                await cl.Message(content=f"❌ Agent profile '{profile_name}' not found.", author="System").send()
            await render_agent_profiles_editor()

        elif name == "config_edit_agent_profile":
            asyncio.create_task(_flow_edit_agent_profile(value))

        elif name == "config_set_default_agent_profile":
            if config_manager.set_default_agent_profile(value):
                await cl.Message(content=f"✅ Default agent profile set to '{value}'.", author="System").send()
            else:
                await cl.Message(content=f"❌ Agent profile '{value}' not found.", author="System").send()
            await render_agent_profiles_editor()

        else:
            logger.warning(f"Unhandled action: {name}")
            await cl.Message(
                content=f"⚠️ Unknown action: `{name}`.",
                author="System",
                actions=_home_actions(),
            ).send()

    except Exception as e:
        logger.exception(f"Error handling action '{action.name}': {e}")
        await cl.Message(
            content=f"❌ **Error:** {type(e).__name__}: {e}",
            author="System",
            actions=_home_actions(),
        ).send()


# ── Home ─────────────────────────────────────────────────────────────────

async def _render_home():
    """Render the home/welcome screen."""
    await cl.Message(
        content="🤝 **Multi-Agent Debate System**\n\n"
                "💡 **How to use:**\n"
                "- **Start a debate:** Type a question or topic in the chat input below.\n"
                "- **Configure:** Click ⚙️ Config to add LLM profiles, agent profiles, etc.\n"
                "- **Documents:** Click 📁 DMS to manage projects and documents.\n"
                "- **Settings:** Use the ⚙️ gear icon (top-right) for quick settings.",
        actions=_home_actions(),
        author="System",
    ).send()


# ── Config Flows (using AskUserMessage for inline input fields) ──────────

async def _flow_add_llm_profile():
    """Multi-step flow to add an LLM profile using inline input fields."""
    name = await _ask(
        "## ➕ Add LLM Profile\n\n"
        "**Step 1/5:** Enter profile name (e.g. `my_openai`):"
    )
    if not name:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    model = await _ask(
        f"Profile: `{name}`\n\n"
        "**Step 2/5:** Enter model name (e.g. `gpt-4o`, `qwen2.5-7b`):"
    )
    if not model:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    base_url = await _ask(
        f"Model: `{model}`\n\n"
        "**Step 3/5:** Enter base URL (e.g. `http://localhost:1234/v1`):"
    )
    if not base_url:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    api_key_env = await _ask(
        f"URL: `{base_url}`\n\n"
        "**Step 4/5:** Enter API key env var name (e.g. `OPENAI_API_KEY`), or leave empty for local LLMs:"
    )
    if api_key_env is None:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    temp = await _ask_float(
        "**Step 5/5:** Enter temperature (0.0-1.0, default `0.4`):",
        default=0.4,
    )

    profile_data = {
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env or "",
        "params": {"temperature": temp, "top_p": 0.9, "seed": 42},
    }
    config_manager.add_llm_profile(name, profile_data)
    await cl.Message(
        content=f"✅ Profile `{name}` added successfully!\n\n"
                f"- Model: `{model}`\n- URL: `{base_url}`\n- Temp: `{temp}`",
        author="Config",
        actions=_home_actions(),
    ).send()
    await render_llm_profiles_editor()


async def _flow_add_prompt_variant():
    """Multi-step flow to add a prompt variant."""
    name = await _ask(
        "## ➕ Add Prompt Variant\n\n"
        "**Step 1/5:** Enter variant name (e.g. `C`, `strict`):"
    )
    if not name:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    roles = ["strategist", "critic", "optimizer", "moderator"]
    variant_data = {}
    for i, role in enumerate(roles):
        path = await _ask(
            f"Variant: `{name}`\n\n"
            f"**Step {i+2}/5:** Enter prompt file path for **{role}** (or leave empty to skip):"
        )
        if path is None:
            await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
            return
        if path:
            variant_data[role] = path

    if variant_data:
        config_manager.add_prompt_variant(name, variant_data)
        await cl.Message(
            content=f"✅ Variant `{name}` added with {len(variant_data)} role(s)!",
            author="Config",
            actions=_home_actions(),
        ).send()
    else:
        await cl.Message(content="❌ No roles defined. Cancelled.", author="Config", actions=_home_actions()).send()
    await render_prompt_variants_editor()


async def _flow_add_agent_profile():
    """Multi-step flow to add an agent profile."""
    name = await _ask(
        "## ➕ Add Agent Profile\n\n"
        "**Step 1:** Enter profile name (e.g. `dual_agent`, `chatbot`):"
    )
    if not name:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    description = await _ask(
        f"Profile: `{name}`\n\n"
        "**Step 2:** Enter description (e.g. `2-agent debate`):"
    )
    if description is None:
        await cl.Message(content="❌ Cancelled.", author="Config", actions=_home_actions()).send()
        return

    llm_profiles = config_manager.get_llm_profiles()
    available = ", ".join(llm_profiles.get("profiles", {}).keys()) or "none"

    agents = []
    while True:
        role = await _ask(
            f"Profile: `{name}` ({len(agents)} agents added)\n\n"
            f"**Enter agent role** (e.g. `strategist`, `assistant`)\n"
            f"Available LLMs: `{available}`\n\n"
            f"Type `done` to finish adding agents."
        )
        if role is None or role.lower() == "done":
            break

        llm = await _ask(
            f"Role: `{role}`\n\n"
            f"**Enter LLM profile** for this role (available: `{available}`):"
        )
        if llm is None:
            break

        temp = await _ask_float(
            f"Role: `{role}` → LLM: `{llm}`\n\n"
            f"**Enter temperature** (0.0-1.0, default `0.5`):",
            default=0.5,
        )

        agents.append({
            "role": role,
            "llm_profile": llm,
            "temperature": temp,
        })
        await cl.Message(
            content=f"✅ Agent `{role}` added! ({len(agents)} total)",
            author="Config",
        ).send()

    if agents:
        profile_data = {"description": description or "", "agents": agents}
        config_manager.add_agent_profile(name, profile_data)
        await cl.Message(
            content=f"✅ Agent profile `{name}` created with {len(agents)} agent(s)!",
            author="Config",
            actions=_home_actions(),
        ).send()
    else:
        await cl.Message(content="❌ No agents defined. Cancelled.", author="Config", actions=_home_actions()).send()
    await render_agent_profiles_editor()


async def _flow_edit_agent_profile(profile_name: str):
    """Flow to edit an existing agent profile."""
    profile = config_manager.get_agent_profile(profile_name)
    if not profile:
        await cl.Message(content=f"❌ Agent profile '{profile_name}' not found.", author="System", actions=_home_actions()).send()
        return

    agents = profile.get("agents", [])
    if not agents:
        await cl.Message(content="No agents to edit. Add a new profile instead.", author="System", actions=_home_actions()).send()
        return

    llm_profiles = config_manager.get_llm_profiles()
    available_llms = list(llm_profiles.get("profiles", {}).keys())

    while True:
        # Show current agents
        content = f"✏️ **Edit Agent Profile: {profile_name}**\n\n"
        content += f"Description: {profile.get('description', '')}\n\n"
        content += "**Current agents:**\n"
        for i, agent in enumerate(agents):
            content += f"{i+1}. **{agent['role']}** → LLM: `{agent['llm_profile']}` (temp: {agent.get('temperature', 'default')})\n"
        content += f"\nAvailable LLMs: `{', '.join(available_llms)}`\n\n"
        content += "Enter the **number** of the agent to edit, `new` to add, or `done` to save and finish."

        choice = await _ask(content)
        if choice is None or choice.lower() == "done":
            break

        if choice.lower() == "new":
            role = await _ask("Enter role name for new agent:")
            if not role:
                continue
            llm = await _ask(f"Role: `{role}`\n\nEnter LLM profile (available: `{', '.join(available_llms)}`):")
            if not llm:
                continue
            temp = await _ask_float(f"Enter temperature for `{role}` (0.0-1.0, default `0.5`):", default=0.5)
            agents.append({"role": role, "llm_profile": llm, "temperature": temp})
            await cl.Message(content=f"✅ Agent `{role}` added!", author="Config").send()
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(agents):
                agent = agents[idx]
                new_llm = await _ask(
                    f"Editing **{agent['role']}** (current LLM: `{agent['llm_profile']}`)\n\n"
                    f"Enter new LLM profile (or press Enter to keep current):"
                )
                if new_llm:
                    agent["llm_profile"] = new_llm
                new_temp = await _ask_float(
                    f"Enter new temperature (current: `{agent.get('temperature', 0.5)}`, or press Enter to keep):",
                    default=agent.get("temperature", 0.5),
                )
                agent["temperature"] = new_temp
                await cl.Message(
                    content=f"✅ Updated **{agent['role']}** → LLM: `{agent['llm_profile']}`, temp: `{new_temp}`",
                    author="Config",
                ).send()
            else:
                await cl.Message(content=f"⚠️ Invalid number. Enter 1-{len(agents)}, `new`, or `done`.", author="Config").send()
        except ValueError:
            await cl.Message(content=f"⚠️ Enter a number (1-{len(agents)}), `new`, or `done`.", author="Config").send()

    # Save
    profile_data = {"description": profile.get("description", ""), "agents": agents}
    config_manager.add_agent_profile(profile_name, profile_data)
    await cl.Message(
        content=f"✅ Agent profile `{profile_name}` updated with {len(agents)} agent(s).",
        author="Config",
        actions=_home_actions(),
    ).send()
    await render_agent_profiles_editor()


# ── Config Menu Renderers ────────────────────────────────────────────────

async def render_config_menu():
    actions = [
        _action("config_settings", "🔧 General Settings", "settings", "Search, Privacy, DMS"),
        _action("config_llm_profiles", "🧠 LLM Profiles", "llm", "LLM Endpoints & Params"),
        _action("config_prompt_variants", "📜 Prompt Variants", "prompts", "Prompt Assignments"),
        _action("config_agent_profiles", "🤖 Agent Profiles", "agents", "Configure debating agents & LLM assignments"),
        _action("config_language", "🌐 Language", "language", "UI Language (i18n/l10n)"),
    ] + _home_actions()
    await cl.Message(
        content="## ⚙️ Configuration Menu\nSelect a category:",
        actions=actions,
        author="Config",
    ).send()


async def render_language_settings():
    """Show the current UI language and available options."""
    current_lang = config_manager.get_ui_language()
    lang_name = ConfigManager.SUPPORTED_LANGUAGES.get(current_lang, current_lang)

    content = "## 🌐 UI Language (i18n/l10n)\n\n"
    content += f"**Current language:** `{current_lang}` ({lang_name})\n\n"
    content += "**Available languages:**\n"
    for code, name in ConfigManager.SUPPORTED_LANGUAGES.items():
        marker = " ✅" if code == current_lang else ""
        content += f"- `{code}` — {name}{marker}\n"

    actions = []
    for code, name in ConfigManager.SUPPORTED_LANGUAGES.items():
        if code != current_lang:
            actions.append(
                _action("config_language", f"Switch to {name} ({code})", code, f"Change UI language to {name}")
            )
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_settings_editor():
    settings_data = config_manager.get_settings()
    content = "## 🔧 General Settings\n"
    content += f"```yaml\n{yaml.dump(settings_data, default_flow_style=False, allow_unicode=True)}\n```\n"
    content += "\n*(Edit directly in `config/settings.yaml`)*"

    actions = [
        _action("config_save_settings", "💾 Save (Manual)", "save", "Save changes to YAML"),
    ] + _home_actions()
    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_llm_profiles_editor():
    profiles = config_manager.get_llm_profiles()
    content = "## 🧠 LLM Profiles\n"
    for pname, data in profiles.get("profiles", {}).items():
        content += f"### {pname}\n"
        content += f"- Model: `{data.get('model', 'N/A')}`\n"
        content += f"- URL: `{data.get('base_url', 'N/A')}`\n"
        content += f"- Params: `{data.get('params', {})}`\n\n"

    actions = [
        _action("config_add_profile", "➕ Add Profile", "add", "Create new LLM profile"),
    ]
    for pname in profiles.get("profiles", {}).keys():
        actions.append(_action("config_delete_profile", f"🗑️ Delete: {pname}", pname, f"Delete profile {pname}"))
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_prompt_variants_editor():
    variants = config_manager.get_prompt_variants()
    content = "## 📜 Prompt Variants\n"
    content += f"**Default:** `{variants.get('default_variant', 'N/A')}`\n\n"
    for vname, data in variants.get("variants", {}).items():
        content += f"### {vname}\n"
        for role, path in data.items():
            content += f"- {role}: `{path}`\n"
        content += "\n"

    actions = [
        _action("config_add_variant", "➕ Add Variant", "add", "Create new prompt variant"),
    ]
    for vname in variants.get("variants", {}).keys():
        actions.append(_action("config_delete_variant", f"🗑️ Delete: {vname}", vname, f"Delete variant {vname}"))
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_agent_profiles_editor():
    """Show all agent profiles with their agent->LLM assignments."""
    profiles_cfg = config_manager.get_agent_profiles()
    profiles = profiles_cfg.get("profiles", {})
    default_name = profiles_cfg.get("default", "")

    if not profiles:
        content = "🤖 **Agent Profiles**\n\n📭 No agent profiles configured."
    else:
        content = f"🤖 **Agent Profiles** (Default: `{default_name}`)\n\n"
        for pname, cfg in profiles.items():
            is_default = " ⭐" if pname == default_name else ""
            content += f"### {pname}{is_default}\n"
            content += f"*{cfg.get('description', 'No description')}*\n"
            for agent in cfg.get("agents", []):
                content += f"- **{agent['role']}** → LLM: `{agent['llm_profile']}` (temp: {agent.get('temperature', 'default')})\n"
            content += "\n"

    actions = [
        _action("config_add_agent_profile", "➕ Add Agent Profile", "add", "Create a new agent profile"),
    ]
    for pname in profiles.keys():
        actions.append(_action("config_edit_agent_profile", f"✏️ Edit: {pname}", pname, f"Edit agent profile {pname}"))
        actions.append(_action("config_set_default_agent_profile", f"⭐ Set Default: {pname}", pname, f"Set {pname} as default"))
        actions.append(_action("config_delete_agent_profile", f"🗑️ Delete: {pname}", pname, f"Delete agent profile {pname}"))
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, author="Config").send()


# ── Settings Update Handler ──────────────────────────────────────────────

@cl.on_settings_update
async def on_settings_update(settings):
    # Persist the full settings dict so profile/variant/agent_profile changes take effect
    cl.user_session.set("settings", settings)

    dms = cl.user_session.get("dms")
    selected_project_id = settings.get("selected_project_id")

    cl.user_session.set("selected_project_id", selected_project_id)

    project_name = "No project selected"
    if selected_project_id and dms:
        projects = dms.list_projects()
        project = next((p for p in projects if p["id"] == selected_project_id), None)
        if project:
            project_name = project["name"]

    agent_profile = settings.get("agent_profile", "none")
    profile = settings.get("profile", "default")

    await cl.Message(
        content=f"⚙️ Settings updated: Profile=`{profile}`, Agent=`{agent_profile}`, "
                f"Project=`{project_name}`",
        author="System",
    ).send()
