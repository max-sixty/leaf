/* Mention, not use: a widget strictly inside an element the registry marks `exhibit` is
   quoted. The descriptor staged before upgrade carries the answer, and `quoted` gives
   the same one for an element no descriptor holds. The server reads it off
   the holder chain (`obligations.quoted_in`); `tests/exhibit_cases.json` holds both runtimes
   to one set of cases. A widget asks through the portable helpers, which give Leaf's
   answer once Leaf has installed its page capabilities and quote nothing before. */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { quoted as asked } from "/runtime/portable-api.js";
import { adoptRegistry } from "/runtime/registry.js";
import { quoted, stageWidgetDescriptors } from "/runtime/widget-descriptors.js";

const { registry, cases } = JSON.parse(
  readFileSync(new URL("../exhibit_cases.json", import.meta.url), "utf8"),
);

// First, while nothing in this process has loaded Leaf's page capabilities.
test("a widget's question is false without Leaf and Leaf's answer with it", async () => {
  adoptRegistry(registry);
  document.body.innerHTML = `<main>${cases[0].markup}</main>`;
  const inner = document.getElementById("inner");
  assert.equal(quoted(inner), true);
  assert.equal(asked(inner), false);
  await import("/runtime/element-integration.js");
  assert.equal(asked(inner), true);
  assert.equal(asked(document.getElementById("exhibit")), false);
});

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
