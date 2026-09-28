"""Automatic incident intake: the agent notices a ShopFast failure and opens an incident without copy-paste."""

import pytest
from fastapi.testclient import TestClient

from agent.actions import ShopFastClient, ShopFastError
from agent.intake import incident_from_alert
from agent.models import Incident, ShopFastAlert
from agent.service import IncidentService
from shopfast import app as shop
from shopfast.faults import FAULT_LOGS, Fault


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(shop, "faults", shop.FaultRegistry())
    monkeypatch.setattr(shop, "alerts", shop.AlertLog())
    return TestClient(shop.app)


def _alert(**overrides) -> ShopFastAlert:
    data = dict(id=7, at="2026-09-28T11:27:07Z", method="POST", path="/checkout", status=503,
                error="Orders database unavailable", count=3,
                log="2026-09-28T11:27:07Z " + FAULT_LOGS[Fault.DB_POOL_EXHAUST])
    data.update(overrides)
    return ShopFastAlert(**data)


# client

def test_latest_incident_is_none_when_nothing_failed(http):
    assert ShopFastClient(http).latest_incident() is None


def test_latest_incident_returns_the_alert(http):
    http.post("/admin/faults/PAYMENT_GATEWAY_TIMEOUT")
    http.post("/checkout", json={"items": [{"product_id": "sku-100", "quantity": 1}]})
    alert = ShopFastClient(http).latest_incident()
    assert (alert.path, alert.status) == ("/checkout", 504)
    assert alert.log.endswith(FAULT_LOGS[Fault.PAYMENT_GATEWAY_TIMEOUT])


# alert -> incident

def test_incident_from_alert_fills_every_field():
    incident = incident_from_alert(_alert())
    assert incident.service == "payment-api"
    assert incident.severity.value == "SEV1"
    assert "POST /checkout" in incident.title and "503" in incident.title
    assert "Orders database unavailable" in incident.symptoms and "3 failed" in incident.symptoms
    assert incident.error_log == _alert().log


@pytest.mark.parametrize("path, severity", [("/checkout", "SEV1"), ("/login", "SEV1"),
                                            ("/products", "SEV2"), ("/cart/items", "SEV2")])
def test_severity_follows_business_impact(path, severity):
    assert incident_from_alert(_alert(path=path)).severity.value == severity


def test_unparseable_service_falls_back_to_shopfast():
    assert incident_from_alert(_alert(log="garbage without a service; DROP TABLE")).service == "shopfast"


@pytest.mark.parametrize("fault", list(Fault))
def test_every_real_fault_becomes_a_valid_incident(http, fault):
    http.post(f"/admin/faults/{fault.value}")
    ShopFastClient(http).health_check()  # the probe itself triggers the failure
    incident = incident_from_alert(ShopFastClient(http).latest_incident())
    assert isinstance(incident, Incident)
    assert FAULT_LOGS[fault] in incident.error_log


# service

class Memory:
    def recall_similar(self, incident):
        return []

    def recall_learned_patterns(self, incident):
        return []


def test_detect_returns_none_when_shop_is_healthy(http):
    http.post("/admin/faults/DB_POOL_EXHAUST")
    http.post("/checkout", json={"items": [{"product_id": "sku-100", "quantity": 1}]})
    http.delete("/admin/faults/DB_POOL_EXHAUST")  # old alert exists, but the shop is healthy now
    assert IncidentService(Memory(), None, shop=ShopFastClient(http)).detect_incident() is None


def test_detect_probes_the_shop_and_opens_an_incident_from_the_new_alert(http):
    http.post("/admin/faults/DB_POOL_EXHAUST")  # nobody has hit checkout yet
    incident = IncidentService(Memory(), None, shop=ShopFastClient(http)).detect_incident()
    assert incident.service == "payment-api"
    assert "POST /checkout" in incident.title
    assert FAULT_LOGS[Fault.DB_POOL_EXHAUST] in incident.error_log


def test_detect_without_shopfast_raises():
    with pytest.raises(ShopFastError):
        IncidentService(Memory(), None).detect_incident()
