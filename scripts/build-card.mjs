// Concatenation only: users still install one ready-to-use vanilla JS file.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = new URL("../", import.meta.url);
const names = JSON.parse(readFileSync(new URL("card-sources.json", import.meta.url), "utf8"));
const content = names.map(name => {
  const path = new URL(`custom_components/photography_events/www/src/${name}.js`, root);
  const check = spawnSync(process.execPath, ["--check", fileURLToPath(path)], { encoding: "utf8" });
  if (check.status !== 0) throw new Error(check.stderr || `Syntax check failed: ${name}`);
  let text = readFileSync(path, "utf8");
  if (name === "catalog") {
    const catalog = JSON.parse(readFileSync(new URL("custom_components/photography_events/eclipse_catalog.json", root), "utf8"));
    const rows = catalog.events.map(row => ({...row,
      region: `${row.type[0].toUpperCase() + row.type.slice(1)} ${row.kind} eclipse. NASA catalog prediction; verify local circumstances.`}));
    text = text.replace("/* @eclipse-catalog */ []", JSON.stringify(rows));
  }
  if (text.includes("\r")) throw new Error(`${name}.js must use LF line endings`);
  return text.trimEnd();
}).join("\n\n") + "\n";
const target = new URL("custom_components/photography_events/www/photography-events-card.js", root);
if (process.argv.includes("--check")) {
  if (readFileSync(target, "utf8") !== content) {
    throw new Error("Bundled card is out of date. Run node scripts/build-card.mjs.");
  }
  console.log(`Card matches ${names.length} source files.`);
} else {
  writeFileSync(target, content);
  console.log(`Built card from ${names.length} source files.`);
}
