/* The page edge and Page Map derive their choices from captured values, before any
   control exists. These cases intentionally import without the DOM test preload. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  marginEntry,
  normalizeMarginReading,
} from "../../skills/leaf/assets/runtime/margin-entry-model.js";
import {
  KINDS,
  clusterProjection,
  marginInventory,
  readingChoices,
} from "../../skills/leaf/assets/runtime/margin-model.js";
import { marginMapGroups } from "../../skills/leaf/assets/runtime/margin-map-model.js";

const control = (key, options = {}) =>
  marginEntry({ key, glyph: "+", label: key, ...options });
const offer = (key, entries, options = {}) =>
  Object.freeze({
    key,
    reading: normalizeMarginReading({ entries, ...options }, key),
  });
const group = (options = {}) => ({
  key: "target",
  targetId: "target",
  title: "Decision",
  searchText: "Author's context",
  offers: [],
  items: [],
  workflowReceipt: null,
  ...options,
});
const inventory = (options) => marginInventory([group(options)])[0];
const marker = (id, kind, options = {}) => ({
  id,
  kind,
  text: id,
  ...options,
});
const map = (entries) =>
  marginMapGroups(
    entries,
    (item) => KINDS[item.kind],
    new Map(entries.map((entry) => [entry.key, entry.searchText])),
  );
const choiceNames = (items) => items.map((item) => item.record?.key ?? item.choice.key);

test("one peer stays directly usable; two peers earn More", () => {
  const entryFor = (entries) => inventory({ offers: [offer("widget", entries)] });
  const two = clusterProjection(
    entryFor([control("save", { rank: "complete" }), control("cancel")]),
  );
  assert.equal(two.primary.record.key, "save");
  assert.equal(two.hasOptions, false);
  assert.equal(two.options.hidden, false);
  assert.deepEqual(choiceNames(two.options.visible), ["cancel"]);

  const threeEntry = entryFor([
    control("save", { rank: "complete" }),
    control("cancel"),
    control("details"),
  ]);
  const closed = clusterProjection(threeEntry);
  assert.equal(closed.hasOptions, true);
  assert.equal(closed.options.hidden, true);
  const open = clusterProjection(threeEntry, { expandedKey: threeEntry.key });
  assert.equal(open.options.hidden, false);
  assert.deepEqual(choiceNames(open.options.visible), ["cancel", "details"]);
});

test("interaction urgency outranks completion; completion leads equal-state peers", () => {
  const entryFor = (state) =>
    inventory({
      offers: [
        offer("finish", [control("save", { rank: "complete" })]),
        offer("retry", [control("retry")], { state }),
        offer("other", [control("details")]),
      ],
    });
  const idle = clusterProjection(entryFor("idle"));
  assert.equal(idle.primary.record.key, "save");
  assert.equal(idle.options.hidden, true);
  for (const state of ["engaged", "busy", "failed"]) {
    const active = clusterProjection(entryFor(state));
    assert.equal(active.primary.record.key, "retry", state);
    assert.equal(active.options.hidden, false, state);
    assert.equal(active.state, state);
  }
  const competing = clusterProjection(
    inventory({
      offers: [
        offer("busy", [control("save", { rank: "complete" })], { state: "busy" }),
        offer("failed", [control("retry")], { state: "failed" }),
      ],
    }),
  );
  assert.equal(competing.primary.record.key, "retry");
});

test("threads aggregate into one control and retain captured conversation order", () => {
  const entry = inventory({
    items: [
      marker("z-newest", "comment"),
      marker("ask", "ask"),
      marker("a-older", "comment"),
      marker("revision", "change"),
    ],
  });
  const choices = readingChoices(entry);
  assert.deepEqual(
    choices.map((choice) => choice.kind),
    ["change", "comment", "ask"],
  );
  assert.deepEqual(
    choices[1].items.map((item) => item.id),
    ["z-newest", "a-older"],
  );
  const cluster = clusterProjection(entry, { expandedKey: entry.key });
  assert.deepEqual(choiceNames(cluster.options.visible), ["threadList", "ask"]);
});

test("an open thread replaces a spilled peer while Page Map retains every action", () => {
  const entry = inventory({
    offers: [
      offer("widget", [
        control("save", { rank: "complete" }),
        ...["a", "b", "c", "d", "e", "f"].map((key) => control(key)),
      ]),
    ],
    items: [marker("conversation", "comment")],
  });
  const ordinary = clusterProjection(entry, { expandedKey: entry.key });
  assert.deepEqual(choiceNames(ordinary.options.visible), ["a", "b", "c", "d"]);
  const forced = clusterProjection(entry, {
    expandedKey: entry.key,
    forcedInlineKey: entry.key,
  });
  assert.deepEqual(choiceNames(forced.options.visible), ["a", "b", "c", "threadList"]);
  assert.equal(forced.options.spill.count, 3);
  assert.equal(forced.options.spill.first.record.key, "d");
  const [pageMap] = map([entry]);
  assert.deepEqual(
    pageMap.actions.map((action) => action.record?.key ?? action.item.id),
    ["conversation", "save", "a", "b", "c", "d", "e", "f"],
  );
});

test("declared representation and a workflow carrier suppress only duplicate readings", () => {
  const workflowReceipt = Object.freeze({ id: "claim" });
  const items = [
    marker("declared", "change", { marker: false, represents: true, owner: "widget" }),
    marker("duplicate", "change"),
    marker("receipt", "activity", {
      workflowFace: KINDS.activity,
      carriesWorkflow: true,
    }),
    marker("other-work", "activity", { workflowFace: KINDS.activity }),
    marker("conversation", "comment"),
  ];
  const entry = inventory({
    items,
    workflowReceipt,
    offers: [offer("widget", [control("apply")])],
  });
  assert.deepEqual(
    entry.items.map((item) => item.id),
    ["declared", "conversation", "other-work"],
  );
  assert.deepEqual(entry.workflowCarrier, {
    key: "apply",
    owner: "widget",
    receipt: workflowReceipt,
  });
  assert.deepEqual(
    map([entry])[0].actions.map((action) => action.record?.key ?? action.item.id),
    ["conversation", "other-work", "apply"],
  );
  const withoutControl = inventory({ items, workflowReceipt });
  assert.equal(withoutControl.workflowCarrier, null);
  assert.ok(withoutControl.items.some((item) => item.id === "receipt"));
});

test("Page Map uses opaque coordinates without delimiter collisions", () => {
  const entries = marginInventory([
    group({ key: "a:b", offers: [offer("c", [control("d")])] }),
    group({
      key: "a",
      offers: [offer("b:c", [control("d")]), offer("b", [control("c:d")])],
    }),
  ]);
  const groups = map(entries);
  const actions = groups.flatMap((group) => group.actions);
  assert.equal(new Set(actions.map((action) => action.key)).size, 3);
  assert.equal(new Set(actions.map((action) => action.id)).size, 3);
  assert.equal(groups[0].search, "decision d author's context");
  assert.ok(Object.isFrozen(entries));
  assert.ok(Object.isFrozen(groups[0].actions));
  assert.ok(Object.isFrozen(actions[0]));
});
