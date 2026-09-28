import pytest
from pydantic import ValidationError

from agent.models import Incident, MAX_LOG_CHARS
from scripts.seed_memory import load_seed_incidents
from shopfast.faults import Fault, FaultRegistry


def _incident(**overrides) -> dict:
    data = {
        "incident_id": "INC-2001",
        "service": "payment-api",
        "severity": "SEV1",
        "title": "Checkout failing",
        "symptoms": "503 on checkout",
        "error_log": "psycopg2.OperationalError",
    }
    data.update(overrides)
    return data


def test_valid_incident_parses():
    assert Incident.model_validate(_incident()).service == "payment-api"


@pytest.mark.parametrize(
    "overrides",
    [
        {"incident_id": "1234"},
        {"service": "Payment API; DROP"},
        {"severity": "SEV9"},
        {"error_log": "x" * (MAX_LOG_CHARS + 1)},
    ],
)
def test_invalid_incident_rejected(overrides):
    with pytest.raises(ValidationError):
        Incident.model_validate(_incident(**overrides))


def test_seed_file_is_valid_and_has_no_payment_gateway_history():
    incidents = load_seed_incidents()
    assert len(incidents) == 25
    assert len({i.incident_id for i in incidents}) == 25
    assert not any("paygate" in i.error_log.lower() for i in incidents)


def test_fault_registry_toggle():
    registry = FaultRegistry()
    registry.enable(Fault.REDIS_TIMEOUT)
    assert registry.is_active(Fault.REDIS_TIMEOUT)
    registry.disable(Fault.REDIS_TIMEOUT)
    assert registry.active() == []
