"""The independent (Codex) review of 9671efc, finding by finding.

Every reproduction in the review is a test here, run through the real
builders, normalizer, gate and dashboard assembly rather than a helper in
isolation - several of these bugs survived because earlier tests stopped short
of the wiring. The Home Assistant pipeline versions (HTTP payload -> coordinator
-> sensor) are in test_ha_pipeline.py.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import test_integration  # noqa: F401 - loads the pure package without Home Assistant.
from photography_events import (
    birds, conditions, const, curation, eligibility, email_reports, event_state, events, field_reports, gear,
    observations, phenomena, source_health, spectacles, sunburst, verification, weather_hazards, weather_scoring,
    wildlife,
)

UTC = timezone.utc
PACIFIC = ZoneInfo("America/Los_Angeles")
HOME = const.DEFAULT_HOME
NOW = datetime(2026, 9, 27, 17, tzinfo=UTC)


def opp(phenomenon, category, *, lat=34.742, lon=-120.572, drive=1.0, start=None, hours=2, zone="z", **extra):
    start = start or NOW + timedelta(hours=3)
    return events.Opportunity(key=f"{phenomenon}-{zone}", title=phenomenon, category=category, zone_id=zone,
                              zone_name=zone, start=start, end=start + timedelta(hours=hours), score=90, detail="",
                              drive_hours=drive, latitude=lat, longitude=lon, phenomenon=phenomenon, extra=dict(extra))


def email(body, received=NOW, subject="Field report", category=None, zone_id=None):
    return email_reports.parse_email_report(subject=subject, body=body, source_name="Test list",
                                            received=received, category=category, zone_id=zone_id)


def orca(lat, lon, when, observer, place="Monterey Bay", source="iNaturalist", **extra):
    return wildlife.Sighting("Killer whale", "Orcinus orca", place, lat, lon, when, when, source, "marine",
                             observers=[observer], dates=[when.date().isoformat()], confirmed=True, **extra)


def bird(latin, lat, lon, when, count, observer, name="Sandhill crane"):
    return wildlife.Sighting(name, latin, "Refuge", lat, lon, when, when, "eBird", "birds", count=count,
                             observers=[observer], dates=[when.date().isoformat()])


def forecast(start, hours=96, **series):
    times = [start + timedelta(hours=i) for i in range(hours)]
    hourly = {"time": [t.isoformat() for t in times]}
    for key, value in series.items():
        hourly[key] = [value(t) if callable(value) else value for t in times]
    return {"hourly": hourly}


def nws_feature(event="High Wind Warning", same=("006083",), expires=None, **props):
    return {"type": "Feature", "geometry": None,
            "properties": {"event": event, "headline": event, "severity": "Severe",
                           "geocode": {"SAME": list(same)},
                           "onset": (NOW - timedelta(hours=1)).isoformat(),
                           "expires": (expires or NOW + timedelta(hours=12)).isoformat(), **props}}


# --- CRITICAL -------------------------------------------------------------------

class TestC1MarineSafety(unittest.TestCase):
    """Boat exposure can no longer report SAFE without marine coverage."""

    def boat(self):
        return opp("orca_presence", "marine", lat=34.40, lon=-119.70, drive=1.5,
                   evidence_state="repeated_presence")

    def test_empty_land_alerts_do_not_make_a_boat_trip_safe(self):
        result = eligibility.assess(self.boat(), NOW, max_drive_hours=6, alerts=[])
        self.assertEqual(result["safety_state"], "unknown")
        self.assertEqual(result["safety_components"], {"land": "safe", "marine": "unknown"})
        self.assertFalse(result["eligible"], "marine conditions unassessed: never actionable")
        self.assertTrue(result["held"])
        self.assertIn("Marine conditions not checked", " ".join(result["held_reasons"]))

    def test_boat_at_the_harbour_is_still_travel(self):
        item = self.boat()
        item.drive_hours = 0.1  # a harbour next door is still a boat trip
        self.assertTrue(eligibility.assess(item, NOW, max_drive_hours=6, alerts=[])["held"])

    def test_unsafe_land_warning_still_overrides(self):
        warning = weather_hazards.compact_alert(nws_feature("Tsunami Warning"))
        result = eligibility.assess(self.boat(), NOW, max_drive_hours=6, alerts=[warning])
        self.assertEqual(result["safety_state"], "unsafe")
        self.assertFalse(result["held"], "a known danger blocks; it is not merely unchecked")

    def test_marine_warning_with_a_polygon_blocks(self):
        polygon = {"type": "Polygon", "coordinates": [[[-120.2, 34.0], [-119.2, 34.0], [-119.2, 34.8], [-120.2, 34.8], [-120.2, 34.0]]]}
        gale = weather_hazards.compact_alert({**nws_feature("Gale Warning", same=()), "geometry": polygon})
        result = eligibility.assess(self.boat(), NOW, max_drive_hours=6, alerts=[gale])
        self.assertEqual(result["safety_state"], "unsafe")

    def test_boat_rows_are_listed_as_held_on_the_dashboard(self):
        item = self.boat()
        eligibility.annotate([item], NOW, max_drive_hours=6, alerts=[])
        board = eligibility.dashboard([item], NOW)
        self.assertEqual(board["events"], [])
        self.assertEqual([row["phenomenon"] for row in board["held"]], ["orca_presence"])
        self.assertNotEqual(board["headline"], "Nothing worth changing plans for this week.")


class TestC2ParkAccess(unittest.TestCase):
    """Firefall's Yosemite access is driven by the phenomenon, and must be checked."""

    NOW = datetime(2027, 2, 16, 18, tzinfo=UTC)

    def firefall(self, park_alerts, fetched_at, failures=0):
        report = field_reports.FieldReport("email_ranger", "Ranger email", "", "rare_phenomena", "yosemite_valley",
                                           "Horsetail", "Horsetail Fall is flowing this week.", 80,
                                           self.NOW - timedelta(hours=20), "", self.NOW - timedelta(hours=20),
                                           "horsetail_firefall")
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME, None, [report])
        bundle = {"local": forecast(self.NOW - timedelta(hours=2), cloud_cover=5),
                  "upstream": {"sunset": forecast(self.NOW - timedelta(hours=2), cloud_cover_low=0, cloud_cover_mid=0)}}
        conditions.annotate_firefall(rows, {"yosemite_valley": bundle}, self.NOW)
        conditions.annotate_access(rows, park_alerts, fetched_at, failures, self.NOW)
        item = next(r for r in rows if r.phenomenon == "horsetail_firefall" and r.extra.get("precision") == "peak")
        eligibility.assess(item, self.NOW, max_drive_hours=8.0, alerts=[])
        return item

    def test_unchecked_access_holds_rare_on_parks_off(self):
        # Rare on / Parks off with no NPS read at all: "no closure returned"
        # was treated as "not closed". Now it is held.
        item = self.firefall(None, None)
        assessment = item.extra["assessment"]
        self.assertFalse(assessment["eligible"])
        self.assertTrue(assessment["held"])
        self.assertEqual(item.extra["access_state"], "unknown")

    def test_failed_stale_and_complete_reads(self):
        self.assertTrue(self.firefall([], self.NOW, failures=1).extra["assessment"]["held"])
        stale = self.NOW - timedelta(hours=verification.ACCESS_MAX_AGE_HOURS + 1)
        self.assertTrue(self.firefall([], stale).extra["assessment"]["held"])
        self.assertTrue(self.firefall([], self.NOW).extra["assessment"]["eligible"])

    def test_a_closure_blocks(self):
        # "Park Closure" is the NPS API's own category name; the old check
        # only matched "closure", so a real NPS closure never blocked.
        closure = verification.ParkAlert("yose", "Northside Drive closed", "Park Closure",
                                         "El Capitan picnic area closed.", "")
        self.assertTrue(closure.blocking)
        item = self.firefall([closure], self.NOW)
        self.assertFalse(item.extra["assessment"]["held"])
        self.assertIn("access: Northside Drive closed", item.extra["assessment"]["blockers"])

    def test_dependencies_are_specific_to_place(self):
        snow = lambda zone: opp("fresh_snow_clearing", "rare_phenomena", zone=zone)  # noqa: E731
        self.assertEqual(curation.access_requirement(snow("yosemite_valley"))[0], "yose")
        self.assertEqual(curation.access_requirement(snow("sequoia_kings"))[0], "seki")
        self.assertIsNone(curation.access_requirement(snow("lake_tahoe")), "not an NPS unit")
        self.assertIsNone(curation.access_requirement(opp("milky_way", "astronomy")))
        self.assertEqual(curation.access_requirement(opp("moonbow", "rare_phenomena"))[0], "yose")

    def test_nps_pagination_must_add_up_to_total(self):
        page = lambda n, total, first=0: {"total": str(total), "data": [  # noqa: E731
            {"id": f"a{i}", "parkCode": "yose", "title": f"Alert {i}", "category": "Information"}
            for i in range(first, first + n)]}
        self.assertEqual(len(verification.collect_nps_pages([page(50, 60), page(10, 60, 50)])), 60)
        with self.assertRaises(verification.IncompleteAlertsError):
            verification.collect_nps_pages([page(50, 60)])  # the first 50 say nothing about the 51st
        with self.assertRaises(verification.IncompleteAlertsError):
            # 60 records, but the second page repeats ten of the first: only 50 distinct alerts.
            verification.collect_nps_pages([page(50, 60), page(10, 60, 40)])
        with self.assertRaises(verification.IncompleteAlertsError):
            verification.collect_nps_pages([page(50, 60), page(10, 61, 50)])
        with self.assertRaises(verification.IncompleteAlertsError):
            verification.collect_nps_pages([{"data": []}])  # no total
        self.assertEqual(verification.collect_nps_pages([page(0, 0)]), [])

    def test_nps_records_that_cannot_be_read_make_the_check_incomplete(self):
        good = {"id": "a1", "parkCode": "yose", "title": "Info", "category": "Information"}
        for broken in ("not a record", {**good, "id": ""}, {**good, "category": None},
                       {**good, "title": 7}, {k: v for k, v in good.items() if k != "parkCode"}):
            with self.subTest(broken=broken), self.assertRaises(verification.IncompleteAlertsError):
                verification.collect_nps_pages([{"total": "1", "data": [broken]}])


