"""Test-only executable acceptance model; NEVER imported by integration runtime.

This is a bounded serialization/state example for the V17A design gate, not an
HA WebSocket implementation, intelligence engine, or proof of deployed privacy.
V17B must run the adversarial tests against its actual serializer and transports.
Only source-controlled reviewed public prose may pass the normal row boundary.
"""
import math
import re
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

VERSION = 'ha.v17.1'
MAX_ITEMS = 500
TRANSPORT_MAX_AGE = timedelta(minutes=15)
ASSESSMENT_MAX_AGE = timedelta(hours=6)  # Provisional development cap, not ecological policy.
MAX_CLOCK_SKEW = timedelta(seconds=60)
POLICY_FIXTURES = Path(__file__).parent / 'fixtures/v17a/policy'
DESTINATION_POLICY = json.loads((POLICY_FIXTURES / 'core-destinations.json').read_text(encoding='utf-8'))
DESTINATION_REVIEW = json.loads((POLICY_FIXTURES / 'destination-review.json').read_text(encoding='utf-8'))
WITHHELD = dict(policy='withheld', key=None, name='Location withheld', latitude=None, longitude=None)
STRINGS = ('occurrence_key', 'phenomenon_key', 'title', 'category', 'presentation', 'evidence_state',
           'access_state', 'safety_state', 'condition_state', 'drive_basis', 'reason', 'awaiting',
           'ethics', 'safety_summary', 'best_time_of_day', 'detail', 'definition_key',
           'definition_version', 'definition_hash', 'engine_version')
LISTS = ('blockers', 'safety_notes')
GEAR_TEXT = ('take', 'start', 'support', 'technique', 'video', 'drone', 'drone_status')
PRESENTATIONS = {'cant_miss','watching','planner','held','bird_spectacle','bird_encounter'}


class InvalidContract(ValueError):
    """Machine-only error; no raw upstream data in its text."""


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError
        return result
    except (ValueError, AttributeError, TypeError):
        raise InvalidContract('invalid_timestamp') from None


def text(value, maximum=2048):
    if not isinstance(value, str) or len(value) > maximum:
        raise InvalidContract('invalid_text')
    return value


def text_list(value):
    if not isinstance(value, list) or len(value) > 32:
        raise InvalidContract('invalid_list')
    return [text(v, 512) for v in value]


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def destination_registry(policy, review):
    """Test witness for a reviewed Core-derived artifact; never authorize drift.

    The independent review pins the artifact digest, Core reference and revision.
    Loading a changed artifact does not automatically renew that review.
    """
    if not isinstance(policy, dict) or not isinstance(review, dict):
        return {}, 'unverified'
    try:
        digest = hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
        if (policy.get('authority') != 'core_curated_definitions'
                or policy.get('synthetic') is not True or review.get('synthetic') is not True
                or review.get('reviewed') is not True
                or policy.get('format_version') != 'v17a.destinations.1'
                or policy.get('core_reference_commit') != review.get('core_reference_commit')
                or policy.get('policy_revision') != review.get('policy_revision')
                or digest != review.get('content_sha256')):
            return {}, 'mismatch'
        result = {}
        for destination in policy['destinations']:
            key = text(destination['key'],256)
            pair = destination['latitude'],destination['longitude']
            if (not key or key in result or destination['policy'] != 'curated_public_site'
                    or not all(finite(v) for v in pair) or not -90 <= pair[0] <= 90 or not -180 <= pair[1] <= 180):
                return {}, 'mismatch'
            definitions = {(text(d['key'],256),text(d['version'],256),text(d['hash'],64))
                           for d in destination['definitions']}
            if not definitions or any(not re.fullmatch('[0-9a-f]{64}',d[2]) for d in definitions):
                return {}, 'mismatch'
            result[key] = dict(name=text(destination['name'],256),pair=pair,definitions=definitions)
        return result, 'verified'
    except (KeyError,TypeError,ValueError):
        return {}, 'mismatch'


