/** Photography Events read-only Core card. Generated from www/src.
 * Copyright (c) 2026 Travis Matzdorf. SPDX-License-Identifier: MIT
 * No browser provider requests or opportunity calculation.
 */
const CARD_VERSION = "0.17.0-dev.1";

// Cosmetic constants only. No catalogs, providers, sky math or fallback engine.
const MODE_HERO = "action_hero", MODE_OUTLOOK = "calendar_outlook", MODE_BIRDS = "birds", MODE_TIMELINE = "timeline";
const BACKEND_MODES = new Set([MODE_HERO, MODE_OUTLOOK, MODE_BIRDS, "watching"]);
const CORE_VIEW = { action_hero: "cant_miss", watching: "watching", calendar_outlook: "planner", timeline: "planner", birds: "birds" };
const CATEGORY_TOGGLE_KEYS = [];
const CORE_TRANSPORT_MS = 15 * 60000, CORE_ASSESSMENT_MS = 6 * 3600000;
const DEFAULT_CONFIG = Object.freeze({title: "Photography Events", mode: MODE_HERO, entry_id: ""});
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c])); }
function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }
function coreDate(value) { const d = new Date(value); return Number.isFinite(d.getTime()) ? d.toLocaleString() : "Unknown"; }

class PhotographyEventsCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); }
  setConfig(config) { this._config = {title:typeof config.title==="string"?config.title.slice(0,256):DEFAULT_CONFIG.title,
    mode:Object.hasOwn(CORE_VIEW,config.mode)?config.mode:MODE_HERO,entry_id:typeof config.entry_id==="string"?config.entry_id.slice(0,128):""}; this._render(); }
  set hass(value) { this._hass = value; this._render(); }
  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `<style>label{display:block;margin:16px 0}input,select{display:block;width:100%;padding:12px;box-sizing:border-box}</style>
      <label>Title<input data-field="title" value="${escapeHtml(this._config.title)}"></label>
      <label>Initial view<select data-field="mode">${[[MODE_HERO,"Can't Miss"],["watching","Watching"],[MODE_OUTLOOK,"Year Planner"],[MODE_BIRDS,"Birds"]].map(([v,t])=>`<option value="${v}" ${v===this._config.mode?"selected":""}>${t}</option>`).join("")}</select></label>
      <p>Core-backed read-only views. Choose the integration entry below only if automatic discovery is unavailable.</p>
      <label>Entry ID<input data-field="entry_id" value="${escapeHtml(this._config.entry_id)}"></label>`;
    for (const input of this.shadowRoot.querySelectorAll("[data-field]")) input.addEventListener("change",()=>{
      this._config = {...this._config,[input.dataset.field]:input.value};
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:true,composed:true}));
    });
  }
}

