"""Celery application factory — lazy-loaded, optional dependency."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_celery_app = None


def get_celery_app():
    """Get or create the Celery application instance.

    Returns None if Celery/Redis is not configured.
    """
    global _celery_app
    if _celery_app is not None:
        return _celery_app

    from backend.core.config import settings

    if not settings.redis_url or not settings.celery_enabled:
        logger.info("Celery not configured (redis_url=%s, celery_enabled=%s)", settings.redis_url, settings.celery_enabled)
        return None

    try:
        from celery import Celery

        _celery_app = Celery(
            "danwa",
            broker=settings.redis_url,
            backend=settings.redis_url,
        )
        _celery_app.conf.update(
            task_routes={
                "backend.tasks.debate.*": {"queue": "debates"},
                "backend.tasks.document.*": {"queue": "documents"},
            },
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            worker_concurrency=settings.celery_worker_concurrency,
            task_soft_time_limit=1800,
            task_time_limit=3600,
            broker_connection_retry_on_startup=True,
        )
        logger.info("Celery app created (broker=%s)", settings.redis_url)
        return _celery_app
    except ImportError:
        logger.warning("Celery package not installed — falling back to BackgroundTasks")
        return None
    except Exception as e:
        logger.warning("Failed to create Celery app: %s — falling back to BackgroundTasks", e)
        return None
