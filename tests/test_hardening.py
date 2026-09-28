"""0.16.0 hardening pass: every fix has a test that names the failure it prevents.

The theme is trust. A degraded source, an unchecked safety feed, a stale
report or a single far-away sighting must each make the dashboard *quieter*
or say what it could not check - never confidently wrong.
"""
import unittest
from datetime import datetime, timedelta, timezone

import test_integration  # noqa: F401 - loads the pure package without Home Assistant.
from zoneinfo import ZoneInfo

from photography_events import (
    birds, conditions, const, curation, eligibility, events, field_reports, gear, lunar, phenomena, source_health,
    spectacles, verification, weather_hazards, wildlife,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 27, 17, tzinfo=UTC)
VANDENBERG = (34.742, -120.572)


def opp(phenomenon, category, *, lat=VANDENBERG[0], lon=VANDENBERG[1], drive=0.0, zone="home",
        start=None, hours=2, score=90, **extra):
    start = start or NOW + timedelta(hours=1)
    return events.Opportunity(
        key=f"{phenomenon}-{zone}", title=phenomenon.replace("_", " "), category=category, zone_id=zone,
        zone_name=zone.title(), start=start, end=start + timedelta(hours=hours), score=score, detail="",
        drive_hours=drive, latitude=lat, longitude=lon, phenomenon=phenomenon, extra=dict(extra))


def sunset(**extra):
    base = {"evidence_state": "forecast", "standout": True, "light_path": "modelled", "local_score": 90}
    return opp("sunset_local", "sunset", **{**base, **extra})


def health(**states):
    return {key: {"state": state, "name": key, "impact": f"{key} impact"} for key, state in states.items()}


def alert(event, same="006083", severity="Moderate", geometry=None, now=NOW):
    return {"event": event, "headline": event, "severity": severity, "same": [same], "geometry": geometry,
            "onset": (now - timedelta(hours=1)).isoformat(), "ends": (now + timedelta(days=1)).isoformat()}


def assess(item, alerts=(), **kwargs):
    return eligibility.assess(item, NOW, max_drive_hours=6.0, alerts=None if alerts is None else list(alerts), **kwargs)


class TestSourceRoles(unittest.TestCase):
    """Item 1: required, preferred (with fallback) and optional sources."""

    def test_sunsetwx_failure_leaves_a_valid_local_sunset_eligible(self):
        sky = sunset()  # The coordinator withholds a failing provider, so the row is local-basis.
        source_health.annotate([sky], health(sunsetwx="failed", weather="ok", air_quality="ok"))
        self.assertTrue(assess(sky)["eligible"], sky.extra["assessment"]["blockers"])

    def test_sunsetwx_failure_is_visible_as_a_fallback(self):
        sky = sunset()
        source_health.annotate([sky], health(sunsetwx="failed", weather="ok"))
        self.assertEqual(sky.extra["degraded_sources"], ["sunsetwx"])
        self.assertIn("local model decided", sky.extra["fallback_note"])
        self.assertNotIn("degraded_required", sky.extra)
        self.assertIn("fallback_note", sky.compact())

    def test_optional_air_quality_failure_does_not_kill_a_sunset(self):
        sky = sunset()
        source_health.annotate([sky], health(air_quality="stale", weather="ok"))
        self.assertTrue(assess(sky)["eligible"])
        self.assertEqual(sky.extra["degraded_sources"], ["air_quality"])

    def test_a_required_source_still_blocks(self):
        local = sunset()
        source_health.annotate([local], health(weather="failed"))
        self.assertFalse(assess(local)["eligible"])
        self.assertIn("required source unavailable: weather", local.extra["assessment"]["blockers"])
        # When SunsetWx itself decided, SunsetWx is the required source.
        provider = sunset(provider_quality="Great", provider_percent=88)
        source_health.annotate([provider], health(sunsetwx="stale", weather="ok"))
        self.assertFalse(assess(provider)["eligible"])

    def test_sighting_feed_outage_is_optional_for_report_driven_phenomena(self):
        whales = opp("humpback_lunge_feeding", "marine", drive=0.8, zone="avila", lat=35.18, lon=-120.74,
                     evidence_state="behavior_confirmed", observed_at=(NOW - timedelta(hours=5)).isoformat())
        source_health.annotate([whales], health(inaturalist="failed", condor_reports="failed"))
        self.assertTrue(assess(whales)["eligible"], whales.extra["assessment"]["blockers"])
        self.assertEqual(whales.extra["degraded_sources"], ["condor_reports", "inaturalist"])

    def test_dependency_roles_are_explicit(self):
        self.assertEqual(source_health.dependency_roles(sunset())["sunsetwx"], source_health.PREFERRED)
        self.assertEqual(source_health.dependency_roles(sunset(provider_quality="Great"))["sunsetwx"],
                         source_health.REQUIRED)
        self.assertEqual(source_health.dependency_roles(sunset())["air_quality"], source_health.OPTIONAL)