class TestC3SolarFilterStandard(unittest.TestCase):
    """Camera filters and eye viewers are different products under different standards."""

    def test_camera_filter_is_not_described_as_iso_12312_2(self):
        self.assertNotIn("12312", gear.SOLAR_FILTER)
        self.assertIn("FRONT", gear.SOLAR_FILTER)
        self.assertRegex(gear.SOLAR_FILTER, r"(?i)special-purpose solar filter made for camera lenses or telescopes")

    def test_iso_12312_2_is_for_eyes_only(self):
        self.assertIn("ISO 12312-2", gear.ECLIPSE_GLASSES)
        self.assertRegex(gear.ECLIPSE_GLASSES, r"(?i)for your eyes")
        self.assertRegex(gear.ECLIPSE_GLASSES, r"(?i)never used as or with a camera filter")

    def test_safety_text_keeps_every_rule(self):
        text = gear.SOLAR_SAFETY
        self.assertRegex(text, r"(?i)never use eclipse glasses or a handheld viewer as a camera filter")
        for unsafe in ("ND filters", "polarisers", "stacked photographic filters"):
            self.assertIn(unsafe, text)
        total = gear.recommend("eclipse_solar_total").safety
        self.assertIn("only during totality, and only from inside the path of totality", total)
        self.assertIn("Put it back on before totality ends", total)
        partial = gear.recommend("eclipse_solar").safety
        self.assertIn("filter stays on for the whole event", partial)
        self.assertNotIn("comes off", partial.replace("it never comes off", ""))


