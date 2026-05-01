import chainlit as cl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _action(name: str, label: str, value: str = "", description: str = "") -> cl.Action:
    """Helper to create a Chainlit 2.x compatible Action."""
    return cl.Action(name=name, label=label, payload={"value": value}, description=description)


async def render_dashboard(db, page: int = 0, filter_high: bool = False):
    offset = page * 10
    min_c = 0.8 if filter_high else None
    sessions = db.list_sessions(limit=10, offset=offset, min_consensus=min_c)

    header = f"## 📊 Sitzungsverwaltung (Seite {page + 1})\n"
    header += f"**Einträge:** {len(sessions)} | **Filter:** {'Konsens ≥ 0.80' if filter_high else 'Alle'}\n\n"

    if not sessions:
        await cl.Message(
            content=header + "📭 Keine Einträge gefunden.\n\n💡 Starte eine Debatte im Chat, um Einträge zu erstellen.",
            author="Dashboard",
        ).send()
        return

    # Navigations-Actions
    nav_actions = [
        _action("dash_filter", "🔍 Nur ≥0.8", "toggle", "Filter umschalten"),
        _action("dash_page", "⬅️ Zurück", str(max(0, page - 1)), "Vorherige Seite"),
        _action("dash_page", "➡️ Weiter", str(page + 1), "Nächste Seite"),
        _action("dash_cleanup", "🗑️ Bereinigen", "run", "Löscht alte Sessions (>90T) & Files"),
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
            _action("sess_trace", "📄 Trace", s["session_id"], "JSON-Trace laden"),
            _action("sess_delete", "🗑️ Löschen", s["session_id"], "Session & Files entfernen"),
            _action("sess_report", "📥 Report", s["session_id"], "Bericht anzeigen"),
        ]
        await cl.Message(content=card, actions=actions, author=f"Session {s['session_id'][:6]}").send()