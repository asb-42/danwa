"""VoiceStore — SQLite cache for available TTS voices.

Populated via edge_tts.list_voices() and cached in the ``tts_voices``
table (migration v11).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class VoiceStore:
    """SQLite cache for available TTS voices.

    The voice catalog is populated lazily on first access via
    :meth:`ensure_populated`.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise VoiceStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_populated(self) -> None:
        """Populate the voice cache if the table is empty.

        Calls edge_tts.list_voices() and inserts all voices.
        """
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM tts_voices").fetchone()
            if row and row["cnt"] > 0:
                return  # Already populated

        logger.info("Populating TTS voice cache...")
        try:
            import edge_tts

            voices = asyncio.run(edge_tts.list_voices())
        except ImportError:
            logger.warning("edge-tts not installed — cannot populate voice cache")
            return

        with self._connect() as conn:
            for voice in voices:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tts_voices
                        (voice_id, name, language, gender, provider, is_active)
                    VALUES (?, ?, ?, ?, 'edge_tts', 1)
                    """,
                    (
                        voice.get("ShortName", ""),
                        voice.get("FriendlyName", ""),
                        voice.get("Locale", ""),
                        voice.get("Gender", ""),
                    ),
                )
        logger.info("TTS voice cache populated with %d voices", len(voices))

    def list_voices(
        self,
        language: str | None = None,
        gender: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return cached voices, optionally filtered.

        Args:
            language: Filter by language prefix (e.g. ``"de"`` matches ``"de-DE"``).
            gender: Filter by gender (``"Male"`` / ``"Female"``).

        Returns:
            List of voice dicts with keys: voice_id, name, language, gender.
        """
        self.ensure_populated()

        conditions: list[str] = ["is_active = 1"]
        params: list[Any] = []

        if language:
            conditions.append("language LIKE ?")
            params.append(f"{language}%")
        if gender:
            conditions.append("gender = ?")
            params.append(gender)

        where = f"WHERE {' AND '.join(conditions)}"

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT voice_id, name, language, gender
                FROM tts_voices
                {where}
                ORDER BY language, name
                """,
                params,
            ).fetchall()

        return [dict(r) for r in rows]

    def get_voice(self, voice_id: str) -> dict[str, Any] | None:
        """Return a single voice by ID, or None if not found."""
        self.ensure_populated()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT voice_id, name, language, gender FROM tts_voices WHERE voice_id = ?",
                (voice_id,),
            ).fetchone()
        return dict(row) if row else None
