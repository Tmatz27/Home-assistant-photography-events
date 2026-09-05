"""Live bloom and autumn-colour reports scraped from the public hotlines.

Bloom timing is the one thing here that cannot be computed. It depends on the
winter's rain, and the only people who know are the ones who drove out and
looked - the Theodore Payne Foundation's wildflower hotline, DesertUSA's desert
reports, and California Fall Color. A static seasonal table cannot answer
"is it happening *this* year", so it is not asked to: these scrapers are the
authority on blooms, and the curated windows in ``seasonal.py`` stay in the
365-day view as trip-planning context only.

Parsing is done with BeautifulSoup against per-source selectors collected in
``SOURCE_SELECTORS``. They are deliberately kept in one table, at the top,
written as plain CSS - when one of these sites is redesigned that table is the
only thing that needs editing.

Structure earns its keep here beyond tidiness. All three sites write a place
name as a heading and then describe it in prose that never repeats the name:

    <h3>Carrizo Plain National Monument</h3>
    <p>Hillsides are carpeted in goldfields right now.</p>

Read as flat text the sentence about carpets has no location in it at all.
Walking the DOM keeps each block attached to the heading above it, so the
report lands on the right zone.

Three behaviours are load-bearing:

- **It fails soft, at every level.** A missing library, a dead site, a changed
  layout, an unparseable block: each degrades to fewer reports, never to an
  error. If the selectors match nothing, it re-reads the page as flat text
  rather than giving up.
- **It reads negation.** "The poppies are past peak" contains "peak", and a
  naive keyword match would send you three hours to photograph seed heads.
- **It never raises a drop-everything alert on its own.** These sentences
  describe where somebody stood, days ago.
"""

from __future__ import annotations

import html as html_module
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from .const import CATEGORY_BLOOMS, CATEGORY_FOLIAGE

_LOGGER = logging.getLogger(__name__)

# How often these are polled. They are updated weekly at best and are small
# volunteer-run sites, so hourly polling would be both pointless and rude.
SCRAPE_INTERVAL_HOURS = 24

# --- Maintenance table ------------------------------------------------------
# If a site is redesigned, edit here and nowhere else. `container` is tried in
# order until one matches; `blocks` selects the readable chunks inside it.
# Both fall back to sensible defaults, so a partial match still works.
SOURCE_SELECTORS: dict[str, dict[str, list[str]]] = {
    "theodore_payne": {
        "container": ["div.entry-content", "article", "main", "div#content"],
        "blocks": ["h1", "h2", "h3", "h4", "p", "li"],
    },
    "desertusa": {
        "container": ["div#content", "div.content", "table", "article", "main"],
        "blocks": ["h1", "h2", "h3", "h4", "p", "li", "td"],
    },
    "california_fall_color": {
        "container": ["div.entry-content", "article", "main", "div#content"],
        "blocks": ["h1", "h2", "h3", "h4", "p", "li"],
    },
}

DEFAULT_CONTAINERS = ["article", "main", "div.entry-content", "body"]
DEFAULT_BLOCKS = ["h1", "h2", "h3", "h4", "p", "li"]
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# Phrases that mean "it is happening now", with how strongly each says it.
BLOOM_SIGNALS: tuple[tuple[str, int], ...] = (
    ("peak bloom", 20),
    ("superbloom", 20),
    ("super bloom", 20),
    ("carpets", 18),
    ("carpeting", 18),
    ("carpeted", 18),
    ("in full bloom", 18),
    ("blanketed", 16),
    ("spectacular", 14),
    ("best display", 14),
    ("blooming now", 12),
    ("hillsides are", 12),
    ("wildflowers are", 8),
)

FOLIAGE_SIGNALS: tuple[tuple[str, int], ...] = (
    ("go now", 20),
    ("75-100%", 20),
    ("75%-100%", 20),
    ("peak color", 18),
    ("peak colour", 18),
    ("near peak", 14),
    ("patchy", 4),
    ("50-75%", 10),
)

