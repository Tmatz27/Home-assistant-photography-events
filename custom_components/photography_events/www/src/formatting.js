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
  waves: { color: "#56cbd2", label: "Waves", icon: "mdi:waves" },
  astronomy: { color: "#9aaeff", label: "Astro", icon: "mdi:telescope" },
  sunset: { color: "#f4a15b", label: "Skies", icon: "mdi:weather-sunset" },
  marine: { color: "#58b9f2", label: "Whales", icon: "mdi:whale" },
  mammals: { color: "#d9b78b", label: "Mammals", icon: "mdi:paw" },
  birds: { color: "#d4ce72", label: "Birds", icon: "mdi:bird" },
  blooms: { color: "#ed9cc8", label: "Blooms", icon: "mdi:flower" },
  foliage: { color: "#e8ab66", label: "Autumn", icon: "mdi:leaf-maple" },
  parks: { color: "#92ca96", label: "Parks", icon: "mdi:pine-tree" },
  rare_phenomena: { color: "#c9a4ef", label: "Rare", icon: "mdi:star-shooting" },
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
    id: attributes.event_id || "",
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
    preferences: attributes.preferences || {},
    sources: attributes.sources || {},
    parks: attributes.parks && typeof attributes.parks === "object" ? attributes.parks : {},
    gear: attributes.gear_by_category && typeof attributes.gear_by_category === "object"
      ? attributes.gear_by_category
      : {},
    categories: Array.isArray(attributes.all_categories) && attributes.all_categories.length
      ? attributes.all_categories
      : Array.isArray(attributes.categories) ? attributes.categories : [],
    truncated: Boolean(attributes.truncated),
    horizonDays: Number.isFinite(attributes.precision_horizon_days)
      ? attributes.precision_horizon_days
      : 60,
    missing: !state,
  };
}

/**
 * What each verification state actually means for somebody about to book.
 *
 * This is the difference between a card that shows a number and one that shows
 * whether the number is worth anything. "Watching" and "corroborated" can carry
 * the same score; only one of them is a reason to drive.
 */
const VERIFICATION_META = {
  computed: { label: "Calculated", tone: "ok", text: "Calculated timing; viewing conditions are separate." },
  corroborated: { label: "Confirmed", tone: "ok", text: "Live reports back this up right now." },
  presence_only: { label: "Species reported", tone: "warn", text: "The named behavior or gathering is not confirmed." },
  forecast: { label: "Forecast", tone: "warn", text: "Conditions are forecast, not yet observed." },
  watching: { label: "Watching", tone: "warn", text: "Nothing reported yet - this is where to look, not when to go." },
  unverified: { label: "Estimate", tone: "warn", text: "A calendar estimate. No live source can confirm it." },
};

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
    .map((event) => ({ ...event, startDate: parseEventDate(event.start), endDate: parseEventDate(event.end) || parseEventDate(event.start) }))
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

/**
 * One row per thing, not one row per place.
 *
 * The Milky Way core is up over all twelve zones on the same night, and one
 * vagrant bird gets reported from four lagoons. Listed flat, that is sixteen
 * rows saying two things, and the calendar has buried everything else under
 * them. The backend stamps rows that are the same thing seen from different
 * places with a shared roll key; the best of them wins the row and the rest
 * live inside it, so the choice of where to drive is still there, one level
 * down, where the choice actually belongs.
 *
 * A row with no roll key is one of a kind and passes through untouched.
 */
function rollUpByPlace(events) {
  const buckets = new Map();
  const out = [];
  for (const event of events) {
    if (!event.roll) {
      out.push(event);
      continue;
    }
    const bucket = buckets.get(event.roll);
    if (bucket) bucket.push(event);
    else buckets.set(event.roll, [event]);
  }
  for (const bucket of buckets.values()) {
    // Best score wins. Preserve the longer usable astronomy window on a tie,
    // then prefer the nearer site when the photographic opportunity is equal.
    bucket.sort((left, right) =>
      (right.score || 0) - (left.score || 0) ||
      (right.duration_minutes || 0) - (left.duration_minutes || 0) ||
      (left.drive_hours || 0) - (right.drive_hours || 0));
    const [best, ...rest] = bucket;
    out.push(rest.length ? { ...best, alternatives: rest } : best);
  }
  return out;
}