class TestSafetyStates(unittest.TestCase):
    """Item 2: SAFE / CAUTION / UNSAFE / UNKNOWN, and unknown is not safe."""

    def seals(self, **extra):
        return opp("elephant_seal_battles", "mammals", drive=1.9, zone="piedras_blancas", lat=35.666, lon=-121.257,
                   evidence_state="calendar", **extra)

    def test_checked_with_no_alerts_is_safe(self):
        seals = self.seals()
        result = assess(seals, [])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_SAFE)

    def test_feed_unavailable_holds_travel_and_says_so(self):
        seals = self.seals()
        result = assess(seals, None)
        self.assertFalse(result["eligible"])
        self.assertTrue(result["held_for_safety"])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_UNKNOWN)
        board = eligibility.dashboard([seals], NOW)
        self.assertEqual(board["events"], [])
        self.assertEqual([row["phenomenon"] for row in board["held"]], ["elephant_seal_battles"])
        self.assertNotEqual(board["headline"], "Nothing worth changing plans for this week.")
        self.assertIn(seals, events.within_drive([seals], 6.0), "the planner still lists it")

    def test_home_sunset_is_not_travel(self):
        sky = sunset()
        result = assess(sky, None)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_UNKNOWN)
        self.assertIn("not checked", sky.extra["safety_summary"])

    def test_location_that_cannot_be_matched_is_unknown(self):
        far = opp("tule_elk_rut", "mammals", drive=5.5, zone="nowhere", lat=41.5, lon=-123.9, evidence_state="calendar_presence")
        result = assess(far, [alert("Wind Advisory")])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_UNKNOWN)
        self.assertFalse(result["eligible"])

    def test_other_alerts_with_polygons_do_not_make_an_unmatched_place_checkable(self):
        box = {"type": "Polygon", "coordinates": [[[-118, 34], [-117, 34], [-117, 35], [-118, 35], [-118, 34]]]}
        _, checkable = weather_hazards.alerts_at([alert("Wind Advisory", geometry=box)], 41.5, -123.9,
                                                 NOW, NOW + timedelta(hours=2), NOW)
        self.assertFalse(checkable)

    def test_serious_warning_is_unsafe(self):
        for event in ("Tornado Warning", "Severe Thunderstorm Warning", "Flash Flood Warning", "Flood Warning",
                      "Winter Storm Warning", "Blizzard Warning", "Ice Storm Warning", "High Wind Warning",
                      "Extreme Wind Warning", "Fire Warning", "Evacuation Immediate", "Tsunami Warning",
                      "Snow Squall Warning", "Tropical Storm Warning", "Hurricane Warning", "Extreme Heat Warning",
                      "Coastal Flood Warning"):
            with self.subTest(event=event):
                seals = self.seals()
                result = assess(seals, [alert(event, same="006079")])
                self.assertEqual(result["safety_state"], weather_hazards.STATE_UNSAFE)
                self.assertFalse(result["eligible"])
                self.assertFalse(events.alert_candidate(seals, 0))

    def test_avalanche_warning_blocks_mountains_only(self):
        seals = self.seals()
        self.assertEqual(assess(seals, [alert("Avalanche Warning", same="006079")])["safety_state"], "caution")
        snow = opp("fresh_snow_clearing", "rare_phenomena", drive=5.0, zone="yosemite_valley", lat=37.746, lon=-119.594,
                   evidence_state="behavior_confirmed")
        self.assertEqual(assess(snow, [alert("Avalanche Warning", same="006043")])["safety_state"], "unsafe")

    def test_unreviewed_severe_event_is_unsafe(self):
        seals = self.seals()
        result = assess(seals, [alert("Brand New Warning", same="006079", severity="Severe")])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_UNSAFE)

    def test_caution_only_does_not_block(self):
        for event in ("Wind Advisory", "Dense Fog Advisory", "Red Flag Warning", "Heat Advisory"):
            with self.subTest(event=event):
                seals = self.seals()
                result = assess(seals, [alert(event, same="006079")])
                self.assertEqual(result["safety_state"], weather_hazards.STATE_CAUTION)
                self.assertTrue(result["eligible"], result["blockers"])

    def test_red_flag_is_fire_weather_not_a_fire(self):
        seals = self.seals()
        assess(seals, [alert("Red Flag Warning", same="006079")])
        self.assertIn("fire weather", seals.extra["safety_summary"])
        seals = self.seals()
        self.assertEqual(assess(seals, [alert("Fire Warning", same="006079")])["safety_state"], "unsafe")

    def test_swell_with_surf_warning_restricts_the_viewpoint(self):
        swell = opp("exceptional_swell", "waves", drive=0.3, zone="surf_beach", evidence_state="measured")
        result = assess(swell, [alert("High Surf Warning")])
        self.assertEqual(result["safety_state"], weather_hazards.STATE_CAUTION)
        self.assertTrue(result["eligible"])
        self.assertIn("never on the beach, rocks or jetties", swell.extra["safety_summary"])

    def test_surf_warning_blocks_a_night_on_the_beach(self):
        glow = opp("bioluminescent_surf", "rare_phenomena", drive=0.9, zone="beach", evidence_state="behavior_confirmed",
                   moon_illumination=0.1, observed_at=(NOW - timedelta(hours=10)).isoformat())
        self.assertTrue(assess(glow, [])["eligible"])
        glow = opp("bioluminescent_surf", "rare_phenomena", drive=0.9, zone="beach", evidence_state="behavior_confirmed",
                   moon_illumination=0.1, observed_at=(NOW - timedelta(hours=10)).isoformat())
        self.assertEqual(assess(glow, [alert("High Surf Warning")])["safety_state"], "unsafe")

    def test_surf_warning_is_irrelevant_inland(self):
        elk = opp("tule_elk_rut", "mammals", drive=1.35, zone="carrizo_plain", lat=35.191, lon=-119.793,
                  evidence_state="calendar_presence")
        self.assertEqual(assess(elk, [alert("High Surf Warning", same="006079")])["safety_state"], "safe")

    def test_boat_trips_say_marine_zones_are_not_checked(self):
        orcas = opp("orca_presence", "marine", drive=1.1, zone="monterey", lat=36.605, lon=-121.89,
                    evidence_state="repeated_presence")
        assess(orcas, [])
        self.assertTrue(any("coastal waters forecast" in note for note in orcas.extra["safety_notes"]))

    def test_unsafe_rows_stay_in_the_planner(self):
        seals = self.seals()
        result = assess(seals, [alert("High Wind Warning", same="006079")])
        self.assertNotEqual(result["presentation"], "cant_miss")
        self.assertIn(seals, events.within_drive([seals], 6.0))

    def test_stale_alert_feed_is_unknown(self):
        fetched = NOW - timedelta(hours=weather_hazards.ALERTS_MAX_AGE_HOURS + 1)
        self.assertIsNone(weather_hazards.current_alerts([], fetched, 0, NOW))
        self.assertIsNone(weather_hazards.current_alerts(None, None, 0, NOW))
        current = weather_hazards.current_alerts([], NOW - timedelta(minutes=30), 0, NOW)
        self.assertTrue(current.complete)
        self.assertEqual(list(current.alerts), [])
        # A failed latest fetch is an incomplete check (0.16.0 correction):
        # retained warnings still block, but an empty match is never "safe".
        failed = weather_hazards.current_alerts([], NOW, 1, NOW)
        self.assertFalse(failed.complete)
        self.assertEqual(weather_hazards.safety(self.seals(), failed, NOW, "coastal")["state"], "unknown")


