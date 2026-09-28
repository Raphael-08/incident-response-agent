"""Orchestrates the incident flow: submit, recall, suggest, record outcome."""

from agent.llm import IncidentAdvisor
from agent.memory import IncidentMemory
from agent.models import Incident, Outcome, Suggestion


class IncidentService:
    def __init__(self, memory: IncidentMemory, advisor: IncidentAdvisor) -> None:
        self._memory = memory
        self._advisor = advisor

    def analyze_incident(self, incident: Incident) -> Suggestion:
        """Steps 1-3: recall similar past incidents, then ask the LLM for root cause and fix steps."""
        raise NotImplementedError  # TODO(agent owner)

    def record_outcome(self, incident: Incident, outcome: Outcome) -> None:
        """Step 4: retain the outcome in Hindsight so the agent learns from it."""
        raise NotImplementedError  # TODO(agent owner)
