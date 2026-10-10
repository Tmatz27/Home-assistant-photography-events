
import fs from "node:fs";

import vm from "node:vm";

const source = fs.readFileSync(new URL("../custom_components/photography_events/www/photography-events-card.js", import.meta.url), "utf8");

class FakeNode {
  constructor(localName = "div") {
    this.localName = localName;
    this.className = "";
    this.children = [];
    this.writes = 0;
    this._html = "";
  }

  set innerHTML(value) {
    this._html = value;
    this.writes += 1;
    // A fresh DOM write means fresh elements, and therefore fresh listeners.
    this._queried = new Map();
  }

  get innerHTML() {
    return this._html;
  }

  setAttribute(name, value) {
    this[name] = value;
  }

  replaceChildren(...nodes) {
    this.children = nodes;
  }

  replaceWith() {}

  querySelector() {
    return null;
  }

  /**
   * Enough of a query to exercise the wiring in both the card and the editor:
   * every `[data-*]` selector returns elements carrying that attribute, with a
   * `dataset` and a `getAttribute`, so a test can set a value and fire it.
   */
  querySelectorAll(selector) {
    const match = /^\[data-([a-z]+)\]$/.exec(selector);
    if (!match) return [];
    const key = match[1];
    this._queried = this._queried || new Map();
    // Return the *same* element objects that had listeners bound to them.
    // Handing back fresh ones each call would make every listener test pass
    // vacuously, since the event would land on an object nobody wired up.
    if (this._queried.has(selector)) return this._queried.get(selector);

    // Match the whole tag, not just the one attribute: an element's other
    // data-* attributes carry real behaviour (the per-input clamp bounds, for
    // one), and a dataset with a single key would silently test the fallback.
    const pattern = new RegExp(`<[^>]*\\bdata-${key}="[^"]*"[^>]*>`, "g");
    const tags = [...this._html.matchAll(pattern)].map((found) => found[0]);
    const elements = tags.map((tag) => {
      const dataset = {};
      for (const [, name, value] of tag.matchAll(/data-([a-z]+)="([^"]*)"/g)) dataset[name] = value;
      return {
      _handlers: {},
      dataset,
      value: "",
      checked: false,
      getAttribute: (name) => {
        const found = /^data-([a-z]+)$/.exec(name);
        return found && found[1] in dataset ? dataset[found[1]] : null;
      },
      addEventListener(type, handler) {
        (this._handlers[type] = this._handlers[type] || []).push(handler);
      },
      fire(type = "click") {
        for (const handler of this._handlers[type] || []) handler();
      },
      click() {
        this.fire("click");
      },
      };
    });
    this._queried.set(selector, elements);
    return elements;
  }

  addEventListener() {}
}

class FakeHTMLElement {
  addEventListener() {}
  constructor() {
    // Real elements always have one, and the hero mode hides itself through it.
    this.style = {};
  }

  attachShadow() {
    this.shadowRoot = new FakeNode("#shadow-root");
    return this.shadowRoot;
  }
}

function baseSandbox() {
  return {
    HTMLElement: FakeHTMLElement,
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options?.detail;
      }
    },
    customElements: {
      define(name, constructor) {
        this._registry = this._registry || new Map();
        this._registry.set(name, constructor);
      },
      get(name) {
        return this._registry?.get(name);
      },
    },
    document: {
      createElement(name) {
        return new FakeNode(name);
      },
    },
    window: { customCards: [] },
    console: { info() {}, error() {} },
    setInterval: (...args) => { const timer = setInterval(...args); timer.unref(); return timer; },
    clearInterval,
    setTimeout,
    Promise,
    URL,
  };
}


export { FakeNode };
export function loadCoreCard() { const context=baseSandbox(); vm.runInNewContext(source,context); return { Card:context.customElements.get('photography-events-card'), Editor:context.customElements.get('photography-events-card-editor'), context, source }; }
