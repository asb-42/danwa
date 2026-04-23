import chainlit as cl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

async def render_dashboard(db, page: int = 0, filter_high: bool = False):
    offset = page * 10
    min_c = 0.8 if filter_high else None
    sessions = db.list_sessions(limit=10, offset=offset, min_consensus=min_c)
    
    header = f"## 📊 Sitzungsverwaltung (Seite {page+1})\n"
    header += f"**Einträge:** {len(sessions)} | **Filter:** {'Konsens ≥ 0.80' if filter_high else 'Alle'}\n\n"

    if not sessions:
        await cl.Message(content=header + "📭 Keine Einträge gefunden.", author="Dashboard").send()
        return

    # Navigations-Actions
    nav_actions = [
        cl.Action(id="dash_filter", label="🔍 Nur ≥0.8", value="toggle", description="Filter umschalten"),
        cl.Action(id="dash_page", label="⬅️ Zurück", value=str(max(0, page-1)), description="Vorherige Seite"),
        cl.Action(id="dash_page", label="➡️ Weiter", value=str(page+1), description="Nächste Seite"),
        cl.Action(id="dash_cleanup", label="🗑️ Bereinigen", value="run", description="Löscht alte Sessions (>90T) & Files")
    ]
    await cl.Message(content=header, actions=nav_actions, author="Dashboard").send()

    # Session-Karten
    for s in sessions:
        card = (
            f"**`{s['session_id'][:8]}...`** | `{s['created_at'][:16]}` | "
            f"Konsens: **{s['consensus']:.2f}** | `{s['profile']}`\n"
            f"`{s['context_preview'][:90]}...`\n"
        )
        actions = [
            cl.Action(id="sess_trace", label="📄 Trace", value=s['session_id'], description="JSON-Trace laden"),
            cl.Action(id="sess_delete", label="🗑️ Löschen", value=s['session_id'], description="Session & Files entfernen"),
            cl.Action(id="sess_report", label="📥 Report", value=s['session_id'], description="Bericht anzeigen")
        ]
        await cl.Message(content=card, actions=actions, author=f"Session {s['session_id'][:6]}").send()