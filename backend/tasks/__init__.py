"""Celery application for Danwa debate tasks.

This module is intentionally lazy-loaded — Celery is optional.
If redis_url is not configured, task_dispatch falls back to FastAPI BackgroundTasks.
"""
