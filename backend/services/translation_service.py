"""Translation service — LLM-based translation with back-translation QA.

Provides high-quality translation of module content (prompt templates,
argumentation patterns, etc.) using configured LLM profiles. Implements
a two-pass translation pipeline:

1. Forward translation: EN source → target language
2. Back-translation: target language → EN for quality verification
3. Optional human review / approval workflow

The translation cache in blueprints.db stores results for reuse and
supports incremental updates when source content changes.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

# Supported target languages (ISO 639-1 codes)
SUPPORTED_LANGUAGES = {"de", "fr", "es", "it", "pt", "nl", "pl", "cs", "zh", "ja", "ko"}


class TranslationEntry(BaseModel):
    """A single translation cache entry."""

    id: str
    module_id: str
    file_path: str
    source_language: str = "en"
    target_language: str
    source_hash: str = ""
    source_content: str = ""
    translated_content: str | None = None
    back_translation: str | None = None
    quality_score: float = 0.0
    approved: bool = False
    generated_at: str = ""
    generated_by: str = "llm"
    error: str | None = None

    def to_db_tuple(self) -> tuple:
        """Convert to db tuple format."""
        return (
            self.id,
            self.module_id,
            self.file_path,
            self.source_language,
            self.target_language,
            self.source_hash,
            self.source_content,
            self.translated_content,
            self.back_translation,
            self.quality_score,
            self.approved,
            self.generated_at,
            self.generated_by,
            self.error,
        )

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> TranslationEntry:
        """Construct an instance from db row."""
        return cls(
            id=row["id"],
            module_id=row["module_id"],
            file_path=row["file_path"],
            source_language=row.get("source_language", "en"),
            target_language=row.get("target_language", "de"),
            source_hash=row.get("source_hash") or "",
            source_content=row.get("source_content") or "",
            translated_content=row.get("translated_content"),
            back_translation=row.get("back_translation"),
            quality_score=row.get("quality_score") or 0.0,
            approved=bool(row.get("approved", 0)),
            generated_at=row.get("generated_at") or "",
            generated_by=row.get("generated_by") or "system",
            error=row.get("error"),
        )


class TranslationRequest(BaseModel):
    """Request model for a translation operation."""

    module_id: str
    target_language: str = "de"
    force: bool = False
    llm_profile_id: str | None = None  # Override default LLM for translation
    skip_back_translation: bool = False  # Skip back-translation QA (faster but lower quality)
    approve_automatically: bool = False  # Auto-approve if quality_score >= threshold
    quality_threshold: float = 0.7  # Minimum quality score for auto-approval


class TranslationResult(BaseModel):
    """Result of a translation operation."""

    module_id: str
    target_language: str
    files_translated: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    quality_scores: dict[str, float] = Field(default_factory=dict)
    back_translation_scores: dict[str, float] = Field(default_factory=dict)
    status: str = "ok"  # "ok", "partial", "error"
    estimated_cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TranslationService:
    """Handles LLM-based translation of module content with quality assurance.

    The translation pipeline:
    1. Load source EN content from module files or DB cache
    2. Translate EN → target language using configured LLM
    3. Back-translate target → EN for quality verification
    4. Compare source and back-translation to compute quality score
    5. Store results in DB with approval status

    Translation quality is ensured through:
    - Semantic faithfulness scoring via LLM comparison
    - Back-translation consistency check
    - Human review workflow (pending/approved/rejected states)
    - Source hash tracking to detect content changes requiring re-translation
    """

    # Prompt templates for translation (can be overridden via module manifest)
    _FWD = (
        "You are a professional technical translator. Translate the following "
        "text from English ({source_lang}) to {target_lang}. Maintain the "
        "technical meaning, tone, and structure. Do NOT translate variable "
        "placeholders like {{role}}, {{topic}}, {{context}}, etc. — keep "
        "them exactly as-is.\n\n"
    )
    _FWD_END = "\nSource text:\n{source_text}\n\nTranslated text in {target_lang}:"
    FORWARD_TRANSLATION_PROMPT = _FWD + _FWD_END

    BACK_TRANSLATION_PROMPT = (
        "You are a professional technical translator. Translate the following "
        "text from {target_lang} back to English. This is used for quality "
        "verification of a previous translation. Be as literal and faithful "
        "as possible to the translated text.\n\n"
        "Source text ({target_lang}):\n"
        "{translated_text}\n\n"
        "Back-translation in English:"
    )

    QUALITY_CHECK_PROMPT = """Compare the following two English texts and rate the semantic faithfulness of the translation on a scale of 0.0 to 1.0.

