"""Alerts ShopFast raises when a fault makes a request fail. The agent fetches the latest one to open an incident."""

from collections import deque
from datetime import datetime, timezone

from shopfast.faults import Fault


class AlertLog:
    """Recent failures, newest last, bounded. Each alert counts how often its fault has failed a request."""

    def __init__(self, max_alerts: int = 100) -> None:
        self._alerts: deque[dict] = deque(maxlen=max_alerts)
        self._counts: dict[Fault, int] = {}
        self._next_id = 1

    def record(self, fault: Fault, method: str, path: str, status: int, error: str, log: str) -> None:
        self._counts[fault] = self._counts.get(fault, 0) + 1
        self._alerts.append({
            "id": self._next_id,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "method": method,
            "path": path,
            "status": status,
            "error": error,
            "log": log,
            "count": self._counts[fault],
        })
        self._next_id += 1

    def latest(self) -> dict | None:
        return self._alerts[-1] if self._alerts else None

    def __len__(self) -> int:
        return len(self._alerts)
