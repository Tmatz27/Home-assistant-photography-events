Object.assign(PhotographyEventsCard.prototype, CARD_MODES);

// Test-only seam: the astronomy math is written as free functions (no `this`
// juggling), so it is exposed here for direct unit testing the same way the
// rest of this repo pokes at underscore-prefixed instance methods.
PhotographyEventsCard.backend = {
  driveLabel,
  driveProvenance,
  parseEventDate,
  heroFromState,
  outlookFromState,
  activeCategories,
  filterOutlook,
  groupByMonth,
  groupByUrgency,
  rollUpByPlace,
  consolidateNights,
  calendarSegments,
  nightTradeoffs,
  cloudLabel,
  healthStripHtml,
  reportLinkHtml,
  rangeLabel,
  findEntity,
  CATEGORY_META,
  DOG_META,
  MODE_HERO,
  MODE_OUTLOOK,
  MODE_TIMELINE,
};

PhotographyEventsCard.astro = {
  daysSinceJ2000,
  sunEquatorial,
  moonEquatorial,
  horizontalFromEquatorial,
  findAltitudeCrossings,
  moonIllumination,
  moonPhaseInfo,
  buildDayTable,
  pruneRoutine,
  buildEvents,
  skyColorQuality,
  meteorQuality,
  planetGeocentric,
  planetElongationDeg,
  planetEvents,
  customSkyEvents,
  angularSeparation,
  PLANETS,
  lunarEclipseVisibility,
  solarEclipseVisibility,
  centralPathMargin,
  METEOR_SHOWERS,
  ECLIPSES,
};

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card?.type === "photography-events-card")) {
  window.customCards.push({
    type: "photography-events-card",
    name: "Photography Events Card",
    description: "Upcoming golden hour, moon phases, meteor showers, eclipses, and more near your location",
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
