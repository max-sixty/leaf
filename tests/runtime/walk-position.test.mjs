/* How long the place a widget's step says stands (runtime/records/walk-position.js): for the
   step's moment, no longer than the stop it was said on stays in the page, no longer
   than focus stays on a stop that held it, and no longer than the widget says the user
   stays on that stop. A step that says none ends it too, which takes a laid-out page to
   show (tests/browser/test_render_floating_panel.py). */
import assert from "node:assert/strict";
import test from "node:test";
import { setImmediate } from "node:timers";

import { NOTICE_MS } from "/runtime/transport/notifications.js";
import { walkPosition } from "/runtime/records/walk-position.js";

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

test("a place goes as the widget says the user has left its stop", (t) => {
  const stop = row(t);
  const other = document.body.appendChild(document.createElement("div"));
  t.after(() => other.remove());
  /** @param {Element} left */
  const leave = (left) =>
    left.dispatchEvent(new CustomEvent("lf-walk", { bubbles: true, composed: true }));
  say(stop, 3);
  // Said on another stop, it is about a place that has already gone.
  leave(other);
  assert.equal(walkPosition()?.text, "Hunk 3 of 7");
  leave(stop);
  assert.equal(walkPosition(), null);
});

// A box the test can focus, in the page until the test ends.
/** @param {import("node:test").TestContext} t @param {Element} [within] */
function stopIn(t, within = document.body) {
  const box = within.appendChild(document.createElement("button"));
  t.after(() => box.remove());
  return box;
}

test("a place goes as focus leaves a stop that held it", (t) => {
  const stop = row(t);
  const [inside, also, away] = [stopIn(t, stop), stopIn(t, stop), stopIn(t)];
  inside.focus();
  say(stop, 3);
  // Focus that moves within the stop is the user still at it.
  also.focus();
  assert.equal(walkPosition()?.text, "Hunk 3 of 7");
  away.focus();
  assert.equal(walkPosition(), null);
  // A widget may say its place before it moves focus to the stop.
  say(stop, 4);
  inside.focus();
  assert.equal(walkPosition()?.text, "Hunk 4 of 7");
  away.focus();
  assert.equal(walkPosition(), null);
});

test("focus moving elsewhere leaves a place said on a stop that never held it", (t) => {
  const stop = row(t);
  const [here, there] = [stopIn(t), stopIn(t)];
  here.focus();
  say(stop, 3);
  there.focus();
  assert.equal(walkPosition()?.text, "Hunk 3 of 7");
});
