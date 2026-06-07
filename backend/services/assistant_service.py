"""Danwa Assistant Service — conversational AI helper for users.

Provides a dedicated "Danwa Kitsune" persona that answers questions about
the system, explains features, and helps users navigate the application.

System prompt is loaded from ``config/prompts/kitsune/kitsune.md`` (SSOT,
versionable, English source).  Translations are generated on-demand via
``TranslationService`` and cached in ``blueprints.db``.

Uses the configured Service LLM (utility LLM) for responses.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.blueprints.repository import BlueprintRepository
from backend.persistence.debate_store import DebateStore
from backend.services.assistant_tools import execute_tool, get_tool_definitions
from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

# Kitsune system prompt directory (SSOT, versionable, translatable)
_KITSUNE_PROMPT_DIR = Path("config/prompts/kitsune")

# Fallback English prompt if file is missing
_FALLBACK_PROMPT = """\
You are Danwa Kitsune, the intelligent assistant of the Danwa Debate Engine system.

Your name "Kitsune" (狐) comes from Japanese and means fox — a symbol of
wisdom, knowledge, and clever problem-solving. You are friendly, precise,
and respond in the user's language.

## What you know
Danwa is a multi-agent debate system that uses AI agents to analyze, critique, and optimize arguments through structured deliberation.

### Core features:
- **Start debates**: Upload documents (PDF, DOCX, ODT, ODS, ODP) or enter
text. Four specialized AI agents discuss the topic and produce a
consensus-based output.
- **Agent roles**: Critic, Analyst, Optimizer, Moderator — each agent has its own persona and perspective.
- **LLM profiles**: Configure different LLM providers (OpenRouter, Ollama, LM Studio, OpenAI, Anthropic) for different tasks.
- **Utility LLM**: A dedicated LLM for background tasks like title generation, translations, and this assistant.
- **Blueprint Canvas**: Visual workflow editor for creating and customizing debate workflows.
- **Module system**: Extensible modules for agents, prompts, roles, tone profiles, workflow templates, and language packs.
- **DMS (Document Management)**: Document management with RAG pipeline, OCR (PaddleOCR), and hybrid retrieval (BM25 + Vector + Re-ranking).
- **HITL (Human-in-the-Loop)**: Users can intervene during running debates, query agents, and extend rounds.
- **A2A Protocol**: Agent-to-Agent communication for multi-agent workflows.
- **Internationalization**: 14 languages with Translation Dashboard.
- **Project isolation**: SQLite-based project management with isolated data.

### How debates work:
1. User uploads a document or enters text
2. System initializes four agents with specialized prompts
3. Agents discuss in rounds (typically 3-5 rounds)
4. Each round: agent reads previous arguments, writes their own
5. Consensus check after each round
6. When consensus reached or max rounds: final summary
7. Output exportable as DOCX or PDF

### Key concepts:
- **Profiles**: YAML/DB-stored configurations for LLMs, agents, prompts
- **Modules**: Extensions with manifest.json + profile directory
- **Bundles**: Agent bundles for reuse
- **Blueprints**: Visual workflow definitions
- **Audit trail**: JSONL trace logs for reproducibility

## Your capabilities
You have access to tools that let you interact with the Danwa system directly:
- **get_system_status** — System status summary
- **list_debates** — List debates with status and topic
- **get_debate_details** — Details about a specific debate
- **get_llm_profiles** — Configured LLM profiles
- **get_modules** — Installed modules by category
- **search_knowledge_base** — Search documentation
You currently have read-only access. You cannot start debates, change settings, or modify data.

