"""Danwa Assistant API router.

Provides endpoints for the conversational AI assistant:
- Session management (create, list, delete)
- Chat messages (send, receive)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.services.assistant_service import AssistantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

# Singleton service instance
_assistant_service: AssistantService | None = None


def get_assistant_service() -> AssistantService:
    """Get or create the assistant service singleton."""
    global _assistant_service
    if _assistant_service is None:
        _assistant_service = AssistantService()
    return _assistant_service


@router.post("/sessions", response_model=dict[str, Any])
async def create_session(
    title: str = "New Conversation",
    profile_id: str | None = None,
):
    """Create a new chat session with the Danwa assistant.

    Args:
        title: Optional title for the session.
        profile_id: Optional LLM profile ID to use for this session.

    Returns:
        Session object with ID and metadata.
    """
    service = get_assistant_service()
    session = service.create_session(title=title, profile_id=profile_id)
    return {
        "id": session.id,
        "title": session.title,
        "message_count": 0,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "llm_profile_id": session.llm_profile_id,
    }


@router.get("/sessions", response_model=list[dict[str, Any]])
async def list_sessions():
    """List all active chat sessions.

    Returns:
        List of session summaries (no message content).
    """
    service = get_assistant_service()
    return service.list_sessions()


@router.get("/sessions/{session_id}", response_model=dict[str, Any])
async def get_session(session_id: str):
    """Get a specific chat session with full message history.

    Args:
        session_id: The session ID.

    Returns:
        Session object with all messages.

    Raises:
        HTTP 404: Session not found.
    """
    service = get_assistant_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "title": session.title,
        "message_count": len(session.messages),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "llm_profile_id": session.llm_profile_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "tokens_in": m.tokens_in,
                "tokens_out": m.tokens_out,
                "model": m.model,
                "tool_call_id": m.tool_call_id,
                "tool_name": m.tool_name,
            }
            for m in session.messages
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session.

    Args:
        session_id: The session ID.

    Returns:
        Status message.

    Raises:
        HTTP 404: Session not found.
    """
    service = get_assistant_service()
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.post("/sessions/{session_id}/chat", response_model=dict[str, Any])
async def send_message(
    session_id: str,
    message: str,
    profile_id: str | None = None,
):
    """Send a message to the Danwa assistant and get a response.

    Args:
        session_id: The session ID.
        message: The user's message.
        profile_id: Optional LLM profile override.

    Returns:
        Contains ``messages`` (array of all new messages from this turn,
        including tool calls and results) and ``message`` (the final
        assistant text response for backward compatibility).

    Raises:
        HTTP 404: Session not found.
        HTTP 500: LLM call failed.
    """
    service = get_assistant_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Track message count before the call to detect new messages
    before_count = len(session.messages)

    try:
        assistant_msg = await service.send_message(
            session_id=session_id,
            user_message=message,
            profile_id=profile_id,
        )
        if not assistant_msg:
            raise HTTPException(status_code=500, detail="Failed to generate response")

        # Return all new messages from this turn
        new_messages = [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "tokens_in": m.tokens_in,
                "tokens_out": m.tokens_out,
                "model": m.model,
                "tool_call_id": m.tool_call_id,
                "tool_name": m.tool_name,
            }
            for m in session.messages[before_count:]
        ]

        return {
            "messages": new_messages,
            "message": {
                "role": assistant_msg.role,
                "content": assistant_msg.content,
                "timestamp": assistant_msg.timestamp,
                "tokens_in": assistant_msg.tokens_in,
                "tokens_out": assistant_msg.tokens_out,
                "model": assistant_msg.model,
                "tool_call_id": assistant_msg.tool_call_id,
                "tool_name": assistant_msg.tool_name,
            },
            "message_count": len(new_messages),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


@router.post("/chat", response_model=dict[str, Any])
async def quick_chat(
    message: str,
    profile_id: str | None = None,
):
    """Quick chat endpoint — creates a session if needed and sends a message.

    This is a convenience endpoint for single-message interactions without
    explicit session management.

    Args:
        message: The user's message.
        profile_id: Optional LLM profile override.

    Returns:
        Session ID and all new messages from this turn.
    """
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    service = get_assistant_service()

    # Create a new session for this quick chat
    session = service.create_session(title="Quick Chat", profile_id=profile_id)

    before_count = len(session.messages)

    assistant_msg = await service.send_message(
        session_id=session.id,
        user_message=message,
        profile_id=profile_id,
    )
    if not assistant_msg:
        raise HTTPException(status_code=500, detail="Failed to generate response")

    new_messages = [
        {
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "tokens_in": m.tokens_in,
            "tokens_out": m.tokens_out,
            "model": m.model,
            "tool_call_id": m.tool_call_id,
            "tool_name": m.tool_name,
        }
        for m in session.messages[before_count:]
    ]

    return {
        "session_id": session.id,
        "messages": new_messages,
        "message": {
            "role": assistant_msg.role,
            "content": assistant_msg.content,
            "timestamp": assistant_msg.timestamp,
            "tokens_in": assistant_msg.tokens_in,
            "tokens_out": assistant_msg.tokens_out,
            "model": assistant_msg.model,
            "tool_call_id": assistant_msg.tool_call_id,
            "tool_name": assistant_msg.tool_name,
        },
        "message_count": len(new_messages),
    }
