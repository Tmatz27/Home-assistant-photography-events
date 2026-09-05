import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../custom_components/photography_events/www/photography-events-card.js", import.meta.url), "utf8");

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
    // A fresh DOM write means fresh elements, and therefore fresh listeners.
    this._queried = new Map();
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

  /**
   * Enough of a query to exercise the wiring in both the card and the editor:
   * every `[data-*]` selector returns elements carrying that attribute, with a
   * `dataset` and a `getAttribute`, so a test can set a value and fire it.
   */
  querySelectorAll(selector) {
    const match = /^\[data-([a-z]+)\]$/.exec(selector);
    if (!match) return [];
    const key = match[1];
    this._queried = this._queried || new Map();
    // Return the *same* element objects that had listeners bound to them.
    // Handing back fresh ones each call would make every listener test pass
    // vacuously, since the event would land on an object nobody wired up.
    if (this._queried.has(selector)) return this._queried.get(selector);

    // Match the whole tag, not just the one attribute: an element's other
    // data-* attributes carry real behaviour (the per-input clamp bounds, for
    // one), and a dataset with a single key would silently test the fallback.
    const pattern = new RegExp(`<[^>]*\\bdata-${key}="[^"]*"[^>]*>`, "g");
    const tags = [...this._html.matchAll(pattern)].map((found) => found[0]);
    const elements = tags.map((tag) => {
      const dataset = {};
      for (const [, name, value] of tag.matchAll(/data-([a-z]+)="([^"]*)"/g)) dataset[name] = value;
      return {
      _handlers: {},
      dataset,
      value: "",
      checked: false,
      getAttribute: (name) => {
        const found = /^data-([a-z]+)$/.exec(name);
        return found && found[1] in dataset ? dataset[found[1]] : null;
      },
      addEventListener(type, handler) {
        (this._handlers[type] = this._handlers[type] || []).push(handler);
      },
      fire(type = "click") {
        for (const handler of this._handlers[type] || []) handler();
      },
      click() {
        this.fire("click");
      },
      };
    });
    this._queried.set(selector, elements);
    return elements;
  }

  addEventListener() {}
}

