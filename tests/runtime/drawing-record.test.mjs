import assert from "node:assert/strict";
import test from "node:test";

import { DRAWING_FORMAT, validDrawing } from "/runtime/composing/drawing-record.js";

const strokes = [
  [
    [80, 20],
    [240, 60],
  ],
];

test("the page accepts the drawings the door accepts", () => {
  // The bounds the door's schema states in registry.json: a record the page refused
  // would drop ink the log holds, and one it alone accepted would be refused on send.
  const drawing = (fields) => ({ format: DRAWING_FORMAT, strokes, ...fields });
  for (const accepted of [
    {},
    { box: [640.5, 96] },
    { says: "to reap every process … before exporting" },
    { says: "𝒳".repeat(500) },
  ])
    assert.equal(validDrawing(drawing(accepted)), true, JSON.stringify(accepted));
  for (const refused of [
    { box: [640.5, 0] },
    { box: [640.5] },
    { box: [640.5, 96, 1] },
    { box: [640.5, 33554433] },
    { says: "" },
    { says: "x".repeat(501) },
    { says: ["to reap"] },
    { words: "to reap" },
  ])
    assert.equal(validDrawing(drawing(refused)), false, JSON.stringify(refused));
});
