import chainlit as cl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _action(name: str, label: str, value: str = "", tooltip: str = "") -> cl.Action:
    """Helper to create a Chainlit 2.x compatible Action."""
    return cl.Action(name=name, label=label, payload={"value": value}, tooltip=tooltip)


async def render_dashboard(db, page: int = 0, filter_high: bool = False):
    offset = page * 10
    min_c = 0.8 if filter_high else None
    sessions = db.list_sessions(limit=10, offset=offset, min_consensus=min_c)

    header = f"## 📊 Session Management (Page {page + 1})\n"
    header += f"**Entries:** {len(sessions)} | **Filter:** {'Consensus ≥ 0.80' if filter_high else 'All'}\n\n"

    if not sessions:
        await cl.Message(
            content=header + "📭 No entries found.\n\n💡 Start a debate in the chat to create entries.",
            author="Dashboard",
        ).send()
        return

    # Navigation actions
    nav_actions = [
        _action("dash_filter", "🔍 Only ≥0.8", "toggle", "Toggle filter"),
        _action("dash_page", "⬅️ Back", str(max(0, page - 1)), "Previous page"),
        _action("dash_page", "➡️ Next", str(page + 1), "Next page"),
        _action("dash_cleanup", "🗑️ Cleanup", "run", "Delete old sessions (>90d) & files"),
    ]
    await cl.Message(content=header, actions=nav_actions, author="Dashboard").send()

    # Session cards
    for s in sessions:
        card = (
            f"**`{s['session_id'][:8]}...`** | `{s['created_at'][:16]}` | "
            f"Consensus: **{s['consensus']:.2f}** | `{s['profile']}`\n"
            f"`{s['context_preview'][:90]}...`\n"
        )
        actions = [
            _action("sess_trace", "📄 Trace", s["session_id"], "Load JSON trace"),
            _action("sess_delete", "🗑️ Delete", s["session_id"], "Remove session & files"),
            _action("sess_report", "📥 Report", s["session_id"], "Show report"),
        ]
        await cl.Message(content=card, actions=actions, author=f"Session {s['session_id'][:6]}").send()