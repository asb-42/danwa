"""Rate limiting via slowapi.

The limiter is initialized in main.py and stored on app.state.
This module provides helpers for per-endpoint rate limit checks.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
