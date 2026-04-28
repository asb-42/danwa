import chainlit as cl
import yaml
import json
import os
from pathlib import Path
from src.core.debate_engine import DebateEngine
from src.tools.doc_parser import DocumentParser
from src.tools.report_generator import ReportGenerator
from src.core.session_db import SessionDB
from src.ui.dashboard import render_dashboard
from src.core.prompt_manager import PromptManager
from src.core.logging_config import setup_logging

setup_logging("INFO")

CONFIG_PATH = Path("config/llm_profiles.yaml")
with open(CONFIG_PATH) as f:
    PROFILES = yaml.safe_load(f)["profiles"]

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
    if parsed_docs:
        doc_context = "\n\n".join(
            [
                f"### Dokument: {d['name']}\n"
                f"Metadaten: {json.dumps(d['metadata'], ensure_ascii=False)}\n"
                f"Inhalt:\n{d['text']}"
                for d in parsed_docs
            ]
        )
        context += f"\n\n[Analysierte Dokumente]\n{doc_context}"

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
    db.save_session(state, settings["profile"], trace_path, docx_path, pdf_path)


@cl.action_callback
async def handle_action(action: cl.Action):
    db = cl.user_session.get("session_db")
    page = cl.user_session.get("dash_page", 0)
    filt = cl.user_session.get("dash_filter", False)

    # Navigation & Filter
    if action.id == "open_dash":
        await render_dashboard(db, page, filt)
    elif action.id == "dash_filter":
        filt = not filt
        cl.user_session.set("dash_filter", filt)
        await render_dashboard(db, 0, filt)
    elif action.id == "dash_page":
        page = int(action.value)
        cl.user_session.set("dash_page", page)
        await render_dashboard(db, page, filt)
    elif action.id == "dash_cleanup":
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
    elif action.id == "sess_trace":
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

    elif action.id == "sess_delete":
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

    elif action.id == "sess_report":
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
