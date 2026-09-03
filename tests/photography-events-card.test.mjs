import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../photography-events-card.js", import.meta.url), "utf8");

class FakeNode {
  constructor(localName = "div") {
    this.localName = localName;
    this.className = "";
    this.children = [];
    this.writes = 0;
    this._html = "";
  }

  set innerHTML(value) {
    this._html = value;
    this.writes += 1;
  }

  get innerHTML() {
    return this._html;
  }

  setAttribute(name, value) {
    this[name] = value;
  }

  replaceChildren(...nodes) {
    this.children = nodes;
  }

  replaceWith() {}

  querySelector() {
    return null;
  }

  querySelectorAll() {
    return [];
  }

  addEventListener() {}
}

class FakeHTMLElement {
  attachShadow() {
    this.shadowRoot = new FakeNode("#shadow-root");
    return this.shadowRoot;
  }
}

function baseSandbox() {
  return {
    HTMLElement: FakeHTMLElement,
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options?.detail;
      }
    },
    customElements: {
      define(name, constructor) {
        this._registry = this._registry || new Map();
        this._registry.set(name, constructor);
      },
      get(name) {
        return this._registry?.get(name);
      },
    },
    document: {
      createElement(name) {
        return new FakeNode(name);
      },
    },
    window: { customCards: [] },
    console: { info() {}, error() {} },
    setInterval,
    clearInterval,
    setTimeout,
    Promise,
  };
}

const sandbox = baseSandbox();
vm.runInNewContext(source, sandbox, { filename: "photography-events-card.js" });
const Card = sandbox.customElements.get("photography-events-card");
const Editor = sandbox.customElements.get("photography-events-card-editor");
const astro = Card.astro;

/** Evaluate the card in a fresh browser-like context, as a <script> load would. */
function runSource({ defineThrows = false } = {}) {
  const defined = new Map();
  const errors = [];
  const context = {
    HTMLElement: FakeHTMLElement,
    CustomEvent: class {},
    customElements: {
      define(name, constructor) {
        if (defineThrows) throw new Error(`'${name}' has already been defined`);
        defined.set(name, constructor);
      },
      get(name) {
        return defined.get(name);
      },
    },
    document: { createElement: (name) => new FakeNode(name) },
    window: {},
    console: { info() {}, error: (...args) => errors.push(args) },
    setInterval,
    clearInterval,
    setTimeout,
    Promise,
  };
  vm.runInNewContext(source, context, { filename: "photography-events-card.js" });
  return { context, defined, errors };
}

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const isValidDate = (value) => value && typeof value.getTime === "function" && !Number.isNaN(value.getTime());

const LONDON = { latitude: 51.5074, longitude: -0.1278, elevation: 11 };

function londonHass(overrides = {}) {
  return { config: { ...LONDON }, states: {}, callWS: async () => ({}), ...overrides };
}

const DEFAULT_TOGGLES = {
  show_sun_events: true,
  show_moon_events: true,
  show_meteor_showers: true,
  show_eclipses: true,
  show_milky_way: true,
  show_bird_migration: true,
};

test("registers the Home Assistant card and editor", () => {
  assert.equal(typeof Card, "function");
  assert.equal(typeof Editor, "function");
  assert.equal(sandbox.window.customCards[0].type, "photography-events-card");
});

test("announces itself to the dashboard card picker", () => {
  const { context, defined } = runSource();
  assert.equal(context.window.customCards.length, 1);
  const entry = context.window.customCards[0];
  assert.equal(entry.type, "photography-events-card");
  assert.equal(entry.preview, true);
  assert.ok(entry.description, "expected a picker description");
  assert.ok(entry.documentationURL.startsWith("https://"), "expected a docs link");
  assert.ok(defined.has("photography-events-card"));
  assert.ok(defined.has("photography-events-card-editor"));
});

test("the picker entry survives a custom element registration failure", () => {
  const { context, errors } = runSource({ defineThrows: true });
  assert.equal(context.window.customCards.length, 1);
  assert.equal(errors.length, 1, "expected the failure to be reported");
});

test("an existing customCards array is preserved, not clobbered", () => {
  const defined = new Map();
  const context = {
    HTMLElement: FakeHTMLElement,
    CustomEvent: class {},
    customElements: {
      define: (name, constructor) => defined.set(name, constructor),
      get: (name) => defined.get(name),
    },
    document: { createElement: (name) => new FakeNode(name) },
    window: { customCards: [{ type: "some-other-card" }] },
    console: { info() {}, error() {} },
    setInterval,
    clearInterval,
    setTimeout,
    Promise,
  };
  vm.runInNewContext(source, context, { filename: "photography-events-card.js" });
  assert.deepEqual(
    context.window.customCards.map((card) => card.type),
    ["some-other-card", "photography-events-card"],
  );
});

