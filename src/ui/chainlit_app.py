import chainlit as cl
import yaml
import json
import os
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


@cl.on_chat_start
async def start():
    settings = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="profile",
                label="LLM-Profil",
                values=list(PROFILES.keys()),
                initial_value="local_lm_studio",
            ),
            cl.input_widget.Slider(
                id="max_rounds", label="Max. Runden", min=1, max=5, step=1, initial=3
            ),
            cl.input_widget.Slider(
                id="threshold",
                label="Konsens-Schwelle",
                min=0.5,
                max=1.0,
                step=0.05,
                initial=0.75,
            ),
            cl.input_widget.Checkbox(
                id="enable_fact_check", label="Web-Validierung aktivieren", value=True
            ),
            cl.input_widget.Checkbox(
                id="enable_memory", label="Präzedenz-Speicher aktivieren", value=True
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
    project_items = {proj["name"]: proj["id"] for proj in projects} if projects else {"Keine Projekte": ""}
    initial_project = None if projects else ""

    selected_project_id = cl.user_session.get("selected_project_id")
    if selected_project_id:
        docs = dms.list_documents(selected_project_id)
        doc_items = {doc["filename"]: doc["id"] for doc in docs} if docs else {}
    else:
        doc_items = {"Kein Dokument ausgewählt": ""}

    cl.user_session.set("settings", settings)
    cl.user_session.set("prompt_manager", pm)

    # Extended settings with variant selection
    settings_extended = await cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="profile",
                label="LLM-Profil",
                values=list(PROFILES.keys()),
                initial_value="local_lm_studio",
            ),
            cl.input_widget.Slider(
                id="max_rounds", label="Max. Runden", min=1, max=5, step=1, initial=3
            ),
            cl.input_widget.Slider(
                id="threshold",
                label="Konsens-Schwelle",
                min=0.5,
                max=1.0,
                step=0.05,
                initial=0.75,
            ),
            cl.input_widget.Checkbox(
                id="enable_fact_check", label="Web-Validierung aktivieren", value=True
            ),
            cl.input_widget.Checkbox(
                id="enable_memory", label="Präzedenz-Speicher aktivieren", value=True
            ),
            cl.input_widget.Select(
                id="variant",
                label="Prompt-Variante",
                values=variant_opts + ["auto"],
                initial_value="auto",
            ),
            cl.input_widget.Select(
                id="selected_project_id",
                label="📁 Aktives Projekt",
                items=project_items,
                initial_value=initial_project,
            ),
            cl.input_widget.Select(
                id="selected_document_id",
                label="📄 Aktives Dokument",
                items=doc_items,
                initial_value="" if not selected_project_id else None,
            ),
        ]
    ).send()

    cl.user_session.set("settings", settings_extended)

    # Dashboard-Trigger hinzufügen
    start_actions = [
        cl.Action(
            name="open_dash",
            label="📊 Dashboard öffnen",
            value="init",
            description="Sitzungsverwaltung",
            payload={},
        ),
        cl.Action(
            name="open_dms",
            label="📁 DMS Dashboard",
            value="dms_init",
            description="Document Management System",
            payload={},
        ),
        cl.Action(
            name="open_config",
            label="⚙️ Konfiguration",
            value="config_init",
            description="App-Konfiguration verwalten",
            payload={},
        )
    ]
    await cl.Message(
        content="🤝 Multi-Agent Debatten-System bereit.",
        actions=start_actions,
        author="System",
    ).send()


