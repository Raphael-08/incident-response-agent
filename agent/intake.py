"""Automatic incident intake: turn a ShopFast failure alert into an Incident, so nobody copies logs by hand."""

import re

from agent.models import MAX_LOG_CHARS, Incident, Severity, ShopFastAlert

# "2026-09-28T11:27:07Z ERROR payment-api sqlalchemy..." -> "payment-api"
_SERVICE_IN_LOG = re.compile(r"^\S+\s+(?:ERROR|WARN|WARNING|INFO|CRITICAL)\s+([a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)\s")
FALLBACK_SERVICE = "shopfast"
# Failures that stop customers from paying or signing in are SEV1; the rest degrade the shop.
SEV1_PATHS = {"/checkout", "/login"}


def incident_from_alert(alert: ShopFastAlert) -> Incident:
    match = _SERVICE_IN_LOG.match(alert.log)
    endpoint = f"{alert.method} {alert.path}"
    return Incident(
        service=match.group(1) if match else FALLBACK_SERVICE,
        severity=Severity.SEV1 if alert.path in SEV1_PATHS else Severity.SEV2,
        title=f"{endpoint} returning {alert.status}: {alert.error}"[:200],
        symptoms=(f"{alert.error}. ShopFast recorded {alert.count} failed request(s) to {endpoint}, "
                  f"latest at {alert.at}.")[:2000],
        error_log=alert.log[:MAX_LOG_CHARS],
    )
