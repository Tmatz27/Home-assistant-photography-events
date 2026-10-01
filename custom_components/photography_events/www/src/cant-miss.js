// --- Can't Miss --------------------------------------------------------------
//
// The primary dashboard. The integration has already decided what deserves a
// row (a hard eligibility gate, then ranking); the card's job is to make those
// few rows impossible to misread and to keep everything else out of the way.
// An empty list is a healthy answer and is drawn as one - unless the data is
// stale or missing, which must never look like a quiet week.

/** The Can't Miss sensor's payload, normalised and defensive about shape. */
function cantMissFromState(state) {
  const attributes = state?.attributes || {};
  const birds = attributes.birds && typeof attributes.birds === "object" ? attributes.birds : {};
  return {
    events: Array.isArray(attributes.events) ? attributes.events : [],
    watch: Array.isArray(attributes.watch) ? attributes.watch : [],
    // Rows that passed everything but a safety check that could not be made.
    held: Array.isArray(attributes.held) ? attributes.held : [],
    signals: Array.isArray(attributes.signals) ? attributes.signals : [],
    signalCount: Number(attributes.signal_count) || 0,
    birds: {
      spectacle: Array.isArray(birds.spectacle) ? birds.spectacle : [],
      encounter: Array.isArray(birds.encounter) ? birds.encounter : [],
      chase: Array.isArray(birds.chase) ? birds.chase : [],
    },
    headline: attributes.headline || "",
    // Whether every source needed to assess the enabled categories answered.
    // "incomplete" must never be drawn as a quiet week.
    assessment: attributes.assessment && typeof attributes.assessment === "object"
      ? { state: attributes.assessment.state || "complete",
          problems: Array.isArray(attributes.assessment.problems) ? attributes.assessment.problems : [] }
      : { state: "complete", problems: [] },
    showLimit: Number(attributes.show_limit) || 5,
    preferences: attributes.preferences || {},
    sources: attributes.sources || {},
    generated: parseEventDate(attributes.generated),
    unavailable: !state || ["unavailable", "unknown"].includes(state.state),
  };
}

// Owned lenses by their everyday names. The backend names them in full; a
// collapsed row has room for "200-600 G", not a model number.
const LENS_SHORT = [
  [/FE 16-35mm f\/2\.8 GM/i, "16-35 GM"],
  [/FE 70-200mm f\/2\.8 GM OSS II/i, "70-200 GM II"],
  [/FE 200-600mm f\/5\.6-6\.3 G OSS/i, "200-600 G"],
  [/FE 2x Teleconverter/i, "2x TC"],
  [/^Sony /i, ""],
];

function shortLens(text) {
  let value = String(text || "");
  for (const [pattern, label] of LENS_SHORT) value = value.replace(pattern, label);
  return value.trim();
}

/** How old a route is, in words: "5 h", "6 days". */
function routeAgeLabel(row, now) {
  const fetched = parseEventDate(row.route_fetched_at);
  if (!fetched) return "";
  const hours = Math.max(0, (now - fetched) / 3600000);
  return hours < 48 ? `${Math.round(hours)} h` : `${Math.round(hours / 24)} days`;
}

/**
 * What a drive time rests on: current traffic, a recent route (typical, not
 * current traffic) or a distance estimate. A hard drive-limit decision can
 * rest on any of the three, so the row must say which.
 */
function driveBasisLabel(row, now) {
  const basis = row.drive_basis;
  if (basis === "current") return `${row.drive_source || "routed"}, ${row.drive_in_traffic ? "current traffic" : "routed now"}`;
  if (basis === "recent") {
    const age = routeAgeLabel(row, now);
    return `${row.drive_source || "routed"}, routed ${age ? `${age} ago` : "earlier"}; not current traffic`;
  }
  if (basis === "estimate" || row.drive_source === "estimate") return "estimated from distance";
  return row.drive_source || "";
}

/** Where, and how far, in the words a person would use. */
function whereLabel(row, now = new Date()) {
  const place = row.where || row.zone || "";
  const hours = Number(row.drive_hours);
  if (row.drive_hours == null || !Number.isFinite(hours)) return `${place ? `${place} · ` : ""}drive unavailable`;
  if (hours <= 0.05) return place ? `${place} · at home` : "At home";
  let basis = "";
  if (row.drive_basis === "recent") {
    const age = routeAgeLabel(row, now);
    basis = age ? ` (route ${age} old)` : " (old route)";
  }
  return `${place} · ~${driveLabel(Math.round(hours * 60))} drive${basis}`;
}

