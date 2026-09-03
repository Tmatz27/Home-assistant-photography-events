"""Per-service rate limiting and caching.

Kept apart from the coordinator so it carries no Home Assistant import and can
be tested directly. The rate limits are the part of this integration most
likely to get an IP blocked if they are wrong, and untestable code is a poor
place to put that.

The rule each ``Source`` enforces is simple and deliberately conservative: a
service is fetched only when its own minimum interval has elapsed, regardless
of how often the coordinator cycles. Raising the coordinator's cadence
therefore cannot make any single service be polled harder than it allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

# After a failure, retry on this backoff rather than waiting out the whole
# interval - a blip should not cost a full cycle of staleness. It multiplies
# with consecutive failures and is capped at the interval itself.
FAILURE_RETRY_MINUTES = 15


@dataclass
class Source:
    """One external service: its cadence, its cached payload, its last outcome."""

    name: str
    min_interval_minutes: int
    value: Any = None
    fetched_at: datetime | None = None
    next_attempt: datetime | None = None
    failures: int = 0
    last_error: str | None = None

    def due(self, now: datetime) -> bool:
        """Whether this service may be called again yet."""
        if self.next_attempt is not None and now < self.next_attempt:
            return False
        if self.fetched_at is None:
            return True
        return now - self.fetched_at >= timedelta(minutes=self.min_interval_minutes)

    def succeed(self, now: datetime, value: Any) -> None:
        self.value = value
        self.fetched_at = now
        self.next_attempt = now + timedelta(minutes=self.min_interval_minutes)
        self.failures = 0
        self.last_error = None

    def fail(self, now: datetime, error: str) -> None:
        """Record a failure but keep the payload - stale beats empty here.

        A forecast from an hour ago still tells you tonight's sunset is worth
        driving to; an empty one tells you nothing and would silently retract
        an alert that is still true.
        """
        self.failures += 1
        self.last_error = error
        backoff = min(self.min_interval_minutes, FAILURE_RETRY_MINUTES * self.failures)
        self.next_attempt = now + timedelta(minutes=backoff)

    def status(self) -> dict:
        return {
            "last_success": self.fetched_at.isoformat() if self.fetched_at else None,
            "failures": self.failures,
            "last_error": self.last_error,
        }
