"""Signals: raw evidence that something was seen, measured, forecast or reported.

A signal is not an event. "A humpback was photographed off Avila yesterday" is
true, useful and not a reason to get in the car - it is evidence *for* the
humpback lunge-feeding phenomenon, and a very weak one, because presence says
nothing about the bait ball. Before 0.16.0 every sighting became its own row
and competed with the phenomenon it should have supported, scored on how fresh
it was rather than on how much it mattered.

So signals are kept - they corroborate phenomena, feed the bird views and fill
the collapsed "background signals" list - but they never become primary rows
on their own. Every signal keeps what it is (observed, reported, forecast,
computed), when that was true, and where it came from, so a missing or failed
feed can be told apart from a quiet one.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

BASIS_OBSERVED = "observed"
BASIS_REPORTED = "reported"
BASIS_FORECAST = "forecast"
BASIS_COMPUTED = "computed"
BASIS_UNDATED = "reported_undated"


@dataclass
class Signal:
    """One piece of supporting evidence."""

    kind: str
    source: str
    subject: str
    category: str
    basis: str
    observed_at: datetime | None = None
    valid_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    place: str = ""
    url: str | None = None
    taxon: str = ""
    count: int | None = None
    reports: int = 1
    days: int = 1
    confirmed: bool = False
    private_location: bool = False
    behaviors: tuple[str, ...] = ()
    text: str = ""
    # The phenomenon this signal was merged into, once resolution has run.
    phenomena: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        stamp = (self.observed_at or self.valid_at)
        raw = f"{self.kind}|{self.source}|{self.taxon or self.subject}|{self.place}|{stamp.isoformat() if stamp else ''}"
        return hashlib.sha1(raw.encode()).hexdigest()[:12]

    def age_hours(self, now: datetime) -> float | None:
        if self.observed_at is None:
            return None
        return max(0.0, (now - self.observed_at).total_seconds() / 3600)

    def compact(self, now: datetime) -> dict:
        """What the collapsed background list needs, and no more."""
        row = {"id": self.id, "kind": self.kind, "subject": self.subject, "category": self.category,
               "basis": self.basis, "source": self.source, "place": self.place}
        for key, value in (("observed_at", self.observed_at), ("valid_at", self.valid_at)):
            if value is not None:
                row[key] = value.isoformat()
        age = self.age_hours(now)
        if age is not None:
            row["age_hours"] = round(age, 1)
        if self.url:
            row["url"] = self.url
        if self.count:
            row["count"] = self.count
        if self.reports > 1:
            row["reports"] = self.reports
        if self.behaviors:
            row["behaviors"] = list(self.behaviors)
        if self.phenomena:
            row["supports"] = list(self.phenomena)
        if self.text:
            row["text"] = self.text[:200]
        return row


def from_sighting(sighting) -> Signal:
    """A clustered eBird/iNaturalist sighting as presence evidence."""
    return Signal(
        kind="sighting", source=sighting.source, subject=sighting.species,
        category=sighting.category, basis=BASIS_OBSERVED,
        observed_at=sighting.latest, latitude=sighting.latitude, longitude=sighting.longitude,
        place=sighting.place, url=sighting.url, taxon=sighting.scientific_name,
        count=sighting.count, reports=max(sighting.reports, len(sighting.observers) or 1),
        days=max(1, len(getattr(sighting, "dates", []) or [])),
        confirmed=sighting.confirmed, private_location=getattr(sighting, "private_location", False),
    )


def from_report(report, latitude=None, longitude=None) -> Signal:
    """A hotline, operator or emailed report. Undated text stays undated."""
    return Signal(
        kind="report", source=report.source_name, subject=report.headline,
        category=report.category,
        basis=BASIS_REPORTED if report.observed_at else BASIS_UNDATED,
        observed_at=report.observed_at, latitude=latitude, longitude=longitude,
        place=report.zone_id, url=report.url or None,
        count=getattr(report, "count", None),
        behaviors=tuple(getattr(report, "behaviors", ()) or ()),
        text=report.snippet,
        phenomena=[report.phenomenon_key] if getattr(report, "phenomenon_key", "") else [],
    )


def background(signals: list[Signal], now: datetime, limit: int = 40) -> list[dict]:
    """Most recent first; undated evidence last, never presented as current."""
    def key(item: Signal):
        stamp = item.observed_at or item.valid_at
        return (stamp is None, -(stamp.timestamp() if stamp else 0))
    return [item.compact(now) for item in sorted(signals, key=key)[:limit]]
