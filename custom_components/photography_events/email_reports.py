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

from .const import CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MAMMALS, CATEGORY_MARINE, ZONES_BY_ID
from .field_reports import (
    BLOOM_SIGNALS,
    FOLIAGE_SIGNALS,
    FieldReport,
    best_sentence,
    build_snippet,
    is_negated,
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
    ("pupping", 16),
    ("pups on the beach", 16),
    ("bulls fighting", 16),
    ("sows with cubs", 16),
    ("herd is", 10),
    ("sighted", 8),
    ("sightings", 8),
)

SIGNALS_BY_CATEGORY: dict[str, tuple[tuple[str, int], ...]] = {
    CATEGORY_MARINE: MARINE_SIGNALS,
    CATEGORY_MAMMALS: MAMMAL_SIGNALS,
    CATEGORY_BLOOMS: BLOOM_SIGNALS,
    CATEGORY_FOLIAGE: FOLIAGE_SIGNALS,
}

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
    sentence = best_sentence(haystack, signals)
    if is_negated(sentence):
        return []

    snippet = build_snippet(haystack, signals)
    source_id = "email_" + re.sub(r"[^a-z0-9]+", "_", (source_name or "inbox").lower()).strip("_")
    return [
        FieldReport(
            source_id=source_id,
            source_name=source_name or "Email subscription",
            url=url,
            category=category,
            zone_id=zone,
            headline=(subject or "Reported by email").strip()[:160],
            snippet=snippet,
            strength=strength,
            # When the mail arrived, not when it was read. Unlike a scraped
            # page, an email genuinely knows its own date, and that is what
            # makes expiry meaningful here.
            fetched=received,
            context=source_name or "",
        )
        for zone in zone_ids
    ]
