#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

COUNT=$(uv run python -c "
import logging
from src.core.privacy import PrivacyGuard
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
guard = PrivacyGuard(retention_days=90)
guard.enforce_retention()
" 2>&1 | grep -c "🗑️ Retention" | tr -d '\n' || echo "0")

echo "✅ Cleanup complete (deleted $COUNT old sessions)"
