import assert from "node:assert/strict";
import test from "node:test";
import {loadCoreCard} from "./card-harness.mjs";

function view(overrides={}) {
  const now=Date.now();
  return {projection_version:"ha.v17.1",entry_id:"entry",snapshot_id:"revision",availability:"online",
    assessment_state:"complete",view_state:"current",coverage:{state:"verified"},
    generated_at:new Date(now).toISOString(),data_as_of:new Date(now-30*60000).toISOString(),fetched_at:new Date(now).toISOString(),
    expires_at:new Date(now+15*60000).toISOString(),problems:[],next_cursor:null,
    choices:{available:false,authority:"pending_core"},notifications_enabled:false,
    items:[{occurrence_key:"tule_elk_rut-2026-09-15",phenomenon_key:"tule_elk_rut",title:"Synthetic test window",
      category:"mammals",location:{policy:"curated_public_site",name:"Synthetic public visitor site"},
      starts_at:new Date(now-3600000).toISOString(),ends_at:new Date(now+86400000).toISOString(),valid_until:new Date(now+7200000).toISOString(),
      data_as_of:new Date(now-30*60000).toISOString(),row_state:"current",row_freshness:"current",actionable:true,held:false,
      evidence_state:"calendar_presence",safety_state:"safe",access_state:"public",condition_state:"not_required",reason:"Synthetic public reason",
      blockers:[],detail:"Synthetic fixture only",awaiting:"",gear:{take:"Synthetic lens"},definition_key:"tule_elk_rut",definition_version:"legacy-0.16.1-1"}],...overrides};
}
function fixture(mode="action_hero",result=view()) {
  const {Card,context,source}=loadCoreCard();const card=new Card();card.setConfig({mode,entry_id:"entry"});
  const requests=[];card.hass={connected:true,user:{id:"admin"},states:{},callWS:async msg=>{requests.push(msg);return structuredClone(result);},callService:()=>{throw new Error("No writes allowed");}};
  card._views.set(({action_hero:"cant_miss",watching:"watching",calendar_outlook:"planner",birds:"birds",timeline:"planner"})[mode],result);
  card._render();return {card,requests,context,source};
}

