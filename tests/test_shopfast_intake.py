"""ShopFast records each fault-caused failure as an alert the agent can fetch."""

import pytest
from fastapi.testclient import TestClient

from shopfast import app as shop
from shopfast.faults import FAULT_LOGS, Fault

ITEMS = {"items": [{"product_id": "sku-100", "quantity": 1}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(shop, "faults", shop.FaultRegistry())
    monkeypatch.setattr(shop, "alerts", shop.AlertLog())
    return TestClient(shop.app)


def test_no_alert_before_any_failure(client):
    client.get("/products")
    assert client.get("/ops/incidents/latest").status_code == 404


def test_failure_becomes_latest_alert(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    client.post("/checkout", json=ITEMS)
    alert = client.get("/ops/incidents/latest").json()
    assert (alert["method"], alert["path"], alert["status"]) == ("POST", "/checkout", 503)
    assert alert["error"] == "Orders database unavailable"
    assert alert["log"].endswith(FAULT_LOGS[Fault.DB_POOL_EXHAUST])
    assert alert["count"] == 1
    assert alert["id"] >= 1 and alert["at"]


def test_repeated_failures_count_up_and_ids_increase(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    client.post("/checkout", json=ITEMS)
    first = client.get("/ops/incidents/latest").json()
    client.post("/checkout", json=ITEMS)
    second = client.get("/ops/incidents/latest").json()
    assert second["count"] == 2
    assert second["id"] > first["id"]


def test_latest_alert_follows_the_newest_failure(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    client.post("/checkout", json=ITEMS)
    client.delete("/admin/faults/DB_POOL_EXHAUST")
    client.post("/admin/faults/REDIS_TIMEOUT")
    client.get("/products")
    alert = client.get("/ops/incidents/latest").json()
    assert (alert["path"], alert["status"], alert["count"]) == ("/products", 503, 1)
    assert alert["log"].endswith(FAULT_LOGS[Fault.REDIS_TIMEOUT])


def test_validation_errors_are_not_alerts(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    client.post("/checkout", json={"items": []})
    assert client.get("/ops/incidents/latest").status_code == 404


def test_alert_log_is_bounded():
    log = shop.AlertLog(max_alerts=3)
    for _ in range(5):
        log.record(Fault.REDIS_TIMEOUT, "GET", "/products", 503, "x", "line")
    assert len(log) == 3
    assert log.latest()["count"] == 5
