"""Portable V17A contract examples and adversarial tests; no runtime changes."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v17a_contract_model import InvalidContract, PUBLIC, WITHHELD, project

FIXTURES = Path(__file__).parent / 'fixtures' / 'v17a'
NOW = datetime(2026,10,9,20,tzinfo=timezone.utc)


def fixture(name):
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'))


class V17AContractTests(unittest.TestCase):
    def project(self, name='approved_public', **kwargs):
        return project(fixture(name),now=NOW,coverage='verified',**kwargs)

    def test_complete_current_empty_is_scoped_assessment(self):
        result = self.project('complete_empty')
        self.assertEqual((result['view_state'],result['count']),('empty_assessed',0))

    def test_empty_without_coverage_witness_is_unknown(self):
        result = project(fixture('complete_empty'),now=NOW)
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
        result = project(p,now=NOW,coverage='verified')
        self.assertEqual(result['view_state'],'offline_stale')
        self.assertFalse(result['items'][0]['actionable'])

    def test_offline_cache_cannot_act(self):
        result = self.project(online=False)
        self.assertEqual(result['view_state'],'offline_stale')
        self.assertFalse(result['items'][0]['eligibility'])
        self.assertTrue(result['items'][0]['held'])

    def test_shadow_preview_never_enters_normal_frontend(self):
        p = fixture('shadow_patterns')
        self.assertTrue(p['preview_opportunities'][0]['held'])
        self.assertFalse(p['preview_opportunities'][0]['eligibility'])
        # Even a contradictory future shadow preview cannot become actionable.
        p['preview_opportunities'][0].update(eligibility=True,held=False,presentation='cant_miss')
        result = project(p,now=NOW,origin='shadow')
        self.assertEqual(result['view_state'],'shadow_only')
        self.assertEqual(result['items'],[])
        self.assertFalse(result['notifications_enabled'])

    def test_unsupported_birds_is_not_empty_birds(self):
        result = project(fixture('complete_empty'),now=NOW,coverage='unsupported')
        self.assertEqual(result['view_state'],'unsupported')
        self.assertIsNone(result['count'])

    def test_approved_curated_destination_retains_exact_coordinates(self):
        row = self.project()['items'][0]
        self.assertEqual((row['location']['latitude'],row['location']['longitude']),PUBLIC['synthetic_public'][1:])
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
        encoded = json.dumps(project(p,now=NOW,coverage='verified'))
        for value in ('SENSITIVE_SENTINEL','35.123456','-120.654321'):
            self.assertNotIn(value,encoded)

    def test_unapproved_or_altered_or_partial_coordinates_are_withheld(self):
        for delta in ({'key':'auto-destination'},{'latitude':0.01},{'longitude':None},{'policy':'unknown'}):
            with self.subTest(delta=delta):
                p = fixture('approved_public')
                p['items'][0]['location'].update(delta)
                self.assertEqual(project(p,now=NOW,coverage='verified')['items'][0]['location'],WITHHELD)

    def test_nonfinite_and_boolean_coordinates_are_withheld(self):
        for value in (float('nan'),float('inf'),True):
            p = fixture('approved_public')
            p['items'][0]['location']['latitude'] = value
            self.assertEqual(project(p,now=NOW,coverage='verified')['items'][0]['location'],WITHHELD)

    def test_unknown_safety_access_cannot_act_even_with_eligibility_flag(self):
        p = fixture('unknown_safety_access')
        p['items'][0].update(eligibility=True,held=False,presentation='cant_miss',blockers=[])
        self.assertFalse(project(p,now=NOW,coverage='verified')['items'][0]['actionable'])

    def test_api_schema_and_projection_incompatibility_fail_closed(self):
        for key,value in [('api_version','v2'),('schema_version','9999')]:
            p = fixture('complete_empty')
            p[key] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW)
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
        encoded = json.dumps(project(p,now=NOW,coverage='verified'))
        for value in ('SENTINEL','35.123456','-120.654321','876543','secret.invalid','raw_evidence','connection'):
            self.assertNotIn(value,encoded)

    def test_identity_survives_score_generation_and_viewpoint_changes(self):
        p = fixture('approved_public')
        before = project(p,now=NOW,coverage='verified')['items'][0]['event_id']
        p.update(assessment_id=18)
        p['items'][0].update(assessment_id=18,confidence=50,title='Updated synthetic title',drive_minutes=80)
        p['items'][0]['location']['latitude'] = 0.01
        after = project(p,now=NOW,coverage='verified')['items'][0]['event_id']
        self.assertEqual(before,after)

    def test_annual_recurrence_has_separate_identity(self):
        p = fixture('approved_public')
        first = self.project()['items'][0]['event_id']
        p['items'][0]['occurrence_key'] = 'synthetic-spectacle-2027'
        self.assertNotEqual(first,project(p,now=NOW,coverage='verified')['items'][0]['event_id'])

    def test_duplicate_or_empty_identity_rejects_entire_snapshot(self):
        p = fixture('approved_public')
        p['items'].append(copy.deepcopy(p['items'][0]))
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,coverage='verified')
        p = fixture('approved_public')
        p['items'][0]['occurrence_key'] = ''
        with self.assertRaises(InvalidContract):
            project(p,now=NOW)

    def test_expiry_ages_without_new_fetch_or_push(self):
        result = project(fixture('approved_public'),now=NOW+timedelta(hours=2),coverage='verified')
        self.assertFalse(result['items'][0]['actionable'])

    def test_naive_future_and_reversed_timestamps_reject(self):
        for key,value in [('data_as_of','2026-10-09T20:00:00'),('generated_at','2026-10-10T20:00:00Z')]:
            p = fixture('approved_public')
            p[key] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW)
        p = fixture('approved_public')
        p['items'][0]['starts_at'] = '2027-10-09T20:00:00Z'
        with self.assertRaises(InvalidContract):
            project(p,now=NOW)

    def test_limits_and_invalid_nested_types_reject(self):
        for field,value in [('gear',{'optional':[{'token':'secret'}]}),('confidence',True),('eligibility','true'),('detail','x'*2049),('drive_minutes',float('inf'))]:
            p = fixture('approved_public')
            p['items'][0][field] = value
            with self.assertRaises(InvalidContract):
                project(p,now=NOW)
        p = fixture('approved_public')
        p['items'] *= 501
        with self.assertRaises(InvalidContract):
            project(p,now=NOW)

    def test_contradictory_complete_assessment_is_not_empty_success(self):
        p = fixture('complete_empty')
        p['missing_required_sources'] = ['nws_alerts']
        with self.assertRaises(InvalidContract):
            project(p,now=NOW,coverage='verified')

    def test_projection_does_not_mutate_cached_core_input(self):
        p = fixture('approved_public')
        saved = copy.deepcopy(p)
        project(p,now=NOW,online=False)
        self.assertEqual(saved,p)

    def test_expired_item_is_held_inside_an_otherwise_current_snapshot(self):
        p = fixture('approved_public')
        p['items'][0]['valid_until'] = '2026-10-09T19:59:00Z'
        row = project(p,now=NOW,coverage='verified')['items'][0]
        self.assertTrue(row['held'])
        self.assertFalse(row['eligibility'])
        self.assertEqual(row['safety_state'],'unknown')

    def test_watching_presentation_is_preserved_without_promotion(self):
        p = fixture('approved_public')
        p['items'][0].update(presentation='watching',watching=True,eligibility=False)
        row = project(p,now=NOW,coverage='verified')['items'][0]
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


if __name__ == '__main__':
    unittest.main()