function consolidateNights(events) {
  const other = events.filter(event => !event.key?.startsWith("milkyway-"));
  const nights = events.filter(event => event.key?.startsWith("milkyway-"))
    .sort((a, b) => a.startDate - b.startDate);
  const periods = [];
  for (const night of nights) {
    const last = periods.at(-1);
    // Do not join different lunar windows across a gap in usable nights.
    if (!last || night.startDate - last.at(-1).startDate > 3 * MS_PER_DAY) periods.push([night]);
    else last.push(night);
  }
  for (const period of periods) {
    const options = period.flatMap(event => [event, ...(event.alternatives || [])]);
    const ranked = [...options].sort((a, b) => (b.score || 0) - (a.score || 0) ||
      (b.duration_minutes || 0) - (a.duration_minutes || 0) || a.startDate - b.startDate);
    const best = ranked[0];
    const places = [...new Set(options.map(event => event.where || event.zone).filter(Boolean))];
    other.push({ ...best, title: "Milky Way core", nights: period, nightOptions: options,
      startDate: period[0].startDate, endDate: new Date(Math.max(...period.map(e => e.endDate))),
      locations: places, alternatives: [], bestNight: best,
      choiceIds: [...new Set(options.map(e => e.event_id || e.roll || e.key))] });
  }
  return other;
}

function cloudLabel(event) {
  if (event.cloud_is_forecast === true) return "Cloud forecast";
  if (event.cloud_is_forecast === false) return "Cloud outlook (lower confidence)";
  return "Cloud estimate (confidence unavailable)";
}

function healthStripHtml(sources) {
  const entries = Object.entries(sources).filter(([, s]) => s.enabled !== false);
  if (!entries.length) return "";
  const degraded = entries.filter(([, s]) => s.failures > 0 || s.stale || s.state === "failed");
  const waiting = entries.filter(([, s]) => !s.last_success && !s.failures);
  return `<details class="source-health ${degraded.length ? "source-warning" : ""}"><summary>${degraded.length ? `${degraded.length} data sources degraded` : waiting.length ? `${waiting.length} data sources awaiting first update` : "Data sources updated"}</summary>
    <p>These are source retrieval checks. Open an event for its observation dates and evidence.</p>
    ${entries.map(([key, s]) => `<div class="source-health-entry"><strong>${escapeHtml(s.name || key)}</strong> · ${escapeHtml(s.state || (s.failures ? "failed" : "unknown"))}<br>
      Last success: ${s.last_success ? escapeHtml(absoluteLabel(parseEventDate(s.last_success))) : "Not yet this session"}
      ${s.failures || s.stale ? `<br>${escapeHtml(s.impact || "Some recent reports may be missing.")}` : ""}</div>`).join("")}</details>`;
}

function nightTradeoffs(night, best) {
  const parts = [];
  if (night.key === best.key) parts.push("Highest ranked among these supplied nights and locations.");
  const duration = (night.duration_minutes || 0) - (best.duration_minutes || 0);
  if (night.duration_minutes && best.duration_minutes) parts.push(duration === 0 ? "Same usable duration as the preferred night." : `${Math.abs(duration)} minutes ${duration > 0 ? "more" : "less"} usable darkness than the preferred night.`);
  if (Number.isFinite(night.moon_illumination)) parts.push(`Moon ${Math.round(night.moon_illumination * 100)}% illuminated; the usable interval already accounts for moonlight and altitude.`);
  if (Number.isFinite(night.peak_altitude)) parts.push(`Core peaks at ${night.peak_altitude}°.`);
  if (Number.isFinite(night.cloud_cover)) parts.push(`${cloudLabel(night)} ${night.cloud_cover}%${Number.isFinite(best.cloud_cover) ? ` versus ${best.cloud_cover}% (${cloudLabel(best).toLowerCase()}) on the preferred night` : ""}.`);
  else parts.push("Cloud conditions are unknown, so this is a calculated option rather than a weather-backed recommendation.");
  if (night.score === best.score && night.key !== best.key) parts.push("Tied priority: this is a comparable alternative, not an inferior date.");
  return parts.join(" ");
}