const CARD_STYLES = `
      .core-calendar-week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; padding: 8px 0; border-bottom: 1px solid var(--pe-border); }
      .core-calendar-day { color: var(--pe-muted); min-height: 24px; font-size: 12px; }
      .core-duration-bar { min-width: 0; padding: 8px; text-align: left; overflow: hidden; text-overflow: ellipsis; border-radius: 7px; border: 1px solid rgba(133,212,129,.35); background: rgba(133,212,129,.12); color: var(--pe-text); cursor: pointer; }
      dialog { max-width: min(680px, 92vw); max-height: 85vh; overflow: auto; background: var(--pe-surface); color: var(--pe-text); border: 1px solid var(--pe-border); border-radius: 18px; padding: 24px; }
      dialog::backdrop { background: rgba(0,0,0,.65); }
      .pe-navigation { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px; margin-bottom: 18px; }
      .pe-navigation button { min-width: 0; padding: 12px 2px; font-family: inherit; font-size: 10px; font-weight: 700; line-height: 1.3; color: var(--pe-muted); background: transparent; border: 0; border-bottom: 2px solid transparent; cursor: pointer; }
      .pe-navigation button[aria-pressed="true"] { color: var(--pe-text); border-color: var(--primary-color, #85d481); }
      .cm-watch-summary { margin: 18px 0; padding: 12px; border: 1px solid var(--pe-border); border-radius: 12px; font-size: .85rem; }
      .cm-watch-summary p { color: var(--pe-muted); }
      .cm-watch-row { padding: 16px 0; border-top: 1px solid var(--pe-border); overflow-wrap: anywhere; }
      .cm-watch-row h4 { margin: 0 0 8px; }
      .cm-watch-row p { font-size: .85rem; line-height: 1.5; margin: 8px 0; }
      .cm-watch-row ha-icon { color: var(--event-color); --mdc-icon-size: 20px; }
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
      .update-time { color: var(--pe-muted); font-size: 11px; margin: 8px 0; }
      .bucket-preview { display: block; margin-top: 5px; font-size: 12px; font-weight: 400; letter-spacing: normal; text-transform: none; color: var(--pe-muted); }
      .view-options { margin: 10px 0; color: var(--pe-muted); font-size: 13px; }
      .view-options > summary, .detail-section > summary { cursor: pointer; padding: 10px 0; }
      .detail-section { border-top: 1px solid var(--divider-color, #ffffff20); }
      .detail-section > summary { font-size: 14px; font-weight: 600; color: var(--primary-text-color); }
      .event-intro { color: var(--primary-text-color); font-size: 14px; line-height: 1.55; margin: 8px 0; }
      .event-recommendation { font-size: 13px; line-height: 1.5; }
      .freshness-warning { background: #ba790f18; border-left: 3px solid #d69a38; padding: 10px; font-size: 13px; line-height: 1.5; }
      .show-more { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid var(--divider-color, #ffffff30); border-radius: 8px; background: transparent; color: var(--primary-text-color); cursor: pointer; }
      .outlook-detail, .outlook-detail-grid { font-size: 13px; line-height: 1.55; }
      .simple-row .outlook-title { font-size: 15px; line-height: 1.4; }
      .outlook-meta { overflow-wrap: anywhere; }
      .detail-section a { overflow-wrap: anywhere; }
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


      /* Can't Miss: few rows, each readable at a glance on a phone. */
      .cm-heading { display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:4px 12px; font-weight:700; font-size:16px; margin-bottom:8px; }
      .cm-sub { color:var(--secondary-text-color); font-size:12px; font-weight:400; }
      .cm-row { border-left:3px solid var(--event-color); margin:0 0 8px; border-radius:0 8px 8px 0; background:rgba(127,127,127,.06); }
      .cm-row.open { background:rgba(127,127,127,.10); }
      .cm-head { display:flex; flex-direction:column; align-items:flex-start; gap:3px; width:100%; padding:12px 12px 12px 12px; border:0; background:transparent; color:var(--primary-text-color); font:inherit; text-align:left; cursor:pointer; }
      .cm-title { font-weight:800; font-size:15px; letter-spacing:.02em; text-transform:uppercase; line-height:1.3; overflow-wrap:anywhere; }
      .cm-where, .cm-when, .cm-status { font-size:13px; color:var(--secondary-text-color); overflow-wrap:anywhere; }
      .cm-why { font-size:14px; line-height:1.4; overflow-wrap:anywhere; }
      .cm-take { font-size:13px; font-weight:600; }
      .cm-required { font-size:13px; font-weight:600; color:var(--error-color, #e0685c); }
      .cm-held { margin:10px 0; padding:10px 12px; border-left:3px solid var(--warning-color, #dca54c); font-size:13px; color:var(--secondary-text-color); }
      .cm-held strong { color:var(--primary-text-color); }
      .cm-held ul { margin:4px 0 0; padding-left:18px; }
      .cm-held li { margin:0 0 6px; overflow-wrap:anywhere; }
      .cm-problems { margin:6px 0 0; padding-left:18px; text-align:left; font-size:12px; color:var(--secondary-text-color); }
      .cm-problems li { margin:0 0 4px; overflow-wrap:anywhere; }
      .cm-incomplete-note { margin:6px 0 10px; padding:8px 12px; border-left:3px solid var(--warning-color, #dca54c); font-size:13px; color:var(--secondary-text-color); }
      .cm-incomplete-note summary { cursor:pointer; color:var(--primary-text-color); }
      .cm-row .outlook-detail { padding:0 12px 12px; }
      .cm-report { font-size:13px; margin:6px 0; overflow-wrap:anywhere; }
      .cm-empty { display:flex; flex-direction:column; align-items:center; text-align:center; gap:6px; padding:22px 12px; color:var(--secondary-text-color); }
      .cm-empty strong { color:var(--primary-text-color); font-size:15px; }
      .cm-empty ha-icon { color:var(--success-color, #4caf72); }
      .cm-empty-stale strong { color:var(--warning-color, #dca54c); }
      .cm-background { margin:10px 0 4px; font-size:13px; color:var(--secondary-text-color); }
      .cm-background summary { cursor:pointer; padding:8px 0; }
      .cm-background ul { margin:4px 0 8px; padding-left:18px; }
      .cm-background li { margin:0 0 6px; overflow-wrap:anywhere; }
      .cm-background h4, .cm-section { margin:10px 0 4px; font-size:13px; color:var(--primary-text-color); }
      .cm-none { font-size:13px; color:var(--secondary-text-color); }
      .cm-card a { color:var(--primary-color, #91bca0); text-underline-offset:2px; }
`;

class PhotographyEventsCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this._config={...DEFAULT_CONFIG};
    this._connected=false; this._initialized=false; this._root=null; this._lastHtml="";
    this._activeFilters=null; this._expanded=new Set(); this._collapsed=new Set(); this._openedBuckets=new Set();
    this._moreBuckets=new Set(); this._calendarView=false; this._calendarOffset=0;
    this._displayEvents=new Map(); this._detailState=new Map(); this._anchorGeneration=0;
    this._views=new Map(); this._selectedView=null; this._requestGeneration=0;
  }
  set hass(value) {
    const previous=this._summaryRevision, previousUser=this._hass?.user?.id; this._hass=value;
    const state=this._summaryState();
    if (!this._explicitMode && !this._initialViewSelected && state?.attributes?.initial_view) {
      this._selectedView=({cant_miss:MODE_HERO,watching:"watching",planner:MODE_OUTLOOK,birds:MODE_BIRDS})[state.attributes.initial_view] || MODE_HERO;
      this._initialViewSelected=true;
    }
    if ((previousUser && previousUser!==value?.user?.id) || ["auth_required","incompatible","invalid_response","connection_required"].includes(state?.attributes?.availability)) this._views.clear();
    this._summaryRevision=`${state?.attributes?.entry_id || ""}:${state?.attributes?.snapshot_id || ""}:${state?.attributes?.availability || ""}:${value?.connected}`;
    if (this._connected && (!this._initialized || previous!==this._summaryRevision)) { this._initialized=true; this._refreshCore(); }
    this._render();
  }
  _summaryState() {
    const states=Object.values(this._hass?.states || {});
    return states.find(s=>s.attributes?.projection_version==="ha.v17.1" && (!this._config.entry_id || s.attributes.entry_id===this._config.entry_id));
  }
  _entryId() { return this._config.entry_id || this._summaryState()?.attributes?.entry_id; }
  _isBackendMode() { return true; }
  setConfig(config) {
    if (!config) throw new Error("Photography Events Card configuration is required");
    this._explicitMode=Object.hasOwn(CORE_VIEW,config.mode); this._initialViewSelected=false;
    this._config={title:typeof config.title==="string"?config.title.slice(0,256):DEFAULT_CONFIG.title,
                  mode:this._explicitMode?config.mode:MODE_HERO,
                  entry_id:typeof config.entry_id==="string"?config.entry_id.slice(0,128):""};
    this._selectedView=this._config.mode;
    this._views.clear(); this._requestGeneration++; this._lastHtml="";
    if (this._connected) this._refreshCore(); this._render();
  }
  connectedCallback() {
    this._connected=true; this._initialized=true; this._refreshCore();
    this._clearIntervals();
    this._eventInterval=setInterval(()=>this._render(),1000);
    this._fetchInterval=setInterval(()=>this._refreshCore(),5*60000);
    this._render();
  }
  disconnectedCallback() {
    this._connected=false; this._requestGeneration++; this._anchorGeneration++;
    this._cancelAnchor?.(); this._clearIntervals();
  }
  _clearIntervals() { clearInterval(this._eventInterval); clearInterval(this._fetchInterval); this._eventInterval=this._fetchInterval=null; }
  async _refreshCore(append=false) {
    if (!this._connected || !this._hass?.callWS || !this._entryId()) return;
    if (this._requestPending) { this._refreshQueued=true; return; }
    const view=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const old=this._views.get(view), entry=this._entryId();
    if (append && !old?.next_cursor) return;
    this._requestPending=true;
    const generation=this._requestGeneration;
    try {
      // Coalesce view changes and summary pushes; one request at a time, <=1/s.
      const pause=Math.max(0,1000-(Date.now()-(this._lastRead || 0)));
      if (pause) await new Promise(resolve=>setTimeout(resolve,pause));
      if (!this._connected || generation!==this._requestGeneration) return;
      this._lastRead=Date.now();
      const message={type:"photography_events/get_view",entry_id:entry,projection_version:"ha.v17.1",view,limit:50};
      if (append) { message.cursor=old.next_cursor; message.snapshot_id=old.snapshot_id; }
      const result=await this._hass.callWS(message);
      if (!this._connected || generation!==this._requestGeneration || entry!==this._entryId()) return;
      if (result?.projection_version!=="ha.v17.1" || result.entry_id!==entry || !Array.isArray(result.items) || result.items.length>50) { this._views.clear(); throw new Error("invalid_projection"); }
      if (append) result.items=[...old.items,...result.items].slice(0,500);
      this._views.set(view,result); this._transportError=null;
      // Other view caches cannot retain an earlier generation or connection.
      for (const [key,v] of this._views) if (v.snapshot_id!==result.snapshot_id) this._views.delete(key);
    } catch (error) {
      if (generation===this._requestGeneration && this._connected) {
        this._transportError="Core view unavailable. Check the integration connection in Settings > Devices & services.";
        if (error?.code==="snapshot_expired") { this._views.delete(view); this._refreshQueued=true; }
        if (["unauthorized","unsupported_projection"].includes(error?.code)) this._views.clear();
      }
    } finally {
      this._requestPending=false; this._render();
      if (this._refreshQueued && this._connected) { this._refreshQueued=false; this._refreshCore(); }
    }
  }
  // Follow the composed tree: a slotted card's scroll owner can live inside
  // the slot host's shadow root, outside the parentElement chain.
  _scrollOwners(element) {
    const owners = [];
    let node = element;
    while (node) {
      if (node.scrollHeight > node.clientHeight && typeof getComputedStyle === "function" &&
          /auto|scroll|overlay/.test(getComputedStyle(node).overflowY)) owners.push(node);
      node = node.assignedSlot || node.parentElement || node.getRootNode?.().host;
    }
    if (document.scrollingElement && !owners.includes(document.scrollingElement)) owners.push(document.scrollingElement);
    return owners;
  }

  _visualAnchor(control) {
    if (!this._root?.getBoundingClientRect) return null;
    const attrs = ["data-expand", "data-category", "data-view", "data-month", "data-more", "data-skipped", "data-tab"];
    const identity = el => {
      if (el?.tagName === "SUMMARY") {
        const section = el.parentElement;
        const attr = section?.hasAttribute("data-section") ? "data-section" : "data-bucket";
        return section?.getAttribute(attr) != null ? [attr, section.getAttribute(attr), true] : null;
      }
      return el && attrs.map(attr => [attr, el.getAttribute?.(attr)]).find(([, value]) => value != null);
    };
    const focused = this.shadowRoot.activeElement;
    let target = control || (identity(focused) ? focused : null);
    const viewport = typeof innerHeight === "number" ? innerHeight : Infinity;
    if (!target) target = [...this._root.querySelectorAll("button, summary")].find(el => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 0 && rect.top < viewport && rect.height && identity(el);
    });
    target ||= this._root;
    const rect = target.getBoundingClientRect();
    if (!rect.height || rect.bottom < 0 || rect.top > viewport) return null;
    return { identity: identity(target), top: rect.top, fallbackTop: this._root.getBoundingClientRect().top,
      focus: identity(focused) };
  }

  _anchorElement(identity) {
    if (!identity) return this._root;
    const [attr, value, summary] = identity;
    const el = [...this._root.querySelectorAll(`[${attr}]`)].find(item => item.getAttribute(attr) === value);
    return summary ? el?.querySelector("summary") : el;
  }

  _restoreAnchor(anchor) {
    this._cancelAnchor?.();
    const generation = ++this._anchorGeneration;
    if (!anchor) return;
    const owners = this._scrollOwners(this._anchorElement(anchor.identity) || this._root);
    const cancel = () => { this._anchorGeneration++; cleanup(); };
    const types = ["wheel", "touchstart", "keydown", "pointerdown"];
    const cleanup = () => {
      for (const owner of owners) for (const type of types) owner.removeEventListener?.(type, cancel);
      if (this._cancelAnchor === cleanup) this._cancelAnchor = null;
    };
    this._cancelAnchor = cleanup;
    for (const owner of owners) for (const type of types) owner.addEventListener?.(type, cancel, { passive: true });
    const restore = () => {
      if (generation !== this._anchorGeneration || !this._connected) return;
      const equivalent = this._anchorElement(anchor.identity);
      const element = equivalent || this._root;
      const top = equivalent ? anchor.top : anchor.fallbackTop;
      for (const owner of this._scrollOwners(element)) {
        const delta = element.getBoundingClientRect().top - top;
        if (Math.abs(delta) < 0.5) break;
        owner.scrollTop += delta;
      }
    };
    this._anchorElement(anchor.focus)?.focus?.({ preventScroll: true });
    restore();
    // Lit custom elements and HA dashboard layout settle after the DOM write.
    // Bounded frames handle that second layout; a new interaction/scroll cancels
    // them so we never drag the user back after they deliberately move away.
    if (typeof requestAnimationFrame === "function") {
      let frames = 3;
      const settle = () => {
        if (generation !== this._anchorGeneration) { cleanup(); return; }
        restore();
        if (--frames) requestAnimationFrame(settle);
        else cleanup();
      };
      requestAnimationFrame(settle);
    } else cleanup();
  }

  _render(control) {
    if (!this.shadowRoot) return;
    const body = this._hass ? this._bodyHtml() : this._loadingHtml("Waiting for Home Assistant");
    if (this._dialog?.open) this._updateEventDialog();

    // A hero with nothing to announce leaves no trace at all. An empty card
    // still draws a border and takes a slot in the layout, which is its own
    // small false alarm on a dashboard whose whole point is that this thing
    // is silent until it matters.
    if (body === null) {
      this._setHidden(true);
      this._lastHtml = "";
      if (this._root) this._root.innerHTML = "";
      return;
    }
    this._setHidden(false);

    const html = `<div class="card-content">${this._navigationHtml()}${body}</div>`;

    // Ticks that produce byte-identical markup leave the live DOM untouched
    // instead of destroying and re-upgrading every ha-icon in the timeline -
    // and, in the outlook, keep the toggle listeners bound.
    if (this._root && html === this._lastHtml) return;
    this._lastHtml = html;

    if (!this._root) {
      const style = document.createElement("style");
      style.textContent = this._styles();
      // Keep ha-card connected. Recreating a Lit host briefly removes its
      // slotted content until its first update, collapsing the dashboard height
      // and clamping scrollTop before a synchronous restoration can succeed.
      const root = document.createElement("ha-card");
      root.className = "pe-root";
      this.shadowRoot.replaceChildren(style, root);
      this._root = root;
    }
    // Keep the planner's internal offset, then preserve a visual anchor in
    // the enclosing dashboard instead of guessing which ancestor scrolls.
    const innerScroll = this._root.querySelector(".outlook")?.scrollTop || 0;
    const anchor = this._visualAnchor(control);
    for (const el of this._root.querySelectorAll("[data-section]")) this._detailState.set(el.dataset.section, el.open);
    const focused = this.shadowRoot.activeElement;
    const focusedSection = focused?.tagName === "SUMMARY" ? focused.parentElement?.dataset.section : null;
    const focusAttributes = ["data-expand", "data-category", "data-view", "data-month", "data-more", "data-skipped"];
    const focusIdentity = focused && focusAttributes.map(attr => [attr, focused.getAttribute?.(attr)]).find(([, value]) => value != null);
    this._root.innerHTML = html;
    for (const el of this._root.querySelectorAll("[data-section]")) {
      if (this._detailState.has(el.dataset.section)) el.open = this._detailState.get(el.dataset.section);
    }
    this._bindEvents();
    if (focusIdentity) [...this._root.querySelectorAll(`[${focusIdentity[0]}]`)]
      .find(el => el.getAttribute(focusIdentity[0]) === focusIdentity[1])?.focus?.({preventScroll: true});
    if (focusedSection) [...this._root.querySelectorAll("[data-section]")]
      .find(el => el.dataset.section === focusedSection)?.querySelector("summary")?.focus?.({preventScroll: true});
    const inner = this._root.querySelector(".outlook");
    if (inner) inner.scrollTop = innerScroll;
    this._restoreAnchor(anchor);
    if (this._focusKey) {
      [...this._root.querySelectorAll("[data-expand]")].find(button => button.dataset.expand === this._focusKey)?.focus?.({ preventScroll: true });
      this._focusKey = null;
    }
  }

  /**
   * Toggle chips are rendered as real buttons carrying their entity id, and
   * wired up here after each DOM write. No inline handlers: they would break
   * under a strict Content-Security-Policy, which several people run.
   */
  _bindEvents() {
    if (!this._root) return;
    for (const button of this._root.querySelectorAll("[data-tab]")) {
      button.addEventListener("click", () => {
        if (this._selectedView === button.dataset.tab) return;
        this._selectedView = button.dataset.tab;
        this._render(button);
        this._refreshCore();
      });
    }
    for (const summary of this._root.querySelectorAll("summary")) {
      summary.addEventListener("click", () => {
        const anchor = this._visualAnchor(summary);
        // Native details stays native: no DOM rebuild for a disclosure.
        this._restoreAnchor(anchor);
      });
    }
    for (const section of this._root.querySelectorAll("[data-bucket]")) {
      section.addEventListener("toggle", () => {
        if (section.open) { this._collapsed.delete(section.dataset.bucket); this._openedBuckets.add(section.dataset.bucket); }
        else this._collapsed.add(section.dataset.bucket);
      });
    }
    for (const button of this._root.querySelectorAll("[data-more]")) {
      button.addEventListener("click", () => {
        const key = button.dataset.more;
        if (this._moreBuckets.has(key)) this._moreBuckets.delete(key);
        else this._moreBuckets.add(key);
        this._render(button);
      });
    }
    for (const button of this._root.querySelectorAll("[data-view]")) {
      button.addEventListener("click", () => { this._calendarView = button.dataset.view === "calendar"; this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-month]")) {
      button.addEventListener("click", () => { this._calendarOffset = clamp(this._calendarOffset + Number(button.dataset.month), 0, 12); this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-open]")) {
      button.addEventListener("click", () => this._openCalendarEvent(button.dataset.open));
    }
    for (const button of this._root.querySelectorAll("[data-skipped]")) {
      button.addEventListener("click", () => { this._showSkipped = !this._showSkipped; this._render(button); });
    }
    for (const button of this._root.querySelectorAll("[data-choice]")) {
      button.addEventListener("click", () => this._saveChoice(button.dataset.eventid, button.dataset.choice));
    }
    for (const button of this._root.querySelectorAll("[data-category]")) {
      button.addEventListener("click", () => {
        const category = button.getAttribute("data-category");
        if (!category || !this._activeFilters) return;
        if (this._activeFilters.has(category)) this._activeFilters.delete(category);
        else this._activeFilters.add(category);
        this._render(button);
      });
    }
    for (const button of this._root.querySelectorAll("[data-expand]")) {
      button.addEventListener("click", () => {
        const key = button.getAttribute("data-expand");
        if (!key) return;
        this._focusKey = key;
        if (this._expanded.has(key)) this._expanded.delete(key);
        else this._expanded.add(key);
        this._render(button);
      });
    }
  }


  async _saveChoice() { return; }
  _eventControlsHtml() {
    return `<div class="event-controls"><button disabled title="Core persistence is unavailable">Follow</button><button disabled title="Core persistence is unavailable">Skip</button><button disabled title="Core persistence is unavailable">Seen · Got the shot</button></div><p class="event-note">Choices are unavailable until Core supports persistence. Nothing is saved. Notifications are disabled.</p>`;
  }
  _setHidden(hidden) { if(this.style)this.style.display=hidden?"none":""; }
  _loadingHtml(label) { return `<div class="loading"><span class="spinner"></span><span>${escapeHtml(label)}</span></div>`; }
  _styles() { return CARD_STYLES; }
  getCardSize() { return 8; }
  static getConfigElement() { return document.createElement("photography-events-card-editor"); }
  static getStubConfig() { return {...DEFAULT_CONFIG}; }
}

const CORE_COPY = {
  current:"Current Core assessment", empty_assessed:"No opportunities in the verified assessed scope",
  coverage_unknown:"Coverage is unverified. Core has not established that the whole week was assessed.",
  incomplete:"Core assessment is incomplete. Required inputs are missing.", degraded:"Core assessment is degraded.",
  stale:"Core assessment or transport has expired. These are held historical details.",
  offline_stale:"Core is offline. Cached context is historical and cannot authorize travel.",
  not_assessed:"A current Core assessment is not available.", unsupported:"This view has no reviewed Core coverage.",
  unavailable:"Core is unavailable. Complete or repair the private connection in Settings > Devices & services.",
  shadow_only:"Shadow diagnostics cannot authorize opportunities."
};
const CORE_VIEWS = {
  _navigationHtml() {
    const selected=this._selectedView || this._config.mode;
    return `<nav class="pe-navigation" aria-label="Photography views">${[[MODE_HERO,"CAN'T MISS"],["watching","WATCHING"],[MODE_OUTLOOK,"YEAR PLANNER"],[MODE_BIRDS,"BIRDS"]].map(([view,label])=>`<button type="button" data-tab="${view}" aria-pressed="${selected===view || (view===MODE_OUTLOOK && selected===MODE_TIMELINE)}">${label}</button>`).join("")}</nav>`;
  },
  _agedView() {
    const key=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const original=this._views.get(key);
    if (!original) return {items:[],view_state:"unavailable",availability:"connection_required",coverage:{state:"unverified"}};
    const v={...original,items:original.items.map(row=>({...row}))};
    const now=Date.now();
    const transportExpired=!v.fetched_at || now>=Date.parse(v.fetched_at)+CORE_TRANSPORT_MS;
    const assessmentExpired=!v.data_as_of || now>=Date.parse(v.data_as_of)+CORE_ASSESSMENT_MS;
    const disconnected=this._hass?.connected===false || Boolean(this._transportError);
    if (disconnected) { v.view_state="offline_stale"; v.availability="offline"; }
    else if ((transportExpired || assessmentExpired) && ["current","empty_assessed","coverage_unknown"].includes(v.view_state)) v.view_state="stale";
    for (const row of v.items) if (disconnected || transportExpired || assessmentExpired || now>=Date.parse(row.valid_until)) {
      row.actionable=false; row.held=true; row.row_state="stale"; row.row_freshness="stale";
      row.safety_state=row.access_state=row.condition_state="unknown";
      row.reason="Current scoped Core assessment unavailable.";row.awaiting="A current reviewed Core assessment.";
    }
    if (v.view_state==="shadow_only" || !["online","offline"].includes(v.availability)) v.items=[];
    if (key==="cant_miss") v.items=v.view_state==="current" && v.coverage?.state==="verified" && v.availability==="online" ? v.items.filter(r=>r.actionable===true && r.row_state==="current") : [];
    return v;
  },
  _bodyHtml() {
    const v=this._agedView(), key=CORE_VIEW[this._selectedView || this._config.mode] || "cant_miss";
    const labels={cant_miss:"Can't Miss",watching:"Watching",planner:"Year Planner",birds:"Birds"};
    const status=this._transportError || CORE_COPY[v.view_state] || CORE_COPY.unavailable;
    let rows=v.items;
    const categories=[...new Set(rows.map(r=>r.category))];
    if(this._activeFilters===null)this._activeFilters=new Set(categories);
    this._knownCoreCategories ||= new Set();
    for (const c of categories) if(!this._knownCoreCategories.has(c)){this._activeFilters.add(c);this._knownCoreCategories.add(c);}
    // Filters are local presentation only; no unsupported Core category query.
    rows=rows.filter(r=>this._activeFilters.has(r.category));
    this._displayEvents=new Map(rows.map(r=>[r.occurrence_key,r]));
    const more=this._moreBuckets.has(key), visible=more?rows:rows.slice(0,5);
    const filters=categories.length>1?`<div class="filters">${categories.map(c=>`<button data-category="${escapeHtml(c)}" aria-pressed="${this._activeFilters.has(c)}">${escapeHtml(c)}</button>`).join("")}</div>`:"";
    const controls=key==="planner"?`<div class="view-switch"><button data-view="list" aria-pressed="${!this._calendarView}">List</button><button data-view="calendar" aria-pressed="${this._calendarView}">Month</button></div>`:"";
    return `<div class="header"><div class="header-title">${escapeHtml(this._config.title)}</div><div class="header-subtitle">${labels[key]} · Read-only Core development build</div></div>
      <div class="cm-watch-summary" role="status"><strong>${escapeHtml(status)}</strong>
      <p>Connection: ${escapeHtml(v.availability)} · Assessment: ${escapeHtml(v.assessment_state || "not_assessed")} · Coverage: ${escapeHtml(v.coverage?.state || "unverified")}</p>
      ${v.data_as_of?`<p>Assessment input: ${escapeHtml(coreDate(v.data_as_of))}<br>Validated HA fetch: ${escapeHtml(coreDate(v.fetched_at))}</p>`:""}
      ${v.problems?.length?`<p>${v.problems.map(p=>escapeHtml(`${p.source}: ${p.code}`)).join(" · ")}</p>`:""}
      <p>Core v1 supplies a limited normal mammal slice. Year-wide planning, Birds and calendar precision are unsupported. Shadow results are excluded.</p></div>
      ${filters}${controls}<div class="outlook">${key==="planner" && this._calendarView?this._coreMonthHtml(rows):visible.map(r=>this._coreRowHtml(r)).join("")}
      ${!rows.length?`<div class="empty-card"><ha-icon icon="mdi:camera-outline"></ha-icon><strong>${v.view_state==="empty_assessed"?"No products in this verified scope":"No current authorized rows in this view"}</strong><p>${escapeHtml(status)}</p></div>`:""}
      ${rows.length>5?`<button data-more="${key}">${more?"Show five previews":`More · ${rows.length-5} additional published rows`}</button>`:""}
      ${v.next_cursor?`<button type="button" data-page="next">Load more published rows</button>`:""}</div>
      <div class="footer">Choices unavailable · Notifications disabled · No legacy intelligence fallback</div>`;
  },
  _coreRowHtml(r) {
    const id=r.occurrence_key, open=this._expanded.has(id);
    const publicLocation=r.location?.policy==="curated_public_site";
    return `<article class="cm-watch-row" style="--event-color:#85d481"><h4><ha-icon icon="mdi:camera-outline"></ha-icon> ${escapeHtml(r.title)}</h4>
      <p>${escapeHtml(coreDate(r.starts_at))} — ${escapeHtml(coreDate(r.ends_at))}<br>Published window; appointment precision unavailable.</p>
      <p>${publicLocation?escapeHtml(r.location.name):"Location withheld"} · ${escapeHtml(r.row_state)} · ${escapeHtml(r.evidence_state)}</p>
      ${r.reason?`<p>${escapeHtml(r.reason)}</p>`:""}
      <button type="button" data-expand="${escapeHtml(id)}" aria-expanded="${open}">${open?"Close details":"Details"}</button>
      <button type="button" data-open="${escapeHtml(id)}">Open window</button>
      ${open?this._coreDetailHtml(r):""}</article>`;
  },
  _coreDetailHtml(r) {
    return `<div class="event-detail"><p>${escapeHtml(r.detail || "No additional public detail supplied.")}</p>
      <p>${escapeHtml(r.awaiting || "")}</p><p>Safety: ${escapeHtml(r.safety_state)} · Access: ${escapeHtml(r.access_state)} · Conditions: ${escapeHtml(r.condition_state)}</p>
      ${r.blockers?.length?`<p>Held: ${r.blockers.map(escapeHtml).join(" · ")}</p>`:""}
      <details data-section="${escapeHtml(r.occurrence_key)}:gear"><summary>Gear and ethics</summary><dl class="outlook-detail-grid">${Object.entries(r.gear || {}).filter(([,v])=>Array.isArray(v)?v.length:Boolean(v)).map(([k,v])=>`<dt>${escapeHtml(k.replaceAll("_"," "))}</dt><dd>${escapeHtml(Array.isArray(v)?v.join(" · "):v)}</dd>`).join("") || "<dd>No public gear recommendation</dd>"}</dl><p>${escapeHtml(r.ethics || "")}</p></details>
      <p>Input: ${escapeHtml(coreDate(r.data_as_of))} · Valid until: ${escapeHtml(coreDate(r.valid_until))}</p>
      <p>Definition ${escapeHtml(r.definition_key)} · ${escapeHtml(r.definition_version)}</p>${this._eventControlsHtml()}</div>`;
  },
  _coreMonthHtml(rows) {
    const month=new Date(); month.setDate(1); month.setMonth(month.getMonth()+this._calendarOffset);
    month.setHours(0,0,0,0);
    const gridStart=new Date(month);gridStart.setDate(1-month.getDay());
    const days=Array.from({length:42},(_,i)=>{const day=new Date(gridStart);day.setDate(day.getDate()+i);return day;});
    const weeks=Array.from({length:6},(_,week)=>{
      const dates=days.slice(week*7,week*7+7);
      const bars=rows.map(r=>{
        const covered=dates.map((d,i)=>{const next=new Date(d);next.setDate(d.getDate()+1);return Date.parse(r.starts_at)<next.getTime() && Date.parse(r.ends_at)>=d.getTime()?i:null;}).filter(i=>i!==null);
        if(!covered.length)return "";
        return `<button class="core-duration-bar" style="grid-column:${covered[0]+1}/${covered.at(-1)+2}" data-open="${escapeHtml(r.occurrence_key)}" title="${escapeHtml(`${r.title}: ${coreDate(r.starts_at)} — ${coreDate(r.ends_at)}`)}">${escapeHtml(r.title)}</button>`;
      }).join("");
      return `<div class="core-calendar-week">${dates.map(d=>`<span class="core-calendar-day" ${d.getMonth()!==month.getMonth()?'style="opacity:.4"':""}>${d.getDate()}</span>`).join("")}${bars}</div>`;
    }).join("");
    return `<div class="calendar"><div class="month-header"><button data-month="-1" aria-label="Previous month">‹</button><strong>${escapeHtml(month.toLocaleDateString(undefined,{month:"long",year:"numeric"}))}</strong><button data-month="1" aria-label="Next month">›</button></div>
      <p>Published Core ranges only; these bars are not timed appointments. This month has not been assessed as a complete plan.</p>
      <div class="core-calendar-week">${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(d=>`<span>${d}</span>`).join("")}</div>${weeks}</div>`;
  },
  _openCalendarEvent(key) {
    if (!this._displayEvents.has(key)) return;
    if (!this._dialog) {
      this._dialog=document.createElement("dialog"); this.shadowRoot.appendChild(this._dialog);
      this._dialog.addEventListener("close",()=>this._dialogOpener?.focus?.({preventScroll:true}));
    }
    this._dialogOpener=this.shadowRoot.activeElement; this._dialogKey=key; this._updateEventDialog();
    this._dialog.showModal?.();
  },
  _updateEventDialog() {
    if(!this._dialog)return;
    const row=this._agedView().items.find(r=>r.occurrence_key===this._dialogKey);
    const html=row?`<h3>${escapeHtml(row.title)}</h3>${this._coreDetailHtml(row)}<button data-close="true">Close</button>`:`<p>This occurrence is no longer in the current sanitized snapshot.</p><button data-close="true">Close</button>`;
    if(this._dialogLastHtml===html)return;
    this._dialogLastHtml=html;
    const scroll=this._dialog.scrollTop || 0;
    this._dialog.innerHTML=html; this._dialog.scrollTop=scroll;
    this._dialog.querySelector("[data-close]")?.addEventListener("click",()=>this._dialog.close());
  }
};
const originalCoreBind=PhotographyEventsCard.prototype._bindEvents;
PhotographyEventsCard.prototype._bindEvents=function(){originalCoreBind.call(this);for(const b of this._root?.querySelectorAll("[data-page]") || [])b.addEventListener("click",()=>this._refreshCore(true));};
Object.assign(PhotographyEventsCard.prototype,CORE_VIEWS);

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card?.type === "photography-events-card")) {
  window.customCards.push({
    type: "photography-events-card",
    name: "Photography Events Card",
    description: "Read-only Core-backed photography views with explicit coverage and connection status",
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
