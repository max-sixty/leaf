/* Who moved the user: focus.js tells every reader of where the user stands what moved
   them, and each placement names that cause. Asked over happy-dom's focus, which moves
   focus and fires its events as a browser does but lays nothing out. */

import assert from "node:assert/strict";
import test from "node:test";

const { focusDestination, onStanding } = await import("/runtime/focus.js");

const heard = [];
onStanding((node, cause) => heard.push([node, cause]));

function scene() {
  document.body.replaceChildren();
  const first = document.createElement("input");
  const second = document.createElement("input");
  const other = document.createElement("button");
  document.body.append(first, second, other);
  heard.length = 0;
  return { first, second, other };
}

test("a placement reaches every reader with the cause it names", () => {
  const { first, second, other } = scene();
  focusDestination(first, "move");
  focusDestination(second, "return");
  focusDestination(other, "step");
  assert.deepEqual(heard, [
    [first, "move"],
    [second, "return"],
    [other, "step"],
  ]);
  assert.throws(() => focusDestination(first), TypeError);
});
