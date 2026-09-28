"""ShopFast runbook actions: the only remediation the agent can perform."""

import logging

import pytest
from fastapi.testclient import TestClient

from shopfast import app as shop
from shopfast.faults import Fault
from shopfast.remediations import ACTIONS

ITEMS = {"items": [{"product_id": "sku-100", "quantity": 1}]}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(shop, "faults", shop.FaultRegistry())
    return TestClient(shop.app)


def test_actions_listed_with_name_and_description_only(client):
    actions = client.get("/ops/actions").json()
    assert {a["name"] for a in actions} == set(ACTIONS)
    for action in actions:
        assert set(action) == {"name", "description"}  # which fault an action fixes stays hidden
        assert action["description"]


def test_every_fault_has_exactly_one_fixing_action_and_decoys_exist():
    for fault in Fault:
        assert sum(fault in a.fixes for a in ACTIONS.values()) == 1, fault
    assert any(not a.fixes for a in ACTIONS.values())


@pytest.mark.parametrize("name", list(ACTIONS))
def test_action_clears_only_the_faults_it_fixes(client, name):
    for fault in Fault:
        client.post(f"/admin/faults/{fault.value}")
    response = client.post(f"/ops/actions/{name}")
    assert response.status_code == 200
    remaining = set(client.get("/admin/faults").json()["active"])
    assert remaining == {f.value for f in Fault} - {f.value for f in ACTIONS[name].fixes}
    assert response.json() == {"action": name, "executed": True}  # no hint whether it helped


def test_fixing_action_restores_checkout(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    assert client.post("/checkout", json=ITEMS).status_code == 503
    fixer = next(n for n, a in ACTIONS.items() if Fault.DB_POOL_EXHAUST in a.fixes)
    client.post(f"/ops/actions/{fixer}")
    assert client.post("/checkout", json=ITEMS).status_code == 200


def test_decoy_action_leaves_checkout_failing(client):
    client.post("/admin/faults/DB_POOL_EXHAUST")
    decoy = next(n for n, a in ACTIONS.items() if not a.fixes)
    client.post(f"/ops/actions/{decoy}")
    assert client.post("/checkout", json=ITEMS).status_code == 503


def test_unknown_action_rejected(client):
    assert client.post("/ops/actions/drop_database").status_code == 404


def test_action_is_logged(client, caplog):
    name = next(iter(ACTIONS))
    with caplog.at_level(logging.INFO, logger="shopfast"):
        client.post(f"/ops/actions/{name}")
    assert f"ops action {name} executed" in caplog.text
