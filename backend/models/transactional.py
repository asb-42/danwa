"""Pydantic models for Transactional Drafting workflow.

Defines the structured output types for Critic, Builder, and Pragmatist
nodes in the Transactional Drafting template.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Herkunftsnachweis (Klausel-Stammbaum) einer BuildResponse."""

    draft_version: int = Field(
        ...,
        description="Iteration, in der diese Revision erzeugt wurde",
    )
    critic_item_id: str = Field(
        ...,
        description="Referenz auf das CriticItem, das diese Revision ausgelöst hat",
    )
    original_text: str = Field(
        default="",
        max_length=1000,
        description="Der ursprüngliche Text, den der Critic beanstandet hat (context_quote oder flaw)",
    )
    revision_type: Literal["conservative", "radical", "minimal"] = Field(
        ...,
        description="Option A = conservative, B = radical, C = minimal",
    )
    pragmatist_verdict: str | None = Field(
        default=None,
        description="Verdict des Pragmatist: accept / revise / reject",
    )
    pragmatist_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Reality-Score aus der Pragmatist-Evaluation (feasibility)",
    )


class CriticItem(BaseModel):
    """Atomare Einheit von Kritik im Transactional Drafting."""

    critic_id: str = Field(
        ...,
        pattern=r"^c-\w+-\d{3}$",
        description="e.g. c-critic_1-003",
    )
    severity: Literal["blocking", "critical", "warning", "cosmetic"]
    target: str = Field(
        ...,
        max_length=500,
        description="Genaue Adresse des kritisierten Elements, z.B. Vertrag §3.2",
    )
    flaw: str = Field(
        ...,
        max_length=500,
        description="Präzise Beschreibung des Mangels",
    )
    principle: str = Field(
        ...,
        description="Die Regel, Norm oder Logik, gegen die verstoßen wird",
    )
    context_quote: str | None = Field(
        default=None,
        description="Wörtliches Zitat aus dem zu kritisierenden Text",
    )


class BuildResponse(BaseModel):
    """Atomare Lösung des Builder als Antwort auf ein CriticItem."""

    response_to: str = Field(..., description="Referenz auf critic_id")
    option_a: str = Field(
        ...,
        description="Konservative Reparatur: Behebung unter Beibehaltung der Architektur",
    )
    option_b: str = Field(
        ...,
        description="Radikales Redesign: Strukturelle Änderung zur Wurzelbehebung",
    )
    option_c: str | None = Field(
        default=None,
        description="Minimalüberlebens-Version, falls A und B scheitern",
    )
    recommendation: Literal["option_a", "option_b", "option_c", "none"]
    rationale: str = Field(
        ...,
        max_length=500,
        description="Max. 2 Sätze Begründung der Empfehlung",
    )
    risk_assessment: Literal["low", "medium", "high"]
    implementable: bool = Field(
        ...,
        description="Kann der Vorschlag sofort übernommen werden?",
    )
    provenance: Provenance | None = Field(
        default=None,
        description="Klausel-Stammbaum: Herkunft und Entscheidungsweg dieser Revision",
    )


class BuilderOutput(BaseModel):
    """Container für die gesamte Builder-Antwort."""

    build_responses: list[BuildResponse]
    global_revision: str | None = Field(
        default=None,
        description="Gesamtüberarbeitung des Dokuments/der Strategie",
    )
    constructivity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Berechnet: Anzahl BuildResponses / Anzahl empfangener CriticItems",
    )


class PragmatistEvaluation(BaseModel):
    """Bewertung einer einzelnen BuildResponse durch den Pragmatist."""

    response_to: str = Field(..., description="BuildResponse-ID")
    feasibility: float = Field(..., ge=0.0, le=1.0)
    process_risk: Literal["low", "medium", "high"]
    cost_time_estimate: str = Field(
        ...,
        description="Kurze Einschätzung, z.B. '2 Wochen, 5.000 EUR'",
    )
    verdict: Literal["accept", "revise", "reject"]
    revision_note: str | None = Field(
        default=None,
        description="Pflicht, wenn verdict != accept",
    )


class PragmatistOutput(BaseModel):
    """Container für die gesamte Pragmatist-Bewertung."""

    evaluations: list[PragmatistEvaluation]
    reality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Durchschnitt über alle Optionen",
    )
    blocking_concerns: list[str] = Field(
        default_factory=list,
        description="Gründe, warum eine Option trotz guter Idee scheitern würde",
    )


class PreservedElement(BaseModel):
    """Ein Element, das der Angel's Advocate als erhaltenswert identifiziert."""

    element_id: str = Field(
        ...,
        description="Eindeutige ID, z.B. 'aa-001'",
    )
    source_location: str = Field(
        ...,
        max_length=500,
        description="Adresse im Dokument, z.B. '§3.2 Abs. 1'",
    )
    preserved_text: str = Field(
        ...,
        max_length=1000,
        description="Der Text, der beibehalten werden soll",
    )
    rationale: str = Field(
        ...,
        max_length=500,
        description="Warum dieses Element kritisch ist und nicht verworfen werden darf",
    )
    priority: Literal["essential", "important", "useful"] = Field(
        ...,
        description="Wie wichtig die Erhaltung ist",
    )


class AngelsAdvocateOutput(BaseModel):
    """Container für die gesamte Angel's Advocate-Analyse."""

    preserved_elements: list[PreservedElement] = Field(
        ...,
        min_length=1,
        description="Elemente, die beibehalten werden müssen",
    )
    overall_stability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Wie stabil ist der aktuelle Stand (1.0 = sehr stabil)",
    )
    warning: str | None = Field(
        default=None,
        description="Warnung, wenn zu viele Elemente verworfen werden könnten",
    )