class FakeHTMLElement {
  constructor() {
    // Real elements always have one, and the hero mode hides itself through it.
    this.style = {};
  }

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

// These fixtures exercise event *generation*. The display filter that hides
// everyday golden hours and lunar quarters sits on top of it and is tested
// separately, so it is off here.
const DEFAULT_TOGGLES = {
  hide_routine: false,
  show_planets: true,
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

const SKY_EVENT_TIME = new Date("2026-09-05T19:00:00Z");

/** Hourly forecast entries at the given hour offsets from the scored event. */
function forecastAround(points) {
  return points.map(({ h, cloud, precip, humidity }) => ({
    datetime: new Date(SKY_EVENT_TIME.getTime() + h * 3600000).toISOString(),
    cloud_coverage: cloud,
    precipitation_probability: precip,
    humidity,
  }));
}

const flatHours = (cloud, precip, humidity) =>
  forecastAround([-3, -2, -1, 0, 1].map((h) => ({ h, cloud, precip, humidity })));

test("sky scoring separates a flat sky from a broken, structured one", () => {
  const overcast = astro.skyColorQuality(flatHours(95, 20, 85), SKY_EVENT_TIME);
  assert.equal(overcast.tier, "poor");

  const clear = astro.skyColorQuality(flatHours(3, 0, 40), SKY_EVENT_TIME);
  assert.equal(clear.tier, "fair", "an empty sky is pleasant but not dramatic");

  // Same average cloud as a flat deck, but moving hour to hour - broken cloud
  // is what actually catches the light.
  const broken = astro.skyColorQuality(
    forecastAround([
      { h: -2, cloud: 20, precip: 5, humidity: 55 },
      { h: -1, cloud: 55, precip: 5, humidity: 55 },
      { h: 0, cloud: 35, precip: 5, humidity: 55 },
      { h: 1, cloud: 62, precip: 5, humidity: 55 },
    ]),
    SKY_EVENT_TIME,
  );
  const flatMid = astro.skyColorQuality(flatHours(43, 5, 55), SKY_EVENT_TIME);
  assert.ok(broken.score > flatMid.score, "broken cloud should outscore a flat deck of the same density");
});

test("the epic tier is reserved for the clearing-after-unsettled setup", () => {
  const clearing = astro.skyColorQuality(
    forecastAround([
      { h: -8, cloud: 95, precip: 80, humidity: 90 },
      { h: -6, cloud: 90, precip: 70, humidity: 88 },
      { h: -4, cloud: 80, precip: 45, humidity: 80 },
      { h: -2, cloud: 55, precip: 15, humidity: 65 },
      { h: -1, cloud: 40, precip: 10, humidity: 62 },
      { h: 0, cloud: 45, precip: 5, humidity: 60 },
      { h: 1, cloud: 30, precip: 5, humidity: 58 },
    ]),
    SKY_EVENT_TIME,
  );
  assert.equal(clearing.tier, "epic");
  assert.ok(
    clearing.reasons.some((reason) => /clearing/i.test(reason)),
    "expected the clearing trend to be named in the reasons",
  );

  // Ordinary good conditions must not reach epic, or the alert means nothing.
  for (const forecast of [flatHours(45, 5, 55), flatHours(30, 0, 50), flatHours(70, 10, 60)]) {
    assert.notEqual(astro.skyColorQuality(forecast, SKY_EVENT_TIME).tier, "epic");
  }
});

test("rain and haze both pull the score down", () => {
  const raining = astro.skyColorQuality(flatHours(88, 85, 95), SKY_EVENT_TIME);
  assert.equal(raining.tier, "poor");
  assert.ok(raining.reasons.some((reason) => /rain/i.test(reason)));

  const hazy = astro.skyColorQuality(flatHours(48, 0, 94), SKY_EVENT_TIME);
  const clean = astro.skyColorQuality(flatHours(48, 0, 55), SKY_EVENT_TIME);
  assert.ok(hazy.score < clean.score, "haze mutes colour rather than enhancing it");
});

test("sky scoring degrades gracefully without cloud data", () => {
  assert.equal(astro.skyColorQuality(null, SKY_EVENT_TIME), null);
  assert.equal(astro.skyColorQuality([], SKY_EVENT_TIME), null);
  const conditionOnly = astro.skyColorQuality(
    [{ datetime: SKY_EVENT_TIME.toISOString(), condition: "partlycloudy" }],
    SKY_EVENT_TIME,
  );
  assert.equal(conditionOnly.tier, "excellent");
  assert.equal(
    astro.skyColorQuality([{ datetime: SKY_EVENT_TIME.toISOString(), condition: "not-real" }], SKY_EVENT_TIME),
    null,
  );
});

test("meteorQuality penalizes a low radiant and a bright moon", () => {
  assert.equal(astro.meteorQuality(5, 0.1).tier, "poor");
  assert.equal(astro.meteorQuality(40, 0.8).tier, "fair");
  assert.equal(astro.meteorQuality(40, 0.1).tier, "excellent");
  assert.equal(astro.meteorQuality(20, 0.35).tier, "good");
});

test("planet positions reproduce real, independently published opposition dates", () => {
  // Oppositions are the sharpest available check on the orbital elements and
  // the Kepler solver: the planet is opposite the Sun to within a fraction of
  // a degree on exactly one day. These four dates are published astronomical
  // fact, not values derived from this code.
  const expected = {
    Mars: ["2027-02-19"],
    Jupiter: ["2026-01-10", "2027-02-11"],
    Saturn: ["2026-10-04"],
  };

  for (const [name, dates] of Object.entries(expected)) {
    const planet = astro.PLANETS.find((entry) => entry.name === name);
    const elongations = [];
    for (let i = 0; i <= 800; i += 1) {
      const date = new Date(Date.UTC(2026, 0, 1, 12) + i * 86400000);
      elongations.push({ date, value: astro.planetElongationDeg(planet, date) });
    }
    const oppositions = elongations
      .filter((entry, i) => i > 0 && i < elongations.length - 1 &&
        entry.value >= elongations[i - 1].value && entry.value >= elongations[i + 1].value && entry.value > 170)
      .map((entry) => entry.date.toISOString().slice(0, 10));

    for (const date of dates) {
      assert.ok(oppositions.includes(date), `expected a ${name} opposition on ${date}, got ${oppositions.join(", ")}`);
    }
  }
});

test("planet distances and elongations stay physically plausible", () => {
  const bounds = {
    Mercury: [0.5, 1.5],
    Venus: [0.25, 1.75],
    Mars: [0.35, 2.7],
    Jupiter: [3.9, 6.6],
    Saturn: [7.9, 11.1],
  };
  for (let i = 0; i < 400; i += 7) {
    const date = new Date(Date.UTC(2026, 0, 1) + i * 86400000);
    for (const planet of astro.PLANETS) {
      const { distanceAu } = astro.planetGeocentric(planet, date);
      const [min, max] = bounds[planet.name];
      assert.ok(distanceAu >= min && distanceAu <= max, `${planet.name} at ${distanceAu} AU on ${date.toISOString()}`);
      const elongation = astro.planetElongationDeg(planet, date);
      assert.ok(elongation >= 0 && elongation <= 180, `${planet.name} elongation ${elongation}`);
      // Inner planets can never appear opposite the Sun.
      if (planet.inner) {
        const limit = planet.name === "Venus" ? 48 : 29;
        assert.ok(elongation <= limit, `${planet.name} elongation ${elongation} exceeds its geometric limit`);
      }
    }
  }
});

test("a planet buried in the Sun's glare is not reported as visible tonight", () => {
  // On this date Mercury sits under 7 degrees from the Sun, so it cannot be
  // above the horizon during astronomical darkness however the night is sliced.
  const now = new Date("2026-09-03T15:00:00Z");
  const { events } = astro.buildEvents(
    { config: { latitude: 36.9741, longitude: -122.0308, elevation: 30 }, states: {} },
    { outlook_days: 7, ...DEFAULT_TOGGLES },
    null,
    now,
  );
  const tonight = events.filter((event) => event.title.startsWith("Planets tonight"));
  assert.ok(tonight.length > 0, "expected a planets-tonight row");
  for (const event of tonight) {
    assert.doesNotMatch(event.detail, /Mercury/, "Mercury is in conjunction with the Sun and cannot be up in darkness");
  }
});

test("a dusk is paired with the dawn that follows it, not with tomorrow's row", () => {
  // Coordinates far from the runtime's timezone push dusk across the calendar
  // boundary; pairing by date instead of by ordering produced a 30-hour
  // "night" that spanned a whole day of sunlight.
  const now = new Date("2026-09-03T15:00:00Z");
  const { events } = astro.buildEvents(
    { config: { latitude: 36.9741, longitude: -122.0308, elevation: 30 }, states: {} },
    { outlook_days: 7, ...DEFAULT_TOGGLES },
    null,
    now,
  );
  // Milky Way windows, migration seasons and comet apparitions are ranged on
  // purpose; the single-night categories are the ones that must not blow out.
  const singleNight = new Set(["sun", "moon", "planet", "meteor"]);
  for (const event of events.filter((entry) => entry.relevantUntil && singleNight.has(entry.category))) {
    const hours = (event.relevantUntil - event.time) / 3600000;
    assert.ok(hours <= 26, `"${event.title}" spans ${hours.toFixed(1)}h, which is longer than any real night`);
  }
});

test("consecutive Milky Way nights collapse into a single window", () => {
  const now = new Date("2026-09-03T15:00:00Z");
  const { events } = astro.buildEvents(
    { config: { latitude: 36.9741, longitude: -122.0308, elevation: 30 }, states: {} },
    { outlook_days: 21, ...DEFAULT_TOGGLES },
    null,
    now,
  );
  const milkyWay = events.filter((event) => event.category === "milkyway");
  assert.ok(milkyWay.length >= 1, "expected a Milky Way entry in September at this latitude");
  assert.ok(milkyWay.length <= 3, `expected grouped windows, got ${milkyWay.length} separate rows`);
});

test("custom sky events are scored, and unusable entries are skipped", () => {
  const now = new Date("2026-09-03T15:00:00Z");
  const config = {
    outlook_days: 21,
    ...DEFAULT_TOGGLES,
    custom_events: [
      { name: "Comet Test", ra_deg: 250, dec_deg: 20, start: "2026-09-05", end: "2026-09-25", note: "Mag 4." },
      { name: "No coordinates" },
      { ra_deg: 10, dec_deg: 10 },
      { name: "Unparseable dates", ra_deg: 10, dec_deg: 10, start: "not-a-date" },
    ],
  };
  const { events } = astro.buildEvents(
    { config: { latitude: 36.9741, longitude: -122.0308, elevation: 30 }, states: {} },
    config,
    null,
    now,
  );
  const custom = events.filter((event) => event.category === "custom");
  assert.equal(custom.length, 1, "only the fully specified entry should produce an event");
  assert.equal(custom[0].title, "Comet Test");
  assert.match(custom[0].detail, /Mag 4\./);
  assert.ok(custom[0].quality, "expected the comet to be scored like any other target");
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

test("an unscored sunset is not evidence of a good one", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const base = { outlook_days: 21, ...DEFAULT_TOGGLES };

  // With no weather entity nothing can be scored, so nothing clears the bar.
  const pruned = astro.buildEvents(londonHass(), { ...base, hide_routine: true }, null, now).events;
  assert.equal(
    pruned.filter((e) => e.category === "sun").length, 0,
    "without a forecast there is no evidence any sunset is worth a row",
  );

  // The underlying events still exist; only the display filter removed them.
  const all = astro.buildEvents(londonHass(), { ...base, hide_routine: false }, null, now).events;
  const sunEvents = all.filter((e) => e.category === "sun");
  assert.ok(sunEvents.length > 0, "expected sun events to still be generated");
  assert.ok(sunEvents.every((e) => e.quality === null), "expected no quality score without a forecast");
});

test("an excellent-quality forecast lets a sun event surface beyond the 72-hour near-term window", () => {
  const now = new Date("2026-09-02T12:00:00Z");
  const config = {
    outlook_days: 21,
    hide_routine: false,
    show_sun_events: true,
    show_moon_events: false,
    show_planets: false,
    show_meteor_showers: false,
    show_eclipses: false,
    show_milky_way: false,
    show_bird_migration: false,
  };
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


// --- Backend-driven modes ----------------------------------------------------

const backend = Card.backend;

function heroState(overrides = {}) {
  return {
    state: "on",
    attributes: {
      event_name: "Sunset could go off at Piedras Blancas",
      confidence_score: 92,
      category: "sunset",
      target_zone: "Piedras Blancas (San Simeon)",
      drive_hours: 1.5,
      drive_minutes: 78,
      drive_source: "Routes API",
      drive_in_traffic: true,
      starts: "2026-03-20T01:10:00+00:00",
      ends: "2026-03-20T02:25:00+00:00",
      condition_summary: "40% high cloud over a clear horizon.",
      reasons: ["high cloud 40%", "low cloud 5%"],
      gear_glass: "Wide for the sweep, 70-200mm to compress layers",
      gear_support: "Tripod, circular polariser",
      gear_settings: "Bracket exposures",
      source_url: "",
      ...overrides,
    },
  };
}

function outlookState(events, extra = {}) {
  return {
    state: String(events.length),
    attributes: {
      events,
      // Derived from the events themselves: a hand-written list that misses a
      // category makes the card filter it out, which looks like a card bug.
      all_categories: [...new Set(["astronomy", "sunset", "marine", "parks",
        ...events.map((event) => event.category)])],
      parks: {
        yosemite_np: {
          name: "Yosemite NP",
          miles: 310,
          drive_hours: 5.5,
          drive_label: "310 mi, about 5.5 h",
          dogs: "limited",
          dog_label: "Paved paths only",
          dog_detail: "Fully paved roads and campgrounds only.",
        },
        muir_woods_nm: {
          name: "Muir Woods NM",
          miles: 290,
          drive_hours: 5,
          drive_label: "290 mi, about 5 h",
          dogs: "none",
          dog_label: "Strictly prohibited",
          dog_detail: "No pets anywhere in the monument.",
        },
      },
      gear_by_category: {},
      ...extra,
    },
  };
}

test("drive times are labelled the way a person would say them", () => {
  assert.equal(backend.driveLabel(45), "45 min");
  assert.equal(backend.driveLabel(89), "89 min");
  assert.equal(backend.driveLabel(120), "2 h");
  assert.equal(backend.driveLabel(105), "1 h 45");
});

test("a routed drive time is distinguishable from a guess", () => {
  const routed = backend.driveProvenance("Routes API", true);
  const legacy = backend.driveProvenance("Distance Matrix API", false);
  const guess = backend.driveProvenance("estimate", false);
  const baseline = backend.driveProvenance("baseline", false);

  assert.equal(routed.routed, true);
  assert.equal(routed.note, "live traffic");
  assert.equal(legacy.routed, true);
  assert.equal(guess.routed, false, "a straight-line estimate must never read as routed");
  assert.equal(baseline.routed, false);
});

test("all-day windows and timestamps both parse, without a timezone shift", () => {
  const allDay = backend.parseEventDate("2026-06-01");
  assert.equal(allDay.getFullYear(), 2026);
  assert.equal(allDay.getMonth(), 5);
  assert.equal(allDay.getDate(), 1, "a date-only value must not slide a day on parse");

  assert.equal(backend.parseEventDate("2026-03-20T01:10:00+00:00").getTime(),
    Date.parse("2026-03-20T01:10:00+00:00"));
  assert.equal(backend.parseEventDate(""), null);
  assert.equal(backend.parseEventDate("nonsense"), null);
});

test("the hero payload is empty unless the sensor is actually on", () => {
  assert.equal(backend.heroFromState(null), null);
  assert.equal(backend.heroFromState({ state: "off", attributes: { event_name: "x" } }), null);
  assert.equal(backend.heroFromState({ state: "on", attributes: {} }), null,
    "an on sensor with no event name has nothing to show");

  const hero = backend.heroFromState(heroState());
  assert.equal(hero.score, 92);
  assert.equal(hero.driveMinutes, 78);
  assert.equal(hero.drive.routed, true);
});

test("the hero falls back to drive_hours when drive_minutes is absent", () => {
  const state = heroState();
  delete state.attributes.drive_minutes;
  assert.equal(backend.heroFromState(state).driveMinutes, 90);
});

test("a category with no toggle configured is shown, never hidden", () => {
  const hass = { states: { "input_boolean.astro": { state: "off" } } };
  const allowed = backend.activeCategories(hass, { astronomy: "input_boolean.astro" },
    ["astronomy", "sunset", "parks"]);
  assert.equal(allowed.has("astronomy"), false, "an off toggle hides its category");
  assert.equal(allowed.has("sunset"), true, "an unconfigured category stays visible");
  assert.equal(allowed.has("parks"), true);
});

test("a toggle pointing at a missing entity does not hide its category", () => {
  const allowed = backend.activeCategories({ states: {} }, { parks: "input_boolean.gone" }, ["parks"]);
  assert.equal(allowed.has("parks"), true, "a half-configured card must not swallow the calendar");
});

test("the outlook keeps seasons already underway and drops what is out of range", () => {
  const now = new Date("2026-06-15T12:00:00Z");
  const events = [
    { key: "a", title: "Underway season", category: "parks", start: "2026-06-01", end: "2026-08-31", score: 60 },
    { key: "b", title: "Next spring", category: "parks", start: "2027-03-01", end: "2027-04-30", score: 55 },
    { key: "c", title: "Finished", category: "parks", start: "2026-04-01", end: "2026-05-31", score: 55 },
    { key: "d", title: "Filtered out", category: "astronomy", start: "2026-07-01", end: "2026-07-02", score: 80 },
  ];
  const filtered = backend.filterOutlook(events, {
    allowed: new Set(["parks"]),
    now,
    fromDays: 0,
    throughDays: 365,
  });
  assert.deepEqual(filtered.map((event) => event.key), ["a", "b"]);
});

test("the outlook window is bounded at both ends", () => {
  const now = new Date("2026-06-15T12:00:00Z");
  const events = [
    { key: "soon", title: "Soon", category: "parks", start: "2026-06-20", end: "2026-06-21", score: 50 },
    { key: "later", title: "Later", category: "parks", start: "2026-09-01", end: "2026-09-30", score: 50 },
  ];
  const far = backend.filterOutlook(events, { allowed: null, now, fromDays: 30, throughDays: 365 });
  assert.deepEqual(far.map((event) => event.key), ["later"], "fromDays should exclude the near event");

  const near = backend.filterOutlook(events, { allowed: null, now, fromDays: 0, throughDays: 40 });
  assert.deepEqual(near.map((event) => event.key), ["soon"], "throughDays should exclude the far event");
});

test("months group in chronological order", () => {
  const now = new Date("2026-01-01T00:00:00Z");
  const events = backend.filterOutlook([
    { key: "b", title: "B", category: "parks", start: "2026-03-05", end: "2026-03-06", score: 50 },
    { key: "a", title: "A", category: "parks", start: "2026-02-05", end: "2026-02-06", score: 50 },
    { key: "c", title: "C", category: "parks", start: "2026-03-20", end: "2026-03-21", score: 50 },
  ], { allowed: null, now, fromDays: 0, throughDays: 365 });
  const months = backend.groupByMonth(events);
  // Built inside the vm realm, so compare plain values rather than references.
  assert.deepEqual(JSON.parse(JSON.stringify(months.map((month) => month.label))),
    ["February 2026", "March 2026"]);
  assert.equal(months[1].events.length, 2);
});

test("a single-day window is not rendered as a range", () => {
  const day = new Date(2026, 2, 3);
  assert.ok(!backend.rangeLabel(day, day).includes("-"));
  assert.ok(backend.rangeLabel(new Date(2026, 2, 3), new Date(2026, 2, 14)).includes("-"));
});

test("action_hero renders nothing at all while the sensor is off", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = { states: { "binary_sensor.action": { state: "off", attributes: {} } } };
  card.connectedCallback();

  assert.equal(card.style.display, "none", "an idle hero must not draw a card at all");
  assert.equal(card._root, null, "an idle hero should not even build a DOM root");
  assert.equal(card.getCardSize(), 1, "a hidden hero should not reserve layout space");
  card.disconnectedCallback();
});

test("action_hero shows the name, drive time, score and gear when it fires", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = { states: { "binary_sensor.action": heroState() } };
  card.connectedCallback();

  const html = card._root.innerHTML;
  assert.equal(card.style.display, "");
  assert.match(html, /Sunset could go off at Piedras Blancas/);
  assert.match(html, /78 min/, "expected the routed drive time");
  assert.match(html, /live traffic/);
  assert.match(html, /92/);
  assert.match(html, /70-200mm to compress layers/);
  card.disconnectedCallback();
});

test("action_hero labels an estimated drive time as estimated", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = {
    states: {
      "binary_sensor.action": heroState({ drive_source: "estimate", drive_in_traffic: false }),
    },
  };
  card.connectedCallback();
  assert.match(card._root.innerHTML, /estimated/);
  assert.doesNotMatch(card._root.innerHTML, /live traffic/);
  card.disconnectedCallback();
});

test("the hero appears and disappears as the sensor flips", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = { states: { "binary_sensor.action": { state: "off", attributes: {} } } };
  card.connectedCallback();
  assert.equal(card.style.display, "none");

  card.hass = { states: { "binary_sensor.action": heroState() } };
  assert.equal(card.style.display, "", "a new state object should redraw the hero");
  assert.match(card._root.innerHTML, /Drop everything/i);

  card.hass = { states: { "binary_sensor.action": { state: "off", attributes: {} } } };
  assert.equal(card.style.display, "none", "the hero must go away again when it is over");
  card.disconnectedCallback();
});

test("a misconfigured hero says so instead of hiding the problem", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.missing" });
  card.hass = { states: {} };
  card.connectedCallback();
  assert.notEqual(card.style.display, "none", "a configuration error is not the same as nothing to report");
  assert.match(card._root.innerHTML, /not in Home Assistant/);
  card.disconnectedCallback();
});

