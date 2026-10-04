import assert from "node:assert/strict";
import test from "node:test";

import {
  DRAWING_FORMAT,
  strokesIn,
  validDrawing,
} from "/runtime/composing/drawing-record.js";

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
    { says: ["to reap"] },
    { words: "to reap" },
  ])
    assert.equal(validDrawing(drawing(refused)), false, JSON.stringify(refused));
});

test("an anchored drawing keeps its share of the box it was drawn in", () => {
  // Drawn on a 320 by 80 element, replayed once the window has narrowed it to 160 by 120:
  // each axis scales on its own, so a mark past the right edge stays past it.
  const drawing = { format: DRAWING_FORMAT, strokes, box: [320, 80] };
  assert.deepEqual(strokesIn(drawing, { width: 160, height: 120 }), [
    [
      [40, 30],
      [120, 90],
    ],
  ]);
  assert.deepEqual(strokesIn(drawing, { width: 320, height: 80 }), strokes);
  // A page drawing has no box, so it stands where it was drawn at any width.
  assert.deepEqual(
    strokesIn({ format: DRAWING_FORMAT, strokes }, { width: 10, height: 10 }),
    strokes,
  );
});
