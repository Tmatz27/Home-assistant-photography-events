// Actual shipped-card HTML, with explicitly synthetic sanitized review inputs.
import fs from "node:fs";
import path from "node:path";
import {loadCoreCard} from "../tests/card-harness.mjs";

const output=process.argv[2];
if(!output)throw new Error("Supply a scratch/output directory");
fs.mkdirSync(output,{recursive:true});
const {Card,source}=loadCoreCard();
const now=Date.now(),iso=delta=>new Date(now+delta).toISOString();
const row={occurrence_key:"tule_elk_rut-2026-09-15",phenomenon_key:"tule_elk_rut",title:"Synthetic review window — not live wildlife",
  category:"mammals",location:{policy:"curated_public_site",key:"synthetic_public",name:"Synthetic public visitor destination",latitude:0,longitude:0},
  starts_at:iso(-3600000),ends_at:iso(3*86400000),data_as_of:iso(-30*60000),valid_until:iso(2*3600000),
  row_state:"current",row_freshness:"current",actionable:true,held:false,eligibility:true,watching:false,
  evidence_state:"calendar_presence",safety_state:"safe",access_state:"public",condition_state:"not_required",
  reason:"Synthetic independently reviewed presentation witness.",awaiting:"",blockers:[],detail:"Sanitized test evidence. No real sighting, policy approval or deployment is claimed.",
  gear:{take:"Synthetic lens",optional:["Synthetic support"]},ethics:"Synthetic public guidance",definition_key:"tule_elk_rut",definition_version:"legacy-0.16.1-1"};
const base={projection_version:"ha.v17.1",entry_id:"synthetic_review",snapshot_id:"synthetic_revision",availability:"online",assessment_state:"complete",
  view_state:"current",freshness:"current",coverage:{state:"verified"},data_as_of:iso(-30*60000),fetched_at:iso(0),generated_at:iso(0),expires_at:iso(15*60000),
  choices:{available:false,authority:"pending_core"},notifications_enabled:false,problems:[],items:[row]};
const examples=[
  ["normal-scoped-witness","action_hero",base],
  ["actual-build-unknown-coverage","action_hero",{...base,view_state:"coverage_unknown",coverage:{state:"unverified"},items:[]}],
  ["held-withheld-context","watching",{...base,view_state:"coverage_unknown",coverage:{state:"unverified"},items:[{...row,title:"Opportunity location withheld",location:{policy:"withheld",name:"Location withheld",key:null,latitude:null,longitude:null},actionable:false,eligibility:false,held:true,row_state:"held",reason:"Current scoped Core assessment unavailable.",detail:"",gear:{}}]}],
  ["incomplete","action_hero",{...base,view_state:"incomplete",assessment_state:"incomplete",items:[],problems:[{source:"nws",code:"required_source_unavailable"}]}],
  ["online-stale","watching",{...base,data_as_of:iso(-7*3600000),view_state:"stale",items:[{...row,actionable:false,held:true,row_state:"held"}]}],
  ["offline-cached","watching",{...base,availability:"offline",view_state:"offline_stale",items:[{...row,actionable:false,held:true,row_state:"held"}]}],
  ["birds-unsupported","birds",{...base,view_state:"unsupported",coverage:{state:"unsupported"},items:[]}],
  ["planner-published-ranges","calendar_outlook",{...base,view_state:"unsupported",coverage:{state:"unsupported"},items:[{...row,actionable:false,held:true,row_state:"held"}]}],
  ["connection-required","action_hero",{...base,availability:"connection_required",view_state:"unavailable",items:[]}],
];
const cards=examples.map(([name,mode,v])=>{
  const card=new Card();card.setConfig({mode,entry_id:base.entry_id});card._hass={connected:true,states:{}};
  card._views.set(({action_hero:"cant_miss",watching:"watching",calendar_outlook:"planner",birds:"birds"})[mode],structuredClone(v));
  card._calendarView=mode==="calendar_outlook";card._expanded.add(row.occurrence_key);
  return {name,html:`<section><h2>${name}</h2><div class="example"><ha-card><div class="card-content">${card._navigationHtml()}${card._bodyHtml()}</div></ha-card></div></section>`,styles:card._styles()};
});
const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V17B sanitized synthetic render evidence</title>
<style>body{background:#101216;color:#f5f5f7;margin:0;padding:24px;font-family:system-ui;--ha-card-background:#1d1d1f;--primary-text-color:#f5f5f7;--secondary-text-color:#afb6c2;--divider-color:#ffffff2d;--primary-color:#85d481}.example{max-width:820px;margin:auto}ha-card{display:block}section{margin:36px 0}button{font:inherit;padding:8px 12px}button:focus-visible{outline:2px solid #85d481}ha-icon{display:inline-block}ha-icon:before{content:'📷'}${cards[0].styles}</style>
<h1>V17B sanitized synthetic render evidence</h1><p><strong>TEST EVIDENCE ONLY — NOT LIVE CORE DATA OR PRODUCTION POLICY APPROVAL.</strong> The first example is a synthetic reviewed-scope witness; the shipped build retains unknown coverage and pending destination review. All HTML below comes from the actual bundled card's render methods. Static buttons illustrate controls; this evidence file makes no network requests.</p>
${cards.map(c=>c.html).join("\n")}</html>`;
fs.writeFileSync(path.join(output,"V17B-CARD-RENDER-EVIDENCE.html"),html);
fs.writeFileSync(path.join(output,"V17B-CARD-STATE-EXAMPLES.json"),JSON.stringify({synthetic_only:true,production_eligibility:false,examples:examples.map(([name,mode,projection])=>({name,mode,projection}))},null,2));
if(source.includes("weather/get_forecasts")||source.includes("buildEvents("))throw new Error("Retired browser path present");
console.log(`Rendered ${cards.length} explicitly synthetic normal/failure cases from the shipped card.`);