test("the backend modes never call the weather websocket", async () => {
  for (const mode of ["action_hero", "calendar_outlook"]) {
    const calls = [];
    const card = new Card();
    card.setConfig({ mode, hero_entity: "binary_sensor.action", outlook_entity: "sensor.outlook" });
    card.hass = {
      states: { "binary_sensor.action": heroState(), "sensor.outlook": outlookState([]) },
      callWS: async (message) => {
        calls.push(message);
        return {};
      },
    };
    card.connectedCallback();
    await new Promise((resolve) => setTimeout(resolve, 20));
    assert.deepEqual(calls, [], `${mode} should read entity state, never poll a forecast`);
    assert.equal(card._eventInterval, null, `${mode} is push-driven and should start no timers`);
    card.disconnectedCallback();
  }
});

test("calendar_outlook lists park windows with their dog rules", () => {
  const now = new Date();
  const soon = new Date(now.getTime() + 40 * 86400000).toISOString().slice(0, 10);
  const later = new Date(now.getTime() + 70 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        {
          key: "park-yosemite_np-optimal", title: "Yosemite NP - best window", category: "parks",
          zone_id: "yosemite_np", zone: "Yosemite NP", start: soon, end: later,
          score: 60, drive_hours: 5.5, planning_only: true, all_day: true, tier: "optimal",
        },
        {
          key: "park-muir_woods_nm-good", title: "Muir Woods NM - good window", category: "parks",
          zone_id: "muir_woods_nm", zone: "Muir Woods NM", start: soon, end: later,
          score: 45, drive_hours: 5, planning_only: true, all_day: true, tier: "good",
        },
      ]),
    },
  };
  card.connectedCallback();

  const html = card._root.innerHTML;
  assert.match(html, /Yosemite NP - best window/);
  assert.match(html, /Best window/);
  assert.match(html, /Paved paths only/);
  assert.match(html, /Strictly prohibited/, "the no-dogs parks are the ones worth flagging hardest");
  assert.match(html, /310 mi, about 5\.5 h/);
  card.disconnectedCallback();
});