def serialize_row(row, now, current=False, *, destinations):
    if not isinstance(row, dict):
        raise InvalidContract('invalid_row')
    out = {key: text(row.get(key)) for key in STRINGS}
    for key in ('occurrence_key','phenomenon_key','title'):
        text(out[key], 256)
    for key in ('occurrence_key','phenomenon_key'):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', out[key]):
            raise InvalidContract('invalid_identity')
    if out['presentation'] not in PRESENTATIONS or out['category'] not in {'mammals','birds','insects'}:
        raise InvalidContract('unsupported_enum')
    if out['safety_state'] not in {'safe','caution','unsafe','unknown'} or out['condition_state'] not in {'not_required','unknown'}:
        raise InvalidContract('unsupported_enum')
    if not re.fullmatch('[0-9a-f]{64}', out['definition_hash']):
        raise InvalidContract('invalid_provenance')
    for key in ('eligibility','held','watching'):
        if type(row.get(key)) is not bool:
            raise InvalidContract('invalid_boolean')
        out[key] = row[key]
    for key in ('significance','confidence','urgency'):
        if type(row.get(key)) is not int or not 0 <= row[key] <= 100:
            raise InvalidContract('invalid_score')
        out[key] = row[key]
    for key in ('starts_at','ends_at','data_as_of','valid_until'):
        timestamp(row.get(key))
        out[key] = row[key]
    if timestamp(out['starts_at']) > timestamp(out['ends_at']) or timestamp(out['data_as_of']) > now + MAX_CLOCK_SKEW:
        raise InvalidContract('invalid_time_order')
    for key in LISTS:
        out[key] = text_list(row.get(key))
    gear = row.get('gear')
    if not isinstance(gear, dict):
        raise InvalidContract('invalid_gear')
    out['gear'] = {k:text(gear.get(k,''),512) for k in GEAR_TEXT}
    out['gear'].update({k:text_list(gear.get(k,[])) for k in ('optional','skip')})
    bird = row.get('bird_classification')
    if bird not in (None,'spectacle','encounter'):
        raise InvalidContract('unsupported_enum')
    out['bird_classification'] = bird
    drive = row.get('drive_minutes')
    if drive is not None and (not finite(drive) or drive < 0):
        raise InvalidContract('invalid_drive')
    loc = row.get('location')
    if not isinstance(loc, dict):
        raise InvalidContract('invalid_location')
    approved = destinations.get(loc.get('key'))
    pair = (loc.get('latitude'),loc.get('longitude'))
    provenance = out['definition_key'],out['definition_version'],out['definition_hash']
    permitted = (loc.get('policy') == 'curated_public_site' and approved is not None
                 and all(finite(v) for v in pair) and pair == approved['pair']
                 and provenance in approved['definitions'])
    if permitted:
        out['location'] = dict(policy='curated_public_site',key=loc['key'],name=approved['name'],latitude=pair[0],longitude=pair[1])
        out['drive_minutes'] = drive
    else:
        out['location'] = dict(WITHHELD)
        out.update(drive_minutes=None,drive_basis='withheld',title='Opportunity location withheld',
                   reason='Location withheld.',awaiting='Approved public destination required.',
                   detail='',ethics='',best_time_of_day='',safety_summary='Travel checks unavailable.',
                   blockers=['location withheld'],safety_notes=[],gear={k:[] if k in ('optional','skip') else '' for k in out['gear']},
                   safety_state='unknown',access_state='unknown',condition_state='unknown')
    # Core owns per-phenomenon/evidence deadlines. Do not impose the HA
    # transport interval on this row's data_as_of or on unrelated rows.
    row_expired = timestamp(out['valid_until']) <= now
    current = current and not row_expired
    action = (current and permitted and out['eligibility'] and not out['held'] and not out['blockers']
              and out['presentation'] == 'cant_miss' and out['safety_state'] in ('safe','caution')
              and out['access_state'] == 'public' and out['condition_state'] == 'not_required'
              and timestamp(out['valid_until']) > now and timestamp(out['ends_at']) > now)
    out['event_id'] = out['occurrence_key']
    out['actionable'] = bool(action)
    out['row_freshness'] = 'stale' if row_expired else 'current'
    out['location_policy_state'] = 'verified' if permitted else 'withheld'
    out['row_state'] = 'stale' if row_expired else 'held' if out['held'] or not current or not permitted else 'current'
    if not current or not permitted:
        out.update(eligibility=False,held=True,watching=False,presentation='held')
    if not current:
        out.update(safety_state='unknown',access_state='unknown',condition_state='unknown',
                   reason='Current assessment unavailable.',awaiting='A current Core assessment.',
                   safety_summary='Travel checks unavailable.',safety_notes=[],blockers=['current assessment unavailable'])
    return out


