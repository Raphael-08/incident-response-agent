"""Groq LLM wrapper. Turns recalled memories into a structured Suggestion."""

from groq import Groq

from agent.config import Settings
from agent.models import Incident, SimilarIncident, Suggestion

MAX_RETRIES = 2


class LLMError(RuntimeError):
    """Raised when the LLM fails or returns output we cannot parse."""


class IncidentAdvisor:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.groq_model
        self._client = Groq(api_key=settings.groq_api_key)

    def suggest(self, incident: Incident, similar: list[SimilarIncident]) -> Suggestion:
        """Ask the LLM for a root cause and ordered fix steps.

        Must return JSON that validates as Suggestion. Retries up to MAX_RETRIES
        on API errors or invalid JSON, then raises LLMError.
        """
        raise NotImplementedError  # TODO(agent owner)
