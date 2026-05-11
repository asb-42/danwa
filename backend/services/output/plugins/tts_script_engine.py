"""TTSScriptEngine — transforms DebateArtifact into TTSScript.

Script rules:
  a) If intro_text is set → TTSSegment(is_intro=True) at the beginning
  b) For each round:
     - Injections → segment with spoken hint
     - UserQueries → segment with spoken hint
     - Turns → segment with voice from voice_mapping
  c) If outro_text is set → TTSSegment(is_outro=True) at the end
"""

from __future__ import annotations

import logging
from collections import defaultdict

from backend.models.artifact import DebateArtifact
from backend.services.output.plugins.tts_models import TTSScript, TTSSegment

logger = logging.getLogger(__name__)

# Role-type-based default style hints for MiMo TTS.
# These provide natural language voice direction per agent role.
ROLE_STYLE_HINTS: dict[str, str] = {
    "strategist": "Confident, structured delivery. Measured pace with emphasis on key points. Authoritative but approachable.",
    "critic": "Sharp, analytical tone. Slightly skeptical. Questions assumptions with precision. Thoughtful pauses between arguments.",
    "optimizer": "Enthusiastic, solution-oriented. Faster pace, forward energy. Positive and constructive framing.",
    "moderator": "Calm, authoritative. Neutral tone with clear transitions between speakers. Steady, reassuring pace.",
    "fact-checker": "Precise, careful delivery. Methodical pacing. Emphasis on accuracy and source references.",
    "expert-reviewer": "Knowledgeable, thorough. Professional tone with technical confidence. Balanced and measured.",
    "narrator": "Warm, engaging narrator voice. Clear enunciation. Slight dramatic flair for transitions.",
    "user": "Natural, conversational tone. Curious and engaged. Slightly faster than other speakers.",
    "injector": "Direct, conversational. Slightly informal interjection style. Brief and focused.",
}


