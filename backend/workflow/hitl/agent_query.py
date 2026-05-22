"""Agent query trigger — determines when an agent should ask the user for clarification.

Uses a hybrid approach combining:
1. LLM confidence analysis (low confidence → query)
2. Content-based detection (needs_clarification markers, questions)
3. Loop detection (repeated patterns → stalemate → query)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Keywords/phrases that indicate the agent needs clarification
_CLARIFICATION_MARKERS = [
    r"\[NEEDS_CLARIFICATION\]",
    r"\[CLARIFICATION_NEEDED\]",
    r"\[QUESTION\]",
    r"(?:i|we)\s+(?:need|require)\s+(?:more|additional|further)\s+(?:information|context|clarification|details)",
    r"(?:could|can|would)\s+you\s+(?:please\s+)?(?:clarify|specify|explain|elaborate|provide)",
    r"(?:what|which)\s+(?:exactly|specifically)\s+(?:do|does|did|is|are|was|were)\s+you",
    r"(?:please|kindly)\s+(?:specify|clarify|elaborate|provide\s+more\s+details)",
    r"(?:ich|wir)\s+(?:benötigen|brauchen)\s+(?:weitere|zusätzliche|nähere)\s+(?:Informationen|Klarstellung|Details)",
    r"(?:könnten|können)\s+Sie\s+(?:bitte\s+)?(?:klären|erläutern|näher\s+erläutern|genauer\s+erklären)",
]

# Patterns indicating uncertainty or hedging
_UNCERTAINTY_MARKERS = [
    r"(?:i'?m?\s+)?(?:not\s+(?:entirely\s+)?sure|uncertain|unclear)",
    r"(?:it'?s?\s+)?(?:unclear|ambiguous|vague)",
    r"(?:this\s+)?(?:requires?\s+)?(?:further|more)\s+(?:investigation|analysis|research|consideration)",
    r"(?:i|we)\s+(?:cannot|can'?t)\s+(?:determine|resolve|conclude|decide)",
    r"(?:the\s+)?(?:information|context|data)\s+(?:provided|given)\s+(?:is\s+)?(?:insufficient|incomplete|lacking)",
    r"(?:es\s+)?(?:ist\s+)?(?:unklar|nicht\s+eindeutig|nicht\s+ausreichend)",
]

# Compile patterns for performance
_CLARIFICATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _CLARIFICATION_MARKERS]
_UNCERTAINTY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _UNCERTAINTY_MARKERS]


@dataclass
class QueryAnalysis:
    """Result of analyzing an agent's output for query potential."""

    should_query: bool
    confidence: float  # 0.0 (definitely query) to 1.0 (no query needed)
    reason: str
    suggested_question: str = ""
    detection_details: list[dict] = field(default_factory=list)

    @property
    def trigger_type(self) -> str:
        """What triggered the query recommendation."""
        if not self.detection_details:
            return "none"
        return self.detection_details[0].get("type", "unknown")