@cl.on_message
async def main(message: cl.Message):
    settings = cl.user_session.get("settings")
    pm = cl.user_session.get("prompt_manager")
    # Optional: UI-seitiger Config-Reload-Trigger (Manager cached eh mtime)
    # pm._load_config()  # Uncomment if you want to force reload on each message

    variant = settings["variant"] if settings["variant"] != "auto" else None

    engine = DebateEngine(
        profile_name=settings["profile"],
        max_rounds=int(settings["max_rounds"]),
        threshold=float(settings["threshold"]),
        enable_fact_check=settings["enable_fact_check"],
        enable_memory=settings["enable_memory"],
    )

    context = message.content
    parsed_docs = []

    if message.elements:
        await cl.Message(
            content=f"📄 Verarbeite {len(message.elements)} Dokument(e)...",
            author="System",
        ).send()
        for elem in message.elements:
            doc = await parser.parse_file(elem.path)
            parsed_docs.append(
                {"name": elem.name, "text": doc["text"], "metadata": doc["metadata"]}
            )

    # Kontext zusammenbauen
    rag_context = cl.user_session.get("rag_context")
    if parsed_docs:
        doc_context = "\n\n".join(
            [
                f"### Dokument: {d['name']}\n"
                f"Metadaten: {json.dumps(d['metadata'], ensure_ascii=False)}\n"
                f"Inhalt:\n{d['text']}"
                for d in parsed_docs
            ]
        )
        if rag_context:
            combined = f"## Parsed Documents\n{doc_context}\n\n## RAG Context\n{rag_context}"
            context += f"\n\n{combined}"
        else:
            context += f"\n\n[Analysierte Dokumente]\n{doc_context}"
    elif rag_context:
        context += f"\n\n## RAG Context\n{rag_context}"



    async def progress(step: str, detail: str):
        await cl.Message(
            content=f"🔄 {step}: {detail}", author="System", type="info"
        ).send()

    with cl.Step(name="Debatte", type="run") as run_step:
        state = await engine.run(
            context, progress_callback=progress, variant_override=variant
        )

    # Privacy enforcement: Apply retention policy before new session
    engine.privacy.enforce_retention()

    # Optional: Privacy-Hinweis im UI
    await cl.Message(
        content="🛡️ Datenschutz: PII wird in Traces maskiert. Externe Calls nur für SearXNG & konfigurierte LLMs.",
        author="System",
        type="info",
    ).send()

    # Füge Variante zur Ausgabe hinzu:
    variant_info = (
        f"`{state.used_variant or variant or 'auto'}`"
        if state.used_variant or variant
        else "`auto`"
    )
    final_msg = f"## Ergebnis (Variante: {variant_info}, Konsens: {state.final_consensus:.2f})\n\n{state.output}"
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
        content="📄 Vollständiger Audit-Trace:", elements=elements, author="System"
    ).send()

    gen = ReportGenerator()
    report_path_docx = await gen.generate(state, fmt="docx")
    report_path_pdf = await gen.generate(state, fmt="pdf")

    await cl.Message(
        content="📥 Reports generiert:",
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

    # Session-Speicherung nach Debatte
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
        document_ids=document_ids
    )


# DMS action names that should be routed to dms_dashboard.handle_action
_DMS_ACTIONS = {
    "create_project", "refresh_projects", "view_documents", "delete_project",
    "upload_document", "back_to_projects", "confirm_delete", "add_to_rag", "remove_from_rag",
}

