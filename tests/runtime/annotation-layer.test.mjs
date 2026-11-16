/* The annotation layer's one door: who hears it hidden, and when its command takes a
   press. */
import assert from "node:assert/strict";
import test from "node:test";

import {
  annotationsHidden,
  mountAnnotationControls,
  restoreAnnotations,
  watchAnnotationLayer,
} from "/runtime/annotation-layer.js";
import { commandAvailable, commandRun } from "/runtime/keyboard/bindings.js";
import { pageScopes } from "/runtime/keyboard/register.js";
import { mountRepaint } from "/runtime/repaint.js";
import { nextRender } from "/runtime/rendering.js";
import { tabStore } from "/runtime/tab-store.js";

const frame = () => new Promise((resolve) => nextRender(resolve));

test("a layer's watchers decide when hiding it takes a press, and hear it hidden", async (t) => {
  mountAnnotationControls();
  // The frame that repaints the leaf's menu row for the command.
  let repaints = 0;
  mountRepaint({ paintTouchControls: () => repaints++ });
  t.after(() => mountRepaint({}));
  await frame();
  const toggle = pageScopes()
    .flatMap((scope) => (typeof scope === "symbol" ? [] : scope.rows))
    .find((row) => row.id === "annotations.toggle");
  const press = () => commandRun(toggle, "o")();

  assert.equal(commandAvailable(toggle), false, "nothing draws a layer to hide");

  // A watcher joining a shown layer draws shown already, so it hears nothing, and its
  // joining repaints the row that now takes a press.
  const heard = [];
  let painted = repaints;
  const leave = watchAnnotationLayer((hidden) => heard.push(hidden));
  await frame();
  assert.ok(repaints > painted, "joining repaints the command's row");
  assert.deepEqual(heard, []);
  assert.equal(commandAvailable(toggle), true);

  press();
  assert.deepEqual(heard, [true]);
  assert.equal(annotationsHidden(), true);
  assert.equal(document.documentElement.getAttribute("data-lf-annotations"), "hidden");

  // One joining a hidden layer hears so at once, as a widget upgrading after the tab's
  // state was restored does.
  const late = [];
  const leaveLate = watchAnnotationLayer((hidden) => late.push(hidden));
  assert.deepEqual(late, [true]);
  leaveLate();
  await frame();

  // The last watcher leaving a hidden layer leaves the press that shows it again.
  painted = repaints;
  leave();
  await frame();
  assert.ok(repaints > painted, "leaving repaints the command's row");
  assert.equal(commandAvailable(toggle), true, "a hidden layer can still be shown");
  press();
  assert.equal(annotationsHidden(), false);
  assert.equal(document.documentElement.hasAttribute("data-lf-annotations"), false);
  assert.deepEqual(heard, [true], "a watcher that left hears nothing more");
  assert.equal(commandAvailable(toggle), false);
});

test("a tab that hid the layer finds it hidden again", (t) => {
  // The prepaint opens the tab's store (prepaint.js), which this document has none of,
  // so the one key the layer keeps is answered here.
  const get = tabStore.get;
  tabStore.get = (key) => (key === "lf-annotations" ? "hidden" : get(key));
  t.after(() => {
    tabStore.get = get;
  });
  const heard = [];
  const leave = watchAnnotationLayer((hidden) => heard.push(hidden));
  restoreAnnotations();
  assert.equal(annotationsHidden(), true);
  assert.deepEqual(heard, [true]);
  leave();
});
