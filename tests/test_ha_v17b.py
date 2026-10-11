"""Real HA lifecycle/registry/Store/authorization boundary for the active v17 code."""
import copy
import importlib.util
import inspect
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import test_integration
test_integration._load_package()
from v17b_fixtures import NOW, payload, policy_documents

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if HAS_HA:
    from aiohttp import web
    from homeassistant.core import HomeAssistant
    from homeassistant.config_entries import ConfigEntry, ConfigEntries, ConfigEntryNotReady, ConfigEntryAuthFailed, ConfigEntryState
    from homeassistant.helpers import entity_registry as er, issue_registry as ir, device_registry as dr
    from homeassistant.helpers.storage import Store
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.setup import async_setup_component
    from homeassistant import auth, loader
    from custom_components import photography_events as integration
    from custom_components.photography_events import config_flow, websocket
    from custom_components.photography_events.coordinator import PhotographyEventsCoordinator
    from custom_components.photography_events.core_bridge import CoreBridge
    from custom_components.photography_events.core_client import CoreAssessment, CoreError, CoreAuthenticationError
    from custom_components.photography_events.projection import DestinationPolicy
    from custom_components.photography_events.sensor import (CantMissSensor, PlanningOutlookSensor, NextOpportunitySensor,
                                                            ConnectionStateSensor, SourceStateSensor, BestSkyScoreSensor)
    from custom_components.photography_events.binary_sensor import PhotographyActionOpportunity
    from custom_components.photography_events.calendar import PhotographyCalendar
    from custom_components.photography_events.repairs import CoreConnectionRepair


