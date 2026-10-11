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
  const {card}=fixture("calendar_outlook",view({view_state:"current"}));card._calendarView=true;
  const html=card._bodyHtml();assert.match(html,/core-duration-bar/);assert.match(html,/not timed appointments/);
  assert.match(html,/data-open="tule_elk_rut-2026-09-15"/);
});
test("card config accepts presentation fields and drops credential/source extras",()=>{
  const {Card}=loadCoreCard();const card=new Card();card.setConfig({title:"Camera",mode:"__proto__",core_token:"PRIVATE_SENTINEL",core_url:"http://private"});
  assert.equal(card._config.mode,"action_hero");assert.ok(!JSON.stringify(card._config).includes("PRIVATE_SENTINEL"));
  assert.equal(card._config.title,"Camera");
});

function scheduledFixture({cached=true, responder}={}) {
  let clock=Date.now(),serial=0;const timers=new Map(),calls=[];
  class Clock extends Date { static now(){return clock;} }
  const runtime=loadCoreCard({Date:Clock,setTimeout:(fn,ms)=>{const id=++serial;timers.set(id,{fn,at:clock+ms});return id;},clearTimeout:id=>timers.delete(id)});
  const card=new runtime.Card();card.setConfig({mode:"watching",entry_id:"entry"});
  const v=view();card.hass={connected:true,user:{id:"shared-user"},states:{},callWS:async msg=>{calls.push(msg);return responder?responder(msg):Promise.reject({code:"rate_limited"});}};
  if(cached)card._views.set("watching",v);card._connected=true;card._render();
  async function settle(){for(let i=0;i<15;i++)await Promise.resolve();}
  async function advance(ms){clock+=ms;const due=[...timers].filter(([,t])=>t.at<=clock);for(const [id,t] of due){timers.delete(id);t.fn();}await settle();}
  return {card,v,timers,calls,advance,settle,runtime,get now(){return clock;}};
}

