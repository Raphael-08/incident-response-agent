"""ShopFast mock API. Run: uvicorn shopfast.app:app --host 127.0.0.1 --port 8001

Bind to 127.0.0.1 only: /admin/faults has no auth and must stay local.

When a fault is on, the affected endpoint fails with its real-looking log line. The line is written to the
server log and returned in the response body as "log", ready to paste into the agent UI.
"""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from shopfast.faults import FAULT_LOGS, Fault, FaultRegistry

logger = logging.getLogger("shopfast")

app = FastAPI(title="ShopFast (mock)")
faults = FaultRegistry()

PRODUCTS: dict[str, dict] = {
    "sku-100": {"id": "sku-100", "name": "Running shoes", "price": 89.99},
    "sku-200": {"id": "sku-200", "name": "Rain jacket", "price": 129.00},
    "sku-300": {"id": "sku-300", "name": "Water bottle", "price": 14.50},
}

# Endpoint failure for each fault: HTTP status and short error message.
FAULT_RESPONSES: dict[Fault, tuple[int, str]] = {
    Fault.REDIS_TIMEOUT: (503, "Cart and catalog cache unavailable"),
    Fault.AUTH_TOKEN_EXPIRED: (401, "Session token expired"),
    Fault.DB_POOL_EXHAUST: (503, "Orders database unavailable"),
    Fault.PAYMENT_GATEWAY_TIMEOUT: (504, "Payment gateway timed out"),
}


class CartItem(BaseModel):
    product_id: str = Field(min_length=1, max_length=32)
    quantity: int = Field(ge=1, le=10)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class CheckoutRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=20)


class FaultTriggered(Exception):
    def __init__(self, fault: Fault) -> None:
        self.fault = fault


@app.exception_handler(FaultTriggered)
def fault_response(_request, exc: FaultTriggered) -> JSONResponse:
    status, error = FAULT_RESPONSES[exc.fault]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} {FAULT_LOGS[exc.fault]}"
    logger.error(line)
    return JSONResponse(status_code=status, content={"error": error, "log": line})


def fail_if_active(*checks: Fault) -> None:
    """Raise for the first active fault, in the order the endpoint would hit those dependencies."""
    for fault in checks:
        if faults.is_active(fault):
            raise FaultTriggered(fault)


def product(product_id: str) -> dict:
    if product_id not in PRODUCTS:
        raise HTTPException(status_code=404, detail=f"Unknown product {product_id}")
    return PRODUCTS[product_id]


@app.get("/products")
def list_products() -> list[dict]:
    fail_if_active(Fault.REDIS_TIMEOUT)
    return list(PRODUCTS.values())


@app.post("/cart/items")
def add_to_cart(item: CartItem) -> dict:
    product(item.product_id)
    fail_if_active(Fault.REDIS_TIMEOUT)
    return {"product_id": item.product_id, "quantity": item.quantity}


@app.post("/login")
def login(credentials: LoginRequest) -> dict:
    fail_if_active(Fault.AUTH_TOKEN_EXPIRED)
    return {"token": secrets.token_urlsafe(16), "username": credentials.username}


@app.post("/checkout")
def checkout(order: CheckoutRequest) -> dict:
    total = sum(product(item.product_id)["price"] * item.quantity for item in order.items)
    fail_if_active(Fault.DB_POOL_EXHAUST, Fault.PAYMENT_GATEWAY_TIMEOUT)  # DB is reached before the gateway
    return {"order_id": f"ORD-{secrets.randbelow(10**8):08d}", "total": round(total, 2)}


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
