"""Report text -> explicit observations: who did what, where, when, how many.

Before this module a report was matched as a bag of words. If the vocabulary
of a phenomenon appeared *anywhere* in an email, the email confirmed it; the
largest number anywhere became its count; negation was judged on one "best"
sentence. Three real failures followed:

- "No lunge feeding at Avila today. Humpbacks are passing offshore." confirmed
  humpback lunge feeding - the negation sat on one sentence and the subject on
  another, and neither was read as belonging to the other.
- "a megapod of 20 dolphins" confirmed a megapod: the aggregation word was
  present, and nothing required the pod to be the size the word promises.
- "Pismo today: 50 monarchs in dense clusters, with 2,000 geese passing
  overhead" became a 2,000-monarch count.

So text is first split into statements (sentences, then clauses at ``;`` and
contrastive joins such as ", but"), and each statement yields observations
whose subject, behaviour, polarity, count, place and date all come from that
statement - or from a genuine, unambiguous place/date header. A number counts a subject only
when it is written against that subject's noun. A negation cue negates the
behaviour it precedes inside its own clause, never a neighbouring statement.

Phenomenon requirements (minimum count, freshness, geography) are applied
*after* this, by ``admissible``, whichever path the report came in by.

Pure, fixed vocabulary, no Home Assistant, no learned model: the text is data,
never instruction (AGENTS.md invariant 8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

POSITIVE = "positive"
NEGATIVE = "negative"

# The noun that has to be present for a behaviour to belong to a phenomenon's
# animal. Phenomena not listed here name their subject in the behaviour phrase
# itself ("firefall", "frazil ice", "carpeted" for a bloom).
SUBJECT_TERMS: dict[str, tuple[str, ...]] = {
    "humpback_lunge_feeding": ("humpback",),
    "blue_whale_feeding": ("blue whale",),
    "transient_orca_hunt": ("orca", "killer whale"),
    "orca_presence": ("orca", "killer whale"),
    "gray_whale_northbound": ("gray whale", "grey whale"),
    "common_dolphin_calving": ("dolphin",),
    "dolphin_megapod": ("dolphin",),
    "elephant_seal_battles": ("elephant seal",),
    "harbor_seal_pupping": ("harbor seal", "harbour seal"),
    "tule_elk_rut": ("elk",),
    "black_bear_cubs": ("bear",),
    "sandhill_crane_flyin": ("crane",),
    "bald_eagle_cachuma": ("eagle",),
    "condor_activity": ("condor",),
    "waterfowl_mass_flight": ("goose", "geese"),
    "pismo_monarchs": ("monarch", "butterfl"),
}
# Nouns a count may be written against, per subject term (plural forms).
COUNT_NOUNS: dict[str, str] = {
    "humpback": r"humpbacks?(?:\s+whales?)?", "blue whale": r"blue\s+whales?", "orca": r"orcas?",
    "killer whale": r"killer\s+whales?", "gray whale": r"gr[ae]y\s+whales?", "grey whale": r"gr[ae]y\s+whales?",
    "dolphin": r"dolphins?", "elephant seal": r"elephant\s+seals?", "harbor seal": r"harbou?r\s+seals?",
    "harbour seal": r"harbou?r\s+seals?", "elk": r"elk", "bear": r"bears?", "crane": r"cranes?",
    "eagle": r"eagles?", "condor": r"condors?", "goose": r"(?:geese|goose)", "geese": r"(?:geese|goose)",
    "monarch": r"monarchs?(?:\s+butterfl(?:y|ies))?", "butterfl": r"butterfl(?:y|ies)",
}
# Phenomena whose evidence is the subject itself, on a dated positive statement
# (orcas are rare enough here that presence is the event).
PRESENCE_EVIDENCE = frozenset({"orca_presence"})
# Behaviour phrases that name their animal without its noun ("a sow with
# cubs" is a bear in this vocabulary). "with cubs" alone is not one.
SELF_IDENTIFYING = {
    "black_bear_cubs": ("sow with cubs", "sow and cubs", "sow and cub", "mother bear with cubs", "bear cubs"),
}
# Monitored colonies where the place names the animal: "first pups at Piedras
# Blancas" is the elephant seal rookery. Product rule, limited to sites whose
# managers publish that animal's cycle (curation sources).
SITE_SUBJECTS = {
    "elephant_seal_battles": ("piedras blancas", "elephant seal vista"),
    "harbor_seal_pupping": ("carpinteria",),
}

_NEGATION_CUE = re.compile(
    r"\b(?:no|not|none|never|without|zero|nothing|nor|no\s+signs?\s+of|didn't|did\s+not|wasn't|was\s+not|"
    r"weren't|were\s+not|isn't|aren't|haven't|hasn't|hadn't|absent|missed)\b", re.IGNORECASE)
# Hotline phrases that negate a whole bloom/colour statement.
_STATEMENT_NEGATIONS = ("past peak", "past its peak", "past their peak", "gone by", "over for the season",
                        "has ended", "not yet", "too early", "no color", "no colour", "leaves have dropped",
                        "little to no", "disappointing", "bare branches")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE = re.compile(r";|,?\s+\bbut\b\s+|,\s*(?:while|whereas|although|though)\s+", re.IGNORECASE)
_SAME_DAY = re.compile(r"\b(?:today|this morning|this afternoon|this evening|tonight)\b", re.IGNORECASE)
_YESTERDAY = re.compile(r"\b(?:yesterday|last night)\b", re.IGNORECASE)
# This explicit continuation states an observation on both days, including
# today. Unordered or conflicting date lists still have no single date.
_CONTINUING_TODAY = re.compile(r"\b(?:yesterday|last night)\s+and\s+today\b", re.IGNORECASE)
# Explicitly older than a day and without a date: it cannot inherit today's.
_VAGUE_PAST = re.compile(r"\b(?:last week|earlier this week|recently|a few days ago|last month|previous(?:ly)?)\b",
                         re.IGNORECASE)
_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+)"
_NON_OBSERVATION = re.compile(
    r"\b(?:planning|planned|plans?\s+to|hoping|hope\s+to|cancelled|canceled|expecting|"
    r"might|could|would|looking\s+for|wish|if)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Observation:
    """One explicit statement about one phenomenon."""

    phenomenon: str
    polarity: str
    text: str
    behaviors: tuple[str, ...] = ()
    subject: str = ""
    count: int | None = None
    observed_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    place: str = ""
    zone_id: str = ""


def statements(text: str) -> list[list[str]]:
    """Sentences, each split into clauses."""
    out = []
    for sentence in _SENTENCE.split(text or ""):
        sentence = sentence.strip()
        if not sentence:
            continue
        clauses = [part.strip(" ,") for part in _CLAUSE.split(sentence) if part and part.strip(" ,")]
        out.append(clauses or [sentence])
    return out


# Every animal a clause might be about, so a behaviour can be tied to the
# animal it is written against. Subject nouns map to their phenomenon's
# canonical animal; the rest are "other animals" that only ever *block* a
# binding ("sea lions feeding" is not condors feeding). Longest match first.
_CANONICAL = {"killer whale": "orca", "grey whale": "gray whale", "harbour seal": "harbor seal",
              "geese": "goose", "butterfl": "monarch"}
_OTHER_ANIMALS = (r"sea\s+lions?", r"(?:fur\s+)?seals?", r"otters?", r"porpoises?", r"fin\s+whales?",
                  r"minke\s+whales?", r"whales?", r"pelicans?", r"gulls?", r"birds?", r"ducks?", r"hawks?",
                  r"vultures?", r"ravens?", r"sharks?", r"fish", r"deer", r"coyotes?", r"bobcats?", r"pups?",
                  r"cormorants?", r"egrets?", r"herons?", r"swans?", r"sardines?", r"anchov(?:y|ies)", r"krill")


def _animal_patterns():
    rows = [(term, _CANONICAL.get(term, term), pattern) for term, pattern in COUNT_NOUNS.items()]
    rows += [(pattern, "other:" + pattern, pattern) for pattern in _OTHER_ANIMALS]
    return [(canonical, re.compile(r"\b" + pattern + r"\b", re.IGNORECASE)) for _term, canonical, pattern in rows]


_ANIMALS = _animal_patterns()


def animal_mentions(text: str) -> list[tuple[int, int, str]]:
    """(start, end, canonical animal) for every animal named, overlaps resolved longest-first."""
    found = []
    for canonical, pattern in _ANIMALS:
        for match in pattern.finditer(text):
            found.append((match.start(), match.end(), canonical))
    found.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    kept, last_end = [], -1
    for start, end, canonical in found:
        if start >= last_end:
            kept.append((start, end, canonical))
            last_end = end
        elif end - start > kept[-1][1] - kept[-1][0] and start == kept[-1][0]:
            kept[-1] = (start, end, canonical)
            last_end = end
    return kept


def _canonical_subjects(key: str) -> set[str]:
    return {_CANONICAL.get(term, term) for term in SUBJECT_TERMS.get(key, ())}


_ASSERTION_JOIN = re.compile(r"\b(?:and|or|but|while|whereas|although|though|as)\b|,\s+", re.IGNORECASE)
_RELATIONAL_SUBJECT = re.compile(r"\b(?:beside|alongside|with|among|near|behind|around|next\s+to)\s+(?:the\s+)?$")


def _assertion_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Local assertion around a phrase; do not split inside the phrase itself."""
    continuing = list(_CONTINUING_TODAY.finditer(text))
    joins = [join for join in _ASSERTION_JOIN.finditer(text)
             if not any(period.start() <= join.start() < period.end() for period in continuing)]
    left = max((join.end() for join in joins if join.end() <= start), default=0)
    right = min((join.start() for join in joins if join.start() >= end), default=len(text))
    return left, right


