"""UI-Translation Service — Verwaltet Frontend-String-Übersetzungen.

Dieser Service speichert und verwaltet UI-Übersetzungen (i18n)
in einer SQLite-Datenbank, ergänzt durch LLM-basierte Ad-hoc-Übersetzung.

Im Gegensatz zum TranslationService (der für Modulinhalte/Blueprints zuständig ist)
handelt dieser Service ausschließlich UI-Strings wie Menüs, Buttons, Labels etc.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from backend.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = Path("data/i18n")
DEFAULT_LOCALES = [
    "de", "en", "fr", "es", "it", "pt", "ru", "zh", "ja", "ko", "sv", "el",
    # Optionale RTL-Sprachen:
    # "ar", "he",
]

LOCALE_NAMES: dict[str, str] = {
    "de": "Deutsch", "en": "English", "fr": "Français",
    "es": "Español", "it": "Italiano", "pt": "Português",
    "ru": "Русский", "zh": "中文", "ja": "日本語",
    "ko": "한국어", "sv": "Svenska", "el": "Ελληνικά",
    "ar": "العربية", "he": "עברית",
}

RTL_LOCALES = {"ar", "he", "fa"}

# Plural-Tags basierend auf Intl.PluralRules
PLURAL_TAGS: dict[str, list[str]] = {
    "de": ["one", "other"],
    "en": ["one", "other"],
    "fr": ["one", "other"],  # vereinfacht
    "es": ["one", "other"],
    "it": ["one", "other"],
    "pt": ["one", "other"],
    "ru": ["one", "few", "many", "other"],
    "zh": ["other"],
    "ja": ["other"],
    "ko": ["one", "other"],
    "sv": ["one", "other"],
    "el": ["one", "other"],
    "ar": ["zero", "one", "two", "few", "many", "other"],
    "he": ["one", "two", "many", "other"],
}


class UITranslationService:
    """SQLite-basierte Übersetzungsverwaltung für UI-Strings."""

    def __init__(self, db_path: Path | str | None = None, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(DEFAULT_BASE_DIR)
        self.db_path = Path(db_path) if db_path else self.base_dir / "ui_translations.db"
        self._locales_cache: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialisiere SQLite-Datenbank für UI-Übersetzungen."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ui_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                locale TEXT NOT NULL,
                value TEXT NOT NULL,
                namespace TEXT DEFAULT 'global',
                source TEXT DEFAULT 'manual',
                -- 'manual' | 'llm_generated' | 'bulk_imported' | 'auto_generated'
                confidence REAL,
                version INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(key, locale, namespace)
            );
            CREATE INDEX IF NOT EXISTS idx_ui_translations_locale
                ON ui_translations(locale);
            CREATE INDEX IF NOT EXISTS idx_ui_translations_namespace
                ON ui_translations(namespace);
            CREATE TABLE IF NOT EXISTS ui_translation_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
        conn.close()
        logger.info("UI-Translation DB initialisiert: %s", self.db_path)

    def _get_conn(self):
        """Erstelle eine neue Datenbankverbindung."""
        import sqlite3
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def set_translation(self, key: str, locale: str, value: str,
                        namespace: str = "global", source: str = "manual") -> None:
        """Speichere oder aktualisiere eine Übersetzung."""
        now = datetime.now(UTC).isoformat()
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO ui_translations (key, locale, value, namespace, source,
                                            confidence, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, 1, ?, ?)
                ON CONFLICT(key, locale, namespace) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    version = ui_translations.version + 1,
                    updated_at = excluded.updated_at
            """, (key, locale, value, namespace, source, now, now))
            conn.commit()
            # Cache invalidieren
            self._locales_cache.pop(locale, None)
            logger.debug("UI-Übersetzung gespeichert: %s [%s/%s]", key, locale, namespace)
        finally:
            conn.close()

    def get_translation(self, key: str, locale: str,
                        namespace: str = "global") -> str | None:
        """Hole eine einzelne Übersetzung."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM ui_translations WHERE key = ? AND locale = ? AND namespace = ?",
            (key, locale, namespace)
        ).fetchone()
        conn.close()
        return row["value"] if row else None

    def get_translations_bulk(self, locale: str, namespace: str = "global",
                               keys: list[str] | None = None) -> dict[str, str]:
        """Hole mehrere Übersetzungen auf einmal."""
        conn = self._get_conn()
        if keys:
            placeholders = ",".join("?" for _ in keys)
            query = f"SELECT key, value FROM ui_translations WHERE locale = ? AND namespace = ? AND key IN ({placeholders})"
            params: list[Any] = [locale, namespace] + keys
        else:
            query = "SELECT key, value FROM ui_translations WHERE locale = ? AND namespace = ?"
            params = [locale, namespace]

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}

    def get_all_keys(self, namespace: str = "global") -> list[str]:
        """Liste aller bekannten Keys."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT key FROM ui_translations WHERE namespace = ?",
            (namespace,)
        ).fetchall()
        conn.close()
        return [r["key"] for r in rows]

    def delete_translation(self, key: str, locale: str,
                           namespace: str = "global") -> bool:
        """Lösche eine Übersetzung."""
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM ui_translations WHERE key = ? AND locale = ? AND namespace = ?",
            (key, locale, namespace)
        )
        conn.commit()
        affected = conn.total_changes
        conn.close()
        self._locales_cache.pop(locale, None)
        return affected > 0

    def bulk_import(self, translations: dict[str, dict[str, str]],
                    namespace: str = "global", source: str = "bulk_imported") -> int:
        """
        Importiere mehrere Übersetzungen auf einmal.
        Format: { locale: { key: value, ... }, ... }
        """
        count = 0
        for locale, kv in translations.items():
            for key, value in kv.items():
                self.set_translation(key, locale, value, namespace, source)
                count += 1
        return count

    # ------------------------------------------------------------------
    # Fallback-Resolution
    # ------------------------------------------------------------------

    def resolve(self, key: str, locale: str,
                namespace: str = "global") -> str:
        """
        Resolviere eine Übersetzung mit Fallback-Kette:
        locale → DEFAULT_LOCALE → en → key
        """
        chain = [locale, "de", "en"]
        for loc in chain:
            val = self.get_translation(key, loc, namespace)
            if val is not None:
                return val
        return key  # Letzter Fallback

    def resolve_bulk(self, locale: str, namespace: str = "global",
                     keys: list[str] | None = None) -> dict[str, str]:
        """Bulk-Resolution mit Fallback-Kette."""
        if keys is None:
            keys = self.get_all_keys(namespace)

        result = {}
        primary = self.get_translations_bulk(locale, namespace, keys)
        fallback_de = self.get_translations_bulk("de", namespace,
                                                  [k for k in keys if k not in primary]) if locale != "de" else {}
        fallback_en = self.get_translations_bulk("en", namespace,
                                                  [k for k in keys if k not in primary and k not in fallback_de])

        result.update(primary)
        result.update(fallback_de)
        result.update(fallback_en)

        # Letzter Fallback: Key selbst
        for k in keys:
            if k not in result:
                result[k] = k

        return result

    # ------------------------------------------------------------------
    # Cache-Management
    # ------------------------------------------------------------------

    def _get_locale_cache(self, locale: str) -> dict[str, str]:
        """Lokalen Cache befüllen oder zurückgeben."""
        if locale not in self._locales_cache:
            self._locales_cache[locale] = self.get_translations_bulk(locale)
        return self._locales_cache[locale]

    def invalidate_cache(self, locale: str | None = None) -> None:
        """Cache invalidieren."""
        if locale:
            self._locales_cache.pop(locale, None)
        else:
            self._locales_cache.clear()

    # ------------------------------------------------------------------
    # Statistiken
    # ------------------------------------------------------------------

    def get_stats(self, namespace: str = "global") -> dict[str, Any]:
        """Übersetzungsstatistiken pro Sprache."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT locale, COUNT(*) as total,
                   SUM(CASE WHEN source = 'manual' THEN 1 ELSE 0 END) as manual,
                   SUM(CASE WHEN source = 'bulk_imported' THEN 1 ELSE 0 END) as bulk,
                   SUM(CASE WHEN source = 'llm_generated' THEN 1 ELSE 0 END) as llm
            FROM ui_translations
            WHERE namespace = ?
            GROUP BY locale
        """, (namespace,)).fetchall()
        conn.close()
        return {r["locale"]: dict(r) for r in rows}

    def get_coverage(self, namespace: str = "global") -> dict[str, Any]:
        """Coverage-Report: Welche Sprachen wie vollständig sind."""
        all_keys = set(self.get_all_keys(namespace))
        if not all_keys:
            return {}

        result = {}
        for locale in DEFAULT_LOCALES:
            translated = set()
            for kv in self.get_translations_bulk(locale, namespace).values():
                if kv:
                    translated.add(kv)
            coverage = len(translated & all_keys) / len(all_keys) * 100
            result[locale] = {
                "total_keys": len(all_keys),
                "translated": len(translated & all_keys),
                "coverage_pct": round(coverage, 1),
            }
        return result
