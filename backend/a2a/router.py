"""A2A FastAPI Router — JSON-RPC endpoints for A2A protocol.

Exposes:
- ``GET /.well-known/agent.json`` — Agent Card discovery
- ``POST /a2a`` — JSON-RPC endpoint for tasks/send, tasks/get, tasks/cancel
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.a2a.agent_card import AGENT_CARD
from backend.a2a.config import get_a2a_config
from backend.a2a.schemas import A2AMessage, A2ATask, A2ATextPart
from backend.a2a.server import A2AServer
from backend.a2a.task_manager import TaskManager
from backend.api.deps import get_project_store

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-initialized singletons
_task_manager: TaskManager | None = None
_server: A2AServer | None = None


def _get_task_manager() -> TaskManager:
    """Return (or lazily create) task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def _get_server() -> A2AServer:
    """Return (or lazily create) server."""
    global _server
    if _server is None:
        _server = A2AServer(task_manager=_get_task_manager())
    return _server


# ------------------------------------------------------------------
# Discovery endpoint
# ------------------------------------------------------------------


@router.get("/.well-known/agent.json")
async def get_agent_card():
    """A2A Agent Card — discovery endpoint.

    Returns the Agent Card JSON so external A2A clients can discover
    Danwa's capabilities, available projects, and supported languages.
    """
    config = get_a2a_config()
    card = {**AGENT_CARD}

    server_cfg = config.get("server", {})
    if server_cfg.get("path"):
        card["url"] = server_cfg["path"]

    projects = get_project_store().list_all()
    card["projects"] = [{"id": p.id, "name": p.name, "description": p.description or ""} for p in projects]

    card["languages"] = [
        {"code": "de", "name": "Deutsch"},
        {"code": "en", "name": "English"},
        {"code": "fr", "name": "Français"},
        {"code": "es", "name": "Español"},
        {"code": "it", "name": "Italiano"},
        {"code": "pt", "name": "Português"},
        {"code": "nl", "name": "Nederlands"},
        {"code": "pl", "name": "Polski"},
        {"code": "sv", "name": "Svenska"},
        {"code": "da", "name": "Dansk"},
        {"code": "no", "name": "Norsk"},
        {"code": "fi", "name": "Suomi"},
        {"code": "ru", "name": "Русский"},
        {"code": "zh", "name": "中文"},
        {"code": "ja", "name": "日本語"},
        {"code": "ko", "name": "한국어"},
        {"code": "ar", "name": "العربية"},
        {"code": "tr", "name": "Türkçe"},
    ]

    for skill in card.get("skills", []):
        if skill.get("id") == "debate":
            project_ids = [p["id"] for p in card["projects"]]
            lang_codes = [lang["code"] for lang in card["languages"]]
            skill["usage"] = {
                "project_id": project_ids,
                "language": lang_codes,
                "note": "Include 'project_id' and 'language' in tasks/send params.metadata to override defaults.",
            }

    return JSONResponse(content=card)


# ------------------------------------------------------------------
# JSON-RPC endpoint
# ------------------------------------------------------------------


@router.post("/a2a")
async def handle_a2a_request(request: Request):
    """A2A JSON-RPC endpoint — handles all A2A methods.

    Supported methods:
    - ``tasks/send`` — create and start a debate
    - ``tasks/get`` — poll for task status/result
    - ``tasks/cancel`` — cancel a running task
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error: invalid JSON",
                },
            },
            status_code=400,
        )

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    server = _get_server()

    try:
        if method == "tasks/send":
            message = None
            if "message" in params:
                parts = [A2ATextPart(type=p.get("type", "text"), text=p.get("text", "")) for p in params["message"].get("parts", [])]
                message = A2AMessage(
                    role=params["message"].get("role", "user"),
                    parts=parts,
                )

            metadata = params.get("metadata", {})
            task = A2ATask(id=params.get("id"), message=message, metadata=metadata)
            result = await server.handle_task_send(task)

        elif method == "tasks/get":
            result = await server.handle_task_get(params.get("id", ""))

        elif method == "tasks/cancel":
            result = await server.handle_task_cancel(params.get("id", ""))

        else:
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}",
                    },
                },
                status_code=400,
            )

        return JSONResponse(content={"jsonrpc": "2.0", "id": req_id, "result": result})

    except Exception as exc:
        logger.error("A2A request failed: %s", exc, exc_info=True)
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(exc)},
            },
            status_code=500,
        )