test("an empty outlook explains itself rather than showing a blank card", () => {
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = { states: { "sensor.outlook": outlookState([]) } };
  card.connectedCallback();
  assert.match(card._root.innerHTML, /Nothing in this window/);
  card.disconnectedCallback();
});

test("an unknown mode falls back to the timeline rather than rendering nothing", () => {
  const card = new Card();
  card.setConfig({ mode: "not_a_mode" });
  assert.equal(card._config.mode, "timeline");
});

test("outlook range options are clamped to a year", () => {
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_from_days: -5, outlook_through_days: 9999 });
  assert.equal(card._config.outlook_from_days, 0);
  assert.equal(card._config.outlook_through_days, 365);
});



test("the editor offers the two backend modes and asks different questions for each", () => {
  const editor = new Editor();
  editor.hass = {
    states: {
      "binary_sensor.photography_events_action_opportunity": { state: "off", attributes: {} },
      "sensor.photography_events_planning_outlook": { state: "12", attributes: {} },
      "input_boolean.show_parks": { state: "on" },
    },
  };

  editor.setConfig({ mode: "timeline" });
  assert.match(editor.shadowRoot.innerHTML, /Days to look ahead/, "timeline mode configures the browser view");
  assert.doesNotMatch(editor.shadowRoot.innerHTML, /Filter switches/);

  editor.setConfig({ mode: "action_hero" });
  const hero = editor.shadowRoot.innerHTML;
  assert.match(hero, /Drop-everything sensor/);
  assert.match(hero, /binary_sensor\.photography_events_action_opportunity/);
  assert.doesNotMatch(hero, /Days to look ahead/, "the hero has no browser-side outlook to configure");

  editor.setConfig({ mode: "calendar_outlook" });
  const outlook = editor.shadowRoot.innerHTML;
  assert.match(outlook, /Planning sensor/);
  assert.match(outlook, /need no helper entities/, "filters are card state, not entities");
});


