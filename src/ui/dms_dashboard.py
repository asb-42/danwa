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


# ── DMS State Machine ────────────────────────────────────────────────────

def _set_dms_state(state: dict):
    cl.user_session.set("dms_mode", state)


def _get_dms_state() -> dict | None:
    return cl.user_session.get("dms_mode")


def _clear_dms_state():
    cl.user_session.set("dms_mode", None)


async def handle_input(message: cl.Message) -> bool:
    """
    Handle user input during a DMS flow.
    Returns True if the message was consumed, False otherwise.
    """
    state = _get_dms_state()
    if not state:
        return False

    flow = state.get("flow")
    text = message.content.strip()

    # Cancel
    if text.lower() in ("cancel", "abort", "quit"):
        _clear_dms_state()
        await cl.Message(content="❌ Cancelled.").send()
        await show_projects()
        return True

    # ── Create Project Flow ──
    if flow == "create_project":
        step = state.get("step")
        data = state.get("data", {})

        if step == "name":
            if not text:
                await cl.Message(content="⚠️ Name cannot be empty. Try again or type `cancel`.").send()
                return True
            data["name"] = text
            state["step"] = "description"
            state["data"] = data
            _set_dms_state(state)
            await cl.Message(
                content=f"Project name: `{text}`\n\nEnter description (or leave empty):",
            ).send()
            return True

        elif step == "description":
            data["description"] = text
            dms = cl.user_session.get("dms")
            project_id = dms.create_project(data["name"], data["description"])
            _clear_dms_state()
            if project_id:
                await cl.Message(content=f"✅ Created '{data['name']}' (ID: `{project_id[:8]}...`)").send()
            else:
                await cl.ErrorMessage(content=f"❌ Failed to create '{data['name']}'").send()
            await show_projects()
            return True

    # ── Delete Project Flow ──
    if flow == "delete_project":
        if text.lower() == "yes":
            dms = cl.user_session.get("dms")
            success = dms.delete_project(state.get("project_id"))
            _clear_dms_state()
            if success:
                await cl.Message(content="✅ Project deleted.").send()
            else:
                await cl.ErrorMessage(content="❌ Delete failed.").send()
        else:
            _clear_dms_state()
            await cl.Message(content="Cancelled.").send()
        await show_projects()
        return True

    # Fallback
    _clear_dms_state()
    await cl.Message(content="⚠️ Unknown DMS state. Returning to projects.").send()
    await show_projects()
    return True


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
        await cl.ErrorMessage(content="DMS not initialized.").send()
        return

    name = action.name
    value = _get_value(action)

    if name == "create_project":
        _set_dms_state({"flow": "create_project", "step": "name", "data": {}})
        await cl.Message(
            content="## ➕ Create Project\n\nEnter project name:\n\n*(Type `cancel` to abort)*",
        ).send()
    elif name == "refresh_projects":
        await show_projects()
    elif name == "view_documents":
        project_id = value
        cl.user_session.set("selected_project_id", project_id)
        await show_documents(project_id)
    elif name == "delete_project":
        projects = dms.list_projects()
        proj_name = next((p["name"] for p in projects if p["id"] == value), "Unknown")
        _set_dms_state({"flow": "delete_project", "project_id": value})
        await cl.Message(
            content=f"⚠️ Type `yes` to delete project **{proj_name}**, or anything else to cancel:",
        ).send()
    elif name == "upload_document":
        project_id = value
        cl.user_session.set("selected_project_id", project_id)
        await cl.Message(
            content="Upload a document using the file uploader:",
            elements=[
                cl.FileUploader(
                    name="doc_upload",
                    label="Choose file",
                    accept=[".pdf", ".docx", ".txt", ".md"],
                    max_files=1,
                )
            ],
        ).send()
    elif name == "back_to_projects":
        cl.user_session.set("selected_project_id", None)
        await show_projects()
    elif name == "confirm_delete":
        success = dms.delete_project(value)
        if success:
            await cl.Message(content="✅ Project deleted.").send()
        else:
            await cl.ErrorMessage(content="❌ Delete failed.").send()
        await show_projects()
    elif name == "add_to_rag":
        doc_id = value
        project_id = cl.user_session.get("selected_project_id")
        if project_id:
            dms.add_to_rag(project_id, doc_id)
            await cl.Message(content="✅ Added to RAG.").send()
            await show_documents(project_id)
    elif name == "remove_from_rag":
        doc_id = value
        dms.remove_from_rag(doc_id)
        await cl.Message(content="✅ Removed from RAG.").send()
        project_id = cl.user_session.get("selected_project_id")
        if project_id:
            await show_documents(project_id)


