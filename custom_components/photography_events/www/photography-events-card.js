/**
 * Photography Events Card for Home Assistant
 * Version 0.2.0
 *
 * Surfaces upcoming photography-worthy sky and nature events near your Home
 * Assistant location: golden/blue hour and sunset/sunrise quality, moon
 * phases, meteor shower peaks, solar/lunar eclipses, Milky Way core season,
 * and a coarse bird migration season heuristic.
 *
 * All astronomy is computed locally from well-known low-precision solar and
 * lunar position formulas (the same family used by public references such as
 * aa.quae.nl's "Position of the Sun/Moon" pages). Expect rise/set times and
 * illumination to be accurate to within a minute or two - plenty for
 * planning a shoot, not survey-grade ephemeris.
 *
 * Copyright (c) 2026 Travis Matzdorf
 * SPDX-License-Identifier: MIT
 */

const CARD_VERSION = "0.2.0";

/* ---------------------------------------------------------------------- *
 * Astronomy core
 * ---------------------------------------------------------------------- */

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;
const MS_PER_DAY = 86400000;
const J1970 = 2440588;
const J2000 = 2451545;
const OBLIQUITY = 23.4397 * RAD;
const SUN_DISTANCE_KM = 149598000;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function toJulian(date) {
  return date.getTime() / MS_PER_DAY - 0.5 + J1970;
}

function daysSinceJ2000(date) {
  return toJulian(date) - J2000;
}

function eclipticToEquatorial(eclLonRad, eclLatRad) {
  const ra = Math.atan2(
    Math.sin(eclLonRad) * Math.cos(OBLIQUITY) - Math.tan(eclLatRad) * Math.sin(OBLIQUITY),
    Math.cos(eclLonRad),
  );
  const dec = Math.asin(
    clamp(
      Math.sin(eclLatRad) * Math.cos(OBLIQUITY) + Math.cos(eclLatRad) * Math.sin(OBLIQUITY) * Math.sin(eclLonRad),
      -1,
      1,
    ),
  );
  return { ra, dec };
}

/** Low-precision solar ecliptic position (Meeus-family truncated series). */
function sunEquatorial(d) {
  const M = RAD * (357.5291 + 0.98560028 * d);
  const C = RAD * (1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M));
  const perihelion = RAD * 102.9372;
  const eclLon = M + C + perihelion + Math.PI;
  return { ...eclipticToEquatorial(eclLon, 0), eclLon };
}

/** Low-precision lunar ecliptic position; distance is in kilometers. */
function moonEquatorial(d) {
  const L = RAD * (218.316 + 13.176396 * d);
  const M = RAD * (134.963 + 13.064993 * d);
  const F = RAD * (93.272 + 13.22935 * d);
  const eclLon = L + RAD * 6.289 * Math.sin(M);
  const eclLat = RAD * 5.128 * Math.sin(F);
  const dist = 385001 - 20905 * Math.cos(M);
  return { ...eclipticToEquatorial(eclLon, eclLat), dist };
}

function hourAngleAt(date, lonRad, raRad) {
  const d = daysSinceJ2000(date);
  const gmstDeg = (280.16 + 360.9856235 * d) % 360;
  return gmstDeg * RAD + lonRad - raRad;
}

/** Horizontal (altitude/azimuth) coordinates; azimuth is degrees from North through East. */
function horizontalFromEquatorial(raRad, decRad, date, latRad, lonRad) {
  const H = hourAngleAt(date, lonRad, raRad);
  const sinAlt = Math.sin(latRad) * Math.sin(decRad) + Math.cos(latRad) * Math.cos(decRad) * Math.cos(H);
  const altitude = Math.asin(clamp(sinAlt, -1, 1));
  const azimuth = Math.atan2(
    -Math.cos(decRad) * Math.sin(H),
    Math.sin(decRad) * Math.cos(latRad) - Math.cos(decRad) * Math.sin(latRad) * Math.cos(H),
  );
  return { altitude, azimuth: (azimuth * DEG + 360) % 360 };
}

function sunAltitude(date, latRad, lonRad) {
  const { ra, dec } = sunEquatorial(daysSinceJ2000(date));
  return horizontalFromEquatorial(ra, dec, date, latRad, lonRad).altitude;
}

function moonAltitude(date, latRad, lonRad) {
  const { ra, dec } = moonEquatorial(daysSinceJ2000(date));
  return horizontalFromEquatorial(ra, dec, date, latRad, lonRad).altitude;
}

/**
 * Samples altitudeFn across [start, end] and linearly interpolates every
 * crossing of thresholdRad. Good to a couple of minutes at a 4-6 minute step,
 * which is what every rise/set/twilight time in this card is built from - a
 * single shared numeric root-finder instead of separate closed-form sunrise
 * and moonrise equations (the moon moves too fast for the sun's day-static
 * closed form to stay accurate).
 */
function findAltitudeCrossings(altitudeFn, startDate, endDate, thresholdRad, stepMinutes) {
  const stepMs = stepMinutes * 60000;
  const endTime = endDate.getTime();
  const crossings = [];
  let prevTime = startDate.getTime();
  let prevValue = altitudeFn(new Date(prevTime)) - thresholdRad;
  for (let time = prevTime + stepMs; time <= endTime; time += stepMs) {
    const value = altitudeFn(new Date(time)) - thresholdRad;
    if ((prevValue < 0 && value >= 0) || (prevValue >= 0 && value < 0)) {
      const fraction = prevValue / (prevValue - value);
      crossings.push({
        time: new Date(prevTime + fraction * (time - prevTime)),
        rising: value > prevValue,
      });
    }
    prevTime = time;
    prevValue = value;
  }
  return crossings;
}

function maxAltitudeInWindow(raDeg, decDeg, start, end, latRad, lonRad, stepMinutes) {
  const raRad = raDeg * RAD;
  const decRad = decDeg * RAD;
  const stepMs = stepMinutes * 60000;
  let max = -Infinity;
  for (let t = start.getTime(); t <= end.getTime(); t += stepMs) {
    const { altitude } = horizontalFromEquatorial(raRad, decRad, new Date(t), latRad, lonRad);
    if (altitude > max) max = altitude;
  }
  return max * DEG;
}

/** Illuminated fraction, phase (0=new, 0.5=full, 1=next new), and distance in km. */
function moonIllumination(date) {
  const d = daysSinceJ2000(date);
  const sun = sunEquatorial(d);
  const moon = moonEquatorial(d);
  const elongation = Math.acos(
    clamp(
      Math.sin(sun.dec) * Math.sin(moon.dec) + Math.cos(sun.dec) * Math.cos(moon.dec) * Math.cos(sun.ra - moon.ra),
      -1,
      1,
    ),
  );
  const phaseAngle = Math.atan2(
    SUN_DISTANCE_KM * Math.sin(elongation),
    moon.dist - SUN_DISTANCE_KM * Math.cos(elongation),
  );
  const fraction = (1 + Math.cos(phaseAngle)) / 2;
  const sign = Math.atan2(
    Math.cos(sun.dec) * Math.sin(sun.ra - moon.ra),
    Math.sin(sun.dec) * Math.cos(moon.dec) - Math.cos(sun.dec) * Math.sin(moon.dec) * Math.cos(sun.ra - moon.ra),
  ) < 0 ? -1 : 1;
  const phase = 0.5 + (0.5 * phaseAngle * sign) / Math.PI;
  return { fraction, phase, distanceKm: moon.dist };
}

const MOON_PHASES = [
  { max: 0.03, label: "New Moon", icon: "mdi:moon-new" },
  { max: 0.22, label: "Waxing Crescent", icon: "mdi:moon-waxing-crescent" },
  { max: 0.28, label: "First Quarter", icon: "mdi:moon-first-quarter" },
  { max: 0.47, label: "Waxing Gibbous", icon: "mdi:moon-waxing-gibbous" },
  { max: 0.53, label: "Full Moon", icon: "mdi:moon-full" },
  { max: 0.72, label: "Waning Gibbous", icon: "mdi:moon-waning-gibbous" },
  { max: 0.78, label: "Last Quarter", icon: "mdi:moon-last-quarter" },
  { max: 0.97, label: "Waning Crescent", icon: "mdi:moon-waning-crescent" },
  { max: 1.01, label: "New Moon", icon: "mdi:moon-new" },
];

function moonPhaseInfo(phase) {
  return MOON_PHASES.find((entry) => phase <= entry.max) || MOON_PHASES[MOON_PHASES.length - 1];
}

function angularSeparation(ra1, dec1, ra2, dec2) {
  return Math.acos(
    clamp(Math.sin(dec1) * Math.sin(dec2) + Math.cos(dec1) * Math.cos(dec2) * Math.cos(ra1 - ra2), -1, 1),
  );
}

/* ---------------------------------------------------------------------- *
 * Planets
 *
 * Mean Keplerian elements at J2000 with per-century rates (the standard
 * low-precision set used for approximate positions of the major planets,
 * good to a few arcminutes over 1800-2050 - far finer than "is Jupiter up
 * tonight, and how close is it to the Moon"). Each planet is propagated as a
 * plain two-body orbit and differenced against Earth's to get a geocentric
 * direction, which then feeds the same altitude machinery as the Sun and Moon.
 * ---------------------------------------------------------------------- */

const EARTH_ELEMENTS = {
  name: "Earth",
  a: [1.00000261, 0.00000562],
  e: [0.01671123, -0.00004392],
  i: [-0.00001531, -0.01294668],
  meanLongitude: [100.46457166, 35999.37244981],
  perihelion: [102.93768193, 0.32327364],
  node: [0, 0],
};

const PLANETS = [
  {
    name: "Mercury",
    inner: true,
    a: [0.38709927, 0.00000037],
    e: [0.20563593, 0.00001906],
    i: [7.00497902, -0.00594749],
    meanLongitude: [252.2503235, 149472.67411175],
    perihelion: [77.45779628, 0.16047689],
    node: [48.33076593, -0.12534081],
  },
  {
    name: "Venus",
    inner: true,
    a: [0.72333566, 0.0000039],
    e: [0.00677672, -0.00004107],
    i: [3.39467605, -0.0007889],
    meanLongitude: [181.9790995, 58517.81538729],
    perihelion: [131.60246718, 0.00268329],
    node: [76.67984255, -0.27769418],
  },
  {
    name: "Mars",
    inner: false,
    a: [1.52371034, 0.00001847],
    e: [0.0933941, 0.00007882],
    i: [1.84969142, -0.00813131],
    meanLongitude: [-4.55343205, 19140.30268499],
    perihelion: [-23.94362959, 0.44441088],
    node: [49.55953891, -0.29257343],
  },
  {
    name: "Jupiter",
    inner: false,
    a: [5.202887, -0.00011607],
    e: [0.04838624, -0.00013253],
    i: [1.30439695, -0.00183714],
    meanLongitude: [34.39644051, 3034.74612775],
    perihelion: [14.72847983, 0.21252668],
    node: [100.47390909, 0.20469106],
  },
  {
    name: "Saturn",
    inner: false,
    a: [9.53667594, -0.0012506],
    e: [0.05386179, -0.00050991],
    i: [2.48599187, 0.00193609],
    meanLongitude: [49.95424423, 1222.49362201],
    perihelion: [92.59887831, -0.41897216],
    node: [113.66242448, -0.28867794],
  },
];

const atCentury = ([value, rate], centuries) => value + rate * centuries;

/** Newton iteration on Kepler's equation; these eccentricities converge in a few passes. */
function eccentricAnomaly(meanAnomalyRad, e) {
  let E = meanAnomalyRad + e * Math.sin(meanAnomalyRad);
  for (let i = 0; i < 8; i += 1) {
    const delta = (E - e * Math.sin(E) - meanAnomalyRad) / (1 - e * Math.cos(E));
    E -= delta;
    if (Math.abs(delta) < 1e-10) break;
  }
  return E;
}

function heliocentricEcliptic(elements, centuries) {
  const a = atCentury(elements.a, centuries);
  const e = atCentury(elements.e, centuries);
  const inclination = atCentury(elements.i, centuries) * RAD;
  const meanLongitude = atCentury(elements.meanLongitude, centuries) * RAD;
  const perihelion = atCentury(elements.perihelion, centuries) * RAD;
  const node = atCentury(elements.node, centuries) * RAD;

  const argPerihelion = perihelion - node;
  const meanAnomaly = meanLongitude - perihelion;
  const E = eccentricAnomaly(meanAnomaly, e);

  const xOrbit = a * (Math.cos(E) - e);
  const yOrbit = a * Math.sqrt(1 - e * e) * Math.sin(E);

  const cosArg = Math.cos(argPerihelion);
  const sinArg = Math.sin(argPerihelion);
  const cosNode = Math.cos(node);
  const sinNode = Math.sin(node);
  const cosInc = Math.cos(inclination);
  const sinInc = Math.sin(inclination);

  return {
    x: (cosArg * cosNode - sinArg * sinNode * cosInc) * xOrbit + (-sinArg * cosNode - cosArg * sinNode * cosInc) * yOrbit,
    y: (cosArg * sinNode + sinArg * cosNode * cosInc) * xOrbit + (-sinArg * sinNode + cosArg * cosNode * cosInc) * yOrbit,
    z: sinArg * sinInc * xOrbit + cosArg * sinInc * yOrbit,
  };
}

function planetGeocentric(planet, date) {
  const centuries = daysSinceJ2000(date) / 36525;
  const body = heliocentricEcliptic(planet, centuries);
  const earth = heliocentricEcliptic(EARTH_ELEMENTS, centuries);
  const x = body.x - earth.x;
  const y = body.y - earth.y;
  const z = body.z - earth.z;
  const eclLon = Math.atan2(y, x);
  const eclLat = Math.atan2(z, Math.sqrt(x * x + y * y));
  return {
    ...eclipticToEquatorial(eclLon, eclLat),
    distanceAu: Math.sqrt(x * x + y * y + z * z),
  };
}