test("the outlook range inputs clamp to their own bounds, not the timeline's", () => {
  const editor = new Editor();
  const emitted = [];
  editor.hass = { states: {} };
  editor.dispatchEvent = (event) => emitted.push(event.detail.config);
  editor.setConfig({ mode: "calendar_outlook" });

  const numbers = editor.shadowRoot.querySelectorAll("[data-number]");
  const through = numbers.find((input) => input.dataset.number === "outlook_through_days");
  assert.ok(through, "expected the outlook range to be editable");

  through.value = "9999";
  through.fire("change");
  assert.equal(emitted.at(-1).outlook_through_days, 365);

  const from = numbers.find((input) => input.dataset.number === "outlook_from_days");
  from.value = "-4";
  from.fire("change");
  assert.equal(emitted.at(-1).outlook_from_days, 0);
});


test("calendar_outlook filters locally, with no helper entities at all", () => {
  const services = [];
  const now = new Date();
  const soon = new Date(now.getTime() + 10 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        { key: "p", title: "Yosemite NP - best window", category: "parks", zone_id: "yosemite_np",
          zone: "Yosemite NP", start: soon, end: soon, score: 60, planning_only: true, tier: "optimal" },
        { key: "a", title: "Perseids peak", category: "astronomy", zone_id: "carrizo_plain",
          zone: "Carrizo Plain", start: soon, end: soon, score: 88, detail: "ZHR ~100/hr" },
      ]),
    },
    callService: (...args) => services.push(args),
  };
  card.connectedCallback();

  assert.match(card._root.innerHTML, /Perseids peak/);
  assert.match(card._root.innerHTML, /Yosemite NP - best window/);

  const astro = card._root.querySelectorAll("[data-category]")
    .find((chip) => chip.getAttribute("data-category") === "astronomy");
  assert.ok(astro, "expected a chip per category");
  astro.click();

  assert.doesNotMatch(card._root.innerHTML, /Perseids peak/, "clicking a chip hides its category");
  assert.match(card._root.innerHTML, /Yosemite NP - best window/, "and leaves the others alone");
  assert.deepEqual(services, [], "filtering must not touch Home Assistant at all");
  card.disconnectedCallback();
});