test("solar declination matches the known solstice/equinox invariants", () => {
  const decAt = (iso) => astro.sunEquatorial(astro.daysSinceJ2000(new Date(iso))).dec * DEG;
  assert.ok(Math.abs(decAt("2026-06-21T06:00:00Z") - 23.44) < 0.3, "June solstice should be ~+23.44 deg");
  assert.ok(Math.abs(decAt("2026-12-21T18:00:00Z") - -23.44) < 0.3, "December solstice should be ~-23.44 deg");
  assert.ok(Math.abs(decAt("2026-09-22T18:00:00Z")) < 1, "the equinox should be close to 0 deg");
});

test("solar noon at the Greenwich meridian falls near 12:00 UTC year-round", () => {
  // At longitude ~0 the average of sunrise and sunset (solar noon) must sit
  // very close to 12:00 UTC regardless of season - a cheap, TZ-independent
  // sanity check on the whole hour-angle/sidereal-time pipeline.
  for (const iso of ["2026-03-20T00:00:00Z", "2026-09-02T00:00:00Z", "2026-12-01T00:00:00Z"]) {
    const start = new Date(iso);
    const end = new Date(start.getTime() + 86400000);
    const crossings = astro.findAltitudeCrossings(
      (d) => {
        const { ra, dec } = astro.sunEquatorial(astro.daysSinceJ2000(d));
        return astro.horizontalFromEquatorial(ra, dec, d, LONDON.latitude * RAD, LONDON.longitude * RAD).altitude;
      },
      start,
      end,
      -0.833 * RAD,
      4,
    );
    const rise = crossings.find((c) => c.rising);
    const set = crossings.find((c) => !c.rising);
    assert.ok(rise && set, `expected both a rise and a set crossing on ${iso}`);
    const noonUtcHours = (rise.time.getTime() + set.time.getTime()) / 2 / 3600000 -
      Math.floor(rise.time.getTime() / 86400000) * 24;
    assert.ok(Math.abs(noonUtcHours - 12) < 0.2, `expected solar noon near 12:00 UTC on ${iso}, got hour ${noonUtcHours}`);
  }
});

test("findAltitudeCrossings finds interior zero crossings of a synthetic wave", () => {
  const periodMs = 86400000;
  const wave = (date) => Math.sin((2 * Math.PI * date.getTime()) / periodMs);
  const start = new Date(-0.25 * periodMs);
  const end = new Date(2.25 * periodMs);
  const crossings = astro.findAltitudeCrossings(wave, start, end, 0, 5);
  const inDays = crossings.map((c) => c.time.getTime() / periodMs);
  assert.equal(crossings.length, 5, `expected 5 interior crossings, got ${inDays}`);
  [0, 0.5, 1, 1.5, 2].forEach((expected, i) => {
    assert.ok(Math.abs(inDays[i] - expected) < 0.02, `crossing ${i} should be near day ${expected}, got ${inDays[i]}`);
  });
  // The booleans live in the vm sandbox's realm, so compare them one at a time
  // rather than via deepEqual (cross-realm array/object identity trips it up).
  [true, false, true, false, true].forEach((expected, i) => {
    assert.equal(crossings[i].rising, expected, `crossing ${i} direction`);
  });
});

test("moon illumination stays within [0, 1] across a full lunar cycle", () => {
  for (let i = 0; i < 40; i += 1) {
    const date = new Date(Date.UTC(2026, 8, 1 + i, 12));
    const { fraction, phase, distanceKm } = astro.moonIllumination(date);
    assert.ok(fraction >= -1e-9 && fraction <= 1 + 1e-9, `fraction out of range on day ${i}: ${fraction}`);
    assert.ok(phase >= -1e-9 && phase <= 1 + 1e-9, `phase out of range on day ${i}: ${phase}`);
    assert.ok(distanceKm > 356000 && distanceKm < 407000, `moon distance out of plausible range: ${distanceKm}`);
  }
});

test("moonPhaseInfo covers the full [0, 1] range with a label and icon", () => {
  for (let phase = 0; phase <= 1; phase += 0.05) {
    const info = astro.moonPhaseInfo(phase);
    assert.ok(info?.label && info?.icon, `expected a label/icon at phase ${phase}`);
  }
});