# Config action names
_CONFIG_ACTIONS = {
    "open_config", "config_settings", "config_llm_profiles", "config_prompt_variants",
    "config_save_settings", "config_add_profile", "config_delete_profile",
    "config_add_variant", "config_delete_variant",
}


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

    action_name = action.name or action.id

    # Route DMS actions to dms_dashboard
    if action_name in _DMS_ACTIONS:
        await dms_dashboard.handle_action(action)
        return

    # Navigation & Filter
    if action_name == "open_dash":
        await render_dashboard(db, page, filt)
    elif action_name == "dash_filter":
        filt = not filt
        cl.user_session.set("dash_filter", filt)
        await render_dashboard(db, 0, filt)
    elif action_name == "dash_page":
        page = int(action.value)
        cl.user_session.set("dash_page", page)
        await render_dashboard(db, page, filt)
    elif action_name == "dash_cleanup":
        await cl.Message(content="🔄 Bereinigung läuft...", author="System").send()
        from src.core.privacy import PrivacyGuard

        PrivacyGuard(retention_days=90).enforce_retention()
        deleted_db = db.cleanup_old_entries(days=90)
        await cl.Message(
            content=f"✅ Bereinigung abgeschlossen. {deleted_db} DB-Einträge entfernt.",
            author="System",
        ).send()
        await render_dashboard(db, 0, filt)

    # Session-Aktionen
    elif action_name == "sess_trace":
        trace_file = Path("logs") / f"{action.value}.jsonl"
        if trace_file.exists():
            await cl.Message(
                content=f"📄 Trace: `{action.value[:8]}...`",
                elements=[
                    cl.Text(
                        name=trace_file.name, path=str(trace_file), display="inline"
                    )
                ],
                author="Trace",
            ).send()
        else:
            await cl.Message(content=f"⚠️ Trace-Datei nicht gefunden.").send()

    elif action_name == "sess_delete":
        sid = action.value
        db.delete_session(sid)
        # Dateien löschen
        Path("logs", f"{sid}.jsonl").unlink(missing_ok=True)
        for f in Path("reports").glob(f"debate_{sid}*"):
            f.unlink(missing_ok=True)
        await cl.Message(
            content=f"✅ Session `{sid[:8]}...` vollständig gelöscht.", author="System"
        ).send()
        await render_dashboard(db, page, filt)

    elif action_name == "sess_report":
        sid = action.value
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
                content=f"⚠️ Kein Report gefunden. Bitte erneut generieren."
            ).send()

    elif action_name == "open_dms":
        await dms_dashboard.start()

    # --- Configuration Actions ---
    elif action_name == "open_config":
        await render_config_menu()

    elif action_name == "config_settings":
        await render_settings_editor()

    elif action_name == "config_llm_profiles":
        await render_llm_profiles_editor()

    elif action_name == "config_prompt_variants":
        await render_prompt_variants_editor()

    elif action_name == "config_save_settings":
        await cl.Message(content="⚙️ Settings Update: This feature is under development. Please edit settings.yaml directly for now.", author="System").send()

    elif action_name == "config_add_profile":
        await add_llm_profile_flow()

    elif action_name == "config_delete_profile":
        profile_name = action.value
        if config_manager.delete_llm_profile(profile_name):
            await cl.Message(content=f"✅ Profil '{profile_name}' gelöscht.", author="System").send()
        else:
            await cl.Message(content=f"❌ Profil '{profile_name}' nicht gefunden.", author="System").send()
        await render_llm_profiles_editor()

    elif action_name == "config_add_variant":
        await add_prompt_variant_flow()

    elif action_name == "config_delete_variant":
        variant_name = action.value
        if config_manager.delete_prompt_variant(variant_name):
            await cl.Message(content=f"✅ Variante '{variant_name}' gelöscht.", author="System").send()
        else:
            await cl.Message(content=f"❌ Variante '{variant_name}' nicht gefunden.", author="System").send()
        await render_prompt_variants_editor()


async def render_config_menu():
    actions = [
        cl.Action(id="config_settings", label="🔧 Allgemeine Einstellungen", value="settings", description="Search, Privacy, DMS"),
        cl.Action(id="config_llm_profiles", label="🧠 LLM Profile", value="llm", description="LLM Endpoints & Params"),
        cl.Action(id="config_prompt_variants", label="📜 Prompt Varianten", value="prompts", description="Prompt Zuweisungen"),
    ]
    await cl.Message(content="## ⚙️ Konfigurationsmenü\nWähle einen Bereich:", actions=actions, author="Config").send()


async def render_settings_editor():
    settings = config_manager.get_settings()
    content = "## 🔧 Allgemeine Einstellungen\n"
    content += f"```yaml\n{yaml.dump(settings, default_flow_style=False, allow_unicode=True)}\n```\n"
    content += "\n*(Bearbeitung direkt in config/settings.yaml möglich)*"
    
    # Simple action to trigger save (manual edit for now)
    actions = [
        cl.Action(id="config_save_settings", label="💾 Speichern (Manuell)", value="save", description="Änderungen in YAML speichern")
    ]
    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_llm_profiles_editor():
    profiles = config_manager.get_llm_profiles()
    content = "## 🧠 LLM Profile\n"
    for name, data in profiles.get("profiles", {}).items():
        content += f"### {name}\n"
        content += f"- Modell: `{data.get('model', 'N/A')}`\n"
        content += f"- URL: `{data.get('base_url', 'N/A')}`\n"
        content += f"- Params: `{data.get('params', {})}`\n\n"
    
    actions = [
        cl.Action(id="config_add_profile", label="➕ Profil hinzufügen", value="add", description="Neues LLM Profil erstellen")
    ]
    for name in profiles.get("profiles", {}).keys():
        actions.append(cl.Action(id="config_delete_profile", label=f"🗑️ Löschen: {name}", value=name, description=f"Profil {name} löschen"))
    
    await cl.Message(content=content, actions=actions, author="Config").send()


