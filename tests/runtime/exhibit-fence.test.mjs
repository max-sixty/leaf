/* Mention, not use: a widget strictly inside an element the registry marks x-exhibit is
   quoted. The live element answers through `quoted`, and the descriptor staged before
   upgrade carries the same answer over the authored parents. The server reads it off
   the holder chain (`questions.quoted_in`); `tests/exhibit_cases.json` holds all three
   to one set of cases. */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { adoptRegistry } from "/runtime/registry.js";
import { quoted } from "/runtime/widget-elements.js";
import { stageWidgetDescriptors } from "/runtime/widget-descriptors.js";

const { registry, cases } = JSON.parse(
  readFileSync(new URL("../exhibit_cases.json", import.meta.url), "utf8"),
);

for (const { id, markup, quoted: expected } of cases)
  test(`exhibit: ${id}`, () => {
    adoptRegistry(registry);
    document.body.innerHTML = `<main>${markup}</main>`;
    const ids = Object.keys(expected);
    assert.deepEqual(
      Object.fromEntries(ids.map((id) => [id, quoted(document.getElementById(id))])),
      expected,
    );
    const staged = stageWidgetDescriptors(document.querySelector("main"), {
      kind: "page",
      revision: 1,
    });
    assert.deepEqual(
      Object.fromEntries(ids.map((id) => [id, staged.descriptors.get(id).quoted])),
      expected,
    );
  });
