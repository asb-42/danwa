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


def _action(name: str, label: str, value: str = "", tooltip: str = "") -> cl.Action:
    """Helper to create a Chainlit 2.x compatible Action."""
    return cl.Action(name=name, label=label, payload={"value": value}, tooltip=tooltip)


@cl.on_chat_start
async def start():
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="profile",
                label="LLM Profile",
                values=list(PROFILES.keys()),
                initial_value="local_lm_studio",
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
        ]
    ).send()

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

    selected_project_id = cl.user_session.get("selected_project_id")
    if selected_project_id:
        docs = dms.list_documents(selected_project_id)
        doc_items = {doc["filename"]: doc["id"] for doc in docs} if docs else {}
    else:
        doc_items = {"No document selected": ""}

    cl.user_session.set("settings", settings)
    cl.user_session.set("prompt_manager", pm)

    # Build agent profile options
    agent_profiles_cfg = config_manager.get_agent_profiles()
    agent_profile_names = list(agent_profiles_cfg.get("profiles", {}).keys())
    default_agent_profile = config_manager.get_default_agent_profile_name()
    agent_profile_items = {
        f"{name} — {cfg.get('description', '')}": name
        for name, cfg in agent_profiles_cfg.get("profiles", {}).items()
    } if agent_profiles_cfg.get("profiles") else {"No profiles": ""}

    # Extended settings with variant and agent profile selection
    settings_extended = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="profile",
                label="LLM Profile",
                values=list(PROFILES.keys()),
                initial_value="local_lm_studio",
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
            cl.input_widget.Select(
                id="selected_document_id",
                label="📄 Active Document",
                items=doc_items,
                initial_value="" if not selected_project_id else None,
            ),
        ]
    ).send()

    cl.user_session.set("settings", settings_extended)

    # Welcome message with action buttons
    start_actions = [
        _action("open_dash", "📊 Open Dashboard", "init", "Session Management"),
        _action("open_dms", "📁 DMS Dashboard", "dms_init", "Document Management System"),
        _action("open_config", "⚙️ Configuration", "config_init", "Manage App Configuration"),
    ]
    await cl.Message(
        content="🤝 Multi-Agent Debate System ready.\n\n"
                "💡 **Tip:** Simply enter a question or topic in the chat to start a debate!\n"
                "Use the buttons below for Dashboard, DMS and Configuration.",
        actions=start_actions,
        author="System",
    ).send()


@cl.on_message
async def main(message: cl.Message):
    settings = cl.user_session.get("settings")
    pm = cl.user_session.get("prompt_manager")

    variant = settings["variant"] if settings["variant"] != "auto" else None
    agent_profile = settings.get("agent_profile")

    engine = DebateEngine(
        profile_name=settings["profile"],
        max_rounds=int(settings["max_rounds"]),
        threshold=float(settings["threshold"]),
        enable_fact_check=settings["enable_fact_check"],
        enable_memory=settings["enable_memory"],
        agent_profile_name=agent_profile if agent_profile else None,
    )

    context = message.content
    parsed_docs = []

    if message.elements:
        await cl.Message(
            content=f"📄 Processing {len(message.elements)} document(s)...",
            author="System",
        ).send()
        for elem in message.elements:
            doc = await parser.parse_file(elem.path)
            parsed_docs.append(
                {"name": elem.name, "text": doc["text"], "metadata": doc["metadata"]}
            )

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

    with cl.Step(name="Debate", type="run") as run_step:
        state = await engine.run(
            context, progress_callback=progress, variant_override=variant
        )

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
    await cl.Message(content=final_msg, author="Moderator").send()

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


