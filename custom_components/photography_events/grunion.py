"""CDFW expected runs, preserving the published year, timezone and location."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .events import Opportunity
from .wildlife import estimate_drive_hours

URL = "https://wildlife.ca.gov/Fishing/Ocean/Grunion"


def parse_schedule(raw):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, "html.parser")
    headings = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3", "caption"]))
    years = set(re.findall(r"\b20\d{2}\b", headings))
    if len(years) != 1:
        return []
    year = int(years.pop())
    result = []
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) != 3 or not re.fullmatch(r"\d{1,2}/\d{1,2}", cells[1]):
            continue
        times = cells[2].lower().replace("midnight", "12:00 a.m.")
        parts = re.findall(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?", times)
        if len(parts) != 2:
            continue
        try:
            month, day = map(int, cells[1].split("/"))
            moments = [datetime(year, month, day, int(h) % 12 + (12 if ap == "p" else 0), int(m),
                                tzinfo=ZoneInfo("America/Los_Angeles")) for h, m, ap in parts]
            if moments[1] <= moments[0]:
                moments[1] += timedelta(days=1)
            if moments[1] - moments[0] != timedelta(hours=2):
                continue
        except ValueError:
            continue
        result.append(tuple(moments))
    return sorted(set(result))


def opportunities(schedule, now, home):
    result = []
    for start, end in schedule:
        # CDFW explicitly gives this offset for Santa Barbara only. Do not
        # silently transfer it to Pismo, Ventura or another beach.
        start, end = start + timedelta(minutes=25), end + timedelta(minutes=25)
        if end < now or start > now + timedelta(days=365):
            continue
        result.append(Opportunity(
            key=f"grunion-cdfw-{start.date()}", title="CDFW expected grunion run", category="rare_phenomena",
            zone_id="grunion_run", zone_name="Santa Barbara — East Beach, check access",
            start=start, end=end, score=60, planning_only=True,
            detail="CDFW's probable two-hour spawning interval, adjusted by its published Santa Barbara offset. This is an expected run, not a confirmed appearance of fish.",
            latitude=34.418, longitude=-119.670, drive_hours=estimate_drive_hours(34.418, -119.670, home),
            source_url=URL,
            extra={"verification": "schedule", "tide_window_start": start.isoformat(),
                   "tide_window_end": end.isoformat(), "evidence_note": "Published CDFW schedule; Pacific local time, including daylight saving.",
                   "confidence_note": "Check the source and beach access before going. No promise fish will spawn on a particular beach."},
        ))
    return result