/**
 * When, as an absolute instruction. A countdown is never shown alone: it
 * cannot go in a calendar and reads differently at every glance.
 */
function whenLabel(row, now) {
  const start = parseEventDate(row.start);
  const end = parseEventDate(row.end) || start;
  if (!start) return "";
  const timed = !row.all_day && String(row.start).includes("T");
  if (timed && end - start <= 36 * 3600000) {
    return `${absoluteLabel(start)}${end > start ? ` – ${clockLabel(end)}` : ""}`;
  }
  if (start <= now && end >= now) return `Underway until ${dateLabel(end)}`;
  return rangeLabel(start, end);
}

/** Full-Moon geometry rows, shared by Can't Miss and the planner detail. */
function moonGeometryRows(row) {
  if (!row.moonrise) return [];
  return [["Moonrise", `${absoluteLabel(parseEventDate(row.moonrise))} · ${row.moonrise_azimuth}° ${row.moonrise_compass}`],
    ["Moonset", row.moonset ? `${absoluteLabel(parseEventDate(row.moonset))}${row.moonset_azimuth != null ? ` · ${row.moonset_azimuth}° ${row.moonset_compass || ""}` : ""}` : ""],
    ["Sunset", (row.sunset_at || row.sunset) ? absoluteLabel(parseEventDate(row.sunset_at || row.sunset)) : ""],
    ["Twilight", row.civil_dusk ? `Civil dusk ${clockLabel(parseEventDate(row.civil_dusk))}${row.nautical_dusk ? ` · nautical ${clockLabel(parseEventDate(row.nautical_dusk))}` : ""}${row.astronomical_dusk ? ` · astronomical ${clockLabel(parseEventDate(row.astronomical_dusk))}` : ""}` : ""],
    ["Moon climb", (row.moon_climb || []).map(step => `${step.altitude}° ${clockLabel(parseEventDate(step.time))} ${step.compass}`).join(" · ")],
    ["Distance", row.distance_km ? `${Number(row.distance_km).toLocaleString()} km · ${row.diameter_arcmin}′${row.distance_rank ? ` · #${row.distance_rank} closest of ${row.full_moons_in_year || "the year's"} full Moons` : ""}${row.supermoon_nolle ? " · supermoon (Nolle's 90% rule)" : ""}` : ""],
    ["Facts", (row.moon_labels || []).join(". ")]];
}

/** A gear plan as labelled rows: required safety kit, owned kit, then unowned suggestions. */
function gearPlanRows(plan) {
  plan = plan || {};
  return [["Required", (plan.required || []).join("; ")], ["Safety", plan.safety],
    ["Take", shortLens(plan.take)], ["Optional", (plan.optional || []).map(shortLens).join("; ")],
    ["Skip", (plan.skip || []).map(shortLens).join("; ")], ["Start with", plan.start], ["Support", plan.support],
    ["Technique", plan.technique], ["Video", shortLens(plan.video)], ["Drone", plan.drone],
    ["Worth adding or renting (not in your bag)", (plan.add || []).map(item => `${item.item}: ${item.why}`).join(" · ")]];
}

const CANT_MISS_MODES = {
  _cantMissEntityId() {
    if (this._config?.cant_miss_entity) return this._config.cant_miss_entity;
    return findEntity(this._hass, "sensor.", "can_t_miss") || findEntity(this._hass, "sensor.", "cant_miss");
  },

  _cantMissHtml() {
    const state = this._hass.states[this._cantMissEntityId()];
    const board = cantMissFromState(state);
    const now = new Date();
    const events = board.events.filter(row => {
      const end = parseEventDate(row.end) || parseEventDate(row.start);
      return !end || end >= now;
    });
    this._choiceGroups.clear();
    for (const row of events) if (row.choice_ids?.length) this._choiceGroups.set(row.event_id || row.key, row.choice_ids);
    const outlookLike = { generated: board.generated, events, unavailable: board.unavailable };
    const stale = board.unavailable || this._hass.connected === false ||
      (board.generated && now - board.generated > 45 * 60000) || !board.generated;
    const all = this._moreBuckets.has("cant-miss");
    const shown = all ? events : events.slice(0, board.showLimit);
    return `<div class="cm-card">
      <div class="cm-heading"><span>Can't miss</span><span class="cm-sub">next 7 days · within your drive limit</span></div>
      ${this._freshnessHtml(outlookLike, now, "Can't miss")}
      ${this._choiceError ? `<div role="alert" class="event-error">${escapeHtml(this._choiceError)}</div>` : ""}
      ${events.length && board.assessment.state === "incomplete" ? this._incompleteNoteHtml(board) : ""}
      ${events.length ? shown.map(row => this._cantMissRowHtml(row, board, now)).join("") +
        (events.length > board.showLimit ? `<button type="button" class="show-more" data-more="cant-miss" aria-expanded="${all}">${all ? "Show fewer" : `Show ${events.length - board.showLimit} more`}</button>` : "")
        : this._cantMissEmptyHtml(board, stale)}
      ${this._heldHtml(board)}
      ${this._watchSummaryHtml(board)}
      ${this._backgroundHtml(board, now)}
      ${healthStripHtml(board.sources)}
    </div>`;
  },

  _watchSummaryHtml(board) {
    if (!board.watch.length) return "";
    return `<aside class="cm-watch-summary"><strong>WATCHING ${board.watch.length} OPPORTUNIT${board.watch.length === 1 ? "Y" : "IES"}</strong>
      <p>${board.watch.slice(0, 3).map(row => escapeHtml(row.title)).join(" · ")}</p>
      <button type="button" class="show-more" data-tab="watching">View Watching</button></aside>`;
  },

  _watchingHtml() {
    const board = cantMissFromState(this._hass.states[this._cantMissEntityId()]);
    const now = new Date();
    return `<div class="cm-card"><div class="cm-heading"><span>Watching</span><span class="cm-sub">tracked · not yet Can't Miss</span></div>
      ${this._freshnessHtml({ generated: board.generated, events: board.watch, unavailable: board.unavailable }, now, "Watching")}
      <p class="cm-none">Potentially exceptional phenomena awaiting their event-specific evidence or conditions. These are not recommendations to go.</p>
      ${board.watch.map((row, index) => {
        const category = CATEGORY_META[row.category];
        const reports = (row.behavior_evidence || []).map(report => `${report.source || "Report"}: ${report.text || ""}`).join(" ");
        const context = (row.unconfirmed_reports || []).map(report => `${report.source || "Report"} (${report.observed_at ? "not qualifying confirmation" : "undated; not confirmation"}): ${report.text || ""}`).join(" ");
        return `<article class="cm-watch-row" style="--event-color:${categoryColor(row.category)}">
          <h4>${category ? `<ha-icon icon="${category.icon}"></ha-icon> ` : ""}${escapeHtml(row.title)}</h4>
          <p>${category ? `${escapeHtml(category.label)} · ` : ""}WATCHING · ${escapeHtml(row.status || "Awaiting confirmation")}</p>
          <p>${escapeHtml(whereLabel(row, now))}<br>${escapeHtml(whenLabel(row, now))}</p>
          ${row.drive_basis ? `<p>${escapeHtml(driveBasisLabel(row, now))}</p>` : ""}
          ${row.detail ? `<p><strong>Why it matters:</strong> ${escapeHtml(row.detail)}</p>` : ""}
          ${reports ? `<p><strong>Evidence:</strong> ${escapeHtml(reports)}</p>` : ""}
          ${context ? `<p><strong>Report context:</strong> ${escapeHtml(context)}</p>` : ""}
          ${row.awaiting ? `<p><strong>Waiting for:</strong> ${escapeHtml(row.awaiting)}</p>` : ""}
          ${row.blockers?.length ? `<p><strong>Why not Can't Miss:</strong> ${escapeHtml(row.blockers.join("; "))}</p>` : ""}
          ${row.source_health_note ? `<p>${escapeHtml(row.source_health_note)}</p>` : ""}
          <details data-section="watch-${escapeHtml(row.key || row.phenomenon || String(index))}" class="detail-section"><summary>Evidence & details</summary>
            ${this._cantMissDetailHtml({ ...row, key: `watch-${row.key || row.phenomenon || index}` }, board, now, false)}</details>
        </article>`;
      }).join("") || `<p class="cm-none">${board.unavailable ? "Waiting for the Watching payload." : "No assessed Watch opportunities in the current watch window. The year planner still lists longer-range seasons."}</p>`}
      ${this._backgroundHtml({ ...board, watch: [] }, now)}${healthStripHtml(board.sources)}</div>`;
  },

  /** Held: every other check passed, but one could not be made. Never silently dropped, never presented as clear. */
  _heldHtml(board) {
    if (!board.held.length) return "";
    const items = board.held.map(item => `<li><strong>${escapeHtml(item.title)}</strong>${item.where ? ` · ${escapeHtml(item.where)}` : ""}<br><span>${escapeHtml(item.summary || "")}</span></li>`).join("");
    return `<div class="cm-held" role="status"><strong>Held: a required check could not be made</strong>
      <p>These would otherwise be listed. Safety, marine conditions or park access could not be checked for them, and unknown is not the same as safe or open.</p><ul>${items}</ul></div>`;
  },

  /** Which required sources prevented a trustworthy assessment. */
  _incompleteProblemsHtml(board) {
    const problems = board.assessment.problems.map(item => `<li>${escapeHtml(item.name || item.source || "Source")}${item.state ? ` · ${escapeHtml(item.state)}` : ""}${item.impact ? `<br><span>${escapeHtml(item.impact)}</span>` : ""}</li>`).join("");
    return problems ? `<ul class="cm-problems">${problems}</ul>` : "";
  },

  _incompleteNoteHtml(board) {
    return `<details class="cm-incomplete-note" data-section="cant-miss-incomplete"><summary>Assessment incomplete: some required data is unavailable</summary>
      <p>The rows below passed every check they depend on. Other opportunities could not be assessed.</p>${this._incompleteProblemsHtml(board)}</details>`;
  },

  _cantMissEmptyHtml(board, stale) {
    if (stale) {
      return `<div class="cm-empty cm-empty-stale" role="status"><strong>Can't Miss is not up to date.</strong>
        <span>Waiting for a successful update. An empty list here is not evidence of a quiet week.</span></div>`;
    }
    if (board.assessment.state === "incomplete") {
      return `<div class="cm-empty cm-empty-stale cm-incomplete" role="status"><strong>${escapeHtml(board.headline || "Can't Miss assessment incomplete: required data unavailable.")}</strong>
        <span>An empty list here is not evidence of a quiet week. Watch items and the planner are still listed.</span>${this._incompleteProblemsHtml(board)}</div>`;
    }
    if (board.held.length) {
      return `<div class="cm-empty cm-empty-stale" role="status"><strong>${escapeHtml(board.headline || "Nothing cleared to recommend.")}</strong></div>`;
    }
    const watched = board.watch.length;
    return `<div class="cm-empty" role="status"><ha-icon icon="mdi:check-circle-outline"></ha-icon>
      <strong>${escapeHtml(board.headline || "Nothing worth changing plans for this week.")}</strong>
      <span>${watched ? `${watched} opportunit${watched === 1 ? "y is" : "ies are"} being watched.` : "Nothing is building either."} The year planner still lists every season.</span></div>`;
  },

  _cantMissRowHtml(row, board, now) {
    const key = row.key;
    const expanded = this._expanded.has(key);
    const take = shortLens(row.gear_plan?.take || row.gear || "");
    const required = (row.gear_plan?.required || [])[0];
    const best = row.best_time_of_day ? ` · ${row.best_time_of_day}` : "";
    const warn = (row.safety_notes || []).length || row.source_health_note;
    const caution = row.safety_state === "caution" ? "Caution · " : row.safety_state === "unknown" ? "Safety not checked · " : "";
    return `<div class="cm-row ${expanded ? "open" : ""}" style="--event-color:${categoryColor(row.category)}">
      <button type="button" class="cm-head" data-expand="${escapeHtml(key)}" aria-expanded="${expanded}">
        <span class="cm-title">${escapeHtml(String(row.title || "").replace(/ \(season\)$/, ""))}</span>
        <span class="cm-where">${escapeHtml(whereLabel(row, now))}</span>
        ${row.why_now ? `<span class="cm-why">${escapeHtml(row.why_now)}</span>` : ""}
        <span class="cm-when">${escapeHtml(whenLabel(row, now))}${escapeHtml(best)}</span>
        <span class="cm-status">${escapeHtml(caution)}${escapeHtml(row.status || "")}${warn ? " · check notes" : ""}</span>
        ${take ? `<span class="cm-take">Take: ${escapeHtml(take)}</span>` : ""}
        ${required ? `<span class="cm-required">Required: ${escapeHtml(required.split(" - ")[0].split(":")[0])}</span>` : ""}
      </button>
      ${expanded ? this._cantMissDetailHtml(row, board, now) : ""}
    </div>`;
  },

  _cantMissDetailHtml(row, board, now, showChoices = true) {
    const list = rows => `<dl class="outlook-detail-grid">${rows.filter(([, v]) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(Array.isArray(v) ? v.join(" ") : v)}</dd>`).join("")}</dl>`;
    const section = (id, title, body) => `<details class="detail-section" data-section="${escapeHtml(row.key)}-${id}"><summary>${title}</summary>${body}</details>`;
    const plan = row.gear_plan || {};
    const start = parseEventDate(row.start);
    const end = parseEventDate(row.end);
    const dates = [["Window", start ? `${absoluteLabel(start)} to ${absoluteLabel(end || start)}` : ""],
      ["Context", start ? countdownLabel(now, start) : ""],
      ["Best time", row.best_time_of_day], ["Season", row.season_range], ["Current phase", row.current_phase],
      ["Other sites or nights", row.alternative_count ? `${row.alternative_count} more in the planner` : ""]];
    dates.push(...moonGeometryRows(row));
    if (row.color_window_start) dates.push(["Colour window", `${clockLabel(parseEventDate(row.color_window_start))} – ${clockLabel(parseEventDate(row.color_window_end))}`]);
    const evidence = [["Status", row.status], ["Significance", row.significance != null ? `${row.significance}/100 — how extraordinary, not how likely` : ""],
      ["Confidence", row.confidence != null ? `${row.confidence}/100 · ${row.confidence_basis || ""}` : ""],
      ["Policy", (row.policy || "").replace(/_/g, " ")], ["Encounter", row.encounter],
      ["Forecast source", row.provider_note], ["Local sky model", row.light_path ? `${row.light_path === "modelled" ? "light path modelled" : "local cloud only"}` : ""],
      ["Still needed / limits", row.awaiting], ["Observed", row.observed_at ? absoluteLabel(parseEventDate(row.observed_at)) : ""],
      ["Fallback in use", row.fallback_note], ["Data degraded", row.source_health_note],
      ...Object.entries(row.condition_states && typeof row.condition_states === "object" ? row.condition_states : {})];
    const reports = (row.behavior_evidence || []).map(report => `<p class="cm-report">${escapeHtml(report.source || "Report")}${report.observed_at ? ` · ${escapeHtml(absoluteLabel(parseEventDate(report.observed_at)))}` : ""}: “${escapeHtml(report.text || "")}”${safeExternalUrl(report.url) ? ` <a href="${escapeHtml(safeExternalUrl(report.url))}" target="_blank" rel="noopener noreferrer">source</a>` : ""}</p>`).join("");
    const urls = [...new Set([...(Array.isArray(row.verify) ? row.verify : []), row.source_url].map(safeExternalUrl).filter(Boolean))];
    const links = urls.map(url => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel(url))}</a>`).join("");
    // Required safety kit first; owned kit next; unowned suggestions last and
    // labelled as such, so the two are never read as one packing list.
    const gear = gearPlanRows(plan);
    const access = [["Where", row.where || row.zone], ["Approximate drive", row.drive_hours == null ? "Unavailable" : Number(row.drive_hours) > 0.05 ? `${driveLabel(Math.round(row.drive_hours * 60))} (${driveBasisLabel(row, now)})` : "At home"],
      ["Drive estimate", row.drive_basis === "recent" && Number(row.estimated_drive_hours) > 0 ? `${driveLabel(Math.round(row.estimated_drive_hours * 60))} by distance` : ""],
      ["Access", row.access_note], ["Safety", [row.safety_summary, ...(row.safety_notes || [])].filter(Boolean).join(" ")],
      ["Wildlife ethics", row.ethics], ["Closures", (row.closures || []).join("; ")]];
    return `<div class="outlook-detail">
      ${row.detail ? `<p class="event-intro">${escapeHtml(row.detail)}</p>` : ""}
      ${showChoices ? this._eventControlsHtml(row.event_id || row.key, board.preferences[row.event_id || row.key]?.choice) : ""}
      ${section("evidence", "Evidence & sources", list(evidence) + reports + reportLinkHtml(row) + `<div class="outlook-verify">${links}</div>`)}
      ${section("dates", "Dates & timing", list(dates))}
      ${this._config.show_gear !== false ? section("gear", "Gear & technique", list(gear)) : ""}
      ${section("access", "Access, safety & ethics", list(access))}
    </div>`;
  },

  /** One collapsed section for everything that is building but not yet a reason to go. */
  _backgroundHtml(board, now) {
    const total = board.signals.length;
    if (!total) return "";
    const signals = board.signals.map(signal => {
      const stamp = parseEventDate(signal.observed_at || signal.valid_at);
      const url = safeExternalUrl(signal.url);
      const basis = signal.basis === "reported_undated" ? "undated report" : signal.basis;
      return `<li>${escapeHtml(signal.subject)}${signal.place ? ` · ${escapeHtml(signal.place)}` : ""} · ${escapeHtml(basis)}${stamp ? ` · ${escapeHtml(absoluteLabel(stamp))}` : ""}${url ? ` · <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">source</a>` : ""}</li>`;
    }).join("");
    return `<details class="cm-background" data-section="cant-miss-background"><summary>Watching ${total} background signal${total === 1 ? "" : "s"}</summary>
      <p>Evidence that something may be building. None of it is a reason to go on its own; a sighting is a signal, not an event.</p>
      ${signals ? `<h4>Recent signals</h4><ul>${signals}</ul>` : ""}</details>`;
  },

  /** The optional bird view: spectacle, encounter, chase. */
  _birdsHtml() {
    const entity = this._cantMissEntityId();
    if (!entity) return this._setupHtml("No Can't miss sensor found", "Install Photography Events 0.16 or later, or set <code>cant_miss_entity</code>.");
    const board = cantMissFromState(this._hass.states[entity]);
    const now = new Date();
    const spectacle = board.birds.spectacle.map(row => this._cantMissRowHtml(row, board, now)).join("");
    const encounter = board.birds.encounter.map(item => `<li><strong>${escapeHtml(item.species)}</strong> · ${escapeHtml(item.site)} · ~${escapeHtml(driveLabel(Math.round(item.drive_hours * 60)))}<br><span>${escapeHtml(item.why)}</span>${safeExternalUrl(item.url) ? ` <a href="${escapeHtml(safeExternalUrl(item.url))}" target="_blank" rel="noopener noreferrer">latest report</a>` : ""}</li>`).join("");
    const chase = board.birds.chase.map(item => `<li><strong>${escapeHtml(item.species)}</strong>${item.photogenic ? " ✦" : ""} · ${escapeHtml(item.site)} · ~${escapeHtml(driveLabel(Math.round(item.drive_hours * 60)))}<br><span>Still findable: ${item.encounter_confidence}/100 (a ranking, not a probability) · ${escapeHtml(item.why)}</span>${safeExternalUrl(item.url) ? ` <a href="${escapeHtml(safeExternalUrl(item.url))}" target="_blank" rel="noopener noreferrer">${/ebird\.org\/checklist/.test(item.url) ? "eBird checklist" : "report"}</a>` : ""}</li>`).join("");
    return `<div class="cm-card">
      <div class="cm-heading"><span>Birds</span><span class="cm-sub">spectacle · encounter · chase</span></div>
      ${this._freshnessHtml({ generated: board.generated, events: board.birds.spectacle, unavailable: board.unavailable }, now, "Bird view")}
      <h4 class="cm-section">Spectacle</h4>${spectacle || `<p class="cm-none">No bird spectacle confirmed this week.</p>`}
      <details class="cm-background" data-section="birds-encounter" ${board.birds.encounter.length ? "open" : ""}><summary>Encounters · ${board.birds.encounter.length}</summary>
        <p>Iconic birds reported repeatedly at a public viewing area, without confirmed behaviour.</p>${encounter ? `<ul>${encounter}</ul>` : `<p class="cm-none">None this week.</p>`}</details>
      <details class="cm-background" data-section="birds-chase"><summary>Bird chase · ${board.birds.chase.length}</summary>
        <p>Notable individual birds. Worth it if you want the species; a single report is often gone by the time you arrive. Private locations are never listed.</p>${chase ? `<ul>${chase}</ul>` : `<p class="cm-none">No reachable notable birds reported in the last 48 hours.</p>`}</details>
      ${healthStripHtml(board.sources)}
    </div>`;
  },
};
