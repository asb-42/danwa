"""Bundle Resolver — resolves AgentBundle references to fully populated ResolvedBundle.

Takes an AgentBundle (which only contains IDs) and loads all referenced
entities from the repository, then assembles the complete system prompt.
"""

from __future__ import annotations

import logging

from backend.blueprints.models import (
    AgentBundle,
    ResolvedBundle,
    RoleType,
    ToneProfile,
)
from backend.blueprints.module_lookups import (
    resolve_role_type,
)
from backend.blueprints.repository import BlueprintRepository
from backend.services.composer_service import ComposerService, Composition

logger = logging.getLogger(__name__)


class BundleResolver:
    """Resolves AgentBundle ID references into a fully populated ResolvedBundle."""

    def __init__(self, repo: BlueprintRepository | None = None):
        """Initialise BundleResolver."""
        self.repo = repo or BlueprintRepository()

    def resolve(self, bundle: AgentBundle) -> ResolvedBundle:
        """Resolve all references in a Bundle and assemble the system prompt.

        Args:
            bundle: The AgentBundle to resolve.

        Returns:
            ResolvedBundle with all referenced entities loaded inline.

        Raises:
            ValueError: If required references (llm_profile_id, role_type_id) are missing.
        """
        llm_profile = self.repo.get_llm_profile(bundle.llm_profile_id)
        if not llm_profile:
            raise ValueError(f"Bundle '{bundle.id}' references non-existent LLM profile '{bundle.llm_profile_id}'")

        role_type = resolve_role_type(bundle.role_type_id)
        if not role_type:
            raise ValueError(f"Bundle '{bundle.id}' references non-existent RoleType '{bundle.role_type_id}'")

        tone_profile: ToneProfile | None = None
        if bundle.tone_profile_id:
            tone_profile = self.repo.get_tone_profile(bundle.tone_profile_id)
            if not tone_profile:
                logger.warning(
                    "Bundle '%s' references non-existent ToneProfile '%s' — skipping",
                    bundle.id,
                    bundle.tone_profile_id,
                )

        # Path C (BundleComposer): assemble from composition when present
        if bundle.composition is not None:
            composition = Composition(
                agent_core_id=bundle.composition.agent_core_id,
                argumentation_pattern_id=bundle.composition.argumentation_pattern_id,
                tone_profile_id=bundle.tone_profile_id or "",
                prompt_modifier_id=bundle.composition.prompt_modifier_id,
            )
            system_prompt = ComposerService().compose(composition)
        else:
            system_prompt = self._assemble_system_prompt(
                role_type=role_type,
                tone_profile=tone_profile,
            )

        return ResolvedBundle(
            bundle_id=bundle.id,
            bundle_name=bundle.name,
            llm_profile=llm_profile,
            role_type=role_type,
            tone_profile=tone_profile,
            system_prompt=system_prompt,
            model_params=bundle.model_params,
        )

    @staticmethod
    def _assemble_system_prompt(
        role_type: RoleType,
        tone_profile: ToneProfile | None = None,
    ) -> str:
        """Assemble the system prompt from Bundle components.

        Priority order:
        1. RoleType name + description + category hints
        2. ToneProfile custom instructions (appended)

        Args:
            role_type: The RoleType (always present).
            tone_profile: Optional ToneProfile for communication style.

        Returns:
            Assembled system prompt string.
        """
        parts: list[str] = []

        # 1. Role identity header
        icon = role_type.icon or "👤"
        parts.append(f"# {icon} {role_type.name}")

        if role_type.description:
            parts.append(role_type.description)

        # 2. Category-based behavioral hint
        if role_type.category == "functional":
            parts.append("\nYou are participating in a structured analytical debate.")
        elif role_type.category == "formative":
            parts.append("\nYou are shaping the discourse and guiding the conversation.")

        # 3. ToneProfile instructions (appended at the end)
        if tone_profile:
            tone_hints = _tone_profile_to_instructions(tone_profile)
            if tone_hints:
                parts.append(f"\n## Communication Style\n{tone_hints}")

        return "\n".join(parts).strip()


def _tone_profile_to_instructions(tone: ToneProfile) -> str:
    """Convert a ToneProfile into natural language instructions."""
    hints: list[str] = []

    style_descriptions = {
        "heated": "Engage with passion and intensity. Challenge ideas vigorously.",
        "academic": "Maintain scholarly rigor. Cite reasoning and structure arguments formally.",
        "conversational": "Use a relaxed, approachable tone. Speak naturally.",
        "socratic": "Ask probing questions. Guide others to discover insights through inquiry.",
        "neutral": "Maintain an even, objective tone. Avoid emotional language.",
    }
    if tone.style in style_descriptions:
        hints.append(style_descriptions[tone.style])

    formality_map = {
        0.0: "Use very casual, informal language.",
        0.25: "Use mostly casual language with occasional formal phrases.",
        0.5: "Balance formal and informal language appropriately.",
        0.75: "Use mostly formal language with occasional casual phrases.",
        1.0: "Use strictly formal, professional language.",
    }
    # Find closest formality level
    closest = min(formality_map.keys(), key=lambda k: abs(k - tone.formality))
    hints.append(formality_map[closest])

    verbosity_map = {
        "concise": "Be brief and to the point. Avoid unnecessary elaboration.",
        "normal": "Provide adequate detail without being overly verbose.",
        "verbose": "Be thorough and detailed. Explain your reasoning fully.",
    }
    if tone.verbosity in verbosity_map:
        hints.append(verbosity_map[tone.verbosity])

    if tone.emotional_valence > 0.7:
        hints.append("Express strong emotions and passion in your responses.")
    elif tone.emotional_valence < 0.3:
        hints.append("Maintain emotional detachment. Focus on facts and logic.")

    rhetorical_map = {
        "questioning": "Frame your contributions as questions to provoke thought.",
        "assertive": "State your positions clearly and confidently.",
        "dialectic": "Present thesis, antithesis, and work toward synthesis.",
    }
    if tone.rhetorical_mode in rhetorical_map:
        hints.append(rhetorical_map[tone.rhetorical_mode])

    if tone.custom_instructions:
        hints.append(tone.custom_instructions)

    return "\n".join(hints)


def resolve_bundle(bundle_id: str, repo: BlueprintRepository | None = None) -> ResolvedBundle:
    """Convenience function: resolve a Bundle by ID.

    Args:
        bundle_id: The AgentBundle ID to resolve.
        repo: Optional repository instance.

    Returns:
        ResolvedBundle with all references loaded.

    Raises:
        ValueError: If the bundle does not exist.
    """
    resolver = BundleResolver(repo)
    bundle = resolver.repo.get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle '{bundle_id}' not found")
    return resolver.resolve(bundle)
