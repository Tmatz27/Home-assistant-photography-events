import fs from "node:fs";
import assert from "node:assert/strict";
const version = fs.readFileSync("VERSION", "utf8").trim();
assert.match(version, /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/);
assert.equal(JSON.parse(fs.readFileSync("package.json", "utf8")).version, version);
const source = fs.readFileSync("custom_components/photography_events/www/photography-events-card.js", "utf8");
assert.equal(source.match(/const CARD_VERSION = "([^"]+)"/)[1], version);
const header = fs.readFileSync("custom_components/photography_events/www/src/header.js", "utf8");
assert.equal(header.match(/const CARD_VERSION = "([^"]+)"/)[1], version);
assert.ok(fs.readFileSync("CHANGELOG.md", "utf8").replace(/\r/g, "").includes(`## ${version}\n`), "Add release notes for this version");
console.log(`Version ${version} agrees across VERSION, package, card, and changelog`);

assert.equal(JSON.parse(fs.readFileSync("custom_components/photography_events/manifest.json", "utf8")).version, version);
