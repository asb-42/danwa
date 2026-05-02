import asyncio
import chainlit as cl
import logging
from typing import List
from src.dms.dms import DMS
logger = logging.getLogger(__name__)



def _action(name: str, label: str, value: str = "", tooltip: str = "") -> cl.Action:
    """Helper to create a Chainlit 2.x compatible Action."""
    return cl.Action(name=name, label=label, payload={"value": value}, tooltip=tooltip)


def _get_value(action: cl.Action, default: str = "") -> str:
    """Extract value from action.payload (Chainlit 2.x)."""
    if isinstance(action.payload, dict):
        return action.payload.get("value", default)
    return default


def _home_actions() -> list:
    """Standard navigation buttons."""
    return [
        _action("go_home", "🏠 Home", "home", "Back to start"),
        _action("open_dash", "📊 Dashboard", "init", "Session Management"),
        _action("open_dms", "📁 DMS", "dms_init", "Document Management"),
        _action("open_config", "⚙️ Config", "config_init", "Configuration"),
    ]


async def _ask(content: str, author: str = "DMS", timeout: int = 120) -> str | None:
    """Ask user a question with inline input field. Returns response text or None on timeout/cancel."""
    try:
        logger.info(f"DMS AskUserMessage: sending prompt (author={author})")
        res = await cl.AskUserMessage(
            content=content,
            author=author,
            timeout=timeout,
        ).send()
        logger.info(f"DMS AskUserMessage: got response type={type(res)}, value={res!r}")
        if res is None:
            logger.warning("DMS AskUserMessage returned None (timeout or cancel)")
            return None
        if isinstance(res, dict):
            output = res.get("output", "").strip()
            return output if output else None
        output = getattr(res, "output", None)
        if output:
            return str(output).strip()
        return None
    except Exception as e:
        logger.warning(f"DMS AskUserMessage failed: {type(e).__name__}: {e}", exc_info=True)
        return None


# ── Entry Points ─────────────────────────────────────────────────────────

async def start():
    """Entry point called from main app action callback."""
    dms = cl.user_session.get("dms")
    if not dms:
        dms = DMS()
        cl.user_session.set("dms", dms)
    logger.info("DMS Dashboard action triggered")
    await show_projects()


async def handle_action(action: cl.Action):
    """Handle DMS-specific actions. Called from main app's action handler."""
    dms = cl.user_session.get("dms")
    if not dms:
        await cl.Message(
            content="❌ DMS not initialized.",
            author="DMS",
            actions=_home_actions(),
        ).send()
        return

    name = action.name
    value = _get_value(action)

    try:
        if name == "create_project":
            asyncio.create_task(_flow_create_project(dms))
        elif name == "refresh_projects":
            await show_projects()
        elif name == "view_documents":
            project_id = value
            cl.user_session.set("selected_project_id", project_id)
            await show_documents(project_id)
        elif name == "delete_project":
            asyncio.create_task(_flow_delete_project(dms, value))
        elif name == "upload_document":
            project_id = value
            cl.user_session.set("selected_project_id", project_id)
            asyncio.create_task(_flow_upload_document(dms, project_id))
        elif name == "back_to_projects":
            cl.user_session.set("selected_project_id", None)
            await show_projects()
        elif name == "confirm_delete":
            success = dms.delete_project(value)
            if success:
                await cl.Message(content="✅ Project deleted.", author="DMS").send()
            else:
                await cl.Message(content="❌ Delete failed.", author="DMS").send()
            await show_projects()
        elif name == "add_to_rag":
            doc_id = value
            project_id = cl.user_session.get("selected_project_id")
            if project_id:
                dms.add_to_rag(project_id, doc_id)
                await cl.Message(content="✅ Added to RAG.", author="DMS").send()
                await show_documents(project_id)
        elif name == "remove_from_rag":
            doc_id = value
            dms.remove_from_rag(doc_id)
            await cl.Message(content="✅ Removed from RAG.", author="DMS").send()
            project_id = cl.user_session.get("selected_project_id")
            if project_id:
                await show_documents(project_id)
    except Exception as e:
        logger.exception(f"DMS action error: {name}")
        await cl.Message(
            content=f"❌ **DMS Error:** {type(e).__name__}: {e}",
            author="DMS",
            actions=_home_actions(),
        ).send()


# ── DMS Flows (using AskUserMessage) ────────────────────────────────────

async def _flow_create_project(dms: DMS):
    """Multi-step flow to create a project using inline input fields."""
    name = await _ask(
        "## ➕ Create Project\n\n"
        "**Step 1/2:** Enter project name:"
    )
    if not name:
        await cl.Message(content="❌ Cancelled.", author="DMS", actions=_home_actions()).send()
        return

    description = await _ask(
        f"Project: `{name}`\n\n"
        "**Step 2/2:** Enter description (or leave empty):"
    )
    if description is None:
        await cl.Message(content="❌ Cancelled.", author="DMS", actions=_home_actions()).send()
        return

    project_id = dms.create_project(name, description or "")
    if project_id:
        await cl.Message(
            content=f"✅ Created project **{name}** (ID: `{project_id[:8]}...`)",
            author="DMS",
        ).send()
    else:
        await cl.Message(content=f"❌ Failed to create project **{name}**.", author="DMS").send()
    await show_projects()