# Phrases that mean the opposite, whatever else the block contains.
NEGATIONS: tuple[str, ...] = (
    "past peak",
    "past its peak",
    "past their peak",
    "gone by",
    "over for the season",
    "has ended",
    "not yet",
    "too early",
    "no color",
    "no colour",
    "leaves have dropped",
    "little to no",
    "disappointing",
    "bare branches",
)

# Place names as these reports actually write them, mapped to target zones.
# Bare "Santa Cruz" is deliberately absent: on this coast it means either the
# island off Ventura or the mountains near Monterey Bay, 300 km apart.
ZONE_HINTS: tuple[tuple[str, str], ...] = (
    ("carrizo", "carrizo_plain"),
    ("soda lake", "carrizo_plain"),
    ("temblor", "carrizo_plain"),
    ("antelope valley", "antelope_valley"),
    ("poppy reserve", "antelope_valley"),
    ("lancaster", "antelope_valley"),
    ("gorman", "antelope_valley"),
    ("death valley", "death_valley"),
    ("badwater", "death_valley"),
    ("furnace creek", "death_valley"),
    ("channel islands", "channel_islands"),
    # Whale Safe and the whale-watch operators name the water, not the harbour.
    ("santa barbara channel", "channel_islands"),
    ("santa barbara", "channel_islands"),
    ("point conception", "channel_islands"),
    ("oxnard", "channel_islands"),
    ("santa cruz island", "channel_islands"),
    ("anacapa", "channel_islands"),
    ("ventura", "channel_islands"),
    ("big sur", "big_sur"),
    ("monterey bay", "big_sur"),
    ("julia pfeiffer", "big_sur"),
    ("pinnacles", "pinnacles"),
    ("morro bay", "piedras_blancas"),
    ("san simeon", "piedras_blancas"),
    ("piedras blancas", "piedras_blancas"),
    ("cambria", "piedras_blancas"),
    ("santa cruz mountains", "santa_cruz_redwoods"),
    ("big basin", "santa_cruz_redwoods"),
    ("henry cowell", "santa_cruz_redwoods"),
    ("sequoia national park", "sequoia_kings"),
    ("kings canyon", "sequoia_kings"),
    ("mineral king", "sequoia_kings"),
    ("yosemite", "yosemite_valley"),
    ("tioga", "yosemite_valley"),
    ("bishop", "eastern_sierra"),
    ("june lake", "eastern_sierra"),
    ("conway summit", "eastern_sierra"),
    ("lundy", "eastern_sierra"),
    ("mcgee creek", "eastern_sierra"),
    ("rock creek", "eastern_sierra"),
    ("tahoe", "lake_tahoe"),
    ("hope valley", "lake_tahoe"),
    ("truckee", "lake_tahoe"),
)

REPORT_SOURCES: tuple[dict, ...] = (
    {
        "id": "theodore_payne",
        "name": "Theodore Payne Wildflower Hotline",
        "url": "https://theodorepayne.org/wildflower-hotline/",
        "category": CATEGORY_BLOOMS,
        "signals": BLOOM_SIGNALS,
        "headline": "Wildflowers reported",
    },
    {
        "id": "desertusa",
        "name": "DesertUSA Wildflower Reports",
        "url": "https://www.desertusa.com/wildflo/wildupdates.html",
        "category": CATEGORY_BLOOMS,
        "signals": BLOOM_SIGNALS,
        "headline": "Desert bloom reported",
    },
    {
        "id": "california_fall_color",
        "name": "California Fall Color",
        "url": "https://www.californiafallcolor.com/",
        "category": CATEGORY_FOLIAGE,
        "signals": FOLIAGE_SIGNALS,
        "headline": "Autumn colour reported",
    },
)

