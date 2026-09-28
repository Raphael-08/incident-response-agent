"""Strips volatile values from error logs so Hindsight recall matches on the error, not on noise."""

import re

# Order matters: more specific patterns run before generic ones.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TIME>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<UUID>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<IP>"),
    # Kubernetes pod names: deployment-<replicaset hash>-<pod hash> or deployment-<hash>
    (re.compile(r"\b([a-z][a-z0-9-]*?)-[a-z0-9]{8,10}-[a-z0-9]{5}\b"), r"\1-<POD>"),
    # Kubernetes hashes use only these characters (no vowels, no 0/1/3), so "us-east1" is not a pod.
    (re.compile(r"\b([a-z][a-z0-9-]*?)-(?=[a-z0-9]*\d)[bcdfghjklmnpqrstvwxz2456789]{5}\b"), r"\1-<POD>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<HEX>"),
    (re.compile(r"\b\d{6,}\b"), "<NUM>"),
]
_WHITESPACE = re.compile(r"\s+")


def normalize_log(log: str) -> str:
    """Return the log with timestamps, IDs, IPs, pod hashes and long numbers replaced by placeholders."""
    for pattern, replacement in _PATTERNS:
        log = pattern.sub(replacement, log)
    return _WHITESPACE.sub(" ", log).strip()