## Response style
- Respond precisely and structured
- Use bullet points for steps
- Offer concrete examples where helpful
- If you don't know something, say so honestly
- Avoid technical details unless asked
- Respond in the language of the question
"""

# In-memory cache for translated Kitsune prompts
# Key: language code, Value: (prompt_text, source_hash)
_kitsune_prompt_cache: dict[str, tuple[str, str]] = {}


def _get_source_hash(content: str) -> str:
    """Compute SHA256 hash of prompt content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_kitsune_prompt(language: str = "en") -> str:
    """Load Kitsune system prompt, translating if necessary.

    For English: loads directly from ``kitsune.md``.
    For other languages: checks DB translation cache, then translates
    on-demand via ``TranslationService``. Falls back to English source
    if translation fails.

    Args:
        language: Language code (e.g. 'en', 'de', 'fr').

    Returns:
        System prompt text in the requested language.
    """
    # English is the source — no translation needed
    if language == "en":
        return _load_english_prompt()

    # Load source and compute hash
    source_content = _load_english_prompt()
    source_hash = _get_source_hash(source_content)

    # Check in-memory cache first
    cached = _kitsune_prompt_cache.get(language)
    if cached and cached[1] == source_hash:
        return cached[0]

    # Try DB translation cache via TranslationService
    try:
        from backend.services.translation_service import TranslationService

        trans_svc = TranslationService()

        # Check if translation already exists in DB
        existing = trans_svc.get_translation("kitsune", "system", language)
        if existing and existing.translated_content and existing.source_hash == source_hash:
            _kitsune_prompt_cache[language] = (existing.translated_content, source_hash)
            return existing.translated_content

        # Import source content if not in DB
        if source_content:
            trans_svc.import_source_content(
                module_id="kitsune",
                file_path="system",
                content=source_content,
            )

        # Translate on-demand
        result = trans_svc.translate_module(
            module_id="kitsune",
            target_language=language,
            force=False,
            auto_approve=True,
            quality_threshold=0.5,
        )

        if result.status in ("ok", "partial") and result.files_translated > 0:
            entry = trans_svc.get_translation("kitsune", "system", language)
            if entry and entry.translated_content:
                _kitsune_prompt_cache[language] = (entry.translated_content, source_hash)
                return entry.translated_content
    except Exception:
        logger.debug("Translation failed for Kitsune prompt (%s)", language, exc_info=True)

    # Fallback: return English source
    logger.warning("No translation available for Kitsune prompt (%s), using English source", language)
    _kitsune_prompt_cache[language] = (source_content, source_hash)
    return source_content


def _load_english_prompt() -> str:
    """Load the English source prompt from config/prompts/kitsune/kitsune.md.

    Appends the auto-generated knowledge base (config/prompts/kitsune/knowledge.txt)
    if it exists, giving Kitsune concrete information about the codebase.
    """
    base_file = _KITSUNE_PROMPT_DIR / "kitsune.md"
    if base_file.exists():
        try:
            content = base_file.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning(f"Failed to read {base_file}: {e}")
            content = _FALLBACK_PROMPT
    else:
        logger.warning("Using hardcoded fallback prompt for Kitsune")
        content = _FALLBACK_PROMPT

    # Append knowledge base if available
    knowledge_file = _KITSUNE_PROMPT_DIR / "knowledge.txt"
    if knowledge_file.exists():
        try:
            knowledge = knowledge_file.read_text(encoding="utf-8").strip()
            content += "\n\n## Reference: Codebase Knowledge Base\n\n" + knowledge
        except OSError:
            logger.warning("Failed to read knowledge base file")

    return content


@dataclass
class ChatMessage:
    """Single message in a chat session."""

    role: str  # "user", "assistant", or "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    tool_call_id: str = ""
    tool_name: str = ""


