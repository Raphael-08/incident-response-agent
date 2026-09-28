"""Orchestrates the incident flow: submit, recall, suggest, record outcome."""

from agent.llm import IncidentAdvisor, LLMError
from agent.memory import IncidentMemory, IncidentMemoryError
from agent.models import Incident, Outcome, Suggestion

LLM_UNAVAILABLE = "AI suggestion unavailable. Review the similar past incidents below."


class IncidentService:
    def __init__(self, memory: IncidentMemory, advisor: IncidentAdvisor) -> None:
        self._memory = memory
        self._advisor = advisor

    def analyze_incident(self, incident: Incident) -> Suggestion:
        """Steps 1-3: recall similar past incidents, then ask the LLM for root cause and fix steps.

        Raises IncidentMemoryError when similar incidents cannot be recalled. Learned patterns are optional.
        When the LLM fails, the recalled memory is still returned with llm_error set.
        """
        similar = self._memory.recall_similar(incident)
        try:
            patterns = self._memory.recall_learned_patterns(incident)
        except IncidentMemoryError:
            patterns = []
        try:
            return self._advisor.suggest(incident, similar, patterns)
        except LLMError as exc:
            return Suggestion(
                similar_incidents=similar,
                learned_patterns=patterns,
                probable_root_cause=LLM_UNAVAILABLE,
                confidence="low",
                memory_used=bool(similar),
                llm_error=str(exc),
            )

    def record_outcome(self, incident: Incident, outcome: Outcome) -> None:
        """Step 4: retain the outcome in Hindsight so the agent learns from it."""
        self._memory.retain_outcome(incident, outcome)
