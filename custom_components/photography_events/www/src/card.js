const EVENT_REFRESH_MS = 5 * 60000;
const WEATHER_REFRESH_MS = 30 * 60000;

class PhotographyEventsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULT_CONFIG };
    this._events = null;
    this._buildError = null;
    this._forecast = null;
    this._weatherMissing = false;
    this._connected = false;
    this._initialized = false;
    this._eventInterval = null;
    this._weatherInterval = null;
    this._root = null;
    this._lastHtml = "";
    // Null until the first render knows which categories exist; a Set after.
    this._activeFilters = null;
    this._expanded = new Set();
    this._collapsed = new Set();
    this._calendarView = false;
    this._calendarOffset = 0;
    this._choiceGroups = new Map();
    this._displayEvents = new Map();
    this._showSkipped = false;
    this._choicePending = false;
    this._choiceError = "";
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (this._connected && !this._initialized) {
      this._start();
      return;
    }
    // The backend modes are push-driven: Home Assistant hands us a new state
    // object whenever one of the entities we read changes, and identity
    // comparison is enough to tell. The timeline mode ignores this entirely,
    // because it recomputes on its own clock and re-rendering it on every
    // unrelated state change in the house would be pure waste.
    if (this._isBackendMode() && this._trackedStatesChanged(previous, hass)) this._render();
  }

  _isBackendMode() {
    return BACKEND_MODES.has(this._config?.mode) || Boolean(this._outlookEntityId());
  }

  /** Every entity this card reads, so changes to them (and only them) redraw. */
  _trackedEntities() {
    return [this._heroEntityId(), this._outlookEntityId()].filter(Boolean);
  }

  _trackedStatesChanged(previous, next) {
    if (!previous) return true;
    return this._trackedEntities().some((id) => previous.states?.[id] !== next.states?.[id]);
  }

  _heroEntityId() {
    if (this._config?.hero_entity) return this._config.hero_entity;
    return findEntity(this._hass, "binary_sensor.", "action_opportunity");
  }

  _outlookEntityId() {
    if (this._config?.outlook_entity) return this._config.outlook_entity;
    return findEntity(this._hass, "sensor.", "planning_outlook");
  }

  setConfig(config) {
    if (!config) throw new Error("Photography Events Card configuration is required");
    const weatherChanged = config.weather_entity !== this._config.weather_entity;
    const mode = BACKEND_MODES.has(config.mode) || config.mode === MODE_TIMELINE
      ? config.mode
      : DEFAULT_CONFIG.mode;
    this._config = {
      ...DEFAULT_CONFIG,
      ...config,
      mode,
      outlook_days: clamp(Number.parseInt(config.outlook_days, 10) || DEFAULT_CONFIG.outlook_days, 7, 30),
      outlook_from_days: clamp(Number.parseInt(config.outlook_from_days, 10) || 0, 0, 365),
      outlook_through_days: clamp(
        Number.parseInt(config.outlook_through_days, 10) || DEFAULT_CONFIG.outlook_through_days, 1, 365),
    };
    this._lastHtml = "";
    if (this._connected && this._hass && this._initialized) {
      if (weatherChanged) this._refreshWeather().then(() => this._recomputeAndRender());
      else this._recomputeAndRender();
    } else if (this._connected) {
      this._render();
    }
  }

  connectedCallback() {
    this._connected = true;
    if (!this._hass) {
      this._render();
      return;
    }
    if (this._initialized) {
      // Home Assistant detaches and re-attaches the element on a dashboard
      // view switch; polling has to be restarted explicitly or data goes
      // stale until a full reload.
      if (this._isBackendMode()) {
        this._render();
        return;
      }
      this._recomputeAndRender();
      this._scheduleRefresh();
      return;
    }
    this._start();
  }

  disconnectedCallback() {
    this._connected = false;
    this._clearIntervals();
  }

  async _start() {
    if (this._initialized || !this._hass) return;
    this._initialized = true;
    // Nothing to fetch or compute in the backend modes - the integration has
    // done it, and state arrives on its own.
    if (this._isBackendMode()) {
      this._render();
      return;
    }
    this._render();
    await this._refreshWeather();
    this._recomputeAndRender();
    this._scheduleRefresh();
  }

  _clearIntervals() {
    if (this._eventInterval) clearInterval(this._eventInterval);
    if (this._weatherInterval) clearInterval(this._weatherInterval);
    this._eventInterval = null;
    this._weatherInterval = null;
  }

  _scheduleRefresh() {
    this._clearIntervals();
    if (!this._connected) return;
    this._eventInterval = setInterval(() => this._recomputeAndRender(), EVENT_REFRESH_MS);
    this._weatherInterval = setInterval(async () => {
      await this._refreshWeather();
      this._recomputeAndRender();
    }, WEATHER_REFRESH_MS);
  }

  async _refreshWeather() {
    if (this._isBackendMode()) return;
    const entityId = this._config.weather_entity;
    if (!entityId || !this._hass) {
      this._forecast = null;
      this._weatherMissing = false;
      return;
    }
    if (!this._hass.states?.[entityId]) {
      this._forecast = null;
      this._weatherMissing = true;
      return;
    }
    this._weatherMissing = false;
    try {
      const result = await this._hass.callWS({
        type: "weather/get_forecasts",
        entity_id: [entityId],
        forecast_type: "hourly",
      });
      this._forecast = result?.[entityId]?.forecast || null;
    } catch (error) {
      console.error("Photography Events Card: weather forecast request failed", error);
      this._forecast = null;
    }
  }

  _recomputeAndRender() {
    if (!this._hass) return;
    if (this._isBackendMode()) { this._clearIntervals(); this._render(); return; }
    const { events, error } = buildEvents(this._hass, this._config, this._forecast, new Date());
    this._events = events;
    this._buildError = error;
    this._render();
  }

  _render() {
    if (!this.shadowRoot) return;
    const body = this._hass ? this._bodyHtml() : this._loadingHtml("Waiting for Home Assistant");

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

    const html = `
      <ha-card>
        <div class="card-content">
          ${body}
        </div>
      </ha-card>
    `;

    // Ticks that produce byte-identical markup leave the live DOM untouched
    // instead of destroying and re-upgrading every ha-icon in the timeline -
    // and, in the outlook, keep the toggle listeners bound.
    if (this._root && html === this._lastHtml) return;
    this._lastHtml = html;

    if (!this._root) {
      const style = document.createElement("style");
      style.textContent = this._styles();
      const root = document.createElement("div");
      root.className = "pe-root";
      this.shadowRoot.replaceChildren(style, root);
      this._root = root;
    }
    // Replacing the scroll container reset it to zero on every expansion.
    // Preserve both its offset and HA's outer scrollers (including shadow hosts).
    const innerScroll = this._root.querySelector(".outlook")?.scrollTop || 0;
    const scrollers = [];
    let ancestor = this;
    while (ancestor) {
      if (typeof ancestor.scrollTop === "number") scrollers.push([ancestor, ancestor.scrollTop, ancestor.scrollLeft]);
      ancestor = ancestor.parentElement || ancestor.getRootNode?.().host;
    }
    if (document.scrollingElement) scrollers.push([document.scrollingElement, document.scrollingElement.scrollTop, document.scrollingElement.scrollLeft]);
    this._root.innerHTML = html;
    this._bindEvents();
    const inner = this._root.querySelector(".outlook");
    if (inner) inner.scrollTop = innerScroll;
    for (const [element, top, left] of scrollers) { element.scrollTop = top; element.scrollLeft = left; }
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
    for (const section of this._root.querySelectorAll("[data-bucket]")) {
      section.addEventListener("toggle", () => {
        if (section.open) this._collapsed.delete(section.dataset.bucket);
        else this._collapsed.add(section.dataset.bucket);
      });
    }
    for (const button of this._root.querySelectorAll("[data-view]")) {
      button.addEventListener("click", () => { this._calendarView = button.dataset.view === "calendar"; this._render(); });
    }
    for (const button of this._root.querySelectorAll("[data-month]")) {
      button.addEventListener("click", () => { this._calendarOffset = clamp(this._calendarOffset + Number(button.dataset.month), 0, 12); this._render(); });
    }
    for (const button of this._root.querySelectorAll("[data-open]")) {
      button.addEventListener("click", () => this._openCalendarEvent(button.dataset.open));
    }
    for (const button of this._root.querySelectorAll("[data-skipped]")) {
      button.addEventListener("click", () => { this._showSkipped = !this._showSkipped; this._render(); });
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
        this._render();
      });
    }
    for (const button of this._root.querySelectorAll("[data-expand]")) {
      button.addEventListener("click", () => {
        const key = button.getAttribute("data-expand");
        if (!key) return;
        this._focusKey = key;
        if (this._expanded.has(key)) this._expanded.delete(key);
        else this._expanded.add(key);
        this._render();
      });
    }
  }

  async _saveChoice(eventId, choice) {
    if (!eventId || this._choicePending) return;
    this._choicePending = true;
    this._choiceError = "";
    try {
      const ids = this._choiceGroups.get(eventId) || [eventId];
      for (const id of ids) await this._hass.callService("photography_events", "set_event_choice", { event_id: id, choice });
      // The server publishes the updated state. Do not claim success locally
      // before it has persisted the choice for the other dashboards too.
    } catch (error) {
      this._choiceError = "Could not save your event choice. Please try again.";
    } finally {
      this._choicePending = false;
      this._render();
    }
  }

  _eventControlsHtml(id, choice = "default") {
    if (!id) return "";
    return `<div class="event-controls">
      <button type="button" data-eventid="${escapeHtml(id)}" data-choice="${choice === "follow" ? "default" : "follow"}"
        aria-pressed="${choice === "follow"}">${choice === "follow" ? "Following · Unfollow" : "Follow"}</button>
      <button type="button" data-eventid="${escapeHtml(id)}" data-choice="${choice === "skip" ? "default" : "skip"}">
        ${choice === "skip" ? "Restore event" : "Not going · Skip"}</button>
    </div>`;
  }

  _setHidden(hidden) {
    if (this.style) this.style.display = hidden ? "none" : "";
  }

  _loadingHtml(label) {
    return `<div class="loading"><span class="spinner"></span><span>${escapeHtml(label)}</span></div>`;
  }

  _styles() { return CARD_STYLES; }

  getCardSize() {
    // A hidden hero should not reserve space in a masonry column.
    if (this._config?.mode === MODE_HERO) {
      return this._outlookEntityId() ? 3 : this._hass && heroFromState(this._hass.states[this._heroEntityId()]) ? 6 : 1;
    }
    if (this._config?.mode === MODE_OUTLOOK) return 12;
    const categories = CATEGORY_TOGGLE_KEYS.filter((key) => this._config?.[key] !== false).length;
    return Math.max(4, 2 + categories * 2);
  }

  static getConfigElement() {
    return document.createElement("photography-events-card-editor");
  }

  static getStubConfig(hass) {
    // When the integration is installed, the hero is the mode worth showing
    // first: it is the one that changes what you do with your evening.
    const heroEntity = findEntity(hass, "binary_sensor.", "action_opportunity");
    if (heroEntity) {
      return { ...DEFAULT_CONFIG, mode: MODE_HERO, hero_entity: heroEntity };
    }
    const weatherEntity = hass?.states ? Object.keys(hass.states).find((id) => id.startsWith("weather.")) : undefined;
    return { ...DEFAULT_CONFIG, weather_entity: weatherEntity || "" };
  }
}
