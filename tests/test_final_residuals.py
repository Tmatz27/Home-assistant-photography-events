"""Third-review reproductions promoted unchanged in intent, plus nearby variants.

Only R1/R2/R3/R5: keep malformed evidence unknown and observations attached to
their actual subject/place/date. Full coordinator counterparts are in
test_ha_final_residuals.py.
"""
import unittest
from datetime import timedelta

import test_codex_review as fixtures
from photography_events import observations, verification, weather_hazards, weather_scoring


class SemanticAlerts(unittest.TestCase):
    def test_nps_records_must_be_interpretable_for_the_requested_parks(self):
        record = {"id": "review", "parkCode": "yose", "title": "Yosemite Valley closed", "category": "Park Closure"}
        for changed in ({"category": "UnexpectedCategory"}, {"parkCode": "????"}, {"parkCode": "zzzz"},
                        {"id": True}, {"id": " "}, {"title": []}):
            with self.subTest(changed=changed), self.assertRaises(verification.IncompleteAlertsError):
                verification.collect_nps_pages([{"total": "1", "data": [{**record, **changed}]}])
        with self.assertRaises(verification.IncompleteAlertsError):
            verification.collect_nps_pages([{"total": "1", "data": [record]}], requested_codes={"pinn"})

    def test_nps_known_information_and_danger_are_preserved(self):
        for category, blocking in (("Information", False), ("Caution", False), ("Park Closure", True), ("Danger", True)):
            with self.subTest(category=category):
                rows = verification.collect_nps_pages([{"total": "1", "data": [
                    {"id": "review", "parkCode": "yose", "title": "Yosemite Valley", "category": category}]}])
                self.assertEqual(rows[0].blocking, blocking)
        self.assertEqual(verification.collect_nps_pages([{"total": "0", "data": []}]), [])

    def test_same_codes_must_be_resolvable_not_just_six_digits(self):
        for code in ("106079", "906079", "999999", "006000", "006002", "006117", "００６０７９"):
            with self.subTest(code=code):
                result = weather_hazards.parse_alert_collection(
                    {"features": [fixtures.nws_feature(same=[code])]}, fixtures.NOW)
                self.assertFalse(result["complete"])
        for code in ("006079", "006083", "006001", "006115"):
            with self.subTest(usable=code):
                self.assertTrue(weather_hazards.parse_alert_collection(
                    {"features": [fixtures.nws_feature(same=[code])]}, fixtures.NOW)["complete"])

    def test_finite_coordinates_are_not_necessarily_usable_polygons(self):
        rings = [
            [[-121.2, 35.6]] * 4,
            [[-121, 35], [-120, 36], [-119, 37], [-121, 35]],
            [[False, True], [False, 2], [3, 2], [False, True]],
            [["-121", 35], [-120, 35], [-120, 36], ["-121", 35]],
            [[-121, 35], [-120, 35], [-120, 36]],
            [[-121, 35], [-120, 35], [-120, 36], [-121, 36]],
            [[-121, 35], [-120, 35], [-120, 36, {}], [-121, 35]],
        ]
        for ring in rings:
            with self.subTest(ring=ring):
                feature = fixtures.nws_feature(same=[])
                feature["geometry"] = {"type": "Polygon", "coordinates": [ring]}
                self.assertFalse(weather_hazards.parse_alert_collection({"features": [feature]}, fixtures.NOW)["complete"])