def project(payload, *, now, fetched_at, saved_at=None, online=True, availability=None,
            cached_context=False, coverage='unverified', origin='normal', projection_version=VERSION,
            destination_policy=DESTINATION_POLICY, destination_review=DESTINATION_REVIEW):
    """Explicit HA retrieval/cache timestamps; never inferred from Core or now.

    coverage, destination review and cached_context are trusted backend test
    witnesses, not invented Core fields or browser-authorized assertions.
    """
    if projection_version != VERSION:
        raise InvalidContract('unsupported_projection')
    if coverage not in {'verified','unverified','unsupported','shadow'} or origin not in {'normal','shadow'}:
        raise InvalidContract('invalid_scope')
    availability = availability or ('online' if online else 'offline')
    error_codes = {'online':None,'offline':'core_unavailable','auth_required':'authentication_failed',
                   'connection_required':'connection_required','incompatible':'unsupported_api_version',
                   'invalid_response':'invalid_core_response'}
    if availability not in error_codes or type(cached_context) is not bool:
        raise InvalidContract('invalid_availability')
    fetch = timestamp(fetched_at) if fetched_at is not None else None
    if fetch and fetch > now + MAX_CLOCK_SKEW:
        raise InvalidContract('future_timestamp')
    if saved_at is not None:
        timestamp(saved_at)  # Cache time is provenance only; never used for expiry.
    transport_freshness = 'unknown' if fetch is None else 'stale' if now - fetch >= TRANSPORT_MAX_AGE else 'current'
    result = dict(projection_version=VERSION,availability=availability,coverage=coverage,
                  error_code=error_codes[availability],assessment_state='not_assessed',
                  transport_freshness=transport_freshness,assessment_freshness='unknown',freshness='unknown',
                  generated_at=None,data_as_of=None,fetched_at=fetched_at,saved_at=saved_at,
                  items=[],count=None,notifications_enabled=False)
    # Connection failures take precedence, including failures on a shadow route.
    # Only explicitly validated normal cached content may be retained offline.
    retained_offline = (availability == 'offline' and cached_context and fetch is not None
                        and origin == 'normal' and isinstance(payload,dict))
    if (availability != 'online' and not retained_offline) or (availability == 'online' and fetch is None):
        result.update(view_state='unavailable')
        if availability == 'online':
            result.update(availability='invalid_response',error_code='invalid_core_response')
        return result
    if not isinstance(payload, dict) or payload.get('api_version') != 'v1' or payload.get('schema_version') != '0008':
        raise InvalidContract('incompatible_api')
    if origin == 'shadow':
        # Do not even serialize previews into the normal card/cache boundary.
        result.update(view_state='offline_stale' if retained_offline else 'shadow_only')
        return result
    stamp = timestamp(payload.get('generated_at'))
    asof = timestamp(payload['data_as_of']) if payload.get('data_as_of') is not None else None
    aid = payload.get('assessment_id')
    if aid is not None and (type(aid) is not int or aid <= 0):
        raise InvalidContract('invalid_generation')
    state = payload.get('assessment_state')
    if state not in ('complete','incomplete','degraded'):
        raise InvalidContract('invalid_assessment')
    for key in ('missing_required_sources','degraded_sources'):
        values = payload.get(key)
        if not isinstance(values,list) or len(values) > 64 or any(not isinstance(v,str) or len(v)>256 for v in values):
            raise InvalidContract('invalid_sources')
    if state == 'complete' and (payload['missing_required_sources'] or payload['degraded_sources']):
        raise InvalidContract('contradictory_assessment')
    if stamp > now + MAX_CLOCK_SKEW or (asof and asof > now + MAX_CLOCK_SKEW):
        raise InvalidContract('future_timestamp')
    rows = payload.get('items')
    if not isinstance(rows,list) or len(rows) > MAX_ITEMS:
        raise InvalidContract('too_many_items')
    assessed = aid is not None and asof is not None
    assessment_freshness = 'unknown' if not assessed else 'stale' if now - asof >= ASSESSMENT_MAX_AGE else 'current'
    stale = transport_freshness == 'stale' or assessment_freshness == 'stale'
    fresh = transport_freshness == 'current' and assessment_freshness == 'current'
    destinations, policy_state = destination_registry(destination_policy,destination_review)
    # Row expiry is independent. One expired row cannot expire valid siblings.
    items = [serialize_row(r,now,availability == 'online' and state == 'complete' and fresh and coverage == 'verified',
                           destinations=destinations) for r in rows]
    keys = [r['occurrence_key'] for r in items]
    if len(set(keys)) != len(keys):
        raise InvalidContract('duplicate_identity')
    all_rows_expired = bool(items) and all(r['row_freshness'] == 'stale' for r in items)
    if retained_offline:
        view = 'offline_stale'
    elif coverage in ('unsupported','shadow'):
        view = 'unsupported' if coverage == 'unsupported' else 'shadow_only'
    elif not assessed:
        view = 'not_assessed'
    elif state != 'complete':
        view = state
    elif stale or all_rows_expired:
        view = 'stale'
    elif not fresh:
        view = 'unavailable'  # No successful HA retrieval stamp; never invent one.
    elif coverage != 'verified':
        view = 'coverage_unknown'
    else:
        view = 'current' if rows else 'empty_assessed'
    current = view in ('current','empty_assessed')
    result.update(view_state=view,assessment_state=state,assessment_id=aid,
                  missing_required_sources=list(payload['missing_required_sources']),
                  degraded_sources=list(payload['degraded_sources']),
                  assessment_freshness=assessment_freshness,
                  freshness='stale' if stale or all_rows_expired or retained_offline else 'current' if fresh else 'unknown',
                  generated_at=payload['generated_at'],data_as_of=payload['data_as_of'],items=items,
                  destination_policy_state=policy_state,count=len(items) if current else None)
    return result