PACIFIC = ZoneInfo("America/Los_Angeles")
HOME = const.DEFAULT_HOME


def forecast(start, hours=72, **series):
    """An Open-Meteo-shaped hourly forecast; each series is a value or f(moment)."""
    times = [start + timedelta(hours=i) for i in range(hours)]
    hourly = {"time": [t.isoformat() for t in times]}
    for key, value in series.items():
        hourly[key] = [value(t) if callable(value) else value for t in times]
    return {"hourly": hourly}


def report(key, zone, observed, text, category="rare_phenomena", source="email_ranger", count=None):
    return field_reports.FieldReport(source, "Ranger email", "", category, zone, text[:60], text, 80,
                                     observed, "", observed, key, None, None, count)


class TestFreshSnowClearing(unittest.TestCase):
    """Item 3: a dated snow report AND a current clearing forecast."""

    NOW = datetime(2027, 1, 12, 18, tzinfo=UTC)

    def rows(self, observed, cloud=None, forecast_start=None):
        found = spectacles.report_opportunities(
            [report("fresh_snow_clearing", "yosemite_valley", observed, "Eight inches of fresh snow on the valley floor this morning.")],
            self.NOW, HOME)
        forecasts = {}
        if cloud is not None:
            forecasts["yosemite_valley"] = {"local": forecast(forecast_start or self.NOW - timedelta(hours=2), cloud_cover=cloud)}
        conditions.annotate_snow(found, forecasts, self.NOW)
        # Yosemite snow depends on park access (curation.ZONE_ACCESS): a
        # current, complete NPS read with no closures here.
        conditions.annotate_access(found, [], self.NOW, 0, self.NOW)
        for item in found:
            eligibility.assess(item, self.NOW, max_drive_hours=8.0, alerts=[])
        return found

    def test_report_only_is_a_watch(self):
        (snow,) = self.rows(self.NOW - timedelta(hours=6))
        self.assertFalse(snow.extra["assessment"]["eligible"])
        self.assertIn("no clearing forecast", " ".join(snow.extra["assessment"]["blockers"]))
        self.assertEqual(snow.extra["assessment"]["presentation"], "watch")

    def test_clearing_only_is_a_signal_not_a_row(self):
        self.assertEqual(spectacles.report_opportunities([], self.NOW, HOME), [])
        start = self.NOW - timedelta(hours=2)
        model = forecast(start, snowfall=lambda t: 1.0 if t < self.NOW + timedelta(hours=14) else 0.0,
                         cloud_cover=lambda t: 100 if t < self.NOW + timedelta(hours=16) else 10)
        signals = weather_hazards.watch_signals({"yosemite_valley": {"local": model}},
                                                [const.ZONES_BY_ID["yosemite_valley"]], self.NOW)
        self.assertEqual([signal.phenomena for signal in signals], [["fresh_snow_clearing"]])

    def test_report_and_clearing_is_eligible(self):
        (snow,) = self.rows(self.NOW - timedelta(hours=6),
                            cloud=lambda t: 100 if t < self.NOW + timedelta(hours=10) else 15)
        self.assertTrue(snow.extra["assessment"]["eligible"], snow.extra["assessment"]["blockers"])
        self.assertEqual(snow.start, datetime.fromisoformat(snow.extra["clearing_at"]))

    def test_stale_report_is_dropped(self):
        stale = self.NOW - timedelta(days=curation.CATALOG["fresh_snow_clearing"].evidence_days, hours=1)
        self.assertEqual(self.rows(stale, cloud=10), [])

    def test_expired_clearing_forecast_does_not_count(self):
        # The model run only covers hours already past: a clearing promised for
        # yesterday is not a clearing forecast today.
        (snow,) = self.rows(self.NOW - timedelta(hours=6), cloud=10, forecast_start=self.NOW - timedelta(hours=80))
        self.assertNotIn("clearing_at", snow.extra)
        self.assertFalse(snow.extra["assessment"]["eligible"])
        snow.extra["clearing_at"] = (self.NOW - timedelta(hours=conditions.CLEARING_WINDOW_HOURS + 1)).isoformat()
        eligibility.assess(snow, self.NOW, max_drive_hours=8.0, alerts=[])
        self.assertIn("the forecast clearing has passed", snow.extra["assessment"]["blockers"])

    def test_winter_storm_warning_blocks(self):
        (snow,) = self.rows(self.NOW - timedelta(hours=6), cloud=10)
        eligibility.assess(snow, self.NOW, max_drive_hours=8.0, alerts=[alert("Winter Storm Warning", same="006043", now=self.NOW)])
        self.assertEqual(snow.extra["assessment"]["safety_state"], "unsafe")
        self.assertFalse(snow.extra["assessment"]["eligible"])


