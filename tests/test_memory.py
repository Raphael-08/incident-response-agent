"""IncidentMemory tests against a fake Hindsight client.

The fake returns real hindsight_client_api response models, so these tests prove what our code sends
to Hindsight and how it reads the reply. If recall looks wrong in the app while these pass, inspect
the bank's stored memories in Hindsight Cloud.
"""

from datetime import datetime, timezone

import pytest
from hindsight_client_api.models.chunk_data import ChunkData
from hindsight_client_api.models.recall_response import RecallResponse
from hindsight_client_api.models.recall_result import RecallResult

from agent.config import Settings
from agent.memory import BANK_MISSION, IncidentMemory, IncidentMemoryError, build_recall_query
from agent.models import HistoricalIncident, Incident, Outcome

BANK = "shopfast-incidents-test"


class FakeHindsight:
    def __init__(self, response: RecallResponse | None = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._response = response or RecallResponse(results=[])
        self._error = error

    def _record(self, name: str, **kwargs):
        self.calls.append((name, kwargs))
        if self._error:
            raise self._error

    def create_bank(self, bank_id, **kwargs):
        self._record("create_bank", bank_id=bank_id, **kwargs)

    def retain(self, bank_id, content, **kwargs):
        self._record("retain", bank_id=bank_id, content=content, **kwargs)

    def recall(self, bank_id, query, **kwargs):
        self._record("recall", bank_id=bank_id, query=query, **kwargs)
        return self._response


def _settings() -> Settings:
    return Settings("https://example.test", "key", BANK, "key", "model")


def _memory(client: FakeHindsight) -> IncidentMemory:
    return IncidentMemory(_settings(), client=client)


def _fact(text: str, document_id: str | None = None, chunk_id: str | None = None, type_: str = "world"):
    return RecallResult(id=f"f-{abs(hash(text))}", text=text, type=type_, document_id=document_id, chunk_id=chunk_id)


def _incident(**overrides) -> Incident:
    data = dict(incident_id="INC-2001", service="payment-api", severity="SEV1", title="Checkout failing",
                symptoms="503 on checkout", error_log="2026-06-03T14:08:11Z too many clients from 10.0.1.5")
    data.update(overrides)
    return Incident(**data)


def _historical() -> HistoricalIncident:
    return HistoricalIncident(
        incident_id="INC-1042", service="payment-api", severity="SEV1", title="Checkout payments failing",
        symptoms="Error rate jumped after deploy",
        error_log="2026-06-03T14:08:11Z FATAL: remaining connection slots are reserved",
        reported_at=datetime(2026, 6, 3, 14, 9, tzinfo=timezone.utc),
        root_cause="Workers x pool size exceeded max_connections",
        resolution_steps=["Roll back payment-api to v2.3.0", "Set pool_size=5"],
        failed_attempts=["Restarted payment-api pods"],
        lesson="Check pods x workers x pool_size against max_connections.",
    )


def _outcome(**overrides) -> Outcome:
    data = dict(incident_id="INC-2001", resolved=True, actual_root_cause="Payment gateway slow",
                steps_that_worked=["Raise gateway timeout to 30s"], failed_attempts=["Restarted pods"],
                notes="Gateway status page showed degraded")
    data.update(overrides)
    return Outcome(**data)


# ensure_bank

def test_ensure_bank_creates_bank_with_observations_enabled():
    client = FakeHindsight()
    _memory(client).ensure_bank()
    [(name, kwargs)] = client.calls
    assert name == "create_bank"
    assert kwargs["bank_id"] == BANK
    assert kwargs["enable_observations"] is True
    assert kwargs["reflect_mission"] == BANK_MISSION
    assert "mission" not in kwargs  # deprecated in hindsight-client


# retain_historical

def test_retain_historical_sends_id_timestamp_metadata_and_full_text():
    client = FakeHindsight()
    incident = _historical()
    _memory(client).retain_historical(incident)
    [(name, kwargs)] = client.calls
    assert name == "retain"
    assert kwargs["bank_id"] == BANK
    assert kwargs["document_id"] == "INC-1042"
    assert kwargs["timestamp"] == incident.reported_at
    assert kwargs["metadata"] == {"service": "payment-api", "severity": "SEV1", "resolved": "true"}
    content = kwargs["content"]
    for part in ["INC-1042", "payment-api", incident.title, incident.symptoms, incident.root_cause,
                 "Roll back payment-api to v2.3.0", "Set pool_size=5", "Restarted payment-api pods", incident.lesson,
                 "remaining connection slots are reserved"]:
        assert part in content
    assert "2026-06-03T14:08:11Z" not in content  # log is normalized, same as the recall query


def test_retain_historical_marks_failed_attempts_as_failed():
    client = FakeHindsight()
    _memory(client).retain_historical(_historical())
    content = client.calls[0][1]["content"]
    line = next(line for line in content.splitlines() if "Restarted payment-api pods" in line)
    assert "did not work" in content.lower()
    assert "Roll back" not in line


# retain_outcome

def test_retain_outcome_sends_incident_and_outcome():
    client = FakeHindsight()
    incident = _incident()
    _memory(client).retain_outcome(incident, _outcome())
    [(name, kwargs)] = client.calls
    assert name == "retain"
    assert kwargs["document_id"] == "INC-2001"
    assert kwargs["timestamp"] == incident.reported_at
    assert kwargs["metadata"] == {"service": "payment-api", "severity": "SEV1", "resolved": "true"}
    for part in ["INC-2001", incident.title, incident.symptoms, "Payment gateway slow",
                 "Raise gateway timeout to 30s", "Restarted pods", "Gateway status page showed degraded"]:
        assert part in kwargs["content"]


def test_retain_outcome_unresolved_is_marked():
    client = FakeHindsight()
    _memory(client).retain_outcome(_incident(), _outcome(resolved=False))
    kwargs = client.calls[0][1]
    assert kwargs["metadata"]["resolved"] == "false"
    assert "not resolved" in kwargs["content"].lower()


def test_retain_outcome_with_mismatched_id_is_rejected_before_calling_hindsight():
    client = FakeHindsight()
    with pytest.raises(ValueError):
        _memory(client).retain_outcome(_incident(), _outcome(incident_id="INC-9999"))
    assert client.calls == []


# recall_similar

def test_recall_similar_sends_normalized_query_with_chunks():
    client = FakeHindsight()
    incident = _incident()
    _memory(client).recall_similar(incident)
    [(name, kwargs)] = client.calls
    assert name == "recall"
    assert kwargs["bank_id"] == BANK
    assert kwargs["query"] == build_recall_query(incident)
    assert kwargs["types"] == ["world"]
    assert kwargs["include_chunks"] is True


def test_recall_similar_groups_facts_by_incident_in_rank_order_with_source_text():
    response = RecallResponse(
        results=[
            _fact("Pool exhausted after worker change", "INC-1042", "c1"),
            _fact("Redis timeout on cart", "INC-1051", "c2"),
            _fact("Restarting pods did not fix pool exhaustion", "INC-1042", "c1"),
        ],
        chunks={
            "c1": ChunkData(id="c1", text="Incident INC-1042 full text", chunk_index=0),
            "c2": ChunkData(id="c2", text="Incident INC-1051 full text", chunk_index=0),
        },
    )
    similar = _memory(FakeHindsight(response)).recall_similar(_incident())
    assert [s.incident_id for s in similar] == ["INC-1042", "INC-1051"]
    assert "Pool exhausted after worker change" in similar[0].summary
    assert "Restarting pods did not fix pool exhaustion" in similar[0].summary
    assert similar[0].source_text == "Incident INC-1042 full text"


def test_recall_similar_respects_limit():
    response = RecallResponse(results=[_fact(f"fact {n}", f"INC-10{n:02d}") for n in range(10)])
    assert len(_memory(FakeHindsight(response)).recall_similar(_incident(), limit=3)) == 3


def test_recall_similar_takes_id_from_text_when_document_id_missing_and_skips_facts_without_id():
    response = RecallResponse(results=[_fact("INC-1088 had a Redis timeout"), _fact("Some general fact")])
    similar = _memory(FakeHindsight(response)).recall_similar(_incident())
    assert [s.incident_id for s in similar] == ["INC-1088"]


def test_recall_similar_excludes_the_incident_itself():
    response = RecallResponse(results=[_fact("same incident", "INC-2001"), _fact("older", "INC-1042")])
    similar = _memory(FakeHindsight(response)).recall_similar(_incident())
    assert [s.incident_id for s in similar] == ["INC-1042"]


def test_recall_similar_handles_missing_chunk_and_empty_results():
    response = RecallResponse(results=[_fact("fact", "INC-1042", "missing-chunk")])
    assert _memory(FakeHindsight(response)).recall_similar(_incident())[0].source_text == ""
    assert _memory(FakeHindsight()).recall_similar(_incident()) == []


# recall_learned_patterns

def test_recall_learned_patterns_uses_observations_and_dedupes():
    response = RecallResponse(results=[
        _fact("Restarting pods never fixes pool exhaustion", type_="observation"),
        _fact("Restarting pods never fixes pool exhaustion", type_="observation"),
        _fact("Redis timeouts follow memory pressure", type_="observation"),
    ])
    client = FakeHindsight(response)
    patterns = _memory(client).recall_learned_patterns(_incident())
    assert client.calls[0][1]["types"] == ["observation"]
    assert client.calls[0][1]["query"] == build_recall_query(_incident())
    assert [p.text for p in patterns] == [
        "Restarting pods never fixes pool exhaustion",
        "Redis timeouts follow memory pressure",
    ]


# errors

@pytest.mark.parametrize("call", [
    lambda m: m.ensure_bank(),
    lambda m: m.retain_historical(_historical()),
    lambda m: m.retain_outcome(_incident(), _outcome()),
    lambda m: m.recall_similar(_incident()),
    lambda m: m.recall_learned_patterns(_incident()),
], ids=["ensure_bank", "retain_historical", "retain_outcome", "recall_similar", "recall_learned_patterns"])
def test_hindsight_errors_are_wrapped_with_operation_and_bank(call):
    memory = _memory(FakeHindsight(error=ConnectionError("network down")))
    with pytest.raises(IncidentMemoryError, match=BANK) as info:
        call(memory)
    assert isinstance(info.value.__cause__, ConnectionError)


# closing

class ClosableFake(FakeHindsight):
    closed = 0

    def close(self):
        self.closed += 1


def test_close_closes_the_hindsight_client():
    client = ClosableFake()
    _memory(client).close()
    assert client.closed == 1


def test_context_manager_closes_client_even_on_error():
    client = ClosableFake()
    with pytest.raises(RuntimeError):
        with _memory(client):
            raise RuntimeError("boom")
    assert client.closed == 1
