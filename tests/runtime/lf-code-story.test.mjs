/* The code block's update as a story (`Story`, @effect/ui/testing): what the reader's
   wrap and notes presses keep for the tab, and the rows a body, its `lines` and its
   notes make, with no page, element or Leaf behind them. The drawing on a page is the
   browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { KeepInTab } from "/runtime/widget-services.js";
import { Code, rowsOf } from "../../packages/default/widgets/lf-code.js";

const props = {
  id: "walk",
  source: "def f():\n    return 1",
  lang: null,
  lines: null,
  hi: null,
  follows: null,
  notes: [],
  interactive: true,
  savedWrap: null,
  savedNotes: null,
};

/** @param {object} given @param {(s: any) => void} story */
const tell = (given, story) =>
  Effect.gen(function* () {
    story(yield* Story.make(Code, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

test("a wrap press turns the lines the other way from how they stood, for the tab", () =>
  tell({}, (s) => {
    assert.equal(s.model.wrap, null);
    s.send({ _tag: "ToggledWrap", wrapped: true })
      .expectExact(KeepInTab.make({ key: "code-wrap:walk", value: "false" }))
      .resolve(KeepInTab, Component.noop);
    assert.equal(s.model.wrap, false);
  }));

test("a notes press hides the notes, for the tab, and the next shows them", () =>
  tell({}, (s) => {
    s.send({ _tag: "ToggledNotes" })
      .expectExact(KeepInTab.make({ key: "code-notes:walk", value: "hidden" }))
      .resolve(KeepInTab, Component.noop);
    assert.equal(s.model.notesShown, false);
    s.send({ _tag: "ToggledNotes" })
      .expectExact(KeepInTab.make({ key: "code-notes:walk", value: "shown" }))
      .resolve(KeepInTab, Component.noop);
    assert.equal(s.model.notesShown, true);
  }));

test("the tab's kept choices are where the block starts", () =>
  tell({ savedWrap: "true", savedNotes: "hidden" }, (s) => {
    assert.equal(s.model.wrap, true);
    assert.equal(s.model.notesShown, false);
  }));

test("an excerpt numbers its lines from its ranges, with a gap's notes as its caption", () => {
  const line = (text) => [{ text, style: {} }];
  const [docked, gap, far] = ["docked", "gap", "far"];
  const { rows, foot, last } = rowsOf([line("a"), line("  b"), line("c")], "10-11,20", [
    { at: 11, note: docked },
    { at: 15, note: gap },
    { at: 99, note: far },
  ]);
  assert.deepEqual(
    rows.map((row) =>
      row.kind === "line"
        ? [row.n, row.indent, row.notes]
        : [`${row.from}-${row.to}`, row.captions],
    ),
    [
      [10, 0, []],
      [11, 2, [docked]],
      ["12-19", [gap]],
      [20, 0, []],
    ],
  );
  assert.deepEqual(foot, [far]);
  assert.equal(last, 20);
});
