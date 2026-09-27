"""SIGNAL -> PHENOMENON -> OPPORTUNITY: the Can't Miss gate and what feeds it.

Each test is one sentence of the 0.16.0 brief. The failure these guard against
is the old one: every sighting, season and park competing for the same five
rows on one overloaded score, so the dashboard said "15 opportunities" every
week and was stopped being read.
"""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import test_integration  # Load the pure package without Home Assistant.
from photography_events import (
    birds, const, curation, eligibility, email_reports, events, field_reports, gear, lunar,
    phenomena, signals, source_health, sunburst, weather_hazards, wildlife,
)

UTC = timezone.utc
PACIFIC = ZoneInfo("America/Los_Angeles")
HOME = const.DEFAULT_HOME


def sighting(name, latin, lat, lon, when, category, observers=("a",), count=None, place="Somewhere", **extra):
    return wildlife.Sighting(species=name, scientific_name=latin, place=place, latitude=lat, longitude=lon,
                             latest=when, earliest=when, source="iNaturalist", category=category,
                             observers=list(observers), reports=len(observers), count=count,
                             dates=[when.date().isoformat()], **extra)


def seasonal(now, sightings=None, reports=None):
    rows = events.build_seasonal_opportunities(now, 365, HOME, sightings, reports)
    eligibility.annotate(rows, now, max_drive_hours=6.0, alerts=[])
    return rows


def row(rows, key):
    return next(item for item in rows if item.phenomenon == key and item.extra.get("precision") == "peak")


def eligible(rows):
    return [item for item in rows if item.extra["assessment"]["eligible"]]


def email(body, received, subject="Field report", category=None, zone_id=None):
    return email_reports.parse_email_report(subject=subject, body=body, source_name="Test observer",
                                            received=received, category=category, zone_id=zone_id)


