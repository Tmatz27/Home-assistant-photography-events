"""Regenerate the shipped 2026–2035 NASA catalog; no network during HA updates.

Use --cache DIR for downloaded NASA pages. Greatest eclipse is in TD in these
catalogs, not UT: subtract the catalog's Delta T, keeping the original values
for audit. Path tables already use UT. Do not replace coordinates with regions.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://eclipse.gsfc.nasa.gov/"
CATALOGS = {"solar": BASE + "SEcat5/SE2001-2100.html", "lunar": BASE + "LEcat5/LE2001-2100.html"}


def fetch(url, cache, name):
    path = cache / name
    if not path.exists():
        with urlopen(Request(url, headers={"User-Agent": "PhotographyEvents catalog maintenance"}), timeout=45) as response:
            path.write_bytes(response.read())
    return path.read_text(encoding="utf-8")


def parse_catalog(markup, kind, start=2026, end=2035):
    found = []
    # Strip tags one physical line at a time: links break up cells, but a line
    # remains a complete catalog row. A schema mismatch aborts the import.
    for line in markup.splitlines():
        plain = BeautifulSoup(line, "html.parser").get_text()
        if not re.match(r"\s*\d{5}\s+20\d{2}\s+[A-Z][a-z]{2}\s+\d{2}\s+\d{2}:\d{2}:\d{2}", plain):
            continue
        fields = plain.split()
        if not start <= int(fields[1]) <= end:
            continue
        td = datetime.strptime(" ".join(fields[1:5]), "%Y %b %d %H:%M:%S").replace(tzinfo=timezone.utc)
        delta = int(fields[5])
        code = fields[8][0]
        types = {"T": "total", "P": "partial", "A": "annular", "H": "hybrid", "N": "penumbral"}
        row = {"date": (td - timedelta(seconds=delta)).isoformat().replace("+00:00", "Z"),
               "td": td.isoformat().replace("+00:00", "Z"), "delta_t_seconds": delta,
               "kind": kind, "type": types[code], "magnitude": float(fields[12] if kind == "lunar" else fields[11]),
               "source_url": CATALOGS[kind]}
        if kind == "lunar":
            row["partial_minutes"] = float(fields[14]) if fields[14] != "-" else 0
            row["total_minutes"] = float(fields[15]) if fields[15] != "-" else 0
        else:
            soup = BeautifulSoup(line, "html.parser")
            link = soup.find("a", href=re.compile(r"path\.html$"))
            if link:
                row["path_url"] = urljoin(CATALOGS[kind], link["href"])
        found.append(row)
    if len(found) < 15:
        raise ValueError(f"Unexpectedly short {kind} catalog: {len(found)}")
    return found


def parse_path(markup):
    soup = BeautifulSoup(markup, "html.parser")
    points = []
    for block in soup.find_all("pre"):
        for line in block.get_text().splitlines():
            clock = re.match(r"\s*(\d{2}:\d{2})\s", line)
            if not clock:
                continue
            coords = list(re.finditer(r"(\d{1,3})\s+(\d{2}\.\d)([NSEW])", line))
            if len(coords) < 2:
                continue
            # Central coordinates are the last geographic pair, even where one
            # horizon limit is missing. Keep every published timed center point.
            pair = coords[-2:]
            lat, lon = [round((int(m[1]) + float(m[2]) / 60) * (-1 if m[3] in "SW" else 1), 5) for m in pair]
            tail = line[pair[-1].end():].split()
            if pair[0][3] not in "NS" or pair[1][3] not in "EW" or len(tail) < 4:
                raise ValueError("Unexpected path coordinate layout")
            width = float(tail[3])
            points.append([clock[1], lat, lon, width])
    if len(points) < 20:
        raise ValueError("Path table missing timed central coordinates")
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    rows, provenance = [], []
    for kind, url in CATALOGS.items():
        markup = fetch(url, args.cache, f"{kind}-catalog.html")
        provenance.append({"url": url, "sha256": hashlib.sha256(markup.encode()).hexdigest()})
        rows.extend(parse_catalog(markup, kind))
    for row in rows:
        if "path_url" not in row:
            continue
        markup = fetch(row["path_url"], args.cache, row["path_url"].rsplit("/", 1)[-1])
        row["path"] = parse_path(markup)
        provenance.append({"url": row["path_url"], "sha256": hashlib.sha256(markup.encode()).hexdigest()})
        print(row["date"][:10], len(row["path"]), "sourced centerline points", flush=True)
    rows.sort(key=lambda row: row["date"])
    output = {"coverage": [2026, 2035], "time_basis": "NASA catalog TD minus its published Delta T; approximate UT",
              "path_columns": ["UT", "latitude_deg", "longitude_deg", "width_km"],
              "provenance": provenance, "events": rows}
    target = ROOT / "custom_components/photography_events/eclipse_catalog.json"
    target.write_text(json.dumps(output, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(len(rows), "eclipses written")


if __name__ == "__main__":
    main()
