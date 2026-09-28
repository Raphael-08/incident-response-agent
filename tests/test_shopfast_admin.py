import pytest
from fastapi.testclient import TestClient

from shopfast import app as shop


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(shop, "faults", shop.FaultRegistry())
    return TestClient(shop.app)


def test_no_faults_active_at_start(client):
    assert client.get("/admin/faults").json() == {"active": []}


def test_enable_and_disable_fault(client):
    assert client.post("/admin/faults/DB_POOL_EXHAUST").json() == {"active": ["DB_POOL_EXHAUST"]}
    assert client.get("/admin/faults").json() == {"active": ["DB_POOL_EXHAUST"]}
    assert client.delete("/admin/faults/DB_POOL_EXHAUST").json() == {"active": []}


def test_disable_inactive_fault_is_harmless(client):
    assert client.delete("/admin/faults/REDIS_TIMEOUT").status_code == 200


def test_unknown_fault_rejected(client):
    assert client.post("/admin/faults/DROP_TABLES").status_code == 422