def _bound_animal(lowered: str, start: int, end: int) -> str | None:
    """One unambiguous animal in this assertion, never merely the nearest noun.

    Both orders of "dolphins beside humpbacks were lunge feeding" are held:
    this fixed-vocabulary parser cannot prove the grammatical attachment.
    An empty string means ambiguous; None means genuinely unnamed behavior.
    """
    left, right = _assertion_span(lowered, start, end)
    mentions = animal_mentions(lowered[left:right])
    # "First pups" at a monitored rookery is the existing colony rule, not
    # another animal's assertion. Pups elsewhere still cannot name a species.
    mentions = [(a, b, animal) for a, b, animal in mentions
                if not (animal == "other:pups?" and a + left < end and b + left > start)]
    if len(mentions) != 1:
        return "" if mentions else None
    first, _last, animal = mentions[0]
    # An unlisted animal can be the subject too. "Squirrels beside condors"
    # must not become condor behavior just because squirrels are not curated.
    if _RELATIONAL_SUBJECT.search(lowered[left:left + first]):
        return ""
    return animal


# A header is pure context: places, dates and a few report words. "Trip
# cancelled at Avila today" is a statement, not a header, and lends nothing.
HEADER_MAX_WORDS = 8
HEADER_WORDS = frozenset({
    "report", "reports", "update", "updates", "sighting", "sightings", "log", "daily", "weekly", "summary",
    "trip", "conditions", "from", "at", "for", "the", "in", "on", "of", "near", "off", "news", "notes",
    "observations", "whale", "watch", "wildlife", "digest", "edition", "am", "pm", "today", "tonight",
    "yesterday", "this", "morning", "afternoon", "evening", "last", "night", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
})