/** Angular distance from the Sun as seen from Earth; ~180 deg at opposition. */
function planetElongationDeg(planet, date) {
  const sun = sunEquatorial(daysSinceJ2000(date));
  const body = planetGeocentric(planet, date);
  return angularSeparation(sun.ra, sun.dec, body.ra, body.dec) * DEG;
}

/* ---------------------------------------------------------------------- *
 * Reference data
 *
 * Meteor shower peaks recur annually (dates drift by about a day year to
 * year); eclipse instants do not, so that table is a manually curated list
 * that will need extending over time.
 * ---------------------------------------------------------------------- */

const METEOR_SHOWERS = [
  { name: "Quadrantids", peakMonth: 1, peakDay: 3, zhr: 110, raDeg: 230.1, decDeg: 49 },
  { name: "Lyrids", peakMonth: 4, peakDay: 22, zhr: 18, raDeg: 271.4, decDeg: 34 },
  { name: "Eta Aquariids", peakMonth: 5, peakDay: 5, zhr: 50, raDeg: 338, decDeg: -1 },
  { name: "Southern Delta Aquariids", peakMonth: 7, peakDay: 30, zhr: 25, raDeg: 339, decDeg: -16 },
  { name: "Perseids", peakMonth: 8, peakDay: 12, zhr: 100, raDeg: 48, decDeg: 58 },
  { name: "Orionids", peakMonth: 10, peakDay: 21, zhr: 20, raDeg: 95, decDeg: 16 },
  { name: "Southern Taurids", peakMonth: 11, peakDay: 5, zhr: 5, raDeg: 32, decDeg: 9 },
  { name: "Northern Taurids", peakMonth: 11, peakDay: 12, zhr: 5, raDeg: 58, decDeg: 22 },
  { name: "Leonids", peakMonth: 11, peakDay: 17, zhr: 15, raDeg: 152, decDeg: 22 },
  { name: "Geminids", peakMonth: 12, peakDay: 13, zhr: 150, raDeg: 112.3, decDeg: 33 },
  { name: "Ursids", peakMonth: 12, peakDay: 22, zhr: 10, raDeg: 217.4, decDeg: 75 },
];

// Compiled September 2026 from NASA/Wikipedia/EclipseWise eclipse predictions.
// Times are greatest-eclipse instants; local-circumstance checks below use a
// multi-hour window around them, so being off by a few minutes doesn't change
// the visibility verdict. Extend this list periodically and verify any new
// entry against an authoritative source (e.g. NASA's eclipse catalog) before
// adding it - a wrong date actively misleads trip planning.
const ECLIPSES = [
  {
    date: "2027-02-06T16:00:48Z",
    kind: "solar",
    type: "annular",
    magnitude: 0.928,
    region: "Path of annularity crosses Chile, Argentina, Uruguay, and Brazil, then the South Atlantic to " +
      "Côte d'Ivoire, Ghana, Togo, Benin, and Nigeria. Partial phases reach much of Africa, South America, " +
      "the Pacific, the Atlantic, and Antarctica.",
  },
  {
    date: "2027-07-18T16:02:58Z",
    kind: "lunar",
    type: "penumbral",
    magnitude: null,
    region: "A shallow penumbral eclipse - the Moon only grazes Earth's outer shadow, so the dimming is subtle " +
      "and easy to miss.",
  },
  {
    date: "2027-08-02T10:07:50Z",
    kind: "solar",
    type: "total",
    magnitude: 1.079,
    region: "Path of totality crosses Spain and Gibraltar, then Morocco, Algeria, Tunisia, Libya, Egypt, Sudan, " +
      "Saudi Arabia, Yemen, and Somalia. Totality lasts up to 6m23s near Luxor, Egypt - one of the longest " +
      "of the century.",
  },
  {
    date: "2027-08-17T07:13:43Z",
    kind: "lunar",
    type: "penumbral",
    magnitude: null,
    region: "Visible across the Americas, rising over Australia and the central Pacific, and setting over West " +
      "Africa. Another shallow, subtle penumbral eclipse.",
  },
  {
    date: "2028-01-12T04:12:57Z",
    kind: "lunar",
    type: "partial",
    magnitude: null,
    region: "Partial lunar eclipse.",
  },
  {
    date: "2028-01-26T15:08:59Z",
    kind: "solar",
    type: "annular",
    magnitude: 0.921,
    region: "Path of annularity crosses Ecuador, Peru, northern Brazil, and French Guiana.",
  },
  {
    date: "2028-07-06T18:19:41Z",
    kind: "lunar",
    type: "partial",
    magnitude: null,
    region: "Partial lunar eclipse.",
  },
  {
    date: "2028-07-22T02:56:40Z",
    kind: "solar",
    type: "total",
    magnitude: 1.056,
    region: "The 'Great Australasian Eclipse' - path of totality crosses Australia (including Kununurra and " +
      "Tennant Creek), the Indian Ocean, and Antarctica.",
  },
  {
    date: "2028-12-31T16:51:58Z",
    kind: "lunar",
    type: "total",
    magnitude: null,
    region: "Total lunar eclipse.",
  },
];

// Sagittarius A*, the galactic center.
const GALACTIC_CORE_RA_DEG = 266.4168;
const GALACTIC_CORE_DEC_DEG = -29.0078;

// Broad, general seasonal windows, not live radar - see the "birds" section note
// rendered with each event.
const BIRD_MIGRATION_WINDOWS = {
  north: [
    { label: "Spring songbird migration", startMonth: 3, startDay: 15, endMonth: 5, endDay: 31 },
    { label: "Fall songbird migration", startMonth: 8, startDay: 15, endMonth: 11, endDay: 15 },
  ],
  south: [
    { label: "Spring songbird migration", startMonth: 9, startDay: 15, endMonth: 11, endDay: 30 },
    { label: "Fall songbird migration", startMonth: 2, startDay: 15, endMonth: 5, endDay: 15 },
  ],
};

/* ---------------------------------------------------------------------- *
 * Daily astronomy table
 * ---------------------------------------------------------------------- */

const SUN_THRESHOLDS_DEG = {
  astro: -18,
  nautical: -12,
  civil: -6,
  blueGoldenBoundary: -4,
  horizon: -0.833,
  goldenTop: 6,
};

function horizonDipDeg(elevationMeters) {
  return elevationMeters > 0 ? (1.76 * Math.sqrt(elevationMeters)) / 60 : 0;
}

function indexByDay(crossings) {
  const map = new Map();
  for (const crossing of crossings) {
    const key = `${crossing.time.toDateString()}|${crossing.rising}`;
    if (!map.has(key)) map.set(key, crossing.time);
  }
  return map;
}

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** One row per calendar day in [start, end] with every named sun/moon instant. */
function buildDayTable(latRad, lonRad, start, end, elevationMeters) {
  const dip = horizonDipDeg(elevationMeters || 0);
  const sunAlt = (date) => sunAltitude(date, latRad, lonRad);
  const moonAlt = (date) => moonAltitude(date, latRad, lonRad);

  const sunCrossings = {};
  for (const [key, thresholdDeg] of Object.entries(SUN_THRESHOLDS_DEG)) {
    sunCrossings[key] = indexByDay(findAltitudeCrossings(sunAlt, start, end, (thresholdDeg - dip) * RAD, 4));
  }
  const moonCrossings = indexByDay(findAltitudeCrossings(moonAlt, start, end, (-0.833 - dip) * RAD, 4));

  const days = [];
  const lastDay = startOfDay(end);
  for (let cursor = startOfDay(start); cursor <= lastDay; cursor = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 1)) {
    const key = cursor.toDateString();
    const rise = (index) => index.get(`${key}|true`) || null;
    const set = (index) => index.get(`${key}|false`) || null;
    days.push({
      date: new Date(cursor),
      astroDawn: rise(sunCrossings.astro),
      nauticalDawn: rise(sunCrossings.nautical),
      civilDawn: rise(sunCrossings.civil),
      blueHourMorningEnd: rise(sunCrossings.blueGoldenBoundary),
      sunrise: rise(sunCrossings.horizon),
      goldenHourMorningEnd: rise(sunCrossings.goldenTop),
      goldenHourEveningStart: set(sunCrossings.goldenTop),
      sunset: set(sunCrossings.horizon),
      blueHourEveningStart: set(sunCrossings.blueGoldenBoundary),
      civilDusk: set(sunCrossings.civil),
      nauticalDusk: set(sunCrossings.nautical),
      astroDusk: set(sunCrossings.astro),
      moonrise: rise(moonCrossings),
      moonset: set(moonCrossings),
    });
  }
  return days;
}

function annotateMoonPhases(days) {
  const infos = days.map((day) => moonIllumination(new Date(day.date.getFullYear(), day.date.getMonth(), day.date.getDate(), 12)));
  days.forEach((day, i) => {
    const prev = infos[i - 1];
    const cur = infos[i];
    const next = infos[i + 1];
    day.moon = cur;
    day.isNewMoon = !!prev && !!next && cur.fraction <= prev.fraction && cur.fraction <= next.fraction && cur.fraction < 0.05;
    day.isFullMoon = !!prev && !!next && cur.fraction >= prev.fraction && cur.fraction >= next.fraction && cur.fraction > 0.95;
  });
}

/* ---------------------------------------------------------------------- *
 * Sky colour quality
 *
 * Grounded in how vivid sunsets actually form (NOAA/SPC, "The Colors of
 * Twilight and Sunset"): the low sun's light has to reach cloud from
 * underneath without first crossing the hazy boundary layer, and there has to
 * be mid/high cloud up there to catch it. So the ingredients are a clear path
 * to the horizon, broken rather than flat cloud, no rain-bearing deck, and
 * clean rather than hazy air - haze and smoke mute colour, they do not
 * enhance it.
 *
 * Almost every Home Assistant weather integration exposes a single aggregate
 * cloud_coverage rather than per-layer cloud, so "broken vs flat" is inferred
 * from how much that number moves across the hours either side of the event.
 * A sky that reads 20/55/35/60 over two hours is structured and dynamic; one
 * that reads 95/96/94 is a lid, and 3/2/4 is empty.
 * ---------------------------------------------------------------------- */

const SKY_TIER_LABELS = {
  epic: "Could be a big one - worth dropping everything for",
  excellent: "Strong potential for vivid colour",
  good: "Decent chance of colour",
  fair: "Probably a plain sky",
  poor: "Unlikely to light up",
};

const CONDITION_TIER = {
  partlycloudy: "excellent",
  sunny: "good",
  "clear-night": "good",
  windy: "good",
  "windy-variant": "good",
  cloudy: "fair",
  fog: "poor",
  rainy: "poor",
  pouring: "poor",
  lightning: "poor",
  "lightning-rainy": "poor",
  snowy: "poor",
  "snowy-rainy": "poor",
  hail: "poor",
};

const SKY_SAMPLE_OFFSETS_MINUTES = [-120, -90, -60, -30, 0, 30];

function forecastAt(forecast, targetDate, toleranceMinutes = 75) {
  if (!Array.isArray(forecast) || !forecast.length || !targetDate) return null;
  let best = null;
  let bestDiff = Infinity;
  for (const entry of forecast) {
    const t = new Date(entry.datetime).getTime();
    if (!Number.isFinite(t)) continue;
    const diff = Math.abs(t - targetDate.getTime());
    if (diff < bestDiff) {
      bestDiff = diff;
      best = entry;
    }
  }
  return bestDiff <= toleranceMinutes * 60000 ? best : null;
}

function collectSkySamples(forecast, eventTime) {
  const seen = new Set();
  const samples = [];
  for (const offset of SKY_SAMPLE_OFFSETS_MINUTES) {
    const entry = forecastAt(forecast, new Date(eventTime.getTime() + offset * 60000));
    if (!entry || seen.has(entry.datetime)) continue;
    seen.add(entry.datetime);
    samples.push(entry);
  }
  return samples;
}

const finiteNumbers = (values) => values.map(Number).filter(Number.isFinite);
const average = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

/** Peaks in the broken-cloud sweet spot; falls away toward empty and overcast skies. */
function cloudBaseScore(meanCloud) {
  if (meanCloud < 10) return 30;
  if (meanCloud < 25) return 55;
  if (meanCloud <= 65) return 75;
  if (meanCloud <= 80) return 55;
  if (meanCloud <= 92) return 30;
  return 12;
}

/**
 * The classic setup for a sky that actually catches fire: an unsettled few
 * hours that clears right as the sun gets low, leaving broken mid/high cloud
 * behind. Detected from the same hourly forecast rather than from history.
 */
function hasClearingTrend(forecast, eventTime, precipNow) {
  const earlier = [];
  for (let hours = 3; hours <= 9; hours += 1) {
    const entry = forecastAt(forecast, new Date(eventTime.getTime() - hours * 3600000), 45);
    if (entry) earlier.push(entry);
  }
  if (!earlier.length) return false;
  const earlierPrecip = finiteNumbers(earlier.map((entry) => entry.precipitation_probability));
  const earlierCloud = finiteNumbers(earlier.map((entry) => entry.cloud_coverage));
  const wasUnsettled = (earlierPrecip.length && Math.max(...earlierPrecip) >= 30) ||
    (earlierCloud.length && Math.max(...earlierCloud) >= 85);
  return wasUnsettled && precipNow < 20;
}

function tierForScore(score) {
  if (score >= 88) return "epic";
  if (score >= 70) return "excellent";
  if (score >= 50) return "good";
  if (score >= 30) return "fair";
  return "poor";
}

/**
 * Scores the colour potential of the sky around one sunrise/sunset, returning
 * a tier plus the plain-language reasons behind it so the pattern is legible
 * rather than a black-box number.
 */
