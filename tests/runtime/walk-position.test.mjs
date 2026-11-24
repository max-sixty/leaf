/* How long the place a widget's step says stands (runtime/walk-position.js): for the
   step's moment, and no longer than the stop it was said on stays in the page. */
import assert from "node:assert/strict";
import test from "node:test";

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
/** @param {import("node:test").TestContext} t */
function stop(t) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const row = document.body.appendChild(document.createElement("div"));
  t.after(() => {
    row.remove();
    window.happyDOM.cancelAsync();
  });
  return row;
}

test("a place a widget's step says stands for the step's moment", (t) => {
  const row = stop(t);
  say(row, 3);
  assert.deepEqual(
    [walkPosition()?.text, walkPosition()?.target],
    ["Hunk 3 of 7", row],
  );
  // A later step's moment runs from that step.
  t.mock.timers.tick(NOTICE_MS - 1);
  say(row, 4);
  t.mock.timers.tick(NOTICE_MS - 1);
  assert.equal(walkPosition()?.text, "Hunk 4 of 7");
  t.mock.timers.tick(1);
  assert.equal(walkPosition(), null);
});

test("a place goes with the stop it was said on", (t) => {
  const row = stop(t);
  say(row, 3);
  row.remove();
  assert.equal(walkPosition(), null);
});