def _is_header(clause: str, catalog) -> bool:
    """A short statement of only places, dates and report words."""
    from .field_reports import PLACE_POINTS, ZONE_HINTS, _MONTHS

    lowered = clause.lower()
    if len(clause.split()) > HEADER_MAX_WORDS:
        return False
    if (_NON_OBSERVATION.search(clause) or animal_mentions(lowered)
            or any(term in lowered for item in catalog.values() for term in item.behavior_terms)):
        return False
    for name in sorted({*(row[0] for row in PLACE_POINTS), *(hint for hint, _ in ZONE_HINTS)}, key=len, reverse=True):
        lowered = lowered.replace(name, " ")
    words = re.findall(r"[a-z]+", lowered)
    return all(word in HEADER_WORDS or word in _MONTHS for word in words)


_JOINERS = re.compile(r"\b(?:and|or|with|plus|nor|but|than)\b|&|,", re.IGNORECASE)


def _subject_count(clause: str, term: str) -> int | None:
    """A number written against this subject's noun, e.g. "50 monarchs", "2,000 sandhill cranes".

    Up to two adjectives may sit between the number and the noun, never a
    conjunction or another animal: in "2,000 geese and monarchs" the 2,000 is
    geese.
    """
    noun = COUNT_NOUNS.get(term)
    if not noun:
        return None
    pattern = re.compile(_NUMBER + r"(\s+(?:[a-z][a-z-]*\s+){0,2}?)" + noun + r"\b", re.IGNORECASE)
    values = []
    for match in pattern.finditer(clause):
        gap = match.group(2)
        if _JOINERS.search(gap) or animal_mentions(gap):
            continue
        try:
            values.append(int(match.group(1).replace(",", "")))
        except ValueError:
            continue
    return max(values) if values else None