class ConservativeStatements(unittest.TestCase):
    def confirmed(self, body, key, subject="Field report"):
        definition = fixtures.curation.definition(key)
        reports = fixtures.email(body, subject=subject, category=definition.category)
        return [r for r in reports if key in r.phenomena and observations.admissible(r, definition, fixtures.NOW)[0]]

    def test_multiple_animal_grammar_does_not_guess_a_subject(self):
        cases = {
            "humpback_lunge_feeding": (
                "Dolphins beside humpbacks were lunge feeding at Avila today.",
                "Humpbacks beside dolphins were lunge feeding at Avila today.",
                "Beside humpbacks, dolphins were lunge feeding at Avila today.",
                "Humpbacks watched as dolphins were lunge feeding at Avila today.",
                "Humpbacks were passing and something else was lunge feeding at Avila today.",
            ),
            "condor_activity": (
                "Ravens beside condors were feeding at Pinnacles today.",
                "Condors beside ravens were feeding at Pinnacles today.",
                "Condors at Pinnacles today and ground squirrels were feeding.",
                "Beside condors, ravens were feeding at Pinnacles today.",
            ),
        }
        for key, sentences in cases.items():
            for body in sentences:
                with self.subTest(body=body):
                    self.assertFalse(self.confirmed(body, key))

    def test_simple_subject_behavior_and_explicit_count_remain_usable(self):
        for body, key in (("Humpbacks were lunge feeding at Avila today.", "humpback_lunge_feeding"),
                          ("Condors were feeding at Pinnacles today.", "condor_activity")):
            with self.subTest(body=body):
                self.assertTrue(self.confirmed(body, key))
        reports = fixtures.email("Pismo today: 50 monarchs in dense clusters, with 2,000 geese passing overhead.")
        self.assertEqual([r.count for r in reports if "pismo_monarchs" in r.phenomena], [50])

    def test_distinct_precise_places_cannot_supply_one_arbitrary_header(self):
        for body in ("Avila today. Pismo today. Humpbacks lunge feeding.",
                     "Avila and Pismo today. Humpbacks lunge feeding.",
                     "Humpbacks were lunge feeding at Avila and Pismo today."):
            with self.subTest(body=body):
                self.assertFalse(self.confirmed(body, "humpback_lunge_feeding"))

    def test_cancelled_or_planned_context_is_not_observation_metadata(self):
        for subject in ("Trip cancelled at Avila today", "Planning a trip to Avila today", "Hoping for humpbacks at Avila today"):
            with self.subTest(subject=subject):
                self.assertFalse(self.confirmed("Humpbacks lunge feeding.", "humpback_lunge_feeding", subject))
        for body in ("Planning to see humpbacks lunge feeding at Avila today.",
                     "Trip cancelled at Avila today. Humpbacks lunge feeding."):
            with self.subTest(body=body):
                self.assertFalse(self.confirmed(body, "humpback_lunge_feeding"))

    def test_ambiguous_dates_do_not_supply_an_observation_date(self):
        body = "Avila today. Avila yesterday. Humpbacks lunge feeding."
        self.assertFalse(self.confirmed(body, "humpback_lunge_feeding"))
        body = "Avila today; Pismo yesterday; humpbacks lunge feeding."
        self.assertFalse(self.confirmed(body, "humpback_lunge_feeding"))
        found = self.confirmed("Humpbacks lunge feeding.", "humpback_lunge_feeding", "Avila yesterday")
        self.assertTrue(found)
        self.assertEqual(found[0].observed_at.date(), (fixtures.NOW - timedelta(days=1)).date())

    def test_content_on_another_assertion_cannot_supply_place_or_date(self):
        for body in ("Humpbacks lunge feeding and dolphins passed Avila today.",
                     "Dolphins passed Avila today and humpbacks lunge feeding.",
                     "Humpbacks lunge feeding today and dolphins passed Avila.",
                     "Humpbacks lunge feeding at Avila and dolphins passed today."):
            with self.subTest(body=body):
                self.assertFalse(self.confirmed(body, "humpback_lunge_feeding"))
        reports = self.confirmed("Humpbacks lunge feeding at Avila today and dolphins passed Pismo yesterday.",
                                 "humpback_lunge_feeding")
        self.assertEqual([(r.place, r.observed_at.date()) for r in reports], [("avila", fixtures.NOW.date())])

    def test_conflicting_or_invalid_explicit_dates_cannot_be_refreshed_by_today(self):
        for stamp in ("September 26 and September 27", "September 1 today", "September 31 today", "today yesterday"):
            with self.subTest(stamp=stamp):
                self.assertFalse(self.confirmed(f"Avila {stamp}. Humpbacks lunge feeding.", "humpback_lunge_feeding"))


class ForecastChronology(unittest.TestCase):
    def test_duplicate_unsorted_and_invalid_axes_are_unusable(self):
        now = fixtures.NOW
        stamps = [(now + timedelta(hours=i)).isoformat() for i in range(3)]
        for times in ([stamps[0]] * 49, stamps[::-1], [stamps[0], "bad", stamps[2]], [True], ["2026-09-27"]):
            with self.subTest(times=times):
                self.assertEqual(weather_scoring.hourly_times({"hourly": {"time": times}}), ())

    def test_event_must_be_bracketed_without_a_missing_hour(self):
        now = fixtures.NOW
        times = (now, now + timedelta(hours=2))
        self.assertIsNone(weather_scoring.hourly_index(times, now + timedelta(minutes=30)))
        self.assertIsNone(weather_scoring.hourly_index(times, now - timedelta(minutes=1)))
        self.assertEqual(weather_scoring.hourly_index(times, now), 0)
        self.assertEqual(weather_scoring.hourly_index((now, now + timedelta(hours=1)), now + timedelta(minutes=30)), 0)