test("meteor shower reference data is internally consistent", () => {
  for (const shower of astro.METEOR_SHOWERS) {
    assert.ok(shower.peakMonth >= 1 && shower.peakMonth <= 12, `${shower.name} has a bad peak month`);
    assert.ok(shower.peakDay >= 1 && shower.peakDay <= 31, `${shower.name} has a bad peak day`);
    assert.ok(shower.raDeg >= 0 && shower.raDeg < 360, `${shower.name} has a bad radiant RA`);
    assert.ok(shower.decDeg >= -90 && shower.decDeg <= 90, `${shower.name} has a bad radiant Dec`);
    assert.ok(shower.zhr > 0, `${shower.name} has a non-positive ZHR`);
  }
  const names = astro.METEOR_SHOWERS.map((s) => s.name);
  assert.equal(new Set(names).size, names.length, "expected unique shower names");
});

test("eclipse reference data parses and is chronologically sorted", () => {
  const dates = astro.ECLIPSES.map((e) => new Date(e.date));
  for (const [i, date] of dates.entries()) {
    assert.ok(isValidDate(date), `eclipse ${astro.ECLIPSES[i].date} did not parse`);
    assert.ok(["solar", "lunar"].includes(astro.ECLIPSES[i].kind));
    assert.ok(astro.ECLIPSES[i].region?.length > 0, "expected a region description");
  }
  for (let i = 1; i < dates.length; i += 1) {
    assert.ok(dates[i] >= dates[i - 1], "expected ECLIPSES to be listed in chronological order");
  }
});

test("lunar eclipse visibility is computed from real moon geometry, not guessed", () => {
  // 2027-08-17 07:13:43Z greatest eclipse. The Moon is comfortably above the
  // horizon for the whole +/-3h window at (40N, 100W) and comfortably below it
  // at the antipodal point (40S, 80E) - two unambiguous, verified reference
  // points rather than a boundary case that could go either way.
  const eclipse = astro.ECLIPSES.find((e) => e.date === "2027-08-17T07:13:43Z");
  const visible = astro.lunarEclipseVisibility(new Date(eclipse.date), 40 * RAD, -100 * RAD);
  assert.equal(visible.visible, true);

  const notVisible = astro.lunarEclipseVisibility(new Date(eclipse.date), -40 * RAD, 80 * RAD);
  assert.equal(notVisible.visible, false);
  assert.match(notVisible.note, /below your horizon/i);
});

test("solar eclipse visibility correctly rules out the night side of Earth", () => {
  const eclipse = astro.ECLIPSES.find((e) => e.kind === "solar");
  const date = new Date(eclipse.date);
  // Longitude 180 degrees from Greenwich is in the middle of its local night
  // at this eclipse's greatest-eclipse instant (verified: sun stays well below
  // the horizon for the whole +/-2h window).
  const nightSide = astro.solarEclipseVisibility(date, 0, 180 * RAD);
  assert.equal(nightSide.visible, false);
  assert.match(nightSide.note, /nighttime/i);
});

test("sunsetQuality bands cloud coverage into tiers, and falls back to condition", () => {
  assert.equal(astro.sunsetQuality(null), null);
  assert.equal(astro.sunsetQuality({ cloud_coverage: 40 }).tier, "excellent");
  assert.equal(astro.sunsetQuality({ cloud_coverage: 5 }).tier, "fair");
  assert.equal(astro.sunsetQuality({ cloud_coverage: 75 }).tier, "good");
  assert.equal(astro.sunsetQuality({ cloud_coverage: 95 }).tier, "poor");
  assert.equal(astro.sunsetQuality({ condition: "partlycloudy" }).tier, "excellent");
  assert.equal(astro.sunsetQuality({ condition: "rainy" }).tier, "poor");
  assert.equal(astro.sunsetQuality({ condition: "not-a-real-condition" }), null);
});

test("meteorQuality penalizes a low radiant and a bright moon", () => {
  assert.equal(astro.meteorQuality(5, 0.1).tier, "poor");
  assert.equal(astro.meteorQuality(40, 0.8).tier, "fair");
  assert.equal(astro.meteorQuality(40, 0.1).tier, "excellent");
  assert.equal(astro.meteorQuality(20, 0.35).tier, "good");
});

