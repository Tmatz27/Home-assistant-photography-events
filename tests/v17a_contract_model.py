"""Test-only executable acceptance model; NEVER imported by integration runtime.

This is a bounded serialization/state example for the V17A design gate, not an
HA WebSocket implementation, intelligence engine, or proof of deployed privacy.
V17B must run the adversarial tests against its actual serializer and transports.
Only source-controlled reviewed public prose may pass the normal row boundary.
"""
import math
import re
from datetime import datetime, timedelta

VERSION = 'ha.v17.1'
MAX_ITEMS = 500
PUBLIC = {'synthetic_public': ('Synthetic public visitor destination', 0.0, 0.0)}
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


def serialize_row(row, now, current=False):
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
    if timestamp(out['starts_at']) > timestamp(out['ends_at']) or timestamp(out['data_as_of']) > now + timedelta(seconds=60):
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
    approved = PUBLIC.get(loc.get('key'))
    pair = (loc.get('latitude'),loc.get('longitude'))
    permitted = (loc.get('policy') == 'curated_public_site' and approved is not None
                 and all(finite(v) for v in pair) and pair == approved[1:])
    if permitted:
        out['location'] = dict(policy='curated_public_site',key=loc['key'],name=approved[0],latitude=pair[0],longitude=pair[1])
        out['drive_minutes'] = drive
    else:
        out['location'] = dict(WITHHELD)
        out.update(drive_minutes=None,drive_basis='withheld',title='Opportunity location withheld',
                   reason='Location withheld.',awaiting='Approved public destination required.',
                   detail='',ethics='',best_time_of_day='',safety_summary='Travel checks unavailable.',
                   blockers=['location withheld'],safety_notes=[],gear={k:[] if k in ('optional','skip') else '' for k in out['gear']},
                   safety_state='unknown',access_state='unknown',condition_state='unknown')
    current = (current and timestamp(out['valid_until']) > now
               and now - timestamp(out['data_as_of']) < timedelta(minutes=15))
    action = (current and permitted and out['eligibility'] and not out['held'] and not out['blockers']
              and out['presentation'] == 'cant_miss' and out['safety_state'] in ('safe','caution')
              and out['access_state'] == 'public' and out['condition_state'] == 'not_required'
              and timestamp(out['valid_until']) > now and timestamp(out['ends_at']) > now)
    out['event_id'] = out['occurrence_key']
    out['actionable'] = bool(action)
    out['row_state'] = 'held' if out['held'] or not current or not permitted else 'current'
    if not current or not permitted:
        out.update(eligibility=False,held=True,watching=False,presentation='held')
    if not current:
        out.update(safety_state='unknown',access_state='unknown',condition_state='unknown',
                   reason='Current assessment unavailable.',awaiting='A current Core assessment.',
                   safety_summary='Travel checks unavailable.',safety_notes=[],blockers=['current assessment unavailable'])
    return out


def project(payload, *, now, online=True, coverage='unverified', origin='normal', projection_version=VERSION):
    """coverage is a reviewed test witness, NOT an invented Core response field."""
    if projection_version != VERSION:
        raise InvalidContract('unsupported_projection')
    if not isinstance(payload, dict) or payload.get('api_version') != 'v1' or payload.get('schema_version') != '0008':
        raise InvalidContract('incompatible_api')
    if origin == 'shadow':
        # Do not even serialize previews into the normal card/cache boundary.
        return dict(projection_version=VERSION,view_state='shadow_only',assessment_state='not_assessed',
                    freshness='unknown',items=[],count=None,notifications_enabled=False)
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
    if stamp > now + timedelta(seconds=60) or (asof and asof > now + timedelta(seconds=60)):
        raise InvalidContract('future_timestamp')
    rows = payload.get('items')
    if not isinstance(rows,list) or len(rows) > MAX_ITEMS:
        raise InvalidContract('too_many_items')
    stale = now - stamp >= timedelta(minutes=15) or (asof is not None and now - asof >= timedelta(minutes=15))
    assessed = aid is not None and asof is not None
    if not online:
        view = 'offline_stale'
    elif coverage in ('unsupported','shadow'):
        view = 'unsupported' if coverage == 'unsupported' else 'shadow_only'
    elif not assessed:
        view = 'not_assessed'
    elif state != 'complete':
        view = state
    elif stale:
        view = 'offline_stale'
    elif coverage != 'verified':
        view = 'coverage_unknown'
    else:
        view = 'current' if rows else 'empty_assessed'
    current = view in ('current','empty_assessed')
    items = [serialize_row(r,now,current) for r in rows]
    keys = [r['occurrence_key'] for r in items]
    if len(set(keys)) != len(keys):
        raise InvalidContract('duplicate_identity')
    return dict(projection_version=VERSION,view_state=view,assessment_state=state if assessed else 'not_assessed',
                freshness='current' if current else 'stale' if stale or not online else 'unknown',
                generated_at=payload['generated_at'],data_as_of=payload['data_as_of'],items=items,
                count=len(items) if current else None,notifications_enabled=False)