def _negated(clause: str, position: int) -> bool:
    """A negation cue before this phrase in its own clause, or a statement-level negation."""
    lowered = clause.lower()
    if any(phrase in lowered for phrase in _STATEMENT_NEGATIONS):
        return True
    return bool(_NEGATION_CUE.search(clause[:position]))


def _clause_date(clause: str, received: datetime | None):
    """(date, explicit) from the clause itself; (None, vague) when it points elsewhere in time."""
    from .field_reports import explicit_date, _NAMED_DATE, _NUMERIC_DATE

    if received is None:
        return None, False
    clause = _CONTINUING_TODAY.sub("today", clause)
    dates = [explicit_date(match.group(), received) for pattern in (_NAMED_DATE, _NUMERIC_DATE)
             for match in pattern.finditer(clause)]
    if _YESTERDAY.search(clause):
        dates.append(received - timedelta(days=1))
    if _SAME_DAY.search(clause):
        dates.append(received)
    if _VAGUE_PAST.search(clause):
        dates.append(None)
    if dates:
        return (dates[0] if len({d.date() if d else None for d in dates}) == 1 else None), True
    return None, False


AMBIGUOUS = {"ambiguous": True}


def _clause_place(clause: str):
    """The one place a clause names, AMBIGUOUS when it names distinct places, or None.

    "Avila and Monterey Bay today" names two regions: nothing in it may be
    placed at either. Two distinct points inside one zone are ambiguous too.
    """
    from .field_reports import PLACE_POINTS, zones_in

    lowered = clause.lower()
    zones = zones_in(clause)
    names = []
    for name, latitude, longitude in sorted(PLACE_POINTS, key=lambda row: -len(row[0])):
        if name in lowered and not any(name in longer for longer, *_ in names):
            names.append((name, latitude, longitude))
    if not zones and not names:
        return None
    if len(set(zones)) > 1:
        return AMBIGUOUS
    points = {(lat, lon) for _, lat, lon in names}
    if len(points) > 1:
        return AMBIGUOUS
    point = next(iter(points)) if len(points) == 1 else None
    return {"point": point, "zone": zones[0] if zones else "", "name": names[0][0] if len(points) == 1 else ""}