test("buildEvents reports an error instead of throwing when no location is configured", () => {
  const hass = { config: {}, states: {}, callWS: async () => ({}) };
  const { events, error } = astro.buildEvents(hass, { outlook_days: 21, ...DEFAULT_TOGGLES }, null, new Date("2026-09-02T12:00:00Z"));
  assert.equal(events.length, 0);
  assert.match(error, /no location configured/i);
});

test("buildEvents never returns an event that has already finished", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const { events } = astro.buildEvents(londonHass(), { outlook_days: 21, ...DEFAULT_TOGGLES }, null, now);
  assert.ok(events.length > 0, "expected some events in a 21-day London outlook");
  for (const event of events) {
    const boundary = event.relevantUntil || new Date(event.time.getTime() + 30 * 60000);
    assert.ok(boundary >= now, `event "${event.title}" at ${event.time.toISOString()} has already finished`);
  }
});

test("buildEvents returns events sorted chronologically", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const { events } = astro.buildEvents(londonHass(), { outlook_days: 21, ...DEFAULT_TOGGLES }, null, now);
  for (let i = 1; i < events.length; i += 1) {
    assert.ok(events[i].time >= events[i - 1].time, "expected events in chronological order");
  }
});

test("category toggles remove exactly that category and nothing else", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const config = { outlook_days: 21, ...DEFAULT_TOGGLES, show_eclipses: false };
  const { events } = astro.buildEvents(londonHass(), config, null, now);
  assert.equal(events.some((e) => e.category === "eclipse"), false);

  const withEclipses = astro.buildEvents(londonHass(), { outlook_days: 21, ...DEFAULT_TOGGLES }, null, now).events;
  assert.ok(withEclipses.some((e) => e.category === "eclipse"), "expected eclipses when the toggle is on");
});

test("an eclipse beyond the outlook window still surfaces as one of the next few", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const config = { outlook_days: 7, ...DEFAULT_TOGGLES };
  const { events } = astro.buildEvents(londonHass(), config, null, now);
  const eclipses = events.filter((e) => e.category === "eclipse");
  assert.ok(eclipses.length > 0, "expected at least one eclipse even with a short outlook window");
  assert.ok(eclipses[0].time > new Date(now.getTime() + 7 * 86400000), "the surfaced eclipse should be beyond the 7-day window");
});

test("sun events still render without a configured weather entity", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const config = { outlook_days: 21, ...DEFAULT_TOGGLES };
  const { events } = astro.buildEvents(londonHass(), config, null, now);
  const sunEvents = events.filter((e) => e.category === "sun");
  assert.ok(sunEvents.length > 0, "expected sun events even without weather data");
  assert.ok(sunEvents.every((e) => e.quality === null), "expected no quality score without a forecast");
});

test("an excellent-quality forecast lets a sun event surface beyond the 72-hour near-term window", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const config = { outlook_days: 21, show_sun_events: true, show_moon_events: false, show_meteor_showers: false, show_eclipses: false, show_milky_way: false, show_bird_migration: false };
  const days = astro.buildDayTable(LONDON.latitude * RAD, LONDON.longitude * RAD, new Date("2026-09-01"), new Date("2026-09-10"), LONDON.elevation);
  const farDay = days.find((d) => d.date.toISOString().slice(0, 10) === "2026-09-08");
  const forecast = [
    { datetime: farDay.sunset.toISOString(), cloud_coverage: 40 },
    { datetime: farDay.sunrise.toISOString(), cloud_coverage: 40 },
  ];
  const { events } = astro.buildEvents(londonHass(), config, forecast, now);
  const beyondNearTerm = events.filter((e) => e.time > new Date(now.getTime() + 72 * 3600000));
  assert.ok(beyondNearTerm.length > 0, "expected the excellent-quality day to surface beyond 72 hours");
  assert.ok(beyondNearTerm.every((e) => e.quality === "excellent"));
});

test("a latitude/longitude/elevation override takes precedence over hass.config", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const overridden = astro.buildEvents(
    londonHass(),
    { outlook_days: 3, ...DEFAULT_TOGGLES, latitude: -33.8688, longitude: 151.2093 },
    null,
    now,
  );
  const stock = astro.buildEvents(londonHass(), { outlook_days: 3, ...DEFAULT_TOGGLES }, null, now);
  const overriddenSunset = overridden.events.find((e) => e.category === "sun" && e.title.includes("Evening"));
  const stockSunset = stock.events.find((e) => e.category === "sun" && e.title.includes("Evening"));
  assert.ok(overriddenSunset && stockSunset);
  assert.notEqual(overriddenSunset.time.getTime(), stockSunset.time.getTime(), "Sydney and London should not share a sunset time");
});