test("shipped artifact excludes provider catalogs, science and browser fallback",()=>{
  const {source}=loadCoreCard();
  for(const forbidden of ["weather/get_forecasts","buildEvents(","METEOR_SHOWERS","BIRD_MIGRATION_WINDOWS","sunEquatorial","set_event_choice","fetch("])
    assert.ok(!source.includes(forbidden),forbidden);
});
test("fresh read-only card renders familiar four views and header",()=>{
  const {card}=fixture();const html=card._bodyHtml()+card._navigationHtml();
  for(const label of ["CAN'T MISS","WATCHING","YEAR PLANNER","BIRDS","Photography Events","Synthetic test window"])assert.ok(html.includes(label));
  assert.match(html,/Read-only Core/);assert.equal(card.style.display,"");
});
test("unknown complete empty is a coverage warning, never a checked week",()=>{
  const {card}=fixture("action_hero",view({items:[],view_state:"coverage_unknown",coverage:{state:"unverified"}}));
  assert.match(card._bodyHtml(),/Coverage is unverified/);
  assert.doesNotMatch(card._bodyHtml(),/Nothing worth changing plans|quiet week|entire week has been checked/i);
});
test("no integration still shows a useful unavailable card with navigation",()=>{
  const {card}=fixture("timeline");card._views.clear();
  assert.match(card._bodyHtml(),/Settings &gt; Devices/);assert.equal(card._isBackendMode(),true);
  assert.match(card._navigationHtml(),/YEAR PLANNER/);assert.ok(card._root);
});
test("incomplete and degraded have separate truthful messages",()=>{
  for(const state of ["incomplete","degraded"]){const {card}=fixture("action_hero",view({view_state:state,assessment_state:state}));assert.match(card._bodyHtml(),new RegExp(state));assert.doesNotMatch(card._bodyHtml(),/Synthetic test window/);}
});
test("unsupported planner and birds retain layout and honest limits",()=>{
  for(const mode of ["calendar_outlook","birds"]){const {card}=fixture(mode,view({view_state:"unsupported",items:[],coverage:{state:"unsupported"}}));assert.match(card._bodyHtml(),/no reviewed Core coverage/);assert.match(card._bodyHtml(),/unsupported/);assert.ok(card._root);}
});
test("shadow flags cannot make a normal current row",()=>{
  const {card}=fixture("action_hero",view({view_state:"shadow_only"}));assert.doesNotMatch(card._bodyHtml(),/Synthetic test window/);
});
test("online old assessment is stale independently of fresh HTTP",()=>{
  const old=new Date(Date.now()-7*3600000).toISOString();const {card}=fixture("watching",view({data_as_of:old}));
  assert.equal(card._agedView().view_state,"stale");assert.equal(card._agedView().items[0].actionable,false);
  assert.equal(card._agedView().items[0].safety_state,"unknown");
});
test("exactly fifteen minutes expires actual HA transport",()=>{
  const {card}=fixture("action_hero",view({fetched_at:new Date(Date.now()-15*60000).toISOString()}));assert.equal(card._agedView().view_state,"stale");assert.equal(card._agedView().items.length,0);
});
test("one expired row cannot invalidate still current siblings",()=>{
  const v=view();const expired={...v.items[0],occurrence_key:"tule_elk_rut-2025-09-15",valid_until:new Date(Date.now()).toISOString()};v.items.unshift(expired);
  const {card}=fixture("action_hero",v);assert.equal(card._agedView().items.length,1);assert.equal(card._agedView().items[0].occurrence_key,"tule_elk_rut-2026-09-15");
});
test("HA disconnect labels cached historical context and removes action",()=>{
  const {card}=fixture("watching");card._hass.connected=false;
  assert.equal(card._agedView().view_state,"offline_stale");assert.equal(card._agedView().items[0].actionable,false);
  assert.match(card._bodyHtml(),/historical/);
});
test("auth failure hides cached rich rows immediately on summary push",()=>{
  const {card}=fixture("watching");card.hass={...card._hass,states:{"sensor.custom_name":{attributes:{projection_version:"ha.v17.1",entry_id:"entry",snapshot_id:"auth",availability:"auth_required"}}}};
  assert.equal(card._views.size,0);assert.doesNotMatch(card._bodyHtml(),/Synthetic test window/);
});
test("principal change cannot retain another user's cache",()=>{
  const {card}=fixture("watching");card.hass={...card._hass,user:{id:"other"}};assert.equal(card._views.size,0);
});
test("choices stay visibly disabled with no persistence or service call",async()=>{
  const {card,requests}=fixture();const html=card._eventControlsHtml();
  assert.equal((html.match(/button disabled/g)||[]).length,3);assert.match(html,/Nothing is saved/);assert.match(html,/Notifications are disabled/);
  await card._saveChoice("tule_elk_rut-2026-09-15","follow");assert.equal(requests.length,0);
});
test("safe details escape supplied strings and preserve identity",()=>{
  const {card}=fixture("watching");const r=view().items[0];r.detail='<script>secret</script>';const html=card._coreDetailHtml(r);
  assert.doesNotMatch(html,/<script>/);assert.match(html,/&lt;script&gt;/);assert.match(card._coreRowHtml(r),/data-expand="tule_elk_rut-2026-09-15"/);
});
test("summary discovery follows attributes even after entity ID customization",()=>{
  const {Card}=loadCoreCard();const card=new Card();card.setConfig({});card.hass={states:{"sensor.my_camera":{attributes:{projection_version:"ha.v17.1",entry_id:"custom-entry"}}}};
  assert.equal(card._entryId(),"custom-entry");
});
test("only authenticated HA WS projections are requested, without Core secrets",async()=>{
  const {card,requests}=fixture();card._connected=true;await card._refreshCore();
  assert.equal(requests.length,1);assert.equal(requests[0].type,"photography_events/get_view");
  assert.deepEqual(Object.keys(requests[0]).sort(),["entry_id","limit","projection_version","type","view"]);
  assert.equal(requests[0].projection_version,"ha.v17.1");card.disconnectedCallback();
});
test("detach discards an in-flight response and cancels refresh timers",async()=>{
  const {card}=fixture();let release;card._hass.callWS=()=>new Promise(r=>release=r);card._connected=true;
  const read=card._refreshCore();await Promise.resolve();card.disconnectedCallback();card._views.clear();release(view());await read;
  assert.equal(card._views.size,0);assert.equal(card._eventInterval,null);assert.equal(card._fetchInterval,null);
});
test("unchanged renders keep the same HA host and live DOM",()=>{
  const {card}=fixture();const root=card._root,writes=root.writes;card._render();assert.equal(card._root,root);assert.equal(root.writes,writes);
});
test("navigation, more, expansion and month switch preserve local state",()=>{
  const v=view();v.items=Array.from({length:8},(_,i)=>({...v.items[0],occurrence_key:`tule_elk_rut-202${i}-09-15`}));
  const {card}=fixture("watching",v);const root=card._root;
  root.querySelectorAll("[data-more]")[0].click();assert.ok(card._moreBuckets.has("watching"));assert.equal(card._root,root);
  root.querySelectorAll("[data-expand]")[0].click();assert.ok(card._expanded.size);
  root.querySelectorAll("[data-tab]").find(b=>b.dataset.tab==="calendar_outlook").click();assert.equal(card._selectedView,"calendar_outlook");assert.equal(card._root,root);
  root.querySelectorAll("[data-view]").find(b=>b.dataset.view==="calendar").click();assert.equal(card._calendarView,true);
});
test("composed scroll owners include slot host and dashboard",()=>{
  const {card,context}=fixture();const outer={scrollHeight:500,clientHeight:100,parentElement:null};const slot={scrollHeight:300,clientHeight:100,parentElement:outer};
  context.getComputedStyle=()=>({overflowY:"auto"});context.document.scrollingElement=outer;
  const owners=card._scrollOwners({scrollHeight:10,clientHeight:10,assignedSlot:slot});assert.equal(owners[0],slot);assert.equal(owners[1],outer);
});
test("modal content is stable between unchanged ticks",()=>{
  const {card}=fixture("watching");let writes=0;card._dialog={scrollTop:37,set innerHTML(v){writes++;this.html=v;},querySelector:()=>null};card._dialogKey="tule_elk_rut-2026-09-15";
  card._updateEventDialog();card._updateEventDialog();assert.equal(writes,1);assert.equal(card._dialog.scrollTop,37);
});
test("month view draws supplied duration bars without inventing appointments",()=>{
  const {card}=fixture("calendar_outlook",view({view_state:"unsupported"}));card._calendarView=true;
  const html=card._bodyHtml();assert.match(html,/core-duration-bar/);assert.match(html,/not timed appointments/);
  assert.match(html,/data-open="tule_elk_rut-2026-09-15"/);
});
test("card config accepts presentation fields and drops credential/source extras",()=>{
  const {Card}=loadCoreCard();const card=new Card();card.setConfig({title:"Camera",mode:"__proto__",core_token:"PRIVATE_SENTINEL",core_url:"http://private"});
  assert.equal(card._config.mode,"action_hero");assert.ok(!JSON.stringify(card._config).includes("PRIVATE_SENTINEL"));
  assert.equal(card._config.title,"Camera");
});
