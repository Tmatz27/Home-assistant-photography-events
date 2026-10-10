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
