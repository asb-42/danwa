"""Debate service sub-package.

Re-exports all public functions from sub-modules for backward compatibility.
"""

from backend.services.debate.debate_oob import (
    _oob_queues,
    clear_cancel,
    clear_oob_queue,
    consume_oob,
    enqueue_oob,
    get_oob_for_debate,
    is_cancelled,
    mark_cancelled,
)
from backend.services.debate.debate_rag import (
    _format_analysis_for_rag,
    _load_analysis_text,
    resolve_rag_context,
    resolve_rag_context_with_debate_results,
)
from backend.services.debate.debate_title import (
    SYSTEM_PROMPT_TITLES,
    _fallback_title,
    _post_process_title,
    _select_service_llm,
    generate_debate_title,
    validate_title,
)

__all__ = [
    # OOB / cancellation
    # Note: ``_cancelled_debates`` was removed in Sprint 37 (3/3)
    # when cancellation moved to ``backend.state.workflow_state``.
    # The state lives on the backend now; use ``get_workflow_state()``
    # for any code that needs to inspect or clear it.
    "_oob_queues",
    "clear_cancel",
    "clear_oob_queue",
    "consume_oob",
    "enqueue_oob",
    "get_oob_for_debate",
    "is_cancelled",
    "mark_cancelled",
    # RAG
    "_format_analysis_for_rag",
    "_load_analysis_text",
    "resolve_rag_context",
    "resolve_rag_context_with_debate_results",
    # Title
    "SYSTEM_PROMPT_TITLES",
    "_fallback_title",
    "_post_process_title",
    "_select_service_llm",
    "generate_debate_title",
    "validate_title",
]