function skyColorQuality(forecast, eventTime) {
  const samples = collectSkySamples(forecast, eventTime);
  if (!samples.length) return null;

  const clouds = finiteNumbers(samples.map((entry) => entry.cloud_coverage));
  if (!clouds.length) {
    const tier = CONDITION_TIER[samples[0].condition] || null;
    return tier ? { tier, label: SKY_TIER_LABELS[tier], reasons: [] } : null;
  }

  const meanCloud = average(clouds);
  const spread = Math.max(...clouds) - Math.min(...clouds);
  const precipValues = finiteNumbers(samples.map((entry) => entry.precipitation_probability));
  const precip = precipValues.length ? Math.max(...precipValues) : 0;
  const humidityValues = finiteNumbers(samples.map((entry) => entry.humidity));
  const humidity = humidityValues.length ? average(humidityValues) : null;

  let score = cloudBaseScore(meanCloud);
  const reasons = [];

  if (meanCloud < 10) reasons.push("nearly empty sky");
  else if (meanCloud > 92) reasons.push("solid overcast");
  else reasons.push(`${Math.round(meanCloud)}% cloud`);

  if (clouds.length >= 2) {
    if (spread >= 35) {
      score += 18;
      reasons.push("broken, fast-changing cloud");
    } else if (spread >= 20) {
      score += 12;
      reasons.push("some structure in the cloud");
    } else if (spread >= 10) {
      score += 6;
    } else if (meanCloud > 25 && meanCloud < 92) {
      score -= 6;
      reasons.push("flat, featureless deck");
    }
  }

  if (precip >= 70) {
    score -= 35;
    reasons.push("rain likely");
  } else if (precip >= 45) {
    score -= 20;
    reasons.push("showers around");
  } else if (precip >= 25) {
    score -= 8;
  }

  if (hasClearingTrend(forecast, eventTime, precip)) {
    score += 15;
    reasons.push("clearing after an unsettled afternoon");
  }

  // Haze and heavy moisture mute colour rather than enhancing it.
  if (humidity !== null) {
    if (humidity >= 90) {
      score -= 10;
      reasons.push("hazy, humid air");
    } else if (humidity >= 80) {
      score -= 5;
    }
  }

  const tier = tierForScore(clamp(score, 0, 100));
  return { tier, label: SKY_TIER_LABELS[tier], reasons, score: Math.round(clamp(score, 0, 100)) };
}

function meteorQuality(maxAltitudeDeg, moonFraction) {
  if (maxAltitudeDeg < 10) return { tier: "poor", label: "Radiant stays low from here" };
  if (moonFraction > 0.5) return { tier: "fair", label: "Bright moonlight will wash out fainter meteors" };
  if (maxAltitudeDeg >= 30 && moonFraction < 0.3) return { tier: "excellent", label: "Radiant well-placed, dark skies" };
  return { tier: "good", label: "Worth a look after midnight" };
}

/* ---------------------------------------------------------------------- *
 * Eclipse local circumstances
 * ---------------------------------------------------------------------- */

function lunarEclipseVisibility(eclipseDate, latRad, lonRad) {
  const windowMs = 3 * 3600000;
  const altitudes = [-1, -0.5, 0, 0.5, 1].map(
    (f) => moonAltitude(new Date(eclipseDate.getTime() + f * windowMs), latRad, lonRad) * DEG,
  );
  const anyUp = altitudes.some((a) => a > 0);
  const allUp = altitudes.every((a) => a > 0);
  if (!anyUp) return { visible: false, note: "The Moon is below your horizon for this entire eclipse." };
  if (!allUp) return { visible: true, note: "The Moon rises or sets during this eclipse - check the moonrise/moonset time." };
  return { visible: true, note: "The Moon is above your horizon for the whole event, weather permitting." };
}

function solarEclipseVisibility(eclipseDate, latRad, lonRad) {
  const windowMs = 2 * 3600000;
  const altitudes = [-1, -0.5, 0, 0.5, 1].map(
    (f) => sunAltitude(new Date(eclipseDate.getTime() + f * windowMs), latRad, lonRad) * DEG,
  );
  const anyUp = altitudes.some((a) => a > 0);
  if (!anyUp) return { visible: false, note: "It's nighttime at your location during this eclipse - not visible from here." };
  return { visible: null, note: "It's daytime at your location, but only the path sees it - check an eclipse map for your area." };
}

/* ---------------------------------------------------------------------- *
 * Event assembly
 * ---------------------------------------------------------------------- */