class TestMoonbow(unittest.TestCase):
    """Item 4: a supported candidate is still a watch; only a validated viewpoint prediction could act."""

    NOW = datetime(2026, 5, 29, 20, tzinfo=UTC)  # near the late-May full Moon

    def test_flow_report_makes_a_supported_candidate_not_an_opportunity(self):
        flow = report("moonbow", "yosemite_valley", self.NOW - timedelta(hours=20), "Yosemite Falls roaring; heavy spray at the footbridge.")
        rows = spectacles.moonbow_opportunities(self.NOW, HOME, None, lambda _: 5, [flow])
        self.assertTrue(rows, "sky geometry is still computed")
        supported = [item for item in rows if item.extra["evidence_state"] == "candidate_supported"]
        self.assertTrue(supported)
        for item in rows:
            result = eligibility.assess(item, self.NOW, max_drive_hours=8.0, alerts=[])
            self.assertFalse(result["eligible"])
            self.assertIn("candidate", item.title)
            self.assertIn("duration_minutes", item.extra, "calculations are preserved")
        self.assertEqual(supported[0].extra["assessment"]["presentation"], "watch")
        self.assertEqual(supported[0].extra["condition_states"]["Viewpoint prediction"],
                         "Not available: no consumable viewpoint timetable")

    def test_only_a_viewpoint_validated_state_is_actionable(self):
        self.assertEqual(curation.CATALOG["moonbow"].actionable, {curation.STATE_VIEWPOINT_VALIDATED})


class TestFirefall(unittest.TestCase):
    """Item 5: alignment, water, local sky, light path and access, all at once."""

    NOW = datetime(2027, 2, 16, 18, tzinfo=UTC)

    def row(self, flow=True, cloud=10, low=0, upstream=True, alerts=(), now=None):
        now = now or self.NOW
        reports = [report("horsetail_firefall", "yosemite_valley", now - timedelta(hours=20),
                          "Horsetail Fall is flowing this week.")] if flow else []
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, reports)
        bundle = {"local": forecast(now - timedelta(hours=2), hours=96, cloud_cover=cloud)}
        if upstream:
            bundle["upstream"] = {"sunset": forecast(now - timedelta(hours=2), hours=96, cloud_cover_low=low, cloud_cover_mid=0)}
        conditions.annotate_firefall(rows, {"yosemite_valley": bundle}, now, list(alerts))
        item = next(item for item in rows if item.phenomenon == "horsetail_firefall" and item.extra.get("precision") == "peak")
        eligibility.assess(item, now, max_drive_hours=8.0, alerts=[])
        return item

    def test_every_condition_met_is_eligible(self):
        item = self.row()
        self.assertTrue(item.extra["assessment"]["eligible"], item.extra["assessment"]["blockers"])
        self.assertEqual(item.extra["condition_states"]["Western light path"], "Open")

    def test_no_flow_report_blocks_and_never_uses_merced(self):
        item = self.row(flow=False)
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertIn("Merced discharge is a different drainage", item.extra["condition_states"]["Water on Horsetail Fall"])

    def test_cloud_at_sunset_blocks(self):
        self.assertFalse(self.row(cloud=60).extra["assessment"]["eligible"])

    def test_blocked_light_path_blocks(self):
        item = self.row(low=95)
        self.assertIn("cloud upstream blocks the sunset light", item.extra["assessment"]["blockers"])

    def test_unmodelled_light_path_blocks(self):
        self.assertIn("western light path not modelled", self.row(upstream=False).extra["assessment"]["blockers"])

    def test_viewing_area_closure_blocks(self):
        closure = type("Alert", (), {"park_code": "yose", "blocking": True, "title": "Northside Drive closed",
                                     "description": "El Capitan picnic area closed for firefall management."})()
        item = self.row(alerts=[closure])
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertIn("Northside Drive closed", item.extra["condition_states"]["Park access"])

    def test_an_early_flow_report_does_not_move_the_alignment(self):
        now = datetime(2027, 1, 25, 18, tzinfo=UTC)
        item = next(item for item in events.build_seasonal_opportunities(
            now, 365, HOME, None, [report("horsetail_firefall", "yosemite_valley", now - timedelta(hours=5), "Horsetail Fall is flowing.")])
            if item.phenomenon == "horsetail_firefall")
        self.assertEqual(item.start.date().isoformat(), "2027-02-12")


