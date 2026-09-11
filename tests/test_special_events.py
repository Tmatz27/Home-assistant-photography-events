"""Regression cases for evidence, persistent choices and exceptional episodes."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import test_integration  # Load the pure package without Home Assistant.
from photography_events.event_state import EventState
from photography_events.events import Opportunity, alert_candidate, action_window
from photography_events import spectacles, streamflow, waves, grunion
import math

NOW = datetime(2026, 9, 6, 7, tzinfo=timezone.utc)


def event(**overrides):
    values = dict(key="site-a", roll="occurrence", title="Special event", category="waves",
                  zone_id="a", zone_name="Coast", start=NOW, end=NOW+timedelta(days=3),
                  score=90, detail="Evidence", drive_hours=5,
                  extra={"verification": "forecast", "wave_height_m": 6,
                         "measurement_label": "offshore"})
    values.update(overrides)
    return Opportunity(**values)


class TestPersistentEvents(unittest.TestCase):
    def test_restarting_does_not_repeat_a_three_day_swell(self):
        state = EventState()
        self.assertEqual(len(state.changes([event()], NOW, lambda x: True)), 1)
        state = EventState(state.dump())
        self.assertEqual(state.changes([event(score=95)], NOW+timedelta(hours=12), lambda x: True), [])

    def test_skip_covers_every_viewpoint_and_survives_restart(self):
        state = EventState()
        state.set_choice("occurrence", "skip", NOW+timedelta(days=4))
        state = EventState(state.dump())
        self.assertEqual(state.changes([event(), event(key="site-b", zone_id="b")], NOW, lambda x: True), [])
        state.set_choice("occurrence", "default", NOW)
        self.assertEqual(len(state.changes([event()], NOW, lambda x: True)), 1)

    def test_changed_measurement_does_not_count_as_larger_waves(self):
        state = EventState()
        state.changes([event()], NOW, lambda x: True)
        other = event(extra={"verification": "forecast", "wave_height_m": 10, "measurement_label": "nearshore"})
        self.assertEqual(state.changes([other], NOW, lambda x: True), [])

    def test_material_peak_increase_is_one_update(self):
        state = EventState()
        state.changes([event()], NOW, lambda x: True)
        larger = event(extra={"verification": "forecast", "wave_height_m": 8, "measurement_label": "offshore"})
        self.assertEqual(len(state.changes([larger], NOW, lambda x: True)), 1)
        self.assertEqual(state.changes([larger], NOW, lambda x: True), [])

    def test_confirmed_stage_notifies_once(self):
        state = EventState()
        state.changes([event()], NOW, lambda x: True)
        observed = event(extra={"verification": "corroborated"})
        self.assertEqual(state.changes([observed], NOW, lambda x: True)[0]["reason"], "New confirmation")
        self.assertEqual(state.changes([observed], NOW, lambda x: True), [])

    def test_ongoing_event_is_kept_even_when_drive_exceeds_remaining_time(self):
        live = event(start=NOW-timedelta(hours=3), end=NOW+timedelta(minutes=20), drive_hours=6)
        self.assertEqual(action_window([live], NOW), [live])
        self.assertEqual(action_window([replace(live, end=NOW)], NOW), [])

    def test_unconfirmed_never_notifies_even_at_a_low_user_threshold(self):
        self.assertFalse(alert_candidate(event(score=60, planning_only=True), 50))


class TestWaves(unittest.TestCase):
    def test_download_time_does_not_replace_model_issue_time(self):
        self.assertTrue(waves.recent_forecast_metadata('String date_created "2026-09-06T06:00:00Z";', NOW))
        self.assertFalse(waves.recent_forecast_metadata('String date_created "2026-09-03T06:00:00Z";', NOW))
        self.assertFalse(waves.recent_forecast_metadata('String history "downloaded today";', NOW))
    def test_missing_measurements_are_not_giant_waves(self):
        raw = "#YY MM DD hh mm WVHT DPD MWD\n2026 09 06 07 00 MM 99 999\n2026 09 06 06 00 6.6 16 290"
        rows = waves.parse_ndbc(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].height, 6.6)

    def test_multi_day_storm_counts_once_but_a_later_storm_is_separate(self):
        rows = [waves.Wave(NOW+timedelta(hours=h), 7, 16, 290) for h in (0, 6, 24, 48, 72, 150)]
        self.assertEqual([len(e) for e in waves.episodes(rows, 6.5)], [5, 1])

    def test_size_alone_does_not_qualify(self):
        self.assertFalse(waves.qualifies(waves.Wave(NOW, 8, 6, 290), 6.5))
        self.assertFalse(waves.qualifies(waves.Wave(NOW, 8, 16, 90), 6.5))

    def test_stale_buoy_is_not_live_evidence(self):
        result = waves.build_opportunities(NOW, {"46011": [waves.Wave(NOW-timedelta(hours=4), 8, 17, 290)]},
                                           {}, {"46011": {"threshold_m": 6.5}}, EventState(), (34.7, -120.5))
        self.assertEqual(result, [])

    def test_offshore_only_does_not_claim_coastal_confirmation(self):
        result = waves.build_opportunities(NOW, {"46011": [waves.Wave(NOW, 8, 17, 290)]},
                                           {}, {"46011": {"threshold_m": 6.5}}, EventState(), (34.7, -120.5))
        self.assertTrue(result[0].planning_only)
        self.assertIn("offshore", result[0].extra["measurement_label"])

    def test_coastal_forecast_and_offshore_measurement_stay_distinct(self):
        result = waves.build_opportunities(NOW, {"46011": [waves.Wave(NOW, 8, 17, 290)]},
            {"B1500": [waves.Wave(NOW+timedelta(hours=12), 6, 16, 290)]},
            {"46011": {"threshold_m": 6.5}, "B1500": {"threshold_m": 5.2}}, EventState(), (34.7, -120.5))
        self.assertFalse(result[0].planning_only)
        self.assertEqual(result[0].extra["wave_height_m"], 8)
        self.assertIn("6.0 m", result[0].extra["forecast_note"])

    def test_invalid_cdip_geometry_and_quality_fail_quiet(self):
        raw = "waveTime[1]\n1788678000\nwaveHs[1]\n7\nwaveTp[1]\n16\nwaveDp[1]\n290\nwaveFlagPrimary[1]\n1\nmetaLatitude, 34.75812\nmetaLongitude, -120.64311"
        self.assertEqual(len(waves.parse_cdip(raw, (34.75812, -120.64311))), 1)
        self.assertEqual(waves.parse_cdip(raw, (37, -122)), [])
        self.assertEqual(waves.parse_cdip(raw.replace("waveFlagPrimary[1]\n1", "waveFlagPrimary[1]\n4")), [])


class TestSpecialSources(unittest.TestCase):
    def test_grunion_published_year_midnight_and_santa_barbara_offset(self):
        html = '<h2>2026 Expected Grunion Runs</h2><table><tr><td>We</td><td>3/4</td><td>10:00 p.m. - Midnight</td></tr></table>'
        schedule = grunion.parse_schedule(html)
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0][1].day, 5)
        items = grunion.opportunities(schedule, datetime(2026, 3, 1, tzinfo=timezone.utc), (34.7, -120.5))
        self.assertEqual(items[0].start.minute, 25)
        self.assertEqual(items[0].start.utcoffset(), timedelta(hours=-8))
        self.assertTrue(items[0].planning_only)
        self.assertEqual(grunion.parse_schedule(html.replace("2026", "")), [])

    def feed(self, body):
        return f"<rss><channel><item><description>{body}</description><link>https://www.condorexpress.com/post/example</link></item></channel></rss>"

    def test_trip_total_is_not_a_megapod(self):
        raw = self.feed("2026 09–06 SB Channel Sightings: 1,000 common dolphins in many small groups.")
        self.assertEqual(spectacles.condor_reports(raw, NOW), [])

    def test_actual_dated_megapod_statement_is_usable(self):
        reports = spectacles.condor_reports(self.feed("2026 09–06 SB Channel We encountered a megapod of 1,500 common dolphins."), NOW)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].observed_at.day, 6)

    def test_new_publication_cannot_refresh_old_sighting(self):
        raw = self.feed("2026 08–06 SB Channel We encountered a megapod of 1,500 common dolphins.")
        self.assertEqual(spectacles.condor_reports(raw, NOW), [])

    def test_undated_and_negated_reports_never_confirm(self):
        self.assertEqual(spectacles.condor_reports(self.feed("We saw a megapod of 1,500 dolphins."), NOW), [])
        self.assertEqual(spectacles.condor_reports(self.feed("2026 09–06 SB Channel There was no megapod of 1,500 dolphins."), NOW), [])

    def test_search_targets_do_not_become_confirmed_with_time(self):
        for item in spectacles.watch_opportunities(NOW, (34.7, -120.5)):
            self.assertTrue(item.planning_only)
            self.assertFalse(alert_candidate(item, 50))

    def test_stale_aurora_and_remote_grid_do_not_alert(self):
        zones = [dict(id="home", name="Home", latitude=34.7, longitude=-120.5, drive_hours=0)]
        payload = {"Observation Time": (NOW-timedelta(hours=3)).isoformat(),
                   "Forecast Time": NOW.isoformat(), "coordinates": [[240, 35, 90]]}
        self.assertEqual(spectacles.aurora_opportunities(payload, NOW, zones, EventState()), [])
        payload["Observation Time"] = NOW.isoformat()
        payload["coordinates"] = [[240, 65, 90]]
        self.assertEqual(spectacles.aurora_opportunities(payload, NOW, zones, EventState()), [])


class TestCardEvidenceRegression(unittest.TestCase):
    def test_extra_astronomy_sites_cannot_evict_future_special_targets(self):
        from photography_events.events import planning_slice
        many_sites = [event(key=f"mw-{i}", roll="one-night", score=90-i) for i in range(20)]
        future = event(key="firefall", roll=None, start=NOW+timedelta(days=150))
        kept = planning_slice(many_sites+[future], 5)
        self.assertEqual(len(kept), 5)
        self.assertIn(future, kept)
        self.assertIn(many_sites[0], kept)

    def test_ordinary_birds_do_not_become_standalone_photography_targets(self):
        from photography_events import wildlife, events
        sightings = wildlife.parse_ebird([
            test_integration._ebird_entry(comName="Great-tailed Grackle", sciName="Quiscalus mexicanus"),
            test_integration._ebird_entry(comName="Vermilion Flycatcher", sciName="Pyrocephalus rubinus"),
        ], timezone.utc)
        now = datetime(2026, 3, 20, 20, tzinfo=timezone.utc)
        found = events.build_wildlife_opportunities(sightings, now)
        self.assertEqual(len(found), 1)
        self.assertIn("Vermilion", found[0].title)
        self.assertEqual(found[0].extra["verification"], "presence_only")
        self.assertEqual(len(sightings), 2, "raw evidence is retained for seasonal corroboration")

    def test_newer_report_without_url_does_not_inherit_an_old_link(self):
        from photography_events import wildlife
        from dataclasses import replace
        old = wildlife.parse_ebird([test_integration._ebird_entry()], timezone.utc)[0]
        new = replace(old, latest=old.latest+timedelta(hours=3), url=None)
        merged = wildlife.cluster([old, new])[0]
        self.assertIsNone(merged.url)
        self.assertEqual(merged.latest, new.latest)

    def test_cloudy_milky_way_alternates_retain_comparison_metrics(self):
        from photography_events import events, const
        zone = const.TARGET_ZONES[0]
        now = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
        clear = events.build_milky_way_opportunities(zone, now, 7, lambda _: 0)
        cloudy = events.build_milky_way_opportunities(zone, now, 7, lambda _: 100)
        self.assertTrue(clear)
        self.assertEqual([e.key for e in clear], [e.key for e in cloudy])
        self.assertLess(cloudy[0].score, clear[0].score)
        compact = cloudy[0].compact()
        self.assertEqual(compact["cloud_cover"], 100)
        self.assertIn("moon_illumination", compact)
        self.assertIn("comparison_through", compact)
        self.assertIn("T", compact["start"], "cloudy alternatives still have exact geometry windows")

    def test_firefall_and_moonbows_remain_year_ahead_unconfirmed_targets(self):
        from photography_events import events
        candidates = events.build_seasonal_opportunities(NOW, 365)
        fire = next(e for e in candidates if "horsetail_firefall" in e.key)
        self.assertNotIn("Southside Drive viewing areas", fire.extra["primary_locations"])
        self.assertTrue(fire.planning_only)
        moons = [e for e in spectacles.watch_opportunities(NOW, test_integration.const.DEFAULT_HOME) if e.key.startswith("moonbow-")]
        self.assertTrue(moons)
        self.assertTrue(all(e.extra["verification"] == "unverified" for e in moons))


def _usgs(readings):
    """An instantaneous-values payload in the shape USGS actually returns."""
    return {"value": {"timeSeries": [{"values": [{"value": [
        {"dateTime": moment, "value": str(value)} for moment, value in readings
    ]}]}]}}


class TestStreamflow(unittest.TestCase):
    """Measured discharge, and the care taken not to call it a waterfall."""

    GAUGE = streamflow.GAUGES["yosemite_valley"]

    def test_parses_the_latest_reading_and_its_trend(self):
        reading = streamflow.parse_streamflow(_usgs([
            ("2026-05-01T00:00:00+00:00", 900),
            ("2026-05-01T06:00:00+00:00", 1200),
            ("2026-05-01T12:00:00+00:00", 1180),
        ]), self.GAUGE)
        self.assertEqual(reading.cfs, 1180)
        self.assertEqual(reading.window_peak_cfs, 1200)
        self.assertEqual(reading.trend, "rising", "900 to 1180 across the window is rising")
        self.assertEqual(reading.observed_at.hour, 12)

    def test_at_the_peak_is_not_the_same_as_rising(self):
        """Measured from the start of the window, not against its highest value.

        Against the peak, a reading a whisker below the last three days' maximum
        reads as "rising" when the basin has in fact been flat.
        """
        flat = streamflow.parse_streamflow(_usgs([
            ("2026-06-01T00:00:00+00:00", 1200),
            ("2026-06-01T06:00:00+00:00", 1240),
            ("2026-06-01T12:00:00+00:00", 1210),
        ]), self.GAUGE)
        self.assertEqual(flat.trend, "steady")
        self.assertEqual(flat.window_peak_cfs, 1240)

    def test_trend_separates_snowmelt_from_recession(self):
        rising = streamflow.parse_streamflow(_usgs([
            ("2026-05-01T00:00:00+00:00", 700), ("2026-05-01T12:00:00+00:00", 1400)]), self.GAUGE)
        falling = streamflow.parse_streamflow(_usgs([
            ("2026-07-01T00:00:00+00:00", 1400), ("2026-07-01T12:00:00+00:00", 400)]), self.GAUGE)
        self.assertEqual(rising.trend, "rising")
        self.assertEqual(falling.trend, "falling")

    def test_the_missing_data_sentinel_is_not_a_flood(self):
        """USGS writes -999999 for a gap. Read as discharge it is a catastrophe."""
        reading = streamflow.parse_streamflow(_usgs([
            ("2026-05-01T00:00:00+00:00", -999999),
            ("2026-05-01T06:00:00+00:00", 850),
        ]), self.GAUGE)
        self.assertEqual(reading.cfs, 850)
        self.assertEqual(reading.window_peak_cfs, 850)

    def test_a_stale_reading_is_not_about_today(self):
        reading = streamflow.parse_streamflow(
            _usgs([("2026-05-01T12:00:00+00:00", 900)]), self.GAUGE)
        self.assertTrue(reading.fresh(datetime(2026, 5, 1, 18, tzinfo=timezone.utc)))
        self.assertFalse(reading.fresh(datetime(2026, 5, 4, 12, tzinfo=timezone.utc)))

    def test_the_summary_never_claims_to_have_measured_a_waterfall(self):
        """The gauge is on the Merced. Yosemite Falls is a different drainage."""
        reading = streamflow.parse_streamflow(
            _usgs([("2026-05-01T12:00:00+00:00", 1100)]), self.GAUGE)
        text = reading.summary()
        self.assertIn("Merced", text)
        self.assertIn("not the fall itself", text)
        self.assertNotIn("Yosemite Falls is", text)

    def test_garbage_yields_nothing_rather_than_a_guess(self):
        for payload in (None, {}, {"value": {}}, {"value": {"timeSeries": []}}):
            self.assertIsNone(streamflow.parse_streamflow(payload, self.GAUGE))

    def test_the_request_asks_for_discharge_without_a_key(self):
        url, params = streamflow.build_streamflow_request("11264500")
        self.assertIn("waterservices.usgs.gov", url)
        self.assertEqual(params["parameterCd"], "00060")
        self.assertEqual(params["sites"], "11264500")
        self.assertNotIn("api_key", params)


class TestMoonbowGeometry(unittest.TestCase):
    """A moonbow is optics, not folklore, so the nights are computed.

    The bow is a circle of radius ~42 degrees about the antilunar point, which
    sits as far below the horizon as the Moon sits above it. So a Moon higher
    than 42 degrees puts the whole bow underfoot.
    """

    LAT, LON = spectacles.MOONBOW_LATITUDE, spectacles.MOONBOW_LONGITUDE

    def _windows(self, year, first, last):
        found = []
        night = datetime(year, first, 1, tzinfo=timezone.utc)
        while night < datetime(year, last, 1, tzinfo=timezone.utc):
            window = spectacles.moonbow_window(night, self.LAT, self.LON)
            if window:
                found.append(window)
            night += timedelta(days=1)
        return found

    def test_the_moon_stays_inside_the_band_for_the_whole_window(self):
        """The bug this guards: taking the first and last qualifying sample.

        Near a full Moon the geometry opens after moonrise, shuts while the
        Moon is above 42 degrees, then reopens as it descends. Spanning that
        reports one nine-hour window across a gap with nothing to photograph -
        the same error as calling astronomical darkness a Milky Way window.
        """
        lat, lon = math.radians(self.LAT), math.radians(self.LON)
        for start, end, _illumination in self._windows(2027, 3, 6):
            moment = start
            while moment <= end:
                altitude = math.degrees(spectacles.astronomy.moon_altitude(moment, lat, lon))
                self.assertGreaterEqual(altitude, spectacles.MOONBOW_MIN_MOON_ALTITUDE - 1.0)
                self.assertLessEqual(
                    altitude, spectacles.MOONBOW_MAX_MOON_ALTITUDE + 1.0,
                    f"the bow is underfoot at {altitude:.1f}deg inside a reported window",
                )
                moment += timedelta(minutes=20)

    def test_windows_cluster_on_bright_moons_and_are_never_trivial(self):
        windows = self._windows(2027, 3, 6)
        self.assertTrue(windows)
        for start, end, illumination in windows:
            self.assertGreaterEqual(illumination, spectacles.MOONBOW_MIN_ILLUMINATION)
            self.assertGreaterEqual(
                (end - start).total_seconds() / 60, spectacles.MOONBOW_MIN_MINUTES,
                "a sampling artefact at the edge of the geometry is not an evening",
            )

    def test_a_dark_moon_produces_nothing_at_all(self):
        """Not a low score - nothing. There is no light to make a bow from."""
        for offset in range(0, 6):
            night = datetime(2027, 4, 4, tzinfo=timezone.utc) + timedelta(days=offset)
            window = spectacles.moonbow_window(night, self.LAT, self.LON)
            if window:
                self.assertGreaterEqual(window[2], spectacles.MOONBOW_MIN_ILLUMINATION)


class TestMoonbowOpportunities(unittest.TestCase):
    def test_timing_is_computed_but_the_phenomenon_is_not_confirmed(self):
        """Two different facts. Collapsing them is how a lead reads as a promise."""
        built = spectacles.moonbow_opportunities(NOW, test_integration.const.DEFAULT_HOME)
        self.assertTrue(built)
        for item in built:
            self.assertEqual(item.extra["verification"], "unverified")
            self.assertEqual(item.extra["timing_basis"], "computed geometry")
            self.assertTrue(item.planning_only)
            self.assertIn("azimuth", item.extra["awaiting"])

    def test_flow_is_reported_when_measured_and_named_when_missing(self):
        reading = streamflow.parse_streamflow(
            _usgs([("2026-09-06T06:00:00+00:00", 1150)]), streamflow.GAUGES["yosemite_valley"])
        with_flow = spectacles.moonbow_opportunities(NOW, test_integration.const.DEFAULT_HOME, reading)
        without = spectacles.moonbow_opportunities(NOW, test_integration.const.DEFAULT_HOME)

        self.assertIn("1,150 cfs", with_flow[0].detail)
        self.assertIn("not the fall itself", with_flow[0].detail)
        self.assertEqual(with_flow[0].extra["streamflow_cfs"], 1150)
        self.assertIsNone(without[0].extra["streamflow_cfs"])
        self.assertIn("basin flow", without[0].extra["awaiting"])


class TestEclipseReachability(unittest.TestCase):
    """An ocean coordinate is not a place you can stand.

    The temptation, when a decade of solar eclipses produces no rows, is to
    loosen the test until something appears - to accept the nearest centreline
    sample as a destination. That would put a trip on the calendar to a point in
    the Pacific. The empty list is the correct answer, and these lock in why.
    """

    def setUp(self):
        import json
        from pathlib import Path
        root = Path(test_integration.__file__).resolve().parent.parent / "custom_components" / "photography_events"
        self.catalog = json.loads((root / "eclipse_catalog.json").read_text(encoding="utf-8"))

    def test_no_central_solar_path_is_drivable_from_home(self):
        """A fact about this decade, not a bug. Recorded so it stays visible."""
        from photography_events.wildlife import haversine_km
        home = test_integration.const.DEFAULT_HOME
        paths = [row for row in self.catalog["events"] if row.get("kind") == "solar" and row.get("path")]
        self.assertGreaterEqual(len(paths), 16, "catalogue should carry the sampled central paths")

        nearest = min(
            haversine_km(home[0], home[1], point[1], point[2])
            for row in paths for point in row["path"]
        )
        self.assertGreater(
            nearest, 3000,
            "a central path has come within driving range - the vetted-site list now "
            "needs real places inside it, and this test needs rewriting rather than deleting",
        )

    def test_a_site_outside_the_corridor_is_refused(self):
        from photography_events import eclipses
        row = next(r for r in self.catalog["events"] if r.get("kind") == "solar" and r.get("path"))
        inside = row["path"][len(row["path"]) // 2]
        self.assertGreaterEqual(
            eclipses.central_path_margin(row, (inside[1], inside[2])), 0,
            "the centreline itself must be inside its own corridor",
        )
        self.assertLess(
            eclipses.central_path_margin(row, test_integration.const.DEFAULT_HOME), 0,
            "home is thousands of km away and must never read as inside a path",
        )

    def test_penumbral_lunar_eclipses_never_reach_the_calendar(self):
        """A camera records a full Moon. Listing them teaches you to skip the row."""
        from photography_events import eclipses
        built = eclipses.opportunities(
            self.catalog, NOW, list(test_integration.const.TARGET_ZONES),
            test_integration.const.DEFAULT_HOME, max_drive_hours=6.0, horizon_days=3650,
        )
        self.assertFalse([item for item in built if "penumbral" in item.title.lower()])
        self.assertFalse(
            [item for item in built if "solar" in item.title.lower()],
            "no solar eclipse in this catalogue has a vetted site inside its path",
        )
        self.assertTrue([item for item in built if "lunar" in item.title.lower()],
                        "umbral lunar eclipses are visible from home and must still appear")