const QUALITY_RANK = { epic: 4, excellent: 3, good: 2, fair: 1, poor: 0 };

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function fmtTime(date) {
  if (!date) return "—";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function fmtDate(date) {
  if (!date) return "—";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function skyBadge(quality) {
  if (!quality) return null;
  return quality.reasons?.length ? `${quality.label} - ${quality.reasons.join(", ")}` : quality.label;
}

function eveningLightEvent(day, forecast) {
  if (!day.sunset) return null;
  const quality = skyColorQuality(forecast, day.sunset);
  const parts = [];
  if (day.goldenHourEveningStart) parts.push(`Golden hour from ${fmtTime(day.goldenHourEveningStart)}`);
  parts.push(`Sunset ${fmtTime(day.sunset)}`);
  if (day.blueHourEveningStart && day.civilDusk) {
    parts.push(`blue hour ${fmtTime(day.blueHourEveningStart)}-${fmtTime(day.civilDusk)}`);
  }
  const epic = quality?.tier === "epic";
  return {
    id: `evening-${day.date.toDateString()}`,
    category: "sun",
    time: day.goldenHourEveningStart || day.sunset,
    relevantUntil: day.civilDusk || day.sunset,
    title: epic ? "Sunset could go off tonight" : "Evening golden hour",
    detail: parts.join(" · "),
    quality: quality?.tier ?? null,
    score: quality?.score ?? null,
    badge: skyBadge(quality),
    icon: epic ? "mdi:fire" : "mdi:weather-sunset-down",
  };
}

function morningLightEvent(day, forecast) {
  if (!day.sunrise) return null;
  const quality = skyColorQuality(forecast, day.sunrise);
  const parts = [];
  if (day.civilDawn && day.blueHourMorningEnd) {
    parts.push(`Blue hour ${fmtTime(day.civilDawn)}-${fmtTime(day.blueHourMorningEnd)}`);
  }
  parts.push(`Sunrise ${fmtTime(day.sunrise)}`);
  if (day.goldenHourMorningEnd) parts.push(`golden hour until ${fmtTime(day.goldenHourMorningEnd)}`);
  const epic = quality?.tier === "epic";
  return {
    id: `morning-${day.date.toDateString()}`,
    category: "sun",
    time: day.civilDawn || day.sunrise,
    relevantUntil: day.goldenHourMorningEnd || day.sunrise,
    title: epic ? "Sunrise could go off" : "Morning golden hour",
    detail: parts.join(" · "),
    quality: quality?.tier ?? null,
    score: quality?.score ?? null,
    badge: skyBadge(quality),
    icon: epic ? "mdi:fire" : "mdi:weather-sunset-up",
  };
}

function moonDayEvent(day, nearTermEnd) {
  const flagged = day.isNewMoon || day.isFullMoon;
  const representativeTime = day.moonrise || day.moonset || new Date(day.date.getFullYear(), day.date.getMonth(), day.date.getDate(), 20);
  if (!flagged && representativeTime > nearTermEnd) return null;

  const bits = [];
  if (day.moonrise) bits.push(`Moonrise ${fmtTime(day.moonrise)}`);
  if (day.moonset) bits.push(`Moonset ${fmtTime(day.moonset)}`);
  const phaseInfo = moonPhaseInfo(day.moon.phase);

  let title = phaseInfo.label;
  let badge = null;
  let quality = null;
  const isSupermoon = day.isFullMoon && day.moon.distanceKm < 360000;
  if (day.isNewMoon) {
    title = "New Moon - dark sky window";
    badge = "Great for stars and the Milky Way";
    quality = "excellent";
  } else if (day.isFullMoon) {
    title = isSupermoon ? "Full Moon (Supermoon)" : "Full Moon";
    badge = "Moonrise-over-the-landscape opportunity";
    quality = "good";
  }

  const detail = [
    title !== phaseInfo.label ? phaseInfo.label : null,
    `${Math.round(day.moon.fraction * 100)}% illuminated`,
    ...bits,
  ].filter(Boolean).join(" · ");

  return {
    id: `moon-${day.date.toDateString()}`,
    category: "moon",
    time: representativeTime,
    // A phase callout describes the whole night, not just a rise/set instant.
    relevantUntil: new Date(day.date.getFullYear(), day.date.getMonth(), day.date.getDate() + 1),
    title,
    detail,
    quality,
    badge,
    // Only two lunar events change what anyone does: the dark-sky window, and
    // a supermoon worth putting a landscape in front of. Quarters are trivia.
    notable: Boolean(day.isNewMoon || isSupermoon),
    icon: phaseInfo.icon,
  };
}

function meteorShowerEvents(days, latRad, lonRad, rangeStart, rangeEnd) {
  const events = [];
  const years = new Set([rangeStart.getFullYear(), rangeEnd.getFullYear()]);
  for (const shower of METEOR_SHOWERS) {
    for (const year of years) {
      const peak = new Date(year, shower.peakMonth - 1, shower.peakDay, 12, 0, 0);
      if (peak < rangeStart || peak > rangeEnd) continue;
      const dayIndex = days.findIndex((d) => d.date.toDateString() === peak.toDateString());
      const day = days[dayIndex];
      const darkHours = darkWindow(days, dayIndex);
      if (!day || !darkHours) continue;
      const maxAlt = maxAltitudeInWindow(shower.raDeg, shower.decDeg, darkHours.start, darkHours.end, latRad, lonRad, 20);
      const quality = meteorQuality(maxAlt, day.moon.fraction);
      events.push({
        id: `meteor-${shower.name}-${year}`,
        category: "meteor",
        time: day.astroDusk,
        relevantUntil: darkHours.end,
        title: `${shower.name} meteor shower peak`,
        detail: `Up to ~${shower.zhr}/hr under ideal dark skies. Best after midnight, looking toward the radiant.`,
        quality: quality.tier,
        badge: quality.label,
        icon: "mdi:star-shooting",
      });
    }
  }
  return events;
}

function milkyWayNight(days, index, latRad, lonRad) {
  const day = days[index];
  const darkHours = darkWindow(days, index);
  if (!darkHours) return null;
  const maxAlt = maxAltitudeInWindow(
    GALACTIC_CORE_RA_DEG,
    GALACTIC_CORE_DEC_DEG,
    darkHours.start,
    darkHours.end,
    latRad,
    lonRad,
    30,
  );
  if (maxAlt < 15 || day.moon.fraction >= 0.4) return null;
  return { day, darkHours, maxAlt };
}

/**
 * The core is well placed on runs of consecutive moonless nights, so a row per
 * night would bury everything else in the timeline. Collapse each run into one
 * entry that names the window and the single best night in it.
 */
function milkyWayEvents(days, latRad, lonRad, todayStart, outlookEnd) {
  const events = [];
  let run = [];

  const flush = () => {
    if (!run.length) return;
    const best = run.reduce((top, night) => (night.maxAlt > top.maxAlt ? night : top), run[0]);
    const first = run[0];
    const last = run[run.length - 1];
    const tier = best.maxAlt >= 35 ? "excellent" : "good";
    const multiNight = run.length > 1;
    events.push({
      id: `milkyway-${first.day.date.toDateString()}`,
      category: "milkyway",
      time: first.darkHours.start,
      relevantUntil: last.darkHours.end,
      title: multiNight ? `Milky Way window: ${run.length} dark nights` : "Milky Way core visible",
      detail: `${multiNight ? `${fmtDate(first.day.date)} to ${fmtDate(last.day.date)}, best on ${fmtDate(best.day.date)} - core ` : "Core "}` +
        `reaches ~${Math.round(best.maxAlt)}° with a ${Math.round(best.day.moon.fraction * 100)}%-lit moon. ` +
        `Look south after ${fmtTime(best.darkHours.start)}, away from light pollution.`,
      quality: tier,
      badge: tier === "excellent" ? "Great dark-sky window" : "Worth a look",
      icon: "mdi:telescope",
    });
    run = [];
  };

  for (let i = 0; i < days.length; i += 1) {
    const inRange = days[i].date >= todayStart && days[i].date <= outlookEnd;
    const night = inRange ? milkyWayNight(days, i, latRad, lonRad) : null;
    if (night) run.push(night);
    else flush();
  }
  flush();

  return events;
}

const PLANET_CONJUNCTION_MAX_DEG = 3;
const MOON_CONJUNCTION_MAX_DEG = 4;
const PHOTOGENIC_PLANETS = new Set(["Venus", "Jupiter", "Saturn", "Mars"]);
const PLANET_VISIBLE_MIN_ALT_DEG = 12;

function isLocalMax(values, i) {
  return i > 0 && i < values.length - 1 && values[i] >= values[i - 1] && values[i] >= values[i + 1];
}

function isLocalMin(values, i) {
  return i > 0 && i < values.length - 1 && values[i] <= values[i - 1] && values[i] <= values[i + 1];
}

/**
 * The span of true darkness that starts with this day's dusk.
 *
 * Pairs a dusk with the next dawn that actually follows it rather than
 * assuming "tomorrow's" row holds it. Which calendar day a dusk lands on
 * depends on the offset between the browser's timezone and the configured
 * coordinates, and when those disagree - a location override in another
 * timezone - the naive pairing silently produces a 30-hour "night" that spans
 * a whole daylight period.
 */
function darkWindow(days, index) {
  const start = days[index]?.astroDusk;
  if (!start) return null;
  for (let i = index; i < days.length; i += 1) {
    const dawn = days[i].astroDawn;
    if (dawn && dawn > start) return { start, end: dawn };
  }
  return null;
}

/**
 * Oppositions, greatest elongations, close conjunctions, and - for the next
 * few nights only - a single consolidated "what's up tonight" row. One row per
 * night rather than one per planet, so the timeline stays readable.
 */
function planetEvents(days, latRad, lonRad, todayStart, outlookEnd, nearTermEnd) {
  const events = [];
  const samples = days.map((day) => {
    const noon = new Date(day.date.getFullYear(), day.date.getMonth(), day.date.getDate(), 12);
    const positions = new Map();
    for (const planet of PLANETS) {
      positions.set(planet.name, {
        ...planetGeocentric(planet, noon),
        elongation: planetElongationDeg(planet, noon),
      });
    }
    return { day, noon, positions, moon: moonEquatorial(daysSinceJ2000(noon)) };
  });

  const inRange = (day) => day.date >= todayStart && day.date <= outlookEnd;

  for (const planet of PLANETS) {
    const elongations = samples.map((sample) => sample.positions.get(planet.name).elongation);
    for (let i = 0; i < samples.length; i += 1) {
      if (!isLocalMax(elongations, i) || !inRange(samples[i].day)) continue;
      const elongation = elongations[i];
      const darkHours = darkWindow(days, i);
      const position = samples[i].positions.get(planet.name);

      if (!planet.inner && elongation > 170) {
        events.push({
          id: `opposition-${planet.name}-${samples[i].day.date.toDateString()}`,
          category: "planet",
          time: samples[i].day.astroDusk || samples[i].noon,
          relevantUntil: darkHours ? darkHours.end : null,
          kind: "opposition",
          title: `${planet.name} at opposition`,
          detail: `Closest and brightest of the year at ${position.distanceAu.toFixed(2)} AU, and above the horizon ` +
            "essentially all night - the best window to shoot it.",
          quality: "excellent",
          badge: "Up all night",
          icon: "mdi:circle-slice-8",
        });
      } else if (planet.inner && elongation > (planet.name === "Venus" ? 40 : 16)) {
        const eastern = isEasternElongation(planet, samples[i].noon);
        events.push({
          id: `elongation-${planet.name}-${samples[i].day.date.toDateString()}`,
          category: "planet",
          time: eastern ? samples[i].day.civilDusk || samples[i].noon : samples[i].day.civilDawn || samples[i].noon,
          relevantUntil: eastern ? samples[i].day.astroDusk : samples[i].day.sunrise,
          title: `${planet.name} at greatest elongation`,
          detail: `${Math.round(elongation)}° from the Sun - its highest, easiest apparition of this cycle, ` +
            `low in the ${eastern ? "west just after sunset" : "east before sunrise"}.`,
          quality: planet.name === "Venus" ? "excellent" : "good",
          badge: eastern ? "Evening star" : "Morning star",
          icon: "mdi:star-four-points",
        });
      }
    }
  }

  const pairs = [];
  for (let a = 0; a < PLANETS.length; a += 1) {
    for (let b = a + 1; b < PLANETS.length; b += 1) pairs.push([PLANETS[a], PLANETS[b]]);
  }

  for (const [first, second] of pairs) {
    const separations = samples.map((sample) => {
      const p1 = sample.positions.get(first.name);
      const p2 = sample.positions.get(second.name);
      return angularSeparation(p1.ra, p1.dec, p2.ra, p2.dec) * DEG;
    });
    for (let i = 0; i < samples.length; i += 1) {
      if (!isLocalMin(separations, i) || separations[i] > PLANET_CONJUNCTION_MAX_DEG || !inRange(samples[i].day)) continue;
      const placement = twilightPlacement(samples[i].positions.get(first.name).ra, samples[i].day);
      events.push({
        id: `conjunction-${first.name}-${second.name}-${samples[i].day.date.toDateString()}`,
        category: "planet",
        time: placement.time || samples[i].noon,
        relevantUntil: placement.until || null,
        kind: "conjunction",
        separationDeg: separations[i],
        title: `${first.name} and ${second.name} in conjunction`,
        detail: `Just ${separations[i].toFixed(1)}° apart ${placement.where} - close enough to frame together with a long lens.`,
        quality: "excellent",
        badge: "Planetary pairing",
        icon: "mdi:star-four-points",
      });
    }
  }

  for (const planet of PLANETS) {
    if (!PHOTOGENIC_PLANETS.has(planet.name)) continue;
    const separations = samples.map((sample) => {
      const position = sample.positions.get(planet.name);
      return angularSeparation(position.ra, position.dec, sample.moon.ra, sample.moon.dec) * DEG;
    });
    for (let i = 0; i < samples.length; i += 1) {
      if (!isLocalMin(separations, i) || separations[i] > MOON_CONJUNCTION_MAX_DEG || !inRange(samples[i].day)) continue;
      const phase = moonPhaseInfo(samples[i].day.moon.phase);
      const placement = twilightPlacement(samples[i].positions.get(planet.name).ra, samples[i].day);
      events.push({
        id: `moon-conjunction-${planet.name}-${samples[i].day.date.toDateString()}`,
        kind: "conjunction",
        separationDeg: separations[i],
        category: "planet",
        time: placement.time || samples[i].noon,
        relevantUntil: placement.until || null,
        title: `Moon meets ${planet.name}`,
        detail: `${separations[i].toFixed(1)}° apart ${placement.where}, with a ${phase.label.toLowerCase()} ` +
          `(${Math.round(samples[i].day.moon.fraction * 100)}% lit) - a classic wide-or-long-lens pairing.`,
        quality: "good",
        badge: "Moon pairing",
        icon: "mdi:star-four-points",
      });
    }
  }

  for (let i = 0; i < samples.length - 1; i += 1) {
    const { day } = samples[i];
    if (!inRange(day) || !day.astroDusk || day.astroDusk > nearTermEnd) continue;
    const darkHours = darkWindow(days, i);
    if (!darkHours) continue;
    const visible = [];
    for (const planet of PLANETS) {
      const position = samples[i].positions.get(planet.name);
      const maxAlt = maxAltitudeInWindow(position.ra * DEG, position.dec * DEG, darkHours.start, darkHours.end, latRad, lonRad, 30);
      if (maxAlt >= PLANET_VISIBLE_MIN_ALT_DEG) visible.push(`${planet.name} (peaks ~${Math.round(maxAlt)}°)`);
    }
    if (!visible.length) continue;
    events.push({
      id: `planets-${day.date.toDateString()}`,
      category: "planet",
      time: day.astroDusk,
      relevantUntil: darkHours.end,
      kind: "nightly",
      title: `Planets tonight: ${visible.length === 1 ? visible[0].split(" ")[0] : `${visible.length} visible`}`,
      detail: visible.join(" · "),
      quality: null,
      badge: null,
      icon: "mdi:star-four-points-outline",
    });
  }

  return events;
}

/** True when the body trails the Sun (visible after sunset) rather than leading it. */
function isEastOfSun(raRad, date) {
  const sun = sunEquatorial(daysSinceJ2000(date));
  return ((raRad - sun.ra) * DEG + 540) % 360 - 180 > 0;
}

function isEasternElongation(planet, date) {
  return isEastOfSun(planetGeocentric(planet, date).ra, date);
}

/**
 * Anything close to the Sun is a twilight subject, and which twilight depends
 * on which side of the Sun it sits - telling someone to look west after sunset
 * for a dawn pairing would be worse than saying nothing.
 */
function twilightPlacement(raRad, day) {
  const evening = isEastOfSun(raRad, day.date);
  return evening
    ? { evening: true, where: "in the west after sunset", time: day.civilDusk, until: day.astroDusk }
    : { evening: false, where: "in the east before dawn", time: day.civilDawn, until: day.sunrise };
}

function eclipseEvents(now) {
  const events = [];
  for (const eclipse of ECLIPSES) {
    const date = new Date(eclipse.date);
    if (date < now) continue;
    events.push({ eclipse, date });
  }
  events.sort((a, b) => a.date - b.date);
  return events;
}

function buildEclipseEvent(eclipse, date, latRad, lonRad) {
  const visibility = eclipse.kind === "lunar"
    ? lunarEclipseVisibility(date, latRad, lonRad)
    : solarEclipseVisibility(date, latRad, lonRad);
  const kindLabel = eclipse.kind === "lunar" ? "Lunar" : "Solar";
  const typeLabel = eclipse.type.charAt(0).toUpperCase() + eclipse.type.slice(1);
  const badge = visibility.visible === false
    ? "Not visible from here"
    : visibility.visible === true
      ? "Visible from here"
      : "Check the path";
  return {
    id: `eclipse-${eclipse.date}`,
    category: "eclipse",
    time: date,
    relevantUntil: new Date(date.getTime() + (eclipse.kind === "lunar" ? 3 : 2) * 3600000),
    title: `${typeLabel} ${kindLabel} Eclipse`,
    detail: `${eclipse.region} ${visibility.note}`,
    quality: visibility.visible === false ? "poor" : visibility.visible === true ? "excellent" : "fair",
    visible: visibility.visible,
    badge,
    icon: "mdi:eclipse",
  };
}

/**
 * Comets, novae, and anything else that gets announced rather than predicted.
 *
 * Unlike meteor showers (which recur annually) or eclipses (which are computed
 * centuries ahead), a bright comet is usually only known to be worth chasing a
 * few months out, so a hardcoded comet table would be stale or wrong more
 * often than right. Instead the user adds an entry when one is announced and
 * this runs it through the same visibility and moonlight scoring as everything
 * else: how high it gets during true darkness, and whether the Moon will wash
 * it out.
 */
function customSkyEvents(config, days, latRad, lonRad, todayStart, outlookEnd) {
  const entries = Array.isArray(config.custom_events) ? config.custom_events : [];
  const events = [];

  for (const entry of entries) {
    const raDeg = numberOrNull(entry?.ra_deg ?? entry?.ra);
    const decDeg = numberOrNull(entry?.dec_deg ?? entry?.dec);
    const name = typeof entry?.name === "string" ? entry.name.trim() : "";
    if (!name || raDeg === null || decDeg === null) continue;

    const start = entry.start ? new Date(entry.start) : todayStart;
    const end = entry.end ? new Date(entry.end) : outlookEnd;
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) continue;
    if (end < todayStart || start > outlookEnd) continue;

    // Score the best night inside the visible window rather than the first,
    // so a comet that only clears the horizon later still reads accurately.
    let best = null;
    for (let i = 0; i < days.length - 1; i += 1) {
      const day = days[i];
      if (day.date < todayStart || day.date > outlookEnd || day.date < startOfDay(start) || day.date > end) continue;
      const darkHours = darkWindow(days, i);
      if (!darkHours) continue;
      const maxAlt = maxAltitudeInWindow(raDeg, decDeg, darkHours.start, darkHours.end, latRad, lonRad, 30);
      if (!best || maxAlt > best.maxAlt) best = { day, darkHours, maxAlt };
    }
    if (!best || best.maxAlt < 5) continue;

    const moonFraction = best.day.moon.fraction;
    const quality = meteorQuality(best.maxAlt, moonFraction);
    const note = typeof entry?.note === "string" && entry.note.trim() ? ` ${entry.note.trim()}` : "";
    events.push({
      id: `custom-${name}-${best.day.date.toDateString()}`,
      category: "custom",
      time: best.day.astroDusk,
      relevantUntil: end < best.darkHours.end ? end : best.darkHours.end,
      title: name,
      detail: `Reaches ~${Math.round(best.maxAlt)}° during full darkness on the best night in range, with a ` +
        `${Math.round(moonFraction * 100)}%-lit moon.${note}`,
      quality: quality.tier,
      badge: quality.label,
      icon: "mdi:comet",
    });
  }

  return events;
}

function birdMigrationEvents(latRad, now, rangeStart, rangeEnd) {
  const hemisphere = latRad >= 0 ? "north" : "south";
  const events = [];
  for (const year of new Set([rangeStart.getFullYear(), rangeEnd.getFullYear()])) {
    for (const season of BIRD_MIGRATION_WINDOWS[hemisphere]) {
      const start = new Date(year, season.startMonth - 1, season.startDay);
      const end = new Date(year, season.endMonth - 1, season.endDay, 23, 59, 59);
      if (end < rangeStart || start > rangeEnd) continue;
      events.push({
        id: `birds-${season.label}-${year}`,
        category: "birds",
        time: start < now ? now : start,
        relevantUntil: end,
        title: season.label,
        detail: "General seasonal pattern for your latitude, not live migration radar. For real-time nocturnal " +
          "migration intensity, check Cornell Lab's BirdCast.",
        quality: null,
        badge: "Seasonal",
        icon: "mdi:bird",
      });
    }
  }
  return events;
}

/** Assembles the sorted event timeline for [now, now + outlook_days], plus any near eclipses beyond it. */
function buildEvents(hass, config, forecast, now) {
  const latDeg = numberOrNull(config.latitude) ?? hass.config?.latitude;
  const lonDeg = numberOrNull(config.longitude) ?? hass.config?.longitude;
  if (!Number.isFinite(latDeg) || !Number.isFinite(lonDeg)) {
    return { events: [], error: "No location configured. Set a latitude/longitude in Home Assistant or override it in this card's config." };
  }
  const latRad = latDeg * RAD;
  const lonRad = lonDeg * RAD;
  const elevation = numberOrNull(config.elevation) ?? hass.config?.elevation ?? 0;

  const todayStart = startOfDay(now);
  const outlookEnd = new Date(todayStart.getTime() + config.outlook_days * MS_PER_DAY);
  const nearTermEnd = new Date(now.getTime() + 72 * 3600000);

  const tableStart = new Date(todayStart.getTime() - MS_PER_DAY);
  const tableEnd = new Date(outlookEnd.getTime() + 2 * MS_PER_DAY);
  const days = buildDayTable(latRad, lonRad, tableStart, tableEnd, elevation);
  annotateMoonPhases(days);

  const relevantDays = days.filter((day) => day.date >= todayStart && day.date <= outlookEnd);
  const events = [];

  if (config.show_sun_events !== false) {
    for (const day of relevantDays) {
      const evening = eveningLightEvent(day, forecast);
      const morning = morningLightEvent(day, forecast);
      // Compare each event's own time, not the calendar day, to the near-term
      // cutoff - otherwise a day that merely starts within 72h would show its
      // late-evening event unconditionally too. Past the near term, only a
      // genuinely promising sky is worth a row.
      for (const event of [morning, evening]) {
        const promising = event?.quality === "excellent" || event?.quality === "epic";
        if (event && (event.time <= nearTermEnd || promising)) events.push(event);
      }
    }
  }

  if (config.show_moon_events !== false) {
    for (const day of relevantDays) {
      const event = moonDayEvent(day, nearTermEnd);
      if (event) events.push(event);
    }
  }

  if (config.show_planets !== false) {
    events.push(...planetEvents(days, latRad, lonRad, todayStart, outlookEnd, nearTermEnd));
  }

  if (config.show_meteor_showers !== false) {
    events.push(...meteorShowerEvents(days, latRad, lonRad, todayStart, outlookEnd));
  }

  events.push(...customSkyEvents(config, days, latRad, lonRad, todayStart, outlookEnd));

  if (config.show_milky_way !== false) {
    events.push(...milkyWayEvents(days, latRad, lonRad, todayStart, outlookEnd));
  }

  if (config.show_bird_migration !== false) {
    events.push(...birdMigrationEvents(latRad, now, todayStart, outlookEnd));
  }

  if (config.show_eclipses !== false) {
    const upcoming = eclipseEvents(now);
    const withinWindow = upcoming.filter((e) => e.date <= outlookEnd);
    const nextFew = upcoming.slice(0, 2);
    const seen = new Set();
    for (const entry of [...withinWindow, ...nextFew]) {
      if (seen.has(entry.eclipse.date)) continue;
      seen.add(entry.eclipse.date);
      events.push(buildEclipseEvent(entry.eclipse, entry.date, latRad, lonRad));
    }
  }

  const kept = config.hide_routine === false ? events : pruneRoutine(events);

  // Each event carries its own "still relevant" boundary (a whole night, an
  // eclipse's multi-hour window, a migration season) rather than a single
  // cutoff, so today's already-finished morning golden hour drops out while
  // an all-night meteor shower or eclipse in progress does not.
  const stillRelevant = kept.filter((event) => (event.relevantUntil || new Date(event.time.getTime() + 30 * 60000)) >= now);
  stillRelevant.sort((a, b) => a.time - b.time);
  return { events: stillRelevant, error: null };
}

// Above this the sky is worth a row of its own. Below it, "the sun will set
// this evening" is not news.
const EPIC_SKY_SCORE = 85;
// A conjunction only reads as one object through a long lens when the two are
// this close; wider than that is a pleasing sky, not a photograph.
const TIGHT_CONJUNCTION_DEG = 1.0;

/**
 * Strip the everyday.
 *
 * Golden hour happens twice a day, the Moon reaches first quarter every month,
 * and two planets are usually up somewhere. Listing all of it buries the four
 * or five things a year that are actually worth reorganising an evening
 * around - which is the entire job of this card.
 */
function pruneRoutine(events) {
  return events.filter((event) => {
    switch (event.category) {
      case "sun":
        // No score means no forecast was available, and an unscored sunset is
        // not evidence of a good one.
        return typeof event.score === "number" && event.score >= EPIC_SKY_SCORE;
      case "moon":
        return event.notable === true;
      case "planet":
        if (event.kind === "opposition") return true;
        if (event.kind === "conjunction") {
          return typeof event.separationDeg === "number" && event.separationDeg < TIGHT_CONJUNCTION_DEG;
        }
        return false;
      case "eclipse":
        // An eclipse nobody here can see is a fact about somewhere else.
        return event.visible !== false;
      default:
        return true;
    }
  });
}

/* ---------------------------------------------------------------------- *
 * Rendering helpers
 * ---------------------------------------------------------------------- */

const escapeHtml = (value) =>
  String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

function dayHeaderLabel(date, now) {
  const diffDays = Math.round((startOfDay(date) - startOfDay(now)) / MS_PER_DAY);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function relativeLabel(now, date) {
  const diffMs = date - now;
  if (diffMs <= 0) return "now";
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hours = Math.round(diffMs / 3600000);
  if (hours < 48) return `in ${hours}h`;
  return `in ${Math.round(diffMs / MS_PER_DAY)}d`;
}

const CATEGORY_TOGGLE_KEYS = [
  "show_sun_events",
  "show_moon_events",
  "show_planets",
  "show_meteor_showers",
  "show_eclipses",
  "show_milky_way",
  "show_bird_migration",
];

/* ---------------------------------------------------------------------- *
 * Config editor
 * ---------------------------------------------------------------------- */

// --- Backend-driven modes ---------------------------------------------------
//
// The timeline mode below computes everything in the browser, which is what
// this card did before the integration existed. It still works standalone, so
// it stays.
//
// These two modes do the opposite: they render what the `photography_events`
// integration has already worked out. That is not a shortcut - the browser
// cannot hold an API key, cannot call eBird or Google past CORS, and only runs
// while somebody has the dashboard open. Anything sourced from a live service
// has to arrive as entity state, so these modes read it and draw it.

const MODE_TIMELINE = "timeline";
const MODE_HERO = "action_hero";
const MODE_OUTLOOK = "calendar_outlook";
const BACKEND_MODES = new Set([MODE_HERO, MODE_OUTLOOK]);

const CATEGORY_META = Object.freeze({
  astronomy: { label: "Astro", icon: "mdi:telescope" },
  sunset: { label: "Skies", icon: "mdi:weather-sunset" },
  marine: { label: "Whales", icon: "mdi:whale" },
  mammals: { label: "Mammals", icon: "mdi:paw" },
  birds: { label: "Birds", icon: "mdi:bird" },
  blooms: { label: "Blooms", icon: "mdi:flower" },
  foliage: { label: "Autumn", icon: "mdi:leaf-maple" },
  parks: { label: "Parks", icon: "mdi:pine-tree" },
});

// Icon and colour per access class. The wording comes from the park itself -
// "Paved paths only" tells you whether the trip is worth taking; a generic
// "Dogs restricted" does not.
const DOG_META = Object.freeze({
  full: { label: "Dogs on trails", icon: "mdi:dog-side", tone: "yes" },
  limited: { label: "Dogs restricted", icon: "mdi:dog", tone: "part" },
  none: { label: "No dogs", icon: "mdi:dog-side-off", tone: "no" },
});

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

/** Minutes as something a person would say out loud. */
function driveLabel(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0));
  if (total < 90) return `${total} min`;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return rest ? `${hours} h ${String(rest).padStart(2, "0")}` : `${hours} h`;
}

