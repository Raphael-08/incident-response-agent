"""Data models for incidents, outcomes and agent suggestions. All user input is validated here."""

import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_LOG_CHARS = 8000
MAX_TEXT_CHARS = 2000
INCIDENT_ID_PATTERN = r"^INC-\d{4,16}$"
SERVICE_PATTERN = r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"

# One step or attempt in a list: not blank, bounded length.
Step = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)]


def new_incident_id() -> str:
    """Generate an ID like INC-26092814301207: UTC timestamp plus 2 random digits."""
    stamp = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    return f"INC-{stamp}{secrets.randbelow(100):02d}"


class Severity(str, Enum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"


class Incident(BaseModel):
    """A new incident submitted by an engineer. The ID is generated when not supplied."""

    # Strip before length checks, so whitespace cannot satisfy min_length.
    model_config = ConfigDict(str_strip_whitespace=True)

    incident_id: str = Field(default_factory=new_incident_id, pattern=INCIDENT_ID_PATTERN)
    service: str = Field(min_length=1, max_length=64, pattern=SERVICE_PATTERN)
    severity: Severity
    title: str = Field(min_length=3, max_length=200)
    symptoms: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)
    error_log: str = Field(default="", max_length=MAX_LOG_CHARS)
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Outcome(BaseModel):
    """What actually happened after the engineer worked on the incident."""

    model_config = ConfigDict(str_strip_whitespace=True)

    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    resolved: bool
    actual_root_cause: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)
    steps_that_worked: list[Step] = Field(default_factory=list, max_length=20)
    failed_attempts: list[Step] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=MAX_TEXT_CHARS)


class HistoricalIncident(Incident):
    """A past incident with its resolution. Used for seed data."""

    reported_at: datetime  # required: a missing date must not default to now

    root_cause: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)
    resolution_steps: list[Step] = Field(min_length=1, max_length=20)
    failed_attempts: list[Step] = Field(default_factory=list, max_length=20)
    lesson: str = Field(default="", max_length=MAX_TEXT_CHARS)


class SimilarIncident(BaseModel):
    """A past incident recalled from Hindsight memory, with its source reference."""

    incident_id: str
    summary: str
    source_text: str = ""


class LearnedPattern(BaseModel):
    """An observation Hindsight consolidated from many incidents, e.g. 'restarting pods never fixes pool exhaustion'."""

    text: str


class RemediationAction(BaseModel):
    """An allow-listed runbook action the agent may propose. Names come from ShopFast's /ops/actions."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    description: str = Field(min_length=3, max_length=MAX_TEXT_CHARS)


class RemediationAttempt(BaseModel):
    """Audit record of one proposed action: what, why, whether a human approved it, and what verification saw."""

    action: str
    description: str
    reason: str = ""
    approved: bool
    executed: bool
    verified: bool
    health: dict[str, int] = Field(default_factory=dict)  # e.g. {"POST /checkout": 200}
    error: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Suggestion(BaseModel):
    """The agent's answer for a new incident."""

    similar_incidents: list[SimilarIncident] = Field(default_factory=list)
    learned_patterns: list[LearnedPattern] = Field(default_factory=list)
    probable_root_cause: str
    fix_steps: list[Step] = Field(default_factory=list)
    avoid_steps: list[Step] = Field(default_factory=list)
    confidence: str = Field(pattern=r"^(low|medium|high)$")
    memory_used: bool
    llm_error: str | None = None  # set when the LLM failed; recalled memory is still returned
    proposed_action: str | None = None  # allow-listed runbook action; runs only after human approval
    action_reason: str = ""