function categoryColor(category) { return CATEGORY_META[category]?.color || "#b7bdc5"; }

function reportLinkHtml(event) {
  const url = safeExternalUrl(event.source_url);
  if (!url) return "";
  const exact = /\/checklist\/S\d+|\/observations\/\d+/.test(url);
  const label = exact ? (url.includes("ebird.org") ? "eBird checklist" : "Observation report") :
    event.observed_at ? "Source report" : "Source / viewing guide";
  return `<a class="outlook-source" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
}

// Local calendar-day arithmetic avoids 23/25-hour daylight-saving days.
function calendarSegments(events, weekStart) {
  const day = date => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / MS_PER_DAY;
  const base = day(weekStart);
  const lanes = [];
  return events.map(event => ({ event, start: Math.max(0, day(event.startDate) - base),
    end: Math.min(6, day(event.endDate) - base) }))
    .filter(item => item.start <= item.end && item.end >= 0 && item.start <= 6)
    .sort((a, b) => a.start - b.start || b.end - a.end)
    .map(item => {
      let lane = lanes.findIndex(end => end < item.start);
      if (lane < 0) lane = lanes.length;
      lanes[lane] = item.end;
      return { ...item, lane };
    });
}

// What the list is actually sorted by. A calendar ordered strictly by date puts
// twenty month-long seasons above the thing happening tonight, which is exactly
// backwards: the further away something is, the less it matters what order it
// is in.
const URGENCY_BUCKETS = [
  { key: "now", label: "Happening now" },
  { key: "week", label: "Next 7 days" },
  { key: "month", label: "Next 30 days" },
];

/**
 * Group by how soon it matters, then by month once it stops being soon.
 *
 * Inside the near buckets the order is by score rather than by date, because
 * over the next week "which of these is worth going out for" is a better
 * question than "which of these is first".
 */
function groupByUrgency(events, now) {
  const week = new Date(now.getTime() + 7 * MS_PER_DAY);
  const month = new Date(now.getTime() + 30 * MS_PER_DAY);
  const near = new Map(URGENCY_BUCKETS.map((bucket) => [bucket.key, { ...bucket, events: [] }]));
  const later = [];

  for (const event of events) {
    if (event.startDate <= now && event.endDate >= now) near.get("now").events.push(event);
    else if (event.startDate <= week) near.get("week").events.push(event);
    else if (event.startDate <= month) near.get("month").events.push(event);
    else later.push(event);
  }

  const groups = [...near.values()]
    .filter((bucket) => bucket.events.length)
    .map((bucket) => ({
      ...bucket,
      urgent: true,
      events: bucket.events.sort((left, right) =>
        (right.score || 0) - (left.score || 0) || left.startDate - right.startDate),
    }));
  return groups.concat(groupByMonth(later));
}

/** "Sat, Sep 5 at 8:49 PM" - what you actually need to plan an evening. */
function absoluteLabel(date) {
  if (!date) return "";
  const day = date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  return `${day} at ${clockLabel(date)}`;
}

/** "Sat 6 Sep". */
function dateLabel(date) {
  return date
    ? date.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })
    : "";
}

// How long before a window opens you actually want to be standing there with
// the tripod levelled. Short, but the difference between arriving and being
// ready is the difference between catching the first ten minutes and not.
// Travel and setup decisions belong to the photographer; show the actual window.

/**
 * "T-2d 3h" - how long until you have to be somewhere.
 *
 * Never shown on its own. "in 45h" cannot go in a calendar, does not survive
 * being read at a different hour, and quietly means something different every
 * time the card re-renders. It is context underneath a real date and time, not
 * a replacement for one.
 */
function countdownLabel(now, target) {
  if (!target) return "";
  const ms = target - now;
  if (ms <= 0) return "underway";
  const totalMinutes = Math.floor(ms / 60000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days) return `T\u2212${days}d ${hours}h`;
  if (hours) return `T\u2212${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `T\u2212${minutes}m`;
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
function safeExternalUrl(value) {
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : ""; }
  catch { return ""; }
}
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
  const left = start.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const right = end.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${left} - ${right}`;
}