def _get_value(action: cl.Action, default: str = "") -> str:
    """Extract value from action.payload (Chainlit 2.x) or fall back to action.id."""
    if isinstance(action.payload, dict):
        return action.payload.get("value", default)
    return default


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
    db = cl.user_session.get("session_db")
    page = cl.user_session.get("dash_page", 0)
    filt = cl.user_session.get("dash_filter", False)

    name = action.name
    value = _get_value(action)

    # Route DMS actions to dms_dashboard
    if name in _DMS_ACTIONS:
        await dms_dashboard.handle_action(action)
        return

    # Navigation & Filter
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
        ).send()
        await render_dashboard(db, 0, filt)

    # Session actions
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
            ).send()
        else:
            await cl.Message(content="⚠️ Trace file not found.").send()

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
            ).send()
        else:
            await cl.Message(
                content="⚠️ No report found. Please generate again."
            ).send()

    elif name == "open_dms":
        await dms_dashboard.start()

    # --- Configuration Actions ---
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
            content="⚙️ Settings Update: This feature is under development. Please edit settings.yaml directly for now.",
            author="System",
        ).send()

    elif name == "config_add_profile":
        await add_llm_profile_flow()

    elif name == "config_delete_profile":
        profile_name = value
        if config_manager.delete_llm_profile(profile_name):
            await cl.Message(content=f"✅ Profile '{profile_name}' deleted.", author="System").send()
        else:
            await cl.Message(content=f"❌ Profile '{profile_name}' not found.", author="System").send()
        await render_llm_profiles_editor()

    elif name == "config_add_variant":
        await add_prompt_variant_flow()

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
            ).send()
        else:
            await render_language_settings()

    # --- Agent Profile Actions ---
    elif name == "config_agent_profiles":
        await render_agent_profiles_editor()

    elif name == "config_add_agent_profile":
        await add_agent_profile_flow()

    elif name == "config_delete_agent_profile":
        profile_name = value
        if config_manager.delete_agent_profile(profile_name):
            await cl.Message(content=f"✅ Agent profile '{profile_name}' deleted.", author="System").send()
        else:
            await cl.Message(content=f"❌ Agent profile '{profile_name}' not found.", author="System").send()
        await render_agent_profiles_editor()

    elif name == "config_edit_agent_profile":
        await edit_agent_profile_flow(value)

    elif name == "config_set_default_agent_profile":
        if config_manager.set_default_agent_profile(value):
            await cl.Message(content=f"✅ Default agent profile set to '{value}'.", author="System").send()
        else:
            await cl.Message(content=f"❌ Agent profile '{value}' not found.", author="System").send()
        await render_agent_profiles_editor()


# ── Config Menu Renderers ────────────────────────────────────────────────

async def render_config_menu():
    actions = [
        _action("config_settings", "🔧 General Settings", "settings", "Search, Privacy, DMS"),
        _action("config_llm_profiles", "🧠 LLM Profiles", "llm", "LLM Endpoints & Params"),
        _action("config_prompt_variants", "📜 Prompt Variants", "prompts", "Prompt Assignments"),
        _action("config_agent_profiles", "🤖 Agent Profiles", "agents", "Configure debating agents & LLM assignments"),
        _action("config_language", "🌐 Language", "language", "UI Language (i18n/l10n)"),
    ]
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
    content += "\n*(Select a language to change the UI)*"

    actions = []
    for code, name in ConfigManager.SUPPORTED_LANGUAGES.items():
        if code != current_lang:
            actions.append(
                _action("config_language", f"Switch to {name} ({code})", code, f"Change UI language to {name}")
            )

    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_settings_editor():
    settings_data = config_manager.get_settings()
    content = "## 🔧 General Settings\n"
    content += f"```yaml\n{yaml.dump(settings_data, default_flow_style=False, allow_unicode=True)}\n```\n"
    content += "\n*(Editing directly in config/settings.yaml possible)*"

    actions = [
        _action("config_save_settings", "💾 Save (Manual)", "save", "Save changes to YAML"),
    ]
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

    await cl.Message(content=content, actions=actions, author="Config").send()


