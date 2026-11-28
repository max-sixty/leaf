/* The call diff's update as stories (`Story`, @effect/ui/testing): what a press asks of
   Leaf, with no page behind it; and how Expand all and Collapse all read the roots'
   folds, on an element. The drawing and the travel on a page are the browser suite's. */
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
/** @param {(s: any) => void} body */
const story = (body) =>
  Effect.gen(function* () {
    body(yield* Story.make(CallDiff, { value, diff: "patch" }));
  }).pipe(Effect.scoped, Effect.runSync);

test("the fold Expand all or Collapse all made is announced", () => {
  story((s) => {
    s.send(CallDiffMessage.Folded({ open: false }))
      .expectExact(Announce.make({ words: "Collapsed all call-tree roots" }))
      .resolve(Announce, Component.noop);
    s.send(CallDiffMessage.Folded({ open: true }))
      .expectExact(Announce.make({ words: "Expanded all call-tree roots" }))
      .resolve(Announce, Component.noop);
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

test("Expand all and Collapse all read the roots' folds as pressed, and say the fold they make next", async () => {
  const el = /** @type {HTMLElement & {value: unknown}} */ (
    document.createElement("lf-call-diff")
  );
  el.setAttribute("diff", "patch");
  el.value = value;
  document.body.append(el);
  await new Promise((resolve) => setTimeout(resolve));
  const control = () =>
    /** @type {HTMLButtonElement} */ (el.querySelector(".lf-call-toggle"));
  const roots = () =>
    /** @type {HTMLDetailsElement[]} */ ([
      ...el.querySelectorAll("details.lf-call-group"),
    ]);
  try {
    assert.equal(
      control().getAttribute("aria-label"),
      "Collapse all 2 call-tree roots",
    );
    // The reader folds one root, and presses before the browser's `toggle` arrives.
    roots()[0].open = false;
    control().click();
    assert.deepEqual(
      roots().map((root) => root.open),
      [true, true],
    );
    assert.equal(
      control().getAttribute("aria-label"),
      "Collapse all 2 call-tree roots",
    );
    control().click();
    assert.deepEqual(
      roots().map((root) => root.open),
      [false, false],
    );
    assert.equal(control().getAttribute("aria-label"), "Expand all 2 call-tree roots");
  } finally {
    el.remove();
  }
});
