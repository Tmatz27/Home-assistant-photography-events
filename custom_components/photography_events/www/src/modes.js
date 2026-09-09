const CARD_MODES = {
  _bodyHtml() {
    if (this._config.mode === MODE_HERO) return this._outlookEntityId() ? this._weekHtml() : this._heroHtml();
    if (this._config.mode === MODE_OUTLOOK || this._outlookEntityId()) return this._outlookHtml();
    // Installed integrations share one event truth, even for older dashboard
    // configs. The legacy calculator remains only for standalone installations.

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
  },

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
  },

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
  },

  _emptyTimelineHtml() {
    return `
      <div class="empty-card">
        <ha-icon icon="mdi:weather-night-partly-cloudy"></ha-icon>
        <strong>No notable photography events</strong>
        <span>Nothing stands out in the next ${this._config.outlook_days} days for the event types you've enabled.</span>
      </div>
    `;
  },

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
  },

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
  },

  _footerHtml() {
    const notes = [];
    if (this._weatherMissing) {
      notes.push("The configured weather entity was not found, so sky-quality scoring is unavailable.");
    } else if (!this._config.weather_entity) {
      notes.push("Add a weather entity in the card editor to score sunset/sunrise color potential.");
    }
    notes.push("Meteor shower, eclipse, and migration data are approximate - verify close to the date.");
    return `<div class="footer">${notes.map((note) => `<div>${escapeHtml(note)}</div>`).join("")}</div>`;
  },


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
          <span>Worth planning for</span>
        </div>

        <div class="hero-title">${escapeHtml(hero.name)}</div>
        ${this._heroDeadlineHtml(hero, now)}
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
            <div class="hero-stat-label">Priority score</div>
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

        ${this._eventControlsHtml(hero.id, this._hass.states[this._outlookEntityId()]?.attributes?.preferences?.[hero.id]?.choice)}
        ${this._choiceError ? `<div role="alert">${escapeHtml(this._choiceError)}</div>` : ""}
        ${this._activeMonthHtml(now)}
      </div>
    `;
  },

  /**
   * When to be standing there, and how long you have to get there.
   *
   * A bare "in 45h" is not something anybody can plan against: it cannot be put
   * in a calendar, it reads differently depending on when you happen to glance
   * at the card, and it makes you do the arithmetic that the card already did.
   * The date and time are the instruction; the countdown sits under it as
   * context. A multi-day window shows its range instead, because "be set up by"
   * is a lie about a fortnight-long peak.
   */
  _heroDeadlineHtml(hero, now) {
    if (!hero.starts) {
      return `<div class="hero-deadline"><div class="hero-deadline-value">Starting shortly</div></div>`;
    }
    const multiDay = hero.ends && hero.ends - hero.starts > 36 * 3600000;
    const target = hero.starts;
    const value = multiDay
      ? `${dateLabel(hero.starts)} \u2013 ${dateLabel(hero.ends)}`
      : `${dateLabel(target)} \u00b7 ${clockLabel(target)}`;

    return `
      <div class="hero-deadline">
        <div class="hero-deadline-label">${multiDay ? "Window" : "Window opens"}</div>
        <div class="hero-deadline-value">${escapeHtml(value)}</div>
        <div class="hero-deadline-count">${escapeHtml(countdownLabel(now, target))}</div>
      </div>
    `;
  },

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
  },

  /**
   * What else is running right now. The hero answers "tonight"; this answers
   * "and while you are out there", which is how one drive becomes two subjects.
   */
  _activeMonthHtml(now) {
    const state = this._hass.states[this._outlookEntityId()];
    if (!state) return "";
    const outlook = outlookFromState(state);
    const running = outlook.events
      .filter((event) => event.precision === "peak" &&
        outlook.preferences[event.event_id || event.roll || event.key]?.choice !== "skip")
      .map((event) => ({ ...event, startDate: parseEventDate(event.start), endDate: parseEventDate(event.end) || parseEventDate(event.start) }))
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
  },

  // --- calendar_outlook -----------------------------------------------------

  _groupEvents(events) {
    const grouped = consolidateNights(rollUpByPlace(events));
    for (const event of grouped) {
      this._displayEvents.set(event.key, event);
      if (event.choiceIds) this._choiceGroups.set(event.event_id || event.roll || event.key, event.choiceIds);
    }
    return grouped;
  },

  _weekHtml() {
    const state = this._hass.states[this._outlookEntityId()];
    if (!state) return this._setupHtml("Planning sensor unavailable", "Check the Photography Events integration.");
    const outlook = outlookFromState(state);
    const now = new Date();
    const weekEnd = new Date(now.getTime() + 7 * MS_PER_DAY);
    const visible = outlook.events.filter(e => outlook.preferences[e.event_id || e.roll || e.key]?.choice !== "skip");
    // Group before cutting to seven days: a later best night must not disappear
    // from a period already underway this week.
    const events = this._groupEvents(filterOutlook(visible, { now, fromDays: 0, throughDays: 365 }))
      .filter(e => e.startDate <= weekEnd && e.endDate >= now)
      .sort((a, b) => (b.score || 0) - (a.score || 0));
    return `<div class="week-card"><div class="week-heading">Next seven days <span>${events.length} opportunities</span></div>
      ${this._choiceError ? `<div role="alert">${escapeHtml(this._choiceError)}</div>` : ""}
      ${events.length ? events.map(e => this._outlookRowHtml(e, outlook, now)).join("") : '<p class="empty-week">No special opportunities reported yet.</p>'}
      ${healthStripHtml(outlook.sources)}
      </div>`;
  },

  _nightComparisonHtml(event) {
    if (!event.nights) return "";
    const best = event.bestNight;
    const forecast = event.nightOptions.filter(e => Number.isFinite(e.cloud_cover) && e.cloud_is_forecast === true);
    const outlookBest = event.nightOptions.filter(e => Number.isFinite(e.cloud_cover) && e.cloud_is_forecast === false)
      .sort((a,b) => (b.score || 0) - (a.score || 0))[0];
    const geometry = [...event.nightOptions].sort((a,b) => (b.duration_minutes || 0) - (a.duration_minutes || 0) ||
      (a.moon_illumination ?? 1) - (b.moon_illumination ?? 1))[0];
    const weatherBest = [...forecast].sort((a,b) => (b.score || 0) - (a.score || 0) ||
      (b.duration_minutes || 0) - (a.duration_minutes || 0))[0];
    return `<section class="night-comparison"><h4>Which night?</h4>
      <p>${event.nights.length} available nights, ${escapeHtml(rangeLabel(event.startDate, event.endDate))}.
      Highest ranked: <strong>${escapeHtml(dateLabel(parseEventDate(best.start)))}</strong> at ${escapeHtml(best.where || best.zone)}.
      Tied scores favor a longer usable window.</p>
      <p>Longest calculated window: ${escapeHtml(dateLabel(parseEventDate(geometry.start)))} (${geometry.duration_minutes || "—"} min).
      ${weatherBest ? `Best with a cloud forecast: ${escapeHtml(dateLabel(parseEventDate(weatherBest.start)))} at ${escapeHtml(weatherBest.where || weatherBest.zone)} (${weatherBest.cloud_cover}% cloud).` : "No cloud forecast is available for these nights yet."}
      ${outlookBest ? `Best with a longer-range cloud outlook: ${escapeHtml(dateLabel(parseEventDate(outlookBest.start)))} (${outlookBest.cloud_cover}% cloud; lower confidence).` : ""}
      Calculated coverage${best.comparison_through ? ` through ${escapeHtml(dateLabel(parseEventDate(best.comparison_through)))}` : " is limited to the supplied nights"}. The end of the displayed range may be the calculation limit, not the end of the season. Forecasts can change the preferred date.</p>
      ${event.nights.map(night => `<details class="night-option"><summary>${escapeHtml(dateLabel(parseEventDate(night.start)))} · priority ${night.score} · ${night.duration_minutes || "—"} min</summary>
        <p>${escapeHtml(nightTradeoffs(night, best))}</p>
        ${[night, ...(night.alternatives || [])].map(location => this._locationHtml(location)).join("")}</details>`).join("")}
      <p>Follow / Skip applies to all listed nights. Weather and available nights update as new forecasts arrive.</p></section>`;
  },

  _locationHtml(event) {
    const dates = !event.all_day && String(event.start).includes("T") ?
      `${absoluteLabel(parseEventDate(event.start))} to ${absoluteLabel(parseEventDate(event.end))}` :
      rangeLabel(parseEventDate(event.start), parseEventDate(event.end));
    return `<section class="location-option"><strong>${escapeHtml(event.where || event.zone || "Viewing location")}</strong>
      <div>${escapeHtml(dates)}</div>
      ${Number.isFinite(event.drive_hours) && event.drive_hours > 0 ? `<div>Approximate drive: ${escapeHtml(driveLabel(Math.round(event.drive_hours * 60)))}</div>` : ""}
      <div>${escapeHtml(event.evidence_note || event.awaiting || event.detail || "")}</div>
      ${Number.isFinite(event.cloud_cover) ? `<div>${cloudLabel(event)}: ${event.cloud_cover}%${event.cloud_confidence ? ` · ${escapeHtml(event.cloud_confidence)}` : ""}</div>` : ""}
      ${event.source_health_note ? `<div class="source-warning">${escapeHtml(event.source_health_note)}</div>` : ""}
      ${event.observed_at ? `<div>Observed ${escapeHtml(absoluteLabel(parseEventDate(event.observed_at)))}</div>` : ""}
      ${reportLinkHtml(event)}</section>`;
  },

  _calendarHtml(events, now) {
    const month = new Date(now.getFullYear(), now.getMonth() + this._calendarOffset, 1);
    const first = new Date(month); first.setDate(1 - first.getDay());
    const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
    const weeks = [];
    for (let start = new Date(first); start <= last; start.setDate(start.getDate() + 7)) {
      const segments = calendarSegments(events, start);
      const days = Array.from({ length: 7 }, (_, i) => {
        const day = new Date(start); day.setDate(day.getDate() + i);
        return `<span class="calendar-date ${day.getMonth() === month.getMonth() ? "" : "outside"}">${day.getDate()}</span>`;
      }).join("");
      weeks.push(`<div class="calendar-week"><div class="calendar-days">${days}</div><div class="calendar-bars">
        ${segments.map(({event, start: left, end, lane}) => `<button type="button" class="calendar-event" data-open="${escapeHtml(event.key)}"
          style="--event-color:${categoryColor(event.category)};grid-column:${left + 1}/${end + 2};grid-row:${lane + 1}"
          title="${escapeHtml(event.title)} · ${escapeHtml(rangeLabel(event.startDate, event.endDate))}">${escapeHtml(event.title.replace(/ at .+$/, "").replace(/ \(season\)$/, ""))}</button>`).join("")}
      </div></div>`);
    }
    return `<div class="calendar-nav"><button type="button" data-month="-1" ${this._calendarOffset === 0 ? "disabled" : ""} aria-label="Previous month">‹</button>
      <strong>${MONTH_NAMES[month.getMonth()]} ${month.getFullYear()}</strong>
      <button type="button" data-month="1" ${this._calendarOffset === 12 ? "disabled" : ""} aria-label="Next month">›</button></div>
      <p class="calendar-note">Bars show planning windows, not confirmed activity. Open an event for its evidence and dates.</p>
      <div class="calendar-grid"><div class="calendar-days">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d => `<span>${d}</span>`).join("")}</div>${weeks.join("")}</div>`;
  },

  _openCalendarEvent(key) {
    const event = this._displayEvents.get(key);
    if (!event) return;
    const outlook = outlookFromState(this._hass.states[this._outlookEntityId()]);
    const dialog = document.createElement("dialog");
    dialog.className = "event-dialog";
    dialog.setAttribute("aria-labelledby", "pe-dialog-title");
    dialog.innerHTML = `<button class="dialog-close" type="button" aria-label="Close event details">Close ×</button><h3 id="pe-dialog-title">${escapeHtml(event.title.replace(/ at .+$/, ""))}</h3>
      ${this._outlookDetailHtml(event, outlook, event.planning_only ? outlook.parks[event.zone_id] : null, new Date())}`;
    this.shadowRoot.appendChild(dialog);
    dialog.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => dialog.remove());
    for (const button of dialog.querySelectorAll("[data-choice]")) button.addEventListener("click", async () => {
      await this._saveChoice(button.dataset.eventid, button.dataset.choice);
      if (!this._choiceError) dialog.close();
      else button.textContent = this._choiceError;
    });
    dialog.showModal();
  },

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

    const visible = outlook.events.filter(event => this._showSkipped ||
      outlook.preferences[event.event_id || event.roll || event.key]?.choice !== "skip");
    const events = filterOutlook(visible, { allowed, now, fromDays: 0, throughDays: 365 });
    const from = new Date(now.getTime() + this._config.outlook_from_days * MS_PER_DAY);
    const through = new Date(now.getTime() + this._config.outlook_through_days * MS_PER_DAY);
    const grouped = this._groupEvents(events).filter(event => event.endDate >= from && event.startDate <= through);
    const groups = groupByUrgency(grouped, now);

    return `
      <div class="header">
        <div class="header-title">${escapeHtml(this._config.title)}</div>
        <div class="header-subtitle">
          ${grouped.length} opportunities,
          next ${this._config.outlook_through_days} days
          ${outlook.truncated ? " (list truncated)" : ""}
        </div>
      </div>
      ${this._filterChipsHtml(known, allowed)}
      <div class="event-toolbar"><button type="button" data-view="list" aria-pressed="${!this._calendarView}">List</button><button type="button" data-view="calendar" aria-pressed="${this._calendarView}">Calendar</button><button type="button" data-skipped="toggle" aria-pressed="${this._showSkipped}">
        ${this._showSkipped ? "Hide skipped" : "Show skipped"}</button></div>
      ${this._choiceError ? `<div role="alert" class="event-error">${escapeHtml(this._choiceError)}</div>` : ""}
      ${healthStripHtml(outlook.sources)}
      ${this._calendarView ? this._calendarHtml(grouped, now) : groups.length
        ? `<div class="outlook">${groups.map((group) => this._monthHtml(group, outlook, now)).join("")}</div>`
        : `<div class="empty-card">
             <ha-icon icon="mdi:calendar-blank-outline"></ha-icon>
             <strong>Nothing in this window</strong>
             <span>Every category may be switched off, or the range may be too narrow.</span>
           </div>`}
      ${this._legendHtml()}
    `;
  },

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
  },

  _monthHtml(group, outlook, now) {
    return `
      <details class="outlook-month${group.urgent ? " urgent" : ""}" data-bucket="${escapeHtml(group.key)}" ${this._collapsed.has(group.key) ? "" : "open"}>
        <summary class="outlook-month-label">
          ${escapeHtml(group.label)}
          <span class="outlook-month-count">${group.events.length}</span>
        </summary>
        ${group.events.map((event) => this._outlookRowHtml(event, outlook, now)).join("")}
      </details>
    `;
  },

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
    // A sky that nothing in the forecast window beats. The score alone cannot
    // say that, and it is the only version of the question worth answering.
    const best = event.standout ? `<span class="outlook-badge peak">Best of the week</span>` : "";
    return `${best}<span class="outlook-badge ${tone}">${event.score}% score</span>`;
  },

  _outlookRowHtml(event, outlook, now) {
    const park = event.planning_only ? outlook.parks[event.zone_id] : null;
    const expanded = this._expanded.has(event.key);
    const choice = outlook.preferences[event.event_id || event.roll || event.key]?.choice || "default";
    const locations = event.locations || (park ? [park.name] : [event.where || event.zone]);
    const total = new Set([...locations, ...(event.alternatives || []).map(e => e.where || e.zone)].filter(Boolean)).size;
    const where = total > 1 ? `${total} locations` : locations[0] || "";
    const status = choice === "skip" ? "Skipped" : choice === "follow" ? "Following" :
      VERIFICATION_META[event.verification]?.label || (event.precision === "season" || park ? "Season" : "Calculated / forecast");
    const title = event.roll ? event.title.replace(/ at .+$/, "") : event.title.replace(/ \(season\)$/, "");
    return `<div class="outlook-row ${expanded ? "open" : ""}" style="--event-color:${categoryColor(event.category)}">
      <button type="button" class="outlook-head simple-row" data-expand="${escapeHtml(event.key)}" aria-expanded="${expanded}">
        <span class="outlook-body"><span class="outlook-title">${escapeHtml(title)}</span>
          <span class="outlook-meta">${escapeHtml(rangeLabel(event.startDate, event.endDate))}${event.precision === "season" ? " · Typical peak" : ""} · ${escapeHtml(where)}${event.nights ? ` · ${event.nights.length} nights · Preferred ${dateLabel(parseEventDate(event.bestNight.start))}` : ""}</span></span>
        <span class="outlook-badge season">${escapeHtml(status)}${[event, ...(event.nightOptions || event.alternatives || [])].some(e => e.degraded_sources?.length) ? " · Data degraded" : ""}</span>
        <ha-icon icon="${expanded ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon>
      </button>
      ${expanded ? this._outlookDetailHtml(event, outlook, park, now) : ""}
    </div>`;
  },

  _outlookDetailHtml(event, outlook, park, now) {
    const rows = [];
    if (event.source_health_note) rows.push(["Data degraded", event.source_health_note]);
    rows.push(["Priority", `${event.score}/100 — ranking, not a probability`]);
    const drives = [event, ...(event.nightOptions || event.alternatives || [])].map(e => e.drive_hours).filter(d => Number.isFinite(d) && d > 0);
    if (drives.length || park?.drive_label) rows.push([drives.length > 1 ? "Closest approximate drive" : "Approximate drive", drives.length ? driveLabel(Math.round(Math.min(...drives) * 60)) : park.drive_label]);
    if (event.category === "sunset") rows.push(["Weather source", "Open-Meteo low, middle and high cloud forecasts, with the upstream light path checked when available. Forecast layers, not measured cloud heights; no Pirate Weather entity required."]);
    if (event.observed_at) rows.push(["Observed", absoluteLabel(parseEventDate(event.observed_at))]);
    if (event.evidence_note) rows.push(["Evidence", event.evidence_note]);
    if (event.closures?.length) rows.push(["Closures", event.closures.join("; ")]);
    if (event.coastal_advisories?.length) rows.push(["Coastal advisories", event.coastal_advisories.join("; ")]);
    if (event.closure_source) rows.push(["Access check", event.closure_source]);
    if (event.access_note) rows.push(["Access", event.access_note]);
    if (event.tide_window_start && event.tide_window_end) rows.push(["Tide window", `${absoluteLabel(parseEventDate(event.tide_window_start))} to ${absoluteLabel(parseEventDate(event.tide_window_end))}`]);
    if (event.measurement_label) rows.push([event.measurement_label, [Number.isFinite(event.wave_height_m) ? `${event.wave_height_m} m` : "Height unknown", Number.isFinite(event.wave_period_s) ? `${event.wave_period_s} s` : "", Number.isFinite(event.wave_direction_deg) ? `from ${event.wave_direction_deg}°` : ""].filter(Boolean).join(" · ")]);
    if (event.forecast_note) rows.push(["Forecast", event.forecast_note]);
    if (event.confidence_note) rows.push(["Limits", event.confidence_note]);

    if (event.precision === "season") {
      rows.push(["Extended season", event.season_range || "-"]);
      rows.push(["Peak window",
        `${rangeLabel(event.startDate, event.endDate)} - specifics firm up inside ${outlook.horizonDays} days`]);
    } else {
      rows.push([event.nights ? "Highest-ranked night" : "Window", !event.all_day && String(event.start).includes("T") ? `${absoluteLabel(parseEventDate(event.start))} to ${absoluteLabel(parseEventDate(event.end))}` : rangeLabel(event.startDate, event.endDate)]);
      if (event.season_range) rows.push(["Extended season", event.season_range]);
    }
    if (event.duration_minutes) {
      const limit = WINDOW_LIMIT_REASON[event.limited_by] || "";
      rows.push(["Usable window", `${event.duration_minutes} min${limit ? ` - ${limit}` : ""}`]);
    }
    if (!event.nights && (event.precision === "season" || ["watching", "unverified", "presence_only"].includes(event.verification))) {
      rows.push(["Preferred days & alternatives", "No evidence-backed ideal day yet. The full seasonal range and typical peak are planning guides; an alternate day is not known to be worse. " + (event.awaiting || "Current reports of the named phenomenon are needed before choosing dates.")]);
    }
    if (event.best_time_of_day) rows.push(["Best time of day", event.best_time_of_day]);

    const locations = event.locations || [event.where || event.zone || park?.name].filter(Boolean);
    if (locations.length) rows.push(["Where", locations.join(" - ")]);

    const gear = event.gear || outlook.gear?.[event.category]?.glass;
    if (gear) rows.push(["Gear", gear]);
    const support = outlook.gear?.[event.category]?.support;
    if (support && !event.gear) rows.push(["Support", support]);

    if (park) rows.push(["Dogs", park.dog_detail]);

    // The row that stops a trip being booked against a date nothing confirms.
    const verification = VERIFICATION_META[event.verification];
    if (verification) {
      rows.push(["Confirmed?", `${verification.label} - ${event.awaiting || verification.text}`]);
    }
    if (event.light_path === "local") {
      rows.push(["Light path", "Not checked - scored from local cloud only, so treat the number as optimistic."]);
    }

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
        ${this._nightComparisonHtml(event)}
        ${!event.nights && event.alternatives?.length ? `<section class="location-options"><h4>Locations & reports</h4>${[event, ...event.alternatives].map(location => this._locationHtml(location)).join("")}</section>` : ""}
        ${this._eventControlsHtml(event.event_id || event.roll || event.key,
          outlook.preferences[event.event_id || event.roll || event.key]?.choice)}
        ${!event.alternatives?.length && !event.nights ? reportLinkHtml(event) : ""}
        ${Array.isArray(event.verify) && event.verify.length ? `
          <div class="outlook-verify">
            <span class="outlook-verify-label">Check before you book</span>
            ${event.verify.filter(url => safeExternalUrl(url)).map((url) => `
              <a href="${escapeHtml(safeExternalUrl(url))}" target="_blank" rel="noopener noreferrer">
                <ha-icon icon="mdi:check-decagram-outline"></ha-icon>${escapeHtml(sourceLabel(url))}
              </a>`).join("")}
          </div>` : ""}
      </div>
    `;
  },

  _legendHtml() {
    return `<div class="pe-legend"><span>Color = event type. Labels describe the evidence; scores rank priority.</span>
      ${Object.entries(CATEGORY_META).map(([category, meta]) => `<span class="pe-legend-item"><span class="category-dot" style="background:${categoryColor(category)}"></span>${escapeHtml(meta.label)}</span>`).join("")}</div>`;
  },

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
  },

  _setupHtml(title, message) {
    return `
      <div class="empty-card">
        <ha-icon icon="mdi:cog-outline"></ha-icon>
        <strong>${escapeHtml(title)}</strong>
        <span>${message}</span>
      </div>
    `;
  },

};
