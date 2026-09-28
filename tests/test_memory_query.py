from agent.memory import build_recall_query
from agent.models import Incident


def _incident(error_log: str) -> Incident:
    return Incident(service="payment-api", severity="SEV1", title="Checkout failing",
                    symptoms="503 on checkout", error_log=error_log)


def test_query_contains_service_title_symptoms_and_normalized_log():
    query = build_recall_query(_incident("2026-06-03T14:08:11Z too many clients from 10.0.1.5"))
    assert query == "payment-api: Checkout failing. 503 on checkout. <TIME> too many clients from <IP>"


def test_same_error_from_different_runs_gives_same_query():
    a = _incident("2026-06-03T14:08:11Z payment-api-6f7d8c9b5-x2k9p too many clients")
    b = _incident("2026-07-09T02:04:19Z payment-api-7b8c9d4f5-q7w8z too many clients")
    assert build_recall_query(a) == build_recall_query(b)
