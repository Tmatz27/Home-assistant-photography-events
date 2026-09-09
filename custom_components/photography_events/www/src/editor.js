const DEFAULT_CONFIG = Object.freeze({
  title: "Photography Events",
  // "timeline" keeps the original browser-computed view. The other two read
  // the photography_events integration's entities instead.
  mode: MODE_OUTLOOK,
  hero_entity: "",
  outlook_entity: "",
  outlook_from_days: 0,
  outlook_through_days: 365,
  show_gear: true,
  // Suppress ordinary golden hours, lunar quarters, nightly planet summaries
  // and eclipses that miss this location.
  hide_routine: true,
  location_name: "",
  latitude: null,
  longitude: null,
  elevation: null,
  weather_entity: "",
  outlook_days: 21,
  show_sun_events: true,
  show_moon_events: true,
  show_planets: true,
  show_meteor_showers: true,
  show_eclipses: true,
  show_milky_way: true,
  show_bird_migration: true,
  custom_events: [],
});


const sameConfig = (left, right) => {
  const keys = new Set([...Object.keys(left || {}), ...Object.keys(right || {})]);
  for (const key of keys) {
    if (left?.[key] !== right?.[key]) return false;
  }
  return true;
};

class PhotographyEventsCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULT_CONFIG };
    this._rendered = false;
  }

  set hass(hass) {
    const before = this._weatherEntityIds().join(",");
    this._hass = hass;
    const after = this._weatherEntityIds().join(",");
    if (this._rendered && before !== after) this._render();
  }

  setConfig(config) {
    const next = { ...DEFAULT_CONFIG, ...(config || {}) };
    // Home Assistant echoes every config-changed event straight back into
    // setConfig; rebuilding the DOM there would close an open dropdown or
    // drop focus mid-edit, so only rebuild when something actually changed.
    const unchanged = this._rendered && sameConfig(next, this._config);
    this._config = next;
    if (unchanged) return;
    this._render();
  }

  connectedCallback() {
    if (!this._rendered) this._render();
  }

  _weatherEntityIds() {
    if (!this._hass?.states) return [];
    return Object.keys(this._hass.states).filter((id) => id.startsWith("weather.")).sort();
  }

  _update(key, value) {
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
  }

  _render() {
    if (!this.shadowRoot) return;
    const cfg = this._config;
    const backendMode = BACKEND_MODES.has(cfg.mode) || Boolean(findEntity(this._hass, "sensor.", "planning_outlook"));
    this.shadowRoot.innerHTML = `
      <style>
        .event-controls, .event-toolbar { display:flex; gap:8px; margin:10px 0; flex-wrap:wrap; }
        .event-controls button, .event-toolbar button { color:var(--primary-text-color); background:var(--secondary-background-color); border:1px solid var(--divider-color); border-radius:8px; padding:8px 12px; cursor:pointer; }
        .event-error, .source-warning { padding:8px 14px; color:var(--warning-color, #b97619); font-size:12px; }
        .simple-row { align-items:center; }
        :host { display: block; color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif); }
        .section { margin: 0 0 20px; }
        .section:last-child { margin-bottom: 0; }
        .title { margin: 0 0 10px; padding-bottom: 5px; border-bottom: 1px solid var(--divider-color); color: var(--secondary-text-color); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
        .row { display: flex; align-items: center; gap: 12px; min-height: 34px; margin-bottom: 8px; }
        .label { flex: 1; font-size: 13px; }
        .hint { margin: -4px 0 10px; color: var(--secondary-text-color); font-size: 11px; line-height: 1.4; }
        select, input[type="text"], input[type="number"] {
          box-sizing: border-box; width: 190px; padding: 6px 8px; border: 1px solid var(--divider-color);
          border-radius: 7px; background: var(--card-background-color); color: var(--primary-text-color);
          font: inherit; font-size: 13px;
        }
        .toggle { position: relative; width: 38px; height: 22px; flex: 0 0 auto; }
        .toggle input { position: absolute; width: 0; height: 0; opacity: 0; }
        .slider { position: absolute; inset: 0; border-radius: 999px; background: var(--divider-color); cursor: pointer; transition: background .18s ease; }
        .slider::before { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: white; content: ""; transition: transform .18s ease; box-shadow: 0 1px 3px rgba(0, 0, 0, .28); }
        input:checked + .slider { background: var(--primary-color); }
        input:checked + .slider::before { transform: translateX(16px); }
      </style>

      <div class="section">
        <div class="title">Display</div>
        <div class="row"><span class="label">Mode</span>
          <select data-select="mode">
            <option value="${MODE_TIMELINE}" ${cfg.mode === MODE_TIMELINE ? "selected" : ""}>Timeline (uses integration when installed)</option>
            <option value="${MODE_HERO}" ${cfg.mode === MODE_HERO ? "selected" : ""}>Next seven days (compact)</option>
            <option value="${MODE_OUTLOOK}" ${cfg.mode === MODE_OUTLOOK ? "selected" : ""}>Planning calendar</option>
          </select>
        </div>
        <div class="hint">${backendMode
          ? "Reads the Photography Events integration's entities. Everything below the mode is about which entities to read."
          : "Computes everything in the browser from your coordinates. Works without the integration installed."}</div>
        <div class="row"><span class="label">Card title</span>
          <input type="text" data-text="title" value="${escapeHtml(cfg.title)}">
        </div>
      </div>

      ${backendMode ? this._backendSectionsHtml(cfg) : this._timelineSectionsHtml(cfg)}
    `;
    this._bindEditor();
    this._rendered = true;
  }

  _timelineSectionsHtml(cfg) {
    return `
      <div class="section">
        <div class="title">Location</div>
        <div class="hint">Leave latitude/longitude blank to use your Home Assistant location. Override them to
          point this card at a specific nearby vantage point (a coastal overlook, a dark-sky spot) instead.</div>
        <div class="row"><span class="label">Location name</span>
          <input type="text" data-text="location_name" placeholder="Home" value="${escapeHtml(cfg.location_name)}">
        </div>
        <div class="row"><span class="label">Latitude</span>
          <input type="text" inputmode="decimal" data-geo="latitude" data-min="-90" data-max="90" value="${cfg.latitude ?? ""}">
        </div>
        <div class="row"><span class="label">Longitude</span>
          <input type="text" inputmode="decimal" data-geo="longitude" data-min="-180" data-max="180" value="${cfg.longitude ?? ""}">
        </div>
        <div class="row"><span class="label">Elevation (meters)</span>
          <input type="text" inputmode="decimal" data-geo="elevation" data-min="-500" data-max="9000" value="${cfg.elevation ?? ""}">
        </div>
      </div>

      <div class="section">
        <div class="title">Weather</div>
        <div class="hint">Optional. Used to score sunset/sunrise color potential from cloud forecast data. Skipped
          if not set or if the integration reports no cloud data.</div>
        <div class="row"><span class="label">Weather entity</span>
          <select data-select="weather_entity">${this._weatherOptionsHtml()}</select>
        </div>
      </div>

      <div class="section">
        <div class="title">Outlook</div>
        <div class="row"><span class="label">Days to look ahead</span>
          <input type="number" min="7" max="30" step="1" data-number="outlook_days" value="${Number(cfg.outlook_days) || DEFAULT_CONFIG.outlook_days}">
        </div>
        <div class="hint">The near-term 24/48/72 hour snapshot always shows regardless of this setting.</div>
      </div>

      <div class="section">
        <div class="title">Event types</div>
        ${this._toggleRow("show_sun_events", "Golden/blue hour and sunrise/sunset")}
        ${this._toggleRow("show_moon_events", "Moon phases, moonrise/moonset")}
        ${this._toggleRow("show_planets", "Planets, oppositions, conjunctions")}
        ${this._toggleRow("show_meteor_showers", "Meteor shower peaks")}
        ${this._toggleRow("show_eclipses", "Solar and lunar eclipses")}
        ${this._toggleRow("show_milky_way", "Milky Way core season")}
        ${this._toggleRow("show_bird_migration", "Bird migration season")}
      </div>
    `;
  }

  /**
   * The entity pickers. Left blank, the card finds the integration's entities
   * by name, which is right almost always and wrong exactly once - when two
   * config entries exist - so they stay overridable.
   */
  _backendSectionsHtml(cfg) {
    const hero = cfg.mode === MODE_HERO;
    return `
      <div class="section">
        <div class="title">Planning sensor</div>
        <div class="hint">Leave as auto-detect unless you run more than one Photography Events entry.</div>
        <div class="row"><span class="label">Entity</span>
          <select data-select="outlook_entity">${this._entityOptionsHtml("sensor.", "planning_outlook", cfg.outlook_entity)}</select>
        </div>
      </div>

      ${hero ? `
        <div class="section">
          <div class="title">Next seven days</div>
          ${this._toggleRow("show_gear", "Show the gear recommendation")}
          <div class="hint">One brief per event, with its dates, locations and details. The planning sensor supplies the whole week.</div>
        </div>` : `
        <div class="section">
          <div class="title">Range</div>
          <div class="row"><span class="label">Start from (days)</span>
            <input type="number" min="0" max="365" step="1" data-number="outlook_from_days"
              data-min="0" data-max="365" value="${Number(cfg.outlook_from_days) || 0}">
          </div>
          <div class="row"><span class="label">Through (days)</span>
            <input type="number" min="1" max="365" step="1" data-number="outlook_through_days"
              data-min="1" data-max="365" value="${Number(cfg.outlook_through_days) || DEFAULT_CONFIG.outlook_through_days}">
          </div>
          <div class="hint">Start from 0 to include seasons already underway - usually what you want, since a park
            in its best window right now is the most useful thing a planning view can show.</div>
        </div>

        <div class="section">
          <div class="title">Filters</div>
          <div class="hint">Category filter chips are built into the card and need no helper entities -
            tap them on the card itself.</div>
        </div>`}
    `;
  }

  _entityOptionsHtml(domain, marker, current) {
    const ids = this._hass?.states
      ? Object.keys(this._hass.states).filter((id) => id.startsWith(domain) && id.includes(marker)).sort()
      : [];
    const options = [`<option value="" ${current ? "" : "selected"}>Auto-detect</option>`];
    if (current && !ids.includes(current)) {
      options.push(`<option value="${escapeHtml(current)}" selected>${escapeHtml(current)} (not found)</option>`);
    }
    for (const id of ids) {
      options.push(`<option value="${escapeHtml(id)}" ${id === current ? "selected" : ""}>${escapeHtml(id)}</option>`);
    }
    return options.join("");
  }

  _bindEditor() {
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((input) => {
      input.addEventListener("change", () => this._update(input.dataset.toggle, input.checked));
    });
    this.shadowRoot.querySelectorAll("[data-text]").forEach((input) => {
      input.addEventListener("change", () => this._update(input.dataset.text, input.value.trim()));
    });
    this.shadowRoot.querySelectorAll("[data-number]").forEach((input) => {
      input.addEventListener("change", () => {
        const key = input.dataset.number;
        // Each number carries its own bounds; the outlook range and the
        // timeline's day count are not the same scale.
        const min = input.dataset.min === undefined ? 7 : Number(input.dataset.min);
        const max = input.dataset.max === undefined ? 30 : Number(input.dataset.max);
        const fallback = DEFAULT_CONFIG[key] ?? min;
        const parsed = Number.parseInt(input.value, 10);
        const value = clamp(Number.isFinite(parsed) ? parsed : fallback, min, max);
        input.value = String(value);
        this._update(key, value);
      });
    });

    this.shadowRoot.querySelectorAll("[data-geo]").forEach((input) => {
      input.addEventListener("change", () => {
        const key = input.dataset.geo;
        const raw = input.value.trim();
        if (raw === "") {
          this._update(key, null);
          return;
        }
        const min = Number(input.dataset.min);
        const max = Number(input.dataset.max);
        const value = clamp(Number.parseFloat(raw), min, max);
        input.value = Number.isFinite(value) ? String(value) : "";
        this._update(key, Number.isFinite(value) ? value : null);
      });
    });
    this.shadowRoot.querySelectorAll("[data-select]").forEach((select) => {
      select.addEventListener("change", () => {
        this._update(select.dataset.select, select.value);
        // Changing the mode changes which questions the form should be asking,
        // so this one redraws rather than waiting for the config to echo back.
        if (select.dataset.select === "mode") this._render();
      });
    });
  }

  _weatherOptionsHtml() {
    const ids = this._weatherEntityIds();
    const current = this._config.weather_entity || "";
    const options = ['<option value="">None (skip sky-quality scoring)</option>'];
    if (current && !ids.includes(current)) {
      options.push(`<option value="${escapeHtml(current)}" selected>${escapeHtml(current)} (not found)</option>`);
    }
    for (const id of ids) {
      const name = this._hass?.states?.[id]?.attributes?.friendly_name || id;
      options.push(`<option value="${escapeHtml(id)}" ${id === current ? "selected" : ""}>${escapeHtml(name)}</option>`);
    }
    return options.join("");
  }

  _toggleRow(key, label) {
    return `
      <div class="row">
        <span class="label">${label}</span>
        <label class="toggle">
          <input type="checkbox" data-toggle="${key}" ${this._config[key] !== false ? "checked" : ""}>
          <span class="slider"></span>
        </label>
      </div>
    `;
  }
}

/* ---------------------------------------------------------------------- *
 * Card
 * ---------------------------------------------------------------------- */