async def handle_file_upload(elements: List[cl.File]):
    dms = cl.user_session.get("dms")
    project_id = cl.user_session.get("selected_project_id")

    if not project_id:
        await cl.ErrorMessage(content="No project selected. Please select a project first.").send()
        return
    if not dms:
        await cl.ErrorMessage(content="DMS not initialized.").send()
        return

    for file in elements:
        msg = None
        try:
            msg = cl.Message(content=f"📤 Uploading {file.name}... (0%)")
            await msg.send()

            await asyncio.sleep(0.3)
            msg.content = f"📤 Uploading {file.name}... (50%)"
            await msg.update()

            await asyncio.sleep(0.3)
            msg.content = f"📤 Uploading {file.name}... (100%)"
            await msg.update()

            doc_id = dms.upload_document(project_id, file.path)

            if doc_id:
                msg.content = f"✅ Uploaded '{file.name}' (ID: {doc_id[:8]}...)"
            else:
                msg.content = f"❌ Failed to upload '{file.name}'"
            await msg.update()

        except Exception as e:
            if msg:
                msg.content = f"❌ Upload error: {str(e)}"
                await msg.update()
            else:
                await cl.ErrorMessage(content=f"❌ Upload error: {str(e)}").send()
            logger.error("Upload failed: %s", e)

    await show_documents(project_id)


# ── View Renderers ───────────────────────────────────────────────────────

async def show_projects():
    dms = cl.user_session.get("dms")
    try:
        projects = dms.list_projects()
    except Exception as e:
        await cl.ErrorMessage(content=f"❌ Failed to list projects: {str(e)}").send()
        return

    content = "## 📁 Projects\n" if projects else "📭 No projects found."
    for proj in projects:
        content += f"- **{proj['name']}** (ID: `{proj['id'][:8]}...`): {proj.get('description', '')}\n"

    actions = [
        _action("create_project", "➕ Create Project", "create", "Create a new project"),
        _action("refresh_projects", "🔄 Refresh", "refresh", "Refresh project list"),
    ]
    for proj in projects:
        actions.append(_action("view_documents", f"📄 Docs: {proj['name']}", proj["id"], f"View documents in {proj['name']}"))
        actions.append(_action("delete_project", f"🗑️ Delete: {proj['name']}", proj["id"], f"Delete {proj['name']}"))

    await cl.Message(content=content, actions=actions).send()


async def show_documents(project_id: str):
    dms = cl.user_session.get("dms")
    try:
        docs = dms.list_documents(project_id)
        projects = dms.list_projects()
        proj_name = next((p["name"] for p in projects if p["id"] == project_id), "Unknown")
        manual_rag_docs = dms.list_manual_rag_documents()
        rag_chunks = dms.get_manual_rag_context(k=10)
    except Exception as e:
        await cl.ErrorMessage(content=f"❌ Failed to load documents: {str(e)}").send()
        return

    content = f"## 📄 Documents in {proj_name}\n" if docs else f"📭 No documents in {proj_name}."
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
        _action("back_to_projects", "🔙 Back", "back", "Back to projects"),
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

    await cl.Message(content=content, actions=actions, elements=elements).send()
