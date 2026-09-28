"""Turn a subscription email into a field report the evidence model can use.

Some of the best sources on this coast do not publish an API. They publish a
mailing list: a person reads the data and writes a paragraph, once a day or once
a week, and sends it to whoever signed up. That paragraph is genuine ground
truth - often better than anything machine-readable, because a human already
decided what mattered - and until now there was no way to get it in here.

This is the way in. Home Assistant's built-in IMAP integration watches a folder
and fires an ``imap_content`` event when a matching message lands; an automation
passes the body to ``photography_events.ingest_report``; and the text arrives
here to be read the same way the scraped hotlines are read - place names matched
to zones, signal phrases scored, negation honoured, everything unrecognised
dropped rather than guessed at.

Three rules, and they are the reason this is safe to point at an inbox:

- **The email is data, never instruction.** Nothing in a message body changes
  what the integration does. It is matched against a fixed vocabulary and
  discarded if it does not fit; a sentence in an email cannot add a zone, move a
  window, or raise a score by saying so.
- **A report with no recognisable place is dropped.** Corroboration is
  distance-based, so a report that cannot be located would otherwise corroborate
  everything, everywhere. Silence is the correct output.
- **It expires.** An email is stamped with when it arrived, and stops
  corroborating anything once it is older than the corroboration window. A
  three-week-old "whales are here" is not evidence about today.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from .const import (
    CATEGORY_BIRDS, CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MAMMALS, CATEGORY_MARINE, CATEGORY_RARE,
    ZONES_BY_ID,
)
from .field_reports import (
    BLOOM_SIGNALS,
    FOLIAGE_SIGNALS,
    FieldReport,
    best_sentence,
    build_snippet,
    explicit_date,
    is_negated,
    place_point,
    signal_strength,
    zones_in,
)

_LOGGER = logging.getLogger(__name__)

# Presence language, roughly in the order a marine biologist would rank it.
# Whale Safe's own daily rating uses "high / medium / low", which is why those
# three appear as phrases rather than bare words - "low" on its own matches half
# the English language.
MARINE_SIGNALS: tuple[tuple[str, int], ...] = (
    ("very high whale presence", 20),
    ("high whale presence", 18),
    ("whale presence: high", 18),
    ("whale presence is high", 18),
    ("large aggregation", 18),
    ("multiple sightings", 16),
    ("feeding aggregation", 16),
    ("blue whales", 15),
    ("orca", 15),
    ("killer whale", 15),
    ("mega-pod", 15),
    ("megapod", 15),
    ("humpbacks", 12),
    ("lunge feeding", 14),
    ("breaching", 12),
    ("medium whale presence", 10),
    ("whale presence: medium", 10),
    ("sighted", 8),
    ("sightings", 8),
)

MAMMAL_SIGNALS: tuple[tuple[str, int], ...] = (
    ("rut is underway", 18),
    ("bugling", 16),
    ("sparring", 14),
    ("pupping", 16),
    ("pups on the beach", 16),
    ("first pup", 16),
    ("bulls fighting", 16),
    ("sows with cubs", 16),
    ("sow with cubs", 16),
    ("sow and cub", 16),
    ("herd is", 10),
    ("sighted", 8),
    ("sightings", 8),
)

# Phenomena that are neither animals nor blooms: monarch clusters, glowing
# surf, waterfall ice, flow on Horsetail Fall. The same fixed-vocabulary rule
# applies - a matching phrase can attach a report to a curated phenomenon,
# never invent one.
RARE_SIGNALS: tuple[tuple[str, int], ...] = (
    ("bioluminescence", 18),
    ("bioluminescent", 18),
    ("glowing waves", 18),
    ("frazil ice", 18),
    ("firefall", 18),
    ("horsetail fall is flowing", 18),
    ("moonbow", 16),
    ("monarchs", 12),
    ("clusters", 12),
    ("fresh snow", 12),
    ("fly-in", 14),
)

BIRD_SIGNALS: tuple[tuple[str, int], ...] = (
    ("eagles fishing", 16),
    ("eagle fishing", 16),
    ("multiple eagles", 14),
    ("several eagles", 14),
    ("condors", 14),
    ("rushing", 14),
    ("lift-off", 14),
    ("thousands of geese", 14),
    ("thousands of cranes", 14),
)

SIGNALS_BY_CATEGORY: dict[str, tuple[tuple[str, int], ...]] = {
    CATEGORY_MARINE: MARINE_SIGNALS,
    CATEGORY_MAMMALS: MAMMAL_SIGNALS,
    CATEGORY_BLOOMS: BLOOM_SIGNALS,
    CATEGORY_FOLIAGE: FOLIAGE_SIGNALS,
    CATEGORY_RARE: RARE_SIGNALS,
    CATEGORY_BIRDS: BIRD_SIGNALS,
}

# Words that date an observation relative to when the message was sent. A
# daily digest saying "this morning" describes the day it arrived; anything
# vaguer ("recently", "this week") leaves the observation undated.
SAME_DAY = re.compile(r"\b(today|this morning|this afternoon|this evening|tonight)\b", re.IGNORECASE)

# Used only when the caller does not say. Ordered most specific first, because
# a whale newsletter that happens to mention a flower is still a whale
# newsletter.
CATEGORY_HINTS: tuple[tuple[str, str], ...] = (
    (CATEGORY_MARINE, "whale"),
    (CATEGORY_MARINE, "dolphin"),
    (CATEGORY_MARINE, "orca"),
    (CATEGORY_MARINE, "cetacean"),
    (CATEGORY_MAMMALS, "elephant seal"),
    (CATEGORY_MAMMALS, "tule elk"),
    (CATEGORY_MAMMALS, "bighorn"),
    (CATEGORY_MAMMALS, "black bear"),
    (CATEGORY_MAMMALS, "harbor seal"),
    (CATEGORY_RARE, "monarch"),
    (CATEGORY_RARE, "bioluminescen"),
    (CATEGORY_RARE, "frazil"),
    (CATEGORY_RARE, "firefall"),
    (CATEGORY_RARE, "moonbow"),
    (CATEGORY_BIRDS, "eagle"),
    (CATEGORY_BIRDS, "condor"),
    (CATEGORY_BIRDS, "grebe"),
    (CATEGORY_FOLIAGE, "fall color"),
    (CATEGORY_FOLIAGE, "autumn colour"),
    (CATEGORY_FOLIAGE, "aspen"),
    (CATEGORY_BLOOMS, "wildflower"),
    (CATEGORY_BLOOMS, "bloom"),
    (CATEGORY_BLOOMS, "poppy"),
)

# Emails carry more furniture than a web page: quoted replies, unsubscribe
# blocks, tracking pixels rendered as URLs. None of it is a field report, and
# some of it ("view this email in your browser") scores on naive keyword
# matching, so it goes before anything is read.
_QUOTED = re.compile(r"^\s*(>|On .{0,80} wrote:)", re.MULTILINE)
_FOOTER = re.compile(
    r"(unsubscribe|manage your preferences|view this email in your browser|"
    r"you are receiving this|sent to you because|update your profile|"
    r"privacy policy|©\s*\d{4})",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+")
_WHITESPACE = re.compile(r"[ \t ]+")

MAX_BODY_CHARS = 40000
MIN_BLOCK_CHARS = 15


def clean_body(body: str) -> str:
    """Strip the parts of an email that are not the message.

    Truncated first: a mailing list that embeds a base64 image inline can run to
    megabytes, and none of it after the first few pages is ever the report.
    """
    text = (body or "")[:MAX_BODY_CHARS]
    text = _URL.sub(" ", text)
    quoted = _QUOTED.search(text)
    if quoted:
        text = text[: quoted.start()]
    footer = _FOOTER.search(text)
    if footer:
        text = text[: footer.start()]
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def infer_category(subject: str, body: str) -> str | None:
    """Guess what an email is about, when the automation did not say."""
    haystack = f"{subject or ''}\n{body or ''}".lower()
    for category, hint in CATEGORY_HINTS:
        if hint in haystack:
            return category
    return None


def parse_email_report(
    subject: str,
    body: str,
    source_name: str,
    category: str | None = None,
    zone_id: str | None = None,
    received: datetime | None = None,
    url: str = "",
) -> list[FieldReport]:
    """Read one email into at most one report per zone it names.

    Returns an empty list rather than a low-confidence guess whenever the text
    does not clearly say something happened somewhere recognisable - which for a
    mailing list is most days, and is the right answer on those days.
    """
    text = clean_body(body)
    if len(text) < MIN_BLOCK_CHARS:
        return []

    category = category or infer_category(subject, text)
    signals = SIGNALS_BY_CATEGORY.get(category or "")
    if not signals:
        _LOGGER.debug("Ignoring email %r: no category could be established", subject)
        return []

    # The subject line is usually where a daily digest puts its headline
    # ("High whale presence in the Santa Barbara Channel"), so it is read as
    # part of the text rather than as metadata.
    haystack = f"{subject or ''}\n{text}"

    # An explicit zone from the automation beats anything inferred: somebody who
    # subscribed to a single-region digest knows the region better than a
    # keyword table does.
    zone_ids = [zone_id] if zone_id and zone_id in ZONES_BY_ID else zones_in(haystack)
    if not zone_ids:
        _LOGGER.debug("Ignoring email %r: names no zone this integration knows", subject)
        return []

    strength = signal_strength(haystack, signals)
    if strength <= 0:
        return []

    source_id = "email_" + re.sub(r"[^a-z0-9]+", "_", (source_name or "inbox").lower()).strip("_")
    headline = (subject or "Reported by email").strip()[:160]
    explicit_zone = zone_id if zone_id and zone_id in ZONES_BY_ID else None

    def make(zone, snippet, observed, *, phenomena=(), count=None, point=None, place=""):
        return FieldReport(
            source_id=source_id, source_name=source_name or "Email subscription", url=url,
            category=category, zone_id=zone, headline=headline, snippet=snippet, strength=strength,
            # When the mail arrived, not when it was read. Unlike a scraped
            # page, an email genuinely knows its own date, and that is what
            # makes expiry meaningful here.
            fetched=received, context=source_name or "", observed_at=observed,
            phenomenon_key=phenomena[0] if len(phenomena) == 1 else "",
            count=count, latitude=point[0] if point else None, longitude=point[1] if point else None,
            phenomena=tuple(phenomena), place=place, normalized=True)

    # Each report is one explicit statement: its subject, behaviour, polarity,
    # count, place and date all come from that statement (observations.py),
    # never from co-occurrence elsewhere in the message. A negated statement
    # confirms nothing; an unlocated one corroborates nothing.
    from .observations import observe, positive
    reports: dict[tuple, FieldReport] = {}
    for item in positive(observe(text, received, category=category, default_zone=explicit_zone,
                                 subject_hint=subject or "")):
        zone = explicit_zone or item.zone_id
        if not zone or zone not in ZONES_BY_ID:
            continue
        # The observed place is independent of the zone an automation files
        # the mail under: a Pismo sighting sent with zone "piedras_blancas"
        # happened at Pismo, and is evaluated there.
        point = (item.latitude, item.longitude) if item.latitude is not None else None
        key = (item.phenomenon, zone, point)
        current = reports.get(key)
        if current is not None and (current.observed_at or received) >= (item.observed_at or received) \
                and (current.count or 0) >= (item.count or 0):
            continue
        reports[key] = make(zone, item.text[:220], item.observed_at, phenomena=(item.phenomenon,),
                            count=item.count, point=point, place=item.place)
    if reports:
        return list(reports.values())

    # No curated phenomenon named: keep one generic report per named zone as a
    # background signal (it can corroborate nothing, see report_phenomena).
    sentence = best_sentence(haystack, signals)
    if is_negated(sentence) or re.match(r"\s*(?:no|not|none)\b", sentence, re.IGNORECASE):
        return []
    observed = explicit_date(sentence, received)
    if observed is None and received is not None and SAME_DAY.search(sentence):
        observed = received
    snippet = build_snippet(haystack, signals)
    point = place_point(sentence)
    return [make(zone, snippet, observed, point=point) for zone in zone_ids[:1 if point else None]]
