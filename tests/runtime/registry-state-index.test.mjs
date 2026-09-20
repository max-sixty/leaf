/* The one traversal of `x-state` and `x-report`, and the generation it belongs to.

   Derived state declarations belong to one complete registry generation. Warming the
   index must not make a later generation inherit the declarations of the one before it,
   and both channels contribute while only recorded declarations contribute owner
   selectors.

   The vocabulary is stated here rather than loaded, so what the index returns is caused
   by these declarations and by nothing else a page might have vendored. */

import assert from "node:assert/strict";
import test from "node:test";

import { recordedWidgetSelector, registry, stateSpecs } from "/runtime/registry.js";

const load = (generation, declarations) => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, declarations, { $layer: { generation } });
};

test("a vocabulary that has not loaded has no state index to give", () => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  assert.throws(stateSpecs, /state vocabulary requested before registry loaded/);
  // The generation is what says a vocabulary arrived, so an unstamped one is refused
  // rather than indexed as the empty vocabulary it would otherwise look like.
  load("", {});
  assert.throws(stateSpecs, /state vocabulary requested before registry loaded/);
});

// The generation is the index's cache key, and in the product it is a content
// fingerprint, so no two vocabularies here share one either.
test("both channels contribute, and only recorded declarations own a selector", () => {
  load("channels", {
    "lf-index-action": { "x-state": { set: { record: { role: "value" } } } },
    "lf-index-report": { "x-report": { measure: { record: { role: "body" } } } },
    "lf-index-recordless": { "x-state": { settle: {} } },
  });

  assert.deepEqual(
    stateSpecs().map(({ tag, channel, verb, spec }) => [
      tag,
      channel,
      verb,
      Boolean(spec.record),
    ]),
    [
      ["lf-index-action", "x-state", "set", true],
      ["lf-index-report", "x-report", "measure", true],
      ["lf-index-recordless", "x-state", "settle", false],
    ],
  );
  assert.deepEqual(recordedWidgetSelector().split(","), [
    "lf-index-action",
    "lf-index-report",
  ]);
});

test("a later generation inherits nothing from the index warmed before it", () => {
  load("warmed", { "lf-index-gone": { "x-state": { set: { record: {} } } } });
  assert.deepEqual(
    stateSpecs().map(({ tag }) => tag),
    ["lf-index-gone"],
  );

  load("later", { "lf-index-fresh": { "x-report": { measure: {} } } });
  assert.deepEqual(
    stateSpecs().map(({ tag }) => tag),
    ["lf-index-fresh"],
  );
  assert.equal(recordedWidgetSelector(), "");
});