@unittest.skipUnless(HAS_HA, "Real HA is exercised in the dedicated CI matrix")
class V17BHomeAssistantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.name == "nt":
            permissions=patch("os.fchmod",create=True);permissions.start();self.addCleanup(permissions.stop)
            from aiohttp.resolver import ThreadedResolver
            resolver=patch("homeassistant.helpers.aiohttp_client.AsyncResolver",ThreadedResolver)
            resolver.start();self.addCleanup(resolver.stop)
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.hass=HomeAssistant(self.directory.name)
        self.addAsyncCleanup(self.hass.async_stop,force=True)
        self.hass.config_entries=ConfigEntries(self.hass,{})
        await er.async_load(self.hass)
        await dr.async_load(self.hass)
        # HA 2025's shared HTTP resolver expects the normal network bootstrap.
        loader.async_setup(self.hass)
        self.hass.auth=await auth.auth_manager_from_config(self.hass,[{"type":"homeassistant"}],[])
        self.assertTrue(await async_setup_component(self.hass,"network",{}))
        self.entry=self.make_entry()
        self.hass.config_entries._entries[self.entry.entry_id]=self.entry
        self.clock=NOW
        self.c=PhotographyEventsCoordinator(self.hass,self.entry)
        self.addAsyncCleanup(self.c.async_shutdown)
        self.policy=DestinationPolicy(*policy_documents())
        self.client=SimpleNamespace(health=AsyncMock(),opportunities=AsyncMock(return_value=CoreAssessment.parse(payload())),
                                    source_health=AsyncMock(return_value={"items":[]}))
        self.c.bridge=CoreBridge(self.client,Store(self.hass,2,"v17b-test-cache"),lambda:self.clock,namespace="one",policy=self.policy)
        await self.c.bridge.refresh();self.c.async_set_updated_data(self.c.view())
        self.hass.data["photography_events"]={self.entry.entry_id:self.c}
        self.connection=SimpleNamespace(user=SimpleNamespace(id="admin",is_active=True,is_admin=True),send_error=Mock(),send_result=Mock())

    def make_entry(self,version=3,data=None,options=None,entry_id="v17b-test"):
        values=dict(domain="photography_events",entry_id=entry_id,title="Photography Events",source="user",version=version,minor_version=1,
                    data=data if data is not None else {"core_url":"http://core.invalid","core_token":"PRIVATE_TOKEN"},
                    options=options or {},unique_id="photography_events",discovery_keys=MappingProxyType({}),subentries_data=())
        entry = ConfigEntry(**{k:v for k,v in values.items() if k in inspect.signature(ConfigEntry).parameters})
        entry._async_set_state(self.hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
        return entry

    def msg(self,view="watching",**kwargs):
        return {"id":1,"type":"photography_events/get_view","entry_id":self.entry.entry_id,"projection_version":"ha.v17.1","view":view,"limit":50,**kwargs}

    async def read(self,msg):
        await websocket.get_view.__wrapped__(self.hass,self.connection,msg)

    async def test_real_shared_session_connects_loopback_contract_server(self):
        now=datetime.now(timezone.utc);requests=[]
        data=payload(now)
        async def handler(request):
            requests.append((request.path,request.headers.get("Authorization")))
            if request.path!="/health/ready" and request.headers.get("Authorization")!="Bearer PRIVATE_TOKEN":
                return web.json_response({},status=401)
            if request.path=="/health/ready":return web.json_response({"status":"ready","core_version":"0.1.0-dev","api_version":"v1","schema_version":"0008"})
            if request.path=="/api/v1/sources/health":return web.json_response({**data,"items":[]})
            return web.json_response(data)
        app=web.Application();app.router.add_get('/{tail:.*}',handler)
        runner=web.AppRunner(app);await runner.setup();self.addAsyncCleanup(runner.cleanup)
        site=web.TCPSite(runner,"127.0.0.1",0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        entry=self.make_entry(entry_id="fresh",data={"core_url":f"http://127.0.0.1:{port}","core_token":"PRIVATE_TOKEN"})
        self.assertIsNone(await config_flow.validate_connection(self.hass,entry.data))
        fresh=PhotographyEventsCoordinator(self.hass,entry);self.addAsyncCleanup(fresh.async_shutdown)
        await fresh.async_initialize();await fresh._async_update_data()
        self.assertEqual(fresh.bridge.availability,"online")
        self.assertEqual(fresh.view()["view_state"],"coverage_unknown")
        self.assertTrue({"/health/ready","/api/v1/opportunities","/api/v1/sources/health"}.issubset({p for p,_ in requests}))
        self.assertTrue(all(p=="/health/ready" or auth=="Bearer PRIVATE_TOKEN" for p,auth in requests))
        self.assertNotIn("PRIVATE_TOKEN",json.dumps(fresh.view("watching")))
        self.assertEqual([r["location"]["policy"] for r in fresh.view("watching")["items"]],["withheld"])
        # Complete the vertical slice through actual HA platform setup too.
        target=Path(self.directory.name)/"custom_components"/"photography_events"
        shutil.copytree(Path(integration.__file__).parent,target,ignore=shutil.ignore_patterns("__pycache__"))
        loader.async_setup(self.hass)
        self.hass.config_entries.async_update_entry(self.entry,data=dict(entry.data))
        self.entry._async_set_state(self.hass,ConfigEntryState.NOT_LOADED,None)
        self.assertTrue(await async_setup_component(self.hass,"photography_events",{}),
                        f"Loaded HA components: {sorted(self.hass.config.components)}")
        await self.hass.async_block_till_done()
        active=self.hass.data["photography_events"][self.entry.entry_id]
        self.assertEqual(active.bridge.availability,"online")
        self.assertEqual(len(er.async_entries_for_config_entry(er.async_get(self.hass),self.entry.entry_id)),8)
        self.assertTrue(self.hass.data.get("photography_events_card_registered"))
        self.assertTrue(await self.hass.config_entries.async_unload(self.entry.entry_id))

    async def test_v1_and_v2_migration_preserve_credentials_options_and_ids(self):
        for version in (1,2):
            original={"ebird_api_key":"OLD_PRIVATE","enabled_categories":[]}
            entry=self.make_entry(version,data=original,options={"google_api_key":"OLD_ROUTE","enabled_categories":[]},entry_id=f"migration-{version}")
            self.hass.config_entries._entries[entry.entry_id]=entry
            self.assertTrue(await integration.async_migrate_entry(self.hass,entry))
            self.assertEqual(entry.version,3);self.assertEqual(entry.unique_id,"photography_events")
            self.assertEqual(entry.data["ebird_api_key"],"OLD_PRIVATE");self.assertEqual(entry.options["google_api_key"],"OLD_ROUTE")
            self.assertEqual(entry.data["enabled_categories"],[]);self.assertEqual(entry.options["enabled_categories"],[])
            self.assertEqual(entry.data["connection_state"],"needs_connection")
            self.assertTrue(await integration.async_migrate_entry(self.hass,entry))

    async def test_future_config_version_rejected_without_changes(self):
        entry=self.make_entry(4);before=dict(entry.data)
        self.assertFalse(await integration.async_migrate_entry(self.hass,entry));self.assertEqual(dict(entry.data),before)

    async def test_entity_registry_customizations_survive_migration(self):
        registry=er.async_get(self.hass)
        for suffix,domain in (("cant_miss","sensor"),("planning_outlook","sensor"),("next_opportunity","sensor"),("best_sky_score","sensor"),("action_opportunity","binary_sensor"),("calendar","calendar")):
            item=registry.async_get_or_create(domain,"photography_events",f"{self.entry.entry_id}_{suffix}",config_entry=self.entry)
            renamed=f"{domain}.my_photo_{suffix}"
            registry.async_update_entity(item.entity_id,new_entity_id=renamed,name="My customized photography entity",disabled_by=er.RegistryEntryDisabler.USER)
            self.assertTrue(await integration.async_migrate_entry(self.hass,self.entry))
            after=registry.async_get(renamed)
            self.assertEqual(after.unique_id,f"{self.entry.entry_id}_{suffix}");self.assertEqual(after.name,"My customized photography entity")
            self.assertEqual(after.disabled_by,er.RegistryEntryDisabler.USER)

    async def test_real_coordinator_has_zero_legacy_collectors_or_actions(self):
        forbidden=("_sources","_build","_apply_routing","_fetch_forecasts","_fetch_surf_alerts","_fetch_inaturalist","event_state","async_set_event_choice")
        for name in forbidden:self.assertFalse(hasattr(self.c,name),name)
        fired=[];unsub=self.hass.bus.async_listen("photography_events_opportunity",lambda e:fired.append(e));self.addCleanup(unsub)
        await self.c._async_update_data();self.client.health.side_effect=CoreError();await self.c._async_update_data()
        await self.hass.async_block_till_done()
        self.assertEqual(fired,[]);self.assertFalse(self.c.view()["notifications_enabled"])

    async def test_compact_entities_no_arrays_tokens_or_coordinates(self):
        for cls in (CantMissSensor,PlanningOutlookSensor,NextOpportunitySensor,ConnectionStateSensor,SourceStateSensor,BestSkyScoreSensor):
            entity=cls(self.c,self.entry);wire=json.dumps(entity.extra_state_attributes)
            self.assertLess(len(wire.encode()),4096)
            for forbidden in ("PRIVATE_TOKEN","latitude","longitude",'"items"','"events"','"gear"'):self.assertNotIn(forbidden,wire)
        self.assertIsNone(CantMissSensor(self.c,self.entry).native_value)
        self.assertFalse(BestSkyScoreSensor(self.c,self.entry).available)

    async def test_action_calendar_and_choices_never_revive_notifications(self):
        action=PhotographyActionOpportunity(self.c,self.entry)
        self.assertFalse(action.available);self.assertIsNone(action.is_on)
        calendar=PhotographyCalendar(self.c,self.entry)
        self.assertFalse(calendar.available);self.assertIsNone(calendar.event)
        self.assertEqual(await calendar.async_get_events(self.hass,NOW,NOW+timedelta(days=365)),[])
        integration._async_register_services(self.hass)
        for service,data in (("set_event_choice",{"event_id":"x","choice":"follow"}),("ingest_report",{"body":"PRIVATE_SENTINEL"})):
            with self.assertRaises(ServiceValidationError):
                await self.hass.services.async_call("photography_events",service,data,blocking=True)

    async def test_expiry_changes_common_revision_without_refresh(self):
        first=self.c.view("cant_miss")["snapshot_id"]
        self.assertEqual(first,self.c.view("watching")["snapshot_id"])
        self.clock+=timedelta(minutes=15)
        await self.c._expire(self.clock)
        self.assertEqual(self.c.view()["view_state"],"stale")
        self.assertNotEqual(first,self.c.view()["snapshot_id"])
        self.client.opportunities.assert_awaited_once()

    async def test_repeated_same_material_fetch_keeps_revision(self):
        first=self.c.view()["snapshot_id"];self.clock+=timedelta(minutes=1)
        data=payload();data["generated_at"]=self.clock.isoformat();self.client.opportunities.return_value=CoreAssessment.parse(data)
        await self.c._async_update_data();self.assertEqual(first,self.c.view()["snapshot_id"])

    async def test_revoked_token_uses_ha_reauth_and_hides_cache(self):
        self.client.health.side_effect=CoreAuthenticationError()
        with self.assertRaises(ConfigEntryAuthFailed):await self.c._async_update_data()
        self.assertEqual(self.c.view("watching")["items"],[])
        self.assertEqual(self.c.view()["availability"],"auth_required")

    async def test_fresh_outage_first_refresh_uses_ha_retry(self):
        self.c.data=None;self.c.bridge.cached=None;self.client.health.side_effect=CoreError()
        with self.assertRaises(ConfigEntryNotReady):await self.c.async_config_entry_first_refresh()

    async def test_ws_authorization_version_and_schema_no_origin_injection(self):
        self.connection.user=None;await self.read(self.msg());self.assertEqual(self.connection.send_error.call_args.args[1],"unauthorized")
        self.connection.user=SimpleNamespace(id="admin",is_admin=True,is_active=True)
        await self.read(self.msg(projection_version="ha.v99"));self.assertEqual(self.connection.send_error.call_args.args[1],"unsupported_projection")
        for fields in ({"core_url":"http://evil"},{"core_token":"private"},{"limit":51},{"cursor":"x"*129},{"view":"debug"}):
            with self.assertRaises(Exception):websocket.get_view._ws_schema(self.msg(**fields))

    async def test_ws_nonadmin_entry_permissions_fail_closed(self):
        registry=er.async_get(self.hass)
        registry.async_get_or_create("sensor","photography_events",f"{self.entry.entry_id}_cant_miss",config_entry=self.entry)
        permissions=SimpleNamespace(check_entity=Mock(return_value=False))
        self.connection.user=SimpleNamespace(id="limited",is_admin=False,is_active=True,permissions=permissions)
        await self.read(self.msg());self.assertEqual(self.connection.send_error.call_args.args[1],"unauthorized")
        permissions.check_entity.return_value=True
        await self.read(self.msg());self.connection.send_result.assert_called_once()

    async def test_ws_rates_and_safe_paging(self):
        self.connection.send_result.reset_mock();await self.read(self.msg())
        result=self.connection.send_result.call_args.args[1]
        self.assertLess(len(json.dumps(result).encode()),128*1024)
        self.assertNotIn("PRIVATE_TOKEN",json.dumps(result))
        await self.read(self.msg());self.assertEqual(self.connection.send_error.call_args.args[1],"rate_limited")

    async def test_ws_cursor_binds_user_entry_view_and_snapshot(self):
        data=payload();other=copy.deepcopy(data["items"][0]);other["occurrence_key"]="tule_elk_rut-2027-09-15";data["items"].append(other)
        self.client.opportunities.return_value=CoreAssessment.parse(data);await self.c._async_update_data()
        await self.read(self.msg(limit=1));cursor=self.connection.send_result.call_args.args[1]["next_cursor"]
        self.assertIsInstance(cursor,str)
        self.connection.user=SimpleNamespace(id="other",is_admin=True,is_active=True)
        await self.read(self.msg(cursor=cursor));self.assertEqual(self.connection.send_error.call_args.args[1],"snapshot_expired")
        self.connection.user.id="admin";self.hass.data[websocket.STATE_KEY]["rates"].clear()
        self.clock+=timedelta(minutes=15);await self.read(self.msg(cursor=cursor))
        self.assertEqual(self.connection.send_error.call_args.args[1],"snapshot_expired")

    async def test_ws_detail_from_same_snapshot_no_upstream_request(self):
        revision=self.c.view()["snapshot_id"]
        await websocket.get_detail.__wrapped__(self.hass,self.connection,{"id":2,"entry_id":self.entry.entry_id,
                "projection_version":"ha.v17.1","snapshot_id":revision,"occurrence_key":"tule_elk_rut-2026-09-15"})
        self.connection.send_result.assert_called_once();self.client.opportunities.assert_awaited_once()

    async def test_cursor_fetch_clock_cannot_be_renewed_by_new_fetch(self):
        data=payload();other=copy.deepcopy(data["items"][0]);other["occurrence_key"]="tule_elk_rut-2027-09-15";data["items"].append(other)
        self.client.opportunities.return_value=CoreAssessment.parse(data);await self.c._async_update_data()
        revision=self.c.view()["snapshot_id"]
        await self.read(self.msg(limit=1));cursor=self.connection.send_result.call_args.args[1]["next_cursor"]
        self.clock+=timedelta(minutes=14);await self.c._async_update_data()
        self.assertEqual(revision,self.c.view()["snapshot_id"])
        self.clock+=timedelta(minutes=1);self.hass.data[websocket.STATE_KEY]["rates"].clear()
        await self.read(self.msg(cursor=cursor))
        self.assertEqual(self.connection.send_error.call_args.args[1],"snapshot_expired")

    async def test_setup_dormant_repair_and_unload_without_provider_start(self):
        entry=self.make_entry(3,data={"ebird_api_key":"OLD_PRIVATE"},entry_id="dormant")
        self.hass.config_entries._entries[entry.entry_id]=entry
        with patch.object(integration,"_async_register_card",AsyncMock()) as card,patch.object(integration,"async_register"),\
             patch.object(self.hass.config_entries,"async_forward_entry_setups",AsyncMock()),\
             patch.object(self.hass.config_entries,"async_unload_platforms",AsyncMock(return_value=True)):
            self.assertTrue(await integration.async_setup_entry(self.hass,entry));card.assert_awaited_once()
            dormant=self.hass.data["photography_events"][entry.entry_id]
            self.assertIsNone(dormant.bridge);self.assertEqual(dormant.view()["availability"],"connection_required")
            self.assertIsNotNone(ir.async_get(self.hass).async_get_issue("photography_events",f"core_connection_required_{entry.entry_id}"))
            self.assertTrue(await integration.async_unload_entry(self.hass,entry))
            self.assertNotIn(entry.entry_id,self.hass.data["photography_events"])

    async def test_reconfigure_blank_token_reauth_and_secure_forms(self):
        flow=config_flow.PhotographyEventsConfigFlow();flow.hass=self.hass
        flow.context={"source":"reconfigure","entry_id":self.entry.entry_id}
        result=await flow.async_step_reconfigure()
        self.assertNotIn("PRIVATE_TOKEN",str(result["data_schema"]))
        with patch.object(config_flow,"validate_connection",AsyncMock(return_value=None)) as validate,\
             patch.object(self.hass.config_entries,"async_schedule_reload"):
            result=await flow.async_step_reconfigure({"core_url":"http://CORE.INVALID:80/","core_token":""})
            self.assertEqual(result["type"],"abort");self.assertEqual(self.entry.data["core_token"],"PRIVATE_TOKEN")
            validate.assert_awaited_once()
        flow=config_flow.PhotographyEventsConfigFlow();flow.hass=self.hass;flow.context={"source":"reauth","entry_id":self.entry.entry_id}
        with patch.object(config_flow,"validate_connection",AsyncMock(return_value=None)),patch.object(self.hass.config_entries,"async_schedule_reload"):
            result=await flow.async_step_reauth_confirm({"core_url":"http://replacement.invalid","core_token":"NEW_PRIVATE"})
            self.assertEqual(result["reason"],"reauth_successful");self.assertEqual(self.entry.data["core_token"],"NEW_PRIVATE")
            self.assertEqual(self.entry.unique_id,"photography_events")

    async def test_repair_completion_updates_existing_entry(self):
        repair=CoreConnectionRepair(self.entry.entry_id);repair.hass=self.hass
        with patch("custom_components.photography_events.repairs.validate_connection",AsyncMock(return_value=None)),\
             patch.object(self.hass.config_entries,"async_schedule_reload"):
            result=await repair.async_step_init({"core_url":"http://replacement.invalid","core_token":"NEW_PRIVATE"})
            self.assertEqual(result["type"],"create_entry");self.assertEqual(self.entry.data["core_token"],"NEW_PRIVATE")

    async def test_real_store_restart_and_token_namespace_change(self):
        await self.c.bridge.refresh()
        second=CoreBridge(self.client,Store(self.hass,2,"v17b-test-cache"),lambda:NOW+timedelta(hours=1),namespace="one",policy=self.policy)
        await second.initialize();self.assertIsNotNone(second.cached)
        wrong=CoreBridge(self.client,Store(self.hass,2,"v17b-test-cache"),lambda:NOW,namespace="changed",policy=self.policy)
        await wrong.initialize();self.assertIsNone(wrong.cached)

    async def test_reconfigure_two_endpoints_never_forward_old_bearer(self):
        ledgers=[[],[]]
        async def endpoint(index, token):
            async def handler(request):
                header=request.headers.get("Authorization");ledgers[index].append(header)
                if header != "Bearer " + token:return web.json_response({},status=401)
                if request.path=="/health/ready":return web.json_response({"status":"ready","core_version":"0.1.0-dev","api_version":"v1","schema_version":"0008"})
                data=payload(datetime.now(timezone.utc))
                if request.path=="/api/v1/sources/health":data["items"]=[]
                return web.json_response(data)
            app=web.Application();app.router.add_get('/{tail:.*}',handler)
            runner=web.AppRunner(app);await runner.setup();self.addAsyncCleanup(runner.cleanup)
            site=web.TCPSite(runner,"127.0.0.1",0);await site.start()
            return f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        first=await endpoint(0,"PRIVATE_TOKEN");second=await endpoint(1,"NEW_PRIVATE")
        self.hass.config_entries.async_update_entry(self.entry,data={"core_url":first,"core_token":"PRIVATE_TOKEN"})
        flow=config_flow.PhotographyEventsConfigFlow();flow.hass=self.hass;flow.context={"source":"reconfigure","entry_id":self.entry.entry_id}
        original=dict(self.entry.data)
        with patch.object(self.hass.config_entries,"async_schedule_reload"):
            result=await flow.async_step_reconfigure({"core_url":second,"core_token":""})
            self.assertEqual(result["errors"]["base"],"new_token_required")
            self.assertEqual(ledgers,[[],[]]);self.assertEqual(dict(self.entry.data),original)
            result=await flow.async_step_reconfigure({"core_url":first+"/","core_token":""})
            self.assertEqual(result["type"],"abort");self.assertEqual(ledgers[0],["Bearer PRIVATE_TOKEN"]*3)
            result=await flow.async_step_reconfigure({"core_url":second,"core_token":"BAD_NEW"})
            self.assertEqual(result["errors"]["base"],"invalid_auth");self.assertEqual(self.entry.data["core_url"],first+"/")
            result=await flow.async_step_reconfigure({"core_url":second,"core_token":"NEW_PRIVATE"})
            self.assertEqual(result["type"],"abort");self.assertEqual(self.entry.data["core_token"],"NEW_PRIVATE")
        self.assertNotIn("Bearer PRIVATE_TOKEN",ledgers[1]);self.assertEqual(self.entry.unique_id,"photography_events")

    async def test_reconfigure_origin_identity_and_failure_before_http(self):
        for same in ("http://CORE.INVALID/","http://core.invalid:80"):
            self.assertEqual(config_flow.canonical_origin(same),config_flow.canonical_origin("http://core.invalid"))
        for changed in ("https://core.invalid","http://other.invalid","http://core.invalid:8099"):
            flow=config_flow.PhotographyEventsConfigFlow();flow.hass=self.hass;flow.context={"source":"reconfigure","entry_id":self.entry.entry_id}
            with patch.object(config_flow,"validate_connection",AsyncMock()) as validate:
                result=await flow.async_step_reconfigure({"core_url":changed,"core_token":""})
                self.assertEqual(result["errors"]["base"],"new_token_required");validate.assert_not_awaited()
                self.assertEqual(self.entry.data["core_url"],"http://core.invalid")
                self.assertNotIn("PRIVATE_TOKEN",str(result))

    async def test_cursor_rechecks_each_row_even_with_unchanged_revision(self):
        data=payload();other=copy.deepcopy(data["items"][0]);other.update(occurrence_key="tule_elk_rut-2027-09-15",valid_until=(NOW+timedelta(seconds=2)).isoformat())
        data["items"].append(other);self.client.opportunities.return_value=CoreAssessment.parse(data);await self.c._async_update_data()
        immutable=self.c.view("watching")
        with patch.object(self.c,"view",return_value=immutable):
            await self.read(self.msg(limit=1));cursor=self.connection.send_result.call_args.args[1]["next_cursor"]
            self.clock+=timedelta(seconds=2);self.hass.data[websocket.STATE_KEY]["rates"].clear();self.connection.send_result.reset_mock()
            await self.read(self.msg(cursor=cursor))
            self.assertEqual(self.connection.send_error.call_args.args[1],"snapshot_expired")
            self.connection.send_result.assert_not_called()

    async def test_two_same_user_connections_share_rate_limit_and_recover(self):
        other=SimpleNamespace(user=self.connection.user,send_error=Mock(),send_result=Mock())
        with patch.object(websocket.time,"monotonic",return_value=10):
            await self.read(self.msg())
            await websocket.get_view.__wrapped__(self.hass,other,self.msg())
            self.assertEqual(other.send_error.call_args.args[1],"rate_limited");other.send_result.assert_not_called()
        with patch.object(websocket.time,"monotonic",return_value=11.1):
            await websocket.get_view.__wrapped__(self.hass,other,self.msg())
            self.assertEqual(other.send_result.call_args.args[1]["availability"],"online")
            self.assertEqual(other.send_result.call_args.args[1]["fetched_at"],self.connection.send_result.call_args.args[1]["fetched_at"])

    async def test_isolated_full_setup_real_entities_reload_and_unload(self):
        # A disposable configuration, never the user's running HA installation.
        target=Path(self.directory.name)/"custom_components"/"photography_events"
        shutil.copytree(Path(integration.__file__).parent,target,ignore=shutil.ignore_patterns("__pycache__"))
        loader.async_setup(self.hass)
        self.hass.config_entries.async_update_entry(self.entry,data={"enabled_categories":[],"ebird_api_key":"OLD_PRIVATE"},version=1)
        self.entry._async_set_state(self.hass,ConfigEntryState.NOT_LOADED,None)
        self.assertTrue(await async_setup_component(self.hass,"photography_events",{}),
                        f"Loaded HA components: {sorted(self.hass.config.components)}")
        self.assertEqual(self.entry.state, ConfigEntryState.LOADED)
        self.assertTrue(self.hass.data.get("photography_events_card_registered"))
        await self.hass.async_block_till_done()
        self.assertEqual(self.entry.version,3)
        registry=er.async_get(self.hass)
        entities=er.async_entries_for_config_entry(registry,self.entry.entry_id)
        self.assertEqual(len(entities),8)
        ids={e.unique_id:e.entity_id for e in entities}
        wanted=ids[f"{self.entry.entry_id}_cant_miss"]
        renamed=registry.async_update_entity(wanted,new_entity_id="sensor.my_existing_photo_card",name="My Photography")
        self.assertEqual(self.hass.states.get(ids[f"{self.entry.entry_id}_action_opportunity"]).state,"unavailable")
        self.assertTrue(await self.hass.config_entries.async_reload(self.entry.entry_id))
        await self.hass.async_block_till_done()
        self.assertEqual(registry.async_get(renamed.entity_id).name,"My Photography")
        self.assertTrue(await self.hass.config_entries.async_unload(self.entry.entry_id))
        self.assertNotIn(self.entry.entry_id,self.hass.data["photography_events"])