class TestWildlifeSignalsAreNotEvents(unittest.TestCase):
    NOW = datetime(2026, 9, 27, 17, tzinfo=UTC)

    def test_fresh_common_dolphin_presence_alone_produces_no_cant_miss_row(self):
        now = datetime(2027, 1, 5, 18, tzinfo=UTC)  # inside the calving window
        pod = [sighting("Common dolphin", "Delphinus delphis", 34.25, -119.30, now - timedelta(hours=3),
                        const.CATEGORY_MARINE, observers=("a", "b", "c"), count=400)]
        rows = seasonal(now, pod)
        rows += birds.marine_presence(pod, now, HOME)
        eligibility.annotate(rows, now, max_drive_hours=6.0, alerts=[])
        # Elephant seals and cranes are in their documented windows in January;
        # nothing marine is eligible on dolphin presence.
        self.assertEqual([item.title for item in eligible(rows) if item.category == const.CATEGORY_MARINE], [])
        self.assertEqual(row(rows, "common_dolphin_calving").extra["evidence_state"], "presence_only")

    def test_fresh_humpback_presence_alone_produces_no_standalone_row(self):
        seen = [sighting("Humpback whale", "Megaptera novaeangliae", 35.17, -120.74, self.NOW - timedelta(hours=2),
                         const.CATEGORY_MARINE, observers=("a", "b", "c"))]
        rows = seasonal(self.NOW, seen)
        self.assertFalse(any("Humpback whale" in item.title for item in rows), "no row is a raw sighting")
        self.assertEqual(eligible(rows), [])

    def test_humpback_presence_corroborates_the_watch_but_cannot_prove_lunge_feeding(self):
        seen = [sighting("Humpback whale", "Megaptera novaeangliae", 35.17, -120.74, self.NOW - timedelta(days=1),
                         const.CATEGORY_MARINE)]
        humpback = row(seasonal(self.NOW, seen), "humpback_lunge_feeding")
        self.assertEqual(humpback.extra["evidence_state"], "presence_only")
        self.assertEqual(humpback.extra["assessment"]["presentation"], "watch")
        self.assertFalse(humpback.extra["assessment"]["eligible"])

    def test_lunge_feeding_behavior_evidence_activates_the_humpback_phenomenon(self):
        reports = email("Humpbacks lunge feeding off Avila Beach this morning, bait balls everywhere.",
                        self.NOW - timedelta(hours=5), category=const.CATEGORY_MARINE)
        self.assertEqual(reports[0].phenomenon_key, "humpback_lunge_feeding")
        self.assertEqual(reports[0].observed_at, self.NOW - timedelta(hours=5), "'this morning' dates it to the message")
        humpback = row(seasonal(self.NOW, None, reports), "humpback_lunge_feeding")
        self.assertEqual(humpback.extra["evidence_state"], "behavior_confirmed")
        self.assertTrue(humpback.extra["assessment"]["eligible"], humpback.extra["assessment"]["blockers"])

    def test_elephant_seal_presence_produces_no_standalone_row(self):
        now = datetime(2026, 11, 20, 18, tzinfo=UTC)
        seals = [sighting("Northern elephant seal", "Mirounga angustirostris", 35.66, -121.26, now - timedelta(hours=4),
                          const.CATEGORY_MAMMALS, observers=("a", "b"))]
        rows = seasonal(now, seals)
        self.assertFalse(any("Northern elephant seal" in item.title for item in rows))
        self.assertEqual(eligible(rows), [])

    def test_elephant_seal_breeding_behavior_activates_the_curated_phenomenon(self):
        now = datetime(2026, 12, 12, 20, tzinfo=UTC)  # before the documented core window
        reports = email("First pups born at Piedras Blancas this morning; bulls fighting on the beach.",
                        now - timedelta(hours=6), category=const.CATEGORY_MAMMALS)
        seals = row(seasonal(now, None, reports), "elephant_seal_battles")
        self.assertEqual(seals.extra["evidence_state"], "behavior_confirmed")
        self.assertLessEqual(seals.start, now, "a dated report opens the occurrence ahead of the calendar")
        self.assertTrue(seals.extra["assessment"]["eligible"], seals.extra["assessment"]["blockers"])

    def test_elephant_seal_core_window_is_calendar_reliable(self):
        now = datetime(2027, 1, 10, 18, tzinfo=UTC)
        seals = row(seasonal(now), "elephant_seal_battles")
        self.assertEqual(seals.extra["evidence_state"], "calendar")
        self.assertTrue(seals.extra["assessment"]["eligible"])
        self.assertLess(seals.score, const.DEFAULT_ALERT_SCORE, "the planner score still carries no alert on its own")

    def test_generic_black_bear_presence_does_not_activate_the_cub_event(self):
        now = datetime(2026, 5, 1, 16, tzinfo=UTC)
        bear = [sighting("American black bear", "Ursus americanus", 37.74, -119.59, now - timedelta(hours=3),
                         const.CATEGORY_MAMMALS, observers=("a", "b", "c"))]
        cubs = row(seasonal(now, bear), "black_bear_cubs")
        self.assertNotEqual(cubs.extra["evidence_state"], "behavior_confirmed")
        self.assertFalse(cubs.extra["assessment"]["eligible"])

    def test_actual_sow_and_cub_evidence_can(self):
        now = datetime(2026, 5, 1, 16, tzinfo=UTC)
        reports = email("A sow with cubs grazing in Cook's Meadow, Yosemite Valley this morning.",
                        now - timedelta(hours=4), category=const.CATEGORY_MAMMALS)
        cubs = row(seasonal(now, None, reports), "black_bear_cubs")
        self.assertEqual(cubs.extra["evidence_state"], "behavior_confirmed")
        self.assertTrue(cubs.extra["assessment"]["eligible"], cubs.extra["assessment"]["blockers"])
        self.assertIn("between a sow", cubs.extra["ethics"])

    def test_tule_elk_rut_needs_a_nearby_report_for_the_encounter(self):
        without = row(seasonal(self.NOW), "tule_elk_rut")
        self.assertFalse(without.extra["assessment"]["eligible"])
        elk = [sighting("Tule elk", "Cervus canadensis nannodes", 35.20, -119.80, self.NOW - timedelta(days=2),
                        const.CATEGORY_MAMMALS)]
        found = row(seasonal(self.NOW, elk), "tule_elk_rut")
        self.assertEqual(found.extra["evidence_state"], "calendar_presence")
        self.assertTrue(found.extra["assessment"]["eligible"], "a park/monument spectacle can reach Can't Miss")


