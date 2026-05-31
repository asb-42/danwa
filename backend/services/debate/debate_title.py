"""Debate title generation, validation, and post-processing."""

from __future__ import annotations

import logging

from backend.core.config import is_service_llm_eligible, settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TITLES: dict[str, str] = {
    "en": (
        "You are a precise debate title generator.\n"
        "Rules — follow ALL of them:\n"
        "1. Output ONLY the title. Nothing else. No intro, no explanation.\n"
        "2. The title must be 40-120 characters.\n"
        '3. Do NOT start with "Here is", "The title is", "I suggest", etc.\n'
        "4. Do NOT describe the task or the user's request.\n"
        "5. Do NOT use quotation marks around the title.\n"
        "6. Do NOT end with punctuation.\n"
        "7. Format: concise noun phrase or simple sentence.\n\n"
        'BAD: "The user wants a debate about climate change"\n'
        'BAD: "Here is my suggested title: ..."\n'
        'GOOD: "Climate Change and Economic Growth: Compatible or Contradictory?"'
    ),
    "de": (
        "Du bist ein praeziser Titel-Generator fuer Debatten.\n"
        "Regeln — befolge ALLE:\n"
        "1. Gib AUSSCHLIESSLICH den Titel aus. Nichts anderes. Keine Einleitung.\n"
        "2. Der Titel muss 40-120 Zeichen lang sein.\n"
        '3. Beginne NICHT mit "Hier ist", "Der Titel lautet", etc.\n'
        "4. Beschreibe NICHT die Aufgabe oder den Wunsch des Benutzers.\n"
        "5. Keine Anfuehrungszeichen um den Titel.\n"
        "6. Kein Satzzeichen am Ende.\n"
        "7. Format: kompakte Nominalphrase oder einfacher Satz.\n\n"
        'BAD: "Der Benutzer moechte einen Titel ueber Klimawandel"\n'
        'BAD: "Hier ist mein vorgeschlagener Titel: ..."\n'
        'GOOD: "Klimawandel und Wirtschaftswachstum: Vereinbar oder Widerspruechlich?"'
    ),
}


async def generate_debate_title(
    case_text: str,
    llm_profile_id: str,
    language: str,
    project_id: str | None = None,
    use_service_llm: bool = True,
) -> str:
    """Generate a concise debate title (40-120 chars) using the best available LLM.

    If ``use_service_llm`` is True, selects a service-eligible LLM via
    ``_select_service_llm()`` for higher quality output.
    """
    from backend.services.llm_service import LLMService
    from backend.services.profile_service import ProfileService

    try:
        ps = ProfileService()

        if use_service_llm:
            service_id = _select_service_llm(ps)
            llm_service = LLMService(profile_id=service_id, profile_service=ps)
        else:
            llm_service = LLMService(profile_id=llm_profile_id, profile_service=ps)

        system_prompt = SYSTEM_PROMPT_TITLES.get(language, SYSTEM_PROMPT_TITLES["de"])

        user_prompt = (
            f"Generate ONE debate title (40-120 characters) for the following case. Output ONLY the title, nothing else.\n\n{case_text[:2000]}"
        )

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=4000,
            context="Debate",
        )

        raw = (result.content or "").strip()
        title = _post_process_title(_extract_title_from_verbose(raw) or raw, case_text)
        logger.info("Generated debate title (%d chars, service=%s): %s", len(title), use_service_llm, title)
        return title

    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)
        return _fallback_title(case_text)


def _select_service_llm(profile_service) -> str:
    """Select the service LLM profile for system/background tasks.

    Strategy — respects the user's UI choice (Build > Manage > LLM Profile,
    Utility-LLM checkbox) above all else:
    1. User-saved profiles (not readonly) with ``service_eligible`` = True.
    2. ``settings.service_llm_profile_id`` if it matches an eligible user-saved profile.
    3. Any eligible readonly profile.
    4. First available text-LLM.
    """
    try:
        all_profiles = profile_service.list_llm_profiles()
    except Exception:
        raise RuntimeError("No suitable LLM profile available for service tasks")

    # --- User-saved eligible profiles (UI checkbox choice) ---
    user_saved = [p for p in all_profiles if is_service_llm_eligible(p)[0] and not getattr(p, "_readonly", False)]
    if user_saved:
        if settings.service_llm_profile_id:
            match = next((p for p in user_saved if p.id == settings.service_llm_profile_id), None)
            if match:
                return match.id
        user_saved.sort(key=lambda p_: -(p_.context_window or 0))
        return user_saved[0].id

    # --- settings.service_llm_profile_id (fallback) ---
    if settings.service_llm_profile_id:
        preferred = profile_service.get_llm_profile(settings.service_llm_profile_id)
        if preferred and is_service_llm_eligible(preferred)[0]:
            return settings.service_llm_profile_id

    # --- Any eligible readonly profile ---
    readonly_eligible = [p for p in all_profiles if is_service_llm_eligible(p)[0]]
    if readonly_eligible:
        readonly_eligible.sort(key=lambda p_: -(p_.context_window or 0))
        return readonly_eligible[0].id

    # --- Last resort ---
    text_profiles = [p for p in all_profiles if getattr(p, "profile_type", "text") == "text"]
    if text_profiles:
        return text_profiles[0].id

    raise RuntimeError("No suitable LLM profile available for service tasks")