class TestEvidenceFreshness(unittest.TestCase):
    """Item 6: fast-moving subjects expire fast; stable ones do not."""

    def test_documented_product_thresholds(self):
        days = {key: curation.CATALOG[key].evidence_days for key in (
            "humpback_lunge_feeding", "blue_whale_feeding", "orca_presence", "bioluminescent_surf",
            "condor_activity", "pismo_monarchs", "aspen_tier1_high", "elephant_seal_battles")}
        self.assertEqual(days, {"humpback_lunge_feeding": 3, "blue_whale_feeding": 3, "orca_presence": 3,
                                "bioluminescent_surf": 3, "condor_activity": 7, "pismo_monarchs": 14,
                                "aspen_tier1_high": 7, "elephant_seal_battles": 14})

    def state(self, key, now, age_days, text, category, count=None):
        window = next(item for item in phenomena.PEAK_WINDOWS if item.key == key)
        zone = {"humpback_lunge_feeding": "morro_bay", "pismo_monarchs": "pismo"}.get(key, "piedras_blancas")
        found = report(key, zone, now - timedelta(days=age_days), text, category=category, count=count)
        found.latitude, found.longitude = window.latitude, window.longitude
        return events.window_evidence(window, None, [found], now).state

    def test_humpback_behaviour_expires_after_three_days(self):
        now = datetime(2026, 9, 1, 18, tzinfo=UTC)
        text = "Humpbacks lunge feeding on anchovy."
        self.assertEqual(self.state("humpback_lunge_feeding", now, 2, text, "marine"), "behavior_confirmed")
        self.assertNotEqual(self.state("humpback_lunge_feeding", now, 4, text, "marine"), "behavior_confirmed")

    def test_monarch_count_lasts_longer(self):
        now = datetime(2026, 12, 1, 18, tzinfo=UTC)
        text = "Clusters of 2,000 monarchs at the grove."
        self.assertEqual(self.state("pismo_monarchs", now, 10, text, "rare_phenomena", count=2000), "behavior_confirmed")
        self.assertNotEqual(self.state("pismo_monarchs", now, 15, text, "rare_phenomena", count=2000), "behavior_confirmed")

    def test_elephant_seals_are_calendar_stable(self):
        now = datetime(2027, 1, 20, 18, tzinfo=UTC)
        window = next(item for item in phenomena.PEAK_WINDOWS if item.key == "elephant_seal_battles")
        self.assertEqual(events.window_evidence(window, None, [], now).state, "calendar")

    def test_bioluminescence_report_expires(self):
        now = datetime(2026, 9, 1, 18, tzinfo=UTC)
        glow = report("bioluminescent_surf", "morro_bay", now - timedelta(days=4), "Bioluminescent waves last night.")
        self.assertEqual(spectacles.report_opportunities([glow], now, HOME), [])


def orca(lat, lon, when, observer, confirmed=False):
    return wildlife.Sighting(species="Orca", scientific_name="Orcinus orca", place="Somewhere", latitude=lat,
                             longitude=lon, latest=when, earliest=when, source="iNaturalist", category="marine",
                             observers=[observer], reports=1, confirmed=confirmed, dates=[when.date().isoformat()])


class TestOrcaClustering(unittest.TestCase):
    """Item 7: far-apart reports do not add up; one observation is a signal."""

    NOW = datetime(2026, 4, 1, 18, tzinfo=UTC)

    def test_close_pair_qualifies(self):
        rows = birds.marine_presence([orca(36.80, -121.90, self.NOW - timedelta(hours=5), "a"),
                                      orca(36.75, -121.95, self.NOW - timedelta(hours=20), "b")], self.NOW, HOME)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].extra["evidence_state"], "repeated_presence")

    def test_far_pair_does_not_combine(self):
        rows = birds.marine_presence([orca(36.80, -121.90, self.NOW - timedelta(hours=5), "a"),
                                      orca(34.40, -119.70, self.NOW - timedelta(hours=20), "b")], self.NOW, HOME)
        self.assertEqual(rows, [])

    def test_single_research_grade_is_background_only(self):
        self.assertEqual(birds.marine_presence([orca(36.8, -121.9, self.NOW - timedelta(hours=3), "a", confirmed=True)],
                                               self.NOW, HOME), [])

    def test_multiple_observers_in_one_region_make_one_row(self):
        rows = birds.marine_presence([orca(36.80 + i * 0.05, -121.90, self.NOW - timedelta(hours=5 + i), obs)
                                      for i, obs in enumerate("abc")], self.NOW, HOME)
        self.assertEqual(len(rows), 1)
        self.assertIn("3 independent observers", rows[0].reasons[0])

    def test_stale_reports_do_not_count(self):
        rows = birds.marine_presence([orca(36.80, -121.90, self.NOW - timedelta(hours=80), "a"),
                                      orca(36.75, -121.95, self.NOW - timedelta(hours=90), "b")], self.NOW, HOME)
        self.assertEqual(rows, [])

    def test_a_dated_operator_report_qualifies_alone(self):
        trip = report("orca_presence", "channel_islands", self.NOW - timedelta(hours=10),
                      "A pod of five orcas passed the boat near Santa Cruz Island.", category="marine", source="condor_express")
        rows = birds.marine_presence([], self.NOW, HOME, [trip])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].extra["behavior_evidence"])
        negated = report("orca_presence", "channel_islands", self.NOW - timedelta(hours=10),
                         "No orcas today, but plenty of dolphins.", category="marine", source="condor_express")
        self.assertEqual(birds.marine_presence([], self.NOW, HOME, [negated]), [])

    def test_condor_feed_emits_orca_reports(self):
        body = ("<rss><channel><item><link>https://example.test/trip</link><description>"
                "2026 03-31 SB Channel trip. We found a pod of orcas near Anacapa. Also humpbacks.</description></item>"
                "</channel></rss>")
        reports = spectacles.condor_reports(body, self.NOW)
        self.assertEqual([item.phenomenon_key for item in reports], ["orca_presence"])

    def test_hunting_subsumes_presence_on_the_dashboard(self):
        hunt = events.Opportunity(key="hunt", title="Orcas hunting", category="marine", zone_id="x", zone_name="X",
                                  start=self.NOW, end=self.NOW + timedelta(hours=5), score=90, detail="", drive_hours=1.0,
                                  phenomenon="transient_orca_hunt")
        presence = events.Opportunity(key="pres", title="Orcas reported", category="marine", zone_id="y", zone_name="Y",
                                      start=self.NOW, end=self.NOW + timedelta(hours=5), score=90, detail="",
                                      drive_hours=1.0, phenomenon="orca_presence")
        for item in (hunt, presence):
            item.extra["assessment"] = {"eligible": True, "priority": 80, "significance": 90}
        board = eligibility.dashboard([hunt, presence], self.NOW)
        self.assertEqual([row["key"] for row in board["events"]], ["hunt"])


