class PhotographyEventsCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this._config={...DEFAULT_CONFIG};
    this._connected=false; this._initialized=false; this._root=null; this._lastHtml="";
    this._activeFilters=null; this._expanded=new Set(); this._collapsed=new Set(); this._openedBuckets=new Set();
    this._moreBuckets=new Set(); this._calendarView=false; this._calendarOffset=0;
    this._displayEvents=new Map(); this._detailState=new Map(); this._anchorGeneration=0;
    this._views=new Map(); this._selectedView=null; this._requestGeneration=0;
    this._retryCount=0; this._retryTimer=null; this._readDelay=null; this._readBusy=false;
  }
  set hass(value) {
    const previous=this._summaryRevision, previousUser=this._hass?.user?.id, previousEntry=this._entryId(); this._hass=value;
    const state=this._summaryState();
    if (!this._explicitMode && !this._initialViewSelected && state?.attributes?.initial_view) {
      this._selectedView=({cant_miss:MODE_HERO,watching:"watching",planner:MODE_OUTLOOK,birds:MODE_BIRDS})[state.attributes.initial_view] || MODE_HERO;
      this._initialViewSelected=true;
    }
    if ((previousUser && previousUser!==value?.user?.id) || (previousEntry && previousEntry!==this._entryId()) || ["auth_required","incompatible","invalid_response","connection_required"].includes(state?.attributes?.availability)) {
      this._cancelReadWork(); this._views.clear();
    }
    this._summaryRevision=`${state?.attributes?.entry_id || ""}:${state?.attributes?.snapshot_id || ""}:${state?.attributes?.availability || ""}:${value?.connected}`;
    if (this._connected && (!this._initialized || previous!==this._summaryRevision)) { this._initialized=true; this._refreshCore(); }
    this._render();
  }
  _summaryState() {
    const states=Object.values(this._hass?.states || {});
    return states.find(s=>s.attributes?.projection_version==="ha.v17.1" && (!this._config.entry_id || s.attributes.entry_id===this._config.entry_id));
  }
  _entryId() { return this._config.entry_id || this._summaryState()?.attributes?.entry_id; }
  _isBackendMode() { return true; }
  setConfig(config) {
    if (!config) throw new Error("Photography Events Card configuration is required");
    this._explicitMode=Object.hasOwn(CORE_VIEW,config.mode); this._initialViewSelected=false;
    this._config={title:typeof config.title==="string"?config.title.slice(0,256):DEFAULT_CONFIG.title,
                  mode:this._explicitMode?config.mode:MODE_HERO,
                  entry_id:typeof config.entry_id==="string"?config.entry_id.slice(0,128):""};
    this._selectedView=this._config.mode;
    this._cancelReadWork(); this._views.clear(); this._lastHtml="";
    if (this._connected) this._refreshCore(); this._render();
  }
  connectedCallback() {
    this._connected=true; this._initialized=true; this._refreshCore();
    this._clearIntervals();
    this._eventInterval=setInterval(()=>this._render(),1000);
    this._fetchInterval=setInterval(()=>this._refreshCore(),5*60000);
    this._render();
  }
  disconnectedCallback() {
    this._connected=false; this._cancelReadWork(); this._anchorGeneration++;
    this._cancelAnchor?.(); this._clearIntervals();
  }
  _clearIntervals() { clearInterval(this._eventInterval); clearInterval(this._fetchInterval); this._eventInterval=this._fetchInterval=null; }
  _cancelReadWork() {
    this._requestGeneration++; clearTimeout(this._retryTimer); this._retryTimer=null;
    if (this._readDelay) { clearTimeout(this._readDelay.timer); this._readDelay.resolve(false); this._readDelay=null; }
    this._refreshQueued=false; this._retryCount=0; this._readBusy=false;
  }
  _waitRead(ms) {
    return new Promise(resolve=>{ this._readDelay={resolve,timer:setTimeout(()=>{this._readDelay=null;resolve(true);},ms)}; });
  }
  async _refreshCore(append=false, retry=false) {
    if (!this._connected || !this._hass?.callWS || !this._entryId()) return;
    if (["auth_required","incompatible","invalid_response","connection_required"].includes(this._summaryState()?.attributes?.availability)) return;
    if (this._retryTimer) return; // Summary pushes share the existing scheduled retry.
    if (this._requestPending) { this._refreshQueued=true; return; }
    if (!retry) this._retryCount=0;
    const view=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const old=this._views.get(view), entry=this._entryId();
    if (append && !old?.next_cursor) return;
    this._requestPending=true;
    const generation=this._requestGeneration;
    try {
      // Coalesce view changes and summary pushes; one request at a time, <=1/s.
      const pause=Math.min(1000,Math.max(0,1000-(Date.now()-(this._lastRead || 0))));
      if (pause && !await this._waitRead(pause)) return;
      if (!this._connected || generation!==this._requestGeneration) return;
      this._lastRead=Date.now();
      const message={type:"photography_events/get_view",entry_id:entry,projection_version:"ha.v17.1",view,limit:50};
      if (append) { message.cursor=old.next_cursor; message.snapshot_id=old.snapshot_id; }
      const result=await this._hass.callWS(message);
      if (!this._connected || generation!==this._requestGeneration || entry!==this._entryId()) return;
      if (result?.projection_version!=="ha.v17.1" || result.entry_id!==entry || !Array.isArray(result.items) || result.items.length>50) { this._views.clear(); throw {code:"unsupported_projection"}; }
      if (append) result.items=[...old.items,...result.items].slice(0,500);
      this._views.set(view,result); this._transportError=null; this._readBusy=false; this._retryCount=0;
      // Other view caches cannot retain an earlier generation or connection.
      for (const [key,v] of this._views) if (v.snapshot_id!==result.snapshot_id) this._views.delete(key);
    } catch (error) {
      if (generation===this._requestGeneration && this._connected) {
        if (error?.code==="rate_limited") {
          // The limit is shared across this HA user's dashboards/devices. Jitter
          // separates contenders; four retries bound each scheduled read series.
          this._transportError=null; this._readBusy=true; this._refreshQueued=false;
          if (this._retryCount<4) {
            const delay=1100+Math.floor(Math.random()*500)+this._retryCount*500;
            this._retryCount++;
            this._retryTimer=setTimeout(()=>{
              this._retryTimer=null;
              if (this._connected && generation===this._requestGeneration && entry===this._entryId()) this._refreshCore(append,true);
            },delay);
          }
        } else {
          this._readBusy=false;
          this._transportError="Core view unavailable. Check the integration connection in Settings > Devices & services.";
          if (error?.code==="snapshot_expired") { this._views.delete(view); this._refreshQueued=true; }
          if (["unauthorized","unsupported_projection"].includes(error?.code)) { this._cancelReadWork(); this._views.clear(); }
        }
      }
    } finally {
      this._requestPending=false; this._render();
      if (this._refreshQueued && this._connected) { this._refreshQueued=false; this._refreshCore(); }
    }
  }
  // Follow the composed tree: a slotted card's scroll owner can live inside
  // the slot host's shadow root, outside the parentElement chain.
  _scrollOwners(element) {
    const owners = [];
    let node = element;
    while (node) {
      if (node.scrollHeight > node.clientHeight && typeof getComputedStyle === "function" &&
          /auto|scroll|overlay/.test(getComputedStyle(node).overflowY)) owners.push(node);
      node = node.assignedSlot || node.parentElement || node.getRootNode?.().host;
    }
    if (document.scrollingElement && !owners.includes(document.scrollingElement)) owners.push(document.scrollingElement);
    return owners;
  }

  _visualAnchor(control) {
    if (!this._root?.getBoundingClientRect) return null;
    const attrs = ["data-expand", "data-category", "data-view", "data-month", "data-more", "data-skipped", "data-tab"];
    const identity = el => {
      if (el?.tagName === "SUMMARY") {
        const section = el.parentElement;
        const attr = section?.hasAttribute("data-section") ? "data-section" : "data-bucket";
        return section?.getAttribute(attr) != null ? [attr, section.getAttribute(attr), true] : null;
      }
      return el && attrs.map(attr => [attr, el.getAttribute?.(attr)]).find(([, value]) => value != null);
    };
    const focused = this.shadowRoot.activeElement;
    let target = control || (identity(focused) ? focused : null);
    const viewport = typeof innerHeight === "number" ? innerHeight : Infinity;
    if (!target) target = [...this._root.querySelectorAll("button, summary")].find(el => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 0 && rect.top < viewport && rect.height && identity(el);
    });
    target ||= this._root;
    const rect = target.getBoundingClientRect();
    if (!rect.height || rect.bottom < 0 || rect.top > viewport) return null;
    return { identity: identity(target), top: rect.top, fallbackTop: this._root.getBoundingClientRect().top,
      focus: identity(focused) };
  }

  _anchorElement(identity) {
    if (!identity) return this._root;
    const [attr, value, summary] = identity;
    const el = [...this._root.querySelectorAll(`[${attr}]`)].find(item => item.getAttribute(attr) === value);
    return summary ? el?.querySelector("summary") : el;
  }

  _restoreAnchor(anchor) {
    this._cancelAnchor?.();
    const generation = ++this._anchorGeneration;
    if (!anchor) return;
    const owners = this._scrollOwners(this._anchorElement(anchor.identity) || this._root);
    const cancel = () => { this._anchorGeneration++; cleanup(); };
    const types = ["wheel", "touchstart", "keydown", "pointerdown"];
    const cleanup = () => {
      for (const owner of owners) for (const type of types) owner.removeEventListener?.(type, cancel);
      if (this._cancelAnchor === cleanup) this._cancelAnchor = null;
    };
    this._cancelAnchor = cleanup;
    for (const owner of owners) for (const type of types) owner.addEventListener?.(type, cancel, { passive: true });
    const restore = () => {
      if (generation !== this._anchorGeneration || !this._connected) return;
      const equivalent = this._anchorElement(anchor.identity);
      const element = equivalent || this._root;
      const top = equivalent ? anchor.top : anchor.fallbackTop;
      for (const owner of this._scrollOwners(element)) {
        const delta = element.getBoundingClientRect().top - top;
        if (Math.abs(delta) < 0.5) break;
        owner.scrollTop += delta;
      }
    };
    this._anchorElement(anchor.focus)?.focus?.({ preventScroll: true });
    restore();
    // Lit custom elements and HA dashboard layout settle after the DOM write.
    // Bounded frames handle that second layout; a new interaction/scroll cancels
    // them so we never drag the user back after they deliberately move away.
    if (typeof requestAnimationFrame === "function") {
      let frames = 3;
      const settle = () => {
        if (generation !== this._anchorGeneration) { cleanup(); return; }
        restore();
        if (--frames) requestAnimationFrame(settle);
        else cleanup();
      };
      requestAnimationFrame(settle);
    } else cleanup();
  }

  _render(control) {
    if (!this.shadowRoot) return;
    const body = this._hass ? this._bodyHtml() : this._loadingHtml("Waiting for Home Assistant");
    if (this._dialog?.open) this._updateEventDialog();

    // A hero with nothing to announce leaves no trace at all. An empty card
    // still draws a border and takes a slot in the layout, which is its own
    // small false alarm on a dashboard whose whole point is that this thing
    // is silent until it matters.
    if (body === null) {
      this._setHidden(true);
      this._lastHtml = "";
      if (this._root) this._root.innerHTML = "";
      return;
    }
    this._setHidden(false);

    const html = `<div class="card-content">${this._navigationHtml()}${body}</div>`;

    // Ticks that produce byte-identical markup leave the live DOM untouched
    // instead of destroying and re-upgrading every ha-icon in the timeline -
    // and, in the outlook, keep the toggle listeners bound.
    if (this._root && html === this._lastHtml) return;
    this._lastHtml = html;

    if (!this._root) {
      const style = document.createElement("style");
      style.textContent = this._styles();
      // Keep ha-card connected. Recreating a Lit host briefly removes its
      // slotted content until its first update, collapsing the dashboard height
      // and clamping scrollTop before a synchronous restoration can succeed.
      const root = document.createElement("ha-card");
      root.className = "pe-root";
      this.shadowRoot.replaceChildren(style, root);
      this._root = root;
    }
    // Keep the planner's internal offset, then preserve a visual anchor in
    // the enclosing dashboard instead of guessing which ancestor scrolls.
    const innerScroll = this._root.querySelector(".outlook")?.scrollTop || 0;
    const anchor = this._visualAnchor(control);
    for (const el of this._root.querySelectorAll("[data-section]")) this._detailState.set(el.dataset.section, el.open);
    const focused = this.shadowRoot.activeElement;
    const focusedSection = focused?.tagName === "SUMMARY" ? focused.parentElement?.dataset.section : null;
    const focusAttributes = ["data-expand", "data-category", "data-view", "data-month", "data-more", "data-skipped"];
    const focusIdentity = focused && focusAttributes.map(attr => [attr, focused.getAttribute?.(attr)]).find(([, value]) => value != null);
    this._root.innerHTML = html;
    for (const el of this._root.querySelectorAll("[data-section]")) {
      if (this._detailState.has(el.dataset.section)) el.open = this._detailState.get(el.dataset.section);
    }
    this._bindEvents();
    if (focusIdentity) [...this._root.querySelectorAll(`[${focusIdentity[0]}]`)]
      .find(el => el.getAttribute(focusIdentity[0]) === focusIdentity[1])?.focus?.({preventScroll: true});
    if (focusedSection) [...this._root.querySelectorAll("[data-section]")]
      .find(el => el.dataset.section === focusedSection)?.querySelector("summary")?.focus?.({preventScroll: true});
    const inner = this._root.querySelector(".outlook");
    if (inner) inner.scrollTop = innerScroll;
    this._restoreAnchor(anchor);
    if (this._focusKey) {
      [...this._root.querySelectorAll("[data-expand]")].find(button => button.dataset.expand === this._focusKey)?.focus?.({ preventScroll: true });
      this._focusKey = null;
    }
  }

  /**
   * Toggle chips are rendered as real buttons carrying their entity id, and
   * wired up here after each DOM write. No inline handlers: they would break
   * under a strict Content-Security-Policy, which several people run.
   */
  _bindEvents() {
    if (!this._root) return;
    for (const button of this._root.querySelectorAll("[data-tab]")) {
      button.addEventListener("click", () => {
        if (this._selectedView === button.dataset.tab) return;
        this._cancelReadWork();
        this._selectedView = button.dataset.tab;
        this._render(button);
        this._refreshCore();
      });
    }
    for (const summary of this._root.querySelectorAll("summary")) {
      summary.addEventListener("click", () => {
        const anchor = this._visualAnchor(summary);
        // Native details stays native: no DOM rebuild for a disclosure.
        this._restoreAnchor(anchor);
      });
    }
    for (const section of this._root.querySelectorAll("[data-bucket]")) {
      section.addEventListener("toggle", () => {
        if (section.open) { this._collapsed.delete(section.dataset.bucket); this._openedBuckets.add(section.dataset.bucket); }
        else this._collapsed.add(section.dataset.bucket);
      });
    }
    for (const button of this._root.querySelectorAll("[data-more]")) {
      button.addEventListener("click", () => {
        const key = button.dataset.more;
        if (this._moreBuckets.has(key)) this._moreBuckets.delete(key);
        else this._moreBuckets.add(key);
        this._render(button);
      });
    }
    for (const button of this._root.querySelectorAll("[data-view]")) {
      button.addEventListener("click", () => { this._calendarView = button.dataset.view === "calendar"; this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-month]")) {
      button.addEventListener("click", () => { this._calendarOffset = clamp(this._calendarOffset + Number(button.dataset.month), 0, 12); this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-open]")) {
      button.addEventListener("click", () => this._openCalendarEvent(button.dataset.open));
    }
    for (const button of this._root.querySelectorAll("[data-skipped]")) {
      button.addEventListener("click", () => { this._showSkipped = !this._showSkipped; this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-choice]")) {
      button.addEventListener("click", () => this._saveChoice(button.dataset.eventid, button.dataset.choice));
    }
    for (const button of this._root.querySelectorAll("[data-category]")) {
      button.addEventListener("click", () => {
        const category = button.getAttribute("data-category");
        if (!category || !this._activeFilters) return;
        if (this._activeFilters.has(category)) this._activeFilters.delete(category);
        else this._activeFilters.add(category);
        this._render(button);
      });
    }
    for (const button of this._root.querySelectorAll("[data-expand]")) {
      button.addEventListener("click", () => {
        const key = button.getAttribute("data-expand");
        if (!key) return;
        this._focusKey = key;
        if (this._expanded.has(key)) this._expanded.delete(key);
        else this._expanded.add(key);
        this._render(button);
      });
    }
  }


  async _saveChoice() { return; }
  _eventControlsHtml() {
    return `<div class="event-controls"><button disabled title="Core persistence is unavailable">Follow</button><button disabled title="Core persistence is unavailable">Skip</button><button disabled title="Core persistence is unavailable">Seen · Got the shot</button></div><p class="event-note">Choices are unavailable until Core supports persistence. Nothing is saved. Notifications are disabled.</p>`;
  }
  _setHidden(hidden) { if(this.style)this.style.display=hidden?"none":""; }
  _loadingHtml(label) { return `<div class="loading"><span class="spinner"></span><span>${escapeHtml(label)}</span></div>`; }
  _styles() { return CARD_STYLES; }
  getCardSize() { return 8; }
  static getConfigElement() { return document.createElement("photography-events-card-editor"); }
  static getStubConfig() { return {...DEFAULT_CONFIG}; }
}
