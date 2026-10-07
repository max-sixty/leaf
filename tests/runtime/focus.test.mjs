/* Who moved the user, and whether they have moved on since.

   focus.js answers both for every owner. Each placement names its cause, and every
   reader of where the user stands hears it. One module keeps the two readings of
   "since": a hold asks whether focus was placed anywhere since it began, since typing in
   the box it holds is the user working there; delayed work asks whether the user did
   anything at all since the gesture that started it. A press on a label leaves the user
   standing on the control they stood on until the press lands. These are asked over
   happy-dom's focus, which moves focus and fires its events as a browser does but lays
   nothing out. */

import assert from "node:assert/strict";
import test from "node:test";

const { focusDestination, focused, holdFocus, onStanding } =
  await import("/runtime/focus.js");
const { retainUserIntent } = await import("/runtime/user-intent.js");

const heard = [];
onStanding((node, cause) => heard.push([node, cause]));

function scene() {
  document.body.replaceChildren();
  const box = document.createElement("section");
  const first = document.createElement("input");
  const second = document.createElement("input");
  const other = document.createElement("button");
  box.append(first, second);
  document.body.append(box, other);
  heard.length = 0;
  return { box, first, second, other };
}

const key = (target, key = "a") =>
  target.dispatchEvent(
    new window.KeyboardEvent("keydown", { key, bubbles: true, composed: true }),
  );
const pointer = (type, target) =>
  target.dispatchEvent(
    new window.PointerEvent(type, {
      bubbles: true,
      composed: true,
      isPrimary: true,
      button: 0,
      pointerId: 1,
    }),
  );
// The label's click alone, without the platform's activation of its control, which
// happy-dom would run: the tests focus the control themselves, or leave it unfocused.
const click = (target) =>
  target.dispatchEvent(
    new window.MouseEvent("click", { bubbles: true, composed: true, cancelable: true }),
  );
const settled = () => new Promise((resolve) => setTimeout(resolve));

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

test("a hold gives way to a placement, not to typing where it holds", () => {
  const { box, first, other } = scene();
  focusDestination(first, "move");
  const typed = holdFocus(box);
  key(first);
  const fresh = document.createElement("input");
  first.replaceWith(fresh);
  assert.equal(typed(fresh), true);
  assert.equal(focused(), fresh);

  const placed = holdFocus(box);
  focusDestination(other, "move");
  const again = document.createElement("input");
  fresh.replaceWith(again);
  assert.equal(placed(again), false);
  assert.equal(focused(), other);
});

test("delayed work gives way to any input since its gesture", () => {
  const { first } = scene();
  focusDestination(first, "move");
  const quiet = retainUserIntent();
  assert.equal(quiet(), true);
  const typed = retainUserIntent();
  key(first);
  assert.equal(typed(), false);
});

test("a press on a label keeps the user on the control they stood on until it lands", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  box.append(label);
  focusDestination(first, "move");
  heard.length = 0;
  pointer("pointerdown", label);
  // The press blurs the field to the body before the platform focuses the control.
  first.blur();
  await settled();
  assert.equal(focused(), first);
  assert.notEqual(holdFocus(box), null);
  assert.deepEqual(heard, []);
  pointer("pointerup", label);
  click(label);
  check.focus();
  assert.equal(focused(), check);
  assert.deepEqual(heard, [[check, "press"]]);
});

test("a label press through a focusable container tells no reader of the container", async () => {
  scene();
  const thread = document.createElement("section");
  thread.tabIndex = -1;
  const field = document.createElement("input");
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  thread.append(field, label);
  document.body.append(thread);
  focusDestination(field, "move");
  const held = holdFocus(thread);
  heard.length = 0;
  pointer("pointerdown", label);
  // The press's default focuses the containing thread before its click.
  thread.focus();
  await settled();
  assert.deepEqual(heard, []);
  assert.equal(focused(), field);
  pointer("pointerup", label);
  click(label);
  check.focus();
  await settled();
  assert.deepEqual(heard, [[check, "press"]]);
  assert.equal(held(), false);
});

test("a label press whose control takes no focus leaves the user nowhere, by their own move", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  const check = document.createElement("input");
  check.type = "checkbox";
  label.append("Agree", check);
  box.append(label);
  focusDestination(first, "move");
  const held = holdFocus(box);
  heard.length = 0;
  pointer("pointerdown", label);
  first.blur();
  pointer("pointerup", label);
  click(label);
  await settled();
  assert.deepEqual(heard, [[null, "move"]]);
  assert.equal(held(), false);
  assert.equal(document.activeElement, document.body);
});

test("a native menu lands a label press, whose release it swallowed", async () => {
  const { box, first } = scene();
  const label = document.createElement("label");
  label.append(
    "Agree",
    Object.assign(document.createElement("input"), { type: "checkbox" }),
  );
  box.append(label);
  focusDestination(first, "move");
  pointer("pointerdown", label);
  first.blur();
  label.dispatchEvent(
    new window.MouseEvent("contextmenu", { bubbles: true, composed: true }),
  );
  await settled();
  assert.equal(focused(), document.body);
});

test("delayed work follows a hold that carries the user to the node replacing theirs", () => {
  const { box, first } = scene();
  focusDestination(first, "move");
  const mayFocus = retainUserIntent();
  const restore = holdFocus(box);
  const fresh = document.createElement("input");
  first.replaceWith(fresh);
  assert.equal(restore(fresh), true);
  assert.equal(mayFocus(), true);
  // A second render carries the user on again before they do anything.
  const again = holdFocus(box);
  const newer = document.createElement("input");
  fresh.replaceWith(newer);
  assert.equal(again(newer), true);
  assert.equal(mayFocus(), true);
  key(newer);
  assert.equal(mayFocus(), false);
});