class TestMonarchLocation(unittest.TestCase):
    """Item 8: the dawn condition is read at the Pismo grove, never at home."""

    NOW = datetime(2026, 12, 2, 20, tzinfo=UTC)

    def grove(self, forecasts):
        count = report("pismo_monarchs", "pismo", self.NOW - timedelta(days=2), "Clusters of 3,000 monarchs at the grove.", count=3000)
        count.latitude, count.longitude = 35.1307, -120.6349
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME, None, [count])
        conditions.annotate_monarchs(rows, forecasts, self.NOW, PACIFIC)
        item = next(item for item in rows if item.phenomenon == "pismo_monarchs" and item.extra.get("precision") == "peak")
        item.drive_hours = 0.6
        eligibility.assess(item, self.NOW, max_drive_hours=6.0, alerts=[])
        return item

    def test_grove_forecast_decides_not_home(self):
        start = self.NOW - timedelta(hours=2)
        cold, warm = {"local": forecast(start, temperature_2m=8.0)}, {"local": forecast(start, temperature_2m=16.0, wind_speed_10m=3.0)}
        item = self.grove({"home": cold, "pismo_grove": warm})
        self.assertEqual(item.extra["dawn_temp_f"], 60.8)
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertEqual(item.extra["dawn_wind_ms"], 3.0)
        item = self.grove({"home": warm, "pismo_grove": cold})
        self.assertTrue(item.extra["assessment"]["eligible"], item.extra["assessment"]["blockers"])

    def test_no_grove_forecast_means_no_condition(self):
        item = self.grove({"home": {"local": forecast(self.NOW - timedelta(hours=2), temperature_2m=5.0)}})
        self.assertNotIn("dawn_temp_f", item.extra)
        self.assertFalse(item.extra["assessment"]["eligible"])

    def test_grove_is_a_forecast_point(self):
        point = next(point for point in conditions.CONDITION_POINTS if point["id"] == "pismo_grove")
        self.assertLess(wildlife.haversine_km(point["latitude"], point["longitude"], 35.131, -120.635), 1)

    def test_the_threshold_is_labelled_a_heuristic(self):
        item = self.grove({"pismo_grove": {"local": forecast(self.NOW - timedelta(hours=2), temperature_2m=16.0)}})
        self.assertIn("product heuristic", " ".join(item.extra["assessment"]["blockers"]))


def tide(moment, feet, high, station):
    info = {row["name"]: row for row in verification.TIDE_STATIONS.values()}[station]
    return verification.TideEvent(moment, feet, high, station, info["latitude"], info["longitude"])


class TestKingTides(unittest.TestCase):
    """Item 9: published dates at once; NOAA times only when predicted."""

    NOW = datetime(2026, 9, 27, 17, tzinfo=UTC)

    def test_published_dates_appear_months_ahead_without_noaa(self):
        rows = lunar.king_tide_opportunities(self.NOW, HOME, PACIFIC, [])
        self.assertEqual([row.start.date().isoformat() for row in rows], ["2026-11-24", "2026-12-23", "2027-01-21"])
        for row in rows:
            self.assertEqual(row.extra["evidence_state"], "schedule")
            self.assertFalse(row.extra["operational"])
            self.assertIn("NOAA", row.extra["awaiting"])
            self.assertIn("published dates", row.title)
            self.assertNotIn("tide_ft", row.extra, "no invented height")

    def test_noaa_predictions_enrich_the_window(self):
        now = datetime(2026, 11, 10, 17, tzinfo=UTC)
        tides = [tide(datetime(2026, 11, 24, 16, 10, tzinfo=UTC), 6.8, True, "Port San Luis"),
                 tide(datetime(2026, 11, 25, 16, 50, tzinfo=UTC), 7.0, True, "Port San Luis"),
                 tide(datetime(2026, 11, 25, 17, 0, tzinfo=UTC), 7.4, True, "Los Angeles")]
        rows = lunar.king_tide_opportunities(now, HOME, PACIFIC, tides)
        november = rows[0]
        self.assertTrue(november.extra["operational"])
        self.assertEqual(november.extra["tide_ft"], 7.0, "the home station, not the highest anywhere")
        self.assertEqual([row["light"] for row in november.extra["tide_predictions"]], ["daylight", "daylight"])
        self.assertIn("Port San Luis", november.extra["best_time_of_day"])
        self.assertFalse(rows[1].extra["operational"], "December is still beyond the prediction horizon")

    def test_past_windows_drop_off(self):
        rows = lunar.king_tide_opportunities(datetime(2027, 1, 1, tzinfo=UTC), HOME, PACIFIC, [])
        self.assertEqual([row.start.date().isoformat() for row in rows], ["2027-01-21"])

    def test_king_tide_is_planner_and_safety_gated(self):
        (row, *_) = lunar.king_tide_opportunities(datetime(2026, 11, 24, 15, tzinfo=UTC), HOME, PACIFIC, [])
        now = datetime(2026, 11, 24, 15, tzinfo=UTC)
        result = eligibility.assess(row, now, max_drive_hours=6.0,
                                    alerts=[alert("Coastal Flood Warning", same="006079", now=now)])
        self.assertEqual(result["safety_state"], "unsafe")
        self.assertEqual(result["presentation"], "planner")

    def test_minus_tides_exist_only_where_noaa_predicts(self):
        self.assertEqual(lunar.tide_opportunities([], self.NOW, HOME, PACIFIC), [])
        low = tide(datetime(2026, 10, 7, 18, tzinfo=UTC), -1.3, False, "Port San Luis")
        (row,) = lunar.tide_opportunities([low], self.NOW, HOME, PACIFIC)
        self.assertTrue(row.extra["operational"])
        self.assertEqual(row.extra["timing_basis"], "NOAA CO-OPS tide prediction")