MAX_SNIPPET_CHARS = 220
MIN_BLOCK_CHARS = 15
_TAG = re.compile(r"<[^>]+>")
_DROP_BLOCKS = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_WHITESPACE = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class FieldReport:
    """One observation from one hotline, tied to one zone."""

    source_id: str
    source_name: str
    url: str
    category: str
    zone_id: str
    headline: str
    snippet: str
    strength: int
    fetched: datetime | None = None
    context: str = ""

    def age_label(self, now: datetime) -> str:
        """When the page was *read*, which is all these pages tell us.

        None of the three date their individual entries, so calling a report
        "today's" would be inventing a fact. This says only what is known: when
        the text was last pulled.
        """
        if self.fetched is None:
            return "in the latest published report"
        hours = max(0.0, (now - self.fetched).total_seconds() / 3600)
        if hours < 24:
            return "on the page as read today"
        return f"on the page as read {round(hours / 24)} days ago"


# --- Extraction -------------------------------------------------------------


def _soup(raw_html: str):
    """Parse with BeautifulSoup, or None if it is unavailable or unhappy."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        _LOGGER.debug("beautifulsoup4 not installed; falling back to text scraping")
        return None

    for parser in ("lxml", "html.parser"):
        try:
            return BeautifulSoup(raw_html, parser)
        except Exception:  # noqa: BLE001 - lxml may not be installed
            continue
    return None


def extract_blocks(raw_html: str, source_id: str = "") -> list[tuple[str, str]]:
    """(heading, text) pairs for every readable block on the page.

    The heading is whatever section title most recently preceded the block,
    which is where these sites keep the place name.
    """
    soup = _soup(raw_html)
    if soup is None:
        return [("", line) for line in strip_html(raw_html).split("\n")]

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    selectors = SOURCE_SELECTORS.get(source_id, {})
    container = None
    for selector in selectors.get("container", DEFAULT_CONTAINERS):
        try:
            container = soup.select_one(selector)
        except Exception:  # noqa: BLE001 - a malformed selector must not be fatal
            container = None
        if container is not None:
            break
    if container is None:
        container = soup.body or soup

    block_tags = selectors.get("blocks", DEFAULT_BLOCKS)
    blocks: list[tuple[str, str]] = []
    heading = ""
    try:
        elements = container.find_all(block_tags)
    except Exception:  # noqa: BLE001
        elements = []

    for element in elements:
        text = _WHITESPACE.sub(" ", element.get_text(" ", strip=True)).strip()
        if not text:
            continue
        if element.name in HEADING_TAGS:
            heading = text
            # A heading can carry the whole report on its own ("Bishop Creek -
            # Go Now!"), so it is scanned as a block too.
            blocks.append((heading, text))
            continue
        blocks.append((heading, text))

    if not blocks:
        # Selectors matched nothing, which is what a redesign looks like.
        _LOGGER.debug("No blocks matched for %s; falling back to flat text", source_id or "page")
        return [("", line) for line in strip_html(raw_html).split("\n")]
    return blocks


def strip_html(raw: str) -> str:
    """Plain text from markup - the fallback when BeautifulSoup cannot help.

    The source's own newlines are flattened *before* block boundaries become
    breaks. Markup wraps wherever the author's editor happened to wrap, and
    treating those wraps as block ends chops a sentence in half, taking the
    strongest phrase in it with them.
    """
    if not isinstance(raw, str):
        return ""
    flattened = _WHITESPACE.sub(" ", _DROP_BLOCKS.sub(" ", raw))
    spaced = re.sub(r"</(p|div|li|h[1-6]|tr|td|blockquote)\s*>", "\n", flattened, flags=re.IGNORECASE)
    spaced = re.sub(r"<br\s*/?>", "\n", spaced, flags=re.IGNORECASE)
    text = html_module.unescape(_TAG.sub(" ", spaced))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


# --- Matching ---------------------------------------------------------------


def zones_in(text: str) -> list[str]:
    """Every zone a piece of text names, longest hint first so specifics win."""
    lowered = text.lower()
    found: list[str] = []
    for hint, zone_id in sorted(ZONE_HINTS, key=lambda pair: -len(pair[0])):
        if hint in lowered and zone_id not in found:
            found.append(zone_id)
    return found


def is_negated(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in NEGATIONS)


def signal_strength(text: str, signals: tuple[tuple[str, int], ...]) -> int:
    """The strongest matching phrase, not the sum.

    Summing rewards a block that lists synonyms over one that actually says
    more, and these reports are written by people who like synonyms.
    """
    lowered = text.lower()
    return max((weight for phrase, weight in signals if phrase in lowered), default=0)


def best_sentence(text: str, signals: tuple[tuple[str, int], ...]) -> str:
    """The sentence carrying the strongest signal, so the quote is the point."""
    sentences = _sentences(text)
    if not sentences:
        return text
    return max(sentences, key=lambda sentence: (signal_strength(sentence, signals), -len(sentence)))


def build_snippet(text: str, signals: tuple[tuple[str, int], ...]) -> str:
    """Quote the strongest sentence, grown outwards until it reads as prose.

    The strongest sentence is often the least informative one on its own -
    California Fall Color's whole verdict is the two words "Go Now!" - so
    neighbouring sentences are pulled in until the quote either fills the
    budget or runs into a negated one. Stopping at negation is what keeps
    "Carrizo is carpeted. The Temblor Range is past peak." from being quoted
    back as though both halves were good news.
    """
    sentences = _sentences(text)
    if not sentences:
        return _truncate(text)

    scores = [signal_strength(sentence, signals) for sentence in sentences]
    best = max(range(len(sentences)), key=lambda i: (scores[i], -len(sentences[i])))
    first = last = best
    length = len(sentences[best])

    # Grow forward first: these reports put the verdict before the detail.
    for step in range(1, len(sentences)):
        grew = False
        after = last + 1
        if after < len(sentences) and not is_negated(sentences[after]):
            candidate = length + 1 + len(sentences[after])
            if candidate <= MAX_SNIPPET_CHARS:
                last, length, grew = after, candidate, True
        before = first - 1
        if before >= 0 and not is_negated(sentences[before]):
            candidate = length + 1 + len(sentences[before])
            if candidate <= MAX_SNIPPET_CHARS:
                first, length, grew = before, candidate, True
        if not grew:
            break

    return _truncate(" ".join(sentences[first : last + 1]))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def _truncate(text: str) -> str:
    if len(text) <= MAX_SNIPPET_CHARS:
        return text
    return text[: MAX_SNIPPET_CHARS - 1].rstrip() + "\u2026"


def parse_report(raw_html: str, source: dict, fetched: datetime | None = None) -> list[FieldReport]:
    """Extract at most one report per zone from one hotline page.

    A page mentioning Carrizo four times is still one place to drive to, so only
    the strongest block for each zone survives.
    """
    blocks = extract_blocks(raw_html, source.get("id", ""))
    if not blocks:
        return []

    best: dict[str, FieldReport] = {}
    for heading, text in blocks:
        if len(text) < MIN_BLOCK_CHARS:
            continue
        strength = signal_strength(text, source["signals"])
        if strength <= 0:
            continue
        # Negation is checked on the sentence that will actually be quoted, so
        # "Carrizo is carpeted. The Temblor Range is past peak." does not lose
        # the good half of the paragraph.
        sentence = best_sentence(text, source["signals"])
        if is_negated(sentence):
            continue

        # The heading is where the place name usually lives; the block text is
        # where it sometimes lives. Both are searched, block first.
        zone_ids = zones_in(text) or zones_in(heading)
        if not zone_ids:
            continue

        snippet = build_snippet(text, source["signals"])
        for zone_id in zone_ids:
            existing = best.get(zone_id)
            if existing is not None and existing.strength >= strength:
                continue
            best[zone_id] = FieldReport(
                source_id=source["id"],
                source_name=source["name"],
                url=source["url"],
                category=source["category"],
                zone_id=zone_id,
                headline=source["headline"],
                snippet=snippet,
                strength=strength,
                fetched=fetched,
                context=heading,
            )
    return list(best.values())