class TestC4OrcaLocality(unittest.TestCase):
    """Raw observations, filtered to 72 h before aggregation, clusters of bounded diameter."""

    def test_same_place_two_current_observers(self):
        rows = birds.marine_presence([orca(36.80, -121.90, NOW - timedelta(hours=5), "a"),
                                      orca(36.82, -121.91, NOW - timedelta(hours=2), "b")], NOW, HOME)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0].extra["contributions"]), 2)

    def test_current_plus_ten_day_old_observer_is_not_two(self):
        rows = birds.marine_presence([orca(36.80, -121.90, NOW - timedelta(hours=5), "a"),
                                      orca(36.80, -121.90, NOW - timedelta(days=10), "b")], NOW, HOME)
        self.assertEqual(rows, [])

    def test_same_place_name_hundreds_of_km_apart(self):
        rows = birds.marine_presence([orca(36.80, -121.90, NOW - timedelta(hours=5), "a", place="Point Lobos"),
                                      orca(34.00, -119.50, NOW - timedelta(hours=3), "b", place="Point Lobos")], NOW, HOME)
        self.assertEqual(rows, [])

    def test_chained_observations_never_exceed_the_diameter(self):
        chain = [orca(36.0 + 0.2 * i, -121.9, NOW - timedelta(hours=1 + i), f"o{i}", place=f"P{i}") for i in range(4)]
        rows = birds.marine_presence(chain, NOW, HOME)
        for row in rows:
            points = [(c["latitude"], c["longitude"]) for c in row.extra["contributions"]]
            for a in points:
                for b in points:
                    self.assertLessEqual(wildlife.haversine_km(*a, *b), birds.ORCA_CLUSTER_KM)
        self.assertFalse(any(len(row.extra["contributions"]) == 4 for row in rows))

    def test_digest_does_not_mutate_cached_records(self):
        raw = [orca(36.8, -121.9, NOW - timedelta(hours=5), "a"), orca(36.8, -121.9, NOW - timedelta(days=10), "b")]
        wildlife.digest(raw, NOW, 14 * 24)
        self.assertEqual(raw[0].observers, ["a"], "the digest wrote into the raw source record")
        # And a stale observation leaves no observer residue in a later current cluster.
        self.assertEqual(birds.marine_presence(raw, NOW, HOME), [])

    def test_trusted_operator_report_qualifies_alone(self):
        (report,) = spectacles.condor_reports(
            "<rss><channel><item><link>https://example.test/t</link><description>"
            f"{NOW:%Y %m-%d} SB Channel trip. A pod of orcas passed the boat near Anacapa.</description></item>"
            "</channel></rss>", NOW + timedelta(hours=3))
        rows = birds.marine_presence([], NOW + timedelta(hours=3), HOME, [report])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].extra["behavior_evidence"])

    def operator_and_one_observer(self, km):
        import math
        later = NOW + timedelta(hours=3)
        (report,) = spectacles.condor_reports(
            "<rss><channel><item><link>https://example.test/t</link><description>"
            f"{NOW:%Y %m-%d} SB Channel trip. A pod of orcas passed the boat near Anacapa.</description></item>"
            "</channel></rss>", later)
        ((_, lat, lon),) = birds.operator_orca_reports([report], later)
        east = lon + km / (111.32 * math.cos(math.radians(lat)))
        community = orca(lat, east, later - timedelta(hours=1), "a", place="Community point")
        return birds.marine_presence([community], later, HOME, [report]), (lat, lon), (lat, east)

    def test_operator_forty_km_away_does_not_promote_a_lone_observation(self):
        # R8: the operator's trust stays at the operator's point. The lone
        # community observation 40 km away remains background only.
        rows, operator_point, _ = self.operator_and_one_observer(40)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].latitude, operator_point[0], places=4)
        self.assertAlmostEqual(rows[0].longitude, operator_point[1], places=4)
        self.assertEqual([c["observer"] for c in rows[0].extra["contributions"]], ["operator:condor_express"])

    def test_operator_within_the_diameter_backs_the_cluster_with_its_point_recorded(self):
        rows, operator_point, community_point = self.operator_and_one_observer(10)
        self.assertEqual(len(rows), 1)
        points = [(c["latitude"], c["longitude"]) for c in rows[0].extra["contributions"]]
        self.assertIn(operator_point, points, "the operator's own point is auditable")
        self.assertEqual(len(points), 2)
        for a in points:
            for b in points:
                self.assertLessEqual(wildlife.haversine_km(*a, *b), birds.ORCA_CLUSTER_KM)

    def test_one_research_grade_observation_is_background_only(self):
        self.assertEqual(birds.marine_presence([orca(36.8, -121.9, NOW - timedelta(hours=2), "a")], NOW, HOME), [])

    def test_obscured_points_cannot_form_a_cluster(self):
        rows = birds.marine_presence([orca(36.8, -121.9, NOW - timedelta(hours=2), "a", private_location=True),
                                      orca(36.8, -121.9, NOW - timedelta(hours=1), "b", private_location=True)], NOW, HOME)
        self.assertEqual(rows, [])


class TestC5StatementNormalization(unittest.TestCase):
    """Subject, behaviour, polarity, count, place and date come from one statement."""

    def humpback_state(self, body, subject="Whale report"):
        reports = email(body, subject=subject)
        rows = events.build_seasonal_opportunities(NOW, 365, HOME, None, reports)
        return next(r for r in rows if r.phenomenon == "humpback_lunge_feeding" and r.extra["precision"] == "peak").extra["evidence_state"]

    def test_negated_lunge_feeding_does_not_confirm(self):
        self.assertNotEqual(self.humpback_state("No lunge feeding at Avila today. Humpbacks are passing offshore."),
                            "behavior_confirmed")

    def test_positive_lunge_feeding_confirms(self):
        self.assertEqual(self.humpback_state("Humpbacks lunge feeding off Avila this morning."), "behavior_confirmed")

    def test_contradictory_multi_sentence_emails(self):
        cases = {
            "Humpbacks were lunge feeding at Avila last week. Today they are just passing.": False,
            # The only humpback statement is negated and about another place;
            # it cannot supply the subject of the unnamed feeding assertion.
            "We saw lunge feeding at Avila today. No humpbacks at Pismo.": False,
            "No bait balls today, but humpbacks lunge feeding off Avila this morning.": True,
            "Lunge feeding reported off Monterey today. Humpbacks passing Avila.": False,
        }
        for body, confirmed in cases.items():
            with self.subTest(body=body):
                self.assertEqual(self.humpback_state(body) == "behavior_confirmed", confirmed)

    def test_twenty_dolphin_megapod_is_not_a_megapod(self):
        reports = email("Channel Islands today: a megapod of 20 dolphins off Santa Cruz Island.", category="marine")
        self.assertEqual([r.count for r in reports], [20])
        self.assertEqual(spectacles.report_opportunities(reports, NOW, HOME), [])
        big = email("Channel Islands today: a megapod of 3,000 common dolphins off Santa Cruz Island.", category="marine")
        self.assertEqual(len(spectacles.report_opportunities(big, NOW, HOME)), 1)

    def test_monarch_count_is_not_contaminated_by_geese(self):
        now = datetime(2026, 12, 5, 16, tzinfo=UTC)
        reports = email("Pismo today: 50 monarchs in dense clusters, with 2,000 geese passing overhead.", received=now)
        self.assertEqual([(r.phenomenon_key, r.count) for r in reports], [("pismo_monarchs", 50)])
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, reports)
        monarchs = next(r for r in rows if r.phenomenon == "pismo_monarchs" and r.extra["precision"] == "peak")
        self.assertNotEqual(monarchs.extra["evidence_state"], "behavior_confirmed")

    def test_place_and_date_bind_to_their_statement(self):
        (one,) = observations.positive(observations.observe(
            "Yesterday at Avila humpbacks were lunge feeding.", NOW, category="marine"))
        self.assertEqual(one.observed_at.date(), (NOW - timedelta(days=1)).date())
        self.assertEqual(one.place, "avila")
        # Two places in the message: an unplaced statement is not given one.
        found = observations.positive(observations.observe(
            "Great day at Avila and Morro Bay. Lunge feeding humpbacks later.", NOW, category="marine"))
        self.assertTrue(all(item.zone_id == "" or item.place for item in found) or not found)

    def test_every_ingress_path_meets_the_same_count_rule(self):
        definition = curation.definition("dolphin_megapod")
        small = field_reports.FieldReport("condor_express", "Operator", "", "marine", "channel_islands", "Megapod",
                                          "Megapod today.", 90, NOW, "", NOW - timedelta(hours=2), "dolphin_megapod",
                                          None, None, 20)
        self.assertEqual(observations.admissible(small, definition, NOW), (False, "count below the phenomenon's threshold"))

    def test_future_dated_report_is_rejected(self):
        report = field_reports.FieldReport("email_x", "X", "", "marine", "piedras_blancas", "H",
                                           "Humpbacks lunge feeding at Avila.", 80, NOW, "", NOW + timedelta(days=2),
                                           "humpback_lunge_feeding")
        self.assertEqual(observations.admissible(report, curation.definition("humpback_lunge_feeding"), NOW)[1],
                         "dated in the future")


