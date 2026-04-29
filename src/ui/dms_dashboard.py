import asyncio
import chainlit as cl
import logging
from typing import List, Dict, Optional
from src.dms.dms import DMS

logger = logging.getLogger(__name__)


@cl.on_chat_start
async def start():
    dms = DMS()
    cl.user_session.set("dms", dms)
    cl.user_session.set("selected_project_id", None)
    logger.info("DMS Dashboard initialized")
    await show_projects()


@cl.on_message
async def main(message: cl.Message):
    if message.elements:
        await handle_file_upload(message.elements)
    else:
        await cl.Message(content="Use dashboard actions to manage projects and documents.").send()


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


@cl.action_callback
async def handle_action(action: cl.Action):
    dms = cl.user_session.get("dms")
    if not dms:
        await cl.ErrorMessage(content="DMS not initialized.").send()
        return

    if action.name == "create_project":
        await create_project_flow()
    elif action.name == "refresh_projects":
        await show_projects()
    elif action.name == "view_documents":
        project_id = action.value
        cl.user_session.set("selected_project_id", project_id)
        await show_documents(project_id)
    elif action.name == "delete_project":
        await delete_project_flow(action.value)
    elif action.name == "upload_document":
        project_id = action.value
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
    elif action.name == "back_to_projects":
        cl.user_session.set("selected_project_id", None)
        await show_projects()
    elif action.name == "confirm_delete":
        success = dms.delete_project(action.value)
        if success:
            await cl.Message(content="✅ Project deleted.").send()
        else:
            await cl.ErrorMessage(content="❌ Delete failed.").send()
        await show_projects()


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
            cl.Action(name="create_project", label="➕ Create Project", value="create", payload={}),
            cl.Action(name="refresh_projects", label="🔄 Refresh", value="refresh", payload={}),
        ]
        for proj in projects:
            actions.append(cl.Action(name="view_documents", label=f"📄 Docs: {proj['name']}", value=proj["id"], payload={}))
            actions.append(cl.Action(name="delete_project", label=f"🗑️ Delete: {proj['name']}", value=proj["id"], payload={}))

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
        cl.Action(name="upload_document", label="📤 Upload Document", value=project_id, payload={}),
        cl.Action(name="back_to_projects", label="🔙 Back", value="back", payload={}),
    ]
    for doc in docs:
        doc_id = doc["id"]
        if doc_id in manual_rag_docs:
            actions.append(
                cl.Action(
                    name="remove_from_rag",
                    label=f"➖ Remove {doc['filename']} from RAG",
                    value=doc_id,
                    payload={},
                )
            )
        else:
            actions.append(
                cl.Action(
                    name="add_to_rag",
                    label=f"➕ Add {doc['filename']} to RAG",
                    value=doc_id,
                    payload={},
                )
            )

    await cl.Message(content=content, actions=actions, elements=elements).send()


async def create_project_flow():
    res = await cl.AskUserMessage(content="Enter project name:").send()
    if not res or not res.content.strip():
        await cl.Message(content="Cancelled.").send()
        return

    name = res.content.strip()
    res = await cl.AskUserMessage(content="Enter description (optional):").send()
    description = res.content.strip() if res else ""

    dms = cl.user_session.get("dms")
    project_id = dms.create_project(name, description)
    if project_id:
        await cl.Message(content=f"✅ Created '{name}' (ID: `{project_id[:8]}...`)").send()
    else:
        await cl.ErrorMessage(content=f"❌ Failed to create '{name}'").send()
    await show_projects()


async def delete_project_flow(project_id: str):
    dms = cl.user_session.get("dms")
    projects = dms.list_projects()
    proj_name = next((p["name"] for p in projects if p["id"] == project_id), "Unknown")

    res = await cl.AskUserMessage(content=f"Type 'yes' to delete '{proj_name}':").send()
    if res and res.content.strip().lower() == "yes":
        await handle_action(cl.Action(name="confirm_delete", value=project_id))
    else:
        await cl.Message(content="Cancelled.").send()
    await show_projects()