class TTSScriptEngine:
    """Transforms a ``DebateArtifact`` into a ``TTSScript``.

    Stateless — a fresh instance is created per render call.
    """

    def transform(
        self,
        artifact: DebateArtifact,
        voice_mapping: dict[str, str],
        default_voice: str,
        segment_pause_ms: int = 800,
        turn_pause_ms: int = 300,
        intro_text: str | None = None,
        outro_text: str | None = None,
        language: str = "de",
        default_style_hint: str = "",
        engine: str = "edge_tts",
    ) -> TTSScript:
        """Build a TTSScript from the artifact.

        Args:
            artifact: The debate artifact.
            voice_mapping: agent_name → voice_id mapping.
            default_voice: Fallback voice ID.
            segment_pause_ms: Pause after injections/queries.
            turn_pause_ms: Pause after each turn.
            intro_text: Optional intro narration.
            outro_text: Optional outro narration.
            language: Language for spoken hints.
            default_style_hint: Default style hint for MiMo TTS segments.
            engine: TTS engine type ("edge_tts" or "mimo_tts").

        Returns:
            A ``TTSScript`` ready for audio rendering.
        """
        segments: list[TTSSegment] = []
        seg_counter = 0

        # Language-specific hints
        hints = self._get_hints(language)

        # Determine if style hints should be applied (only for MiMo TTS)
        use_style_hints = engine == "mimo_tts"

        # (a) Intro segment
        if intro_text:
            seg_counter += 1
            style = ROLE_STYLE_HINTS.get("narrator", default_style_hint) if use_style_hints else ""
            segments.append(
                TTSSegment(
                    id=f"seg-{seg_counter:04d}",
                    speaker_name="Narrator",
                    speaker_role="narrator",
                    voice_id=default_voice,
                    text=intro_text,
                    pause_after_ms=segment_pause_ms,
                    is_intro=True,
                    style_hint=style,
                )
            )

        # Group queries by round (injections grouped below via node_to_round)
        queries_by_round = self._group_queries_by_round(artifact)

        # Build turn_round map for injection round resolution
        # Injections don't have a round field directly — map via target_node_id
        node_to_round: dict[str, int] = {}
        for turn in artifact.transcript:
            node_to_round[turn.node_id] = turn.round

        # Re-group injections by round using node_to_round
        inj_by_round: dict[int, list] = defaultdict(list)
        for inj in artifact.interjections:
            rnd = node_to_round.get(inj.target_node_id, 0)
            inj_by_round[rnd].append(inj)

        # Process rounds
        rounds = sorted({t.round for t in artifact.transcript})

        for rnd in rounds:
            # Injections for this round
            for inj in inj_by_round.get(rnd, []):
                seg_counter += 1
                style = ROLE_STYLE_HINTS.get("injector", default_style_hint) if use_style_hints else ""
                segments.append(
                    TTSSegment(
                        id=f"seg-{seg_counter:04d}",
                        speaker_name=inj.source,
                        speaker_role="injector",
                        voice_id=default_voice,
                        text=f"{hints['interjection']} {inj.content}",
                        pause_after_ms=segment_pause_ms,
                        injection_reference=inj.id,
                        style_hint=style,
                    )
                )

            # User queries for this round
            for q in queries_by_round.get(rnd, []):
                seg_counter += 1
                style = ROLE_STYLE_HINTS.get("user", default_style_hint) if use_style_hints else ""
                segments.append(
                    TTSSegment(
                        id=f"seg-{seg_counter:04d}",
                        speaker_name="Nutzer",
                        speaker_role="user",
                        voice_id=default_voice,
                        text=f"{hints['user_query']} {q.content}",
                        pause_after_ms=segment_pause_ms,
                        style_hint=style,
                    )
                )

            # Turns for this round
            round_turns = [t for t in artifact.transcript if t.round == rnd]
            for turn in round_turns:
                seg_counter += 1
                voice_id = voice_mapping.get(turn.agent_name, default_voice)
                style = ROLE_STYLE_HINTS.get(turn.role_type, default_style_hint) if use_style_hints else ""
                segments.append(
                    TTSSegment(
                        id=f"seg-{seg_counter:04d}",
                        speaker_name=turn.agent_name,
                        speaker_role=turn.role_type,
                        voice_id=voice_id,
                        text=turn.content,
                        pause_after_ms=turn_pause_ms,
                        style_hint=style,
                    )
                )

        # (c) Outro segment
        if outro_text:
            seg_counter += 1
            style = ROLE_STYLE_HINTS.get("narrator", default_style_hint) if use_style_hints else ""
            segments.append(
                TTSSegment(
                    id=f"seg-{seg_counter:04d}",
                    speaker_name="Narrator",
                    speaker_role="narrator",
                    voice_id=default_voice,
                    text=outro_text,
                    pause_after_ms=0,
                    is_outro=True,
                    style_hint=style,
                )
            )

        # Estimate duration (rough: ~150 words/min)
        total_words = sum(len(s.text.split()) for s in segments)
        total_pauses_ms = sum(s.pause_after_ms for s in segments)
        estimated_ms = int(total_words / 150 * 60 * 1000) + total_pauses_ms

        return TTSScript(
            segments=segments,
            metadata={
                "topic": artifact.topic,
                "total_segments": len(segments),
                "estimated_duration_ms": estimated_ms,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_injections_by_round(artifact: DebateArtifact) -> dict[int, list]:
        """Group injections by round (using node_to_round mapping)."""
        # This is a simplified version — the actual round is resolved
        # in transform() using node_to_round
        return {}

    @staticmethod
    def _group_queries_by_round(artifact: DebateArtifact) -> dict[int, list]:
        """Group user queries by round."""
        result: dict[int, list] = defaultdict(list)
        turn_rounds = {t.id: t.round for t in artifact.transcript}
        for q in artifact.user_queries:
            rnd = turn_rounds.get(q.response_turn_id, 0) if q.response_turn_id else 0
            result[rnd].append(q)
        return dict(result)

    @staticmethod
    def _get_hints(language: str) -> dict[str, str]:
        """Return language-specific spoken hints."""
        if language == "en":
            return {
                "interjection": "Interjection:",
                "user_query": "User question:",
            }
        # Default German
        return {
            "interjection": "Zwischenfrage:",
            "user_query": "Nutzerfrage:",
        }