class TestR3SubjectBinding(unittest.TestCase):
    """Second review, R3: behaviour and count bind to their own subject; headers inherit only when they are headers."""

    def humpback(self, body):
        reports = email(body, subject="Whale report")
        rows = events.build_seasonal_opportunities(NOW, 365, HOME, None, reports)
        row = next(r for r in rows if r.phenomenon == "humpback_lunge_feeding" and r.extra["precision"] == "peak")
        eligibility.assess(row, NOW, max_drive_hours=6.0, alerts=[])
        return reports, row

    def test_another_species_lunge_feeding_does_not_confirm_humpbacks(self):
        reports, row = self.humpback("Humpbacks passed Avila today and dolphins were lunge feeding.")
        self.assertEqual([r.phenomena for r in reports], [()], "no phenomenon was confirmed by this sentence")
        self.assertNotEqual(row.extra["evidence_state"], "behavior_confirmed")
        self.assertFalse(row.extra["assessment"]["eligible"])

    def test_the_same_sentence_about_humpbacks_does_confirm(self):
        reports, row = self.humpback("Humpbacks were lunge feeding off Avila today.")
        (report,) = reports
        self.assertEqual(report.phenomena, ("humpback_lunge_feeding",))
        self.assertEqual(report.observed_at, NOW)
        self.assertEqual(report.place, "avila")
        self.assertEqual(row.extra["evidence_state"], "behavior_confirmed")

    def test_conjoined_species_count_is_not_the_monarch_count(self):
        now = datetime(2026, 12, 5, 16, tzinfo=UTC)
        reports = email("Pismo today: 2,000 geese and monarchs in clusters.", received=now)
        self.assertEqual([(r.phenomena, r.count) for r in reports], [(("pismo_monarchs",), None)])
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, reports)
        monarchs = next(r for r in rows if r.phenomenon == "pismo_monarchs" and r.extra["precision"] == "peak")
        self.assertNotEqual(monarchs.extra.get("count"), 2000)

    def test_a_short_first_sentence_is_not_a_header(self):
        (found,) = observations.observe("Trip cancelled at Avila today. Humpbacks lunge feeding.", NOW, category="marine")[-1:]
        self.assertIsNone(found.observed_at, "the date belonged to the cancelled trip")
        self.assertIsNone(found.latitude, "and so did the place")
        reports, row = self.humpback("Trip cancelled at Avila today. Humpbacks lunge feeding.")
        self.assertNotEqual(row.extra["evidence_state"], "behavior_confirmed")

    def test_a_header_naming_two_places_gives_no_place(self):
        found = observations.positive(observations.observe("Avila and Monterey Bay today. Humpbacks lunge feeding.",
                                                           NOW, category="marine"))
        self.assertTrue(all(item.latitude is None for item in found))
        reports, row = self.humpback("Avila and Monterey Bay today. Humpbacks lunge feeding.")
        self.assertNotEqual(row.extra["evidence_state"], "behavior_confirmed")

    def test_a_real_header_still_carries_place_and_date(self):
        found = observations.positive(observations.observe("Avila, September 27:\nHumpbacks lunge feeding.",
                                                           NOW, category="marine"))
        (item,) = [f for f in found if f.phenomenon == "humpback_lunge_feeding"]
        self.assertEqual(item.place, "avila")
        self.assertEqual(item.observed_at.date(), NOW.date())

    def test_sea_lions_feeding_is_not_condor_behaviour(self):
        now = datetime(2026, 12, 20, 18, tzinfo=UTC)
        reports = email("Condors at Pinnacles today and sea lions feeding.", received=now - timedelta(hours=3),
                        category="birds")
        self.assertFalse(any("condor_activity" in r.phenomena for r in reports))
        views = birds.classify([bird("Gymnogyps californianus", 36.487, -121.195, now - timedelta(hours=5), 1, "a",
                                     name="California condor")], now, HOME, 6.0, reports)
        self.assertEqual(views["spectacle"], [])


class TestR4HotlineStatementDates(unittest.TestCase):
    """Second review, R4: the page heading's date never renews an older statement."""

    PAGE = ("<h2>Carrizo March 27, 2026</h2>\n<p>On March 1, 2026 Carrizo was carpeted with wildflowers in full bloom.\n"
            "The road was repaired today.</p>")
    NOW = datetime(2026, 3, 27, 18, tzinfo=UTC)

    def test_stale_bloom_under_a_current_heading_is_not_eligible(self):
        reports = field_reports.parse_report(self.PAGE, field_reports.REPORT_SOURCES[0], self.NOW)
        self.assertEqual([(r.zone_id, r.observed_at, r.phenomena) for r in reports],
                         [("carrizo_plain", datetime(2026, 3, 1, 12, tzinfo=UTC), ("bloom_carrizo_plain",))])
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME, None, reports)
        bloom = next(r for r in rows if r.phenomenon == "bloom_carrizo_plain" and r.extra.get("precision", "peak") == "peak")
        eligibility.assess(bloom, self.NOW, max_drive_hours=6.0, alerts=[])
        self.assertNotEqual(bloom.extra["evidence_state"], "behavior_confirmed")
        self.assertFalse(bloom.extra["assessment"]["eligible"])