test("the score is a readable badge, not a coloured bar", () => {
  const now = new Date();
  const soon = new Date(now.getTime() + 5 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        { key: "a", title: "Milky Way core", category: "astronomy", zone_id: "carrizo_plain",
          zone: "Carrizo", start: soon, end: soon, score: 95, precision: "peak" },
        { key: "s", title: "Gray whales (season)", category: "marine", zone_id: "x", zone: "Coast",
          start: soon, end: soon, score: 45, precision: "season", season_range: "December to May" },
      ]),
    },
  };
  card.connectedCallback();
  const html = card._root.innerHTML;
  assert.match(html, /95% score/);
  assert.match(html, /Season</, "a background season is labelled, not scored");
  assert.match(html, /pe-legend/, "the legend explains what the badges mean");
  card.disconnectedCallback();
});

test("clicking a row expands the full brief", () => {
  const now = new Date();
  const soon = new Date(now.getTime() + 5 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        {
          key: "elk", title: "Tule elk rut", category: "mammals", zone_id: "tule_elk_rut",
          zone: "Carrizo Plain", start: soon, end: soon, score: 78, precision: "peak",
          season_range: "August to October",
          locations: ["Carrizo Plain, Soda Lake Road foothills", "Tomales Point"],
          gear: "200-600mm telephoto, beanbag or gimbal head",
          best_time_of_day: "Dawn, 06:00-08:30",
          tips: "Bugling and sparring run on first light.",
        },
      ]),
    },
  };
  card.connectedCallback();
  assert.doesNotMatch(card._root.innerHTML, /Soda Lake Road/, "detail is hidden until asked for");

  const row = card._root.querySelectorAll("[data-expand]")[0];
  row.click();

  const html = card._root.innerHTML;
  assert.match(html, /Soda Lake Road/, "locations");
  assert.match(html, /200-600mm/, "gear");
  assert.match(html, /Dawn, 06:00-08:30/, "time of day");
  assert.match(html, /August to October/, "extended season alongside the peak");
  assert.match(html, /Why this score/, "plain-language reasoning");

  row.click();
  assert.doesNotMatch(card._root.innerHTML, /Soda Lake Road/, "and collapses again");
  card.disconnectedCallback();
});

