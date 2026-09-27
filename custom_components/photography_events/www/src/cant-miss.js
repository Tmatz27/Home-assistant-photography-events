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
    signals: Array.isArray(attributes.signals) ? attributes.signals : [],
    signalCount: Number(attributes.signal_count) || 0,
    birds: {
      spectacle: Array.isArray(birds.spectacle) ? birds.spectacle : [],
      encounter: Array.isArray(birds.encounter) ? birds.encounter : [],
      chase: Array.isArray(birds.chase) ? birds.chase : [],
    },
    headline: attributes.headline || "",
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

/** Where, and how far, in the words a person would use. */
function whereLabel(row) {
  const place = row.where || row.zone || "";
  const hours = Number(row.drive_hours);
  if (!Number.isFinite(hours) || hours <= 0.05) return place ? `${place} · at home` : "At home";
  return `${place} · ~${driveLabel(Math.round(hours * 60))} drive`;
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
      ${events.length ? shown.map(row => this._cantMissRowHtml(row, board, now)).join("") +
        (events.length > board.showLimit ? `<button type="button" class="show-more" data-more="cant-miss" aria-expanded="${all}">${all ? "Show fewer" : `Show ${events.length - board.showLimit} more`}</button>` : "")
        : this._cantMissEmptyHtml(board, stale)}
      ${this._backgroundHtml(board, now)}
      ${healthStripHtml(board.sources)}
    </div>`;
  },

  _cantMissEmptyHtml(board, stale) {
    if (stale) {
      return `<div class="cm-empty cm-empty-stale" role="status"><strong>Can't Miss is not up to date.</strong>
        <span>Waiting for a successful update. An empty list here is not evidence of a quiet week.</span></div>`;
    }
    const watched = board.watch.length;
    return `<div class="cm-empty" role="status"><ha-icon icon="mdi:check-circle-outline"></ha-icon>
      <strong>${escapeHtml(board.headline || "Nothing worth changing plans for this week.")}</strong>
      <span>${watched ? `${watched} phenomen${watched === 1 ? "on is" : "a are"} being watched below.` : "Nothing is building either."} The year planner still lists every season.</span></div>`;
  },

  _cantMissRowHtml(row, board, now) {
    const key = row.key;
    const expanded = this._expanded.has(key);
    const take = shortLens(row.gear_plan?.take || row.gear || "");
    const best = row.best_time_of_day ? ` · ${row.best_time_of_day}` : "";
    const warn = (row.safety_notes || []).length || row.source_health_note;
    return `<div class="cm-row ${expanded ? "open" : ""}" style="--event-color:${categoryColor(row.category)}">
      <button type="button" class="cm-head" data-expand="${escapeHtml(key)}" aria-expanded="${expanded}">
        <span class="cm-title">${escapeHtml(String(row.title || "").replace(/ \(season\)$/, ""))}</span>
        <span class="cm-where">${escapeHtml(whereLabel(row))}</span>
        ${row.why_now ? `<span class="cm-why">${escapeHtml(row.why_now)}</span>` : ""}
        <span class="cm-when">${escapeHtml(whenLabel(row, now))}${escapeHtml(best)}</span>
        <span class="cm-status">${escapeHtml(row.status || "")}${warn ? " · check notes" : ""}</span>
        ${take ? `<span class="cm-take">Take: ${escapeHtml(take)}</span>` : ""}
      </button>
      ${expanded ? this._cantMissDetailHtml(row, board, now) : ""}
    </div>`;
  },

  _cantMissDetailHtml(row, board, now) {
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
    if (row.moonrise) {
      dates.push(["Moonrise", `${absoluteLabel(parseEventDate(row.moonrise))} · ${row.moonrise_azimuth}° ${row.moonrise_compass}`],
        ["Sunset", row.sunset_at ? absoluteLabel(parseEventDate(row.sunset_at)) : ""],
        ["Moon climb", (row.moon_climb || []).map(step => `${step.altitude}° ${clockLabel(parseEventDate(step.time))} ${step.compass}`).join(" · ")],
        ["Distance", row.distance_km ? `${Number(row.distance_km).toLocaleString()} km · ${row.diameter_arcmin}′` : ""],
        ["Facts", (row.moon_labels || []).join(". ")]);
    }
    if (row.color_window_start) dates.push(["Colour window", `${clockLabel(parseEventDate(row.color_window_start))} – ${clockLabel(parseEventDate(row.color_window_end))}`]);
    const evidence = [["Status", row.status], ["Significance", row.significance != null ? `${row.significance}/100 — how extraordinary, not how likely` : ""],
      ["Confidence", row.confidence != null ? `${row.confidence}/100 · ${row.confidence_basis || ""}` : ""],
      ["Policy", (row.policy || "").replace(/_/g, " ")], ["Encounter", row.encounter],
      ["Forecast source", row.provider_note], ["Local sky model", row.light_path ? `${row.light_path === "modelled" ? "light path modelled" : "local cloud only"}` : ""],
      ["Still needed / limits", row.awaiting], ["Observed", row.observed_at ? absoluteLabel(parseEventDate(row.observed_at)) : ""],
      ["Data degraded", row.source_health_note]];
    const reports = (row.behavior_evidence || []).map(report => `<p class="cm-report">${escapeHtml(report.source || "Report")}${report.observed_at ? ` · ${escapeHtml(absoluteLabel(parseEventDate(report.observed_at)))}` : ""}: “${escapeHtml(report.text || "")}”${safeExternalUrl(report.url) ? ` <a href="${escapeHtml(safeExternalUrl(report.url))}" target="_blank" rel="noopener noreferrer">source</a>` : ""}</p>`).join("");
    const urls = [...new Set([...(Array.isArray(row.verify) ? row.verify : []), row.source_url].map(safeExternalUrl).filter(Boolean))];
    const links = urls.map(url => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(sourceLabel(url))}</a>`).join("");
    const gear = [["Take", shortLens(plan.take)], ["Optional", (plan.optional || []).map(shortLens).join("; ")],
      ["Skip", (plan.skip || []).map(shortLens).join("; ")], ["Start with", plan.start], ["Support", plan.support],
      ["Technique", plan.technique], ["Video", shortLens(plan.video)], ["Drone", plan.drone]];
    const access = [["Where", row.where || row.zone], ["Approximate drive", Number(row.drive_hours) > 0.05 ? `${driveLabel(Math.round(row.drive_hours * 60))} (${row.drive_source === "estimate" ? "estimated" : row.drive_source})` : "At home"],
      ["Access", row.access_note], ["Safety", [row.safety_summary, ...(row.safety_notes || [])].filter(Boolean).join(" ")],
      ["Wildlife ethics", row.ethics], ["Closures", (row.closures || []).join("; ")]];
    return `<div class="outlook-detail">
      ${row.detail ? `<p class="event-intro">${escapeHtml(row.detail)}</p>` : ""}
      ${this._eventControlsHtml(row.event_id || row.key, board.preferences[row.event_id || row.key]?.choice)}
      ${section("evidence", "Evidence & sources", list(evidence) + reports + reportLinkHtml(row) + `<div class="outlook-verify">${links}</div>`)}
      ${section("dates", "Dates & timing", list(dates))}
      ${this._config.show_gear !== false ? section("gear", "Gear & technique", list(gear)) : ""}
      ${section("access", "Access, safety & ethics", list(access))}
    </div>`;
  },

  /** One collapsed section for everything that is building but not yet a reason to go. */
  _backgroundHtml(board, now) {
    const total = board.watch.length + board.signals.length;
    if (!total) return "";
    const watch = board.watch.map(item => `<li><strong>${escapeHtml(item.title)}</strong> · ${escapeHtml(item.status || "")}<br><span>${escapeHtml(item.awaiting || "")}</span></li>`).join("");
    const signals = board.signals.map(signal => {
      const stamp = parseEventDate(signal.observed_at || signal.valid_at);
      const url = safeExternalUrl(signal.url);
      const basis = signal.basis === "reported_undated" ? "undated report" : signal.basis;
      return `<li>${escapeHtml(signal.subject)}${signal.place ? ` · ${escapeHtml(signal.place)}` : ""} · ${escapeHtml(basis)}${stamp ? ` · ${escapeHtml(absoluteLabel(stamp))}` : ""}${url ? ` · <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">source</a>` : ""}</li>`;
    }).join("");
    return `<details class="cm-background" data-section="cant-miss-background"><summary>Watching ${total} background signal${total === 1 ? "" : "s"}</summary>
      <p>Evidence that something may be building. None of it is a reason to go on its own; a sighting is a signal, not an event.</p>
      ${watch ? `<h4>Phenomena being watched</h4><ul>${watch}</ul>` : ""}
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
