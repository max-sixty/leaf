/* The browser's side of quote resolution's shared cases: `tests/quote_cases.json` holds
   the browser's `findQuote` (passages.js) and the file's `resolve_quote`
   (anchor_capture.py) to one answer for each, so the two readers of a stored anchor
   resolve it by the same rules (root AGENTS.md, "Validate once and share readings").
   An answer is how many of the section's letters stand before the passage. */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { findQuote, pageText, spanIn, textNodesUnder } from "/runtime/passages.js";
import { registry } from "/runtime/registry.js";
import { shadowStage } from "/runtime/shadow-stage.js";

const { cases } = JSON.parse(
  readFileSync(new URL("../quote_cases.json", import.meta.url), "utf8"),
);

for (const { id, markup, anchor, before, ...widgets } of cases)
  test(`quote: ${id}`, () => {
    Object.assign(registry, widgets.registry ?? {}, { $layer: { generation: id } });
    document.body.innerHTML = `<main>${markup}</main>`;
    // Each staged widget's shadow tree, its light children slotted into it as authored.
    for (const [tag, shadow] of Object.entries(widgets.stage ?? {}))
      for (const host of document.querySelectorAll(tag)) {
        const light = host.innerHTML;
        const tree = document.createElement("template");
        tree.innerHTML = /** @type {string} */ (shadow);
        shadowStage(host, [...tree.content.childNodes]);
        host.innerHTML = light;
      }
    const section = document.getElementById(anchor.section);
    const reading = pageText();
    const found = findQuote(reading, anchor.quote, anchor, section);
    const [start] = spanIn(reading, textNodesUnder(/** @type {Element} */ (section)));
    // The reading's edges stand between its words without being any.
    const letters = found.length
      ? reading.raw
          .slice(start, spanIn(reading, found)[0])
          .replaceAll("\u0000", "")
          .replace(/\s/g, "").length
      : null;
    assert.equal(letters, before);
  });
