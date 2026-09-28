"""Learning evidence: which runbook actions worked or failed, read from outcomes the agent recorded in memory.

Only allow-listed action names inside the stored "Fix steps that worked" / "Fix attempts that did not work"
sections count, so every number shown traces back to a verified, recorded outcome. Seed incidents describe
fixes in free text and therefore add no evidence.
"""

import re
from collections.abc import Iterable

from agent.models import ActionEvidence, SimilarIncident

_SECTION = re.compile(
    r"(Fix steps that worked|Fix attempts that did not work):(.*?)"
    r"(?=Fix steps that worked:|Fix attempts that did not work:|Notes:|Lesson:|Status:|Root cause:|Incident INC-|\Z)",
    re.S,
)
_LISTED_ACTION = re.compile(r"(?:^|\s)- ([a-z][a-z0-9_]{2,63}):")


def action_evidence(similar: Iterable[SimilarIncident], action_names: Iterable[str]) -> list[ActionEvidence]:
    known = set(action_names)
    found: dict[str, ActionEvidence] = {}
    for item in similar:
        for heading, body in _SECTION.findall(item.source_text):
            for name in _LISTED_ACTION.findall(body):
                if name not in known:
                    continue
                evidence = found.setdefault(name, ActionEvidence(action=name))
                bucket = evidence.worked_in if heading == "Fix steps that worked" else evidence.failed_in
                if item.incident_id not in bucket:
                    bucket.append(item.incident_id)
    return sorted(found.values(), key=lambda e: (-len(e.worked_in), len(e.failed_in), e.action))
