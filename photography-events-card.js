/**
 * Photography Events Card for Home Assistant
 * Version 0.1.0
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

const CARD_VERSION = "0.1.0";

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
 * Weather-based sky quality
 * ---------------------------------------------------------------------- */

const SUN_QUALITY_LABELS = {
  excellent: "Good potential for vivid color",
  good: "Decent conditions",
  fair: "Variable - could go either way",
  poor: "Unlikely to produce a colorful sky",
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

function nearestForecast(forecast, targetDate) {
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
  return bestDiff <= 90 * 60000 ? best : null;
}

function sunsetQuality(forecastEntry) {
  if (!forecastEntry) return null;
  const cloud = Number(forecastEntry.cloud_coverage);
  let tier;
  if (Number.isFinite(cloud)) {
    if (cloud > 85) tier = "poor";
    else if (cloud > 65) tier = "good";
    else if (cloud >= 15) tier = "excellent";
    else tier = "fair";
  } else {
    tier = CONDITION_TIER[forecastEntry.condition] || null;
  }
  return tier ? { tier, label: SUN_QUALITY_LABELS[tier] } : null;
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

const QUALITY_RANK = { excellent: 3, good: 2, fair: 1, poor: 0 };

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function fmtTime(date) {
  if (!date) return "—";
  return date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function eveningLightEvent(day, forecast) {
  if (!day.sunset) return null;
  const quality = sunsetQuality(nearestForecast(forecast, day.sunset));
  const parts = [];
  if (day.goldenHourEveningStart) parts.push(`Golden hour from ${fmtTime(day.goldenHourEveningStart)}`);
  parts.push(`Sunset ${fmtTime(day.sunset)}`);
  if (day.blueHourEveningStart && day.civilDusk) {
    parts.push(`blue hour ${fmtTime(day.blueHourEveningStart)}-${fmtTime(day.civilDusk)}`);
  }
  return {
    id: `evening-${day.date.toDateString()}`,
    category: "sun",
    time: day.goldenHourEveningStart || day.sunset,
    relevantUntil: day.civilDusk || day.sunset,
    title: "Evening golden hour",
    detail: parts.join(" · "),
    quality: quality?.tier ?? null,
    badge: quality?.label ?? null,
    icon: "mdi:weather-sunset-down",
  };
}

function morningLightEvent(day, forecast) {
  if (!day.sunrise) return null;
  const quality = sunsetQuality(nearestForecast(forecast, day.sunrise));
  const parts = [];
  if (day.civilDawn && day.blueHourMorningEnd) {
    parts.push(`Blue hour ${fmtTime(day.civilDawn)}-${fmtTime(day.blueHourMorningEnd)}`);
  }
  parts.push(`Sunrise ${fmtTime(day.sunrise)}`);
  if (day.goldenHourMorningEnd) parts.push(`golden hour until ${fmtTime(day.goldenHourMorningEnd)}`);
  return {
    id: `morning-${day.date.toDateString()}`,
    category: "sun",
    time: day.civilDawn || day.sunrise,
    relevantUntil: day.goldenHourMorningEnd || day.sunrise,
    title: "Morning golden hour",
    detail: parts.join(" · "),
    quality: quality?.tier ?? null,
    badge: quality?.label ?? null,
    icon: "mdi:weather-sunset-up",
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
      const nextDay = days[dayIndex + 1];
      if (!day?.astroDusk || !nextDay?.astroDawn) continue;
      const maxAlt = maxAltitudeInWindow(shower.raDeg, shower.decDeg, day.astroDusk, nextDay.astroDawn, latRad, lonRad, 20);
      const quality = meteorQuality(maxAlt, day.moon.fraction);
      events.push({
        id: `meteor-${shower.name}-${year}`,
        category: "meteor",
        time: day.astroDusk,
        relevantUntil: nextDay.astroDawn,
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

function milkyWayEvent(day, nextDay, latRad, lonRad) {
  if (!day.astroDusk || !nextDay?.astroDawn || nextDay.astroDawn <= day.astroDusk) return null;
  const maxAlt = maxAltitudeInWindow(
    GALACTIC_CORE_RA_DEG,
    GALACTIC_CORE_DEC_DEG,
    day.astroDusk,
    nextDay.astroDawn,
    latRad,
    lonRad,
    30,
  );
  if (maxAlt < 15 || day.moon.fraction >= 0.4) return null;
  const tier = maxAlt >= 35 ? "excellent" : "good";
  return {
    id: `milkyway-${day.date.toDateString()}`,
    category: "milkyway",
    time: day.astroDusk,
    relevantUntil: nextDay.astroDawn,
    title: "Milky Way core visible",
    detail: `Galactic core reaches ~${Math.round(maxAlt)}° with a ${Math.round(day.moon.fraction * 100)}%-lit moon. ` +
      `Look south after ${fmtTime(day.astroDusk)}, away from light pollution.`,
    quality: tier,
    badge: tier === "excellent" ? "Great dark-sky night" : "Worth a look",
    icon: "mdi:telescope",
  };
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
    badge,
    icon: "mdi:eclipse",
  };
}

function birdMigrationEvents(latRad, now, rangeStart, rangeEnd) {
  const hemisphere = latRad >= 0 ? "north" : "south";
  const events = [];
  for (const year of new Set([rangeStart.getFullYear(), rangeEnd.getFullYear()])) {
    for (const window of BIRD_MIGRATION_WINDOWS[hemisphere]) {
      const start = new Date(year, window.startMonth - 1, window.startDay);
      const end = new Date(year, window.endMonth - 1, window.endDay, 23, 59, 59);
      if (end < rangeStart || start > rangeEnd) continue;
      events.push({
        id: `birds-${window.label}-${year}`,
        category: "birds",
        time: start < now ? now : start,
        relevantUntil: end,
        title: window.label,
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
      // late-evening event unconditionally too.
      for (const event of [morning, evening]) {
        if (event && (event.time <= nearTermEnd || event.quality === "excellent")) events.push(event);
      }
    }
  }

  if (config.show_moon_events !== false) {
    for (const day of relevantDays) {
      const event = moonDayEvent(day, nearTermEnd);
      if (event) events.push(event);
    }
  }

  if (config.show_meteor_showers !== false) {
    events.push(...meteorShowerEvents(days, latRad, lonRad, todayStart, outlookEnd));
  }

  if (config.show_milky_way !== false) {
    for (let i = 0; i < days.length - 1; i += 1) {
      if (days[i].date < todayStart || days[i].date > outlookEnd) continue;
      const event = milkyWayEvent(days[i], days[i + 1], latRad, lonRad);
      if (event) events.push(event);
    }
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

  // Each event carries its own "still relevant" boundary (a whole night, an
  // eclipse's multi-hour window, a migration season) rather than a single
  // cutoff, so today's already-finished morning golden hour drops out while
  // an all-night meteor shower or eclipse in progress does not.
  const stillRelevant = events.filter((event) => (event.relevantUntil || new Date(event.time.getTime() + 30 * 60000)) >= now);
  stillRelevant.sort((a, b) => a.time - b.time);
  return { events: stillRelevant, error: null };
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
  "show_meteor_showers",
  "show_eclipses",
  "show_milky_way",
  "show_bird_migration",
];

/* ---------------------------------------------------------------------- *
 * Config editor
 * ---------------------------------------------------------------------- */

const DEFAULT_CONFIG = Object.freeze({
  title: "Photography Events",
  location_name: "",
  latitude: null,
  longitude: null,
  elevation: null,
  weather_entity: "",
  outlook_days: 21,
  show_sun_events: true,
  show_moon_events: true,
  show_meteor_showers: true,
  show_eclipses: true,
  show_milky_way: true,
  show_bird_migration: true,
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
        <div class="row"><span class="label">Card title</span>
          <input type="text" data-text="title" value="${escapeHtml(cfg.title)}">
        </div>
      </div>

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
        ${this._toggleRow("show_meteor_showers", "Meteor shower peaks")}
        ${this._toggleRow("show_eclipses", "Solar and lunar eclipses")}
        ${this._toggleRow("show_milky_way", "Milky Way core season")}
        ${this._toggleRow("show_bird_migration", "Bird migration season")}
      </div>
    `;

    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((input) => {
      input.addEventListener("change", () => this._update(input.dataset.toggle, input.checked));
    });
    this.shadowRoot.querySelectorAll("[data-text]").forEach((input) => {
      input.addEventListener("change", () => this._update(input.dataset.text, input.value.trim()));
    });
    this.shadowRoot.querySelectorAll("[data-number]").forEach((input) => {
      input.addEventListener("change", () => {
        const value = clamp(Number.parseInt(input.value, 10) || DEFAULT_CONFIG.outlook_days, 7, 30);
        input.value = String(value);
        this._update(input.dataset.number, value);
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
      select.addEventListener("change", () => this._update(select.dataset.select, select.value));
    });

    this._rendered = true;
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
  }

  set hass(hass) {
    this._hass = hass;
    if (this._connected && !this._initialized) this._start();
  }

  setConfig(config) {
    if (!config) throw new Error("Photography Events Card configuration is required");
    const weatherChanged = config.weather_entity !== this._config.weather_entity;
    this._config = {
      ...DEFAULT_CONFIG,
      ...config,
      outlook_days: clamp(Number.parseInt(config.outlook_days, 10) || DEFAULT_CONFIG.outlook_days, 7, 30),
    };
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
    const html = `
      <ha-card>
        <div class="card-content">
          ${this._hass ? this._bodyHtml() : this._loadingHtml("Waiting for Home Assistant")}
        </div>
      </ha-card>
    `;

    // Ticks that produce byte-identical markup leave the live DOM untouched
    // instead of destroying and re-upgrading every ha-icon in the timeline.
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
  }

  _loadingHtml(label) {
    return `<div class="loading"><span class="spinner"></span><span>${escapeHtml(label)}</span></div>`;
  }

  _bodyHtml() {
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
      ${this._snapshotHtml(now)}
      ${this._events.length ? this._timelineHtml(now) : this._emptyTimelineHtml()}
      ${this._footerHtml()}
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

  _styles() {
    return `
      :host {
        --pe-surface: var(--ha-card-background, var(--card-background-color, #1d1d1f));
        --pe-text: var(--primary-text-color, #f5f5f7);
        --pe-muted: var(--secondary-text-color, rgba(235, 235, 245, .60));
        --pe-border: var(--divider-color, rgba(255, 255, 255, .18));
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
      @media (max-width: 600px) {
        .card-content { padding: 16px 12px; }
        .snapshot-strip { gap: 6px; }
        .snapshot-tile { padding: 8px; }
        .snapshot-count { font-size: 17px; }
      }
    `;
  }

  getCardSize() {
    const categories = CATEGORY_TOGGLE_KEYS.filter((key) => this._config?.[key] !== false).length;
    return Math.max(4, 2 + categories * 2);
  }

  static getConfigElement() {
    return document.createElement("photography-events-card-editor");
  }

  static getStubConfig(hass) {
    const weatherEntity = hass?.states ? Object.keys(hass.states).find((id) => id.startsWith("weather.")) : undefined;
    return { ...DEFAULT_CONFIG, weather_entity: weatherEntity || "" };
  }
}

// Test-only seam: the astronomy math is written as free functions (no `this`
// juggling), so it is exposed here for direct unit testing the same way the
// rest of this repo pokes at underscore-prefixed instance methods.
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
  sunsetQuality,
  meteorQuality,
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