class TestBirds(unittest.TestCase):
    NOW = datetime(2026, 9, 27, 17, tzinfo=UTC)

    def _ebird(self, **overrides):
        base = test_integration._ebird_entry(obsDt="2026-09-27 08:00")
        base.update(overrides)
        return base

    def test_painted_bunting_is_bird_chase_not_cant_miss(self):
        sightings = wildlife.parse_ebird([self._ebird(comName="Painted Bunting", sciName="Passerina ciris")], UTC)
        views = birds.classify(sightings, self.NOW, HOME, 6.0)
        self.assertEqual(views["spectacle"], [])
        self.assertEqual([row["species"] for row in views["chase"]], ["Painted Bunting"])
        board = eligibility.dashboard([], self.NOW, birds=views)
        self.assertEqual(board["events"], [])
        self.assertEqual(board["birds"]["chase"][0]["species"], "Painted Bunting")

    def test_repeated_condor_reports_are_a_bird_encounter(self):
        condors = [sighting("California condor", "Gymnogyps californianus", 36.49, -121.19,
                            self.NOW - timedelta(days=d), const.CATEGORY_BIRDS, observers=(f"o{d}",), count=1)
                   for d in (0, 1, 3)]
        views = birds.classify(condors, self.NOW, HOME, 6.0)
        self.assertEqual(views["spectacle"], [])
        self.assertEqual(views["encounter"][0]["species"], "California condors")
        self.assertEqual(views["encounter"][0]["site"], "Pinnacles High Peaks")

    def test_condor_concentration_can_reach_cant_miss(self):
        condors = [sighting("California condor", "Gymnogyps californianus", 36.49, -121.19,
                            self.NOW - timedelta(hours=h), const.CATEGORY_BIRDS, observers=(f"o{h}",), count=c)
                   for h, c in ((3, 4), (26, 2), (50, 1))]
        views = birds.classify(condors, self.NOW, HOME, 6.0)
        self.assertEqual(len(views["spectacle"]), 1)
        spectacle = views["spectacle"][0]
        eligibility.assess(spectacle, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertTrue(spectacle.extra["assessment"]["eligible"], spectacle.extra["assessment"]["blockers"])
        self.assertIn("Prohibited", spectacle.extra["gear_plan"]["drone"], "Pinnacles is a national park")

    def test_raw_bird_sightings_remain_available_for_corroboration(self):
        now = datetime(2026, 12, 20, 22, tzinfo=UTC)
        cranes = [sighting("Sandhill crane", "Antigone canadensis", 37.18, -120.60, now - timedelta(days=1),
                           const.CATEGORY_BIRDS, count=3200)]
        crane = row(seasonal(now, cranes), "sandhill_crane_flyin")
        self.assertEqual(crane.extra["evidence_state"], "calendar_presence")
        self.assertEqual(signals.from_sighting(cranes[0]).count, 3200)

    def test_a_crane_count_merges_into_the_fly_in_instead_of_a_second_row(self):
        now = datetime(2026, 12, 20, 22, tzinfo=UTC)
        cranes = [sighting("Sandhill crane", "Antigone canadensis", 37.18, -120.60, now - timedelta(hours=h),
                           const.CATEGORY_BIRDS, observers=(f"o{h}",), count=3200) for h in (3, 30)]
        rows = seasonal(now, cranes)
        views = birds.classify(cranes, now, HOME, 6.0)
        leftovers = eligibility.merge_into_phenomena(rows, views["spectacle"], now)
        self.assertEqual(leftovers, [])
        self.assertEqual(sum(1 for item in rows if item.phenomenon == "sandhill_crane_flyin"
                             and item.extra.get("precision") == "peak"), 1)
        self.assertEqual(row(rows, "sandhill_crane_flyin").extra["evidence_state"], "behavior_confirmed")


class TestReportsMergeIntoPhenomena(unittest.TestCase):
    def test_a_dated_hotline_report_is_merged_not_listed_beside_the_window(self):
        now = datetime(2026, 9, 27, 17, tzinfo=UTC)
        page = """<div class="entry-content"><h3>Bishop Creek - Go Now! (Sept 25)</h3>
        <p>North Lake and Lake Sabrina aspen are at peak color, go now.</p></div>"""
        source = field_reports.REPORT_SOURCES[2]
        reports = field_reports.parse_report(page, source, now)
        self.assertEqual(reports[0].observed_at.date().isoformat(), "2026-09-25", "the page's own date, not the fetch")
        rows = seasonal(now, None, reports)
        aspen = row(rows, "aspen_tier1_high")
        self.assertEqual(aspen.extra["evidence_state"], "behavior_confirmed")
        merged = {ident for item in rows for ident in item.extra.get("merged_reports", [])}
        unmatched = [r for r in reports if events.report_id(r) not in merged]
        self.assertEqual(unmatched, [], "the report enriches the phenomenon; no duplicate row")
        self.assertTrue(aspen.extra["assessment"]["eligible"], aspen.extra["assessment"]["blockers"])

    def test_an_undated_hotline_report_is_shown_as_undated_and_does_not_activate(self):
        now = datetime(2026, 9, 27, 17, tzinfo=UTC)
        page = """<div class="entry-content"><h3>Bishop Creek</h3><p>North Lake aspen near peak, go now.</p></div>"""
        reports = field_reports.parse_report(page, field_reports.REPORT_SOURCES[2], now)
        self.assertIsNone(reports[0].observed_at, "download time never becomes an observation time")
        aspen = row(seasonal(now, None, reports), "aspen_tier1_high")
        self.assertEqual(aspen.extra["evidence_state"], "reported_undated")
        self.assertFalse(aspen.extra["assessment"]["eligible"])

    def test_monarchs_need_a_count_and_a_cold_dawn(self):
        now = datetime(2026, 12, 1, 18, tzinfo=UTC)
        observed = [sighting("Monarch", "Danaus plexippus", 35.13, -120.63, now - timedelta(hours=3), const.CATEGORY_RARE)]
        grove = row(seasonal(now, observed), "pismo_monarchs")
        self.assertFalse(grove.extra["assessment"]["eligible"], "one monarch observation is not an active roost")
        low = email("About 400 monarchs clustering at the Pismo grove today.", now - timedelta(hours=2),
                    category=const.CATEGORY_RARE)
        self.assertEqual(low[0].count, 400)
        self.assertFalse(row(seasonal(now, None, low), "pismo_monarchs").extra["assessment"]["eligible"])
        high = email("2,300 monarchs in dense clusters at the Pismo grove this morning.", now - timedelta(hours=2),
                     category=const.CATEGORY_RARE)
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, high)
        grove = row(rows, "pismo_monarchs")
        grove.extra["dawn_temp_f"] = 61
        eligibility.assess(grove, now, max_drive_hours=6.0, alerts=[])
        self.assertFalse(grove.extra["assessment"]["eligible"], "a warm dawn disperses the clusters")
        grove.extra["dawn_temp_f"] = 48
        eligibility.assess(grove, now, max_drive_hours=6.0, alerts=[])
        self.assertTrue(grove.extra["assessment"]["eligible"], grove.extra["assessment"]["blockers"])

    def test_evidence_expires(self):
        now = datetime(2026, 9, 27, 17, tzinfo=UTC)
        old = email("Humpbacks lunge feeding off Avila Beach on Sept 5.", now, category=const.CATEGORY_MARINE)
        self.assertEqual(old[0].observed_at.date().isoformat(), "2026-09-05")
        humpback = row(seasonal(now, None, old), "humpback_lunge_feeding")
        self.assertNotEqual(humpback.extra["evidence_state"], "behavior_confirmed")
        self.assertFalse(humpback.extra["assessment"]["eligible"])

    def test_bioluminescence_needs_a_report_and_a_dark_moon(self):
        now = datetime(2026, 10, 9, 18, tzinfo=UTC)
        self.assertFalse(any(item.phenomenon == "bioluminescent_surf"
                             for item in __import__("photography_events.spectacles", fromlist=["x"]).watch_opportunities(now, HOME)),
                         "no year-long glowing-surf row")
        from photography_events import spectacles
        report = email("Bioluminescent waves glowing blue at Pismo Beach last night and today.", now - timedelta(hours=3),
                       category=const.CATEGORY_RARE)
        rows = spectacles.report_opportunities(report, now, HOME)
        self.assertEqual([item.phenomenon for item in rows], ["bioluminescent_surf"])
        eligibility.assess(rows[0], now, max_drive_hours=6.0, alerts=[])
        moon = rows[0].extra["moon_illumination"]
        self.assertEqual(rows[0].extra["assessment"]["eligible"], moon < 0.5)


