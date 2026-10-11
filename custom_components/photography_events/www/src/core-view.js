const CORE_COPY = {
  current:"Current Core assessment", empty_assessed:"No opportunities in the verified assessed scope",
  coverage_unknown:"Coverage is unverified. Core has not established that the whole week was assessed.",
  incomplete:"Core assessment is incomplete. Required inputs are missing.", degraded:"Core assessment is degraded.",
  stale:"Core assessment or transport has expired. These are held historical details.",
  offline_stale:"Core is offline. Cached context is historical and cannot authorize travel.",
  not_assessed:"A current Core assessment is not available.", unsupported:"This view has no reviewed Core coverage.",
  unavailable:"Core is unavailable. Complete or repair the private connection in Settings > Devices & services.",
  shadow_only:"Shadow diagnostics cannot authorize opportunities.",
  busy:"View read is busy. Waiting for a bounded retry or the next refresh."
};
const CORE_VIEWS = {
  _navigationHtml() {
    const selected=this._selectedView || this._config.mode;
    return `<nav class="pe-navigation" aria-label="Photography views">${[[MODE_HERO,"CAN'T MISS"],["watching","WATCHING"],[MODE_OUTLOOK,"YEAR PLANNER"],[MODE_BIRDS,"BIRDS"]].map(([view,label])=>`<button type="button" data-tab="${view}" aria-pressed="${selected===view || (view===MODE_OUTLOOK && selected===MODE_TIMELINE)}">${label}</button>`).join("")}</nav>`;
  },
  _agedView() {
    const key=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const original=this._views.get(key);
    if (!original) return {items:[],view_state:this._readBusy?"busy":"unavailable",availability:this._readBusy?(this._summaryState()?.attributes?.availability || "unknown"):"connection_required",coverage:{state:"unverified"}};
    const v={...original,items:original.items.map(row=>({...row}))};
    const now=Date.now();
    const transportExpired=!v.fetched_at || now>=Date.parse(v.fetched_at)+CORE_TRANSPORT_MS;
    const assessmentExpired=!v.data_as_of || now>=Date.parse(v.data_as_of)+CORE_ASSESSMENT_MS;
    const disconnected=this._hass?.connected===false || Boolean(this._transportError);
    if (disconnected) { v.view_state="offline_stale"; v.availability="offline"; }
    else if ((transportExpired || assessmentExpired) && ["current","empty_assessed","coverage_unknown"].includes(v.view_state)) v.view_state="stale";
    for (const row of v.items) if (disconnected || transportExpired || assessmentExpired || now>=Date.parse(row.valid_until)) {
      row.actionable=false; row.held=true; row.row_state="stale"; row.row_freshness="stale";
      row.eligibility=false; row.watching=false; row.presentation="held";
      row.safety_state=row.access_state=row.condition_state="unknown";
      row.reason="Current scoped Core assessment unavailable.";row.awaiting="A current reviewed Core assessment.";
    }
    if (v.view_state==="shadow_only" || !["online","offline"].includes(v.availability)) v.items=[];
    if (v.view_state==="unsupported" || v.coverage?.state==="unsupported") v.items=[];
    if (key==="birds") v.items=v.coverage?.state==="verified" ? v.items.filter(r=>r.category==="birds") : [];
    if (key==="planner" && v.coverage?.state!=="verified") v.items=[];
    if (key==="cant_miss") v.items=v.view_state==="current" && v.coverage?.state==="verified" && v.availability==="online" ? v.items.filter(r=>r.actionable===true && r.row_state==="current") : [];
    return v;
  },
  _bodyHtml() {
    const v=this._agedView(), key=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const labels={cant_miss:"Can't Miss",watching:"Watching",planner:"Year Planner",birds:"Birds"};
    const status=this._transportError || (this._readBusy?CORE_COPY.busy:null) || CORE_COPY[v.view_state] || CORE_COPY.unavailable;
    let rows=v.items;
    const categories=[...new Set(rows.map(r=>r.category))];
    if(this._activeFilters===null)this._activeFilters=new Set(categories);
    this._knownCoreCategories ||= new Set();
    for (const c of categories) if(!this._knownCoreCategories.has(c)){this._activeFilters.add(c);this._knownCoreCategories.add(c);}
    // Filters are local presentation only; no unsupported Core category query.
    rows=rows.filter(r=>this._activeFilters.has(r.category));
    this._displayEvents=new Map(rows.map(r=>[r.occurrence_key,r]));
    const more=this._moreBuckets.has(key), visible=more?rows:rows.slice(0,5);
    const filters=categories.length>1?`<div class="filters">${categories.map(c=>`<button data-category="${escapeHtml(c)}" aria-pressed="${this._activeFilters.has(c)}">${escapeHtml(c)}</button>`).join("")}</div>`:"";
    const controls=key==="planner"?`<div class="view-switch"><button data-view="list" aria-pressed="${!this._calendarView}">List</button><button data-view="calendar" aria-pressed="${this._calendarView}">Month</button></div>`:"";
    return `<div class="header"><div class="header-title">${escapeHtml(this._config.title)}</div><div class="header-subtitle">${labels[key]} · Read-only Core development build</div></div>
      <div class="cm-watch-summary" role="status"><strong>${escapeHtml(status)}</strong>
      <p>Connection: ${escapeHtml(v.availability)} · Assessment: ${escapeHtml(v.assessment_state || "not_assessed")} · Coverage: ${escapeHtml(v.coverage?.state || "unverified")}</p>
      ${v.data_as_of?`<p>Assessment input: ${escapeHtml(coreDate(v.data_as_of))}<br>Validated HA fetch: ${escapeHtml(coreDate(v.fetched_at))}</p>`:""}
      ${v.problems?.length?`<p>${v.problems.map(p=>escapeHtml(`${p.source}: ${p.code}`)).join(" · ")}</p>`:""}
      <p>Core v1 supplies a limited normal mammal slice. Year-wide planning, Birds and calendar precision are unsupported. Shadow results are excluded.</p></div>
      ${filters}${controls}<div class="outlook">${key==="planner" && this._calendarView?this._coreMonthHtml(rows):visible.map(r=>this._coreRowHtml(r)).join("")}
      ${!rows.length?`<div class="empty-card"><ha-icon icon="mdi:camera-outline"></ha-icon><strong>${v.view_state==="empty_assessed"?"No products in this verified scope":"No current authorized rows in this view"}</strong><p>${escapeHtml(status)}</p></div>`:""}
      ${rows.length>5?`<button data-more="${key}">${more?"Show five previews":`More · ${rows.length-5} additional published rows`}</button>`:""}
      ${v.next_cursor?`<button type="button" data-page="next">Load more published rows</button>`:""}</div>
      <div class="footer">Choices unavailable · Notifications disabled · No legacy intelligence fallback</div>`;
  },
  _coreRowHtml(r) {
    const id=r.occurrence_key, open=this._expanded.has(id);
    const publicLocation=r.location?.policy==="curated_public_site";
    return `<article class="cm-watch-row" style="--event-color:#85d481"><h4><ha-icon icon="mdi:camera-outline"></ha-icon> ${escapeHtml(r.title)}</h4>
      <p>${escapeHtml(coreDate(r.starts_at))} — ${escapeHtml(coreDate(r.ends_at))}<br>Published window; appointment precision unavailable.</p>
      <p>${publicLocation?escapeHtml(r.location.name):"Location withheld"} · ${escapeHtml(r.row_state)} · ${escapeHtml(r.evidence_state)}</p>
      ${r.reason?`<p>${escapeHtml(r.reason)}</p>`:""}
      <button type="button" data-expand="${escapeHtml(id)}" aria-expanded="${open}">${open?"Close details":"Details"}</button>
      <button type="button" data-open="${escapeHtml(id)}">Open window</button>
      ${open?this._coreDetailHtml(r):""}</article>`;
  },
  _coreDetailHtml(r) {
    return `<div class="event-detail"><p>${escapeHtml(r.detail || "No additional public detail supplied.")}</p>
      <p>${escapeHtml(r.awaiting || "")}</p><p>Safety: ${escapeHtml(r.safety_state)} · Access: ${escapeHtml(r.access_state)} · Conditions: ${escapeHtml(r.condition_state)}</p>
      ${r.blockers?.length?`<p>Held: ${r.blockers.map(escapeHtml).join(" · ")}</p>`:""}
      <details data-section="${escapeHtml(r.occurrence_key)}:gear"><summary>Gear and ethics</summary><dl class="outlook-detail-grid">${Object.entries(r.gear || {}).filter(([,v])=>Array.isArray(v)?v.length:Boolean(v)).map(([k,v])=>`<dt>${escapeHtml(k.replaceAll("_"," "))}</dt><dd>${escapeHtml(Array.isArray(v)?v.join(" · "):v)}</dd>`).join("") || "<dd>No public gear recommendation</dd>"}</dl><p>${escapeHtml(r.ethics || "")}</p></details>
      <p>Input: ${escapeHtml(coreDate(r.data_as_of))} · Valid until: ${escapeHtml(coreDate(r.valid_until))}</p>
      <p>Definition ${escapeHtml(r.definition_key)} · ${escapeHtml(r.definition_version)}</p>${this._eventControlsHtml()}</div>`;
  },
  _coreMonthHtml(rows) {
    const month=new Date(); month.setDate(1); month.setMonth(month.getMonth()+this._calendarOffset);
    month.setHours(0,0,0,0);
    const gridStart=new Date(month);gridStart.setDate(1-month.getDay());
    const days=Array.from({length:42},(_,i)=>{const day=new Date(gridStart);day.setDate(day.getDate()+i);return day;});
    const weeks=Array.from({length:6},(_,week)=>{
      const dates=days.slice(week*7,week*7+7);
      const bars=rows.map(r=>{
        const covered=dates.map((d,i)=>{const next=new Date(d);next.setDate(d.getDate()+1);return Date.parse(r.starts_at)<next.getTime() && Date.parse(r.ends_at)>=d.getTime()?i:null;}).filter(i=>i!==null);
        if(!covered.length)return "";
        return `<button class="core-duration-bar" style="grid-column:${covered[0]+1}/${covered.at(-1)+2}" data-open="${escapeHtml(r.occurrence_key)}" title="${escapeHtml(`${r.title}: ${coreDate(r.starts_at)} — ${coreDate(r.ends_at)}`)}">${escapeHtml(r.title)}</button>`;
      }).join("");
      return `<div class="core-calendar-week">${dates.map(d=>`<span class="core-calendar-day" ${d.getMonth()!==month.getMonth()?'style="opacity:.4"':""}>${d.getDate()}</span>`).join("")}${bars}</div>`;
    }).join("");
    return `<div class="calendar"><div class="month-header"><button data-month="-1" aria-label="Previous month">‹</button><strong>${escapeHtml(month.toLocaleDateString(undefined,{month:"long",year:"numeric"}))}</strong><button data-month="1" aria-label="Next month">›</button></div>
      <p>Published Core ranges only; these bars are not timed appointments. This month has not been assessed as a complete plan.</p>
      <div class="core-calendar-week">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=>`<span>${d}</span>`).join("")}</div>${weeks}</div>`;
  },
  _openCalendarEvent(key) {
    if (!this._displayEvents.has(key)) return;
    if (!this._dialog) {
      this._dialog=document.createElement("dialog"); this.shadowRoot.appendChild(this._dialog);
      this._dialog.addEventListener("close",()=>this._dialogOpener?.focus?.({preventScroll:true}));
    }
    this._dialogOpener=this.shadowRoot.activeElement; this._dialogKey=key; this._updateEventDialog();
    this._dialog.showModal?.();
  },
  _updateEventDialog() {
    if(!this._dialog)return;
    const row=this._agedView().items.find(r=>r.occurrence_key===this._dialogKey);
    const html=row?`<h3>${escapeHtml(row.title)}</h3>${this._coreDetailHtml(row)}<button data-close="true">Close</button>`:`<p>This occurrence is no longer in the current sanitized snapshot.</p><button data-close="true">Close</button>`;
    if(this._dialogLastHtml===html)return;
    this._dialogLastHtml=html;
    const scroll=this._dialog.scrollTop || 0;
    this._dialog.innerHTML=html; this._dialog.scrollTop=scroll;
    this._dialog.querySelector("[data-close]")?.addEventListener("click",()=>this._dialog.close());
  }
};
const originalCoreBind=PhotographyEventsCard.prototype._bindEvents;
PhotographyEventsCard.prototype._bindEvents=function(){originalCoreBind.call(this);for(const b of this._root?.querySelectorAll("[data-page]") || [])b.addEventListener("click",()=>this._refreshCore(true));};
Object.assign(PhotographyEventsCard.prototype,CORE_VIEWS);
