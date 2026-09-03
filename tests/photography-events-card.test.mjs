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
  const config = {
    outlook_days: 21,
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
