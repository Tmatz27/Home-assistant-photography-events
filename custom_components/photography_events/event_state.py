"""Persistent choices and meaningful event notifications, independent of HA.

Identity belongs to the occurrence, never its score or favourite viewpoint.
Otherwise a forecast refresh resurrects a skipped event or notifies twice.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def event_id(item) -> str:
    return item.roll or item.key


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class EventState:
    def __init__(self, saved=None):
        saved = saved if isinstance(saved, dict) else {}
        self.choices = dict(saved.get("choices") or {})
        self.announced = dict(saved.get("announced") or {})
        self.episodes = dict(saved.get("episodes") or {})

    def dump(self):
        return {"choices": self.choices, "announced": self.announced, "episodes": self.episodes}

    def choice(self, key):
        return self.choices.get(key, {}).get("choice", "default")

    def set_choice(self, key, choice, expires):
        if choice not in {"default", "follow", "skip"}:
            raise ValueError("Unknown event choice")
        if choice == "default":
            self.choices.pop(key, None)
        else:
            self.choices[key] = {"choice": choice, "expires": expires.isoformat()}

    def prune(self, now):
        for collection in (self.choices, self.announced):
            for key, value in list(collection.items()):
                expiry = timestamp(value.get("expires"))
                if expiry and expiry < now:
                    del collection[key]

    def changes(self, items, now, qualifies):
        """At most one notification per occurrence per meaningful transition.

        Score fluctuations and repeated downloads are not news. Keep the last
        *announced* time, so small shifts can accumulate into a real change.
        A vanished item isn't called cancelled: the source may simply be down.
        """
        self.prune(now)
        best = {}
        for item in items:
            key = event_id(item)
            if key not in best or item.score > best[key].score:
                best[key] = item
        notifications = []
        for key, item in best.items():
            if self.choice(key) == "skip" or not qualifies(item):
                continue
            if item.end and item.end <= now:
                continue
            stage = item.extra.get("verification", "forecast")
            observed = item.extra.get("observed_at")
            fingerprint = {
                "stage": stage,
                "start": item.start.isoformat(),
                "zone": item.zone_id,
                "peak": item.extra.get("wave_height_m"),
                "measurement": item.extra.get("measurement_label"),
                "expires": ((item.end or item.start) + timedelta(days=31)).isoformat(),
            }
            previous = self.announced.get(key)
            reason = "First worthwhile opportunity"
            if previous:
                old_start = timestamp(previous.get("start"))
                shifted = old_start and abs((item.start - old_start).total_seconds()) >= 6 * 3600
                confirmed = stage == "corroborated" and previous.get("stage") != stage
                wave_change = (fingerprint["measurement"] == previous.get("measurement")
                               and fingerprint["peak"] is not None and previous.get("peak") is not None
                               and fingerprint["peak"] >= previous["peak"] * 1.25)
                # A followed occurrence may change its best place. Unfollowed
                # alternatives reshuffling would otherwise become noisy.
                moved = self.choice(key) == "follow" and previous.get("zone") != item.zone_id
                if not (shifted or confirmed or wave_change or moved):
                    continue
                reason = ("New confirmation" if confirmed else "Swell substantially larger"
                          if wave_change else "Timing changed" if shifted else "Best location changed")
            self.announced[key] = fingerprint
            notifications.append({
                "event_id": key, "title": item.title, "reason": reason,
                "starts": item.start.isoformat(), "ends": item.end.isoformat() if item.end else None,
                "where": item.zone_name, "drive_hours": item.drive_hours,
                "verification": stage, "observed_at": observed,
                "detail": item.detail, "source_url": item.source_url,
            })
        return notifications

