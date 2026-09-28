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
statement - or, only where the whole message leaves no ambiguity, from the
message (one subject, one place, one date). A number counts a subject only
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
# Explicitly older than a day and without a date: it cannot inherit today's.
_VAGUE_PAST = re.compile(r"\b(?:last week|earlier this week|recently|a few days ago|last month|previous(?:ly)?)\b",
                         re.IGNORECASE)
_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+)"


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


def _bound_animal(lowered: str, start: int, end: int) -> str | None:
    """The animal a phrase at [start, end) is written against: the nearest one
    before it in its clause, else the nearest after, else None."""
    mentions = animal_mentions(lowered)
    inside = [m for m in mentions if m[0] >= start and m[1] <= end]
    if inside:
        return inside[0][2]
    before = [m for m in mentions if m[1] <= start]
    if before:
        return before[-1][2]
    after = [m for m in mentions if m[0] >= end]
    return after[0][2] if after else None


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
    if animal_mentions(lowered) or any(term in lowered for item in catalog.values() for term in item.behavior_terms):
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
    from .field_reports import explicit_date

    if received is None:
        return None, False
    stated = explicit_date(clause, received)
    if stated is not None:
        return stated, True
    if _YESTERDAY.search(clause):
        return received - timedelta(days=1), True
    if _SAME_DAY.search(clause):
        return received, True
    if _VAGUE_PAST.search(clause):
        return None, True  # explicitly not today; never inherits
    return None, False


AMBIGUOUS = {"ambiguous": True}


def _clause_place(clause: str):
    """The one place a clause names, AMBIGUOUS when it names several zones, or None.

    "Avila and Monterey Bay today" names two regions: nothing in it may be
    placed at either. Two points inside one zone keep the zone but no point.
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
    point = next(iter(points)) if len(points) == 1 else None
    return {"point": point, "zone": zones[0] if zones else "", "name": names[0][0] if len(points) == 1 else ""}


def _one_place(places):
    """The single place among several clause places, AMBIGUOUS, or None."""
    real = [place for place in places if place]
    if any(place is AMBIGUOUS for place in real):
        return AMBIGUOUS
    zones = {place["zone"] for place in real}
    if len(zones) > 1:
        return AMBIGUOUS
    return real[0] if real else None


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
    animals_named = {terms for terms in SUBJECT_TERMS.values() if any(term in whole for term in terms)}
    context = [clause for clauses in statements(subject_hint) for clause in clauses]
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
        sentence_place = _one_place([_clause_place(c) for c in clauses])
        sentence_date, sentence_explicit = None, False
        for clause in clauses:
            moment, explicit = _clause_date(clause, received)
            if explicit:
                sentence_date, sentence_explicit = moment, True
                break
        for clause in clauses:
            lowered = clause.lower()
            clause_date, clause_explicit = _clause_date(clause, received)
            if clause_explicit:
                observed = clause_date
            elif sentence_explicit:
                observed = sentence_date
            else:
                observed = message_date
            own = _clause_place(clause)
            # A clause that names several regions is placed nowhere, and never
            # inherits a place from its sentence or the message.
            place = None if own is AMBIGUOUS else own or (
                None if sentence_place is AMBIGUOUS else sentence_place) or (
                None if message_place is AMBIGUOUS else message_place)
            for definition in CATALOG.values():
                if category and definition.category != category and not (
                        category == CATEGORY_RARE and definition.category in (CATEGORY_RARE, CATEGORY_BIRDS)):
                    continue
                subjects = SUBJECT_TERMS.get(definition.key, ())
                subject = next((term for term in subjects if term in lowered), "")
                if definition.key in PRESENCE_EVIDENCE:
                    hits = [(lowered.find(subject), subject)] if subject else []
                else:
                    hits = [(lowered.find(term), term) for term in definition.behavior_terms if term in lowered]
                if not hits:
                    continue
                if subjects and definition.key not in PRESENCE_EVIDENCE:
                    # Each behaviour phrase must be written against *this*
                    # animal: the nearest animal before it in the clause (else
                    # the nearest after). "Humpbacks passed Avila and dolphins
                    # were lunge feeding" is dolphins feeding; "Condors at
                    # Pinnacles and sea lions feeding" is sea lions feeding.
                    wanted = _canonical_subjects(definition.key)
                    bound = []
                    for position, term in hits:
                        if any(noun in term for noun in subjects) or term in SELF_IDENTIFYING.get(definition.key, ()):
                            bound.append((position, term))
                            continue
                        animal = _bound_animal(lowered, position, position + len(term))
                        if animal is None:
                            where = f"{lowered} {(place or {}).get('name') or ''}"
                            if any(site in where for site in SITE_SUBJECTS.get(definition.key, ())) or (
                                    len(animals_named) == 1 and subjects in animals_named):
                                # A monitored colony names its animal; one animal
                                # in the whole message is what an unnamed clause
                                # is about ("Humpbacks off Avila. Lunge feeding at 9.").
                                bound.append((position, term))
                        elif animal in wanted:
                            bound.append((position, term))
                    hits = bound
                    if not hits:
                        continue
                    subject = subject or next((term for term in subjects if term in whole), subjects[0])
                if definition.location_terms and not any(t in lowered or (place and t in (place.get("name") or ""))
                                                         for t in definition.location_terms):
                    # Sibling phenomena sharing vocabulary are told apart by place.
                    siblings = [other for other in CATALOG.values() if other.key != definition.key
                                and other.behavior_terms == definition.behavior_terms and other.location_terms]
                    if any(any(t in lowered for t in other.location_terms) for other in siblings):
                        continue
                negated = all(_negated(clause, position) for position, _ in hits)
                count_term = subject or ""
                # Only a number written against this subject's own noun.
                count = _subject_count(clause, count_term) if count_term else None
                point = (place or {}).get("point")
                found.append(Observation(
                    phenomenon=definition.key, polarity=NEGATIVE if negated else POSITIVE, text=clause,
                    behaviors=tuple(term for _, term in hits), subject=subject, count=count,
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