class TestC6MalformedAlerts(unittest.TestCase):
    """An HTTP success with unusable features is not a healthy empty feed."""

    def check(self, features, failures=0):
        value = weather_hazards.parse_alert_collection({"type": "FeatureCollection", "features": features}, NOW)
        return value, weather_hazards.current_alerts(value, NOW, failures, NOW)

    def seals(self):
        return opp("elephant_seal_battles", "mammals", lat=35.664, lon=-121.257, drive=2.0, evidence_state="calendar")

    def test_valid_empty_collection_is_healthy_and_safe(self):
        value, check = self.check([])
        self.assertTrue(value["complete"])
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "safe")

    def test_one_valid_warning_is_applied(self):
        value, check = self.check([nws_feature("High Wind Warning", same=("006079",))])
        self.assertTrue(value["complete"])
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unsafe")

    def test_malformed_only_nonempty_is_incomplete_and_unknown(self):
        value, check = self.check([{"type": "Feature", "properties": {"headline": "no event"}}])
        self.assertFalse(value["complete"])
        self.assertEqual(value["invalid"], 1)
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unknown")

    def test_mixed_valid_and_malformed_keeps_the_warning_but_never_says_safe(self):
        malformed = {"type": "Feature", "properties": {"event": "Flash Flood Warning", "geocode": {}}}  # no area, no expiry
        value, check = self.check([nws_feature("Wind Advisory", same=("006079",)), malformed])
        self.assertFalse(value["complete"])
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unknown",
                         "a caution from a partial feed is not a full check")
        value, check = self.check([nws_feature("High Wind Warning", same=("006079",)), malformed])
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unsafe",
                         "a readable warning still blocks")

    def test_required_fields(self):
        for feature in ({"properties": {"event": "X", "expires": NOW.isoformat()}},  # nowhere to place it
                        {"properties": {"event": "X", "geocode": {"SAME": ["006083"]}}},  # no expiry
                        {"properties": {"event": "", "geocode": {"SAME": ["006083"]}, "expires": NOW.isoformat()}},
                        {"geometry": {"type": "Polygon", "coordinates": "junk"},
                         "properties": {"event": "X", "expires": NOW.isoformat()}},
                        "not a feature"):
            with self.subTest(feature=feature):
                self.assertIsNone(weather_hazards.validate_feature(feature)[0])
        with self.assertRaises(weather_hazards.AlertFeedError):
            weather_hazards.parse_alert_collection({"features": "nope"}, NOW)

    def test_geography_the_resolver_cannot_place_is_incomplete(self):
        # Second review, R2: every one of these used to be accepted and match
        # nowhere, which read as SAFE.
        polygon_nan = {"type": "Polygon", "coordinates": [[[-121.0, 35.0], [float("nan"), 35.5], [-120.5, 35.5],
                                                           [-121.0, 35.0]]]}
        cases = {
            "UGC only": nws_feature(geocode={"UGC": ["CAZ340"]}),
            "bogus SAME": nws_feature(same=("garbage",)),
            "scalar SAME": nws_feature(geocode={"SAME": "006079"}),
            "UGC not a list": nws_feature(geocode={"SAME": ["006079"], "UGC": "CAZ340"}),
            "NaN polygon": {**nws_feature(same=()), "geometry": polygon_nan},
            "latitude out of range": {**nws_feature(same=()), "geometry": {"type": "Polygon", "coordinates": [
                [[-121.0, 95.0], [-120.5, 35.5], [-120.0, 35.0], [-121.0, 95.0]]]}},
        }
        for name, feature in cases.items():
            with self.subTest(name):
                self.assertIsNone(weather_hazards.validate_feature(feature)[0])
                value, check = self.check([feature])
                self.assertFalse(value["complete"])
                self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unknown")

    def test_a_placeable_warning_with_ugc_codes_too_is_used(self):
        feature = nws_feature("High Wind Warning", same=("006079",))
        feature["properties"]["geocode"]["UGC"] = ["CAZ340"]
        value, check = self.check([feature])
        self.assertTrue(value["complete"])
        self.assertEqual(weather_hazards.safety(self.seals(), check, NOW, "coastal")["state"], "unsafe")

    def test_through_the_gate_and_dashboard(self):
        _value, check = self.check([{"type": "Feature", "properties": {}}])
        item = self.seals()
        eligibility.annotate([item], NOW, max_drive_hours=6, alerts=check)
        self.assertTrue(item.extra["assessment"]["held"])
        board = eligibility.dashboard([item], NOW)
        self.assertEqual(board["events"], [])
        self.assertTrue(board["held"])


# --- HIGH --------------------------------------------------------------------------

