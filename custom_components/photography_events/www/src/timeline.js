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
    supermoon: isSupermoon,
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
    ? lunarEclipseVisibility(date, latRad, lonRad, eclipse)
    : solarEclipseVisibility(date, latRad, lonRad, eclipse);
  const kindLabel = eclipse.kind === "lunar" ? "Lunar" : "Solar";
  const typeLabel = eclipse.kind === "lunar" && eclipse.type === "total" && visibility.visible && !visibility.totalVisible
    ? "Partial" : eclipse.type.charAt(0).toUpperCase() + eclipse.type.slice(1);
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
    // A penumbral lunar eclipse is not a photograph. The Moon grazes the outer
    // shadow, the dimming is subtle enough that people looking for it miss it,
    // and a camera records a full moon. Listing it trains you to skip the row
    // that says "eclipse" - which is the one row that must never be skipped.
    photographable: eclipse.type !== "penumbral",
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
        // A supermoon is a landscape to put something in front of. A new moon
        // is already priced into every Milky Way and meteor row on the card,
        // and quarters were never news. Nothing else earns a line.
        return event.supermoon === true;
      case "planet":
        if (event.kind === "opposition") return true;
        if (event.kind === "conjunction") {
          return typeof event.separationDeg === "number" && event.separationDeg < TIGHT_CONJUNCTION_DEG;
        }
        return false;
      case "eclipse":
        // An eclipse nobody here can see is a fact about somewhere else - and a
        // penumbral lunar eclipse is a fact about nothing. The Moon grazes the
        // outer shadow, the dimming is invisible in a photograph, and listing
        // it teaches you to ignore the row that says "eclipse".
        return event.visible === true && event.photographable !== false;
      default:
        return true;
    }
  });
}

/* ---------------------------------------------------------------------- *
 * Rendering helpers
 * ---------------------------------------------------------------------- */