class TestGate(unittest.TestCase):
    NOW = datetime(2027, 1, 10, 18, tzinfo=UTC)

    def test_generic_park_windows_never_reach_cant_miss(self):
        parks = events.build_park_opportunities(self.NOW, 60)
        eligibility.annotate(parks, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertTrue(parks)
        self.assertEqual(eligible(parks), [])
        self.assertTrue(all(item.extra["assessment"]["presentation"] == "planner" for item in parks))

    def test_the_six_hour_gate_applies_and_planning_only_does_not_bypass_it(self):
        seals = row(seasonal(self.NOW), "elephant_seal_battles")
        self.assertTrue(seals.extra["assessment"]["eligible"])
        seals.drive_hours, seals.planning_only = 6.5, True
        eligibility.assess(seals, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertFalse(seals.extra["assessment"]["eligible"])
        self.assertTrue(any("drive limit" in blocker for blocker in seals.extra["assessment"]["blockers"]))
        self.assertIn(seals, events.within_drive([seals], 6.0), "the planner keeps the long trip")

    def test_zero_eligible_events_is_a_healthy_empty_state(self):
        board = eligibility.dashboard([], self.NOW)
        self.assertEqual(board["events"], [])
        self.assertEqual(board["headline"], "Nothing worth changing plans for this week.")

    def test_significance_is_not_confidence(self):
        seals = row(seasonal(self.NOW), "elephant_seal_battles")
        assessment = seals.extra["assessment"]
        for key in ("significance", "confidence", "urgency", "encounter", "access", "actionable", "eligible", "priority"):
            self.assertIn(key, assessment)
        self.assertEqual(assessment["significance"], curation.CATALOG["elephant_seal_battles"].significance)

    def test_unsafe_weather_cannot_produce_a_go_now_recommendation(self):
        seals = row(seasonal(self.NOW), "elephant_seal_battles")
        warning = [{"event": "High Wind Warning", "headline": "High Wind Warning for the SLO coast",
                    "onset": (self.NOW - timedelta(hours=1)).isoformat(), "ends": (self.NOW + timedelta(days=1)).isoformat(),
                    "same": ["006079"], "geometry": None}]
        eligibility.assess(seals, self.NOW, max_drive_hours=6.0, alerts=warning)
        self.assertFalse(seals.extra["assessment"]["eligible"])
        self.assertTrue(seals.extra["assessment"]["unsafe"])
        self.assertFalse(events.alert_candidate(seals, 0))
        self.assertIn("not a storm-chasing system", seals.extra["safety_summary"])

    def test_a_failed_alert_feed_is_not_read_as_all_clear(self):
        seals = row(seasonal(self.NOW), "elephant_seal_battles")
        eligibility.assess(seals, self.NOW, max_drive_hours=6.0, alerts=None)
        self.assertIn("unavailable", seals.extra["safety_summary"])

    def test_polygon_alerts_are_matched_by_geometry(self):
        box = {"type": "Polygon", "coordinates": [[[-121.5, 35.4], [-121.0, 35.4], [-121.0, 35.9], [-121.5, 35.9], [-121.5, 35.4]]]}
        self.assertTrue(weather_hazards.in_geometry(35.66, -121.26, box))
        self.assertFalse(weather_hazards.in_geometry(34.74, -120.57, box))

    def test_stale_forecast_data_cannot_remain_falsely_active(self):
        sky = events.Opportunity(key="sky", title="Sunset could be exceptional tonight", category="sunset", zone_id="home",
                                 zone_name="Home", start=self.NOW, end=self.NOW + timedelta(hours=1), score=92, detail="",
                                 drive_hours=0.0, phenomenon="sunset_local",
                                 extra={"evidence_state": "forecast", "standout": True, "light_path": "modelled"})
        eligibility.assess(sky, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertTrue(sky.extra["assessment"]["eligible"])
        source_health.annotate([sky], {"weather": {"state": "stale", "name": "Weather", "impact": ""}})
        eligibility.assess(sky, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertFalse(sky.extra["assessment"]["eligible"], "the local model's own forecast is required")

    def test_duplicate_rows_collapse_to_one_occurrence(self):
        zones = [const.ZONES_BY_ID["carrizo_plain"], const.ZONES_BY_ID["death_valley"]]
        now = datetime(2026, 7, 10, 12, tzinfo=UTC)
        rows = []
        for zone in zones:
            rows += events.build_milky_way_opportunities(zone, now, 7, lambda _: 0)
        for item in rows:
            item.extra["assessment"] = {"eligible": True, "priority": item.score, "significance": 70}
        board = eligibility.dashboard(rows, now)
        self.assertLessEqual(len(board["events"]), 2, "consecutive nights at many sites are one lunar window")

    def test_suppressed_occurrences_leave_the_dashboard(self):
        seals = row(seasonal(self.NOW), "elephant_seal_battles")
        board = eligibility.dashboard([seals], self.NOW, suppressed=lambda key: True)
        self.assertEqual(board["events"], [])
        self.assertEqual(board["suppressed_count"], 1)

    def test_the_planner_keeps_everything_and_signals_are_not_lost(self):
        rows = seasonal(self.NOW) + events.build_park_opportunities(self.NOW, 365)
        eligibility.annotate(rows, self.NOW, max_drive_hours=6.0, alerts=[])
        planner = events.planning_slice(rows, 400)
        self.assertEqual(len(planner), len(rows))
        self.assertTrue(any(item.phenomenon == "park_season" for item in planner))
        observed = [signals.from_sighting(sighting("Fin whale", "Balaenoptera physalus", 34.3, -119.5,
                                                   self.NOW - timedelta(hours=2), const.CATEGORY_MARINE))]
        board = eligibility.dashboard(rows, self.NOW, signals=observed)
        self.assertEqual(board["signals"][0]["subject"], "Fin whale")
        self.assertTrue(all("presentation" in item.compact() for item in rows))


class TestSunset(unittest.TestCase):
    def _home(self):
        return {"id": "home", "name": "Home coast", "latitude": HOME[0], "longitude": HOME[1],
                "drive_hours": 0.0, "bortle": 4, "specialties": ("sunset",)}

    def _upstream(self, low):
        forecast = test_integration._multiday(0, 0, low, 60, 0)
        return {"sunset": forecast, "sunrise": forecast}

    def test_ordinary_vandenberg_sunset_creates_no_main_event(self):
        now = test_integration.NOW
        flat = test_integration._multiday(0, 5, 10, 70, 0)
        rows = events.build_sunset_opportunities(self._home(), flat, now, 85, 3, self._upstream(90))
        eligibility.annotate(rows, now, max_drive_hours=6.0, alerts=[], sunset_drive_hours=1.0)
        self.assertEqual(eligible(rows), [])

    def test_exceptional_local_sunset_can(self):
        now = test_integration.NOW
        canvas = test_integration._multiday(55, 20, 5, 55, 0)
        rows = events.build_sunset_opportunities(self._home(), canvas, now, 80, 2, self._upstream(5))
        eligibility.annotate(rows, now, max_drive_hours=6.0, alerts=[], sunset_drive_hours=1.0)
        sunsets = [item for item in rows if "Sunset" in item.title]
        self.assertTrue(sunsets)
        self.assertTrue(any(item.extra["assessment"]["eligible"] for item in sunsets),
                        [item.extra["assessment"]["blockers"] for item in sunsets])
        self.assertTrue(all(item.zone_id == "home" for item in rows))

    def test_provider_top_tier_is_primary_and_failure_falls_back(self):
        now = test_integration.NOW
        lukewarm = test_integration._multiday(15, 10, 20, 70, 0)
        home = self._home()
        import math
        sunset = next(moment for moment in (events.astro.sun_event(now + timedelta(days=d), math.radians(HOME[0]),
                                                                   math.radians(HOME[1]), rising=False) for d in (0, 1))
                      if moment and moment > now)
        great = [{"kind": "sunset", "quality": "Great", "percent": 88.0, "valid_at": sunset, "last_updated": None, "model": "GFS"}]
        rows = events.build_sunset_opportunities(home, lukewarm, now, 85, 2, self._upstream(5), provider=great)
        self.assertEqual(len([r for r in rows if "Sunset" in r.title]), 1, "SunsetWx's Great is listed despite a lukewarm local model")
        eligibility.annotate(rows, now, max_drive_hours=6.0, alerts=[])
        self.assertTrue(rows[0].extra["assessment"]["eligible"])
        self.assertIn("not a probability", rows[0].extra["provider_note"])
        # Provider down: nothing from it, and the local model decides alone.
        self.assertEqual(sunburst.parse_quality({"error": "unauthorized"}), [])
        self.assertEqual(sunburst.parse_quality(None), [])
        fallback = events.build_sunset_opportunities(home, lukewarm, now, 85, 2, self._upstream(5), provider=[])
        self.assertEqual(fallback, [])

    def test_provider_payload_parses_the_published_shape(self):
        payload = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
            "type": "Sunset", "quality": "Fair", "quality_percent": 37.51, "quality_value": -147.696,
            "valid_at": "2019-07-01T03:36:00Z", "last_updated": "2019-06-30T12:00:00Z", "source": "NAM"}}]}
        parsed = sunburst.parse_quality(payload)
        self.assertEqual(parsed[0]["quality"], "Fair")
        self.assertEqual(parsed[0]["kind"], "sunset")
        url, headers, form = sunburst.login_request("id", "secret")
        self.assertTrue(headers["Authorization"].startswith("Basic "))
        self.assertEqual(form["grant_type"], "client_credentials")


