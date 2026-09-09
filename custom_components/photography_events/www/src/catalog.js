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

// Inserted from eclipse_catalog.json by the dependency-free card assembler.
const ECLIPSES = /* @eclipse-catalog */ [];

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
