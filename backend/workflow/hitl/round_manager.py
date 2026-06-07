"""HITL round manager — coordinates HITL interactions across debate rounds.

Provides high-level coordination for:
- Injecting user context at the right point in the workflow
- Managing agent query lifecycle (create → wait → resolve)
- Tracking interaction history per round
- Providing round-level HITL statistics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.workflow.hitl.api import (
    get_pending_injects,
)

logger = logging.getLogger(__name__)


@dataclass
class RoundHITLStats:
    """HITL statistics for a single debate round."""

    round: int
    injects_consumed: int = 0
    queries_triggered: int = 0
    queries_answered: int = 0
    queries_timed_out: int = 0
    total_pause_seconds: float = 0.0
    interactions: list[dict] = field(default_factory=list)


@dataclass
class DebateHITLSummary:
    """Aggregated HITL statistics for an entire debate."""

    debate_id: str
    total_interactions: int = 0
    total_injects: int = 0
    total_queries: int = 0
    total_responses: int = 0
    total_timeouts: int = 0
    total_pause_seconds: float = 0.0
    rounds: list[RoundHITLStats] = field(default_factory=list)

    @property
    def query_answer_rate(self) -> float:
        """Percentage of agent queries that were answered by the user."""
        if self.total_queries == 0:
            return 0.0
        return self.total_responses / self.total_queries

    @property
    def average_pause_per_round(self) -> float:
        """Average pause duration per round."""
        if not self.rounds:
            return 0.0
        return self.total_pause_seconds / len(self.rounds)


class HITLRoundManager:
    """Manages HITL interactions across debate rounds.

    This manager is instantiated per debate and tracks all HITL activity.
    It provides methods for the workflow nodes to report HITL events and
    for the API to query HITL statistics.
    """

    def __init__(self, debate_id: str) -> None:
        """Initialise HITLRoundManager."""
        self.debate_id = debate_id
        self._rounds: dict[int, RoundHITLStats] = {}
        self._current_round: int = 0

    def start_round(self, round_num: int) -> None:
        """Mark the start of a new round."""
        self._current_round = round_num
        if round_num not in self._rounds:
            self._rounds[round_num] = RoundHITLStats(round=round_num)
        logger.debug("HITL round manager: round %d started for debate %s", round_num, self.debate_id)

    def record_inject(self, round_num: int, interaction: dict) -> None:
        """Record a consumed inject interaction."""
        stats = self._rounds.setdefault(round_num, RoundHITLStats(round=round_num))
        stats.injects_consumed += 1
        stats.interactions.append(interaction)

    def record_query(self, round_num: int, interaction: dict) -> None:
        """Record an agent query."""
        stats = self._rounds.setdefault(round_num, RoundHITLStats(round=round_num))
        stats.queries_triggered += 1
        stats.interactions.append(interaction)

    def record_response(self, round_num: int, interaction: dict) -> None:
        """Record a user response to an agent query."""
        stats = self._rounds.setdefault(round_num, RoundHITLStats(round=round_num))
        stats.queries_answered += 1
        stats.interactions.append(interaction)

    def record_timeout(self, round_num: int) -> None:
        """Record a query timeout."""
        stats = self._rounds.setdefault(round_num, RoundHITLStats(round=round_num))
        stats.queries_timed_out += 1

    def record_pause(self, round_num: int, duration_seconds: float) -> None:
        """Record a pause duration."""
        stats = self._rounds.setdefault(round_num, RoundHITLStats(round=round_num))
        stats.total_pause_seconds += duration_seconds

    def get_round_stats(self, round_num: int) -> RoundHITLStats | None:
        """Get HITL stats for a specific round."""
        return self._rounds.get(round_num)

    def get_summary(self) -> DebateHITLSummary:
        """Get aggregated HITL statistics for the entire debate."""
        summary = DebateHITLSummary(debate_id=self.debate_id)

        for stats in self._rounds.values():
            summary.total_injects += stats.injects_consumed
            summary.total_queries += stats.queries_triggered
            summary.total_responses += stats.queries_answered
            summary.total_timeouts += stats.queries_timed_out
            summary.total_pause_seconds += stats.total_pause_seconds
            summary.rounds.append(stats)

        summary.total_interactions = summary.total_injects + summary.total_queries + summary.total_responses

        return summary

    def should_allow_query(self, round_num: int, max_interrupts: int) -> bool:
        """Check if another query is allowed in this round."""
        stats = self._rounds.get(round_num)
        if not stats:
            return True
        return stats.queries_triggered < max_interrupts

    def get_pending_context(self, agent_role: str, round_num: int) -> str:
        """Get formatted context from pending injects for an agent.

        This is a convenience method that combines inject retrieval
        with formatting for the agent prompt.
        """
        pending = get_pending_injects(self.debate_id)
        if not pending:
            return ""

        relevant = []
        for inject in pending:
            metadata = inject.get("metadata", {})
            target_agent = metadata.get("target_agent")

            # Filter by target agent
            if target_agent and target_agent != agent_role:
                continue

            relevant.append(inject)

        if not relevant:
            return ""

        lines = []
        for inject in relevant:
            priority = inject.get("metadata", {}).get("priority", "normal")
            prefix = f"[{priority.upper()}] " if priority != "normal" else ""
            lines.append(f"{prefix}{inject['content']}")

        return "\n\n--- USER CONTEXT ---\n" + "\n".join(lines) + "\n--- END CONTEXT ---\n"


# ---------------------------------------------------------------------------
# Global manager registry
# ---------------------------------------------------------------------------

_managers: dict[str, HITLRoundManager] = {}


def get_round_manager(debate_id: str) -> HITLRoundManager:
    """Get or create the HITL round manager for a debate."""
    if debate_id not in _managers:
        _managers[debate_id] = HITLRoundManager(debate_id)
    return _managers[debate_id]


def remove_round_manager(debate_id: str) -> None:
    """Remove the round manager for a completed/deleted debate."""
    _managers.pop(debate_id, None)