async def render_prompt_variants_editor():
    variants = config_manager.get_prompt_variants()
    content = "## 📜 Prompt Varianten\n"
    content += f"**Standard:** `{variants.get('default_variant', 'N/A')}`\n\n"
    for name, data in variants.get("variants", {}).items():
        content += f"### {name}\n"
        for role, path in data.items():
            content += f"- {role}: `{path}`\n"
        content += "\n"
    
    actions = [
        cl.Action(id="config_add_variant", label="➕ Variante hinzufügen", value="add", description="Neue Prompt Variante erstellen")
    ]
    for name in variants.get("variants", {}).keys():
        actions.append(cl.Action(id="config_delete_variant", label=f"🗑️ Löschen: {name}", value=name, description=f"Variante {name} löschen"))
    
    await cl.Message(content=content, actions=actions, author="Config").send()


async def add_llm_profile_flow():
    res = await cl.AskUserMessage(content="Profilname eingeben:").send()
    if not res or not res.content.strip():
        return
    name = res.content.strip()
    
    res = await cl.AskUserMessage(content="Modellname (z.B. qwen2.5-7b):").send()
    model = res.content.strip() if res else ""
    
    res = await cl.AskUserMessage(content="Base URL (z.B. http://localhost:1234/v1):").send()
    base_url = res.content.strip() if res else ""
    
    res = await cl.AskUserMessage(content="API Key Env Var (z.B. LM_STUDIO_KEY):").send()
    api_key_env = res.content.strip() if res else ""
    
    res = await cl.AskUserMessage(content="Temperatur (z.B. 0.4):").send()
    try:
        temp = float(res.content.strip()) if res else 0.4
    except:
        temp = 0.4
    
    profile_data = {
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "params": {"temperature": temp, "top_p": 0.9, "seed": 42}
    }
    
    config_manager.add_llm_profile(name, profile_data)
    await cl.Message(content=f"✅ Profil '{name}' hinzugefügt.", author="System").send()
    await render_llm_profiles_editor()


async def add_prompt_variant_flow():
    res = await cl.AskUserMessage(content="Variantenname eingeben (z.B. C):").send()
    if not res or not res.content.strip():
        return
    name = res.content.strip()
    
    roles = ["strategist", "critic", "optimizer", "moderator"]
    variant_data = {}
    for role in roles:
        res = await cl.AskUserMessage(content=f"Prompt-Datei für {role} (z.B. prompts/{role}_v3.md):").send()
        if res and res.content.strip():
            variant_data[role] = res.content.strip()
    
    if variant_data:
        config_manager.add_prompt_variant(name, variant_data)
        await cl.Message(content=f"✅ Variante '{name}' hinzugefügt.", author="System").send()
    else:
        await cl.Message(content="❌ Keine Rollen definiert. Abbruch.", author="System").send()
    
    await render_prompt_variants_editor()


@cl.on_settings_update
async def on_settings_update(settings):
    dms = cl.user_session.get("dms")
    selected_project_id = settings.get("selected_project_id")
    selected_document_id = settings.get("selected_document_id")

    cl.user_session.set("selected_project_id", selected_project_id)
    cl.user_session.set("selected_document_id", selected_document_id)

    project_name = "Kein Projekt ausgewählt"
    doc_name = "Kein Dokument ausgewählt"

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

    await cl.Message(
        content=f"📁 Aktives Projekt: {project_name} | 📄 Aktives Dokument: {doc_name}",
        author="System",
    ).send()