def _one_place(places):
    """The single place among several clause places, AMBIGUOUS, or None."""
    real = [place for place in places if place]
    if any(place is AMBIGUOUS for place in real):
        return AMBIGUOUS
    zones = {place["zone"] for place in real}
    points = {place["point"] for place in real if place.get("point") is not None}
    if len(zones) > 1 or len(points) > 1:
        return AMBIGUOUS
    return next((place for place in real if place.get("point") is not None), real[0] if real else None)


def observe(text: str, received: datetime | None, *, category: str | None = None,
            default_zone: str | None = None, subject_hint: str = "") -> list[Observation]:
    """Every explicit observation of a curated phenomenon in a text.

    ``category`` limits which phenomena may be named (the rare category also
    admits birds, as before). ``default_zone`` is a place stated outside the
    text (an automation's single-region digest, a hotline heading).
    ``subject_hint`` is context such as a subject line, read for message-level
    subject/place/date only.
    """
    from .const import CATEGORY_BIRDS, CATEGORY_RARE
    from .curation import CATALOG

    parsed = statements(text)
    whole = f"{subject_hint}\n{text}".lower()
    # Message-level context, used only when it is unambiguous *and* comes
    # from a place that is context rather than content: the subject line, an
    # automation's explicit zone, or a short header statement ("Sunday 27
    # Sept report", "Avila update:"). A place or date written in another
    # content sentence is never borrowed - "Lunge feeding off Monterey today.
    # Humpbacks passing Avila." must not put the lunge feeding at Avila.
    context = [clause for clauses in statements(subject_hint) for clause in clauses if _is_header(clause, CATALOG)]
    context += [clause for clauses in parsed for clause in clauses if _is_header(clause, CATALOG)]
    message_place = _one_place([_clause_place(clause) for clause in context])
    if default_zone:
        from .const import ZONES_BY_ID
        if ZONES_BY_ID.get(default_zone) and message_place is None:
            message_place = {"point": None, "zone": default_zone, "name": ""}
    dates = [moment for moment, explicit in (_clause_date(clause, received) for clause in context) if explicit]
    message_date = dates[0] if dates and len({d.date() if d else None for d in dates}) == 1 and dates[0] else None

    found: list[Observation] = []
    for clauses in parsed:
        headers = [c for c in clauses if _is_header(c, CATALOG)]
        sentence_place = _one_place([_clause_place(c) for c in headers])
        dated = [moment for moment, explicit in (_clause_date(c, received) for c in headers) if explicit]
        sentence_explicit = bool(dated)
        sentence_date = dated[0] if dated and len({d.date() if d else None for d in dated}) == 1 else None
        for clause in clauses:
            if _NON_OBSERVATION.search(clause):
                continue
            lowered = clause.lower()
            # Coordination is an assertion boundary. Only pure context on the
            # other side may supply metadata; a second animal's statement may not.
            local_headers = [part for part in _ASSERTION_JOIN.split(clause) if _is_header(part, CATALOG)]
            heading, colon, _body = clause.partition(":")
            if colon and _is_header(heading, CATALOG):
                local_headers.append(heading)
            local_place = _one_place([_clause_place(part) for part in local_headers])
            local_dates = [moment for moment, explicit in (_clause_date(part, received) for part in local_headers)
                           if explicit]

            def metadata(left, right):
                assertion = clause[left:right]
                own = _one_place([_clause_place(assertion), local_place])
                inherited = sentence_place if sentence_place is not None else message_place
                place = own if own is not None else inherited
                place = None if place is AMBIGUOUS else place
                moment, explicit = _clause_date(assertion, received)
                dates = ([moment] if explicit else []) + local_dates
                if dates:
                    observed = dates[0] if len({d.date() if d else None for d in dates}) == 1 else None
                else:
                    observed = sentence_date if sentence_explicit else message_date
                return place, observed

            for definition in CATALOG.values():
                if category and definition.category != category and not (
                        category == CATEGORY_RARE and definition.category in (CATEGORY_RARE, CATEGORY_BIRDS)):
                    continue
                subjects = SUBJECT_TERMS.get(definition.key, ())
                subject = next((term for term in subjects if term in lowered), "")
                if definition.key in PRESENCE_EVIDENCE:
                    terms = (subject,) if subject else ()
                else:
                    terms = definition.behavior_terms
                hits = [(match.start(), term) for term in terms for match in re.finditer(re.escape(term), lowered)]
                if not hits:
                    continue
                if subjects and definition.key not in PRESENCE_EVIDENCE:
                    # Require a subject-specific assertion. A nearby noun or
                    # a subject in an unrelated sentence cannot supply one.
                    wanted = _canonical_subjects(definition.key)
                    bound = []
                    for position, term in hits:
                        if any(noun in term for noun in subjects) or term in SELF_IDENTIFYING.get(definition.key, ()):
                            bound.append((position, term))
                            continue
                        animal = _bound_animal(lowered, position, position + len(term))
                        if animal is None:
                            left, right = _assertion_span(lowered, position, position + len(term))
                            place, _observed = metadata(left, right)
                            where = f"{lowered[left:right]} {(place or {}).get('name') or ''}"
                            prefix = lowered[left:position].strip(" :,-")
                            if (_is_header(prefix, CATALOG) and
                                    any(site in where for site in SITE_SUBJECTS.get(definition.key, ()))):
                                # Only a monitored colony can supply an unnamed
                                # animal, and no unexplained subject may precede it.
                                bound.append((position, term))
                        elif animal in wanted:
                            bound.append((position, term))
                    hits = bound
                    if not hits:
                        continue
                    subject = subject or next((term for term in subjects if term in whole), subjects[0])
                groups = {}
                for position, term in hits:
                    groups.setdefault(_assertion_span(clause, position, position + len(term)), []).append((position, term))
                for (left, right), local_hits in groups.items():
                    assertion = clause[left:right]
                    place, observed = metadata(left, right)
                    if definition.location_terms and not any(
                            t in assertion.lower() or (place and t in (place.get("name") or ""))
                            for t in definition.location_terms):
                        siblings = [other for other in CATALOG.values() if other.key != definition.key
                                    and other.behavior_terms == definition.behavior_terms and other.location_terms]
                        if any(any(t in assertion.lower() for t in other.location_terms) for other in siblings):
                            continue
                    negated = all(_negated(assertion, position - left) for position, _ in local_hits)
                    count = _subject_count(assertion, subject) if subject else None
                    point = (place or {}).get("point")
                    found.append(Observation(
                        phenomenon=definition.key, polarity=NEGATIVE if negated else POSITIVE, text=assertion,
                        behaviors=tuple(term for _, term in local_hits), subject=subject, count=count,
                        observed_at=observed,
                        latitude=point[0] if point else None, longitude=point[1] if point else None,
                        place=(place or {}).get("name") or "", zone_id=(place or {}).get("zone") or "",
                    ))
    return _resolve_siblings(found)