class TestH1SpectacleCountFreshness(unittest.TestCase):
    NOW = datetime(2026, 12, 20, 18, tzinfo=UTC)

    def classify(self, sightings, reports=None):
        return birds.classify(sightings, self.NOW, HOME, 6.0, reports)

    def test_old_count_plus_fresh_single_bird_is_not_a_spectacle(self):
        views = self.classify([bird("Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(days=6), 3000, "a"),
                               bird("Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(hours=2), 1, "b")])
        self.assertEqual(views["spectacle"], [])

    def test_fresh_count_is_a_spectacle_dated_by_the_count(self):
        counted = self.NOW - timedelta(days=1)
        views = self.classify([bird("Antigone canadensis", 37.18, -120.60, counted, 3000, "a"),
                               bird("Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(hours=2), 1, "b")])
        (row,) = views["spectacle"]
        self.assertEqual(row.extra["observed_at"], counted.isoformat())
        self.assertEqual(row.extra["count"], 3000)

    def test_future_dated_sighting_is_rejected(self):
        views = self.classify([bird("Antigone canadensis", 37.18, -120.60, self.NOW + timedelta(days=2), 3000, "a")])
        self.assertEqual(views["spectacle"], [])

    def test_behaviour_report_must_name_this_species_at_this_site(self):
        wrong_species = field_reports.FieldReport("email_x", "X", "", "birds", "yosemite_valley", "R",
                                                  "Sea lions feeding at Merced NWR today.", 80, self.NOW, "",
                                                  self.NOW - timedelta(hours=3), "", 37.18, -120.60)
        views = self.classify([bird("Gymnogyps californianus", 36.487, -121.195, self.NOW - timedelta(hours=5), 1, "a",
                                    name="California condor")], [wrong_species])
        self.assertEqual(views["spectacle"], [])


class TestH2SiteIdentity(unittest.TestCase):
    NOW = datetime(2026, 12, 20, 18, tzinfo=UTC)

    def test_woodbridge_evidence_does_not_confirm_merced(self):
        seasonal = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        merced = next(r for r in seasonal if r.phenomenon == "sandhill_crane_flyin" and r.extra["precision"] == "peak")
        views = birds.classify([bird("Antigone canadensis", 38.156, -121.416, self.NOW - timedelta(hours=6), 4000, "a")],
                               self.NOW, HOME, 8.0)
        left = eligibility.merge_into_phenomena(seasonal, views["spectacle"], self.NOW)
        self.assertEqual(len(left), 1, "Woodbridge stays its own occurrence")
        self.assertNotEqual(merced.extra["evidence_state"], "behavior_confirmed")
        self.assertAlmostEqual(left[0].latitude, 38.156, places=2)
        self.assertNotEqual(event_state.event_id(left[0]), event_state.event_id(merced))

    def test_merced_evidence_merges_into_merced(self):
        seasonal = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        views = birds.classify([bird("Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(hours=6), 4000, "a")],
                               self.NOW, HOME, 8.0)
        self.assertEqual(eligibility.merge_into_phenomena(seasonal, views["spectacle"], self.NOW), [])
        merced = next(r for r in seasonal if r.phenomenon == "sandhill_crane_flyin" and r.extra["precision"] == "peak")
        self.assertEqual(merced.extra["evidence_state"], "behavior_confirmed")


class TestH3ExactCoordinates(unittest.TestCase):
    def test_pismo_bioluminescence_stays_at_pismo(self):
        reports = email("Bioluminescence at Pismo tonight, glowing waves along the pier.", category="rare_phenomena")
        (row,) = spectacles.report_opportunities(reports, NOW, HOME)
        self.assertAlmostEqual(row.latitude, 35.131, places=3)
        self.assertAlmostEqual(row.longitude, -120.635, places=3)
        self.assertIn("Pismo", row.zone_name)
        self.assertEqual(row.extra["location_precision"], "reported place")
        self.assertLess(row.drive_hours, wildlife.estimate_drive_hours(35.664, -121.257, HOME))

    def test_region_only_report_says_so(self):
        reports = email("Bioluminescence along the Santa Barbara Channel tonight.", category="rare_phenomena")
        rows = spectacles.report_opportunities(reports, NOW, HOME)
        self.assertTrue(rows)
        self.assertEqual(rows[0].extra["location_precision"], "region")

    NIGHT = datetime(2026, 10, 10, 3, tzinfo=UTC)  # dark, Moon low: glowing surf's conditions pass

    def gate(self, rows):
        for row in rows:
            eligibility.assess(row, self.NIGHT, max_drive_hours=8.0, alerts=[])
        return rows

    def test_a_region_is_not_a_destination(self):
        # R7: the Channel's centre is not where anyone saw the glow, so it is
        # never recommended there, however dark the night.
        reports = email("Bioluminescence along the Santa Barbara Channel tonight.", received=self.NIGHT - timedelta(hours=1),
                        category="rare_phenomena")
        (row,) = self.gate(spectacles.report_opportunities(reports, self.NIGHT, HOME))
        self.assertFalse(row.extra["assessment"]["eligible"])
        self.assertIn("reported for a region, not a site: no place to check darkness, drive and safety",
                      row.extra["assessment"]["blockers"])

    def test_the_same_report_at_a_named_beach_is_eligible(self):
        reports = email("Bioluminescence at Pismo tonight.", received=self.NIGHT - timedelta(hours=1),
                        category="rare_phenomena")
        (row,) = self.gate(spectacles.report_opportunities(reports, self.NIGHT, HOME))
        self.assertTrue(row.extra["assessment"]["eligible"], row.extra["assessment"]["blockers"])

    def test_an_explicit_zone_keeps_the_observed_point(self):
        # R7: the automation's zone files the mail; the text says where it was.
        reports = email("Bioluminescence at Pismo tonight.", received=self.NIGHT - timedelta(hours=1),
                        category="rare_phenomena", zone_id="piedras_blancas")
        self.assertEqual([(r.latitude, r.longitude) for r in reports], [(35.131, -120.635)])
        (row,) = self.gate(spectacles.report_opportunities(reports, self.NIGHT, HOME))
        self.assertAlmostEqual(row.latitude, 35.131, places=3)
        self.assertAlmostEqual(row.longitude, -120.635, places=3)
        self.assertEqual(row.extra["location_precision"], "reported place")
        self.assertLess(row.drive_hours, wildlife.estimate_drive_hours(35.6664, -121.2571, HOME))
        self.assertTrue(row.extra["assessment"]["eligible"], row.extra["assessment"]["blockers"])


class TestH4LightPathLayers(unittest.TestCase):
    def test_missing_layers_are_never_open(self):
        self.assertIsNone(weather_scoring.light_path_gate(None, None))
        self.assertIsNone(weather_scoring.light_path_gate_checked(10.0, None))

    def test_invalid_or_mismatched_values_are_unknown(self):
        start = NOW - timedelta(hours=2)
        for value in (float("nan"), 140, -5, True, None, "10"):
            with self.subTest(value=value):
                self.assertIsNone(weather_scoring.layer_at(forecast(start, cloud_cover_low=value), "cloud_cover_low", NOW))
        far = forecast(NOW + timedelta(days=5), cloud_cover_low=10)
        self.assertIsNone(weather_scoring.layer_at(far, "cloud_cover_low", NOW), "not time matched")

    def test_firefall_with_upstream_layers_missing_is_not_eligible(self):
        now = datetime(2027, 2, 16, 18, tzinfo=UTC)
        report = field_reports.FieldReport("email_ranger", "Ranger", "", "rare_phenomena", "yosemite_valley", "H",
                                           "Horsetail Fall is flowing.", 80, now, "", now - timedelta(hours=10),
                                           "horsetail_firefall")
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, [report])
        bundle = {"local": forecast(now - timedelta(hours=2), cloud_cover=5),
                  "upstream": {"sunset": forecast(now - timedelta(hours=2), cloud_cover=5)}}  # layers absent
        conditions.annotate_firefall(rows, {"yosemite_valley": bundle}, now)
        conditions.annotate_access(rows, [], now, 0, now)
        item = next(r for r in rows if r.phenomenon == "horsetail_firefall" and r.extra["precision"] == "peak")
        eligibility.assess(item, now, max_drive_hours=8.0, alerts=[])
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertIn("western light path not modelled", " ".join(item.extra["assessment"]["blockers"]))
        self.assertIn("Unknown", item.extra["condition_states"]["Western light path"])

    def test_sunset_with_one_upstream_layer_is_not_modelled(self):
        start = NOW - timedelta(hours=2)
        local = forecast(start, cloud_cover_high=40, cloud_cover_mid=10, cloud_cover_low=5)
        upstream = forecast(start, cloud_cover_low=0)  # mid missing
        sunset = weather_scoring.astro.sun_event(NOW + timedelta(days=1), *[__import__("math").radians(v) for v in HOME],
                                                 rising=False)
        self.assertGreater(sunset, NOW)
        scored = weather_scoring.score_sky(local, sunset, upstream=upstream)
        self.assertNotEqual(scored.light_path, "modelled")
        both = forecast(start, cloud_cover_low=0, cloud_cover_mid=0)
        self.assertEqual(weather_scoring.score_sky(local, sunset, upstream=both).light_path, "modelled")


class TestH5ProviderModelFreshness(unittest.TestCase):
    def prediction(self, updated):
        return {"kind": "sunset", "quality": "Great", "percent": 90.0, "valid_at": NOW + timedelta(hours=3),
                "last_updated": updated, "model": "GFS"}

    def test_old_model_downloaded_now_is_not_current(self):
        stale = self.prediction(NOW - timedelta(days=5))
        self.assertEqual(sunburst.current([stale], NOW), [])
        self.assertIn("model last updated", sunburst.model_age_problem(stale, NOW))

    def test_missing_or_future_model_time_is_not_current(self):
        self.assertEqual(sunburst.current([self.prediction(None)], NOW), [])
        self.assertEqual(sunburst.current([self.prediction(NOW + timedelta(hours=2))], NOW), [])

    def test_current_model_is_used(self):
        self.assertEqual(len(sunburst.current([self.prediction(NOW - timedelta(hours=2))], NOW)), 1)


class TestH6InputsResolvedBeforeScoring(unittest.TestCase):
    def test_provider_can_decide_without_a_local_forecast(self):
        import math
        sunset = weather_scoring.astro.sun_event(NOW + timedelta(days=1), math.radians(HOME[0]), math.radians(HOME[1]),
                                                 rising=False)
        provider = [{"kind": "sunset", "quality": "Great", "percent": 91.0, "valid_at": sunset,
                     "last_updated": NOW - timedelta(hours=1), "model": "GFS"}]
        zone = {"id": "home", "name": "Home", "latitude": HOME[0], "longitude": HOME[1], "drive_hours": 0.0}
        rows = events.build_sunset_opportunities(zone, {}, NOW, 70, 3, {}, None, provider)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].extra["provider_quality"], "Great")
        self.assertIsNone(rows[0].extra["local_score"])
        self.assertEqual(source_health.dependency_roles(rows[0])["sunsetwx"], source_health.REQUIRED)
        eligibility.assess(rows[0], NOW, max_drive_hours=6, alerts=[])
        self.assertTrue(rows[0].extra["assessment"]["eligible"], rows[0].extra["assessment"]["blockers"])


class TestH7PerPointWeather(unittest.TestCase):
    def test_unrelated_point_failure_does_not_degrade_home_sunset(self):
        sky = opp("sunset_local", "sunset", zone="home", evidence_state="forecast")
        health = {"weather": {"state": "failed", "name": "Open-Meteo", "impact": "x"}}
        source_health.annotate([sky], health, {"home": "ok", "home:sunset": "ok", "lake_tahoe": "failed"})
        self.assertNotIn("degraded_required", sky.extra)

    def test_the_consumed_point_failing_does_degrade(self):
        sky = opp("sunset_local", "sunset", zone="home", evidence_state="forecast")
        source_health.annotate([sky], {"weather": {"state": "failed", "name": "Open-Meteo", "impact": "x"}},
                               {"home": "failed", "lake_tahoe": "ok"})
        self.assertEqual(sky.extra["degraded_required"], ["weather"])

    def test_point_health_states(self):
        points = source_health.point_health({"home": {"fetched_at": NOW, "failed": False},
                                             "tahoe": {"fetched_at": NOW, "failed": True},
                                             "old": {"fetched_at": NOW - timedelta(hours=5), "failed": False},
                                             "new": {"fetched_at": None, "failed": False}}, NOW)
        self.assertEqual(points, {"home": "ok", "tahoe": "failed", "old": "stale", "new": "waiting"})


class TestH8AssessmentCoverage(unittest.TestCase):
    def health(self, **states):
        return {key: {"state": state, "enabled": True, "name": key, "impact": ""} for key, state in states.items()}

    def test_required_source_down_is_incomplete_not_quiet(self):
        coverage = source_health.assessment_coverage(self.health(weather="failed", surf_alerts="ok"), {"sunset"})
        self.assertEqual(coverage["state"], "incomplete")
        board = eligibility.dashboard([], NOW, coverage=coverage)
        self.assertEqual(board["headline"], eligibility.INCOMPLETE_HEADLINE)
        self.assertEqual(board["assessment"]["problems"][0]["source"], "weather")

    def test_all_sources_answered_is_a_healthy_empty_week(self):
        coverage = source_health.assessment_coverage(self.health(weather="ok", surf_alerts="ok"), {"sunset"},
                                                     {"home": "ok"})
        board = eligibility.dashboard([], NOW, coverage=coverage)
        self.assertEqual(board["headline"], "Nothing worth changing plans for this week.")

    def test_home_point_failure_is_incomplete_for_sunsets(self):
        coverage = source_health.assessment_coverage(self.health(weather="ok", surf_alerts="ok"), {"sunset"},
                                                     {"home": "failed"})
        self.assertEqual(coverage["state"], "incomplete")

    def test_safety_feed_down_is_incomplete_for_every_category(self):
        coverage = source_health.assessment_coverage(self.health(surf_alerts="failed"), {"parks"})
        self.assertEqual(coverage["state"], "incomplete")

    def test_optional_or_disabled_sources_do_not_count(self):
        health = self.health(surf_alerts="ok", weather="ok")
        health["ebird"] = {"state": "failed", "enabled": False, "name": "eBird"}
        self.assertEqual(source_health.assessment_coverage(health, {"birds"})["state"], "complete")


class TestH9OwnershipIsNotPresentation(unittest.TestCase):
    NOW = datetime(2026, 12, 20, 18, tzinfo=UTC)

    def build(self, categories):
        seasonal = events.build_seasonal_opportunities(self.NOW, 365, HOME)
        views = birds.classify([bird("Antigone canadensis", 37.18, -120.60, self.NOW - timedelta(hours=6), 4000, "a"),
                                bird("Antigone canadensis", 38.156, -121.416, self.NOW - timedelta(hours=5), 3000, "b")],
                               self.NOW, HOME, 8.0)
        rows = seasonal + eligibility.merge_into_phenomena(seasonal, views["spectacle"], self.NOW)
        rows = [item for item in rows if eligibility.presentation_categories(item) & categories]
        eligibility.annotate(rows, self.NOW, max_drive_hours=8.0, alerts=[])
        return eligibility.dashboard(rows, self.NOW)["birds"]["spectacle"]

    def test_birds_on_rare_off_keeps_the_crane_spectacle(self):
        spectacle = self.build({"birds"})
        self.assertEqual(sorted(round(row["drive_hours"]) for row in spectacle if row["phenomenon"] == "sandhill_crane_flyin"),
                         sorted({round(row["drive_hours"]) for row in spectacle if row["phenomenon"] == "sandhill_crane_flyin"}))
        self.assertTrue(any(row["phenomenon"] == "sandhill_crane_flyin" for row in spectacle))

    def test_merced_and_woodbridge_each_once(self):
        for categories in ({"birds"}, {"birds", "rare_phenomena"}):
            with self.subTest(categories=categories):
                spectacle = [row for row in self.build(categories) if row["phenomenon"] == "sandhill_crane_flyin"]
                keys = [row["event_id"] for row in spectacle]
                self.assertEqual(len(keys), len(set(keys)), "no duplicates")
                self.assertEqual(len(spectacle), 2, "Merced and Woodbridge are two occurrences")


class TestH10OutOfSeasonLiveEvidence(unittest.TestCase):
    NOW = datetime(2026, 10, 25, 18, tzinfo=UTC)  # blue whale window is 15 Jul - 10 Sep

    def test_valid_blue_whale_report_opens_a_bounded_occurrence_now(self):
        reports = email("Blue whales feeding off Santa Cruz Island this morning, several close to the boat.",
                        received=self.NOW - timedelta(hours=4), category="marine")
        rows = events.build_seasonal_opportunities(self.NOW, 365, HOME, None, reports)
        live = [r for r in rows if r.phenomenon == "blue_whale_feeding" and r.extra.get("live_occurrence")]
        self.assertEqual(len(live), 1)
        item = live[0]
        self.assertLessEqual(item.start, self.NOW)
        self.assertLessEqual(item.end - item.start, timedelta(days=4))
        eligibility.assess(item, self.NOW, max_drive_hours=6, alerts=[])
        self.assertTrue(item.extra["assessment"]["policy_met"])
        # A boat trip: held for marine conditions, never silently lost.
        self.assertTrue(item.extra["assessment"]["held"])

    def test_humpback_out_of_season_on_the_shore_can_be_eligible(self):
        now = datetime(2027, 1, 20, 18, tzinfo=UTC)  # humpback window is Aug - mid Oct
        reports = email("Humpbacks lunge feeding off Avila this morning.", received=now - timedelta(hours=3), category="marine")
        rows = events.build_seasonal_opportunities(now, 365, HOME, None, reports)
        (live,) = [r for r in rows if r.phenomenon == "humpback_lunge_feeding" and r.extra.get("live_occurrence")]
        eligibility.assess(live, now, max_drive_hours=6, alerts=[])
        self.assertTrue(live.extra["assessment"]["eligible"], live.extra["assessment"]["blockers"])

    def test_stale_or_calendar_bound_reports_do_not(self):
        stale = email("Blue whales feeding off Santa Cruz Island today.", received=self.NOW - timedelta(days=6),
                      category="marine")
        self.assertFalse(any(r.extra.get("live_occurrence") for r in events.build_seasonal_opportunities(self.NOW, 365, HOME, None, stale)))
        elk = email("Tule elk bugling and sparring at Carrizo this morning.", received=datetime(2027, 4, 2, 15, tzinfo=UTC),
                    category="mammals")
        rows = events.build_seasonal_opportunities(datetime(2027, 4, 2, 18, tzinfo=UTC), 365, HOME, None, elk)
        self.assertFalse(any(r.extra.get("live_occurrence") for r in rows), "the rut is physically seasonal")


class TestH11RouteBasisSurfaces(unittest.TestCase):
    def test_bird_views_say_their_drive_is_an_estimate(self):
        now = datetime(2026, 12, 20, 18, tzinfo=UTC)
        views = birds.classify([bird("Antigone canadensis", 37.18, -120.60, now - timedelta(days=2), 1, f"o{i}")
                                for i in range(3)] + [bird("Antigone canadensis", 37.18, -120.60, now - timedelta(days=4), 1, "z")],
                               now, HOME, 8.0)
        self.assertTrue(views["encounter"])
        self.assertEqual({row["drive_basis"] for row in views["encounter"]}, {"estimate"})

    def test_assessment_reports_the_drive_basis(self):
        item = opp("milky_way", "astronomy", evidence_state="computed", cloud_is_forecast=True)
        self.assertEqual(eligibility.assess(item, NOW, max_drive_hours=6, alerts=[])["drive_basis"], "estimate")
        item.extra["drive_basis"] = "recent"
        self.assertEqual(eligibility.assess(item, NOW, max_drive_hours=6, alerts=[])["drive_basis"], "recent")


# --- MEDIUM ------------------------------------------------------------------------

class TestM1TimePrecision(unittest.TestCase):
    def test_grunion_run_keeps_its_interval_across_dst(self):
        # 14 March 2027 is the US spring-forward date; 22:15 PDT is 05:15 UTC next day.
        start = datetime(2027, 3, 14, 21, 50, tzinfo=PACIFIC)
        (row,) = __import__("photography_events.grunion", fromlist=["x"]).opportunities(
            [(start, start + timedelta(hours=2))], datetime(2027, 3, 10, tzinfo=UTC), HOME)
        compact = row.compact()
        self.assertEqual(row.time_precision, "interval")
        self.assertNotIn("all_day", compact)
        self.assertEqual(datetime.fromisoformat(compact["start"]).astimezone(PACIFIC).strftime("%Y-%m-%d %H:%M"),
                         "2027-03-14 22:15")

    def test_moonbow_candidate_is_timed(self):
        rows = spectacles.moonbow_opportunities(datetime(2026, 5, 25, tzinfo=UTC), HOME)
        self.assertTrue(rows)
        self.assertTrue(all(row.time_precision == "interval" and "all_day" not in row.compact() for row in rows[:3]))

    def test_seasons_are_still_date_ranges(self):
        season = next(r for r in events.build_seasonal_opportunities(NOW, 365, HOME) if r.extra["precision"] == "season")
        self.assertEqual(season.time_precision, "day")
        self.assertTrue(season.compact()["all_day"])


class TestM2YearBoundaryIdentity(unittest.TestCase):
    def crane_key(self, now):
        return next(r.key for r in events.build_seasonal_opportunities(now, 365, HOME)
                    if r.phenomenon == "sandhill_crane_flyin" and r.start <= now <= r.end)

    def test_same_key_either_side_of_new_year(self):
        december = datetime(2026, 12, 31, 20, tzinfo=UTC)
        january = datetime(2027, 1, 1, 8, tzinfo=UTC)
        self.assertEqual(self.crane_key(december), self.crane_key(january))

    def test_skip_survives_the_year_boundary(self):
        december = datetime(2026, 12, 31, 20, tzinfo=UTC)
        state = event_state.EventState()
        key = self.crane_key(december)
        state.set_choice(key, "skip", december + timedelta(days=60))
        january = datetime(2027, 1, 1, 8, tzinfo=UTC)
        crane = next(r for r in events.build_seasonal_opportunities(january, 365, HOME)
                     if r.phenomenon == "sandhill_crane_flyin" and r.start <= january <= r.end)
        self.assertTrue(state.suppressed(event_state.event_id(crane)))

    def test_windows_are_one_occurrence_each(self):
        window = phenomena.WINDOWS_BY_KEY["sandhill_crane_flyin"]
        self.assertEqual(window.occurrences(2026), [(datetime(2026, 12, 10).date(), datetime(2027, 1, 18).date())])


class TestM3SuppressionBeforeRepresentative(unittest.TestCase):
    def test_suppressed_best_night_does_not_represent_the_group(self):
        base = NOW + timedelta(hours=5)
        a = opp("milky_way", "astronomy", start=base, zone="a", evidence_state="computed", cloud_is_forecast=True)
        b = opp("milky_way", "astronomy", start=base + timedelta(days=1), zone="b", evidence_state="computed",
                cloud_is_forecast=True)
        a.roll, b.roll = "mw-a", "mw-b"
        a.score, b.score = 99, 91
        eligibility.annotate([a, b], NOW, max_drive_hours=6, alerts=[])
        board = eligibility.dashboard([a, b], NOW, suppressed=lambda key: key == "mw-a")
        self.assertEqual([row["key"] for row in board["events"]], [b.key])
        self.assertEqual(sorted(board["events"][0]["choice_ids"]), ["mw-a", "mw-b"])


class TestM4QualifyBeforeRank(unittest.TestCase):
    def test_eligible_alternative_is_announced(self):
        good = opp("milky_way", "astronomy", zone="good")
        bad = opp("milky_way", "astronomy", zone="bad")
        good.roll = bad.roll = "mw-night"
        good.score, bad.score = 94, 95
        good.extra["assessment"] = {"eligible": True, "priority": 80}
        bad.extra["assessment"] = {"eligible": False, "priority": None}
        notices = event_state.EventState().changes([bad, good], NOW, lambda item: item.extra["assessment"]["eligible"])
        self.assertEqual([notice["where"] for notice in notices], ["good"])


class TestPayloadSize(unittest.TestCase):
    def test_realistic_maximum_cant_miss_payload_serializes_and_stays_bounded(self):
        rows = []
        for i in range(60):
            item = opp("meteor_major", "astronomy", start=NOW + timedelta(hours=3 + i), zone=f"z{i}",
                       evidence_state="computed", cloud_cover=0, cloud_is_forecast=True)
            item.roll = f"meteor-{i}"
            item.extra["behavior_evidence"] = [{"source": "x" * 40, "text": "y" * 220}] * 3
            rows.append(item)
        eligibility.annotate(rows, NOW, max_drive_hours=6, alerts=[])
        board = eligibility.dashboard(rows, NOW, coverage={"state": "incomplete",
                                                           "problems": [{"source": "weather", "name": "Open-Meteo"}]})
        encoded = json.dumps(board, default=str)
        self.assertLess(len(encoded), 400_000)
        self.assertEqual(len(board["events"]), 60)


if __name__ == "__main__":
    unittest.main()
