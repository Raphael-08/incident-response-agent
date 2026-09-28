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