/**
 * How much to trust the drive time. A routed figure and a straight-line
 * estimate are both "a number of minutes", and showing them identically would
 * quietly imply the estimate is as good as the route.
 */
function driveProvenance(source, inTraffic) {
  if (source === "Routes API" || source === "Distance Matrix API") {
    return { routed: true, note: inTraffic ? "live traffic" : "by road", detail: source };
  }
  if (source === "estimate") return { routed: false, note: "estimated", detail: "distance estimate, no route" };
  return { routed: false, note: "baseline", detail: "measured baseline for this destination" };
}

/** Date from either a full timestamp or an all-day `YYYY-MM-DD`. */
function parseEventDate(value) {
  if (!value) return null;
  const text = String(value);
  const date = /^\d{4}-\d{2}-\d{2}$/.test(text) ? new Date(`${text}T00:00:00`) : new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** The hero's payload, or null when there is nothing to shout about. */
function heroFromState(state) {
  if (!state || state.state !== "on") return null;
  const attributes = state.attributes || {};
  if (!attributes.event_name) return null;
  return {
    name: attributes.event_name,
    score: Number(attributes.confidence_score) || 0,
    category: attributes.category || "",
    zone: attributes.target_zone || "",
    driveMinutes: Number(attributes.drive_minutes) || Math.round((Number(attributes.drive_hours) || 0) * 60),
    drive: driveProvenance(attributes.drive_source, attributes.drive_in_traffic),
    starts: parseEventDate(attributes.starts),
    ends: parseEventDate(attributes.ends),
    summary: attributes.condition_summary || "",
    reasons: Array.isArray(attributes.reasons) ? attributes.reasons : [],
    gear: {
      glass: attributes.gear_glass || "",
      support: attributes.gear_support || "",
      settings: attributes.gear_settings || "",
    },
    sourceUrl: attributes.source_url || "",
  };
}

/** The planning sensor's payload, normalised and defensive about shape. */
function outlookFromState(state) {
  const attributes = state?.attributes || {};
  const events = Array.isArray(attributes.events) ? attributes.events : [];
  return {
    events,
    parks: attributes.parks && typeof attributes.parks === "object" ? attributes.parks : {},
    gear: attributes.gear_by_category && typeof attributes.gear_by_category === "object"
      ? attributes.gear_by_category
      : {},
    categories: Array.isArray(attributes.all_categories) && attributes.all_categories.length
      ? attributes.all_categories
      : Array.isArray(attributes.categories) ? attributes.categories : [],
    truncated: Boolean(attributes.truncated),
    missing: !state,
  };
}

/**
 * Which categories the toggles currently allow.
 *
 * A category with no toggle configured is always shown - the absence of a
 * switch means "not filtered", never "hidden", so a half-configured card
 * cannot silently swallow half the calendar.
 */
function activeCategories(hass, toggles, known) {
  const allowed = new Set(known);
  for (const [category, entityId] of Object.entries(toggles || {})) {
    const state = hass?.states?.[entityId];
    if (!state) continue;
    if (state.state === "off") allowed.delete(category);
    else allowed.add(category);
  }
  return allowed;
}

/** Events inside the planning window, in the allowed categories, in order. */
function filterOutlook(events, { allowed, now, fromDays, throughDays }) {
  const from = new Date(now.getTime() + fromDays * 86400000);
  const through = new Date(now.getTime() + throughDays * 86400000);
  return events
    .map((event) => ({ ...event, startDate: parseEventDate(event.start), endDate: parseEventDate(event.end) }))
    .filter((event) => {
      if (!event.startDate) return false;
      if (allowed && !allowed.has(event.category)) return false;
      // A season already underway is kept: its end is what matters, not its
      // start, and a park in its best window right now is the single most
      // useful thing a planning view can show.
      const finish = event.endDate || event.startDate;
      return finish >= from && event.startDate <= through;
    })
    .sort((left, right) => left.startDate - right.startDate || right.score - left.score);
}

/** Group into month buckets for the scrollable timeline. */
function groupByMonth(events) {
  const buckets = new Map();
  for (const event of events) {
    const key = `${event.startDate.getFullYear()}-${event.startDate.getMonth()}`;
    if (!buckets.has(key)) {
      buckets.set(key, {
        key,
        label: `${MONTH_NAMES[event.startDate.getMonth()]} ${event.startDate.getFullYear()}`,
        events: [],
      });
    }
    buckets.get(key).events.push(event);
  }
  return [...buckets.values()];
}

/** "Sat, Sep 5 at 8:49 PM" - what you actually need to plan an evening. */
function absoluteLabel(date) {
  if (!date) return "";
  const day = date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  return `${day} at ${clockLabel(date)}`;
}

/** "8:49 PM". */
function clockLabel(date) {
  return date ? date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
}

/** "1h 36m", or "" once the moment has passed. */
function remainingLabel(now, end) {
  if (!end) return "";
  const minutes = Math.round((end - now) / 60000);
  if (minutes <= 0) return "";
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${String(minutes % 60).padStart(2, "0")}m` : `${minutes}m`;
}

// What actually closes an astro window. "Ends at 22:36" and "the core sets at
// 22:36" are the same time and completely different instructions - the first
// sounds arbitrary, the second tells you to be set up by 21:00.
const WINDOW_LIMIT_REASON = Object.freeze({
  target: "before the core sets",
  dawn: "until dawn",
  moonrise: "before the moon rises",
});

// The organisations that actually count these animals, by hostname. Shown as
// names rather than URLs, because "NOAA Fisheries" tells you whether to trust
// the link and "fisheries.noaa.gov/west-coast/science-data/..." does not.
const SOURCE_LABELS = Object.freeze({
  "whalesafe.com": "Whale Safe (daily acoustic + visual rating)",
  "fisheries.noaa.gov": "NOAA Fisheries",
  "pacificwhale.org": "Pacific Whale Foundation sightings",
  "wildlife.ca.gov": "California Fish and Wildlife",
  "keepbearswild.org": "Bear Tracker sightings",
  "tahoebears.org": "Tahoe Interagency Bear Team",
  "theodorepayne.org": "Theodore Payne wildflower hotline",
  "californiafallcolor.com": "California Fall Color",
  "westernmonarchcount.org": "Western Monarch Count",
  "nps.gov": "National Park Service",
  "ebird.org": "eBird regional bar charts",
});

/** A readable name for a verification source. */
function sourceLabel(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    return SOURCE_LABELS[host] || host;
  } catch (error) {
    return url;
  }
}

/** First entity whose id starts with a domain and contains a marker. */
function findEntity(hass, domain, marker) {
  if (!hass?.states) return "";
  return Object.keys(hass.states).find((id) => id.startsWith(domain) && id.includes(marker)) || "";
}

/** "1-14 Mar", or "Mar 3" when a window is a single day. */
function rangeLabel(start, end) {
  if (!end || Math.abs(end - start) < 86400000) {
    return start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  const sameMonth = start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear();
  const left = start.toLocaleDateString(undefined, sameMonth ? { day: "numeric" } : { month: "short", day: "numeric" });
  const right = end.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${left} - ${right}`;
}

const DEFAULT_CONFIG = Object.freeze({
  title: "Photography Events",
  // "timeline" keeps the original browser-computed view. The other two read
  // the photography_events integration's entities instead.
  mode: MODE_TIMELINE,
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
    const backendMode = BACKEND_MODES.has(cfg.mode);
    this.shadowRoot.innerHTML = `
      <style>
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
            <option value="${MODE_TIMELINE}" ${cfg.mode === MODE_TIMELINE ? "selected" : ""}>Timeline (computed here)</option>
            <option value="${MODE_HERO}" ${cfg.mode === MODE_HERO ? "selected" : ""}>Drop everything (hero)</option>
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
        <div class="title">${hero ? "Drop-everything sensor" : "Planning sensor"}</div>
        <div class="hint">Leave as auto-detect unless you run more than one Photography Events entry.</div>
        <div class="row"><span class="label">Entity</span>
          ${hero
            ? `<select data-select="hero_entity">${this._entityOptionsHtml("binary_sensor.", "action_opportunity", cfg.hero_entity)}</select>`
            : `<select data-select="outlook_entity">${this._entityOptionsHtml("sensor.", "planning_outlook", cfg.outlook_entity)}</select>`}
        </div>
      </div>

      ${hero ? `
        <div class="section">
          <div class="title">Hero</div>
          ${this._toggleRow("show_gear", "Show the gear recommendation")}
          <div class="hint">This card renders nothing at all while the sensor is off.</div>
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
    return BACKEND_MODES.has(this._config?.mode);
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
    this._root.innerHTML = html;
    this._bindEvents();
  }

  /**
   * Toggle chips are rendered as real buttons carrying their entity id, and
   * wired up here after each DOM write. No inline handlers: they would break
   * under a strict Content-Security-Policy, which several people run.
   */
  _bindEvents() {
    if (!this._root) return;
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
        if (this._expanded.has(key)) this._expanded.delete(key);
        else this._expanded.add(key);
        this._render();
      });
    }
  }

  _setHidden(hidden) {
    if (this.style) this.style.display = hidden ? "none" : "";
  }

  _loadingHtml(label) {
    return `<div class="loading"><span class="spinner"></span><span>${escapeHtml(label)}</span></div>`;
  }

  _bodyHtml() {
    if (this._config.mode === MODE_HERO) return this._heroHtml();
    if (this._config.mode === MODE_OUTLOOK) return this._outlookHtml();
    if (this._buildError) {
      return `<div class="empty-card"><ha-icon icon="mdi:map-marker-off-outline"></ha-icon><strong>${escapeHtml(this._buildError)}</strong></div>`;
    }
    if (!this._events) return this._loadingHtml("Calculating photography events");

    const now = new Date();
    const subtitle = this._config.location_name
      ? escapeHtml(this._config.location_name)
      : "Your Home Assistant location";

    return `
      <div class="header">
        <div class="header-title">${escapeHtml(this._config.title)}</div>
        <div class="header-subtitle">${subtitle}</div>
      </div>
      ${this._alertHtml(now)}
      ${this._snapshotHtml(now)}
      ${this._events.length ? this._timelineHtml(now) : this._emptyTimelineHtml()}
      ${this._timelineLegendHtml()}
      ${this._footerHtml()}
    `;
  }

  /**
   * A top-of-card callout for the rare stuff worth reorganising an evening
   * around: a sky forecast to actually catch fire, or a headline sky event
   * happening imminently. Deliberately capped at one banner - if everything
   * shouts, nothing does.
   */
  _alertHtml(now) {
    const horizon = new Date(now.getTime() + 36 * 3600000);
    const candidates = this._events.filter((event) => event.time <= horizon &&
      (event.quality === "epic" || (event.category === "eclipse" && event.quality === "excellent")));
    if (!candidates.length) return "";

    const alert = candidates.reduce((best, event) => {
      const rank = QUALITY_RANK[event.quality] ?? -1;
      return !best || rank > (QUALITY_RANK[best.quality] ?? -1) ? event : best;
    }, null);

    return `
      <div class="alert">
        <ha-icon icon="${alert.icon}"></ha-icon>
        <div class="alert-body">
          <div class="alert-title">${escapeHtml(alert.title)} · ${relativeLabel(now, alert.time)}</div>
          <div class="alert-detail">${escapeHtml(alert.badge || alert.detail)}</div>
        </div>
      </div>
    `;
  }

  _snapshotHtml(now) {
    const buckets = [
      { label: "Next 24h", hours: 24 },
      { label: "Next 48h", hours: 48 },
      { label: "Next 72h", hours: 72 },
    ];
    const tiles = buckets.map(({ label, hours }) => {
      const cutoff = new Date(now.getTime() + hours * 3600000);
      const inBucket = this._events.filter((event) => event.time >= now && event.time <= cutoff);
      let best = null;
      for (const event of inBucket) {
        const rank = QUALITY_RANK[event.quality] ?? -1;
        if (!best || rank > (QUALITY_RANK[best.quality] ?? -1)) best = event;
      }
      return `
        <div class="snapshot-tile">
          <div class="snapshot-label">${label}</div>
          <div class="snapshot-count">${inBucket.length}</div>
          <div class="snapshot-detail">${best ? escapeHtml(best.title) : "Nothing notable yet"}</div>
        </div>
      `;
    }).join("");
    return `<div class="snapshot-strip">${tiles}</div>`;
  }

  _emptyTimelineHtml() {
    return `
      <div class="empty-card">
        <ha-icon icon="mdi:weather-night-partly-cloudy"></ha-icon>
        <strong>No notable photography events</strong>
        <span>Nothing stands out in the next ${this._config.outlook_days} days for the event types you've enabled.</span>
      </div>
    `;
  }

  _timelineHtml(now) {
    const groups = [];
    let currentKey = null;
    for (const event of this._events) {
      const key = startOfDay(event.time).toDateString();
      if (key !== currentKey) {
        groups.push({ key, date: event.time, items: [] });
        currentKey = key;
      }
      groups[groups.length - 1].items.push(event);
    }

    return `
      <div class="timeline">
        ${groups.map((group) => `
          <div class="day-group">
            <div class="day-header">${dayHeaderLabel(group.date, now)}</div>
            ${group.items.map((event) => this._eventRowHtml(event, now)).join("")}
          </div>
        `).join("")}
      </div>
    `;
  }

  _eventRowHtml(event, now) {
    const qualityClass = event.quality ? ` quality-${event.quality}` : "";
    return `
      <article class="event-row${qualityClass}">
        <ha-icon class="event-icon" icon="${event.icon}"></ha-icon>
        <div class="event-body">
          <div class="event-top">
            <span class="event-title">${escapeHtml(event.title)}</span>
            <span class="event-when">${relativeLabel(now, event.time)}</span>
          </div>
          ${event.detail ? `<div class="event-detail">${escapeHtml(event.detail)}</div>` : ""}
          ${event.badge ? `<span class="event-badge">${escapeHtml(event.badge)}</span>` : ""}
        </div>
      </article>
    `;
  }

  _footerHtml() {
    const notes = [];
    if (this._weatherMissing) {
      notes.push("The configured weather entity was not found, so sky-quality scoring is unavailable.");
    } else if (!this._config.weather_entity) {
      notes.push("Add a weather entity in the card editor to score sunset/sunrise color potential.");
    }
    notes.push("Meteor shower, eclipse, and migration data are approximate - verify close to the date.");
    return `<div class="footer">${notes.map((note) => `<div>${escapeHtml(note)}</div>`).join("")}</div>`;
  }


  // --- action_hero ----------------------------------------------------------

  /**
   * The drop-everything card. Returns null - not empty markup - when there is
   * nothing worth driving to, which is how it stays completely invisible.
   */
  _heroHtml() {
    const entityId = this._heroEntityId();
    if (!entityId) {
      return this._setupHtml(
        "No drop-everything sensor found",
        "Install the Photography Events integration, or set <code>hero_entity</code> to its binary sensor."
      );
    }
    const state = this._hass.states[entityId];
    if (!state) {
      return this._setupHtml("Sensor unavailable", `<code>${escapeHtml(entityId)}</code> is not in Home Assistant.`);
    }

    const hero = heroFromState(state);
    if (!hero) return null;

    const now = new Date();
    const meta = CATEGORY_META[hero.category] || { label: hero.category, icon: "mdi:camera" };
    const attributes = state.attributes || {};
    const gear = [
      ["Glass", hero.gear.glass],
      ["Support", hero.gear.support],
      ["Settings", hero.gear.settings],
    ].filter(([, value]) => value);

    return `
      <div class="hero">
        <div class="hero-flag">
          <span class="hero-pulse"></span>
          <span>Drop everything</span>
        </div>

        <div class="hero-title">${escapeHtml(hero.name)}</div>
        <div class="hero-when">Starts ${escapeHtml(absoluteLabel(hero.starts) || "shortly")}</div>
        ${hero.zone ? `<div class="hero-zone"><ha-icon icon="mdi:map-marker"></ha-icon>${escapeHtml(hero.zone)}</div>` : ""}

        ${this._heroWindowHtml(hero, attributes, now)}

        <div class="hero-stats">
          <div class="hero-stat">
            <div class="hero-stat-label">Drive</div>
            <div class="hero-stat-value">${escapeHtml(driveLabel(hero.driveMinutes))}</div>
            <div class="hero-stat-note ${hero.drive.routed ? "routed" : ""}" title="${escapeHtml(hero.drive.detail)}">
              ${hero.drive.routed ? `<ha-icon icon="mdi:car-clock"></ha-icon>` : ""}${escapeHtml(hero.drive.note)}
            </div>
          </div>
          <div class="hero-stat">
            <div class="hero-stat-label">Confidence</div>
            <div class="hero-stat-value">${hero.score}<span class="hero-stat-unit">/100</span></div>
            <div class="hero-meter"><span style="width:${clamp(hero.score, 0, 100)}%"></span></div>
          </div>
          <div class="hero-stat">
            <div class="hero-stat-label">Type</div>
            <div class="hero-stat-value small">
              <ha-icon icon="${meta.icon}"></ha-icon>${escapeHtml(meta.label)}
            </div>
          </div>
        </div>

        ${hero.summary ? `<div class="hero-summary">${escapeHtml(hero.summary)}</div>` : ""}

        ${this._config.show_gear && gear.length ? `
          <div class="hero-gear">
            <div class="hero-gear-head"><ha-icon icon="mdi:camera-iris"></ha-icon>Take</div>
            ${gear.map(([label, value]) => `
              <div class="hero-gear-row">
                <span class="hero-gear-label">${label}</span>
                <span class="hero-gear-value">${escapeHtml(value)}</span>
              </div>`).join("")}
          </div>` : ""}

        ${hero.sourceUrl ? `
          <a class="hero-link" href="${escapeHtml(hero.sourceUrl)}" target="_blank" rel="noopener noreferrer">
            <ha-icon icon="mdi:open-in-new"></ha-icon>Check the original report
          </a>` : ""}

        ${this._activeMonthHtml(now)}
      </div>
    `;
  }

  /**
   * The window, spelled out. A start time alone does not tell you whether you
   * have four hours or forty minutes, and for astro that is the whole decision.
   */
  _heroWindowHtml(hero, attributes, now) {
    if (!hero.starts || !hero.ends) return "";
    const duration = Number(attributes.duration_minutes) || 0;
    const limit = WINDOW_LIMIT_REASON[attributes.limited_by] || "";
    const remaining = hero.ends > now ? remainingLabel(now, hero.ends) : "";

    const parts = [];
    if (duration) parts.push(`${duration} min`);
    if (remaining && limit) parts.push(`${remaining} remaining ${limit}`);
    else if (remaining) parts.push(`${remaining} remaining`);
    else if (limit) parts.push(limit.replace(/^before /, "closes before "));

    return `
      <div class="hero-window">
        <ha-icon icon="mdi:clock-outline"></ha-icon>
        <span class="hero-window-range">${escapeHtml(clockLabel(hero.starts))} to ${escapeHtml(clockLabel(hero.ends))}</span>
        ${parts.length ? `<span class="hero-window-note">(${escapeHtml(parts.join(", "))})</span>` : ""}
      </div>
    `;
  }

  /**
   * What else is running right now. The hero answers "tonight"; this answers
   * "and while you are out there", which is how one drive becomes two subjects.
   */
  _activeMonthHtml(now) {
    const state = this._hass.states[this._outlookEntityId()];
    if (!state) return "";
    const outlook = outlookFromState(state);
    const running = outlook.events
      .filter((event) => event.precision === "peak")
      .map((event) => ({ ...event, startDate: parseEventDate(event.start), endDate: parseEventDate(event.end) }))
      .filter((event) => event.startDate && event.endDate && event.startDate <= now && event.endDate >= now)
      .sort((left, right) => right.score - left.score)
      .slice(0, 2);
    if (!running.length) return "";

    return `
      <div class="hero-active">
        <span class="hero-active-label">Also peaking now</span>
        ${running.map((event) => `<span class="hero-active-item">${escapeHtml(event.title)}</span>`).join("")}
      </div>
    `;
  }

  // --- calendar_outlook -----------------------------------------------------

  /** The year-ahead planning view, filtered by the toggle chips. */
  _outlookHtml() {
    const entityId = this._outlookEntityId();
    if (!entityId) {
      return this._setupHtml(
        "No planning sensor found",
        "Install the Photography Events integration, or set <code>outlook_entity</code> to its planning outlook sensor."
      );
    }
    const state = this._hass.states[entityId];
    if (!state) {
      return this._setupHtml("Sensor unavailable", `<code>${escapeHtml(entityId)}</code> is not in Home Assistant.`);
    }

    const outlook = outlookFromState(state);
    const now = new Date();
    const known = outlook.categories.length ? outlook.categories : Object.keys(CATEGORY_META);
    // Filters live in the card, not in Home Assistant. Making somebody create
    // eight input_boolean helpers before they can hide a category is a lot of
    // setup for a view preference that never needed to leave the browser.
    if (this._activeFilters === null) this._activeFilters = new Set(known);
    const allowed = this._activeFilters;

    const events = filterOutlook(outlook.events, {
      allowed,
      now,
      fromDays: this._config.outlook_from_days,
      throughDays: this._config.outlook_through_days,
    });
    const months = groupByMonth(events);

    return `
      <div class="header">
        <div class="header-title">${escapeHtml(this._config.title)}</div>
        <div class="header-subtitle">
          ${events.length} of ${outlook.events.length} events, next ${this._config.outlook_through_days} days
          ${outlook.truncated ? " (list truncated)" : ""}
        </div>
      </div>
      ${this._filterChipsHtml(known, allowed)}
      ${months.length
        ? `<div class="outlook">${months.map((month) => this._monthHtml(month, outlook, now)).join("")}</div>`
        : `<div class="empty-card">
             <ha-icon icon="mdi:calendar-blank-outline"></ha-icon>
             <strong>Nothing in this window</strong>
             <span>Every category may be switched off, or the range may be too narrow.</span>
           </div>`}
      ${this._legendHtml()}
    `;
  }

  _filterChipsHtml(known, allowed) {
    const chips = known.map((category) => {
      const meta = CATEGORY_META[category] || { label: category, icon: "mdi:camera" };
      const on = allowed.has(category);
      return `<button type="button" class="pe-chip ${on ? "on" : "off"}" data-category="${escapeHtml(category)}"
                aria-pressed="${on}">
                <ha-icon icon="${meta.icon}"></ha-icon>${escapeHtml(meta.label)}
              </button>`;
    });
    return `<div class="pe-chips">${chips.join("")}</div>`;
  }

  _monthHtml(month, outlook, now) {
    return `
      <div class="outlook-month">
        <div class="outlook-month-label">${escapeHtml(month.label)}</div>
        ${month.events.map((event) => this._outlookRowHtml(event, outlook, now)).join("")}
      </div>
    `;
  }

  /**
   * The badge replaces a coloured bar down the side of the row. A bar encodes
   * a number nobody can read off it; if the score is worth showing at all it is
   * worth showing as a number.
   */
  _scoreBadgeHtml(event) {
    if (event.precision === "season") {
      return `<span class="outlook-badge season">Season</span>`;
    }
    if (event.tier === "optimal") {
      return `<span class="outlook-badge peak">Best window</span>`;
    }
    const tone = event.score >= 90 ? "high" : event.score >= 75 ? "good" : "fair";
    return `<span class="outlook-badge ${tone}">${event.score}% score</span>`;
  }

  _outlookRowHtml(event, outlook, now) {
    const meta = CATEGORY_META[event.category] || { label: event.category, icon: "mdi:camera" };
    const park = event.planning_only ? outlook.parks[event.zone_id] : null;
    const dog = park ? DOG_META[park.dogs] : null;
    const drive = park ? park.drive_label : driveLabel(Math.round((event.drive_hours || 0) * 60));
    const expanded = this._expanded.has(event.key);

    return `
      <div class="outlook-row ${expanded ? "open" : ""}">
        <button type="button" class="outlook-head" data-expand="${escapeHtml(event.key)}"
          aria-expanded="${expanded}">
          <span class="outlook-when">${escapeHtml(rangeLabel(event.startDate, event.endDate))}</span>
          <span class="outlook-body">
            <span class="outlook-title">${escapeHtml(event.title)}</span>
            <span class="outlook-meta">
              <span class="outlook-tag"><ha-icon icon="${meta.icon}"></ha-icon>${escapeHtml(meta.label)}</span>
              ${drive ? `<span class="outlook-tag"><ha-icon icon="mdi:car"></ha-icon>${escapeHtml(drive)}</span>` : ""}
              ${dog ? `<span class="outlook-tag dog-${dog.tone}" title="${escapeHtml(park.dog_detail)}">
                         <ha-icon icon="${dog.icon}"></ha-icon>${escapeHtml(park.dog_label || dog.label)}
                       </span>` : ""}
            </span>
          </span>
          ${this._scoreBadgeHtml(event)}
          <ha-icon class="outlook-chevron" icon="${expanded ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon>
        </button>
        ${expanded ? this._outlookDetailHtml(event, outlook, park, now) : ""}
      </div>
    `;
  }

  _outlookDetailHtml(event, outlook, park, now) {
    const rows = [];

    if (event.precision === "season") {
      rows.push(["Extended season", event.season_range || "-"]);
      rows.push(["Peak window", `${rangeLabel(event.startDate, event.endDate)} - specifics firm up inside 30 days`]);
    } else {
      rows.push(["Peak window", rangeLabel(event.startDate, event.endDate)]);
      if (event.season_range) rows.push(["Extended season", event.season_range]);
    }
    if (event.duration_minutes) {
      const limit = WINDOW_LIMIT_REASON[event.limited_by] || "";
      rows.push(["Usable window", `${event.duration_minutes} min${limit ? ` - ${limit}` : ""}`]);
    }
    if (event.best_time_of_day) rows.push(["Best time of day", event.best_time_of_day]);

    const locations = event.locations || (park ? [park.name] : []);
    if (locations.length) rows.push(["Where", locations.join(" - ")]);

    const gear = event.gear || outlook.gear?.[event.category]?.glass;
    if (gear) rows.push(["Gear", gear]);
    const support = outlook.gear?.[event.category]?.support;
    if (support && !event.gear) rows.push(["Support", support]);

    if (park) rows.push(["Dogs", park.dog_detail]);

    const why = event.tips || event.detail
      || (event.reasons || []).join(", ")
      || "Scored from the season table; no live signal for this one yet.";

    return `
      <div class="outlook-detail">
        <dl class="outlook-detail-grid">
          ${rows.map(([label, value]) => `
            <dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}
        </dl>
        <div class="outlook-why">
          <span class="outlook-why-label">Why this score</span>
          ${escapeHtml(why)}
          ${event.confirm ? `<em> Timing shifts year to year - confirm current reports before driving.</em>` : ""}
        </div>
        ${event.source_url ? `
          <a class="outlook-source" href="${escapeHtml(event.source_url)}" target="_blank" rel="noopener noreferrer">
            <ha-icon icon="mdi:open-in-new"></ha-icon>Original report
          </a>` : ""}
        ${Array.isArray(event.verify) && event.verify.length ? `
          <div class="outlook-verify">
            <span class="outlook-verify-label">Check before you book</span>
            ${event.verify.map((url) => `
              <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">
                <ha-icon icon="mdi:check-decagram-outline"></ha-icon>${escapeHtml(sourceLabel(url))}
              </a>`).join("")}
          </div>` : ""}
      </div>
    `;
  }

  _legendHtml() {
    const items = [
      ["high", "90+ drop everything"],
      ["good", "75-89 worth the drive"],
      ["fair", "60-74 keep an eye on it"],
      ["season", "background season, not yet actionable"],
    ];
    return `
      <div class="pe-legend">
        ${items.map(([tone, label]) => `
          <span class="pe-legend-item">
            <span class="outlook-badge ${tone} tiny"></span>${escapeHtml(label)}
          </span>`).join("")}
      </div>
    `;
  }

  /** What the colours mean, and what is deliberately not shown. */
  _timelineLegendHtml() {
    const tiers = [
      ["epic", "Epic - drop everything"],
      ["excellent", "Excellent"],
      ["good", "Good"],
      ["fair", "Fair"],
    ];
    return `
      <div class="pe-legend">
        ${tiers.map(([tier, label]) => `
          <span class="pe-legend-item">
            <span class="pe-legend-dot ${tier}"></span>${escapeHtml(label)}
          </span>`).join("")}
        ${this._config.hide_routine === false ? "" : `
          <span class="pe-legend-note">
            Ordinary golden hours, lunar quarters and eclipses that miss this location are hidden.
            ${this._config.weather_entity
              ? ""
              : "Set a weather entity to score sunsets - without a forecast none can clear the bar."}
          </span>`}
      </div>
    `;
  }

  _setupHtml(title, message) {
    return `
      <div class="empty-card">
        <ha-icon icon="mdi:cog-outline"></ha-icon>
        <strong>${escapeHtml(title)}</strong>
        <span>${message}</span>
      </div>
    `;
  }

  _styles() {
    return `
      :host {
        --pe-surface: var(--ha-card-background, var(--card-background-color, #1d1d1f));
        --pe-text: var(--primary-text-color, #f5f5f7);
        --pe-muted: var(--secondary-text-color, rgba(235, 235, 245, .60));
        --pe-border: var(--divider-color, rgba(255, 255, 255, .18));
        --pe-epic: #ff8a3d;
        --pe-excellent: #85d481;
        --pe-good: #66a7ff;
        --pe-fair: #e8b15e;
        --pe-poor: #ef7064;
        display: block;
        color: var(--pe-text);
        font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
      }
      * { box-sizing: border-box; }
      ha-card {
        overflow: hidden;
        border: 1px solid var(--pe-border);
        border-radius: var(--ha-card-border-radius, 28px);
        background:
          radial-gradient(circle at 15% 0%, rgba(102, 167, 255, .10), transparent 40%),
          radial-gradient(circle at 85% 100%, rgba(133, 212, 129, .08), transparent 40%),
          var(--pe-surface);
        box-shadow: var(--ha-card-box-shadow, 0 10px 30px rgba(0, 0, 0, .22));
      }
      .card-content { padding: clamp(18px, 3vw, 26px); }
      .header { margin-bottom: 14px; }
      .header-title { font-size: 19px; font-weight: 800; }
      .header-subtitle { color: var(--pe-muted); font-size: 12px; }
      .alert {
        display: flex; align-items: center; gap: 12px; margin-bottom: 14px; padding: 12px 14px;
        border: 1px solid rgba(255, 138, 61, .45); border-radius: 16px;
        background: linear-gradient(120deg, rgba(255, 138, 61, .22), rgba(255, 138, 61, .06));
      }
      .alert ha-icon { flex: 0 0 auto; color: var(--pe-epic); --mdc-icon-size: 26px; }
      .alert-body { min-width: 0; }
      .alert-title { font-size: 15px; font-weight: 800; }
      .alert-detail { margin-top: 2px; color: var(--pe-muted); font-size: 12px; line-height: 1.4; }
      .snapshot-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
      .snapshot-tile {
        min-width: 0; padding: 10px 11px; border: 1px solid var(--pe-border); border-radius: 14px;
        background: rgba(255, 255, 255, .04);
      }
      .snapshot-label { color: var(--pe-muted); font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
      .snapshot-count { margin: 2px 0; font-size: 20px; font-weight: 800; }
      .snapshot-detail { overflow: hidden; color: var(--pe-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
      .day-group { margin-bottom: 14px; }
      .day-group:last-child { margin-bottom: 0; }
      .day-header {
        margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid color-mix(in srgb, var(--pe-border) 60%, transparent);
        color: var(--pe-muted); font-size: 11px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
      }
      .event-row {
        display: flex; gap: 10px; padding: 9px 3px; border-left: 3px solid transparent;
      }
      .event-row.quality-epic {
        border-left-color: var(--pe-epic);
        border-radius: 0 12px 12px 0;
        background: linear-gradient(90deg, rgba(255, 138, 61, .16), transparent 65%);
      }
      .event-row.quality-epic .event-icon { color: var(--pe-epic); }
      .event-row.quality-epic .event-badge {
        background: rgba(255, 138, 61, .22);
        color: #ffd7bb;
      }
      .event-row.quality-excellent { border-left-color: var(--pe-excellent); }
      .event-row.quality-good { border-left-color: var(--pe-good); }
      .event-row.quality-fair { border-left-color: var(--pe-fair); }
      .event-row.quality-poor { border-left-color: var(--pe-poor); }
      .event-icon { flex: 0 0 auto; margin-top: 1px; color: var(--pe-muted); --mdc-icon-size: 20px; }
      .event-body { min-width: 0; flex: 1; }
      .event-top { display: flex; align-items: baseline; gap: 8px; }
      .event-title { flex: 1; font-size: 14px; font-weight: 700; }
      .event-when { flex: 0 0 auto; color: var(--pe-muted); font-size: 11px; }
      .event-detail { margin-top: 2px; color: var(--pe-muted); font-size: 12px; line-height: 1.4; }
      .event-badge {
        display: inline-block; margin-top: 5px; padding: 2px 9px; border-radius: 999px;
        background: rgba(255, 255, 255, .08); color: var(--pe-text); font-size: 10.5px; font-weight: 600;
      }
      .footer { margin-top: 14px; padding-top: 10px; border-top: 1px solid color-mix(in srgb, var(--pe-border) 50%, transparent); color: var(--pe-muted); font-size: 10.5px; line-height: 1.5; }
      .empty-card, .loading {
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
        min-height: 130px; color: var(--pe-muted); font-size: 13px; text-align: center;
      }
      .empty-card ha-icon { --mdc-icon-size: 32px; }
      .empty-card strong { color: var(--pe-text); }
      .spinner {
        display: inline-block; width: 20px; height: 20px; border: 2px solid rgba(255, 255, 255, .22);
        border-top-color: var(--pe-text); border-radius: 50%; animation: pe-spin .75s linear infinite;
      }
      @keyframes pe-spin { to { transform: rotate(360deg); } }
      /* --- action_hero ---------------------------------------------------
         Loud on purpose. This card exists to interrupt whatever you were
         doing, and it is invisible the rest of the time, so it can afford to
         shout when it does appear. */
      .hero {
        position: relative;
        border-radius: 14px;
        padding: 16px;
        background:
          radial-gradient(120% 140% at 0% 0%, rgba(255, 138, 61, .22), transparent 58%),
          linear-gradient(160deg, rgba(255, 138, 61, .12), rgba(255, 138, 61, .03));
        border: 1px solid rgba(255, 138, 61, .45);
      }
      .hero-flag {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .14em;
        text-transform: uppercase;
        color: var(--pe-epic);
      }
      .hero-when { margin-left: auto; letter-spacing: .04em; color: var(--pe-muted); font-weight: 600; }
      .hero-pulse {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--pe-epic);
        box-shadow: 0 0 0 0 rgba(255, 138, 61, .7);
        animation: pe-pulse 2.4s ease-out infinite;
      }
      @keyframes pe-pulse {
        70% { box-shadow: 0 0 0 10px rgba(255, 138, 61, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 138, 61, 0); }
      }
      .hero-title {
        margin-top: 10px;
        font-size: 24px;
        font-weight: 700;
        line-height: 1.15;
        letter-spacing: -.01em;
      }
      .hero-zone {
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 6px;
        color: var(--pe-muted);
        font-size: 13px;
      }
      .hero-zone ha-icon { --mdc-icon-size: 16px; }
      .hero-stats {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-top: 14px;
      }
      .hero-stat {
        background: rgba(255, 255, 255, .06);
        border: 1px solid var(--pe-border);
        border-radius: 10px;
        padding: 10px;
      }
      .hero-stat-label {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: .1em;
        color: var(--pe-muted);
      }
      .hero-stat-value { margin-top: 4px; font-size: 21px; font-weight: 700; }
      .hero-stat-value.small { font-size: 14px; display: flex; align-items: center; gap: 5px; }
      .hero-stat-value.small ha-icon { --mdc-icon-size: 16px; color: var(--pe-muted); }
      .hero-stat-unit { font-size: 12px; font-weight: 500; color: var(--pe-muted); }
      .hero-stat-note {
        display: flex;
        align-items: center;
        gap: 3px;
        margin-top: 3px;
        font-size: 11px;
        color: var(--pe-muted);
      }
      .hero-stat-note.routed { color: var(--pe-excellent); }
      .hero-stat-note ha-icon { --mdc-icon-size: 13px; }
      .hero-meter {
        margin-top: 6px;
        height: 4px;
        border-radius: 2px;
        background: rgba(255, 255, 255, .14);
        overflow: hidden;
      }
      .hero-meter span { display: block; height: 100%; background: var(--pe-epic); }
      .hero-summary { margin-top: 12px; font-size: 13px; line-height: 1.5; color: var(--pe-text); }
      .hero-reasons { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
      .hero-reasons span {
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(255, 255, 255, .08);
        color: var(--pe-muted);
      }
      .hero-gear {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid var(--pe-border);
      }
      .hero-gear-head {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .1em;
        text-transform: uppercase;
        color: var(--pe-muted);
        margin-bottom: 8px;
      }
      .hero-gear-head ha-icon { --mdc-icon-size: 15px; }
      .hero-gear-row { display: flex; gap: 10px; font-size: 12.5px; line-height: 1.5; }
      .hero-gear-row + .hero-gear-row { margin-top: 4px; }
      .hero-gear-label { flex: 0 0 62px; color: var(--pe-muted); }
      .hero-gear-value { flex: 1; }
      .hero-link {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        margin-top: 12px;
        font-size: 12.5px;
        color: var(--pe-epic);
        text-decoration: none;
      }
      .hero-link ha-icon { --mdc-icon-size: 15px; }

      /* --- calendar_outlook ------------------------------------------------ */
      .pe-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 4px; }
      .pe-chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font: inherit;
        font-size: 12px;
        padding: 5px 10px;
        border-radius: 999px;
        border: 1px solid var(--pe-border);
        background: rgba(255, 255, 255, .05);
        color: var(--pe-muted);
        cursor: pointer;
        transition: background .15s ease, color .15s ease, border-color .15s ease;
      }
      .pe-chip ha-icon { --mdc-icon-size: 15px; }
      .pe-chip.on { background: rgba(133, 212, 129, .16); border-color: rgba(133, 212, 129, .5); color: var(--pe-text); }
      .pe-chip.off { opacity: .5; }
      .pe-chip.static { cursor: default; opacity: .75; }
      .pe-chip:focus-visible { outline: 2px solid var(--pe-epic); outline-offset: 2px; }

      .outlook { max-height: 560px; overflow-y: auto; margin-top: 8px; padding-right: 4px; }
      .outlook-month + .outlook-month { margin-top: 14px; }
      .outlook-month-label {
        position: sticky;
        top: 0;
        z-index: 2;
        padding: 6px 0;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
        color: var(--pe-muted);
        background: var(--pe-surface);
      }
      .outlook-row {
        display: flex;
        align-items: stretch;
        gap: 10px;
        padding: 9px 0;
        border-top: 1px solid var(--pe-border);
      }
      .outlook-when {
        flex: 0 0 88px;
        font-size: 12px;
        font-variant-numeric: tabular-nums;
        color: var(--pe-muted);
        padding-top: 1px;
      }
      .outlook-row.optimal .outlook-when { color: var(--pe-excellent); font-weight: 600; }
      .outlook-body { flex: 1; min-width: 0; }
      .outlook-title { font-size: 13.5px; font-weight: 600; line-height: 1.3; }
      .outlook-meta { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
      .outlook-tag {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 11px;
        padding: 2px 7px;
        border-radius: 999px;
        background: rgba(255, 255, 255, .07);
        color: var(--pe-muted);
      }
      .outlook-tag ha-icon { --mdc-icon-size: 13px; }
      .outlook-tag.best { background: rgba(133, 212, 129, .18); color: var(--pe-excellent); }
      .outlook-tag.dog-yes { background: rgba(16, 185, 129, .16); color: #34d399; }
      .outlook-tag.dog-part { background: rgba(234, 179, 8, .16); color: #eab308; }
      .outlook-tag.dog-no { background: rgba(244, 63, 94, .16); color: #fb7185; }
      .outlook-detail { margin-top: 5px; font-size: 12px; line-height: 1.45; color: var(--pe-muted); }

      @media (prefers-reduced-motion: reduce) {
        .hero-pulse { animation: none; }
      }

      .hero-when {
        margin-top: 6px;
        font-size: 13.5px;
        font-weight: 600;
        color: var(--pe-epic);
      }
      .hero-window {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 12px;
        padding: 9px 11px;
        border-radius: 9px;
        background: rgba(255, 255, 255, .07);
        border: 1px solid var(--pe-border);
        font-size: 13px;
      }
      .hero-window ha-icon { --mdc-icon-size: 16px; color: var(--pe-muted); align-self: center; }
      .hero-window-range { font-weight: 700; font-variant-numeric: tabular-nums; }
      .hero-window-note { color: var(--pe-muted); font-size: 12px; }
      .hero-active {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 6px;
        margin-top: 14px;
        padding-top: 11px;
        border-top: 1px solid var(--pe-border);
        font-size: 12px;
      }
      .hero-active-label {
        text-transform: uppercase;
        letter-spacing: .09em;
        font-size: 10px;
        font-weight: 700;
        color: var(--pe-muted);
      }
      .hero-active-item {
        padding: 2px 8px;
        border-radius: 999px;
        background: rgba(255, 255, 255, .08);
        color: var(--pe-text);
      }

      .outlook-head {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        width: 100%;
        padding: 9px 0;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }
      .outlook-head:focus-visible { outline: 2px solid var(--pe-epic); outline-offset: 2px; border-radius: 6px; }
      .outlook-row.open { background: rgba(255, 255, 255, .03); border-radius: 8px; }
      .outlook-chevron { --mdc-icon-size: 18px; color: var(--pe-muted); flex: 0 0 auto; align-self: center; }
      .outlook-badge {
        flex: 0 0 auto;
        align-self: center;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 999px;
        white-space: nowrap;
      }
      .outlook-badge.high { background: rgba(255, 138, 61, .2); color: var(--pe-epic); }
      .outlook-badge.good { background: rgba(133, 212, 129, .2); color: var(--pe-excellent); }
      .outlook-badge.fair { background: rgba(255, 255, 255, .1); color: var(--pe-muted); }
      .outlook-badge.peak { background: rgba(133, 212, 129, .22); color: var(--pe-excellent); }
      .outlook-badge.season { background: rgba(255, 255, 255, .07); color: var(--pe-muted); font-weight: 500; }
      .outlook-badge.tiny { padding: 0; width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

      .outlook-detail { padding: 2px 0 12px 0; }
      .outlook-detail-grid {
        display: grid;
        grid-template-columns: 118px 1fr;
        gap: 4px 12px;
        margin: 0 0 10px;
        font-size: 12.5px;
      }
      .outlook-detail-grid dt { color: var(--pe-muted); }
      .outlook-detail-grid dd { margin: 0; line-height: 1.45; }
      .outlook-why {
        font-size: 12.5px;
        line-height: 1.5;
        padding: 9px 11px;
        border-radius: 8px;
        background: rgba(255, 255, 255, .05);
      }
      .outlook-why-label {
        display: block;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: .09em;
        font-weight: 700;
        color: var(--pe-muted);
        margin-bottom: 4px;
      }
      .outlook-source {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        margin-top: 9px;
        font-size: 12.5px;
        color: var(--pe-epic);
        text-decoration: none;
      }
      .outlook-source ha-icon { --mdc-icon-size: 15px; }

      .outlook-verify {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-top: 10px;
        padding-top: 9px;
        border-top: 1px dashed var(--pe-border);
        font-size: 12px;
      }
      .outlook-verify-label {
        flex-basis: 100%;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: .09em;
        font-weight: 700;
        color: var(--pe-muted);
      }
      .outlook-verify a {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: var(--pe-excellent);
        text-decoration: none;
      }
      .outlook-verify a ha-icon { --mdc-icon-size: 14px; }

      .pe-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 14px;
        padding-top: 11px;
        border-top: 1px solid var(--pe-border);
        font-size: 11px;
        color: var(--pe-muted);
      }
      .pe-legend-item { display: inline-flex; align-items: center; gap: 5px; }
      .pe-legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
      .pe-legend-dot.epic { background: var(--pe-epic); }
      .pe-legend-dot.excellent { background: var(--pe-excellent); }
      .pe-legend-dot.good { background: var(--pe-muted); }
      .pe-legend-dot.fair { background: rgba(255, 255, 255, .25); }
      .pe-legend-note { flex-basis: 100%; opacity: .8; }

      @media (max-width: 600px) {
        .card-content { padding: 16px 12px; }
        .snapshot-strip { gap: 6px; }
        .snapshot-tile { padding: 8px; }
        .snapshot-count { font-size: 17px; }
        .hero-stats { grid-template-columns: 1fr 1fr; }
        .hero-title { font-size: 20px; }
        .outlook-head { flex-wrap: wrap; }
        .outlook-when { flex-basis: 100%; }
        .outlook-detail-grid { grid-template-columns: 1fr; gap: 2px; }
        .outlook-detail-grid dt { margin-top: 6px; font-size: 11px; }
        .outlook { max-height: 420px; }
      }
    `;
  }

  getCardSize() {
    // A hidden hero should not reserve space in a masonry column.
    if (this._config?.mode === MODE_HERO) {
      return this._hass && heroFromState(this._hass.states[this._heroEntityId()]) ? 6 : 1;
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

// Test-only seam: the astronomy math is written as free functions (no `this`
// juggling), so it is exposed here for direct unit testing the same way the
// rest of this repo pokes at underscore-prefixed instance methods.
PhotographyEventsCard.backend = {
  driveLabel,
  driveProvenance,
  parseEventDate,
  heroFromState,
  outlookFromState,
  activeCategories,
  filterOutlook,
  groupByMonth,
  rangeLabel,
  findEntity,
  CATEGORY_META,
  DOG_META,
  MODE_HERO,
  MODE_OUTLOOK,
  MODE_TIMELINE,
};

PhotographyEventsCard.astro = {
  daysSinceJ2000,
  sunEquatorial,
  moonEquatorial,
  horizontalFromEquatorial,
  findAltitudeCrossings,
  moonIllumination,
  moonPhaseInfo,
  buildDayTable,
  buildEvents,
  skyColorQuality,
  meteorQuality,
  planetGeocentric,
  planetElongationDeg,
  planetEvents,
  customSkyEvents,
  angularSeparation,
  PLANETS,
  lunarEclipseVisibility,
  solarEclipseVisibility,
  METEOR_SHOWERS,
  ECLIPSES,
};

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card?.type === "photography-events-card")) {
  window.customCards.push({
    type: "photography-events-card",
    name: "Photography Events Card",
    description: "Upcoming golden hour, moon phases, meteor showers, eclipses, and more near your location",
    preview: true,
    documentationURL: "https://github.com/Tmatz27/Home-assistant-photography-events",
  });
}

try {
  if (!customElements.get("photography-events-card-editor")) {
    customElements.define("photography-events-card-editor", PhotographyEventsCardEditor);
  }
  if (!customElements.get("photography-events-card")) {
    customElements.define("photography-events-card", PhotographyEventsCard);
  }
} catch (error) {
  console.error("Photography Events Card could not register its custom elements", error);
}

console.info(
  `%c Photography Events Card %c v${CARD_VERSION} `,
  "color: white; background: #3a7d5c; font-weight: 700;",
  "color: #3a7d5c; background: transparent;",
);