# ── Agent Profile Renderers & Flows ──────────────────────────────────────

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

    await cl.Message(content=content, actions=actions, author="Config").send()


async def _ask_user(content: str) -> str:
    """Helper to ask user for input and return the text response."""
    res = await cl.AskUserMessage(content=content).send()
    if not res:
        return ""
    # AskUserMessage.send() returns a StepDict (dict), user response is in 'output'
    if isinstance(res, dict):
        return res.get("output", "").strip()
    # Fallback for older Chainlit versions
    return getattr(res, "content", "").strip()


async def add_agent_profile_flow():
    """Interactive flow to create a new agent profile."""
    name = await _ask_user("Enter agent profile name (e.g. dual_agent):")
    if not name:
        return

    description = await _ask_user("Enter description:")

    # Get available LLM profiles for assignment
    llm_profiles = config_manager.get_llm_profiles()
    available_llms = list(llm_profiles.get("profiles", {}).keys())
    llm_options = ", ".join(available_llms) if available_llms else "none configured"

    agents = []
    while True:
        role = await _ask_user(
            f"Add an agent role (or 'done' to finish).\nAvailable LLMs: {llm_options}\n\nEnter role name (e.g. strategist, critic, proponent):"
        )
        if not role or role.lower() == "done":
            break

        llm_profile = await _ask_user(f"LLM profile for '{role}' ({llm_options}):")
        if not llm_profile:
            llm_profile = available_llms[0] if available_llms else ""

        temp_str = await _ask_user(f"Temperature for '{role}' (0.0-1.0, default 0.5):")
        try:
            temp = float(temp_str) if temp_str else 0.5
        except ValueError:
            temp = 0.5

        agents.append({"role": role, "llm_profile": llm_profile, "temperature": temp})
        await cl.Message(content=f"✅ Added agent: {role} → {llm_profile} (temp: {temp})", author="System").send()

    if agents:
        profile_data = {"description": description, "agents": agents}
        config_manager.add_agent_profile(name, profile_data)
        await cl.Message(content=f"✅ Agent profile '{name}' created with {len(agents)} agent(s).", author="System").send()
    else:
        await cl.Message(content="❌ No agents defined. Cancelled.", author="System").send()

    await render_agent_profiles_editor()


async def edit_agent_profile_flow(profile_name):
    """Interactive flow to edit an existing agent profile."""
    profile = config_manager.get_agent_profile(profile_name)
    if not profile:
        await cl.Message(content=f"❌ Agent profile '{profile_name}' not found.", author="System").send()
        return

    llm_profiles = config_manager.get_llm_profiles()
    available_llms = list(llm_profiles.get("profiles", {}).keys())

    content = f"✏️ **Edit Agent Profile: {profile_name}**\n\n"
    content += f"Current description: {profile.get('description', '')}\n\n"
    content += "**Current agents:**\n"
    for i, agent in enumerate(profile.get("agents", [])):
        content += f"{i+1}. **{agent['role']}** → LLM: `{agent['llm_profile']}` (temp: {agent.get('temperature', 'default')})\n"

    content += f"\nAvailable LLMs: {', '.join(available_llms)}"

    await cl.Message(content=content, author="Config").send()

    # Ask which agent to edit
    agents = profile.get("agents", [])
    if not agents:
        await cl.Message(content="No agents to edit. Add a new profile instead.", author="System").send()
        return

    agent_labels = {str(i+1): a["role"] for i, a in enumerate(agents)}
    agent_labels["new"] = "Add new agent"
    agent_labels["done"] = "Finish editing"

    choice = await _ask_user("Enter the number of the agent to edit, 'new' to add, or 'done' to finish:")
    if not choice or choice.lower() == "done":
        await render_agent_profiles_editor()
        return

    choice = choice.lower()

    if choice == "new":
        role = await _ask_user("Enter role name for new agent:")
        if not role:
            await render_agent_profiles_editor()
            return

        llm_profile = await _ask_user(f"LLM profile for '{role}':")
        if not llm_profile:
            llm_profile = available_llms[0] if available_llms else ""

        temp_str = await _ask_user(f"Temperature for '{role}' (0.0-1.0):")
        try:
            temp = float(temp_str) if temp_str else 0.5
        except ValueError:
            temp = 0.5

        agents.append({"role": role, "llm_profile": llm_profile, "temperature": temp})
        await cl.Message(content=f"✅ Added agent: {role}", author="System").send()

    elif choice in agent_labels:
        idx = int(choice) - 1
        agent = agents[idx]

        new_llm = await _ask_user(f"New LLM for '{agent['role']}' (current: {agent['llm_profile']}):")
        if new_llm:
            agent["llm_profile"] = new_llm

        new_temp = await _ask_user(f"New temperature (current: {agent.get('temperature', 0.5)}):")
        if new_temp:
            try:
                agent["temperature"] = float(new_temp)
            except ValueError:
                pass

        await cl.Message(content=f"✅ Updated agent: {agent['role']}", author="System").send()

    # Save the updated profile
    profile_data = {"description": profile.get("description", ""), "agents": agents}
    config_manager.add_agent_profile(profile_name, profile_data)
    await cl.Message(content=f"✅ Agent profile '{profile_name}' updated.", author="System").send()
    await render_agent_profiles_editor()


