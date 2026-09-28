"""ShopFast mock API. Run: uvicorn shopfast.app:app --host 127.0.0.1 --port 8001

Bind to 127.0.0.1 only: /admin/faults has no auth and must stay local.
"""

from fastapi import FastAPI

from shopfast.faults import Fault, FaultRegistry

app = FastAPI(title="ShopFast (mock)")
faults = FaultRegistry()


@app.get("/products")
def list_products() -> list[dict]:
    raise NotImplementedError  # TODO(ShopFast owner): return static products; fail on REDIS_TIMEOUT


@app.post("/cart/items")
def add_to_cart() -> dict:
    raise NotImplementedError  # TODO(ShopFast owner): fail on REDIS_TIMEOUT


@app.post("/login")
def login() -> dict:
    raise NotImplementedError  # TODO(ShopFast owner): fail on AUTH_TOKEN_EXPIRED


@app.post("/checkout")
def checkout() -> dict:
    raise NotImplementedError  # TODO(ShopFast owner): fail on DB_POOL_EXHAUST / PAYMENT_GATEWAY_TIMEOUT


@app.get("/admin/faults")
def get_faults() -> dict:
    return {"active": faults.active()}


@app.post("/admin/faults/{fault}")
def enable_fault(fault: Fault) -> dict:
    faults.enable(fault)
    return {"active": faults.active()}


@app.delete("/admin/faults/{fault}")
def disable_fault(fault: Fault) -> dict:
    faults.disable(fault)
    return {"active": faults.active()}
