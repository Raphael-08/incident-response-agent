"""Orchestrates the incident flow: detect, recall, suggest, act (with approval), verify, learn."""

from collections.abc import Sequence

from agent.actions import ShopFastClient, ShopFastError
from agent.intake import incident_from_alert
from agent.llm import IncidentAdvisor, LLMError
from agent.memory import IncidentMemory, IncidentMemoryError
from agent.models import Incident, Outcome, RemediationAction, RemediationAttempt, Suggestion

LLM_UNAVAILABLE = "AI suggestion unavailable. Review the similar past incidents below."


def _is_healthy(health: dict[str, int]) -> bool:
    return bool(health) and all(status < 400 for status in health.values())


def _failing(health: dict[str, int]) -> str:
    return ", ".join(f"{endpoint} {status}" for endpoint, status in health.items() if status >= 400)


def build_outcome(incident: Incident, suggestion: Suggestion, attempts: Sequence[RemediationAttempt]) -> Outcome:
    """The outcome the agent records after verifying its latest action. Rejected actions never ran, so they are
    left out; executed actions that did not restore health are failed attempts."""
    executed = [a for a in attempts if a.executed]
    last = executed[-1]
    health = ", ".join(f"{endpoint} {status}" for endpoint, status in last.health.items())
    return Outcome(
        incident_id=incident.incident_id,
        resolved=last.verified,
        actual_root_cause=suggestion.probable_root_cause,
        steps_that_worked=[f"{a.action}: {a.description}" for a in executed if a.verified],
        failed_attempts=[f"{a.action}: {a.description} (checkout still failing: {_failing(a.health)})"
                         for a in executed if not a.verified],
        notes=f"Recorded automatically by the agent after verifying ShopFast. Health after last action: {health}.",
    )


class IncidentService:
    def __init__(self, memory: IncidentMemory, advisor: IncidentAdvisor, shop: ShopFastClient | None = None) -> None:
        self._memory = memory
        self._advisor = advisor
        self._shop = shop

    def _actions(self) -> list[RemediationAction]:
        try:
            return self._shop.list_actions()
        except ShopFastError:
            return []

    def detect_incident(self) -> Incident | None:
        """Probe ShopFast like a monitor. If an endpoint fails, open an incident from ShopFast's latest alert.

        Returns None when the shop is healthy, so an old alert is never imported after it was fixed.
        """
        if self._shop is None:
            raise ShopFastError("ShopFast is not configured")
        if _is_healthy(self._shop.health_check()):
            return None
        alert = self._shop.latest_incident()
        return incident_from_alert(alert) if alert else None

    def analyze_incident(self, incident: Incident, tried_actions: Sequence[str] = ()) -> Suggestion:
        """Recall similar past incidents, then ask the LLM for root cause, fix steps and one action to propose.

        Raises IncidentMemoryError when similar incidents cannot be recalled. Learned patterns are optional, and so
        are actions: without ShopFast the agent only advises. When the LLM fails, the recalled memory is still
        returned with llm_error set.
        """
        similar = self._memory.recall_similar(incident)
        try:
            patterns = self._memory.recall_learned_patterns(incident)
        except IncidentMemoryError:
            patterns = []
        try:
            if self._shop is None:
                return self._advisor.suggest(incident, similar, patterns)
            return self._advisor.suggest(incident, similar, patterns, actions=self._actions(),
                                         tried_actions=list(tried_actions))
        except LLMError as exc:
            return Suggestion(
                similar_incidents=similar,
                learned_patterns=patterns,
                probable_root_cause=LLM_UNAVAILABLE,
                confidence="low",
                memory_used=bool(similar),
                llm_error=str(exc),
            )

    def remediate(self, incident: Incident, suggestion: Suggestion, approved: bool,
                  previous_attempts: Sequence[RemediationAttempt] = ()) -> RemediationAttempt:
        """Act -> verify -> learn for the suggestion's proposed action.

        Runs nothing unless a human approved it. After running, probes ShopFast and records the outcome in memory
        automatically, including earlier failed attempts, so the next similar incident can recall it.
        """
        if self._shop is None or not suggestion.proposed_action:
            raise ValueError("No proposed action to run")
        actions = {a.name: a for a in self._shop.list_actions()}
        action = actions.get(suggestion.proposed_action)
        if action is None:
            raise ValueError(f"Action {suggestion.proposed_action!r} is not allow-listed")
        attempt = dict(action=action.name, description=action.description, reason=suggestion.action_reason,
                       approved=approved)
        if not approved:
            return RemediationAttempt(**attempt, executed=False, verified=False)
        try:
            self._shop.run_action(action.name)
            health = self._shop.health_check()
        except ShopFastError as exc:
            return RemediationAttempt(**attempt, executed=False, verified=False, error=str(exc))
        result = RemediationAttempt(**attempt, executed=True, verified=_is_healthy(health), health=health)
        try:
            self._memory.retain_outcome(incident, build_outcome(incident, suggestion, [*previous_attempts, result]))
        except IncidentMemoryError as exc:
            result.error = f"Action ran, but the outcome was not recorded in memory: {exc}"
        return result

    def record_outcome(self, incident: Incident, outcome: Outcome) -> None:
        """Manual fallback: retain an outcome the engineer typed in."""
        self._memory.retain_outcome(incident, outcome)
