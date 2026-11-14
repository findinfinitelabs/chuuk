"""
A circuit breaker for wol.jw.org, shared by every fetcher in the app.

When the site declines automated requests (it answers HTTP 202 with an empty
body for a while after heavy use) every fetch would otherwise cost its full
polite spacing and time out one by one, and a page that cites thirty verses
would hold a server worker for minutes. After a few consecutive failures the
breaker opens: fetchers return "unavailable" at once for a cooling-off
period, then one request is allowed through to test the water. A success
closes the breaker again.
"""

from __future__ import annotations

import threading
import time

# One honest identity for every request to wol.jw.org. The site answers a
# browser-impersonating User-Agent with an empty HTTP 202; a plain client is served.
USER_AGENT = "ChuukDictionary/1.0 (polite fetcher; a few requests, spaced out, cached)"

FAILURES_TO_OPEN = 3
COOL_OFF_SECONDS = 600

_lock = threading.Lock()
_failures = 0
_opened_at: float | None = None
_probe_in_flight = False


def available() -> bool:
    """True when a fetch may be attempted. While the breaker is open only one
    probe per cooling-off period gets through."""
    global _probe_in_flight
    with _lock:
        if _opened_at is None:
            return True
        if time.monotonic() - _opened_at < COOL_OFF_SECONDS:
            return False
        if _probe_in_flight:
            return False
        _probe_in_flight = True
        return True


def record_success() -> None:
    global _failures, _opened_at, _probe_in_flight
    with _lock:
        _failures, _opened_at, _probe_in_flight = 0, None, False


def record_failure() -> None:
    """A non-200 or empty answer. Opens the breaker after a few in a row."""
    global _failures, _opened_at, _probe_in_flight
    with _lock:
        _failures += 1
        _probe_in_flight = False
        if _failures >= FAILURES_TO_OPEN:
            _opened_at = time.monotonic()


def is_open() -> bool:
    with _lock:
        return _opened_at is not None and time.monotonic() - _opened_at < COOL_OFF_SECONDS


def reset() -> None:
    """For tests."""
    global _failures, _opened_at, _probe_in_flight
    with _lock:
        _failures, _opened_at, _probe_in_flight = 0, None, False


__all__ = ["available", "record_success", "record_failure", "is_open", "reset", "FAILURES_TO_OPEN", "COOL_OFF_SECONDS"]
