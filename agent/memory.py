"""Thin wrapper around the Hindsight client. All memory reads and writes go through this module."""

from hindsight_client import Hindsight

from agent.config import Settings
from agent.models import HistoricalIncident, Incident, Outcome, SimilarIncident

BANK_MISSION = (
    "You are the incident memory for ShopFast, an e-commerce platform. "
    "Remember incidents, root causes, fixes that worked and fixes that failed."
)


class IncidentMemory:
    def __init__(self, settings: Settings) -> None:
        self._bank_id = settings.hindsight_bank_id
        self._client = Hindsight(
            base_url=settings.hindsight_base_url,
            api_key=settings.hindsight_api_key,
        )

    def ensure_bank(self) -> None:
        """Create the shared memory bank if it does not exist yet."""
        raise NotImplementedError  # TODO(memory owner): client.create_bank(...)

    def retain_historical(self, incident: HistoricalIncident) -> None:
        """Store one seeded past incident. Uses incident_id as document_id."""
        raise NotImplementedError  # TODO(memory owner): client.retain(...)

    def retain_outcome(self, incident: Incident, outcome: Outcome) -> None:
        """Store a newly resolved (or failed) incident so future recalls can use it."""
        raise NotImplementedError  # TODO(memory owner): client.retain(...)

    def recall_similar(self, incident: Incident, limit: int = 5) -> list[SimilarIncident]:
        """Return past incidents similar to the given one, with source references."""
        raise NotImplementedError  # TODO(memory owner): client.recall(..., include_chunks=True)