class TestGrunionStation(unittest.TestCase):
    """Item 10: the beach's own station decides the hour."""

    def test_conflicting_stations_use_the_nearest(self):
        night = datetime(2026, 4, 8).date()
        tides = [tide(datetime(2026, 4, 8, 22, 0, tzinfo=UTC), 7.1, True, "Los Angeles"),
                 tide(datetime(2026, 4, 8, 21, 0, tzinfo=UTC), 6.2, True, "Santa Barbara")]
        santa_barbara = (34.418, -119.670)
        start, _ = verification.grunion_run_window(tides, night, santa_barbara)
        self.assertEqual(start, tides[1].moment + verification.GRUNION_LAG_MIN,
                         "Santa Barbara's high tide, not the higher Los Angeles one")
        self.assertEqual({row.station for row in verification.tides_for_place(tides, *santa_barbara)}, {"Santa Barbara"})

    def test_mixed_unlabelled_stations_are_refused(self):
        tides = [verification.TideEvent(datetime(2026, 4, 8, 22, tzinfo=UTC), 7.1, True, "A"),
                 verification.TideEvent(datetime(2026, 4, 8, 21, tzinfo=UTC), 6.2, True, "B")]
        self.assertEqual(verification.tides_for_place(tides, 34.4, -119.7), [])


def bird(name, latin, lat, lon, when, observer, count=None):
    return wildlife.Sighting(species=name, scientific_name=latin, place="Site", latitude=lat, longitude=lon,
                             latest=when, earliest=when, source="eBird", category="birds", observers=[observer],
                             reports=1, count=count, dates=[when.date().isoformat()])


