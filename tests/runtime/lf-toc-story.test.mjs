/* The contents' update as a story (`Story`, @effect/ui/testing): how the reader's
   disclosure choice survives the forms that stand the outline open, with no page behind
   it. Where the reader is and what the map leaves off are the Mounts' to measure, and
   the drawing is the browser suite's (`tests/browser/widgets/test_contents_and_glosses.py`). */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Effect } from "/vendor/effect-ui.js";
import { Toc, TocMessage } from "../../packages/default/widgets/lf-toc.js";

const props = { main: null, open: false, sections: [] };

/** @param {(s: any) => void} story @param {object} [given] */
const run = (story, given = {}) =>
  Effect.gen(function* () {
    story(yield* Story.make(Toc, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

test("the disclosure opens as the author asked and follows the reader's press", () => {
  run(
    (s) => {
      assert.equal(s.model.open, true);
      s.send(TocMessage.Toggled({ open: false }));
      assert.equal(s.model.open, false);
    },
    { open: true },
  );
});

test("a form that stands the outline open keeps the reader's choice for flow", () => {
  run((s) => {
    s.send(TocMessage.Exposed({ exposed: true, keep: false }));
    // The browser's toggle as the form opens the disclosure is not the reader's.
    s.send(TocMessage.Toggled({ open: true }));
    assert.deepEqual([s.model.exposed, s.model.open], [true, false]);
    s.send(TocMessage.Exposed({ exposed: false, keep: false }));
    assert.deepEqual([s.model.exposed, s.model.open], [false, false]);
  });
});

test("returning to flow keeps the outline open while focus is on one of its links", () => {
  run((s) => {
    s.send(TocMessage.Exposed({ exposed: true, keep: false }));
    s.send(TocMessage.Exposed({ exposed: false, keep: true }));
    assert.equal(s.model.open, true);
  });
});