test("unsupported Birds and Planner never render mixed or withheld ordinary rows",()=>{
  const mixed=view();mixed.items=["mammals","insects","birds"].flatMap(category=>["cant_miss","watching","held","planner"].map(presentation=>({...mixed.items[0],category,presentation,location:{policy:"withheld"}})));
  for(const mode of ["birds","calendar_outlook"]){
    const {card}=fixture(mode,{...mixed,view_state:"unsupported",coverage:{state:"unsupported"}});
    assert.equal(card._agedView().items.length,0);assert.doesNotMatch(card._bodyHtml(),/Synthetic test window|data-open="tule_elk/);
    assert.match(card._bodyHtml(),/no reviewed Core coverage/);assert.doesNotMatch(card._bodyHtml(),/No products in this verified scope/);
  }
  const {card}=fixture("birds",mixed);assert.ok(card._agedView().items.every(r=>r.category==="birds"));
});

test("two dashboards on one user recover from shared rate limit without an outage",async()=>{
  let previous=-Infinity;const responder=()=>{const now=a.now;if(now-previous<1000)throw {code:"rate_limited"};previous=now;return structuredClone(a.v);};
  const a=scheduledFixture({responder}),b=scheduledFixture({responder});
  await Promise.all([a.card._refreshCore(),b.card._refreshCore()]);
  assert.equal(b.card._readBusy,true);assert.equal(b.card._agedView().availability,"online");
  assert.doesNotMatch(b.card._bodyHtml(),/Core is offline|Core view unavailable/);
  await a.advance(3000);await b.advance(3000);
  assert.equal(b.calls.length,2);assert.equal(b.card._readBusy,false);assert.equal(b.card._agedView().availability,"online");
  assert.equal(b.card._views.get("watching").fetched_at,a.v.fetched_at);
  a.card.disconnectedCallback();b.card.disconnectedCallback();
});

test("no-cache rate limit shows busy and retries are bounded and coalesced",async()=>{
  const f=scheduledFixture({cached:false});await f.card._refreshCore();
  assert.equal(f.card._agedView().view_state,"busy");assert.match(f.card._bodyHtml(),/View read is busy/);assert.doesNotMatch(f.card._bodyHtml(),/Core is offline|Core is unavailable/);
  for(let i=0;i<20;i++)await f.card._refreshCore();assert.equal(f.calls.length,1);assert.equal(f.timers.size,1);
  for(let i=0;i<6;i++)await f.advance(4000);
  assert.equal(f.calls.length,5);assert.equal(f.timers.size,0);assert.equal(f.card._requestPending,false);
  f.card.disconnectedCallback();
});

test("retained rate-limited data keeps original stamps and ages expired rows",async()=>{
  const f=scheduledFixture();f.v.items[0].valid_until=new Date(f.now+500).toISOString();
  const stamps=[f.v.fetched_at,f.v.data_as_of,f.v.expires_at];await f.card._refreshCore();await f.advance(1000);
  const aged=f.card._agedView();assert.equal(aged.availability,"online");assert.equal(aged.items[0].actionable,false);assert.equal(aged.items[0].safety_state,"unknown");assert.equal(aged.items[0].eligibility,false);
  assert.deepEqual([aged.fetched_at,aged.data_as_of,aged.expires_at],stamps);
  await f.advance(15*60000);assert.equal(f.card._agedView().view_state,"stale");f.card.disconnectedCallback();
});

test("retry timers cancel on disconnect, entry and view changes or incompatibility",async()=>{
  for(const kind of ["disconnect","entry","view","incompatible"]){
    const f=scheduledFixture();await f.card._refreshCore();const retry=f.card._retryTimer;assert.ok(f.timers.has(retry));
    if(kind==="disconnect")f.card.disconnectedCallback();
    if(kind==="entry")f.card.setConfig({mode:"watching",entry_id:"other"});
    if(kind==="view")f.card._root.querySelectorAll("[data-tab]").find(b=>b.dataset.tab==="birds").click();
    if(kind==="incompatible")f.card.hass={...f.card._hass,states:{"sensor.connection":{attributes:{projection_version:"ha.v17.1",entry_id:"entry",availability:"incompatible"}}}};
    assert.equal(f.timers.has(retry),false);assert.equal(f.card._retryCount,0);
    f.card.disconnectedCallback();await f.settle();assert.equal(f.timers.size,0);
  }
});

test("an incompatible retry response clears caches and cannot schedule another read",async()=>{
  let reads=0;const f=scheduledFixture({responder:()=>{if(++reads===1)throw {code:"rate_limited"};return {projection_version:"ha.v99",items:[]};}});
  await f.card._refreshCore();await f.advance(4000);assert.equal(f.card._views.size,0);assert.equal(f.timers.size,0);assert.equal(f.card._readBusy,false);
  f.card.disconnectedCallback();
});

test("busy recovery preserves the card host, expansion, focus and inner scroll",async()=>{
  let reads=0;const f=scheduledFixture({responder:()=>{if(++reads===1)throw {code:"rate_limited"};return structuredClone(f.v);}});
  const root=f.card._root,id=f.v.items[0].occurrence_key;f.card._expanded.add(id);f.card._moreBuckets.add("watching");
  let inner={scrollTop:37},writes=root.writes,focused=0;const query=root.querySelectorAll.bind(root);
  root.querySelector=()=>{if(root.writes!==writes){inner={scrollTop:0};writes=root.writes;}return inner;};
  root.querySelectorAll=selector=>query(selector).map(el=>{el.focus=()=>{focused++;f.card.shadowRoot.activeElement=el;};return el;});
  f.card.shadowRoot.activeElement=root.querySelectorAll("[data-expand]")[0];
  await f.card._refreshCore();await f.advance(4000);
  assert.equal(f.card._root,root);assert.ok(f.card._expanded.has(id));assert.ok(f.card._moreBuckets.has("watching"));
  assert.ok(focused>=2);assert.equal(root.querySelector().scrollTop,37);f.card.disconnectedCallback();
});