def _resolve_siblings(found: list[Observation]) -> list[Observation]:
    """Phenomena that share one vocabulary (the four bloom sites) are told apart by place.

    A located statement keeps only the siblings whose site is within the
    corroboration radius of it; an unlocated one keeps them all (and will
    corroborate nothing, being nowhere).
    """
    from .curation import CATALOG
    from .phenomena import LIVE_CORROBORATION_KM, WINDOWS_BY_KEY
    from .wildlife import haversine_km

    out = []
    for item in found:
        definition = CATALOG[item.phenomenon]
        siblings = [other for other in CATALOG.values() if other.key != item.phenomenon
                    and other.behavior_terms and other.behavior_terms == definition.behavior_terms
                    and not other.location_terms]
        window = WINDOWS_BY_KEY.get(item.phenomenon)
        point = report_point(item)
        if siblings and window is not None and point is not None and haversine_km(
                window.latitude, window.longitude, point[0], point[1]) > LIVE_CORROBORATION_KM:
            continue
        out.append(item)
    return out


def positive(observations: list[Observation]) -> list[Observation]:
    return [item for item in observations if item.polarity == POSITIVE]


def report_phenomena(report) -> tuple[str, ...]:
    """The phenomena a report's own statements name positively.

    Reports built by the normalizer carry them; a report built any other way
    (tests, an older cached object) is normalized here from its text, so no
    path falls back to whole-text keyword co-occurrence.
    """
    recorded = tuple(getattr(report, "phenomena", None) or ())
    key = getattr(report, "phenomenon_key", "") or ""
    if key and key not in recorded:
        # A parser's explicit assignment (operator feeds) stands with the rest.
        recorded = (*recorded, key)
    if recorded or getattr(report, "normalized", False):
        # Normalized reports are final, even when they name nothing.
        return recorded
    text = " ".join(str(getattr(report, name, "") or "") for name in ("snippet",))
    return tuple(dict.fromkeys(item.phenomenon for item in positive(
        observe(text, getattr(report, "observed_at", None) or getattr(report, "fetched", None),
                category=getattr(report, "category", None), default_zone=getattr(report, "zone_id", None),
                subject_hint=f"{getattr(report, 'headline', '')} {getattr(report, 'context', '')}"))))


