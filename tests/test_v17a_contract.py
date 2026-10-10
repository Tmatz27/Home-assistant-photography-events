"""Portable V17A contract examples and adversarial tests; no runtime changes."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v17a_contract_model import InvalidContract, DESTINATION_POLICY, DESTINATION_REVIEW, WITHHELD, project, TRANSPORT_MAX_AGE, ASSESSMENT_MAX_AGE

FIXTURES = Path(__file__).parent / 'fixtures' / 'v17a'
NOW = datetime(2026,10,9,20,tzinfo=timezone.utc)
FETCHED_AT = NOW.isoformat()


def fixture(name):
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'))


class V17AContractTests(unittest.TestCase):
    def project(self, name='approved_public', **kwargs):
        return project(fixture(name),now=NOW,fetched_at=FETCHED_AT,coverage='verified',**kwargs)

    def test_complete_current_empty_is_scoped_assessment(self):
        result = self.project('complete_empty')
        self.assertEqual((result['view_state'],result['count']),('empty_assessed',0))

    def test_empty_without_coverage_witness_is_unknown(self):
        result = project(fixture('complete_empty'),now=NOW,fetched_at=FETCHED_AT)
        self.assertEqual(result['view_state'],'coverage_unknown')
        self.assertIsNone(result['count'])

    def test_incomplete_and_never_assessed_are_distinct(self):
        for name, expected in [('incomplete','incomplete'),('never_assessed','not_assessed')]:
            with self.subTest(name=name):
                result = self.project(name)
                self.assertEqual(result['view_state'],expected)
                self.assertIsNone(result['count'])

    def test_degraded_is_not_a_current_empty_assessment(self):
        self.assertEqual(self.project('degraded')['view_state'],'degraded')

    def test_stale_response_stays_nonactionable(self):
        result = self.project('stale')
        self.assertEqual(result['freshness'],'stale')
        self.assertFalse(result['items'][0]['actionable'])

    def test_successful_http_timestamp_cannot_renew_old_assessment(self):
        p = fixture('approved_public')
        p['data_as_of'] = '2026-10-08T19:55:00Z'
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'stale')
        self.assertEqual(result['assessment_freshness'],'stale')
        self.assertEqual(result['transport_freshness'],'current')
        self.assertFalse(result['items'][0]['actionable'])

    def test_offline_cache_cannot_act(self):
        result = self.project(online=False,cached_context=True)
        self.assertEqual(result['view_state'],'offline_stale')
        self.assertFalse(result['items'][0]['eligibility'])
        self.assertTrue(result['items'][0]['held'])

    def test_shadow_preview_never_enters_normal_frontend(self):
        p = fixture('shadow_patterns')
        self.assertTrue(p['preview_opportunities'][0]['held'])
        self.assertFalse(p['preview_opportunities'][0]['eligibility'])
        # Even a contradictory future shadow preview cannot become actionable.
        p['preview_opportunities'][0].update(eligibility=True,held=False,presentation='cant_miss')
        result = project(p,now=NOW,fetched_at=FETCHED_AT,origin='shadow')
        self.assertEqual(result['view_state'],'shadow_only')
        self.assertEqual(result['items'],[])
        self.assertFalse(result['notifications_enabled'])

    def test_unsupported_birds_is_not_empty_birds(self):
        result = project(fixture('complete_empty'),now=NOW,fetched_at=FETCHED_AT,coverage='unsupported')
        self.assertEqual(result['view_state'],'unsupported')
        self.assertIsNone(result['count'])

    def test_approved_curated_destination_retains_exact_coordinates(self):
        row = self.project()['items'][0]
        self.assertEqual((row['location']['latitude'],row['location']['longitude']),(DESTINATION_POLICY['destinations'][0]['latitude'], DESTINATION_POLICY['destinations'][0]['longitude']))
        self.assertTrue(row['actionable'])
        self.assertFalse(self.project()['notifications_enabled'],'V17A never enables delivery')

    def test_withheld_has_no_location_or_travel_hint(self):
        row = self.project('withheld')['items'][0]
        self.assertEqual(row['location'],WITHHELD)
        self.assertIsNone(row['drive_minutes'])
        self.assertEqual(row['detail'],'')
        self.assertFalse(row['actionable'])

    def test_withheld_prose_and_recognized_nested_fields_cannot_leak(self):
        p = fixture('withheld')
        row = p['items'][0]
        for key in ('title','detail','reason','awaiting','ethics','best_time_of_day','safety_summary','drive_basis'):
            row[key] = 'SENSITIVE_SENTINEL 35.123456 -120.654321'
        row['location'].update(latitude=35.123456,longitude=-120.654321,name='SENSITIVE_SENTINEL',key='SENSITIVE_SENTINEL')
        row['blockers'] = row['safety_notes'] = ['SENSITIVE_SENTINEL']
        row['gear']['take'] = 'SENSITIVE_SENTINEL'
        row['gear']['optional'] = ['SENSITIVE_SENTINEL']
        encoded = json.dumps(project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified'))
        for value in ('SENSITIVE_SENTINEL','35.123456','-120.654321'):
            self.assertNotIn(value,encoded)

    def test_unapproved_or_altered_or_partial_coordinates_are_withheld(self):
        for delta in ({'key':'auto-destination'},{'latitude':0.01},{'longitude':None},{'policy':'unknown'}):
            with self.subTest(delta=delta):
                p = fixture('approved_public')
                p['items'][0]['location'].update(delta)
                self.assertEqual(project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['location'],WITHHELD)

    def test_nonfinite_and_boolean_coordinates_are_withheld(self):
        for value in (float('nan'),float('inf'),True):
            p = fixture('approved_public')
            p['items'][0]['location']['latitude'] = value
            self.assertEqual(project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['location'],WITHHELD)

    def test_unknown_safety_access_cannot_act_even_with_eligibility_flag(self):
        p = fixture('unknown_safety_access')
        p['items'][0].update(eligibility=True,held=False,presentation='cant_miss',blockers=[])
        self.assertFalse(project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['actionable'])

    def test_api_schema_and_projection_incompatibility_fail_closed(self):
        for key,value in [('api_version','v2'),('schema_version','9999')]:
            p = fixture('complete_empty')
            p[key] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW,fetched_at=FETCHED_AT)
        with self.assertRaises(InvalidContract):
            self.project(projection_version='ha.v99')

    def test_credentials_and_unknown_nested_evidence_are_not_serialized(self):
        p = fixture('approved_public')
        sentinel = dict(token='CREDENTIAL_SENTINEL',raw_geometry=[35.123456,-120.654321],
                        centroid='CENTROID_SENTINEL',observer='OBSERVER_SENTINEL',observation_id='RAW_ID_SENTINEL',description='DESCRIPTION_SENTINEL')
        p['connection'] = sentinel
        row = p['items'][0]
        row.update(raw_evidence=sentinel,source_url='https://secret.invalid/?token=CREDENTIAL_SENTINEL',pattern_episode_id=876543)
        row['location']['raw'] = sentinel
        row['gear']['metadata'] = [sentinel]
        encoded = json.dumps(project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified'))
        for value in ('SENTINEL','35.123456','-120.654321','876543','secret.invalid','raw_evidence','connection'):
            self.assertNotIn(value,encoded)

    def test_identity_survives_score_generation_and_viewpoint_changes(self):
        p = fixture('approved_public')
        before = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['event_id']
        p.update(assessment_id=18)
        p['items'][0].update(assessment_id=18,confidence=50,title='Updated synthetic title',drive_minutes=80)
        p['items'][0]['location']['latitude'] = 0.01
        after = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['event_id']
        self.assertEqual(before,after)

    def test_annual_recurrence_has_separate_identity(self):
        p = fixture('approved_public')
        first = self.project()['items'][0]['event_id']
        p['items'][0]['occurrence_key'] = 'synthetic-spectacle-2027'
        self.assertNotEqual(first,project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]['event_id'])
        # A single Core-defined season crosses New Year without becoming a
        # new occurrence. The next annual season is a genuinely separate window.
        def published(key, start, end, at, generation):
            snapshot = fixture('approved_public')
            stamp = at.isoformat()
            snapshot.update(assessment_id=generation,generated_at=stamp,data_as_of=stamp)
            snapshot['items'][0].update(occurrence_key=key,assessment_id=generation,
                                       starts_at=start,ends_at=end,data_as_of=stamp,
                                       valid_until=(at+timedelta(hours=1)).isoformat())
            return project(snapshot,now=at,fetched_at=stamp,coverage='verified')['items'][0]

        season = 'synthetic-spectacle-winter-2026'
        before = published(season,'2026-12-31T23:30:00Z','2027-01-02T20:00:00Z',
                           datetime(2026,12,31,23,45,tzinfo=timezone.utc),17)
        after = published(season,'2026-12-31T23:30:00Z','2027-01-02T20:00:00Z',
                          datetime(2027,1,1,0,15,tzinfo=timezone.utc),18)
        recurrence = published('synthetic-spectacle-winter-2027','2027-12-31T23:30:00Z','2028-01-02T20:00:00Z',
                               datetime(2027,12,31,23,45,tzinfo=timezone.utc),19)
        self.assertEqual(before['event_id'],after['event_id'])
        self.assertNotEqual(after['event_id'],recurrence['event_id'])
        self.assertEqual(before['phenomenon_key'],recurrence['phenomenon_key'])
        self.assertLess(before['ends_at'],recurrence['starts_at'])
        legacy_choice_scope = {before['event_id']:'skip'}
        self.assertEqual(legacy_choice_scope.get(after['event_id']),'skip')
        self.assertIsNone(legacy_choice_scope.get(recurrence['event_id']))

    def test_duplicate_or_empty_identity_rejects_entire_snapshot(self):
        p = fixture('approved_public')
        p['items'].append(copy.deepcopy(p['items'][0]))
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        p = fixture('approved_public')
        p['items'][0]['occurrence_key'] = ''
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,fetched_at=FETCHED_AT)

    def test_expiry_ages_without_new_fetch_or_push(self):
        result = project(fixture('approved_public'),now=NOW+timedelta(hours=2),fetched_at=FETCHED_AT,coverage='verified')
        self.assertFalse(result['items'][0]['actionable'])
        self.assertEqual(result['transport_freshness'],'stale')
        self.assertEqual(result['assessment_freshness'],'current')
        self.assertEqual(result['items'][0]['row_freshness'],'stale')
        self.assertEqual(result['fetched_at'],FETCHED_AT)

    def test_naive_future_and_reversed_timestamps_reject(self):
        for key,value in [('data_as_of','2026-10-09T20:00:00'),('generated_at','2026-10-10T20:00:00Z')]:
            p = fixture('approved_public')
            p[key] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW,fetched_at=FETCHED_AT)
        p = fixture('approved_public')
        p['items'][0]['starts_at'] = '2027-10-09T20:00:00Z'
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,fetched_at=FETCHED_AT)

    def test_limits_and_invalid_nested_types_reject(self):
        for field,value in [('gear',{'optional':[{'token':'secret'}]}),('confidence',True),('eligibility','true'),('detail','x'*2049),('drive_minutes',float('inf'))]:
            p = fixture('approved_public')
            p['items'][0][field] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW,fetched_at=FETCHED_AT)
        p = fixture('approved_public')
        p['items'] *= 501
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,fetched_at=FETCHED_AT)

    def test_contradictory_complete_assessment_is_not_empty_success(self):
        p = fixture('complete_empty')
        p['missing_required_sources'] = ['nws_alerts']
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')

    def test_projection_does_not_mutate_cached_core_input(self):
        p = fixture('approved_public')
        saved = copy.deepcopy(p)
        project(p,now=NOW,fetched_at=FETCHED_AT,online=False,cached_context=True)
        self.assertEqual(saved,p)

    def test_expired_item_is_held_inside_an_otherwise_current_snapshot(self):
        p = fixture('approved_public')
        p['items'][0]['valid_until'] = '2026-10-09T19:59:00Z'
        row = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]
        self.assertTrue(row['held'])
        self.assertFalse(row['eligibility'])
        self.assertEqual(row['safety_state'],'unknown')

    def test_watching_presentation_is_preserved_without_promotion(self):
        p = fixture('approved_public')
        p['items'][0].update(presentation='watching',watching=True,eligibility=False)
        row = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')['items'][0]
        self.assertEqual(row['presentation'],'watching')
        self.assertFalse(row['actionable'])

    def test_normal_fixtures_are_accepted_by_existing_core_client(self):
        # Exercise the existing parser as well as the test-only acceptance model.
        # This does not assert that the existing parser meets the V17B leak gates.
        import test_integration
        test_integration._load_package()
        from photography_events.core_client import CoreAssessment, CoreVersionError
        for name in ('complete_empty','never_assessed','incomplete','degraded','approved_public',
                     'stale','withheld','unknown_safety_access'):
            with self.subTest(name=name):
                payload = fixture(name)
                result = CoreAssessment.parse(payload)
                self.assertEqual(len(result.items),len(payload['items']))
                for parsed, raw in zip(result.items,payload['items']):
                    self.assertEqual(parsed.occurrence_key,raw['occurrence_key'])
        with self.assertRaises(CoreVersionError):
            CoreAssessment.parse(fixture('incompatible'))

    def test_thirty_minute_assessment_and_row_remain_current_after_recent_fetch(self):
        p = fixture('approved_public')
        old = (NOW-timedelta(minutes=30)).isoformat()
        p.update(generated_at=old,data_as_of=old)
        p['items'][0]['data_as_of'] = old
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'current')
        self.assertEqual(result['transport_freshness'],'current')
        self.assertEqual(result['assessment_freshness'],'current')
        self.assertTrue(result['items'][0]['actionable'])
        self.assertEqual(result['generated_at'],old)
        self.assertEqual(result['data_as_of'],old)
        self.assertFalse(result['notifications_enabled'])

    def test_transport_boundary_uses_actual_fetch_not_generated_or_saved_time(self):
        p = fixture('approved_public')
        p['generated_at'] = (NOW-timedelta(hours=2)).isoformat()
        p['data_as_of'] = (NOW-timedelta(hours=3)).isoformat()
        for age,expected in [(TRANSPORT_MAX_AGE-timedelta(microseconds=1),'current'),
                             (TRANSPORT_MAX_AGE,'stale'),
                             (TRANSPORT_MAX_AGE+timedelta(microseconds=1),'stale')]:
            with self.subTest(age=age):
                result = project(p,now=NOW,fetched_at=(NOW-age).isoformat(),saved_at=FETCHED_AT,coverage='verified')
                self.assertEqual(result['view_state'],expected)
                self.assertEqual(result['transport_freshness'],expected)
                self.assertEqual(result['assessment_freshness'],'current')
                self.assertEqual(result['data_as_of'],p['data_as_of'])
                self.assertEqual(result['items'][0]['row_freshness'],'current')
                self.assertEqual(result['items'][0]['actionable'],expected == 'current')

    def test_assessment_boundary_is_exactly_six_hours_with_fresh_transport(self):
        for age,expected in [(ASSESSMENT_MAX_AGE-timedelta(microseconds=1),'current'),
                             (ASSESSMENT_MAX_AGE,'stale'),
                             (ASSESSMENT_MAX_AGE+timedelta(microseconds=1),'stale')]:
            with self.subTest(age=age):
                p = fixture('approved_public')
                p['data_as_of'] = (NOW-age).isoformat()
                result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
                self.assertEqual(result['view_state'],expected)
                self.assertEqual(result['assessment_freshness'],expected)
                self.assertEqual(result['transport_freshness'],'current')
                self.assertEqual(result['items'][0]['row_freshness'],'current')
                self.assertEqual(result['items'][0]['actionable'],expected == 'current')

    def test_fresh_http_seven_hour_assessment_is_online_stale(self):
        p = fixture('approved_public')
        p['data_as_of'] = (NOW-timedelta(hours=7)).isoformat()
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual((result['availability'],result['view_state']),('online','stale'))
        self.assertIsNone(result['error_code'])
        self.assertFalse(result['items'][0]['actionable'])

    def test_row_deadline_boundary_is_independent_of_a_new_fetch(self):
        p = fixture('approved_public')
        deadline = NOW+timedelta(hours=1)
        for at,expected in [(deadline-timedelta(microseconds=1),'current'),
                            (deadline,'stale'),(deadline+timedelta(microseconds=1),'stale')]:
            with self.subTest(at=at):
                result = project(p,now=at,fetched_at=at.isoformat(),coverage='verified')
                self.assertEqual(result['transport_freshness'],'current')
                self.assertEqual(result['assessment_freshness'],'current')
                self.assertEqual(result['items'][0]['row_freshness'],expected)
                self.assertEqual(result['items'][0]['row_state'],expected)
                self.assertEqual(result['view_state'],expected)
                self.assertEqual(result['items'][0]['valid_until'],p['items'][0]['valid_until'])
                self.assertEqual(result['items'][0]['actionable'],expected == 'current')

    def test_one_expired_row_does_not_expire_valid_sibling(self):
        p = fixture('approved_public')
        expired = copy.deepcopy(p['items'][0])
        expired.update(occurrence_key='synthetic-expired-2026',valid_until=FETCHED_AT)
        p['items'].insert(0,expired)
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'current')
        self.assertEqual(result['freshness'],'current')
        self.assertEqual(result['items'][0]['row_state'],'stale')
        self.assertFalse(result['items'][0]['actionable'])
        self.assertTrue(result['items'][0]['held'])
        self.assertEqual(result['items'][1]['row_state'],'current')
        self.assertTrue(result['items'][1]['actionable'])

    def test_empty_assessment_requires_scope_and_its_own_freshness(self):
        p = fixture('complete_empty')
        p['data_as_of'] = (NOW-timedelta(minutes=30)).isoformat()
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'empty_assessed')
        self.assertEqual(result['count'],0)
        p['data_as_of'] = (NOW-ASSESSMENT_MAX_AGE).isoformat()
        result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'stale')
        self.assertIsNone(result['count'])

    def test_incomplete_unknown_coverage_preserves_all_orthogonal_problems(self):
        p = fixture('incomplete')
        p['data_as_of'] = (NOW-timedelta(hours=7)).isoformat()
        result = project(p,now=NOW,fetched_at=FETCHED_AT)
        self.assertEqual(result['view_state'],'incomplete')
        self.assertEqual(result['assessment_state'],'incomplete')
        self.assertEqual(result['missing_required_sources'],['nws_alerts'])
        self.assertEqual(result['coverage'],'unverified')
        self.assertEqual(result['assessment_freshness'],'stale')
        self.assertEqual(result['transport_freshness'],'current')

    def test_missing_generation_is_distinct_from_missing_coverage(self):
        missing = project(fixture('never_assessed'),now=NOW,fetched_at=FETCHED_AT)
        unverified = project(fixture('complete_empty'),now=NOW,fetched_at=FETCHED_AT)
        self.assertEqual(missing['view_state'],'not_assessed')
        self.assertEqual(missing['assessment_state'],'incomplete')
        self.assertIsNone(missing['assessment_id'])
        self.assertEqual(missing['assessment_freshness'],'unknown')
        self.assertEqual(unverified['view_state'],'coverage_unknown')
        self.assertEqual(unverified['assessment_state'],'complete')
        self.assertEqual(unverified['assessment_freshness'],'current')
        self.assertEqual(unverified['coverage'],'unverified')
        self.assertIsNone(unverified['count'])

    def test_connection_failures_hide_rich_data_before_scope_and_shadow(self):
        for availability,code in [('auth_required','authentication_failed'),('incompatible','unsupported_api_version'),
                                  ('invalid_response','invalid_core_response'),('connection_required','connection_required')]:
            with self.subTest(availability=availability):
                result = project(fixture('shadow_patterns'),now=NOW,fetched_at=FETCHED_AT,
                                 availability=availability,cached_context=True,coverage='unsupported',origin='shadow')
                self.assertEqual(result['view_state'],'unavailable')
                self.assertEqual(result['availability'],availability)
                self.assertEqual(result['error_code'],code)
                self.assertEqual(result['items'],[])

    def test_offline_without_validated_cache_is_unavailable(self):
        for payload,fetch in [(None,None),(fixture('approved_public'),FETCHED_AT)]:
            result = project(payload,now=NOW,fetched_at=fetch,online=False)
            self.assertEqual(result['view_state'],'unavailable')
            self.assertEqual(result['items'],[])
            self.assertEqual(result['error_code'],'core_unavailable')

    def test_precedence_matches_contract_including_competing_states(self):
        cases = [
            ('shadow_patterns',dict(origin='shadow',coverage='unsupported'),'shadow_only'),
            ('never_assessed',dict(coverage='unsupported'),'unsupported'),
            ('never_assessed',dict(coverage='unverified'),'not_assessed'),
            ('incomplete',dict(coverage='unverified'),'incomplete'),
            ('degraded',dict(coverage='unverified'),'degraded'),
            ('complete_empty',dict(coverage='unverified'),'coverage_unknown'),
            ('complete_empty',dict(coverage='verified'),'empty_assessed'),
            ('approved_public',dict(coverage='verified'),'current'),
            ('incomplete',dict(coverage='unsupported'),'unsupported'),
            ('approved_public',dict(online=False,cached_context=True,coverage='unsupported'),'offline_stale'),
        ]
        for name,kwargs,expected in cases:
            with self.subTest(name=name,kwargs=kwargs):
                result = project(fixture(name),now=NOW,fetched_at=FETCHED_AT,**kwargs)
                self.assertEqual(result['view_state'],expected)
                self.assertEqual(result['coverage'],kwargs.get('coverage','unverified'))
                self.assertFalse(result['notifications_enabled'])
                if expected != 'current':
                    self.assertTrue(all(not r['actionable'] for r in result['items']))
        p = fixture('complete_empty')
        p['data_as_of'] = (NOW-timedelta(hours=7)).isoformat()
        self.assertEqual(project(p,now=NOW,fetched_at=FETCHED_AT)['view_state'],'stale')

    def test_fetch_renews_only_transport_and_cache_reload_cannot_renew_assessment(self):
        p = fixture('approved_public')
        saved = copy.deepcopy(p)
        old_fetch = (NOW-TRANSPORT_MAX_AGE).isoformat()
        cached = project(p,now=NOW,fetched_at=old_fetch,saved_at=FETCHED_AT,coverage='verified')
        refreshed = project(p,now=NOW,fetched_at=FETCHED_AT,saved_at=FETCHED_AT,coverage='verified')
        self.assertEqual(cached['view_state'],'stale')
        self.assertEqual(refreshed['view_state'],'current')
        self.assertEqual(refreshed['data_as_of'],saved['data_as_of'])
        self.assertEqual(refreshed['items'][0]['valid_until'],saved['items'][0]['valid_until'])
        self.assertEqual(p,saved)

    def test_missing_fetch_time_cannot_be_inferred_from_generated_or_cache_time(self):
        result = project(fixture('complete_empty'),now=NOW,fetched_at=None,saved_at=FETCHED_AT,coverage='verified')
        self.assertEqual(result['view_state'],'unavailable')
        self.assertEqual(result['transport_freshness'],'unknown')

    def test_destination_registry_requires_independent_review_and_provenance(self):
        result = self.project()
        self.assertEqual(result['destination_policy_state'],'verified')
        self.assertEqual(DESTINATION_POLICY['authority'],'core_curated_definitions')
        self.assertTrue(DESTINATION_POLICY['synthetic'])
        for review in (None,{**DESTINATION_REVIEW,'reviewed':False},{**DESTINATION_REVIEW,'content_sha256':'0'*64}):
            with self.subTest(review=review):
                row = self.project(destination_review=review)['items'][0]
                self.assertEqual(row['location'],WITHHELD)
                self.assertFalse(row['actionable'])

    def test_destination_authority_revision_commit_and_content_drift_fail_closed(self):
        for key,value in [('authority','ha_invented'),('core_reference_commit','0'*40),
                          ('policy_revision','unreviewed-2')]:
            policy = copy.deepcopy(DESTINATION_POLICY)
            policy[key] = value
            result = self.project(destination_policy=policy)
            self.assertEqual(result['destination_policy_state'],'mismatch')
            self.assertEqual(result['items'][0]['location'],WITHHELD)
        for change in ('coordinate','name','broaden'):
            policy = copy.deepcopy(DESTINATION_POLICY)
            if change == 'coordinate':
                policy['destinations'][0]['latitude'] = 0.01
            elif change == 'name':
                policy['destinations'][0]['name'] = 'Unapproved location'
            else:
                policy['destinations'].append({**policy['destinations'][0],'key':'auto-destination'})
            result = self.project(destination_policy=policy)
            self.assertEqual(result['destination_policy_state'],'mismatch')
            self.assertEqual(result['items'][0]['location'],WITHHELD)
            self.assertFalse(result['items'][0]['actionable'])

    def test_core_definition_drift_cannot_reuse_an_approved_destination(self):
        for key,value in [('definition_key','unreviewed_phenomenon'),('definition_version','unreviewed-2'),
                          ('definition_hash','b'*64)]:
            with self.subTest(key=key):
                p = fixture('approved_public')
                p['items'][0][key] = value
                result = project(p,now=NOW,fetched_at=FETCHED_AT,coverage='verified')
                self.assertEqual(result['destination_policy_state'],'verified')
                self.assertEqual(result['items'][0]['location_policy_state'],'withheld')
                self.assertEqual(result['items'][0]['location'],WITHHELD)
                self.assertFalse(result['items'][0]['actionable'])

    def test_shadow_diagnostics_cannot_supply_normal_offline_cache(self):
        result = project(fixture('shadow_patterns'),now=NOW,fetched_at=FETCHED_AT,
                         online=False,cached_context=True,origin='shadow')
        self.assertEqual(result['view_state'],'unavailable')
        self.assertEqual(result['items'],[])


if __name__ == '__main__':
    unittest.main()
