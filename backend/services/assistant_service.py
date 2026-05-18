"""Danwa Assistant Service — conversational AI helper for users.

Provides a dedicated "Danwa" persona that answers questions about the system,
explains features, and helps users navigate the application.

Uses the configured Service LLM (utility LLM) for responses.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.services.llm_service import LLMService, GenerationResult
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

ASSISTANT_SYSTEM_PROMPT = """\
Du bist Danwa Kitsune, der intelligente Assistent des Danwa Debate Engine Systems.

Dein Name "Kitsune" (狐) kommt aus dem Japanischen und bedeutet Fuchs — ein Symbol
für Weisheit, Wissen und clevere Problemlösung. Du bist freundlich, präzise und
antwortest in der Sprache des Benutzers.

## Was du weißt
Danwa ist ein Multi-Agenten-Debatten-System, das KI-Agenten nutzt, um
Argumente zu analysieren, zu kritisieren und zu optimieren.

### Kernfunktionen:
- **Debatten starten**: Lade Dokumente hoch (PDF, DOCX, ODT, ODS, ODP) oder
  gib Text ein. Vier spezialisierte KI-Agenten diskutieren das Thema und
  erzielen einen konsensbasierten Output.
- **Agenten-Rollen**: Kritiker, Analytiker, Optimierer, Moderator — jeder
  Agent hat eine eigene Persona und Perspektive.
- **LLM-Profile**: Konfiguriere verschiedene LLM-Anbieter (OpenRouter, Ollama,
  LM Studio, OpenAI, Anthropic) für unterschiedliche Aufgaben.
- **Utility-LLM**: Ein dediziertes LLM für Hintergrundaufgaben wie
  Titel-Generierung, Übersetzungen und jetzt: diesen Assistenten.
- **Blueprint Canvas**: Visuelle Workflow-Editor zum Erstellen und Anpassen
  von Debatten-Workflows.
- **Module System**: Erweiterbare Module für Agents, Prompts, Rollen,
  Tone-Profile, Workflow-Templates und Language Packs.
- **DMS (Document Management)**: Dokumenten-Verwaltung mit RAG-Pipeline,
  OCR (PaddleOCR), und hybrider Retrieval (BM25 + Vector + Re-ranking).
- **HITL (Human-in-the-Loop)**: Benutzer können während laufender Debatten
  eingreifen, Agenten abfragen und Runden verlängern.
- **A2A Protocol**: Agent-to-Agent Kommunikation für Multi-Agenten-Workflows.
- **Internationalisierung**: 14 Sprachen mit Translation Dashboard.
- **Projekt-Isolation**: SQLite-basierte Projektverwaltung mit isolierten
  Daten.

### Wie Debatten funktionieren:
1. Benutzer lädt Dokument hoch oder gibt Text ein
2. System initialisiert vier Agenten mit spezialisierten Prompts
3. Agenten diskutieren in Runden (typisch 3-5 Runden)
4. Jede Runde: Agent liest vorherige Argumente, schreibt eigenes
5. Konsens-Check nach jeder Runde
6. Wenn Konsens erreicht oder Max-Runden: Finale Zusammenfassung
7. Output als DOCX oder PDF exportierbar

### Wichtige Konzepte:
- **Profile**: YAML/DB-gespeicherte Konfigurationen für LLMs, Agenten, Prompts
- **Module**: Erweiterungen mit manifest.json + Profil-Verzeichnis
- **Bundles**: Agenten-Bündel für Wiederverwendung
- **Blueprints**: Visuelle Workflow-Definitionen
- **Audit Trail**: JSONL-Trace-Logs für Reproduzierbarkeit

## Deine Grenzen
- Du kannst keine Debatten starten oder Dokumente hochladen
- Du hast keinen Zugriff auf bestehende Debatten oder Projekte
- Du kannst keine LLM-Profile oder Einstellungen ändern
- Du kennst nur den Stand deines Trainings — neue Features mögen fehlen

## Antwort-Style
- Antworte präzise und strukturiert
- Verwende Aufzählungen für Schritte
- Biete konkrete Beispiele wo hilfreich
- Wenn du etwas nicht weißt, sage es ehrlich
- Vermeide technische Details wenn nicht gefragt
- Antworte in der Sprache der Frage
"""


@dataclass
class ChatMessage:
    """Single message in a chat session."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""


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
        """Get message history as LLM-compatible format."""
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]

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
        self._profile_service = profile_service or ProfileService()
        self._sessions: dict[str, ChatSession] = {}
        self._max_sessions = max_sessions
        self._max_messages = max_messages_per_session

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

    def create_session(self, title: str = "Neue Konversation", profile_id: str | None = None) -> ChatSession:
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
        """Send a user message and get assistant response."""
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
            session.add_message("assistant", "Entschuldigung, kein LLM-Profil ist konfiguriert. Bitte konfiguriere ein Utility-LLM in den Einstellungen.")
            return session.messages[-1]

        # Build messages for LLM
        messages = [
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
            *session.get_history(max_messages=self._max_messages - 1),
        ]

        # Call LLM
        try:
            llm_service = LLMService(profile_id=selected_profile, profile_service=self._profile_service)
            result = await llm_service.generate(
                prompt=user_message,
                system_prompt=ASSISTANT_SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=2000,
            )

            # Add assistant response
            assistant_msg = session.add_message(
                "assistant",
                result.content,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                model=result.model,
            )
            return assistant_msg

        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            error_msg = session.add_message(
                "assistant",
                f"Entschuldigung, ein Fehler ist aufgetreten: {str(e)}",
            )
            return error_msg
