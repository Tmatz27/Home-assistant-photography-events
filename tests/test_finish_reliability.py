"""Evidence survives the builder -> compact boundary without gaining certainty."""
import copy
import unittest
from datetime import timedelta
from unittest.mock import patch

import test_integration
from test_special_events import NOW, _usgs
from photography_events import spectacles, streamflow, source_health


class FinishReliability(unittest.TestCase):
    def test_published_moonbow_anchor_does_not_turn_generic_geometry_into_a_prediction(self):
        # Brian Hawkins, Lower Falls table, published May 11 2026:
        # May 29 local ideal 22:20 PDT = May 30 05:20 UTC, ends 22:50.
        # https://www.yosemitemoonbow.com/ (Lower Falls.JPG, reviewed Sep 17).
        # This historical fixture is never recycled as next year's prediction.
        from datetime import datetime, timezone
        night = datetime(2026, 5, 29, tzinfo=timezone.utc)
        start, end, _ = spectacles.moonbow_window(night, spectacles.MOONBOW_LATITUDE, spectacles.MOONBOW_LONGITUDE)
        ideal = datetime(2026, 5, 30, 5, 20, tzinfo=timezone.utc)
        published_end = datetime(2026, 5, 30, 5, 50, tzinfo=timezone.utc)
        self.assertLess(start, ideal)
        self.assertGreater(end, published_end + timedelta(hours=2), 'Generic geometry must not be described as the actual bow duration')

    def test_discharge_rejects_wrong_identity_units_quality_and_nonfinite_values(self):
        gauge = streamflow.GAUGES['yosemite_valley']
        valid = _usgs([(NOW.isoformat(), 200)])
        changes = [('value', 'NaN'), ('value', 'Infinity'), ('value', '-Infinity'),
                   ('value', None), ('value', True), ('value', -1),
                   ('monitoring_location_id', 'USGS-00000000'), ('parameter_code', '00065'),
                   ('unit_of_measure', 'm^3/s'), ('statistic_id', '00003'),
                   ('approval_status', 'Rejected'), ('approval_status', []),
                   ('qualifier', ['ICE']), ('time', NOW.replace(tzinfo=None).isoformat())]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                payload = copy.deepcopy(valid)
                payload['features'][0]['properties'][key] = value
                self.assertIsNone(streamflow.parse_streamflow(payload, gauge))

    def test_partial_page_is_not_a_complete_trend(self):
        payload = _usgs([(NOW.isoformat(), 200)])
        payload['links'] = [{'rel': 'next', 'href': 'https://example.test/next'}]
        self.assertIsNone(streamflow.parse_streamflow(payload, streamflow.GAUGES['yosemite_valley']))

    def test_request_is_a_bounded_utc_interval(self):
        _, params = streamflow.build_streamflow_request('11264500', now=NOW)
        self.assertEqual(params['datetime'], f'{(NOW-timedelta(hours=72)).isoformat()}/{NOW.isoformat()}')
        self.assertEqual(params['limit'], 1000)

    def test_bad_conditions_and_outlook_survive_compact_and_health(self):
        reading = streamflow.parse_streamflow(_usgs([(NOW.isoformat(), 0)]), streamflow.GAUGES['yosemite_valley'])
        for days, is_forecast in ((2, True), (10, False)):
            start = NOW + timedelta(days=days)
            with patch.object(spectacles, 'MOONBOW_HORIZON_DAYS', 0), patch.object(
                    spectacles, 'moonbow_window', side_effect=[None, (start, start+timedelta(hours=1), .99)]):
                item = spectacles.moonbow_opportunities(NOW, test_integration.const.DEFAULT_HOME, reading, lambda _: 100)[0]
            source_health.annotate([item], {'streamflow': {'state': 'failed', 'name': 'USGS', 'impact': 'Missing readings'}})
            row = item.compact()
            self.assertTrue(row['planning_only'])
            self.assertEqual(row['start'], start.isoformat())
            self.assertNotIn('all_day', row)
            self.assertEqual(row['verification'], 'unverified')
            self.assertIn('unfavourable', row['condition_states']['Cloud'])
            self.assertEqual(row['condition_states']['Waterfall spray'], 'Unconfirmed')
            self.assertNotIn('conditions_met', row)
            self.assertEqual(row['cloud_is_forecast'], is_forecast)
            self.assertEqual(row['streamflow_cfs'], 0)
            self.assertEqual(row['streamflow_observed_at'], NOW.isoformat())
            self.assertIn('waterdata.usgs.gov', row['streamflow_url'])
            self.assertEqual(row['degraded_sources'], ['streamflow'])
            self.assertEqual(source_health.dependencies(item), {'weather', 'streamflow'})
            source_health.annotate([item], {'streamflow': {'state': 'ok'}})
            self.assertNotIn('degraded_sources', item.compact())
            self.assertEqual(item.extra['verification'], 'unverified')