A score of 1.0 means the back-translation is semantically identical to the original.
A score of 0.0 means the meaning is completely different or lost.

Consider: technical accuracy, intent preservation, completeness, and absence of hallucinated content.

Original English:
{original_text}

Back-translation (English):
{back_translation}

Respond with ONLY a valid JSON object:
{{"score": 0.0-1.0, "issues": ["issue1", "issue2"]}}"""

    def __init__(
        self,
        db_path: Path | str | None = None,
        modules_dir: Path | str | None = None,
        profile_service: ProfileService | None = None,
        llm_profile_id: str | None = None,
    ):
        """Initialise TranslationService."""
        self.db_path = Path(db_path) if db_path else Path("data/blueprints.db")
        self.modules_dir = Path(modules_dir) if modules_dir else Path("modules")
        self._profile_service = profile_service or ProfileService()
        self._llm_profile_id = llm_profile_id
        self._llm_service: LLMService | None = None

    def _get_llm_service(self) -> LLMService:
        """Get or create the LLM service for translation calls."""
        if self._llm_service is None:
            self._llm_service = LLMService(
                profile_id=self._llm_profile_id,
                profile_service=self._profile_service,
            )
        return self._llm_service

    def _get_db(self) -> sqlite3.Connection:
        """Get a fresh database connection with WAL mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        from backend.blueprints.migrations import run_migrations

        run_migrations(self.db_path)
        return conn

    def _compute_source_hash(self, content: str) -> str:
        """Compute SHA-256[:16] hash of source content for change detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _semantic_similarity_score(self, text1: str, text2: str) -> float:
        """
        Compute a semantic similarity score between two English texts.

        Uses an LLM call for accurate semantic comparison rather than
        simple string matching. Returns a score between 0.0 and 1.0.
        """
        llm = self._get_llm_service()
        # Use a lower temperature for deterministic scoring
        prompt = self.QUALITY_CHECK_PROMPT.format(
            original_text=text1,
            back_translation=text2,
        )
        try:
            result = llm.generate_sync(
                prompt=prompt,
                system_prompt="You are a translation quality evaluator. Only respond with valid JSON.",
                temperature=0.1,
                max_tokens=256,
                context="Quality Check",
            )
            import re

            match = re.search(r'"score"\s*:\s*([\d.]+)', result.content)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
        except Exception as e:
            logger.warning("Quality check LLM call failed: %s", e)

        # Fallback: token-overlap based similarity
        return self._token_overlap_score(text1, text2)

    def _token_overlap_score(self, text1: str, text2: str) -> float:
        """Fallback similarity score based on normalized token overlap."""
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0.0

    def _get_source_files(
        self,
        module_id: str,
        target_lang: str,
        force: bool = False,
    ) -> list[tuple[str, str, str, bool]]:
        """Get list of source files needing translation.

        Returns list of tuples: (file_path, source_content, source_hash, needs_translation)
        """
        conn = self._get_db()
        cursor = conn.cursor()

        # Get all EN source files for this module
        cursor.execute(
            "SELECT file_path, source_hash, source_content "
            "FROM module_translation_cache "
            "WHERE module_id = ? AND (source_language = 'en' OR source_language = ?)",
            (module_id, "en"),
        )
        source_rows = cursor.fetchall()

        if not source_rows:
            conn.close()
            return []

        results = []
        for row in source_rows:
            fpath = row["file_path"]
            source_hash = row["source_hash"]
            source_content = row["source_content"]

            if not force:
                # Check if a valid translation already exists
                cursor.execute(
                    """SELECT quality_score, source_hash as cached_hash,
                       translated_content FROM module_translation_cache
                       WHERE module_id = ? AND file_path = ? AND language = ?
                       AND approved = 1 AND translated_content IS NOT NULL""",
                    (module_id, fpath, target_lang),
                )
                existing = cursor.fetchone()
                if existing:
                    if existing["cached_hash"] == source_hash and existing["quality_score"] >= 0.7:
                        results.append((fpath, source_content, source_hash, False))
                        continue

            results.append((fpath, source_content, source_hash, True))

        conn.close()
        return results

    def translate_module(
        self,
        module_id: str,
        target_language: str = "de",
        force: bool = False,
        llm_profile_id: str | None = None,
        skip_back_translation: bool = False,
        auto_approve: bool = False,
        quality_threshold: float = 0.7,
    ) -> TranslationResult:
        """Translate all files in a module to the target language.

        Args:
            module_id: The module to translate.
            target_language: Target language code (e.g. "de").
            force: Force re-translation even if cache exists.
            llm_profile_id: Override LLM profile for translation.
            skip_back_translation: Skip back-translation QA (faster).
            auto_approve: Auto-approve if quality meets threshold.
            quality_threshold: Minimum score for auto-approval.

        Returns:
            TranslationResult with detailed status.
        """
        if target_language not in SUPPORTED_LANGUAGES and target_language != "en":
            return TranslationResult(
                module_id=module_id,
                target_language=target_language,
                status="error",
                errors=[f"Unsupported language: {target_language}. Supported: {SUPPORTED_LANGUAGES}"],
            )

        if target_language == "en":
            return TranslationResult(
                module_id=module_id,
                target_language=target_language,
                status="ok",
                files_translated=0,
                files_skipped=0,
                quality_scores={},
                warnings=["English is the source language — no translation needed"],
            )

        # Temporarily override LLM if specified
        original_profile_id = self._llm_profile_id
        if llm_profile_id:
            self._llm_profile_id = llm_profile_id
            self._llm_service = None  # Force recreation

        try:
            source_files = self._get_source_files(module_id, target_language, force)

            if not source_files:
                return TranslationResult(
                    module_id=module_id,
                    target_language=target_language,
                    status="ok",
                    files_translated=0,
                    files_skipped=0,
                    quality_scores={},
                    warnings=["No source files found or all translations are current"],
                )

            translated = 0
            skipped = 0
            errored = 0
            quality_scores: dict[str, float] = {}
            back_trans_scores: dict[str, float] = {}
            errors: list[str] = []
            warnings: list[str] = []
            now = datetime.now(UTC).isoformat()

            conn = self._get_db()
            cursor = conn.cursor()
            llm = self._get_llm_service()

            for fpath, source_content, source_hash, needs_translation in source_files:
                cache_id = f"{module_id}:{fpath}:{target_language}"

                if not needs_translation:
                    skipped += 1
                    # Fetch existing quality score
                    cursor.execute("SELECT quality_score FROM module_translation_cache WHERE id = ?", (cache_id,))
                    row = cursor.fetchone()
                    quality_scores[fpath] = row["quality_score"] if row else 0.0
                    continue

                try:
                    # Step 1: Forward translation (EN → target) with retry
                    forward_prompt = self.FORWARD_TRANSLATION_PROMPT.format(
                        source_lang="en",
                        target_lang=target_language,
                        source_text=source_content,
                    )
                    forward_result = None
                    for attempt in range(2):
                        try:
                            forward_result = llm.generate_sync(
                                prompt=forward_prompt,
                                system_prompt=f"You are a professional translator translating from English to {target_language}. "
                                f"Preserve technical terms and placeholder variables.",
                                temperature=0.3,
                                max_tokens=max(512, len(source_content) // 2),
                                context="Translate",
                            )
                            if forward_result and forward_result.content.strip():
                                break
                        except Exception as e:
                            if attempt == 0:
                                logger.warning(
                                    "Forward translation attempt 1 failed for %s/%s → %s, retrying: %s",
                                    module_id,
                                    fpath,
                                    target_language,
                                    e,
                                )
                                time.sleep(1)
                                continue
                            raise
                    if forward_result is None:
                        raise RuntimeError(f"Forward translation failed after retry for {fpath}")
                    translated_content = forward_result.content.strip()
                    quality_scores[fpath] = 0.0  # temporary, will be updated
                    back_trans_scores[fpath] = 0.0

                    if not translated_content:
                        raise ValueError("Empty translation result")

                    # Step 2: Back-translation (target → EN) for QA
                    if skip_back_translation:
                        back_translation = ""
                        quality_score = 0.5  # Default for unchecked translations
                        warnings.append(f"Skipped back-translation QA for {fpath}")
                    else:
                        back_prompt = self.BACK_TRANSLATION_PROMPT.format(
                            target_lang=target_language,
                            translated_text=translated_content,
                        )
                        back_result = llm.generate_sync(
                            prompt=back_prompt,
                            system_prompt="You are a professional translator translating back to English for quality verification.",
                            temperature=0.3,
                            max_tokens=max(512, len(translated_content) // 2),
                            context="Back-Translate",
                        )
                        back_translation = back_result.content.strip()

                        # Step 3: Quality scoring via LLM comparison
                        quality_score = self._semantic_similarity_score(source_content, back_translation)

                    quality_scores[fpath] = round(quality_score, 3)
                    back_trans_scores[fpath] = round(quality_score, 3)

                    # Determine approval
                    approved = auto_approve and quality_score >= quality_threshold

                    # Step 4: Store in DB
                    cursor.execute(
                        """INSERT OR REPLACE INTO module_translation_cache
                            (id, module_id, file_path, language,
                             translated_content, source_hash, quality_score,
                             generated_at, generated_by, approved)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            cache_id,
                            module_id,
                            fpath,
                            target_language,
                            translated_content,
                            source_hash,
                            quality_score,
                            now,
                            "translation-service",
                            1 if approved else 0,
                        ),
                    )

                    if approved:
                        logger.info(
                            "Auto-approved translation: %s/%s (score=%.3f)",
                            module_id,
                            fpath,
                            quality_score,
                        )

                    translated += 1

                    # Cost estimation (rough: 3 chars ≈ 1 token)
                    total_chars = len(source_content) + len(translated_content)
                    if back_translation:
                        total_chars += len(back_translation)

                except Exception as e:
                    errored += 1
                    errors.append(f"Failed to translate {fpath}: {e}")
                    logger.error("Translation failed for %s/%s: %s", module_id, fpath, e)

                    # Store error entry in cache
                    try:
                        cursor.execute(
                            """INSERT OR REPLACE INTO module_translation_cache
                                (id, module_id, file_path, language,
                                 translated_content, source_hash, quality_score,
                                 generated_at, generated_by, approved, error)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                cache_id,
                                module_id,
                                fpath,
                                target_language,
                                None,
                                source_hash,
                                0.0,
                                now,
                                "translation-service",
                                0,
                                str(e),
                            ),
                        )
                    except sqlite3.Error as exc:
                        logger.error(
                            "Failed to update translation cache for %s/%s: %s",
                            module_id,
                            fpath,
                            exc,
                        )

            conn.commit()
            conn.close()

            # Log per-module summary when failures occurred
            if errored > 0:
                logger.warning(
                    "Translation summary for %s → %s: %d translated, %d skipped, %d errored (status=%s)",
                    module_id,
                    target_language,
                    translated,
                    skipped,
                    errored,
                    "error" if errored > 0 and translated == 0 else "partial",
                )

            # Determine overall status
            if errored > 0 and translated == 0:
                status = "error"
            elif errored > 0:
                status = "partial"
            elif translated > 0:
                status = "ok"
            else:
                status = "partial"

            # Cost estimation (rough: 3 chars ≈ 1 token, $0.001/1K tokens input+output)
            total_chars = sum(len(sc) for _, sc, _, _ in source_files)
            estimated_cost = (total_chars / 3000) * 0.002  # Very rough estimate

            return TranslationResult(
                module_id=module_id,
                target_language=target_language,
                files_translated=translated,
                files_skipped=skipped,
                files_errored=errored,
                quality_scores=quality_scores,
                back_translation_scores=back_trans_scores,
                status=status,
                estimated_cost_usd=round(estimated_cost, 6),
                errors=errors,
                warnings=warnings,
            )

        finally:
            # Restore original profile
            if llm_profile_id:
                self._llm_profile_id = original_profile_id
                self._llm_service = None

    def get_translation(
        self,
        module_id: str,
        file_path: str,
        target_language: str,
    ) -> TranslationEntry | None:
        """Get a specific cached translation from the database."""
        conn = self._get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, module_id, file_path, source_language, language as target_language,
                      source_hash, source_content, translated_content,
                      back_translation, quality_score, approved, generated_at,
                      generated_by, error
               FROM module_translation_cache
               WHERE module_id = ? AND file_path = ? AND language = ?""",
            (module_id, file_path, target_language),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return TranslationEntry.from_db_row(dict(row))
        return None

    def get_all_translations(
        self,
        module_id: str,
        target_language: str | None = None,
        approved_only: bool = False,
    ) -> list[TranslationEntry]:
        """Get all translation entries for a module, optionally filtered by language and approval."""
        conn = self._get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """SELECT id, module_id, file_path, source_language, language as target_language,
                           source_hash, source_content, translated_content,
                           back_translation, quality_score, approved, generated_at,
                           generated_by, error
                    FROM module_translation_cache
                    WHERE module_id = ? AND source_language = 'en'"""
        params: list[Any] = [module_id]

        if target_language:
            query += " AND language = ?"
            params.append(target_language)

        if approved_only:
            query += " AND approved = 1"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [TranslationEntry.from_db_row(dict(row)) for row in rows]

    def approve_translation(
        self,
        module_id: str,
        file_path: str,
        target_language: str,
        approved: bool = True,
    ) -> bool:
        """Approve or reject a cached translation."""
        conn = self._get_db()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE module_translation_cache
               SET approved = ?
               WHERE module_id = ? AND file_path = ? AND language = ?""",
            (1 if approved else 0, module_id, file_path, target_language),
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def invalidate_translation(
        self,
        module_id: str,
        file_path: str | None = None,
        target_language: str | None = None,
    ) -> int:
        """Invalidate (remove) cached translations, forcing re-translation.

        Args:
            module_id: The module to invalidate.
            file_path: If specified, only this file. Otherwise all files.
            target_language: If specified, only this language. Otherwise all languages.

        Returns:
            Number of entries invalidated.
        """
        conn = self._get_db()
        cursor = conn.cursor()

        query = "DELETE FROM module_translation_cache WHERE module_id = ?"
        params: list[Any] = [module_id]

        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)
        if target_language:
            query += " AND language = ?"
            params.append(target_language)

        cursor.execute(query, params)
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    def get_translation_statistics(self, module_id: str) -> dict[str, Any]:
        """Get translation statistics for a module.

        Returns:
            Dict with counts of total, translated, approved, pending entries per language.
        """
        conn = self._get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """SELECT language, COUNT(*) as total,
                      SUM(CASE WHEN translated_content IS NOT NULL THEN 1 ELSE 0 END) as translated,
                      SUM(approved) as approved,
                      AVG(quality_score) as avg_quality
               FROM module_translation_cache
               WHERE module_id = ? AND source_language = 'en'
               GROUP BY language""",
            (module_id,),
        )

        stats = {}
        for row in cursor.fetchall():
            stats[row["language"]] = {
                "total": row["total"],
                "translated": row["translated"],
                "approved": row["approved"],
                "avg_quality": round(row["avg_quality"], 3) if row["avg_quality"] else 0.0,
            }

        conn.close()
        return stats

    def import_source_content(
        self,
        module_id: str,
        file_path: str,
        content: str,
        source_language: str = "en",
    ) -> bool:
        """Import source content into the translation cache.

        This is used when module files are installed/updated to register
        their content for future translation.
        """
        conn = self._get_db()
        cursor = conn.cursor()
        source_hash = self._compute_source_hash(content)
        now = datetime.now(UTC).isoformat()

        try:
            # Ensure module exists in module_registry to satisfy FK constraint
            cursor.execute(
                """INSERT OR IGNORE INTO module_registry
                    (id, name, description, type, category, version,
                     author_json, license, checksum, installed_at,
                     updated_at, enabled, source_schema, tags_json, dependencies)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    module_id,
                    module_id,
                    "",
                    "custom",
                    "prompts",
                    "0.0.0",
                    "{}",
                    "CC-BY-4.0",
                    "",
                    now,
                    now,
                    1,
                    "1.0.0",
                    "[]",
                    "{}",
                ),
            )
            cursor.execute(
                """INSERT OR REPLACE INTO module_translation_cache
                    (id, module_id, file_path, source_language, language,
                     source_hash, source_content, translated_content,
                     generated_at, generated_by, approved)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{module_id}:{file_path}:{source_language}",
                    module_id,
                    file_path,
                    source_language,
                    source_language,
                    source_hash,
                    content,
                    content,  # Translated = original for source language
                    now,
                    "system",
                    1,
                ),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            logger.error("Failed to import source content: %s", e)
            conn.close()
            return False

    def get_prompt_translated(
        self,
        module_id: str,
        file_path: str,
        target_language: str,
        source_content: str = "",
        source_hash: str = "",
        force: bool = False,
    ) -> TranslationEntry | None:
        """Get or create a translated prompt for a specific file.

        Used by PromptService to get translated prompts on demand.

        Args:
            module_id: The module ID (e.g. "prompts-base")
            file_path: The file path within the module (e.g. "default/strategist")
            target_language: Target language code
            source_content: Source content to import if not already cached
            source_hash: Source hash for change detection
            force: Force re-translation even if cached

        Returns:
            TranslationEntry with translated content, or None
        """
        if target_language == "en":
            return None

        # Check cache first
        existing = self.get_translation(module_id, file_path, target_language)
        if existing and existing.translated_content and not force:
            if existing.source_hash == source_hash or not source_hash:
                return existing

        # Import source content if provided
        if source_content:
            self.import_source_content(
                module_id=module_id,
                file_path=file_path,
                content=source_content,
            )

        # Perform translation
        result = self.translate_module(
            module_id=module_id,
            target_language=target_language,
            force=force,
            auto_approve=True,
            quality_threshold=0.5,  # Lower threshold for individual prompts
        )

        if result.status in ("ok", "partial") and result.files_translated > 0:
            return self.get_translation(module_id, file_path, target_language)

        # Log failure details so operators can diagnose
        if result.status == "error":
            logger.warning(
                "Translation failed for %s/%s → %s: %s",
                module_id,
                file_path,
                target_language,
                "; ".join(result.errors) if result.errors else "unknown error",
            )
        elif result.files_errored > 0:
            logger.warning(
                "Translation partial for %s/%s → %s: %d file(s) errored, %d skipped",
                module_id,
                file_path,
                target_language,
                result.files_errored,
                result.files_skipped,
            )

        return None
