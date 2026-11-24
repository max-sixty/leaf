/* How long the place a widget's step says stands (runtime/walk-position.js): for the
   step's moment, and no longer than the stop it was said on stays in the page. A step
   that says none ends it too, which takes a laid-out page to show
   (tests/browser/test_render_floating_panel.py). */
import assert from "node:assert/strict";
import test from "node:test";
import { setImmediate } from "node:timers";

import { NOTICE_MS } from "/runtime/notifications.js";
import { walkPosition } from "/runtime/walk-position.js";

/** @param {Element} stop @param {number} position */
const say = (stop, position) =>
  stop.dispatchEvent(
    new CustomEvent("lf-walk", {
      bubbles: true,
      composed: true,
      detail: { noun: "Hunk", position, total: 7 },
    }),
  );
// A stop in the page, on a clock the test runs, so no step's moment outlives its test.
/** @param {import("node:test").TestContext} t */
function row(t) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const stop = document.body.appendChild(document.createElement("div"));
  t.after(() => stop.remove());
  return stop;
}

test("a place a widget's step says stands for the step's moment", (t) => {
  const stop = row(t);
  say(stop, 3);
  assert.deepEqual(
    [walkPosition()?.text, walkPosition()?.target],
    ["Hunk 3 of 7", stop],
  );
  // A later step's moment runs from that step.
  t.mock.timers.tick(NOTICE_MS - 1);
  say(stop, 4);
  t.mock.timers.tick(NOTICE_MS - 1);
  assert.equal(walkPosition()?.text, "Hunk 4 of 7");
  t.mock.timers.tick(1);
  assert.equal(walkPosition(), null);
});

test("a place goes as the stop it was said on leaves the page", async (t) => {
  const stop = row(t);
  say(stop, 3);
  assert.equal(walkPosition()?.text, "Hunk 3 of 7");
  stop.remove();
  // The page hears a departure with its next batch of mutations.
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(walkPosition(), null);
});
