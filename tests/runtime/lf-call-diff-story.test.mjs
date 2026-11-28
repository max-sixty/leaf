/* The call diff's update as stories (`Story`, @effect/ui/testing): which roots the
   reader folded, and what a press asks of Leaf, with no page behind it. The drawing
   and the travel on a page are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { Announce, NavigateToDatum } from "/runtime/widget-services.js";
import { CallDiff, CallDiffMessage } from "../../packages/diff/widgets/lf-call-diff.js";

/** @param {string} label @param {number} line */
const root = (label, line) => ({
  entry: label,
  tree: { key: label, label, status: "same", file: "app.py", line, children: [] },
});
const value = {
  mode: "diff",
  from: "main",
  to: "feature",
  trees: [root("first()", 1), root("second()", 2)],
};
const keys = [
  JSON.stringify(["first()", "first()", "unchanged", "app.py", 1, 0]),
  JSON.stringify(["second()", "second()", "unchanged", "app.py", 2, 0]),
];

/** @param {(s: any) => void} body */
const story = (body) =>
  Effect.gen(function* () {
    body(yield* Story.make(CallDiff, { value, diff: "patch" }));
  }).pipe(Effect.scoped, Effect.runSync);

test("a root the reader folds stays folded until they open it", () => {
  story((s) => {
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: false }));
    assert.deepEqual(s.model.closed, [keys[0]]);
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: true }));
    assert.deepEqual(s.model.closed, []);
  });
});

test("a fold the Model already holds, as the toggle answering its own write, leaves the Model as it stands", () => {
  story((s) => {
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: false }));
    const folded = s.model;
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: false }));
    assert.equal(s.model, folded);
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: true }));
    const opened = s.model;
    s.send(CallDiffMessage.ToggledGroup({ key: keys[0], open: true }));
    assert.equal(s.model, opened);
  });
});

test("the toggle folds every root, then opens them all once any is folded", () => {
  story((s) => {
    s.send(CallDiffMessage.ClickedToggle())
      .expectExact(Announce.make({ words: "Collapsed all call-tree roots" }))
      .resolve(Announce, Component.noop);
    assert.deepEqual(s.model.fold, { open: false, press: 1 });
    // The browser folds each root through its node, and tells the Model with `toggle`.
    for (const key of keys) s.send(CallDiffMessage.ToggledGroup({ key, open: false }));
    s.send(CallDiffMessage.ToggledGroup({ key: keys[1], open: true }));
    s.send(CallDiffMessage.ClickedToggle())
      .expectExact(Announce.make({ words: "Expanded all call-tree roots" }))
      .resolve(Announce, Component.noop);
    assert.deepEqual(s.model.fold, { open: true, press: 2 });
  });
});

test("a location's press travels to its line in the linked diff, taking focus there", () => {
  story((s) => {
    const key = JSON.stringify(["app.py", "source", "new", 2]);
    s.send(CallDiffMessage.ClickedLocation({ key, text: "app.py:2" }))
      .expectExact(
        NavigateToDatum.make({
          reference: "diff",
          key,
          success: "Opened app.py:2 in the exact patch",
          missing: "app.py:2 is not present in the exact patch",
          focus: true,
        }),
      )
      .resolve(NavigateToDatum, Component.noop);
  });
});