@dataclass
class ChatSession:
    """A complete chat session with the Danwa assistant."""

    id: str
    title: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    llm_profile_id: str | None = None

    def add_message(self, role: str, content: str, **kwargs) -> ChatMessage:
        """Add a message to the session."""
        msg = ChatMessage(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = time.time()
        return msg

    def get_history(self, max_messages: int = 20) -> list[dict[str, str]]:
        """Get message history as LLM-compatible format.

        For ``role="tool"`` messages, adds the ``tool_call_id`` and ``name``
        fields required by the OpenAI chat completions API.
        """
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        result = []
        for m in recent:
            entry: dict[str, str] = {"role": m.role, "content": m.content}
            if m.role == "tool" and m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
                entry["name"] = m.tool_name
            result.append(entry)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict."""
        return {
            "id": self.id,
            "title": self.title,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "llm_profile_id": self.llm_profile_id,
            "last_message": self.messages[-1].content[:100] if self.messages else "",
        }


class AssistantService:
    """Manages chat sessions with the Danwa Kitsune assistant persona."""

    def __init__(
        self,
        profile_service: ProfileService | None = None,
        max_sessions: int = 50,
        max_messages_per_session: int = 100,
    ):
        """Initialise AssistantService."""
        self._profile_service = profile_service or ProfileService()
        self._sessions: dict[str, ChatSession] = {}
        self._max_sessions = max_sessions
        self._max_messages = max_messages_per_session
        self._system_prompt: str | None = None  # Lazy-loaded cache

    @property
    def system_prompt(self) -> str:
        """Load and cache the Kitsune system prompt in the user's configured language."""
        if self._system_prompt is None:
            from backend.api.deps import get_user_language

            user_lang = get_user_language()
            self._system_prompt = load_kitsune_prompt(user_lang)
        return self._system_prompt

    def _select_llm_profile(self, profile_id: str | None = None) -> str | None:
        """Select LLM profile for assistant responses.

        Priority:
        1. Explicit profile_id
        2. Configured service_llm_profile_id
        3. First service-eligible profile
        """
        if profile_id:
            profile = self._profile_service.get_llm_profile(profile_id)
            if profile:
                return profile_id

        # Try configured service LLM
        try:
            from backend.api.deps import get_settings

            settings = get_settings()
            if settings.service_llm_profile_id:
                profile = self._profile_service.get_llm_profile(settings.service_llm_profile_id)
                if profile:
                    return settings.service_llm_profile_id
        except Exception:
            pass

        # Fallback: first service-eligible profile
        try:
            eligible = self._profile_service.list_service_eligible_profiles()
            if eligible:
                return eligible[0].id
        except Exception:
            pass

        # Last resort: first LLM profile
        try:
            profiles = self._profile_service.list_llm_profiles()
            if profiles:
                return profiles[0].id
        except Exception:
            pass

        return None

    def create_session(self, title: str = "New Conversation", profile_id: str | None = None) -> ChatSession:
        """Create a new chat session."""
        # Evict oldest session if at capacity
        if len(self._sessions) >= self._max_sessions:
            oldest_id = min(self._sessions, key=lambda k: self._sessions[k].updated_at)
            del self._sessions[oldest_id]
            logger.info(f"Evicted oldest session: {oldest_id}")

        session = ChatSession(
            id=str(uuid.uuid4()),
            title=title,
            llm_profile_id=profile_id,
        )
        self._sessions[session.id] = session
        logger.info(f"Created session: {session.id} ({title})")
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions (summary only)."""
        return [s.to_dict() for s in sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    async def send_message(
        self,
        session_id: str,
        user_message: str,
        profile_id: str | None = None,
    ) -> ChatMessage | None:
        """Send a user message and get assistant response.

        If tools are registered, the LLM may respond with tool calls.
        Tool calls are executed automatically (up to 5 iterations) and
        the final text response is returned to the caller.
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return None

        # Add user message
        session.add_message("user", user_message)

        # Select LLM profile
        llm_profile_id = profile_id or session.llm_profile_id
        selected_profile = self._select_llm_profile(llm_profile_id)
        if not selected_profile:
            session.add_message(
                "assistant",
                "Entschuldigung, kein LLM-Profil ist konfiguriert. Bitte konfiguriere ein Utility-LLM in den Einstellungen.",
            )
            return session.messages[-1]

        tool_defs = get_tool_definitions()

        # Tool execution loop
        max_iterations = 5
        current_message = user_message
        for iteration in range(max_iterations):
            # Build messages for LLM
            _messages = [
                {"role": "system", "content": self.system_prompt},
                *session.get_history(max_messages=self._max_messages - 1),
            ]

            # Call LLM
            try:
                llm_service = LLMService(
                    profile_id=selected_profile,
                    profile_service=self._profile_service,
                )
                result = await llm_service.generate(
                    prompt=current_message if iteration == 0 else "",
                    system_prompt=self.system_prompt,
                    temperature=0.7,
                    max_tokens=2000,
                    tools=tool_defs if tool_defs else None,
                    context="Assistant",
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                error_msg = session.add_message(
                    "assistant",
                    f"Entschuldigung, ein Fehler ist aufgetreten: {str(e)}",
                )
                return error_msg

            if result.tool_calls:
                # Execute each tool call and add results to session history
                for tc in result.tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = tc["function"]["arguments"]

                    # Build context with available services
                    repo = BlueprintRepository()
                    ctx: dict[str, Any] = {
                        "assistant_service": self,
                        "profile_service": self._profile_service,
                        "blueprint_repository": repo,
                    }

                    ctx["debate_store"] = DebateStore()

                    # Optionally provide module_service if available
                    try:
                        from backend.modules.service import ModuleService

                        ctx["module_service"] = ModuleService()
                    except Exception:
                        pass

                    ctx["knowledge_base_path"] = Path("config/prompts/kitsune/knowledge.txt")

                    tool_result_str = await execute_tool(fn_name, fn_args, **ctx)

                    # Add tool result message to session
                    session.add_message(
                        "tool",
                        tool_result_str,
                        tool_call_id=tc.get("id", ""),
                        tool_name=fn_name,
                    )

                current_message = ""  # Continue loop without user prompt
            else:
                # Text response — done
                assistant_msg = session.add_message(
                    "assistant",
                    result.content or "",
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    model=result.model,
                )
                return assistant_msg

        # Max iterations reached without text response
        fallback_msg = session.add_message(
            "assistant",
            "Entschuldigung, die Anfrage konnte nicht vollständig bearbeitet werden. Bitte versuche es erneut oder formuliere deine Frage anders.",
        )
        return fallback_msg
