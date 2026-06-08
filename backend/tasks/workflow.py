"""Celery task for generic workflow execution."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def _get_celery_app():
    """Return (or lazily create) celery app."""
    from backend.tasks.celery_app import get_celery_app

    app = get_celery_app()
    if app is None:
        raise RuntimeError("Celery not configured")
    return app


def _create_task():
    """Lazily create the Celery task (only if Celery is available)."""
    try:
        app = _get_celery_app()

        @app.task(
            bind=True,
            name="backend.tasks.workflow.run_workflow_task",
            max_retries=2,
            soft_time_limit=1800,
            time_limit=3600,
        )
        def run_workflow_task(self, session_id: str, workflow_id: str, project_id: str):
            """Execute a compiled workflow in a Celery worker.

            Note: The full initial_state and compiled_workflow are not serialized
            to Celery (they're large objects). Instead, the worker re-loads them
            from the project store. This is a limitation of the Celery approach —
            complex state must be reconstructable.
            """
            logger.info("Celery worker executing workflow %s for project %s", session_id, project_id)

            asyncio.run(_run_workflow_async(session_id, workflow_id, project_id))

        return run_workflow_task
    except Exception as e:
        logger.warning("Cannot create Celery workflow task: %s", e)
        return None


async def _run_workflow_async(session_id: str, workflow_id: str, project_id: str):
    """Async workflow execution — re-loads state from stores."""

    logger.warning(
        "Celery workflow execution for %s requires state re-loading — "
        "falling back to BackgroundTasks is recommended for workflows with complex state",
        session_id,
    )
    # Full workflow execution with re-loaded state is complex.
    # For Phase 3, debate tasks are the primary Celery target.
    # Workflow tasks should use BackgroundTasks until full serialization is implemented.
    raise NotImplementedError(
        "Workflow tasks via Celery require full state serialization. Use BackgroundTasks for workflows with complex initial_state."
    )


# Module-level reference — None if Celery is not available
run_workflow_task = _create_task()