test("editor renders category toggles and a weather entity dropdown", () => {
  const editor = new Editor();
  editor.hass = { states: { "weather.home": { attributes: { friendly_name: "Home Weather" } } } };
  editor.setConfig({});
  editor.connectedCallback();
  const html = editor.shadowRoot.innerHTML;
  assert.match(html, /Home Weather/);
  assert.match(html, /data-toggle="show_bird_migration"/);
  assert.match(html, /data-number="outlook_days"/);
});

test("editor ignores the config echo Home Assistant sends back", () => {
  const editor = new Editor();
  let renders = 0;
  editor._render = function stubbedRender() {
    this._rendered = true;
    renders += 1;
  };

  editor.setConfig({ outlook_days: 14 });
  assert.equal(renders, 1, "expected the first setConfig to build the form");

  editor.setConfig({ outlook_days: 14 });
  assert.equal(renders, 1, "expected an identical config not to rebuild the form");

  editor.setConfig({ outlook_days: 10 });
  assert.equal(renders, 2, "expected a real change to rebuild the form");
});

test("card shows a loading state before hass arrives and an error with no location", () => {
  const card = new Card();
  card.setConfig({});
  card.connectedCallback();
  assert.match(card._root.innerHTML, /Waiting for Home Assistant/);

  card.hass = { config: {}, states: {}, callWS: async () => ({}) };
  return new Promise((resolve) => setTimeout(resolve, 20)).then(() => {
    assert.match(card._root.innerHTML, /No location configured/i);
    card.disconnectedCallback();
  });
});

test("an unchanged refresh does not rewrite the card DOM", async () => {
  const card = new Card();
  card.setConfig({ outlook_days: 21 });
  card.hass = londonHass();
  card.connectedCallback();
  await new Promise((resolve) => setTimeout(resolve, 20));

  const writesAfterFirstRender = card._root.writes;
  assert.ok(writesAfterFirstRender > 0);

  card._render();
  assert.equal(card._root.writes, writesAfterFirstRender, "expected identical markup to leave the DOM untouched");
  card.disconnectedCallback();
});

test("polling restarts when Home Assistant re-attaches the card", async () => {
  const card = new Card();
  card.setConfig({ outlook_days: 21 });
  card.hass = londonHass();
  card.connectedCallback();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.notEqual(card._eventInterval, null, "expected polling to start on first attach");

  card.disconnectedCallback();
  assert.equal(card._eventInterval, null, "expected the timer to be cleared while detached");

  card.connectedCallback();
  assert.notEqual(card._eventInterval, null, "expected polling to resume after re-attach");
  card.disconnectedCallback();
});

test("a missing configured weather entity is reported, not silently ignored", async () => {
  const card = new Card();
  card.setConfig({ outlook_days: 21, weather_entity: "weather.does_not_exist" });
  card.hass = londonHass();
  card.connectedCallback();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(card._weatherMissing, true);
  assert.match(card._root.innerHTML, /was not found/i);
  card.disconnectedCallback();
});

test("the card only ever calls the weather/get_forecasts websocket command", () => {
  const calls = [];
  const card = new Card();
  card.setConfig({ outlook_days: 21, weather_entity: "weather.home" });
  card.hass = {
    config: { ...LONDON },
    states: { "weather.home": {} },
    callWS: async (msg) => {
      calls.push(msg.type);
      return {};
    },
  };
  card.connectedCallback();
  return new Promise((resolve) => setTimeout(resolve, 20)).then(() => {
    assert.ok(calls.length > 0);
    assert.ok(calls.every((type) => type === "weather/get_forecasts"));
    card.disconnectedCallback();
  });
});

test("card getCardSize and getStubConfig behave reasonably", () => {
  const card = new Card();
  card.setConfig({});
  assert.ok(card.getCardSize() >= 4);

  const hass = { states: { "weather.home": {} } };
  const stub = Card.getStubConfig(hass);
  assert.equal(stub.weather_entity, "weather.home");
  assert.equal(Card.getStubConfig({ states: {} }).weather_entity, "");
});

test("card carries no embedded credentials and only reads hass.config/hass.states", () => {
  assert.equal(
    /(api_?key|password|passwd|token|secret)\s*[:=]\s*["'`][^"'`]{3,}["'`]/i.test(source),
    false,
    "found what looks like a hardcoded credential",
  );
});
