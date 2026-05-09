"""TonePromptInjector — injects tone profile instructions into system prompts.

Takes a ToneProfile and the existing System-Prompt-String and generates
a style instruction appended to the prompt.
"""

from __future__ import annotations

import logging

from backend.blueprints.models import ToneProfile

logger = logging.getLogger(__name__)

# Style descriptions for each style enum value
_STYLE_DESCRIPTIONS: dict[str, str] = {
    "heated": "Du führst ein hitziges Streitgespräch.",
    "academic": "Du führst eine formale, akademische Debatte.",
    "conversational": "Du führst ein lockeres, gesprächsartiges Gespräch.",
    "socratic": "Du führst ein sokratisches Gespräch mit gezielten Fragen.",
    "neutral": "Du argumentierst sachlich und neutral.",
}

# Formality level descriptions
_FORMALITY_LEVELS: dict[str, str] = {
    "low": "Nutze eine informelle, umgangssprachliche Ausdrucksweise.",
    "medium": "Nutze eine ausgewogene Mischung aus formeller und informeller Sprache.",
    "high": "Nutze eine hochformale, akademische Sprache.",
}

# Verbosity descriptions
_VERBOSITY_DESCRIPTIONS: dict[str, str] = {
    "concise": "Sei kurz und prägnant.",
    "normal": "Sei ausführlich genug, um deine Argumente zu stützen.",
    "verbose": "Sei sehr ausführlich und detailliert.",
}

# Emotional valence descriptions
_EMOTIONAL_VALENCE_DESCRIPTIONS: dict[str, str] = {
    "low": "Halte die Emotionalität gering.",
    "medium": "Zeige moderate emotionale Beteiligung.",
    "high": "Zeige hohe emotionale Intensität.",
}

# Rhetorical mode descriptions
_RHETORICAL_MODE_DESCRIPTIONS: dict[str, str] = {
    "none": "",
    "questioning": "Stelle rhetorische Fragen, um deine Argumente zu untermauern.",
    "assertive": "Tritt selbstbewusst und bestimmt auf.",
    "dialectic": "Nutze dialektische Methoden: These, Antithese, Synthese.",
}


def _formality_level(value: float) -> str:
    """Map formality float to low/medium/high."""
    if value < 0.33:
        return "low"
    elif value < 0.67:
        return "medium"
    else:
        return "high"


def _emotional_level(value: float) -> str:
    """Map emotional_valence float to low/medium/high."""
    if value < 0.33:
        return "low"
    elif value < 0.67:
        return "medium"
    else:
        return "high"


def inject_tone_profile(system_prompt: str, profile: ToneProfile) -> str:
    """Inject tone profile instructions into a system prompt.

    Args:
        system_prompt: The existing system prompt string.
        profile: The ToneProfile to inject.

    Returns:
        The modified system prompt with tone instructions appended.
    """
    parts: list[str] = []

    # Style description
    style_desc = _STYLE_DESCRIPTIONS.get(profile.style, "")
    if style_desc:
        parts.append(style_desc)

    # Formality
    formality_desc = _FORMALITY_LEVELS.get(_formality_level(profile.formality), "")
    if formality_desc:
        parts.append(formality_desc)

    # Verbosity
    verbosity_desc = _VERBOSITY_DESCRIPTIONS.get(profile.verbosity, "")
    if verbosity_desc:
        parts.append(verbosity_desc)

    # Emotional valence
    emotion_desc = _EMOTIONAL_VALENCE_DESCRIPTIONS.get(_emotional_level(profile.emotional_valence), "")
    if emotion_desc:
        parts.append(emotion_desc)

    # Rhetorical mode
    rhetorical_desc = _RHETORICAL_MODE_DESCRIPTIONS.get(profile.rhetorical_mode, "")
    if rhetorical_desc:
        parts.append(rhetorical_desc)

    # Custom instructions
    if profile.custom_instructions:
        parts.append(profile.custom_instructions)

    if not parts:
        return system_prompt

    tone_instruction = " ".join(parts)
    return f"{system_prompt}\n\n[TONE PROFILE]\n{tone_instruction}"