class TestLunarEngine(unittest.TestCase):
    def test_annual_full_moons_rank_by_distance_against_published_anchors(self):
        moons = lunar.rank_by_year(lunar.full_moons(datetime(2026, 1, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)))
        by_rank = {moon.distance_rank: moon for moon in moons}
        closest = by_rank[1]
        self.assertEqual(closest.instant.date().isoformat(), "2026-12-24")
        self.assertAlmostEqual(closest.distance_km, 356758, delta=100)  # EarthSky/NASA published
        self.assertEqual(by_rank[2].instant.date().isoformat(), "2026-11-24")
        self.assertAlmostEqual(by_rank[2].distance_km, 360800, delta=100)
        farthest = by_rank[len(moons)]
        self.assertIn("micromoon", farthest.labels[0])
        self.assertGreater(closest.diameter_arcmin, farthest.diameter_arcmin)
        self.assertTrue(closest.nolle_supermoon)

    def test_moonrise_and_moonset_geometry_is_exposed(self):
        now = datetime(2026, 12, 20, 18, tzinfo=UTC)
        rows = lunar.opportunities(now, HOME, PACIFIC, horizon_days=10)
        extra = rows[0].extra
        for key in ("moonrise", "moonset", "moonrise_azimuth", "moonrise_compass", "moonset_azimuth", "sunset",
                    "civil_dusk", "nautical_dusk", "astronomical_dusk", "sunrise", "rise_after_sunset_minutes"):
            self.assertIn(key, extra)
        self.assertEqual([step["altitude"] for step in extra["moon_climb"]], [0, 1, 2, 5, 10])
        self.assertTrue(40 < extra["moonrise_azimuth"] < 80, "a December full Moon rises north of east")
        self.assertTrue(extra["king_tide"], "24 Dec coincides with the published King Tide dates")
        self.assertIn("No landmark alignment", extra["access_note"])

    def test_the_closest_full_moon_can_qualify(self):
        now = datetime(2026, 12, 20, 18, tzinfo=UTC)
        closest = next(row for row in lunar.opportunities(now, HOME, PACIFIC, horizon_days=10)
                       if row.phenomenon == "full_moon_closest")
        eligibility.assess(closest, now, max_drive_hours=6.0, alerts=[])
        self.assertTrue(closest.extra["assessment"]["eligible"], closest.extra["assessment"]["blockers"])
        self.assertIn("200-600", closest.extra["gear_plan"]["take"])

    def test_an_ordinary_full_moon_does_not_qualify(self):
        now = datetime(2026, 10, 22, 18, tzinfo=UTC)
        ordinary = next(row for row in lunar.opportunities(now, HOME, PACIFIC, horizon_days=10))
        self.assertEqual(ordinary.phenomenon, "full_moon")
        eligibility.assess(ordinary, now, max_drive_hours=6.0, alerts=[])
        self.assertFalse(ordinary.extra["assessment"]["eligible"])
        self.assertEqual(ordinary.extra["assessment"]["presentation"], "planner")


