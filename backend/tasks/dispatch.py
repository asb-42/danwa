"""Task dispatch — routes debate/workflow tasks to Celery or BackgroundTasks.

This is the single integration point for async task execution.
All routers call ``dispatch_debate_task()`` or ``dispatch_workflow_task()``
instead of ``background_tasks.add_task()`` directly.

If Celery is configured and available, tasks are dispatched to a Celery worker.
Otherwise, they fall back to FastAPI BackgroundTasks (single-process mode).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)


def dispatch_debate_task(
    background_tasks: BackgroundTasks,
    debate_id: str,
    project_id: str,
    audit: Any,
    store: Any,
    project_store: Any = None,
) -> str:
    """Dispatch a debate workflow task.

    The ``project_store`` parameter is kept for backward compatibility but
    is no longer required.

    Returns:
        "celery" if dispatched to Celery, "background" if using BackgroundTasks.
    """
    from backend.tasks.celery_app import get_celery_app

    celery_app = get_celery_app()
    if celery_app is not None:
        try:
            from backend.tasks.debate import run_debate_task

            run_debate_task.delay(debate_id, project_id)
            logger.info("Debate %s dispatched to Celery", debate_id)
            return "celery"
        except Exception as e:
            logger.warning("Celery dispatch failed for debate %s, falling back: %s", debate_id, e)

    # Fallback: FastAPI BackgroundTasks
    from backend.services.debate_workflow import run_debate_workflow

    background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store)
    logger.info("Debate %s dispatched to BackgroundTasks", debate_id)
    return "background"


def dispatch_workflow_task(
    background_tasks: BackgroundTasks,
    session_id: str,
    workflow_id: str,
    project_id: str,
    initial_state: dict[str, Any],
    compiled_workflow: Any,
    snapshot_store: Any,
) -> str:
    """Dispatch a generic workflow task.

    Returns:
        "celery" if dispatched to Celery, "background" if using BackgroundTasks.
    """
    from backend.tasks.celery_app import get_celery_app

    celery_app = get_celery_app()
    if celery_app is not None:
        try:
            from backend.tasks.workflow import run_workflow_task

            run_workflow_task.delay(session_id, workflow_id, project_id)
            logger.info("Workflow %s dispatched to Celery", session_id)
            return "celery"
        except Exception as e:
            logger.warning("Celery dispatch failed for workflow %s, falling back: %s", session_id, e)

    # Fallback: FastAPI BackgroundTasks
    from backend.workflow.workflow_runner import run_workflow_background

    background_tasks.add_task(
        run_workflow_background,
        session_id=session_id,
        workflow_id=workflow_id,
        project_id=project_id,
        initial_state=initial_state,
        compiled_workflow=compiled_workflow,
        snapshot_store=snapshot_store,
    )
    logger.info("Workflow %s dispatched to BackgroundTasks", session_id)
    return "background"