test("the hero states an absolute start, not a countdown", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = { states: { "binary_sensor.action": heroState() } };
  card.connectedCallback();
  const html = card._root.innerHTML;
  assert.match(html, /Starts \w{3}, \w{3} \d+ at /, "expected a real day and time");
  assert.doesNotMatch(html, /\bIN \d+H\b/i);
  card.disconnectedCallback();
});

test("the hero spells out the window and what closes it", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  const now = new Date();
  card.hass = {
    states: {
      "binary_sensor.action": heroState({
        starts: new Date(now.getTime() + 30 * 60000).toISOString(),
        ends: new Date(now.getTime() + 126 * 60000).toISOString(),
        duration_minutes: 96,
        limited_by: "target",
      }),
    },
  };
  card.connectedCallback();
  const html = card._root.innerHTML;
  assert.match(html, /96 min/);
  assert.match(html, /before the core sets/, "the limit is named, not just the end time");
  assert.match(html, /remaining/);
  card.disconnectedCallback();
});

test("the hero body does not repeat the summary as pills", () => {
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action" });
  card.hass = { states: { "binary_sensor.action": heroState() } };
  card.connectedCallback();
  const html = card._root.innerHTML;
  assert.match(html, /40% high cloud over a clear horizon/, "the readable summary stays");
  assert.doesNotMatch(html, /hero-reasons/, "the duplicate tag row is gone");
  card.disconnectedCallback();
});

test("the hero names what else is peaking right now", () => {
  const now = new Date();
  const started = new Date(now.getTime() - 3 * 86400000).toISOString().slice(0, 10);
  const ends = new Date(now.getTime() + 12 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "action_hero", hero_entity: "binary_sensor.action", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "binary_sensor.action": heroState(),
      "sensor.outlook": outlookState([
        { key: "elk", title: "Tule elk rut", category: "mammals", zone_id: "x", zone: "Carrizo",
          start: started, end: ends, score: 78, precision: "peak" },
        { key: "far", title: "Gray whales (season)", category: "marine", zone_id: "y", zone: "Coast",
          start: ends, end: ends, score: 45, precision: "season" },
      ]),
    },
  };
  card.connectedCallback();
  const html = card._root.innerHTML;
  assert.match(html, /Also peaking now/);
  assert.match(html, /Tule elk rut/);
  assert.doesNotMatch(html, /Gray whales/, "a background season is not 'peaking now'");
  card.disconnectedCallback();
});