class TestGear(unittest.TestCase):
    def test_gear_advice_uses_owned_equipment(self):
        for profile in gear.PROFILES:
            plan = gear.recommend(profile)
            self.assertTrue(gear.uses_only_owned(plan), profile)

    def test_the_teleconverter_is_optional_never_preferred(self):
        for profile, spec in gear.PROFILES.items():
            self.assertNotIn("Teleconverter", spec["take"], profile)
        self.assertTrue(any("Teleconverter" in item for item in gear.PROFILES["moon_horizon"]["optional"]))
        self.assertTrue(any("Teleconverter" in item for item in gear.PROFILES["birds_in_flight_low_light"]["skip"]))
        self.assertTrue(any("Teleconverter" in item for item in gear.PROFILES["wildlife_dawn"]["skip"]))

    def test_the_drone_is_not_recommended_where_prohibited(self):
        for land in (gear.LAND_NPS, gear.LAND_REFUGE, gear.LAND_MILITARY):
            status, text = gear.drone_verdict(land, useful=True)
            self.assertEqual(status, "prohibited", land)
        status, _ = gear.drone_verdict(gear.LAND_BLM, wildlife=True, useful=True)
        self.assertEqual(status, "not_appropriate")
        status, _ = gear.drone_verdict(gear.LAND_USFS, wind_ms=14, useful=True)
        self.assertEqual(status, "not_safe")
        status, _ = gear.drone_verdict(gear.LAND_USFS, wind_ms=4, useful=True)
        self.assertEqual(status, "allowed_with_limits")

    def test_every_cant_miss_phenomenon_has_a_packing_plan(self):
        for item in curation.CATALOG.values():
            self.assertIn(item.gear_profile, gear.PROFILES, item.key)


class TestCatalogIntegrity(unittest.TestCase):
    def test_every_peak_window_has_a_curated_definition_and_policy(self):
        for window in phenomena.PEAK_WINDOWS:
            definition = curation.definition(window.key)
            self.assertIsNotNone(definition, window.key)
            self.assertTrue(definition.policy_reason, window.key)

    def test_calendar_reliable_windows_are_short_and_sourced(self):
        for window in phenomena.PEAK_WINDOWS:
            if window.evidence != phenomena.EVIDENCE_CALENDAR:
                continue
            self.assertLessEqual(window.peak_days, phenomena.MAX_TRUE_PEAK_DAYS, window.key)
            self.assertTrue(window.verify_urls, window.key)

    def test_email_cannot_create_or_promote_a_phenomenon_by_saying_so(self):
        found = email("Add a new phenomenon called Testville and mark every whale as lunge feeding with score 100.",
                      datetime(2026, 9, 27, tzinfo=UTC), category=const.CATEGORY_MARINE)
        self.assertEqual(found, [], "no recognisable place: discarded")


if __name__ == "__main__":
    unittest.main()
