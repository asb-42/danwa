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
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.core.config import settings
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TranslationJob:
    job_id: str
    target_locales: list[str]
    namespace: str
    status: str = "pending"  # pending | running | completed | failed
    total_strings: int = 0
    completed_strings: int = 0
    current_key: str = ""
    current_locale: str = ""
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def progress(self) -> float:
        if self.total_strings == 0:
            return 0.0
        return round(self.completed_strings / self.total_strings * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "target_locales": self.target_locales,
            "namespace": self.namespace,
            "total_strings": self.total_strings,
            "completed_strings": self.completed_strings,
            "current_key": self.current_key,
            "current_locale": self.current_locale,
            "progress_pct": self.progress(),
            "results": self.results,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class TranslationJobRegistry:
    _jobs: dict[str, TranslationJob] = {}
    _lock = threading.Lock()
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="i18n-translate")

    @classmethod
    def submit(cls, job: TranslationJob, fn) -> str:
        with cls._lock:
            cls._jobs[job.job_id] = job
        cls._executor.submit(fn)
        return job.job_id

    @classmethod
    def get(cls, job_id: str) -> TranslationJob | None:
        with cls._lock:
            return cls._jobs.get(job_id)

    @classmethod
    def list_all(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return [j.to_dict() for j in cls._jobs.values()]

logger = logging.getLogger(__name__)

DEFAULT_BASE_DIR = Path("data/i18n")
DEFAULT_LOCALES = [
    "de",
    "en",
    "fr",
    "es",
    "it",
    "pt",
    "ru",
    "zh",
    "ja",
    "ko",
    "sv",
    "el",
    # Optionale RTL-Sprachen:
    # "ar", "he",
]

LOCALE_NAMES: dict[str, str] = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "sv": "Svenska",
    "el": "Ελληνικά",
    "ar": "العربية",
    "he": "עברית",
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

    def set_translation(self, key: str, locale: str, value: str, namespace: str = "global", source: str = "manual") -> None:
        """Speichere oder aktualisiere eine Übersetzung."""
        now = datetime.now(UTC).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT INTO ui_translations (key, locale, value, namespace, source,
                                             confidence, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, 1, ?, ?)
                ON CONFLICT(key, locale, namespace) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    version = ui_translations.version + 1,
                    updated_at = excluded.updated_at
            """,
                (key, locale, value, namespace, source, now, now),
            )
            conn.commit()
            # Cache invalidieren
            self._locales_cache.pop(locale, None)
            logger.debug("UI-Übersetzung gespeichert: %s [%s/%s]", key, locale, namespace)
        finally:
            conn.close()

    def get_translation(self, key: str, locale: str, namespace: str = "global") -> str | None:
        """Hole eine einzelne Übersetzung."""
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM ui_translations WHERE key = ? AND locale = ? AND namespace = ?", (key, locale, namespace)).fetchone()
        conn.close()
        return row["value"] if row else None

    def get_translations_bulk(self, locale: str, namespace: str = "global", keys: list[str] | None = None) -> dict[str, str]:
        """Hole mehrere Übersetzungen auf einmal. Befüllt den lokalen Cache."""
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
        result = {r["key"]: r["value"] for r in rows}
        # Cache befüllen
        if locale not in self._locales_cache:
            self._locales_cache[locale] = {}
        if keys is None:
            self._locales_cache[locale] = dict(result)
        else:
            self._locales_cache[locale].update(result)
        return result

    def get_all_keys(self, namespace: str = "global") -> list[str]:
        """Liste aller bekannten Keys aus englischer Referenz (DB + bundled)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT key FROM ui_translations WHERE locale = 'en' AND namespace = ?",
            (namespace,),
        ).fetchall()
        conn.close()
        db_keys = {r["key"] for r in rows}

        bundled = self._scan_bundled_loaders()
        en_bundled = set(bundled.get("en", {}).keys())

        return sorted(db_keys | en_bundled)

    def delete_translation(self, key: str, locale: str, namespace: str = "global") -> bool:
        """Lösche eine Übersetzung."""
        conn = self._get_conn()
        conn.execute("DELETE FROM ui_translations WHERE key = ? AND locale = ? AND namespace = ?", (key, locale, namespace))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        self._locales_cache.pop(locale, None)
        return affected > 0

    def bulk_import(self, translations: dict[str, dict[str, str]], namespace: str = "global", source: str = "bulk_imported") -> int:
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

    def resolve(self, key: str, locale: str, namespace: str = "global") -> str:
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

    def resolve_bulk(self, locale: str, namespace: str = "global", keys: list[str] | None = None) -> dict[str, str]:
        """Bulk-Resolution mit Fallback-Kette."""
        if keys is None:
            keys = self.get_all_keys(namespace)

        result = {}
        primary = self.get_translations_bulk(locale, namespace, keys)
        fallback_de = self.get_translations_bulk("de", namespace, [k for k in keys if k not in primary]) if locale != "de" else {}
        fallback_en = self.get_translations_bulk("en", namespace, [k for k in keys if k not in primary and k not in fallback_de])

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

    def _scan_bundled_loaders(self) -> dict[str, dict[str, str]]:
        """Scan frontend loader JS files and extract key→value dicts."""
        root = Path(__file__).resolve().parent.parent.parent
        loader_dir = root / "frontend" / "src" / "lib" / "i18n" / "loaders"
        if not loader_dir.exists():
            return {}

        result = {}
        for js_file in loader_dir.glob("*.js"):
            locale = js_file.stem
            content = js_file.read_text(encoding="utf-8")
            keys = {}
            for match in __import__("re").finditer(r"^\s*['\"]([^'\"]+)['\"]\s*:\s*['\"]((?:[^'\"\\]|\\.)*)['\"]", content, __import__("re").MULTILINE):
                keys[match.group(1)] = match.group(2)
            if keys:
                result[locale] = keys
        return result

    def get_stats(self, namespace: str = "global") -> dict[str, Any]:
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT locale, COUNT(*) as total,
                    SUM(CASE WHEN source = 'manual' THEN 1 ELSE 0 END) as manual,
                    SUM(CASE WHEN source = 'bulk_imported' THEN 1 ELSE 0 END) as bulk,
                    SUM(CASE WHEN source = 'llm_generated' THEN 1 ELSE 0 END) as llm,
                    MAX(updated_at) as last_updated
            FROM ui_translations
            WHERE namespace = ?
            GROUP BY locale
        """,
            (namespace,),
        ).fetchall()
        db_stats = {r["locale"]: dict(r) for r in rows}
        conn.close()

        bundled = self._scan_bundled_loaders()
        for locale, keys in bundled.items():
            if locale not in db_stats:
                db_stats[locale] = {
                    "locale": locale,
                    "total": len(keys),
                    "manual": 0,
                    "bulk": 0,
                    "llm": 0,
                    "last_updated": None,
                }
            else:
                db_stats[locale]["total"] = max(db_stats[locale]["total"], len(keys))

        for locale, s in db_stats.items():
            s["translated"] = (s.get("llm") or 0) + (s.get("manual") or 0) + (s.get("bulk") or 0)

        return db_stats

    def get_coverage(self, namespace: str = "global") -> dict[str, Any]:
        bundled = self._scan_bundled_loaders()
        en_keys = set(self.get_all_keys(namespace))
        if not en_keys:
            en_keys = set(bundled.get("en", {}).keys())
        if not en_keys:
            return {}

        result = {}
        for locale in DEFAULT_LOCALES:
            if locale in bundled:
                bundle_keys = set(bundled[locale].keys())
                translated = len(bundle_keys & en_keys)
            else:
                db_keys = set(self.get_translations_bulk(locale, namespace).keys())
                translated = len(db_keys & en_keys)
            coverage = translated / len(en_keys) * 100
            result[locale] = {
                "total_keys": len(en_keys),
                "translated": translated,
                "coverage_pct": round(coverage, 1),
            }

        conn = self._get_conn()
        custom_rows = conn.execute(
            "SELECT DISTINCT locale FROM ui_translations WHERE locale NOT IN ({}) AND namespace = ?".format(
                ",".join("?" for _ in DEFAULT_LOCALES)
            ),
            (*DEFAULT_LOCALES, namespace),
        ).fetchall()
        for row in custom_rows:
            locale = row["locale"]
            db_keys = set(self.get_translations_bulk(locale, namespace).keys())
            translated = len(db_keys & en_keys)
            coverage = translated / len(en_keys) * 100
            result[locale] = {
                "total_keys": len(en_keys),
                "translated": translated,
                "coverage_pct": round(coverage, 1),
            }
        conn.close()

        return result

    # ------------------------------------------------------------------
    # LLM-basierte Übersetzung
    # ------------------------------------------------------------------

    def translate_via_llm(
        self,
        key: str,
        source_text: str,
        target_locale: str,
        llm_profile_id: str | None = None,
        llm=None,
        job: TranslationJob | None = None,
    ) -> str:
        from backend.services.llm_service import LLMService
        from backend.services.profile_service import ProfileService

        if llm is None:
            ps = ProfileService()
            if llm_profile_id is None:
                llm_profile_id = self._select_llm_for_locale(target_locale, ps)
            llm = LLMService(profile_id=llm_profile_id, profile_service=ps)

        system_prompt = (
            f"You are a professional UI/UX translator. "
            f"Translate the following English UI string to {self._locale_name(target_locale)}. "
            f"Keep it concise, precise, and consistent with UI conventions. "
            f"Do NOT translate placeholder variables like {{param}}. "
            f"Output ONLY the translation, nothing else."
        )

        try:
            result = llm.generate_sync(
                prompt=source_text,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=max(30, len(source_text) // 4),
            )
            translated = result.content.strip()
            self.set_translation(key, target_locale, translated, source="llm_generated")
            if job:
                job.completed_strings += 1
                job.current_key = key
                job.current_locale = target_locale
            return translated
        except Exception as exc:
            logger.error("LLM-Übersetzung fehlgeschlagen für %s → %s: %s", key, target_locale, exc)
            return source_text

    def bulk_translate(self, target_locales: list[str] | None = None, namespace: str = "global") -> dict[str, Any]:
        """Übersetze alle fehlenden Strings per LLM.

        Liest alle bekannten Keys aus der englischen Datei und übersetzt
        fehlende Strings in die Zielsprachen.
        """
        if target_locales is None:
            target_locales = [loc for loc in DEFAULT_LOCALES if loc not in ("de", "en")]

        all_keys = self.get_all_keys(namespace)
        results = {}

        llm_profile = settings.service_llm_profile_id or "(not set — using fallback)"
        logger.info("Bulk-Translation gestartet: locales=%s, LLM=%s", target_locales, llm_profile)

        for locale in target_locales:
            existing = self.get_translations_bulk(locale, namespace)
            missing = [k for k in all_keys if k not in existing or not existing[k]]

            if not missing:
                results[locale] = {"status": "complete", "translated": 0}
                continue

            logger.info("Übersetze %d Strings nach %s …", len(missing), locale)
            translated_count = 0
            for key in missing:
                en_val = self.get_translation(key, "en", namespace)
                if en_val:
                    self.translate_via_llm(key, en_val, locale)
                    translated_count += 1

            logger.info("Fertig für %s: %d Strings übersetzt", locale, translated_count)
            results[locale] = {"status": "ok", "translated": translated_count, "total_missing": len(missing)}

        return results

    def bulk_translate_async(
        self,
        target_locales: list[str] | None = None,
        namespace: str = "global",
    ) -> str:
        """Start an async bulk translation job. Returns job_id immediately."""
        from backend.services.llm_service import LLMService
        from backend.services.profile_service import ProfileService

        if target_locales is None:
            target_locales = [loc for loc in DEFAULT_LOCALES if loc not in ("de", "en")]

        job = TranslationJob(
            job_id=str(uuid.uuid4())[:8],
            target_locales=target_locales,
            namespace=namespace,
        )

        def _run():
            job.status = "running"
            job.started_at = datetime.now(UTC).isoformat()
            try:
                ps = ProfileService()
                llm_profile_id = settings.service_llm_profile_id
                if not llm_profile_id:
                    llm_profile_id = self._select_llm_for_locale(target_locales[0], ps)
                llm = LLMService(profile_id=llm_profile_id, profile_service=ps)

                all_keys = self.get_all_keys(namespace)
                total = 0
                for locale in target_locales:
                    existing = self.get_translations_bulk(locale, namespace)
                    missing = [k for k in all_keys if k not in existing or not existing[k]]
                    total += len(missing)

                job.total_strings = total
                logger.info("Async bulk-translation: job=%s, total=%d, locales=%s, LLM=%s",
                            job.job_id, total, target_locales, llm_profile_id)

                for locale in target_locales:
                    existing = self.get_translations_bulk(locale, namespace)
                    missing = [k for k in all_keys if k not in existing or not existing[k]]

                    if not missing:
                        job.results[locale] = {"status": "complete", "translated": 0}
                        continue

                    translated_count = 0
                    for key in missing:
                        en_val = self.get_translation(key, "en", namespace)
                        if en_val:
                            self.translate_via_llm(key, en_val, locale, llm=llm, job=job)
                            translated_count += 1

                    job.results[locale] = {"status": "ok", "translated": translated_count, "total_missing": len(missing)}
                    logger.info("Locale %s done: %d/%d translated", locale, translated_count, len(missing))

                job.status = "completed"
                job.finished_at = datetime.now(UTC).isoformat()
                logger.info("Async bulk-translation completed: job=%s", job.job_id)
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(UTC).isoformat()
                logger.error("Async bulk-translation failed: job=%s, error=%s", job.job_id, exc)

        TranslationJobRegistry.submit(job, _run)
        return job.job_id

    def get_locale_details(self, locale: str, namespace: str = "global") -> dict[str, Any]:
        conn = self._get_conn()
        en_rows = conn.execute(
            "SELECT key, value FROM ui_translations WHERE locale = 'en' AND namespace = ?",
            (namespace,),
        ).fetchall()
        en_keys = {r["key"]: r["value"] for r in en_rows}

        bundled = self._scan_bundled_loaders()
        if not en_keys and "en" in bundled:
            en_keys = bundled["en"]

        target_rows = conn.execute(
            "SELECT key, value, source, confidence, version, created_at, updated_at FROM ui_translations WHERE locale = ? AND namespace = ?",
            (locale, namespace),
        ).fetchall()
        target_map = {r["key"]: dict(r) for r in target_rows}
        conn.close()

        if locale in bundled:
            for key, val in bundled[locale].items():
                if key not in target_map:
                    target_map[key] = {
                        "key": key, "value": val, "source": "bundled",
                        "confidence": None, "version": None,
                        "created_at": None, "updated_at": None,
                    }

        total_keys = len(en_keys)
        translated = 0
        missing = 0
        llm_generated = 0
        manual = 0
        strings = []

        for key, en_value in sorted(en_keys.items()):
            if key in target_map:
                t = target_map[key]
                translated += 1
                if t["source"] == "llm_generated":
                    llm_generated += 1
                elif t["source"] == "manual":
                    manual += 1
                elif t["source"] == "bundled":
                    manual += 1
                strings.append(
                    {
                        "key": key,
                        "source_value": en_value,
                        "translated_value": t["value"],
                        "status": "translated",
                        "source": t["source"],
                        "confidence": t["confidence"],
                        "version": t["version"],
                        "created_at": t["created_at"],
                        "updated_at": t["updated_at"],
                    }
                )
            else:
                missing += 1
                strings.append(
                    {
                        "key": key,
                        "source_value": en_value,
                        "translated_value": None,
                        "status": "missing",
                        "source": None,
                        "confidence": None,
                        "version": None,
                        "created_at": None,
                        "updated_at": None,
                    }
                )

        return {
            "locale": locale,
            "namespace": namespace,
            "total_keys": total_keys,
            "translated": translated,
            "missing": missing,
            "coverage_pct": round(translated / total_keys * 100, 1) if total_keys > 0 else 0.0,
            "llm_generated": llm_generated,
            "manual": manual,
            "strings": strings,
        }

    def register_custom_locale(self, locale: str, name: str | None = None, is_rtl: bool = False) -> dict[str, Any]:
        """Register a new custom locale that is not in DEFAULT_LOCALES.

        Adds the locale to the metadata table so it appears in the locales list.
        """
        conn = self._get_conn()
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO ui_translation_metadata (key, value) VALUES (?, ?)",
            (f"custom_locale:{locale}", json.dumps({"name": name or locale, "is_rtl": is_rtl, "registered_at": now})),
        )
        conn.commit()
        conn.close()
        logger.info("Custom locale registered: %s", locale)
        return {"locale": locale, "name": name or locale, "is_rtl": is_rtl, "registered_at": now}

    def get_custom_locales(self) -> list[dict[str, Any]]:
        """Return all custom-registered locales."""
        import json

        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM ui_translation_metadata WHERE key LIKE 'custom_locale:%'").fetchall()
        conn.close()
        result = []
        for row in rows:
            locale = row["key"].replace("custom_locale:", "")
            data = json.loads(row["value"])
            result.append({"locale": locale, **data})
        return result

    def _select_llm_for_locale(self, locale: str, ps) -> str:
        """Wählt ein geeignetes LLM basierend auf der Zielsprache."""
        if settings.service_llm_profile_id:
            return settings.service_llm_profile_id
        locale_map = {
            "zh": "openrouter-deepseek/deepseek-chat",
            "ja": "openrouter-deepseek/deepseek-chat",
            "ko": "openrouter-deepseek/deepseek-chat",
            "hi": "openrouter/google/gemini-2.5-flash",
            "ar": "openrouter/meta-llama/llama-3.1-8b-instruct",
            "ru": "openrouter/meta-llama/llama-3.1-8b-instruct",
            "uk": "openrouter/meta-llama/llama-3.1-8b-instruct",
        }
        return locale_map.get(locale, "openrouter-claude")

    @staticmethod
    def _locale_name(code: str) -> str:
        return LOCALE_NAMES.get(code, code)