test("the timeline hides everyday light, phases, planets and distant eclipses", () => {
  const prune = (events) => {
    // Exercised through buildEvents' own filter by calling it directly.
    const kept = [];
    for (const event of events) {
      const only = Card.astro.buildEvents ? null : null;
      kept.push(event);
    }
    return kept;
  };

  const card = new Card();
  card.setConfig({ outlook_days: 21 });
  card.hass = londonHass();
  card.connectedCallback();
  return new Promise((resolve) => setTimeout(resolve, 40)).then(() => {
    const events = card._events || [];

    for (const event of events) {
      if (event.category === "sun") {
        assert.ok(event.score >= 85, `an ordinary sunset survived with score ${event.score}`);
      }
      if (event.category === "moon") {
        assert.ok(event.notable === true, `a routine lunar phase survived: ${event.title}`);
        assert.doesNotMatch(event.title, /Quarter/, "quarters are trivia");
      }
      if (event.category === "planet") {
        assert.notEqual(event.kind, "nightly", "the nightly what's-up row is noise");
        if (event.kind === "conjunction") assert.ok(event.separationDeg < 1.0);
      }
      if (event.category === "eclipse") {
        assert.notEqual(event.visible, false, "an eclipse nobody here can see is not an event");
      }
    }

    assert.match(card._root.innerHTML, /pe-legend/, "the legend explains the colours");
    assert.match(card._root.innerHTML, /are hidden/, "and says what is being suppressed");
    card.disconnectedCallback();
  });
});

test("the suppression can be turned off", async () => {
  const quiet = new Card();
  quiet.setConfig({ outlook_days: 21 });
  quiet.hass = londonHass();
  quiet.connectedCallback();
  await new Promise((resolve) => setTimeout(resolve, 40));

  const loud = new Card();
  loud.setConfig({ outlook_days: 21, hide_routine: false });
  loud.hass = londonHass();
  loud.connectedCallback();
  await new Promise((resolve) => setTimeout(resolve, 40));

  assert.ok(
    (loud._events || []).length > (quiet._events || []).length,
    "hide_routine: false should restore the everyday events",
  );
  quiet.disconnectedCallback();
  loud.disconnectedCallback();
});

test("the brief says whether anything has actually confirmed the dates", () => {
  const now = new Date();
  const soon = new Date(now.getTime() + 20 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        {
          key: "grays", title: "Gray whale southbound", category: "marine",
          zone_id: "gray_whale_southbound", zone: "Piedras Blancas",
          start: soon, end: soon, score: 60, precision: "peak",
          verification: "watching",
          awaiting: "A sighting of Eschrichtius robustus within 120 km in the last 14 days. None yet.",
        },
      ]),
    },
  };
  card.connectedCallback();
  card._root.querySelectorAll("[data-expand]")[0].click();

  const html = card._root.innerHTML;
  assert.match(html, /Confirmed\?/, "the question is asked on the row itself");
  assert.match(html, /Watching/);
  assert.match(html, /None yet/, "and it names what is missing, not just a state");
  card.disconnectedCallback();
});

test("a sky scored without a light path is marked optimistic", () => {
  const now = new Date();
  const soon = new Date(now.getTime() + 1 * 86400000).toISOString().slice(0, 10);
  const later = new Date(now.getTime() + 3 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  card.hass = {
    states: {
      "sensor.outlook": outlookState([
        { key: "sky1", title: "Sunset", category: "sunset", zone_id: "z", zone: "Coast",
          start: soon, end: soon, score: 88, precision: "peak", light_path: "local" },
        { key: "sky2", title: "Sunset two", category: "sunset", zone_id: "z2", zone: "Inland",
          start: later, end: later, score: 92, precision: "peak", light_path: "modelled",
          standout: true },
      ]),
    },
  };
  card.connectedCallback();
  const rows = card._root.querySelectorAll("[data-expand]");
  rows[0].click();
  assert.match(card._root.innerHTML, /Light path/);
  assert.match(card._root.innerHTML, /optimistic/);

  assert.match(card._root.innerHTML, /Best of the week/, "the standout is badged in the list");
  card.disconnectedCallback();
});

test("the season caption quotes the horizon the backend published", () => {
  const now = new Date();
  const far = new Date(now.getTime() + 200 * 86400000).toISOString().slice(0, 10);
  const card = new Card();
  card.setConfig({ mode: "calendar_outlook", outlook_entity: "sensor.outlook" });
  const state = outlookState([
    { key: "s", title: "Gray whales (season)", category: "marine", zone_id: "x", zone: "Coast",
      start: far, end: far, score: 45, precision: "season", season_range: "December to May" },
  ]);
  state.attributes.precision_horizon_days = 60;
  card.hass = { states: { "sensor.outlook": state } };
  card.connectedCallback();
  card._root.querySelectorAll("[data-expand]")[0].click();
  assert.match(card._root.innerHTML, /inside 60 days/,
    "the card must never carry its own copy of the horizon");
  card.disconnectedCallback();
});
