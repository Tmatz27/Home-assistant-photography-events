"""The production serializer/transport/bridge, including adversarial boundaries."""
import copy
import json
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import test_integration  # Portable namespace for actual shipped pure modules.
test_integration._load_package()
from photography_events.projection import (DestinationPolicy, InvalidProjection, sanitize_envelope, project,
                                           validate_envelope)
from photography_events.core_client import (PhotographyEventsCoreClient, CoreError, CoreAuthenticationError,
                                            CoreVersionError, CoreProtocolError, CoreNotReady)
from photography_events.core_bridge import CoreBridge
from test_core_client import Session, Response
from v17b_fixtures import NOW, payload, policy_documents

HEALTH = {"status": "ready", "api_version": "v1", "schema_version": "0008", "core_version": "0.1.0-dev"}
SOURCES = {**HEALTH, "generated_at": NOW.isoformat(), "items": []}


def reviewed_policy():
    return DestinationPolicy(*policy_documents())


class RuntimeProjectionTests(unittest.TestCase):
    def sanitized(self, data=None):
        return sanitize_envelope(data or payload(), reviewed_policy())

    def view(self, *, now=NOW, fetch=NOW, data=None, view="cant_miss", coverage="verified", **kwargs):
        return project(self.sanitized(data), now=now, fetched_at=fetch, coverage=coverage, view=view, **kwargs)

    def test_real_serializer_recent_fetch_old_assessment_current(self):
        result = self.view()
        self.assertEqual(result["view_state"], "current")
        self.assertTrue(result["items"][0]["actionable"])
        self.assertFalse(result["notifications_enabled"])

    def test_transport_exact_boundary_not_generated_or_saved(self):
        for delta, state in ((-1,"current"),(0,"stale"),(1,"stale")):
            with self.subTest(delta=delta):
                data=payload(); data["generated_at"]=(NOW-timedelta(hours=2)).isoformat()
                result=self.view(now=NOW+timedelta(minutes=15,microseconds=delta), data=data, saved_at=NOW+timedelta(minutes=14))
                self.assertEqual(result["view_state"],state)
                self.assertEqual(result["transport_freshness"],state)
                self.assertEqual(result["assessment_freshness"],"current")

    def test_assessment_exact_boundary_with_new_transport(self):
        for delta,state in ((-1,"current"),(0,"stale"),(1,"stale")):
            data=payload(); data["data_as_of"]=(NOW-timedelta(hours=6,microseconds=delta)).isoformat()
            self.assertEqual(self.view(data=data)["view_state"],state)

    def test_seven_hour_online_response_stale_never_offline(self):
        data=payload(); data["data_as_of"]=(NOW-timedelta(hours=7)).isoformat()
        result=self.view(data=data,view="watching")
        self.assertEqual(result["view_state"],"stale")
        self.assertEqual(result["availability"],"online")
        self.assertFalse(result["items"][0]["actionable"])

    def test_independent_row_boundaries_and_siblings(self):
        for delta,state in ((-1,"current"),(0,"stale"),(1,"stale")):
            data=payload(); row=data["items"][0]; row["valid_until"]=(NOW-timedelta(microseconds=delta)).isoformat()
            other=copy.deepcopy(row); other.update(occurrence_key="tule_elk_rut-2027-09-15",valid_until=(NOW+timedelta(hours=1)).isoformat())
            data["items"].append(other)
            safe=self.sanitized(data)
            held_context=copy.deepcopy(safe)
            for context_row in held_context["items"]:
                context_row.update(eligibility=False,held=True,presentation="held")
            all_rows=project(held_context,now=NOW,fetched_at=NOW,coverage="verified",view="watching")["items"]
            self.assertEqual(all_rows[0]["row_freshness"],state)
            self.assertEqual(all_rows[1]["row_freshness"],"current")
            cant=project(safe,now=NOW,fetched_at=NOW,coverage="verified")
            self.assertEqual(cant["view_state"],"current")
            self.assertIn("tule_elk_rut-2027-09-15",[r["event_id"] for r in cant["items"]])

    def test_all_expired_is_stale_not_empty(self):
        data=payload(); data["items"][0]["valid_until"]=NOW.isoformat()
        self.assertEqual(self.view(data=data)["view_state"],"stale")

    def test_state_precedence_preserves_orthogonal_problems(self):
        data=payload(); data.update(assessment_state="incomplete",data_as_of=(NOW-timedelta(hours=7)).isoformat(),missing_required_sources=["nws"])
        result=self.view(data=data,coverage="unverified",view="watching")
        self.assertEqual(result["view_state"],"incomplete")
        self.assertEqual(result["coverage"]["state"],"unverified")
        self.assertEqual(result["assessment_freshness"],"stale")
        self.assertEqual(result["problems"][0]["source"],"nws")
        data["assessment_id"]=None
        data["items"][0]["assessment_id"]=None
        self.assertEqual(self.view(data=data)["view_state"],"not_assessed")
        self.assertEqual(self.view(data=data)["assessment_state"],"incomplete")

    def test_offline_cache_and_no_cache_distinct(self):
        self.assertEqual(self.view(availability="offline",cached_context=True)["view_state"],"offline_stale")
        self.assertEqual(project(None,now=NOW,fetched_at=None,availability="offline")["view_state"],"unavailable")

    def test_unknown_empty_scope_is_not_assessed_week(self):
        data=payload(); data["items"]=[]
        self.assertEqual(self.view(data=data,coverage="unverified")["view_state"],"coverage_unknown")
        self.assertIsNone(self.view(data=data,coverage="unverified")["counts"]["available"])
        self.assertEqual(self.view(data=data)["view_state"],"empty_assessed")
        self.assertEqual(self.view(data=data,view="birds")["view_state"],"unsupported")

    def test_never_assessed_missing_input_and_fetch(self):
        data=payload(); data["data_as_of"]=None
        self.assertEqual(self.view(data=data)["view_state"],"not_assessed")
        self.assertEqual(self.view(fetch=None)["view_state"],"not_assessed")

    def test_unsupported_views_never_reuse_mixed_products(self):
        safe=self.sanitized()
        for category in ("mammals", "insects", "birds"):
            for presentation in ("cant_miss", "watching", "held", "planner"):
                row=copy.deepcopy(safe["items"][0]);row.update(category=category,presentation=presentation)
                for name in ("birds", "planner"):
                    with self.subTest(category=category,presentation=presentation,view=name):
                        result=project({**safe,"items":[row]},now=NOW,fetched_at=NOW,coverage="verified",view=name)
                        self.assertEqual(result["items"],[])
                        self.assertEqual(result["coverage"]["state"],"unsupported")
                        self.assertEqual(result["view_state"],"unsupported")
                        self.assertIsNone(result["counts"]["available"])

    def test_unsupported_withheld_and_empty_preserve_assessment_states(self):
        for state in ("complete", "incomplete", "degraded"):
            data=payload();data["assessment_state"]=state
            safe=sanitize_envelope(data,DestinationPolicy.load())
            for items in (safe["items"],[]):
                for name in ("birds","planner"):
                    result=project({**safe,"items":items},now=NOW,fetched_at=NOW,view=name)
                    self.assertEqual(result["items"],[])
                    self.assertEqual(result["assessment_state"],state)
                    self.assertEqual(result["view_state"],"unsupported")
                    self.assertNotEqual(result["view_state"],"empty_assessed")
        missing=project(None,now=NOW,fetched_at=None,view="birds")
        self.assertEqual(missing["assessment_state"],"not_assessed")
        self.assertEqual(missing["view_state"],"unsupported")

    def test_real_serializer_ignores_raw_additive_nested_data(self):
        data=payload(); data["bearer_token"]="PRIVATE_SENTINEL"
        row=data["items"][0]; row["geometry"]="PRIVATE_SENTINEL"; row["gear"]["provider_raw"]="PRIVATE_SENTINEL";row["location"]["centroid"]="PRIVATE_SENTINEL"
        self.assertNotIn("PRIVATE_SENTINEL",json.dumps(self.sanitized(data)))

    def test_withheld_recognized_prose_and_geographic_clues_removed(self):
        data=payload(); row=data["items"][0]; row["location"]["policy"]="withheld"
        for key in ("title","reason","detail","awaiting","ethics","safety_summary","best_time_of_day"):
            row[key]="PRIVATE_SENTINEL observer coordinates"
        row["blockers"]=["PRIVATE_SENTINEL"]; row["safety_notes"]=["PRIVATE_SENTINEL"]; row["gear"]["take"]="PRIVATE_SENTINEL"
        safe=self.sanitized(data); wire=json.dumps(safe)
        self.assertNotIn("PRIVATE_SENTINEL",wire)
        self.assertNotIn("synthetic_public",wire)
        self.assertEqual(safe["items"][0]["location"]["latitude"],None)

    def test_public_prose_is_independently_pinned_not_upstream_trusted(self):
        data=payload(); data["items"][0]["reason"]="PRIVATE_SENTINEL"
        data["items"][0]["blockers"]=["PRIVATE_SENTINEL"]
        safe=self.sanitized(data)
        self.assertNotIn("PRIVATE_SENTINEL",json.dumps(safe))
        self.assertEqual(safe["items"][0]["blockers"],["Core check unresolved"])

    def test_default_pending_destination_policy_never_promotes(self):
        safe=sanitize_envelope(payload(),DestinationPolicy.load())
        self.assertEqual(safe["items"][0]["location"]["policy"],"withheld")

    def test_source_and_review_drift_fail_closed(self):
        artifact,review=policy_documents()
        for key,value in (("authority","ha_invented"),("core_reference_commit","f"*40),("policy_revision","new"),("synthetic",True),("schema_version","9999")):
            changed=copy.deepcopy(artifact);changed[key]=value
            self.assertEqual(DestinationPolicy(changed,review).state,"unverified")
        self.assertEqual(DestinationPolicy(artifact,{**review,"reviewed":False}).state,"unverified")
        self.assertEqual(DestinationPolicy(artifact,{**review,"content_sha256":"a"*64}).state,"unverified")

    def test_product_definition_coordinate_drift_fail_closed(self):
        for mutate in (lambda r:r.update(definition_hash="b"*64),lambda r:r["location"].update(latitude=1),lambda r:r["location"].update(longitude=None)):
            data=payload();mutate(data["items"][0]);safe=self.sanitized(data)
            self.assertEqual(safe["items"][0]["location"]["policy"],"withheld")

    def test_strict_fields_and_normal_debug_boundary(self):
        mutations = [lambda d:d.update(schema_version="0001"),lambda d:d.update(mode="shadow"),lambda d:d.update(preview_opportunities=[]),
                     lambda d:d["items"][0].update(eligibility="true"),lambda d:d["items"][0].update(confidence=True),
                     lambda d:d["items"][0].update(urgency=101),lambda d:d["items"][0].update(definition_hash="private"),
                     lambda d:d["items"][0].update(occurrence_key="observer:private:12.5"),lambda d:d["items"][0].update(valid_until="2026-10-10"),
                     lambda d:d["items"][0]["location"].update(latitude=float("nan")),lambda d:d["items"][0].update(blockers=[{}]),
                     lambda d:d["items"][0].update(detail="x"*2049),lambda d:d["items"].append(copy.deepcopy(d["items"][0])),
                     lambda d:d.update(items=d["items"]*501)]
        for mutate in mutations:
            data=payload(); mutate(data)
            with self.subTest(mutation=mutate),self.assertRaises(InvalidProjection):
                validate_envelope(data)

    def test_annual_identity_preserved_generation_and_new_occurrence(self):
        data=payload(); first=self.sanitized(data)["items"][0]["occurrence_key"]
        data.update(assessment_id=18);data["items"][0]["assessment_id"]=18
        self.assertEqual(self.sanitized(data)["items"][0]["occurrence_key"],first)
        data["items"][0]["occurrence_key"]="tule_elk_rut-2027-09-15"
        self.assertNotEqual(self.sanitized(data)["items"][0]["occurrence_key"],first)

    def test_contradictory_complete_source_failures_cannot_act(self):
        data=payload();data["missing_required_sources"]=["nws"]
        with self.assertRaises(InvalidProjection):self.sanitized(data)
        data=payload();data["items"][0]["watching"]=True
        self.assertEqual(self.view(data=data)["items"],[])


