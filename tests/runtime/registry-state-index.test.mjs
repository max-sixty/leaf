/* The one traversal of `verbs`, and the generation it belongs to.

   Derived state declarations belong to one complete registry generation. Warming the
   index must not make a later generation inherit the declarations of the one before it,
   and verbs of both writers contribute while only recorded declarations contribute owner
   selectors.

   The vocabulary is stated here rather than loaded, so what the index returns is caused
   by these declarations and by nothing else a page might have vendored. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  adoptRegistry,
  elementDeclarations,
  recordedWidgetSelector,
  registry,
  sameRecord,
  stateSpecs,
} from "/runtime/state/registry.js";

const load = (generation, declarations) => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  adoptRegistry({ ...declarations, $layer: { generation } });
};

test("a vocabulary that has not loaded has no state index to give", () => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  assert.throws(stateSpecs, /state vocabulary requested before registry loaded/);
  // The generation is what says a vocabulary arrived, so an unstamped one is refused
  // rather than indexed as the empty vocabulary it would otherwise look like.
  load("", {});
  assert.throws(stateSpecs, /state vocabulary requested before registry loaded/);
});

test("authoring selectors and shared facts never enter widget state", () => {
  const idiom = {
    description: "An authored shape.",
    example: "<table></table>",
  };
  load("mixed-vocabulary", {
    "lf-index-owner": {
      verbs: { set: {} },
    },
    "lf-index-owner.selected": idiom,
    table: idiom,
    ".lf-lede": idiom,
    $keys: {
      verbs: "State meanings.",
    },
  });
  assert.deepEqual(
    elementDeclarations().map(([name]) => name),
    ["lf-index-owner"],
  );
  assert.deepEqual(
    stateSpecs().map(({ tag }) => tag),
    ["lf-index-owner"],
  );
});

// The generation is the index's cache key, and in the product it is a content
// fingerprint, so no two vocabularies here share one either.
test("both writers contribute, and only recorded declarations own a selector", () => {
  load("writers", {
    "lf-index-action": {
      verbs: { set: { record: { kind: "value", attr: "phase" } } },
    },
    "lf-index-report": {
      verbs: {
        measure: { writer: "agent", record: { kind: "value", attr: "phase" } },
      },
    },
    "lf-index-recordless": {
      verbs: { settle: {} },
    },
  });

  assert.deepEqual(
    stateSpecs().map(({ tag, verb, spec }) => [tag, verb, Boolean(spec.record)]),
    [
      ["lf-index-action", "set", true],
      ["lf-index-report", "measure", true],
      ["lf-index-recordless", "settle", false],
    ],
  );
  assert.deepEqual(
    recordedWidgetSelector({ kind: "value", attr: "phase" }).split(","),
    ["lf-index-action", "lf-index-report"],
  );
});

test("a later generation inherits nothing from the index warmed before it", () => {
  load("warmed", {
    "lf-index-gone": {
      verbs: { set: { record: {} } },
    },
  });
  assert.deepEqual(
    stateSpecs().map(({ tag }) => tag),
    ["lf-index-gone"],
  );

  load("later", {
    "lf-index-fresh": {
      verbs: { measure: {} },
    },
  });
  assert.deepEqual(
    stateSpecs().map(({ tag }) => tag),
    ["lf-index-fresh"],
  );
  assert.equal(recordedWidgetSelector({ kind: "value", attr: "phase" }), "");
});

test("records that differ only in how the element keeps the value are one record", () => {
  const phase = { kind: "value", attr: "phase" };
  assert.ok(sameRecord(phase, { ...phase, property: "value", event: "sl-change" }));
  assert.ok(!sameRecord(phase, { kind: "value", attr: "status" }));
  assert.ok(!sameRecord(phase, { kind: "attribute", attr: "phase" }));
  assert.ok(
    !sameRecord(
      { kind: "position", within: "lf-lane" },
      { kind: "position", within: "lf-shelf" },
    ),
  );
  assert.ok(sameRecord(undefined, undefined));
  assert.ok(!sameRecord(phase, undefined));
});

test("a layer-wide declaration is frozen as the registry adopts it", () => {
  load("frozen", { $work: { widgets: { "lf-task": { role: "goal" } } } });
  assert.throws(() => {
    registry.$work.widgets["lf-task"].role = "worker";
  }, TypeError);
  assert.equal(registry.$work.widgets["lf-task"].role, "goal");
});
