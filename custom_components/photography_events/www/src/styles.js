const CARD_STYLES = `
      .source-health { margin: 10px 0; font-size: .82rem; }
      .source-health summary { cursor: pointer; }
      .source-health-entry { margin: 10px 0; line-height: 1.5; }
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
      .hero-deadline { margin-top: 12px; }
      .hero-deadline-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .07em;
        color: var(--pe-muted);
      }
      .hero-deadline-value { font-size: 21px; font-weight: 600; line-height: 1.25; }
      .hero-deadline-count {
        font-size: 13px;
        font-variant-numeric: tabular-nums;
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
      .outlook-month.urgent .outlook-month-label { color: var(--pe-epic); }
      .outlook-month-count {
        margin-left: 6px;
        font-weight: 500;
        opacity: .6;
      }
      .outlook-tag.where { font-weight: 500; }
      .outlook-tag.more { opacity: .75; }
      .outlook-alts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
      .outlook-alts-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: .06em;
        color: var(--pe-muted);
      }
      .outlook-alt {
        font-size: 12px;
        padding: 3px 9px;
        border-radius: 999px;
        background: rgba(255, 255, 255, .06);
      }
      .outlook-alt em { font-style: normal; opacity: .65; }
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
      .outlook-row { display: block; }
      .outlook-row.open { background: rgba(255, 255, 255, .03); border-radius: 8px; }
      .outlook-head.simple-row { width: 100%; align-items: center; padding: 12px 8px; }
      .simple-row .outlook-body { display: flex; flex-direction: column; gap: 4px; }
      .simple-row .outlook-meta { font-size: 12px; color: var(--pe-muted); }
      .event-controls, .event-toolbar { display: flex; gap: 8px; margin: 10px 0; flex-wrap: wrap; }
      .event-controls button, .event-toolbar button {
        color: var(--pe-text); background: rgba(255,255,255,.06); border: 1px solid var(--pe-border);
        border-radius: 8px; padding: 8px 12px; cursor: pointer; font: inherit; font-size: 12px;
      }
      .event-controls button[aria-pressed="true"] { border-color: var(--pe-excellent); }
      .event-error, .source-warning { padding: 8px 14px; color: var(--warning-color, #dca54c); font-size: 12px; }
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
      .outlook-row { border-left: 3px solid var(--event-color); padding: 0 0 0 10px; }
      .outlook-head.simple-row { padding: 13px 0; gap: 9px; }
      .outlook-title { font-size: 15px; line-height: 1.35; }
      .outlook-meta { font-size: 12px; margin-top: 4px; }
      .outlook-badge { font-size: 11px; white-space: normal; }
      .week-heading { display:flex; justify-content:space-between; gap:12px; font-weight:700; margin-bottom:12px; }
      .week-heading span, .calendar-note { color:var(--secondary-text-color); font-size:12px; font-weight:400; }
      .week-card .outlook-detail { font-size:13px; }
      .week-card .outlook-row { margin-bottom:3px; }
      .outlook-month-label { cursor:pointer; padding:12px 0; }
      .outlook-month:not([open]) { margin-bottom:12px; }
      .outlook { overflow-anchor:none; }
      .location-option { padding:12px; margin:8px 0; border:1px solid var(--divider-color); border-radius:10px; line-height:1.6; }
      .location-option div { font-size:13px; color:var(--secondary-text-color); }
      .night-option summary { cursor:pointer; padding:10px 0; }
      .night-comparison p { line-height:1.6; }
      .category-dot { width:10px; height:10px; border-radius:3px; flex-shrink:0; }
      .event-toolbar { display:flex; flex-wrap:wrap; gap:8px; }
      .event-toolbar button[aria-pressed="true"] { border-color:var(--primary-color); }
      .calendar-nav { display:flex; align-items:center; justify-content:space-between; margin:16px 0; }
      .calendar-nav button { padding:8px 18px; cursor:pointer; }
      .calendar-grid { border:1px solid var(--divider-color); border-radius:8px; overflow:hidden; }
      .calendar-days,.calendar-bars { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:3px; }
      .calendar-days { text-align:center; font-size:11px; color:var(--secondary-text-color); padding:6px 0; }
      .calendar-week { min-height:72px; border-top:1px solid var(--divider-color); padding:3px; }
      .calendar-date.outside { opacity:.4; }
      .calendar-bars { grid-auto-rows:24px; }
      .calendar-event { background:color-mix(in srgb,var(--event-color) 20%,var(--card-background-color,#222)); color:var(--primary-text-color); border:0; border-left:3px solid var(--event-color); border-radius:3px; font:inherit; font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; text-align:left; padding:3px 5px; cursor:pointer; }
      .event-dialog { color:var(--primary-text-color); background:var(--card-background-color,#222); border:1px solid var(--divider-color); border-radius:16px; width:min(620px,calc(100vw - 48px)); max-height:80vh; padding:20px; }
      .event-dialog::backdrop { background:#0009; }
      .dialog-close { float:right; padding:8px 12px; cursor:pointer; }
      @media(max-width:450px) { .card-content { padding:16px; } .simple-row .outlook-badge { max-width:76px; } .outlook-detail-grid { grid-template-columns:1fr; } .outlook-detail-grid dd { margin:0 0 9px; } }

    `;