class RuntimeTransportBridgeTests(unittest.IsolatedAsyncioTestCase):
    def client(self,*responses,timeout=0.1):
        session=Session(*responses)
        return PhotographyEventsCoreClient(session,"http://core.invalid:8099","SENTINEL_TOKEN",timeout),session

    def bridge(self,client,*,now=NOW,store=None,namespace="one"):
        return CoreBridge(client,store or SimpleNamespace(async_save=AsyncMock(),async_load=AsyncMock(return_value=None)),lambda:now,
                          namespace=namespace,policy=reviewed_policy())

    async def test_private_bounded_normal_endpoints(self):
        client,session=self.client(Response(HEALTH),Response(payload()),Response(SOURCES))
        await client.health(); result=await client.opportunities();await client.source_health()
        self.assertEqual(result.payload["assessment_id"],17)
        self.assertEqual([u.split(":8099")[1] for u,_ in session.requests],["/health/ready","/api/v1/opportunities","/api/v1/sources/health"])
        self.assertTrue(all(not kw["allow_redirects"] for _,kw in session.requests))
        self.assertNotIn("SENTINEL_TOKEN",repr(result))

    async def test_missing_invalid_token_origin_rejected(self):
        for url,token in (("http://x/",""),("http://user:pass@x","x"),("http://x/?secret=x","x"),("http://x","x\r\nInjected: yes")):
            with self.assertRaises(ValueError): PhotographyEventsCoreClient(Session(),url,token)

    async def test_auth_version_503_redirect_and_timeout(self):
        for response,error in ((Response({},401),CoreAuthenticationError),(Response({},403),CoreAuthenticationError),
                               (Response({},503),CoreNotReady),(Response({},302),CoreError),(Response({**HEALTH,"schema_version":"0001"}),CoreVersionError),
                               (Response(HEALTH,delay=1),CoreError),(OSError("secret"),CoreError)):
            client,_=self.client(response,timeout=0.01)
            with self.assertRaises(error) as caught: await client.health()
            self.assertNotIn("secret",str(caught.exception))

    async def test_malformed_json_and_size_limit(self):
        class Bad(Response):
            async def iter_chunked(self,size): yield b"not JSON"
        class Large(Response):
            async def iter_chunked(self,size): yield b"x"*(2*1024*1024+1)
        for r in (Bad({}),Large({})):
            client,_=self.client(r)
            with self.assertRaises(CoreProtocolError):await client.health()

    async def test_source_errors_fixed_and_bounded(self):
        data=copy.deepcopy(SOURCES);data["items"]=[{"key":"PRIVATE_SENTINEL","state":"DOWN","error_code":"PRIVATE_SENTINEL"}]
        client,_=self.client(Response(data));safe=await client.source_health()
        self.assertNotIn("PRIVATE_SENTINEL",json.dumps(safe))

    async def test_success_cache_restart_ages_original_fetch(self):
        client,_=self.client(Response(HEALTH),Response(payload()),Response(SOURCES)); first=self.bridge(client)
        await first.refresh();saved=first.store.async_save.call_args.args[0]
        offline,_=self.client(OSError());store=SimpleNamespace(async_load=AsyncMock(return_value=saved),async_save=AsyncMock())
        restart=self.bridge(offline,now=NOW+timedelta(minutes=15),store=store);await restart.initialize();await restart.refresh()
        view=restart.view("watching",coverage="verified")
        self.assertEqual(view["view_state"],"offline_stale");self.assertEqual(view["fetched_at"],NOW.isoformat())
        self.assertFalse(view["items"][0]["actionable"])
        self.assertEqual(saved["payload"]["data_as_of"],payload()["data_as_of"])

    async def test_fetch_never_renews_row_or_assessment(self):
        data=payload();data["items"][0]["valid_until"]=NOW.isoformat();data["data_as_of"]=(NOW-timedelta(hours=7)).isoformat()
        client,_=self.client(Response(HEALTH),Response(data),Response(SOURCES));b=self.bridge(client);await b.refresh()
        v=b.view("watching",coverage="verified")
        self.assertEqual(v["transport_freshness"],"current");self.assertEqual(v["view_state"],"stale")
        self.assertEqual(v["items"][0]["valid_until"],NOW.isoformat())

    async def test_incomplete_preserves_complete_cache(self):
        complete=payload();incomplete=payload();incomplete.update(assessment_state="incomplete",items=[])
        client,_=self.client(Response(HEALTH),Response(complete),Response(SOURCES),Response(HEALTH),Response(incomplete),Response(SOURCES),OSError())
        b=self.bridge(client);await b.refresh();await b.refresh();self.assertEqual(b.payload["assessment_state"],"incomplete")
        self.assertEqual(b.store.async_save.await_count,1);await b.refresh();self.assertEqual(len(b.view("watching")["items"]),1)

    async def test_auth_and_protocol_failures_hide_rich_cache(self):
        for failure in (Response({},401),Response({**HEALTH,"schema_version":"0011"}),Response({})):
            client,_=self.client(Response(HEALTH),Response(payload()),Response(SOURCES),failure)
            b=self.bridge(client);await b.refresh();await b.refresh()
            self.assertIsNone(b.payload);self.assertEqual(b.view("watching")["items"],[])

    async def test_cache_namespace_and_version_revalidation(self):
        client,_=self.client(Response(HEALTH),Response(payload()),Response(SOURCES));b=self.bridge(client);await b.refresh();saved=b.store.async_save.call_args.args[0]
        for key,value in (("namespace","new"),("projection_version","old"),("fetched_at",None)):
            bad={**saved,key:value};store=SimpleNamespace(async_load=AsyncMock(return_value=bad))
            r=self.bridge(client,store=store);await r.initialize();self.assertIsNone(r.cached)

    async def test_seven_day_cache_retention_and_future_timestamp_fail_closed(self):
        client,_=self.client(Response(HEALTH),Response(payload()),Response(SOURCES));b=self.bridge(client);await b.refresh();saved=b.store.async_save.call_args.args[0]
        r=self.bridge(client,now=NOW+timedelta(days=7),store=SimpleNamespace(async_load=AsyncMock(return_value=saved)))
        await r.initialize();self.assertIsNone(r.cached)
        data=payload();data["generated_at"]=(NOW+timedelta(minutes=2)).isoformat()
        c,_=self.client(Response(HEALTH),Response(data));r=self.bridge(c);await r.refresh()
        self.assertEqual(r.availability,"invalid_response")

    async def test_cache_is_sanitized_even_for_withheld_recognized_fields(self):
        data=payload();data["items"][0]["location"]["policy"]="withheld";data["items"][0]["detail"]="PRIVATE_SENTINEL"
        client,_=self.client(Response(HEALTH),Response(data),Response(SOURCES));b=self.bridge(client);await b.refresh()
        saved=b.store.async_save.call_args.args[0]
        self.assertNotIn("PRIVATE_SENTINEL",json.dumps(saved));self.assertNotIn("SENTINEL_TOKEN",json.dumps(saved))
        r=self.bridge(client,store=SimpleNamespace(async_load=AsyncMock(return_value=saved)));await r.initialize()
        self.assertIsNotNone(r.cached)
