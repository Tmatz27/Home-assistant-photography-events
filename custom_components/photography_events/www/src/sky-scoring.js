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

function lunarEclipseVisibility(eclipseDate, latRad, lonRad, eclipse = null) {
  if (eclipse) {
    const half = (eclipse.partial_minutes || 0) * 30000;
    if (!half) return {visible:false, note:"No photographable umbral phase."};
    let visible = false, totalVisible = false, allUp = true;
    for (let t = -half; t <= half; t += 60000) {
      const up = moonAltitude(new Date(eclipseDate.getTime()+t),latRad,lonRad)*DEG >= 5;
      visible ||= up; allUp &&= up;
      totalVisible ||= up && eclipse.total_minutes > 0 && Math.abs(t) <= eclipse.total_minutes*30000;
    }
    return {visible, totalVisible, note: !visible ? "The Moon does not clear 5 degrees during the umbral phase." :
      `${totalVisible ? "Totality is visible here." : "Only the partial phase is verified here."} ${allUp ? "The full umbral phase clears 5 degrees." : "Moonrise or moonset limits the viewing window."}`};
  }
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

function centralPathMargin(row, point) {
  const angular = (a,b) => 2 * Math.asin(Math.min(1, Math.sqrt(
    Math.sin((b[0]-a[0])*RAD/2)**2 + Math.cos(a[0]*RAD)*Math.cos(b[0]*RAD)*Math.sin((b[1]-a[1])*RAD/2)**2)));
  const bearing = (a,b) => Math.atan2(Math.sin((b[1]-a[1])*RAD)*Math.cos(b[0]*RAD),
    Math.cos(a[0]*RAD)*Math.sin(b[0]*RAD)-Math.sin(a[0]*RAD)*Math.cos(b[0]*RAD)*Math.cos((b[1]-a[1])*RAD));
  let margin = -Infinity;
  for (let i = 1; i < (row.path || []).length; i++) {
    const a = row.path[i-1], b = row.path[i], start = a.slice(1,3), end = b.slice(1,3);
    const arc = angular(start,end), distance = angular(start,point), angle = bearing(start,point)-bearing(start,end);
    const along = Math.atan2(Math.sin(distance)*Math.cos(angle),Math.cos(distance));
    const cross = Math.asin(clamp(Math.sin(distance)*Math.sin(angle),-1,1));
    const nearest = arc > 1e-9 && along >= 0 && along <= arc ? Math.abs(cross) : Math.min(distance,angular(end,point));
    margin = Math.max(margin, Math.min(a[3],b[3])/2 - 10 - nearest*6371);
  }
  return margin;
}

function solarEclipseVisibility(eclipseDate, latRad, lonRad, eclipse = null) {
  if (eclipse?.path?.length) {
    const inside = centralPathMargin(eclipse, [latRad*DEG,lonRad*DEG]) >= 0;
    if (!inside) return {visible:false, note:"Your location is outside the verified central path. Partial-only visibility is not assessed."};
    const dot = p => Math.sin(latRad)*Math.sin(p[1]*RAD)+Math.cos(latRad)*Math.cos(p[1]*RAD)*Math.cos(p[2]*RAD-lonRad);
    const closest = eclipse.path.reduce((a,b) => dot(a) > dot(b) ? a : b);
    const [hour,minute] = closest[0].split(":").map(Number);
    let local = new Date(eclipseDate); local.setUTCHours(hour,minute,0,0);
    local = [-1,0,1].map(d=>new Date(local.getTime()+d*MS_PER_DAY)).sort((a,b)=>Math.abs(a-eclipseDate)-Math.abs(b-eclipseDate))[0];
    const visible = sunAltitude(local,latRad,lonRad)*DEG >= 5;
    return {visible, note: visible ? "Your location is inside NASA's sampled central path. Verify local contacts and access before planning the shot." : "The Sun does not clear 5 degrees at the nearest path sample's time."};
  }
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
