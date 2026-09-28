"""IncidentService tests with fake memory and advisor."""

import pytest

from agent.llm import LLMError
from agent.memory import IncidentMemoryError
from agent.models import Incident, LearnedPattern, Outcome, SimilarIncident, Suggestion
from agent.service import IncidentService

SIMILAR = [SimilarIncident(incident_id="INC-1042", summary="Pool exhausted")]
PATTERNS = [LearnedPattern(text="Restarting pods never fixes pool exhaustion")]
INCIDENT = Incident(incident_id="INC-2001", service="payment-api", severity="SEV1",
                    title="Checkout failing", symptoms="503 on checkout")
OUTCOME = Outcome(incident_id="INC-2001", resolved=True, actual_root_cause="Pool exhausted")


class FakeMemory:
    def __init__(self, similar=SIMILAR, patterns=PATTERNS, similar_error=None, patterns_error=None):
        self.calls = []
        self._similar, self._patterns = similar, patterns
        self._similar_error, self._patterns_error = similar_error, patterns_error

    def recall_similar(self, incident):
        self.calls.append(("recall_similar", incident))
        if self._similar_error:
            raise self._similar_error
        return self._similar

    def recall_learned_patterns(self, incident):
        self.calls.append(("recall_learned_patterns", incident))
        if self._patterns_error:
            raise self._patterns_error
        return self._patterns

    def retain_outcome(self, incident, outcome):
        self.calls.append(("retain_outcome", incident, outcome))


class FakeAdvisor:
    def __init__(self, error=None):
        self.calls = []
        self._error = error

    def suggest(self, incident, similar, patterns):
        self.calls.append((incident, similar, patterns))
        if self._error:
            raise self._error
        return Suggestion(similar_incidents=similar, learned_patterns=patterns, probable_root_cause="Pool",
                          fix_steps=["Roll back (INC-1042)"], confidence="high", memory_used=bool(similar))


def test_analyze_recalls_memory_then_asks_advisor():
    memory, advisor = FakeMemory(), FakeAdvisor()
    suggestion = IncidentService(memory, advisor).analyze_incident(INCIDENT)
    assert [c[0] for c in memory.calls] == ["recall_similar", "recall_learned_patterns"]
    assert advisor.calls == [(INCIDENT, SIMILAR, PATTERNS)]
    assert suggestion.similar_incidents == SIMILAR
    assert suggestion.learned_patterns == PATTERNS
    assert suggestion.llm_error is None


def test_analyze_continues_without_patterns_when_pattern_recall_fails():
    memory, advisor = FakeMemory(patterns_error=IncidentMemoryError("observations down")), FakeAdvisor()
    suggestion = IncidentService(memory, advisor).analyze_incident(INCIDENT)
    assert advisor.calls == [(INCIDENT, SIMILAR, [])]
    assert suggestion.learned_patterns == []


def test_analyze_raises_when_similar_recall_fails():
    memory, advisor = FakeMemory(similar_error=IncidentMemoryError("hindsight down")), FakeAdvisor()
    with pytest.raises(IncidentMemoryError):
        IncidentService(memory, advisor).analyze_incident(INCIDENT)
    assert advisor.calls == []


@pytest.mark.parametrize("similar", [SIMILAR, []], ids=["with-memory", "without-memory"])
def test_llm_failure_still_returns_recalled_memory(similar):
    memory, advisor = FakeMemory(similar=similar), FakeAdvisor(error=LLMError("groq down"))
    suggestion = IncidentService(memory, advisor).analyze_incident(INCIDENT)
    assert suggestion.similar_incidents == similar
    assert suggestion.learned_patterns == PATTERNS
    assert suggestion.llm_error == "groq down"
    assert suggestion.confidence == "low"
    assert suggestion.fix_steps == []
    assert suggestion.memory_used is bool(similar)


def test_record_outcome_retains_it():
    memory = FakeMemory()
    IncidentService(memory, FakeAdvisor()).record_outcome(INCIDENT, OUTCOME)
    assert memory.calls == [("retain_outcome", INCIDENT, OUTCOME)]


# act -> verify -> learn

from agent.actions import ShopFastError  # noqa: E402
from agent.models import RemediationAction, RemediationAttempt  # noqa: E402

ACTIONS = [
    RemediationAction(name="rollback_payment_api", description="Roll payment-api back to its previous release"),
    RemediationAction(name="restart_payment_api_pods", description="Restart all payment-api pods"),
]
HEALTHY = {"GET /products": 200, "POST /checkout": 200}
BROKEN = {"GET /products": 200, "POST /checkout": 503}


class FakeShop:
    def __init__(self, health=HEALTHY, list_error=None, run_error=None):
        self.ran = []
        self._health, self._list_error, self._run_error = health, list_error, run_error

    def list_actions(self):
        if self._list_error:
            raise self._list_error
        return ACTIONS

    def run_action(self, name):
        if self._run_error:
            raise self._run_error
        self.ran.append(name)

    def health_check(self):
        return self._health


class ActionAdvisor(FakeAdvisor):
    def suggest(self, incident, similar, patterns, actions=(), tried_actions=()):
        self.calls.append((incident, similar, patterns, list(actions), list(tried_actions)))
        return Suggestion(similar_incidents=similar, learned_patterns=patterns, probable_root_cause="Pool exhausted",
                          fix_steps=["Roll back (INC-1042)"], confidence="high", memory_used=True,
                          proposed_action="rollback_payment_api", action_reason="Rollback fixed INC-1042")


