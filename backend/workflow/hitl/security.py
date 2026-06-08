"""HITL security — prompt injection detection and content sanitization.

Detects common prompt injection patterns in user-supplied content
before it is passed to LLM agents.  Uses a layered approach:
1. Pattern matching against known injection signatures
2. Structural analysis (role-play attempts, system prompt overrides)
3. Length and encoding validation
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Injection pattern database
# ---------------------------------------------------------------------------

# Each pattern is a compiled regex with a severity level.
# Severity: 'low' (suspicious), 'medium' (likely injection), 'high' (definite injection)

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # --- System prompt override attempts ---
    (
        re.compile(
            r"(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|earlier|system)\s+(?:instructions?|prompts?|rules?|context)",
            re.IGNORECASE,
        ),
        "high",
        "system_override",
    ),
    (
        re.compile(
            r"(?:you\s+are\s+now|from\s+now\s+on|new\s+instructions?|act\s+as\s+if)\b",
            re.IGNORECASE,
        ),
        "high",
        "role_hijack",
    ),
    (
        re.compile(
            r"(?:system\s*prompt|initial\s*prompt|hidden\s*instructions?)\s*(?:is|are|:|=)",
            re.IGNORECASE,
        ),
        "high",
        "system_probe",
    ),
    # --- Role-play / persona injection ---
    (
        re.compile(
            r"(?:pretend|imagine|roleplay|role\s*play)\s+(?:you\s+are|that\s+you|to\s+be)\b",
            re.IGNORECASE,
        ),
        "medium",
        "roleplay_attempt",
    ),
    (
        re.compile(
            r"\b(?:DAN|jailbreak|developer\s*mode|god\s*mode|unrestricted)\b",
            re.IGNORECASE,
        ),
        "high",
        "jailbreak_keyword",
    ),
    # --- Prompt extraction attempts ---
    (
        re.compile(
            r"(?:repeat|show|display|print|output|reveal|tell\s+me)\s+(?:your|the)\s+(?:system|initial|original|hidden)\s+(?:prompt|instructions?|rules?)",
            re.IGNORECASE,
        ),
        "high",
        "prompt_extraction",
    ),
    (
        re.compile(
            r"(?:what|show)\s+(?:are|is)\s+your\s+(?:system|initial)\s+(?:prompt|instructions?)",
            re.IGNORECASE,
        ),
        "medium",
        "prompt_probe",
    ),
    # --- Delimiter / boundary injection ---
    (
        re.compile(
            r"(?:---+|===+|```+)\s*(?:system|assistant|user|human|ai)\s*(?:---+|===+|```+)",
            re.IGNORECASE,
        ),
        "high",
        "delimiter_injection",
    ),
    (
        re.compile(
            r"<\|(?:im_start|im_end|system|endoftext)\|>",
            re.IGNORECASE,
        ),
        "high",
        "token_injection",
    ),
    # --- Encoding / obfuscation attempts ---
    (
        re.compile(
            r"(?:base64|rot13|hex\s*encode|url\s*encode)\s*(?:decode|this|the\s+following)",
            re.IGNORECASE,
        ),
        "medium",
        "encoding_attempt",
    ),
    (
        re.compile(
            r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){3,}",
            re.IGNORECASE,
        ),
        "low",
        "hex_sequence",
    ),
    # --- Instruction injection via markdown/XML ---
    (
        re.compile(
            r"(?:<instructions?>|<system>|<prompt>|<context>)",
            re.IGNORECASE,
        ),
        "medium",
        "xml_injection",
    ),
    # --- Multi-language injection patterns ---
    (
        re.compile(
            r"(?:ignoriere|vergiss|überschreibe)\s+(?:alle\s+)?(?:vorherigen|vorangegangenen)\s+(?:Anweisungen|Befehle|Regeln)",
            re.IGNORECASE,
        ),
        "high",
        "system_override_de",
    ),
]


@dataclass
class SecurityScanResult:
    """Result of a security scan on user input."""

    is_safe: bool
    risk_level: str  # 'none', 'low', 'medium', 'high'
    detections: list[dict] = field(default_factory=list)
    sanitized_content: str = ""

    @property
    def should_block(self) -> bool:
        """Whether the content should be blocked entirely."""
        return self.risk_level == "high"

    @property
    def should_warn(self) -> bool:
        """Whether the content should trigger a warning but still pass."""
        return self.risk_level == "medium"

    def to_dict(self) -> dict:
        """Convert to dict for logging/storage."""
        return {
            "is_safe": self.is_safe,
            "risk_level": self.risk_level,
            "detection_count": len(self.detections),
            "detections": self.detections,
        }


def scan_for_injection(content: str) -> SecurityScanResult:
    """Scan user-supplied content for prompt injection patterns.

    Args:
        content: The user input to scan.

    Returns:
        SecurityScanResult with risk assessment and detection details.
    """
    if not content or not content.strip():
        return SecurityScanResult(is_safe=True, risk_level="none")

    detections: list[dict] = []
    max_risk = "none"
    risk_order = {"none": 0, "low": 1, "medium": 2, "high": 3}

    for pattern, severity, category in _INJECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            detections.append(
                {
                    "category": category,
                    "severity": severity,
                    "matched_text": match.group(0)[:100],  # Truncate for logging
                    "position": match.start(),
                }
            )
            if risk_order.get(severity, 0) > risk_order.get(max_risk, 0):
                max_risk = severity

    # Additional structural checks
    structural = _check_structural_anomalies(content)
    for det in structural:
        detections.append(det)
        if risk_order.get(det["severity"], 0) > risk_order.get(max_risk, 0):
            max_risk = det["severity"]

    is_safe = max_risk in ("none", "low")

    if detections:
        logger.info(
            "Security scan: %d detection(s), max risk=%s, categories=%s",
            len(detections),
            max_risk,
            [d["category"] for d in detections],
        )

    return SecurityScanResult(
        is_safe=is_safe,
        risk_level=max_risk,
        detections=detections,
        sanitized_content=content,  # Content is not modified, only flagged
    )


def _check_structural_anomalies(content: str) -> list[dict]:
    """Check for structural anomalies that may indicate injection attempts."""
    anomalies: list[dict] = []

    # Excessive length (potential context stuffing)
    if len(content) > 4000:
        anomalies.append(
            {
                "category": "excessive_length",
                "severity": "low",
                "matched_text": f"Content length: {len(content)} chars",
                "position": 0,
            }
        )

    # High ratio of special characters
    special_count = sum(1 for c in content if not c.isalnum() and not c.isspace())
    if len(content) > 50 and special_count / len(content) > 0.4:
        anomalies.append(
            {
                "category": "high_special_char_ratio",
                "severity": "low",
                "matched_text": f"Special char ratio: {special_count / len(content):.2f}",
                "position": 0,
            }
        )

    # Repeated patterns (potential padding attack)
    words = content.lower().split()
    if len(words) > 20:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.2:
            anomalies.append(
                {
                    "category": "repetitive_content",
                    "severity": "low",
                    "matched_text": f"Unique word ratio: {unique_ratio:.2f}",
                    "position": 0,
                }
            )

    return anomalies


def sanitize_for_display(content: str, max_length: int = 500) -> str:
    """Sanitize content for safe display in UI.

    Truncates and escapes potentially dangerous content by encoding
    HTML-significant characters as entities so that injected markup
    renders as literal text rather than being interpreted by the browser.
    """
    if len(content) > max_length:
        content = content[:max_length] + "..."
    # Encode HTML-significant characters to prevent XSS in display contexts.
    # Order matters: ampersand must be encoded first to avoid double-encoding.
    content = content.replace("&", "&").replace("<", "<").replace(">", ">")
    return content