def validate_title(title: str, case_text: str) -> tuple[bool, str]:
    """Check whether a generated title is acceptable.

    Returns:
        (valid: bool, reason: str) — reason explains why validation failed.
    """
    import re as _re

    if len(title) < 10:
        return False, "Zu kurz (< 10 Zeichen)"
    if len(title) > 150:
        return False, "Zu lang (> 150 Zeichen)"
    if title.lower()[:15] in case_text.lower()[:50]:
        return False, "Identisch mit Fallbeschreibung"
    meta_patterns = [
        "the user",
        "the case",
        "this debate",
        "würde gerne",
        "der benutzer",
        "der fall",
        "diese debatte",
        "hier ist",
        "here is",
        "i suggest",
        "ich schlage",
    ]
    if any(p in title.lower() for p in meta_patterns):
        return False, "Enthält Meta-Text"
    if _re.match(r"^[\s\"'„" r"''`\-–:.,!?]+$", title):
        return False, "Nur Sonderzeichen"
    return True, "OK"


def _extract_title_from_verbose(text: str) -> str:
    """Extract just the title from verbose/reasoning-style LLM output.

    Handles models (e.g. MiMo) that output chain-of-thought reasoning with
    the final answer appended at the end.
    """
    if not text or len(text) < 150:
        return ""

    _re = __import__("re")

    markers = [
        r"Final title:\s*",
        r"Title:\s*",
        r"Answer:\s*",
        r"I'll go with:\s*",
        r"I think I'll use:\s*",
        r"I will use:\s*",
        r"Let me use:\s*",
        r"So the title is:\s*",
        r"The best title is:\s*",
        r"Abschließender Titel:\s*",
        r"Titel:\s*",
        r"Antwort:\s*",
        r"Abschließend:\s*",
        r"Ich verwende:\s*",
        r"Der beste Titel ist:\s*",
        r"Der Titel lautet:\s*",
    ]

    for marker in markers:
        parts = _re.split(marker, text, flags=_re.IGNORECASE)
        if len(parts) >= 2:
            candidate = parts[-1].strip()
            if 10 <= len(candidate) <= 200:
                for ch in ['"', "'", "„", "`"]:
                    candidate = candidate.strip(ch)
                return candidate.strip()

    # No marker found: take the last sentence (or last ~120 chars)
    sentences = _re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) >= 2:
        tail = sentences[-1].strip()
        if 10 <= len(tail) <= 200:
            return tail

    return ""


def _post_process_title(raw: str, case_text: str) -> str:
    """Clean and validate a generated title, falling back if needed."""
    _re = __import__("re")
    verbose = [
        r"^Here(?:'s| is) (?:a |the |an )?(?:suggested |proposed )?(?:debate )?title[:\s]*",
        r"^The title is[:\s]*",
        r"^Title[:\s]*",
        r"^I suggest[:\s]*",
        r"^I propose[:\s]*",
        r"^I think[:\s]*",
        r"^Der Titel lautet[:\s]*",
        r"^Titel[:\s]*",
        r"^Hier ist ein Titel[:\s]*",
        r"^Ich schlage vor[:\s]*",
        r"^Ein passender Titel (?:wäre|ist)[:\s]*",
    ]
    cleaned = raw.strip()
    for pat in verbose:
        cleaned = _re.sub(pat, "", cleaned, count=1, flags=_re.IGNORECASE).strip()
    for ch in ['"', "'", "„", """, """, """, """, "`", "-", "–", ":", ".", ","]:
        cleaned = cleaned.strip(ch)
    cleaned = cleaned.strip()

    if not cleaned or len(cleaned) < 15 or len(cleaned) > 150:
        return _fallback_title(case_text)

    reflection = [
        r"\b(?:the user|der benutzer)\b",
        r"\bbased on\b",
        r"\bbasierend auf\b",
        r"\b(?:description|beschreibung)\b.*\b(?:about|um)\b",
        r"^-\s",
    ]
    if any(_re.search(p, cleaned, _re.IGNORECASE) for p in reflection):
        return _fallback_title(case_text)

    # Final validation using standalone validate_title()
    valid, reason = validate_title(cleaned, case_text)
    if not valid:
        logger.debug("Title validation failed: %s — %s", reason, cleaned[:80])
        return _fallback_title(case_text)

    return cleaned


def _fallback_title(case_text: str) -> str:
    """Fallback: use beginning of case text as title."""
    fallback = case_text[:120].strip()
    for sep in [".", "?", "!"]:
        if sep in fallback:
            fallback = fallback[: fallback.rfind(sep) + 1]
            break
    if len(fallback) > 150:
        fallback = fallback[:147] + "..."
    return fallback
