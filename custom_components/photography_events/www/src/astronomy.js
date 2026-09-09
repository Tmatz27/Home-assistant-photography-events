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
