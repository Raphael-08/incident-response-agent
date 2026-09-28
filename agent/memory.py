"""Thin wrapper around the Hindsight client. All memory reads and writes go through this module."""

from hindsight_client import Hindsight

from agent.config import Settings
from agent.log_normalizer import normalize_log
from agent.models import HistoricalIncident, Incident, LearnedPattern, Outcome, SimilarIncident

BANK_MISSION = (
    "You are the incident memory for ShopFast, an e-commerce platform. "
    "Remember incidents, root causes, fixes that worked and fixes that failed."
)

# "world" = stored incident facts; "observation" = patterns Hindsight consolidates across incidents.
INCIDENT_FACT_TYPES = ["world"]
LEARNED_PATTERN_TYPES = ["observation"]


def build_recall_query(incident: Incident) -> str:
    """Build the recall query from the incident. The log is normalized so noise does not hurt matching."""
    return f"{incident.service}: {incident.title}. {incident.symptoms}. {normalize_log(incident.error_log)}"


class IncidentMemory:
    def __init__(self, settings: Settings) -> None:
        self._bank_id = settings.hindsight_bank_id
        self._client = Hindsight(
            base_url=settings.hindsight_base_url,
            api_key=settings.hindsight_api_key,
        )

    @property
    def bank_id(self) -> str:
        return self._bank_id

    def ensure_bank(self) -> None:
        """Create the memory bank if it does not exist yet."""
        raise NotImplementedError  # TODO(memory owner): client.create_bank(bank_id, name, mission=BANK_MISSION)

    def retain_historical(self, incident: HistoricalIncident) -> None:
        """Store one seeded past incident. Uses incident_id as document_id."""
        raise NotImplementedError  # TODO(memory owner): client.retain(...)

    def retain_outcome(self, incident: Incident, outcome: Outcome) -> None:
        """Store a newly resolved (or failed) incident so future recalls can use it."""
        raise NotImplementedError  # TODO(memory owner): client.retain(...)

    def recall_similar(self, incident: Incident, limit: int = 5) -> list[SimilarIncident]:
        """Return past incidents similar to the given one, with source references."""
        raise NotImplementedError  # TODO(memory owner): client.recall(query=build_recall_query(incident),
        #                                  types=INCIDENT_FACT_TYPES, include_chunks=True)

    def recall_learned_patterns(self, incident: Incident) -> list[LearnedPattern]:
        """Return patterns Hindsight learned across many incidents (observations) relevant to this one."""
        raise NotImplementedError  # TODO(memory owner): client.recall(query=build_recall_query(incident),
        #                                  types=LEARNED_PATTERN_TYPES)
