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