async def add_llm_profile_flow():
    name = await _ask_user("Enter profile name:")
    if not name:
        return

    model = await _ask_user("Model name (e.g. qwen2.5-7b):")
    base_url = await _ask_user("Base URL (e.g. http://localhost:1234/v1):")
    api_key_env = await _ask_user("API Key Env Var (e.g. LM_STUDIO_KEY):")

    temp_str = await _ask_user("Temperature (e.g. 0.4):")
    try:
        temp = float(temp_str) if temp_str else 0.4
    except ValueError:
        temp = 0.4

    profile_data = {
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "params": {"temperature": temp, "top_p": 0.9, "seed": 42},
    }

    config_manager.add_llm_profile(name, profile_data)
    await cl.Message(content=f"✅ Profile '{name}' added.", author="System").send()
    await render_llm_profiles_editor()


async def add_prompt_variant_flow():
    name = await _ask_user("Enter variant name (e.g. C):")
    if not name:
        return

    roles = ["strategist", "critic", "optimizer", "moderator"]
    variant_data = {}
    for role in roles:
        path = await _ask_user(f"Prompt file for {role} (e.g. prompts/{role}_v3.md):")
        if path:
            variant_data[role] = path

    if variant_data:
        config_manager.add_prompt_variant(name, variant_data)
        await cl.Message(content=f"✅ Variant '{name}' added.", author="System").send()
    else:
        await cl.Message(content="❌ No roles defined. Cancelled.", author="System").send()

    await render_prompt_variants_editor()


@cl.on_settings_update
async def on_settings_update(settings):
    dms = cl.user_session.get("dms")
    selected_project_id = settings.get("selected_project_id")
    selected_document_id = settings.get("selected_document_id")

    cl.user_session.set("selected_project_id", selected_project_id)
    cl.user_session.set("selected_document_id", selected_document_id)

    project_name = "No project selected"
    doc_name = "No document selected"

    if selected_project_id and dms:
        projects = dms.list_projects()
        project = next((p for p in projects if p["id"] == selected_project_id), None)
        if project:
            project_name = project["name"]
            if selected_document_id:
                docs = dms.list_documents(selected_project_id)
                doc = next((d for d in docs if d["id"] == selected_document_id), None)
                if doc:
                    doc_name = doc["filename"]

    agent_profile = settings.get("agent_profile", "none")

    await cl.Message(
        content=f"📁 Active Project: {project_name} | 📄 Active Document: {doc_name} | 🤖 Agent Profile: {agent_profile}",
        author="System",
    ).send()