class TestBirdViews(unittest.TestCase):
    """Item 11: one drive limit, one classification, no duplicates."""

    NOW = datetime(2026, 12, 20, 22, tzinfo=UTC)

    def test_encounter_obeys_the_drive_limit(self):
        sightings = [bird("Sandhill Crane", "Antigone canadensis", 38.156, -121.416, self.NOW - timedelta(days=day), obs, 40)
                     for day, obs in ((0, "a"), (1, "b"), (2, "c"))]
        near = birds.classify(sightings, self.NOW, HOME, 8.0)
        self.assertEqual(len(near["encounter"]), 1)
        far = birds.classify(sightings, self.NOW, HOME, 2.0)
        self.assertEqual(far["encounter"], [])

    def test_merced_crane_cant_miss_row_is_in_the_spectacle_view(self):
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        eligibility.annotate(rows, self.NOW, max_drive_hours=6.0, alerts=[])
        board = eligibility.dashboard(rows, self.NOW, birds={})
        self.assertIn("sandhill_crane_flyin", [row["phenomenon"] for row in board["events"]])
        self.assertEqual([row["phenomenon"] for row in board["birds"]["spectacle"]], ["sandhill_crane_flyin"])

    def test_spectacle_view_obeys_the_drive_limit(self):
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        eligibility.annotate(rows, self.NOW, max_drive_hours=2.0, alerts=[])
        board = eligibility.dashboard(rows, self.NOW, birds={})
        self.assertEqual(board["birds"]["spectacle"], [])

    def test_a_count_merges_and_is_not_duplicated(self):
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        count = [bird("Sandhill Crane", "Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(hours=20), obs, 4000)
                 for obs in "abc"]
        views = birds.classify(count, self.NOW, HOME, 6.0)
        leftovers = eligibility.merge_into_phenomena(rows, views["spectacle"], self.NOW)
        rows += leftovers
        eligibility.annotate(rows, self.NOW, max_drive_hours=6.0, alerts=[])
        board = eligibility.dashboard(rows, self.NOW, birds=views)
        self.assertEqual([row["phenomenon"] for row in board["birds"]["spectacle"]], ["sandhill_crane_flyin"])
        self.assertEqual([row["phenomenon"] for row in board["events"]].count("sandhill_crane_flyin"), 1)
        self.assertFalse([row for row in board["birds"]["encounter"] if row["phenomenon"] == "sandhill_crane_flyin"])


UNOWNED = (gear.TC14, gear.FAST_WIDE, gear.DEW_HEATER, gear.RAIN_COVER)


class TestGearSemantics(unittest.TestCase):
    """Item 12: TAKE/OPTIONAL/SKIP are the bag; WORTH ADDING is not; REQUIRED is safety."""

    def test_owned_lists_never_name_unowned_kit(self):
        for name in gear.PROFILES:
            with self.subTest(profile=name):
                plan = gear.recommend(name)
                self.assertTrue(gear.uses_only_owned(plan), plan)

    def test_worth_adding_is_unowned_specific_and_brief(self):
        for name in gear.PROFILES:
            plan = gear.recommend(name)
            self.assertLessEqual(len(plan.add), 2, f"{name}: no shopping list")
            for item in plan.add:
                self.assertTrue(item["why"], f"{name}: every suggestion says why")
                self.assertFalse(any(owned in item["item"] for owned in gear.OWNED), f"{name}: {item} is already owned")

    def test_suggestions_go_where_they_matter(self):
        self.assertIn(gear.TC14, [item["item"] for item in gear.recommend("raptor").add])
        for name in ("astro_wide", "meteor", "aurora", "waterfall_night", "night_beach"):
            self.assertIn(gear.FAST_WIDE, [item["item"] for item in gear.recommend(name).add], name)
        self.assertEqual(gear.recommend("wildlife_dawn").add, [], "an elk morning needs nothing new")
        self.assertIn(gear.RAIN_COVER, [item["item"] for item in gear.recommend("storm_surf").add])

    def test_the_2x_is_never_the_default(self):
        for name in gear.PROFILES:
            self.assertNotIn(gear.TC2X, gear.recommend(name).take, name)

    def test_red_headlamp_is_required_on_a_night_beach(self):
        self.assertTrue(any(gear.RED_HEADLAMP in item for item in gear.recommend("night_beach").required))

    def test_plans_do_not_share_mutable_state(self):
        first = gear.recommend("raptor")
        first.add[0]["why"] = "changed"
        self.assertNotEqual(gear.recommend("raptor").add[0]["why"], "changed")


def eclipse(kind):
    start = NOW + timedelta(days=2)
    return events.Opportunity(key=f"eclipse-{kind}", title=f"{kind.title()} solar eclipse", category="astronomy",
                              zone_id="home", zone_name="Home", start=start, end=start, score=75, detail="",
                              drive_hours=0.0, phenomenon="eclipse_solar", planning_only=True,
                              extra={"evidence_state": "computed", "eclipse_type": kind})


class TestSolarEclipseGear(unittest.TestCase):
    """Item 13: a solar event never omits the front-mounted certified filter."""

    def test_every_solar_plan_requires_a_front_filter_and_eye_protection(self):
        for kind in ("total", "annular", "hybrid", "partial"):
            with self.subTest(kind=kind):
                row = eclipse(kind)
                assess(row)
                plan = row.extra["gear_plan"]
                self.assertIn(gear.SOLAR_FILTER, plan["required"])
                self.assertIn(gear.ECLIPSE_GLASSES, plan["required"])
                self.assertIn("FRONT", plan["safety"])
                self.assertIn("ND filters", plan["safety"])
                self.assertIn("polarisers", plan["safety"])
                self.assertEqual(plan["take"], gear.LONG, "an owned lens")
                self.assertTrue(any(gear.TC2X in option for option in plan["optional"]), "the TC is optional")

    def test_only_totality_removes_the_filter(self):
        total = eclipse("total")
        assess(total)
        self.assertIn("Remove the filter only during totality", total.extra["gear_plan"]["safety"])
        annular = eclipse("annular")
        assess(annular)
        self.assertNotIn("Remove the filter", annular.extra["gear_plan"]["safety"])
        self.assertIn("stays on for the whole event", annular.extra["gear_plan"]["safety"])

    def test_the_catalog_uses_the_solar_profile(self):
        self.assertEqual(curation.CATALOG["eclipse_solar"].gear_profile, "eclipse_solar")
        self.assertIn("FRONT", curation.CATALOG["eclipse_solar"].safety)


class TestWeatherIsNotCantMiss(unittest.TestCase):
    """Item 14: weather subjects are watch signals until observed."""

    def test_thunder_is_watch_only(self):
        self.assertEqual(curation.CATALOG["thunderstorm_watch"].product_class, curation.CLASS_WATCH)
        storm = opp("thunderstorm_watch", "rare_phenomena", evidence_state="behavior_confirmed")
        self.assertFalse(assess(storm)["eligible"])

    def test_no_weather_optics_are_curated_for_the_dashboard(self):
        for word in ("lightning", "lenticular", "rainbow", "fog", "inversion", "halo", "waterspout", "sun_pillar"):
            for key, definition in curation.CATALOG.items():
                if word in key:
                    self.assertNotEqual(definition.product_class, curation.CLASS_CANT_MISS, key)

    def test_forecast_signals_never_become_rows(self):
        now = NOW
        model = forecast(now - timedelta(hours=2), weather_code=95, cloud_cover=100)
        signals = weather_hazards.watch_signals({"yosemite_valley": {"local": model}},
                                                [const.ZONES_BY_ID["yosemite_valley"]], now)
        self.assertTrue(signals)
        self.assertTrue(all(not hasattr(signal, "phenomenon") or signal.kind == "forecast" for signal in signals))
        self.assertEqual(spectacles.report_opportunities([], now, HOME), [])


class TestFractionsAreNotDates(unittest.TestCase):
    """Found during this pass: "1/2 mile" in January read as 2 January."""

    def test_fractions_are_rejected_and_dates_kept(self):
        january = datetime(2027, 1, 10, tzinfo=UTC)
        for text in ("Humpbacks 1/2 mile offshore", "about 1 1/2 hours out", "3/4 of the way to the island", "a 1/2 moon"):
            self.assertIsNone(field_reports.explicit_date(text, january), text)
        self.assertEqual(field_reports.explicit_date("Updated 1/8", january).date().isoformat(), "2027-01-08")
        self.assertEqual(field_reports.explicit_date("Trip 1/8/2027", january).date().isoformat(), "2027-01-08")


if __name__ == "__main__":
    unittest.main()