def analyze_for_query(
    agent_output: str,
    agent_role: str,
    current_round: int,
    max_rounds: int,
    auto_query_threshold: float = 0.4,
    previous_outputs: list[str] | None = None,
) -> QueryAnalysis:
    """Analyze agent output to determine if a user query is needed.

    Args:
        agent_output: The agent's generated text.
        agent_role: The agent's role (e.g. 'critic').
        current_round: Current debate round.
        max_rounds: Maximum debate rounds.
        auto_query_threshold: Confidence below which a query is triggered.
        previous_outputs: Previous agent outputs for loop detection.

    Returns:
        QueryAnalysis with recommendation and details.
    """
    detections: list[dict] = []
    min_confidence = 1.0

    # --- 1. Explicit clarification markers ---
    for pattern in _CLARIFICATION_PATTERNS:
        match = pattern.search(agent_output)
        if match:
            detections.append(
                {
                    "type": "explicit_marker",
                    "severity": "high",
                    "matched": match.group(0)[:100],
                    "confidence_impact": 0.6,
                }
            )
            min_confidence = min(min_confidence, 0.2)

    # --- 2. Uncertainty markers ---
    uncertainty_count = 0
    for pattern in _UNCERTAINTY_PATTERNS:
        if pattern.search(agent_output):
            uncertainty_count += 1

    if uncertainty_count >= 2:
        detections.append(
            {
                "type": "uncertainty",
                "severity": "medium",
                "count": uncertainty_count,
                "confidence_impact": 0.3,
            }
        )
        min_confidence = min(min_confidence, 0.5)
    elif uncertainty_count == 1:
        detections.append(
            {
                "type": "uncertainty",
                "severity": "low",
                "count": uncertainty_count,
                "confidence_impact": 0.15,
            }
        )
        min_confidence = min(min_confidence, 0.7)

    # --- 3. Question density (agent asking many questions) ---
    question_marks = agent_output.count("?")
    if question_marks >= 3:
        detections.append(
            {
                "type": "high_question_density",
                "severity": "medium",
                "count": question_marks,
                "confidence_impact": 0.25,
            }
        )
        min_confidence = min(min_confidence, 0.6)

    # --- 4. Loop detection (repeated content across rounds) ---
    if previous_outputs and len(previous_outputs) >= 2:
        loop_score = _detect_loop(agent_output, previous_outputs)
        if loop_score > 0.7:
            detections.append(
                {
                    "type": "loop_detected",
                    "severity": "high",
                    "similarity": round(loop_score, 3),
                    "confidence_impact": 0.4,
                }
            )
            min_confidence = min(min_confidence, 0.3)
        elif loop_score > 0.5:
            detections.append(
                {
                    "type": "repetition",
                    "severity": "medium",
                    "similarity": round(loop_score, 3),
                    "confidence_impact": 0.2,
                }
            )
            min_confidence = min(min_confidence, 0.5)

    # --- 5. Very short output (agent produced almost nothing) ---
    word_count = len(agent_output.split())
    if word_count < 20:
        detections.append(
            {
                "type": "minimal_output",
                "severity": "medium",
                "word_count": word_count,
                "confidence_impact": 0.3,
            }
        )
        min_confidence = min(min_confidence, 0.4)

    # --- 6. Late-round uncertainty (more likely to query in later rounds) ---
    if current_round >= max_rounds - 1 and min_confidence < 0.7:
        detections.append(
            {
                "type": "late_round_uncertainty",
                "severity": "low",
                "round": current_round,
                "max_rounds": max_rounds,
                "confidence_impact": 0.1,
            }
        )
        min_confidence = min(min_confidence, 0.6)

    # --- Decision ---
    should_query = min_confidence < auto_query_threshold
    reason = _build_reason(detections, should_query, min_confidence)
    suggested_question = _extract_question(agent_output) if should_query else ""

    if should_query:
        logger.info(
            "Agent query triggered for %s (round %d): confidence=%.3f, threshold=%.3f, detections=%s",
            agent_role,
            current_round,
            min_confidence,
            auto_query_threshold,
            [d["type"] for d in detections],
        )

    return QueryAnalysis(
        should_query=should_query,
        confidence=round(min_confidence, 3),
        reason=reason,
        suggested_question=suggested_question,
        detection_details=detections,
    )


def _detect_loop(current_output: str, previous_outputs: list[str]) -> float:
    """Detect if the agent is repeating itself across rounds.

    Uses simple word-level Jaccard similarity.
    Returns a score from 0.0 (no similarity) to 1.0 (identical).
    """
    current_words = set(current_output.lower().split())
    if not current_words:
        return 0.0

    similarities = []
    for prev in previous_outputs[-3:]:  # Check last 3 outputs
        prev_words = set(prev.lower().split())
        if not prev_words:
            continue
        intersection = current_words & prev_words
        union = current_words | prev_words
        if union:
            similarities.append(len(intersection) / len(union))

    return max(similarities) if similarities else 0.0


def _extract_question(agent_output: str) -> str:
    """Extract the most relevant question from the agent's output.

    Returns the first question found, or a generic clarification request.
    Handles markdown-formatted output by stripping formatting before extraction.
    """
    # Strip markdown code blocks and inline code to avoid extracting questions from examples
    cleaned = re.sub(r"```[\s\S]*?```", "", agent_output)
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    # Strip bold/italic markers but keep the text
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    # Strip list markers for cleaner extraction
    cleaned = re.sub(r"^\s*[-*•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)

    # Look for explicit question sentences
    sentences = re.split(r"[.!?\n]+", cleaned)
    for sentence in sentences:
        stripped = sentence.strip()
        if "?" in stripped and 10 < len(stripped) < 300:
            return stripped + "?" if not stripped.endswith("?") else stripped

    # Look for [NEEDS_CLARIFICATION] or [QUESTION] markers
    for pattern in _CLARIFICATION_PATTERNS:
        match = pattern.search(agent_output)
        if match:
            # Get surrounding context (next sentence)
            start = match.end()
            remaining = agent_output[start : start + 200].strip()
            if remaining:
                next_sentence = re.split(r"[.!?\n]+", remaining)[0].strip()
                if next_sentence:
                    return next_sentence

    return "Could you please provide additional context or clarification?"


def _build_reason(detections: list[dict], should_query: bool, confidence: float) -> str:
    """Build a human-readable reason for the query decision."""
    if not detections:
        return "No indicators detected — agent output appears confident"

    primary = detections[0]
    type_descriptions = {
        "explicit_marker": "Agent explicitly requested clarification",
        "uncertainty": "Agent expressed uncertainty about the topic",
        "high_question_density": "Agent asked multiple questions indicating need for input",
        "loop_detected": "Agent appears stuck in a repetitive loop",
        "repetition": "Agent output shows significant repetition from previous rounds",
        "minimal_output": "Agent produced very little output, possibly due to insufficient context",
        "late_round_uncertainty": "Late-round uncertainty detected",
    }

    desc = type_descriptions.get(primary["type"], f"Detection: {primary['type']}")
    action = "Query recommended" if should_query else "Monitoring — below threshold"

    return f"{desc} (confidence={confidence:.2f}). {action}."
