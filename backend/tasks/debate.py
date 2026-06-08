"""Celery task for debate workflow execution."""

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
            name="backend.tasks.debate.run_debate_task",
            max_retries=2,
            soft_time_limit=1800,
            time_limit=3600,
        )
        def run_debate_task(self, debate_id: str, project_id: str):
            """Execute a debate workflow in a Celery worker.

            This runs the LangGraph workflow in a dedicated event loop
            inside the Celery worker process.
            """
            logger.info("Celery worker executing debate %s for project %s", debate_id, project_id)

            asyncio.run(_run_debate_async(debate_id, project_id))

        return run_debate_task
    except Exception as e:
        logger.warning("Cannot create Celery debate task: %s", e)
        return None


async def _run_debate_async(debate_id: str, project_id: str):
    """Async debate execution — called inside the Celery worker's event loop."""
    from backend.api.deps import get_case_dir
    from backend.persistence.audit import AuditService
    from backend.persistence.debate_store import DebateStore
    from backend.services.debate_workflow import run_debate_workflow

    project_dir = get_case_dir(project_id)
    store = DebateStore(data_dir=project_dir / "debates")
    audit = AuditService()

    await run_debate_workflow(debate_id, project_id, audit, store)


# Module-level reference — None if Celery is not available
run_debate_task = _create_task()