def _proposal(action="rollback_payment_api"):
    return Suggestion(probable_root_cause="Pool exhausted after deploy", confidence="high", memory_used=True,
                      proposed_action=action, action_reason="Rollback fixed INC-1042")


def _service(shop=None, memory=None):
    return IncidentService(memory or FakeMemory(), ActionAdvisor(), shop=shop or FakeShop())


def test_analyze_offers_shop_actions_and_tried_actions_to_advisor():
    advisor = ActionAdvisor()
    IncidentService(FakeMemory(), advisor, shop=FakeShop()).analyze_incident(INCIDENT, tried_actions=["x_action"])
    assert advisor.calls[0][3] == ACTIONS
    assert advisor.calls[0][4] == ["x_action"]


def test_analyze_still_advises_when_shopfast_is_unreachable():
    advisor = ActionAdvisor()
    shop = FakeShop(list_error=ShopFastError("down"))
    suggestion = IncidentService(FakeMemory(), advisor, shop=shop).analyze_incident(INCIDENT)
    assert advisor.calls[0][3] == []
    assert suggestion.probable_root_cause == "Pool exhausted"


def test_rejected_action_is_not_executed_or_recorded():
    shop, memory = FakeShop(), FakeMemory()
    attempt = _service(shop, memory).remediate(INCIDENT, _proposal(), approved=False)
    assert (attempt.approved, attempt.executed, attempt.verified) == (False, False, False)
    assert shop.ran == [] and memory.calls == []


def test_approved_action_runs_verifies_and_records_success():
    shop, memory = FakeShop(health=HEALTHY), FakeMemory()
    attempt = _service(shop, memory).remediate(INCIDENT, _proposal(), approved=True)
    assert shop.ran == ["rollback_payment_api"]
    assert (attempt.approved, attempt.executed, attempt.verified) == (True, True, True)
    assert attempt.health == HEALTHY
    assert attempt.reason == "Rollback fixed INC-1042"
    [(name, incident, outcome)] = memory.calls
    assert name == "retain_outcome" and incident == INCIDENT
    assert outcome.resolved is True
    assert outcome.actual_root_cause == "Pool exhausted after deploy"
    assert outcome.steps_that_worked == ["rollback_payment_api: Roll payment-api back to its previous release"]
    assert outcome.failed_attempts == []
    assert "automatically" in outcome.notes.lower() and "POST /checkout 200" in outcome.notes


def test_failed_verification_is_recorded_as_failed_attempt():
    shop, memory = FakeShop(health=BROKEN), FakeMemory()
    attempt = _service(shop, memory).remediate(INCIDENT, _proposal("restart_payment_api_pods"), approved=True)
    assert (attempt.executed, attempt.verified) == (True, False)
    outcome = memory.calls[0][2]
    assert outcome.resolved is False
    assert outcome.steps_that_worked == []
    assert outcome.failed_attempts == ["restart_payment_api_pods: Restart all payment-api pods "
                                       "(checkout still failing: POST /checkout 503)"]


def test_outcome_accumulates_earlier_attempts_and_skips_rejected_ones():
    earlier = [
        RemediationAttempt(action="scale_out_payment_api", description="Add pods", reason="r",
                           approved=False, executed=False, verified=False),
        RemediationAttempt(action="restart_payment_api_pods", description="Restart all payment-api pods", reason="r",
                           approved=True, executed=True, verified=False, health=BROKEN),
    ]
    memory = FakeMemory()
    _service(FakeShop(health=HEALTHY), memory).remediate(INCIDENT, _proposal(), approved=True,
                                                         previous_attempts=earlier)
    outcome = memory.calls[0][2]
    assert outcome.resolved is True
    assert outcome.failed_attempts == ["restart_payment_api_pods: Restart all payment-api pods "
                                       "(checkout still failing: POST /checkout 503)"]
    assert outcome.steps_that_worked == ["rollback_payment_api: Roll payment-api back to its previous release"]


def test_action_outside_allow_list_is_refused_before_running():
    shop = FakeShop()
    with pytest.raises(ValueError):
        _service(shop).remediate(INCIDENT, _proposal("drop_database"), approved=True)
    assert shop.ran == []


def test_suggestion_without_action_cannot_be_remediated():
    with pytest.raises(ValueError):
        _service().remediate(INCIDENT, _proposal(action=None), approved=True)


def test_shopfast_error_during_action_is_reported_not_recorded():
    memory = FakeMemory()
    attempt = _service(FakeShop(run_error=ShopFastError("connection refused")), memory).remediate(
        INCIDENT, _proposal(), approved=True)
    assert (attempt.executed, attempt.verified) == (False, False)
    assert "connection refused" in attempt.error
    assert memory.calls == []


class FailingRetainMemory(FakeMemory):
    def retain_outcome(self, incident, outcome):
        raise IncidentMemoryError("hindsight down")


def test_memory_failure_after_action_keeps_the_executed_attempt():
    shop = FakeShop(health=HEALTHY)
    attempt = _service(shop, FailingRetainMemory()).remediate(INCIDENT, _proposal(), approved=True)
    assert shop.ran == ["rollback_payment_api"]
    assert (attempt.executed, attempt.verified) == (True, True)
    assert "not recorded" in attempt.error and "hindsight down" in attempt.error