async def _flow_delete_project(dms: DMS, project_id: str):
    """Confirm and delete a project."""
    projects = dms.list_projects()
    proj_name = next((p["name"] for p in projects if p["id"] == project_id), "Unknown")

    confirm = await _ask(
        f"⚠️ **Delete Project: {proj_name}**\n\n"
        f"Type `yes` to confirm deletion, or anything else to cancel:"
    )
    if confirm and confirm.lower() == "yes":
        success = dms.delete_project(project_id)
        if success:
            await cl.Message(content=f"✅ Project **{proj_name}** deleted.", author="DMS").send()
        else:
            await cl.Message(content=f"❌ Failed to delete **{proj_name}**.", author="DMS").send()
    else:
        await cl.Message(content="Cancelled.", author="DMS").send()
    await show_projects()


async def _flow_upload_document(dms: DMS, project_id: str):
    """Upload a document using AskFileMessage (inline file picker)."""
    try:
        files = await cl.AskFileMessage(
            content="## 📤 Upload Document\n\n"
                    "Click below to select a file (PDF, DOCX, TXT, MD):",
            accept=["application/pdf", "text/plain",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            max_size_mb=50,
            author="DMS",
            timeout=300,
        ).send()

        if not files:
            await cl.Message(content="❌ No file selected.", author="DMS", actions=_home_actions()).send()
            return

        for file in files:
            msg = cl.Message(content=f"📤 Processing `{file.name}`...", author="DMS")
            await msg.send()

            try:
                doc_id = dms.upload_document(project_id, file.path)
                if doc_id:
                    msg.content = f"✅ Uploaded **{file.name}** (ID: `{doc_id[:8]}...`)"
                else:
                    msg.content = f"❌ Failed to upload **{file.name}**"
                await msg.update()
            except Exception as e:
                msg.content = f"❌ Upload error for **{file.name}**: {e}"
                await msg.update()
                logger.error("Upload failed: %s", e)

        await show_documents(project_id)

    except Exception as e:
        logger.exception("File upload flow error")
        await cl.Message(
            content=f"❌ **Upload Error:** {type(e).__name__}: {e}",
            author="DMS",
            actions=_home_actions(),
        ).send()


# ── View Renderers ───────────────────────────────────────────────────────

async def show_projects():
    dms = cl.user_session.get("dms")
    try:
        projects = dms.list_projects()
    except Exception as e:
        await cl.Message(
            content=f"❌ Failed to list projects: {e}",
            author="DMS",
            actions=_home_actions(),
        ).send()
        return

    content = "## 📁 Projects\n" if projects else "📭 No projects found.\n\nCreate a project to get started."
    for proj in projects:
        content += f"- **{proj['name']}** (ID: `{proj['id'][:8]}...`): {proj.get('description', '')}\n"

    actions = [
        _action("create_project", "➕ Create Project", "create", "Create a new project"),
        _action("refresh_projects", "🔄 Refresh", "refresh", "Refresh project list"),
    ]
    for proj in projects:
        actions.append(_action("view_documents", f"📄 Docs: {proj['name']}", proj["id"], f"View documents in {proj['name']}"))
        actions.append(_action("delete_project", f"🗑️ Delete: {proj['name']}", proj["id"], f"Delete {proj['name']}"))
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, author="DMS").send()


async def show_documents(project_id: str):
    dms = cl.user_session.get("dms")
    try:
        docs = dms.list_documents(project_id)
        projects = dms.list_projects()
        proj_name = next((p["name"] for p in projects if p["id"] == project_id), "Unknown")
        manual_rag_docs = dms.list_manual_rag_documents()
        rag_chunks = dms.get_manual_rag_context(k=10)
    except Exception as e:
        await cl.Message(
            content=f"❌ Failed to load documents: {e}",
            author="DMS",
            actions=_home_actions(),
        ).send()
        return

    content = f"## 📄 Documents in {proj_name}\n" if docs else f"📭 No documents in **{proj_name}**.\n\nUpload a document to get started."
    for doc in docs:
        content += f"- **{doc['filename']}** (ID: `{doc['id'][:8]}...`)\n"

    elements = []
    if rag_chunks:
        content += "\n## 📚 Manual RAG Context Preview\n"
        for chunk in rag_chunks:
            chunk_text = chunk.get("text", "")
            snippet = chunk_text[:200] + ("..." if len(chunk_text) > 200 else "")
            source = chunk.get("source") or chunk.get("metadata", {}).get("file_name", "unknown")
            chunk_idx = chunk.get("chunk_index") or chunk.get("metadata", {}).get("chunk_index", -1)
            elements.append(cl.Expandable(title=f"📄 {source} (Chunk {chunk_idx})", content=snippet))

    actions = [
        _action("upload_document", "📤 Upload Document", project_id, "Upload a document"),
        _action("back_to_projects", "🔙 Back to Projects", "back", "Back to projects"),
    ]
    for doc in docs:
        doc_id = doc["id"]
        if doc_id in manual_rag_docs:
            actions.append(
                _action("remove_from_rag", f"➖ Remove {doc['filename']} from RAG", doc_id, "Remove from RAG")
            )
        else:
            actions.append(
                _action("add_to_rag", f"➕ Add {doc['filename']} to RAG", doc_id, "Add to RAG")
            )
    actions.extend(_home_actions())

    await cl.Message(content=content, actions=actions, elements=elements, author="DMS").send()
