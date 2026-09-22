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
  secondaryCount,
  choosePrimary,
  entryHasMarginHost,
} from "../../skills/leaf/assets/runtime/margin-model.js";
import { marginMapGroups } from "../../skills/leaf/assets/runtime/margin-map-model.js";

const control = (key, options = {}) =>
  marginEntry({ key, glyph: "+", label: key, ...options });
const offer = (key, entries, options = {}) => {
  const { readings, ...reading } = normalizeMarginReading({ entries, ...options }, key);
  return Object.freeze({
    key,
    reading: Object.freeze({ ...reading, hasReadings: readings.length > 0 }),
  });
};
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
const choiceNames = (items) =>
  items.map(
    (item) =>
      item.record?.key ??
      (item.choice.kind === "comment" ? "threadList" : item.choice.items[0].id),
  );

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

test("long subjects stay visible and searchable while spoken controls stay concise", () => {
  for (const text of [
    "An explanation with words to keep together. ".repeat(10),
    `Paragraph · ${"説明文𠮷".repeat(90)}`,
    `Link · https://example.com/${"long".repeat(90)}`,
  ]) {
    const entry = inventory({
      title: text,
      items: [marker("discussion", "comment", { text })],
    });
    const cluster = clusterProjection(entry);
    const mapped = map([entry])[0];
    assert.equal(entry.title, text);
    assert.equal(mapped.actions[0].visibleLabel, text);
    assert.ok(mapped.search.includes(text.toLocaleLowerCase()));
    for (const [label, prefix] of [
      [cluster.label, "Page actions for "],
      [cluster.moreLabel, "More options for "],
      [cluster.options.label, "More options for "],
      [mapped.actions[0].label, "Open thread: "],
    ]) {
      assert.ok(label.startsWith(prefix));
      const subject = label.slice(prefix.length);
      assert.ok([...subject].length <= 120);
      assert.ok([...subject].length >= 60);
      assert.ok(subject.endsWith("…"));
      assert.ok(text.startsWith(subject.slice(0, -1)));
    }
  }
});

test("placement counts claimed after controls while an unclaimed cluster keeps only readings", () => {
  for (const claimed of [false, true]) {
    const entry = inventory({
      offers: [
        offer("direct", [control("primary"), control("peer")], { claim: claimed }),
        offer("after", [control("after-peer")], { side: "after", claim: false }),
      ],
      items: [marker("question", "ask")],
    });
    assert.equal(secondaryCount(entry, choosePrimary(entry)), 3);
    assert.equal(
      secondaryCount(entry, choosePrimary(entry), { claimedOnly: true }),
      claimed ? 2 : 1,
    );
    assert.equal(entryHasMarginHost(entry), true);
  }
  const entry = inventory({
    offers: [offer("after", [control("peer")], { side: "after" })],
  });
  assert.equal(choosePrimary(entry), null);
  assert.equal(secondaryCount(entry, null, { claimedOnly: true }), 1);
});

test("focused owner exposes only its controls and retains the six-seat budget", () => {
  const entry = inventory({
    offers: [
      offer("standing", [control("primary")]),
      offer(
        "reaction",
        Array.from({ length: 6 }, (_, index) => control(String(index))),
        { side: "after" },
      ),
    ],
    items: [marker("conversation", "comment")],
  });
  const focused = clusterProjection(entry, {
    expandedKey: entry.key,
    expandedOwner: "reaction",
  });
  assert.equal(focused.primary, null);
  assert.deepEqual(choiceNames(focused.options.visible), [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
  ]);
  assert.equal(focused.options.spill, null);
  assert.equal(focused.options.hidden, false);
});

test("reading IDs belong to their contribution in both margin and Page Map", () => {
  const entry = inventory({
    items: [null, "first", "second"].map((owner) => marker("same", "ask", { owner })),
  });
  const choices = readingChoices(entry);
  assert.equal(new Set(choices.map((choice) => choice.key)).size, 3);
  const cluster = clusterProjection(entry, { expandedKey: entry.key });
  assert.deepEqual(
    new Set(
      [choices[0], ...cluster.options.items.map((item) => item.choice)].map(
        (choice) => choice.items[0].owner,
      ),
    ),
    new Set([null, "first", "second"]),
  );
  const actions = map([entry])[0].actions;
  assert.equal(new Set(actions.map((action) => action.key)).size, 3);
  assert.deepEqual(
    actions.map((action) => action.item.owner),
    [null, "first", "second"],
  );
});

test("contribution admission rejects missing and duplicate reading identities", () => {
  for (const readings of [[{}], [{ id: "" }], [{ id: "same" }, { id: "same" }]]) {
    assert.throws(
      () => normalizeMarginReading({ readings }, "owner"),
      /Margin reading IDs must be nonempty and unique/,
    );
  }
});
