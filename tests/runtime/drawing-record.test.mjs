import assert from "node:assert/strict";
import test from "node:test";

import { DRAWING_FORMAT, validDrawing } from "/runtime/composing/drawing-record.js";

const strokes = [
  [
    [80, 20],
    [240, 60],
  ],
];

test("the page accepts the drawings the door accepts, and a draft's", () => {
  // The bounds are the door's schema in registry.json, which the page's copy is
  // generated from. The page also takes a draft's shape, whose `box` is optional and
  // which may carry `at`; `sentDrawing` sends the door the comment's shape.
  const drawnIn = { viewport: [1280, 720], scheme: "light" };
  const drawing = (fields) => ({
    format: DRAWING_FORMAT,
    strokes,
    ...drawnIn,
    ...fields,
  });
  for (const accepted of [
    {},
    { box: [640.5, 96] },
    { at: [1, 0, 0, 1, 12, -40] },
    { frame: { root: "svg", path: [] } },
    {
      frame: {
        root: "figure",
        path: [{ tag: "svg", index: 1, siblings: 3, shadow: true }],
      },
    },
    { says: "to reap every process … before exporting" },
    { says: "𝒳".repeat(500) },
    { viewport: [390.5, 844], scheme: "dark" },
  ])
    assert.equal(validDrawing(drawing(accepted)), true, JSON.stringify(accepted));
  for (const refused of [
    { format: "leaf-drawing/2" },
    { frame: { root: "figure", path: [{ tag: "svg", index: 1 }] } },
    { frame: { root: "figure", path: [{ tag: "svg", index: -1, siblings: 3 }] } },
    {
      frame: {
        root: "figure",
        path: [{ tag: "svg", index: 1, siblings: 3, shadow: 1 }],
      },
    },
    {
      frame: {
        root: "figure",
        path: Array(33).fill({ tag: "svg", index: 0, siblings: 1 }),
      },
    },
    { box: [640.5, 0] },
    { box: [640.5] },
    { box: [640.5, 96, 1] },
    { box: [640.5, 33554433] },
    { says: "" },
    { says: ["to reap"] },
    { words: "to reap" },
    { viewport: [1280, 0] },
    { viewport: [1280] },
    { viewport: undefined },
    { scheme: "sepia" },
    { scheme: undefined },
  ])
    assert.equal(validDrawing(drawing(refused)), false, JSON.stringify(refused));
});