# --- Phenomenon requirements, applied after normalization ------------------------

def admissible(report, definition, now: datetime, site: tuple[float, float] | None = None,
               radius_km: float | None = None) -> tuple[bool, str]:
    """Whether a normalized report may confirm this phenomenon here, now.

    One gate for every ingress path (email, hotline, operator feed): positive
    polarity, the phenomenon named in the report's own statements, a stated
    observation date that is neither in the future nor older than the
    phenomenon's evidence window, the minimum count written against the
    subject, and - when a site is given - a located report within the radius.
    """
    from .wildlife import haversine_km

    if getattr(report, "polarity", POSITIVE) != POSITIVE:
        return False, "negated"
    if definition.key not in report_phenomena(report):
        return False, "does not describe this phenomenon"
    if text_negates(report, definition.key):
        return False, "negated"
    observed = getattr(report, "observed_at", None)
    if observed is None:
        return False, "undated"
    if observed > now + timedelta(hours=1):
        return False, "dated in the future"
    if now - observed > timedelta(days=min(14, definition.evidence_days)):
        return False, "stale"
    if definition.min_count and (getattr(report, "count", None) or 0) < definition.min_count:
        return False, "count below the phenomenon's threshold"
    if site is not None and radius_km is not None:
        point = report_point(report)
        if point is None or haversine_km(site[0], site[1], point[0], point[1]) > radius_km:
            return False, "not at this site"
    return True, ""


def text_negates(report, key: str) -> bool:
    """Whether the report's own text only ever negates this phenomenon.

    A report can carry a phenomenon key from a parser (an operator feed) or a
    test without having gone through ``observe``. Its text is still read: if
    every statement about the phenomenon is negative ("No orcas today, but
    plenty of dolphins"), it confirms nothing. Text that says nothing about the
    phenomenon leaves the parser's key standing.
    """
    text = str(getattr(report, "snippet", "") or "")
    received = getattr(report, "observed_at", None) or getattr(report, "fetched", None)
    about = [item for item in observe(text, received, default_zone=getattr(report, "zone_id", None),
                                      subject_hint=str(getattr(report, "headline", "") or ""))
             if item.phenomenon == key]
    return bool(about) and all(item.polarity == NEGATIVE for item in about)


def report_point(report) -> tuple[float, float] | None:
    """Where a report is: its own validated coordinates, else its zone, else nowhere."""
    from .const import ZONES_BY_ID

    if getattr(report, "latitude", None) is not None and getattr(report, "longitude", None) is not None:
        return report.latitude, report.longitude
    zone = ZONES_BY_ID.get(getattr(report, "zone_id", "") or "")
    return (zone["latitude"], zone["longitude"]) if zone else None
