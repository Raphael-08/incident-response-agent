"""Action evidence: worked/failed counts read only from outcomes recorded in memory."""

from datetime import datetime, timezone

from agent.evidence import action_evidence
from agent.memory import format_outcome
from agent.models import Incident, Outcome, SimilarIncident

ACTIONS = ["rollback_payment_api", "restart_payment_api_pods", "raise_payment_gateway_timeout"]


def _recorded(incident_id: str, worked: list[str], failed: list[str]) -> SimilarIncident:
    """A recalled incident whose source text is exactly what retain_outcome stores."""
    incident = Incident(incident_id=incident_id, service="payment-api", severity="SEV1", title="Checkout failing",
                        symptoms="503 on checkout", reported_at=datetime(2026, 9, 28, tzinfo=timezone.utc))
    outcome = Outcome(
        incident_id=incident_id, resolved=bool(worked), actual_root_cause="Pool exhausted",
        steps_that_worked=[f"{a}: description of {a}" for a in worked],
        failed_attempts=[f"{a}: description of {a} (checkout still failing: POST /checkout 503)" for a in failed],
    )
    return SimilarIncident(incident_id=incident_id, summary="facts", source_text=format_outcome(incident, outcome))


def test_counts_worked_and_failed_per_action_with_incident_ids():
    similar = [
        _recorded("INC-26092810000001", ["rollback_payment_api"], ["restart_payment_api_pods"]),
        _recorded("INC-26092811000002", ["rollback_payment_api"], []),
        _recorded("INC-26092812000003", [], ["restart_payment_api_pods"]),
    ]
    evidence = {e.action: e for e in action_evidence(similar, ACTIONS)}
    assert evidence["rollback_payment_api"].worked_in == ["INC-26092810000001", "INC-26092811000002"]
    assert evidence["rollback_payment_api"].failed_in == []
    assert evidence["restart_payment_api_pods"].failed_in == ["INC-26092810000001", "INC-26092812000003"]
    assert "raise_payment_gateway_timeout" not in evidence  # never recorded, never shown


def test_proven_actions_come_first():
    similar = [_recorded("INC-26092810000001", ["rollback_payment_api"], ["restart_payment_api_pods"])]
    assert [e.action for e in action_evidence(similar, ACTIONS)] == ["rollback_payment_api", "restart_payment_api_pods"]


def test_seed_incidents_without_action_names_give_no_evidence():
    seed = SimilarIncident(incident_id="INC-1042", summary="Pool exhausted",
                           source_text="Fix steps that worked:\n- Roll back payment-api to v2.3.0\n"
                                       "Fix attempts that did not work:\n- Restarted payment-api pods")
    assert action_evidence([seed], ACTIONS) == []


def test_action_name_in_other_text_is_not_counted():
    tricky = SimilarIncident(incident_id="INC-26092810000001", summary="rollback_payment_api worked",
                             source_text="Notes: someone suggested rollback_payment_api once")
    assert action_evidence([tricky], ACTIONS) == []


def test_same_incident_counted_once_per_action():
    item = _recorded("INC-26092810000001", ["rollback_payment_api"], [])
    item.source_text += "\n" + item.source_text  # a chunk that repeats the text
    [evidence] = action_evidence([item], ACTIONS)
    assert evidence.worked_in == ["INC-26092810000001"]


def test_latest_learned_from_is_the_newest_generated_incident():
    similar = [_recorded("INC-26092812000003", ["rollback_payment_api"], []),
               _recorded("INC-26092810000001", ["rollback_payment_api"], [])]
    [evidence] = action_evidence(similar, ACTIONS)
    assert evidence.latest == "INC-26092812000003"
