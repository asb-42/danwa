"""API router for debate execution (start, WebSocket streaming, result)."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.core.debate_engine import DebateEngine, DebateState
from src.core.session_db import SessionDB
from src.core.config_manager import ConfigManager
from src.tools.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter()


class DebateStartRequest(BaseModel):
    context: str
    profile: Optional[str] = None
    agent_profile: Optional[str] = None
    max_rounds: int = 3
    threshold: float = 0.75
    enable_fact_check: bool = True
    enable_memory: bool = False
    variant_override: Optional[str] = None
    project_id: Optional[str] = None
    document_ids: Optional[list[str]] = None
    rag_context: Optional[str] = None


# --- REST endpoint: start debate (returns session_id immediately) ---

@router.post("/start")
async def start_debate(body: DebateStartRequest):
    """
    Start a debate. Returns session_id immediately.
    The actual debate runs via WebSocket at /ws/debate/{session_id}.
    """
    # Validate agent profile exists
    cm = ConfigManager()
    if body.agent_profile:
        profile = cm.get_agent_profile(body.agent_profile)
        if profile is None:
            raise HTTPException(
                status_code=400,
                detail=f"Agent profile '{body.agent_profile}' not found",
            )
    else:
        body.agent_profile = cm.get_default_agent_profile_name()

    # Pre-create a session_id so the client can connect to the WebSocket
    import uuid
    session_id = str(uuid.uuid4())[:8]

    return {
        "session_id": session_id,
        "agent_profile": body.agent_profile,
        "max_rounds": body.max_rounds,
    }


# --- WebSocket endpoint: debate streaming ---

@router.websocket("/ws/{session_id}")
async def debate_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time debate streaming.

    Protocol:
      Client sends: {"type": "start", "context": "...", "profile": "...", ...}
      Server sends: {"type": "status", "message": "..."}
                    {"type": "round", "round": 1, "max_rounds": 3}
                    {"type": "agent_start", "role": "strategist"}
                    {"type": "agent_message", "role": "strategist", "content": "..."}
                    {"type": "consensus", "round": 1, "value": 0.75}
                    {"type": "complete", "consensus": 0.85, "output": "...", "session_id": "..."}
                    {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info("WebSocket connected for session %s", session_id)

    try:
        # Wait for the client to send the start message
        raw = await websocket.receive_text()
        msg = json.loads(raw)

        if msg.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected 'start' message"})
            await websocket.close()
            return

        context = msg.get("context", "")
        if not context.strip():
            await websocket.send_json({"type": "error", "message": "Context cannot be empty"})
            await websocket.close()
            return

        # Build engine parameters
        profile = msg.get("profile")
        agent_profile = msg.get("agent_profile")
        max_rounds = msg.get("max_rounds", 3)
        threshold = msg.get("threshold", 0.75)
        enable_fact_check = msg.get("enable_fact_check", True)
        enable_memory = msg.get("enable_memory", False)
        variant_override = msg.get("variant_override")
        project_id = msg.get("project_id")
        document_ids = msg.get("document_ids")
        rag_context = msg.get("rag_context", "")

        # Resolve agent profile
        cm = ConfigManager()
        if not agent_profile:
            agent_profile = cm.get_default_agent_profile_name()

        await websocket.send_json({"type": "status", "message": f"Starting debate with profile '{agent_profile}'..."})

        # Progress callback sends updates via WebSocket
        async def progress_callback(step: str, detail: str):
            try:
                await websocket.send_json({"type": step, "message": detail})
            except Exception:
                pass  # Client disconnected

        # Run the debate engine
        # DebateEngine.run() is async, so we can await it directly
        try:
            engine = DebateEngine(
                profile_name=profile,
                max_rounds=max_rounds,
                threshold=threshold,
                enable_fact_check=enable_fact_check,
                enable_memory=enable_memory,
                rag_context=rag_context,
                agent_profile_name=agent_profile,
            )

            # Override the session_id to match what the client expects
            engine.state.session_id = session_id

            state = await engine.run(
                context,
                progress_callback=progress_callback,
                variant_override=variant_override,
            )

            # Save session to database
            db = SessionDB()
            db.save_session(
                state,
                profile=profile or "default",
                project_id=project_id,
                document_ids=document_ids,
            )

            # Send completion message
            await websocket.send_json({
                "type": "complete",
                "session_id": state.session_id,
                "consensus": state.final_consensus,
                "output": state.output,
                "rounds": len(state.rounds),
                "variant": state.used_variant,
                "agent_profile": state.used_agent_profile,
            })

        except Exception as e:
            logger.error("Debate error: %s", e, exc_info=True)
            await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
