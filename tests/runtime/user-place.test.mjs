/* The user's place in a scroller, and the one hold that keeps it across a change.

   Asked over boxes this file states, since happy-dom lays nothing out: focus is where
   the user is while they see it, a stuck header included, or while a glide carries them
   to it, and not once they scrolled it away; a hold puts the node it read
   back where it stood, or its stand-in where the change hid it, paying only for what
   the browser's own anchoring left. The user's place across a reading is the first the
   change moved of those they named, a field they type in before a resting pointer and
   the pointer only on a control, and its keep yields to a scroll since in a box scrolling
   the place and to the user's own press or key, but not to typing into the field it
   holds. */

import assert from "node:assert/strict";
import test from "node:test";

import { recentPlaceInput } from "/runtime/focus.js";
import { pointerAt } from "/runtime/pointer.js";
import { glideTo, startScroll, stopGlide } from "/runtime/scrolling.js";
import { focusPlace, holdPlace, holdUserPlace } from "/runtime/user-place.js";

// A scroller whose boxes are stated: each node's viewport top is its content top less
// the scroller's scrollTop.
function laidOut() {
  const scroller = document.createElement("div");
  scroller.style.overflowY = "auto";
  document.body.append(scroller);
  let scrollTop = 0;
  Object.defineProperty(scroller, "scrollTop", {
    get: () => scrollTop,
    set: (value) => {
      scrollTop = value;
    },
  });
  Object.defineProperties(scroller, {
    scrollHeight: { get: () => 5000 },
    clientHeight: { get: () => 400 },
    clientWidth: { get: () => 300 },
  });
  scroller.scrollTo = ({ top }) => {
    scrollTop = top;
  };
  scroller.getBoundingClientRect = () => new DOMRect(0, 0, 300, 400);
  const at = new Map();
  const item = (id, contentTop, height = 100) => {
    const node = document.createElement("section");
    node.className = "item";
    node.dataset.id = id;
    at.set(node, contentTop);
    node.getBoundingClientRect = () =>
      new DOMRect(0, at.get(node) - scrollTop, 300, node.hidden ? 0 : height);
    return node;
  };
  return {
    scroller,
    item,
    at,
    scrolled: () => scrollTop,
    scrollTo: (y) => (scrollTop = y),
  };
}

test("focus is where the user is while they see it or a glide carries them to it", () => {
  const { scroller, item, scrollTo } = laidOut();
  const [first, second] = [item("a", 1000), item("b", 1250)];
  first.tabIndex = 0;
  // A heading sticking at the scroller's top, which holds it at its own place until
  // its section scrolls past that top.
  const heading = document.createElement("h2");
  heading.tabIndex = 0;
  heading.style.position = "sticky";
  heading.style.top = "0px";
  heading.getBoundingClientRect = () =>
    new DOMRect(0, Math.max(second.getBoundingClientRect().top, 0), 300, 20);
  second.append(heading);
  scroller.append(first, second);

  scrollTo(1000);
  first.focus();
  assert.equal(focusPlace(), first);
  scrollTo(3000);
  assert.equal(focusPlace(), null, "focus scrolled away was still where the user is");
  // A walk focuses its stop before gliding there, so a key pressed on the way is meant
  // for the stop.
  glideTo(scroller, 1000);
  assert.equal(focusPlace(), first, "a glide to focus didn't carry the user there");
  stopGlide(scroller);
  assert.equal(focusPlace(), null);
  // A glide carrying focus out of view, as `g g` does, lets go of it once it has left.
  scrollTo(1500);
  glideTo(scroller, 4000);
  assert.equal(focusPlace(), null, "a glide carrying focus away kept it the place");
  stopGlide(scroller);
  // Nor is a key pressed while a card it moved slides from where it stood, though a box
  // clips it meanwhile; an endless animation, as the sheen's, a fade, a slide held paused
  // and one on a pseudo-element bring the user nowhere.
  const sliding =
    ({
      endTime = 150,
      playState = "running",
      property = "transform",
      pseudoElement = null,
    } = {}) =>
    () => [
      /** @type {Animation} */ (
        /** @type {unknown} */ ({
          playState,
          effect: {
            target: first,
            pseudoElement,
            getComputedTiming: () => ({ endTime }),
            getKeyframes: () => [{ [property]: "none" }],
          },
        })
      ),
    ];
  const animations = document.getAnimations;
  try {
    document.getAnimations = sliding();
    assert.equal(focusPlace(), first, "a slide under way didn't carry the user there");
    document.getAnimations = sliding({ endTime: Infinity });
    assert.equal(focusPlace(), null, "an endless animation kept focus the place");
    document.getAnimations = sliding({ property: "opacity" });
    assert.equal(focusPlace(), null, "a fade kept focus the place");
    document.getAnimations = sliding({ playState: "paused" });
    assert.equal(focusPlace(), null, "a slide held paused kept focus the place");
    document.getAnimations = sliding({ pseudoElement: "::before" });
    assert.equal(focusPlace(), null, "a pseudo-element's slide kept focus the place");
  } finally {
    document.getAnimations = animations;
  }

  // A stuck heading stays in front of the user, so a key pressed there acts there.
  scrollTo(1000);
  heading.focus();
  assert.equal(focusPlace(), heading);
  scrollTo(1300);
  assert.equal(
    focusPlace(),
    heading,
    "a stuck heading in view was not where the user is",
  );
  scroller.remove();
});

test("a wheel leaves the precise pointer position intact", () => {
  const movement = new Event("pointermove");
  Object.defineProperties(movement, {
    clientX: { value: 120.5 },
    clientY: { value: 240.25 },
  });
  document.dispatchEvent(movement);
  document.dispatchEvent(new Event("wheel"));
  assert.deepEqual(pointerAt(), { x: 120.5, y: 240.25 });
});

test("a mouse that leaves the window stands nowhere, and a lifted finger stays", () => {
  /** @param {string} type @param {object} fields */
  const send = (type, fields) => {
    const event = new Event(type);
    for (const [name, value] of Object.entries(fields))
      Object.defineProperty(event, name, { value });
    document.dispatchEvent(event);
  };
  send("pointermove", { clientX: 40, clientY: 50 });
  // Out to another element of the page: the mouse is still over it.
  send("pointerout", { pointerType: "mouse", relatedTarget: document.body });
  assert.deepEqual(pointerAt(), { x: 40, y: 50 });
  send("pointerout", { pointerType: "touch", relatedTarget: null });
  assert.deepEqual(pointerAt(), { x: 40, y: 50 });
  send("pointerout", { pointerType: "mouse", relatedTarget: null });
  assert.deepEqual(pointerAt(), { x: -1, y: -1 });
});

test("a hold pays for the growth above its node that anchoring left", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [above, read] = [item("a", 1000), item("b", 1150)];
  scroller.append(above, read);
  scrollTo(1100);
  const hold = holdPlace(read);
  // The edit grows the block above by 126px, and the browser's anchoring, holding that
  // block's top, paid for none of it.
  at.set(read, 1276);
  hold();
  assert.equal(scrolled(), 1226);
  assert.equal(read.getBoundingClientRect().top, 50);
  // Where anchoring already paid, the hold has nothing left to pay.
  const again = holdPlace(read);
  at.set(read, 1300);
  scrollTo(1250);
  again();
  assert.equal(scrolled(), 1250);
  scroller.remove();
});

test("a change that hides the held node puts its stand-in where it stood", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [gist, folded] = [item("gist", 1000), item("folded", 1100)];
  scroller.append(gist, folded);
  scrollTo(1080);
  const hold = holdPlace(folded, (node) => (node === folded ? gist : null));
  // The fold hides the block being read, and the gist it runs under stays put above.
  // happy-dom applies no user-agent sheet, so the block states what `[hidden]` computes.
  folded.hidden = true;
  folded.style.display = "none";
  hold();
  assert.equal(scrolled(), 980);
  assert.equal(gist.getBoundingClientRect().top, 20);
  // With no stand-in, a hidden or removed node holds nothing.
  at.set(gist, 1000);
  const lost = holdPlace(gist);
  gist.remove();
  scrollTo(900);
  lost();
  assert.equal(scrolled(), 900);
  scroller.remove();
});

// The pointer moved to rest over `node`, as the platform reports what lies under it.
/** @param {Element | null} node */
function restOn(node) {
  document.elementFromPoint = () => node;
  const movement = new Event("pointermove");
  Object.defineProperties(movement, { clientX: { value: 10 }, clientY: { value: 10 } });
  document.dispatchEvent(movement);
}

test("the keep puts back the first place the change moved", () => {
  const page = laidOut();
  const rail = laidOut();
  const read = page.item("read", 1150);
  const resting = rail.item("rail", 0);
  page.scroller.append(read);
  rail.scroller.append(resting);
  page.scrollTo(1100);
  read.tabIndex = 0;
  read.focus();
  // The pointer, moved last, rests on a rail of its own that the edit leaves still, so
  // the focused block it pushed down 126px is the place kept.
  restOn(resting);
  assert.equal(recentPlaceInput(), "pointer");
  const keep = holdUserPlace();
  page.at.set(read, 1276);
  keep();
  assert.equal(page.scrolled(), 1226);
  // With focus in a field that names no place, the row under the resting pointer is kept.
  const search = document.createElement("input");
  document.body.append(search);
  search.focus();
  read.setAttribute("role", "button");
  restOn(read);
  const row = holdUserPlace();
  page.at.set(read, 1400);
  row();
  assert.equal(page.scrolled(), 1350);
  [page.scroller, rail.scroller, search].forEach((node) => node.remove());
  restOn(null);
});

test("a place the change left still keeps its scroller", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [above, below] = [item("above", 1150), item("below", 1300)];
  scroller.append(above, below);
  scrollTo(1100);
  // Focus arrives last on the upper block, with the pointer resting on the lower one;
  // news joins between them, and anchoring holds the upper block.
  below.setAttribute("role", "button");
  restOn(below);
  above.tabIndex = 0;
  above.focus();
  assert.equal(recentPlaceInput(), "focus");
  const keep = holdUserPlace();
  at.set(below, 1426);
  keep();
  assert.equal(scrolled(), 1100, "the block under the pointer moved the focused one");
  scroller.remove();
  restOn(null);
});

test("the keep yields to a scroll or the user's own act, and typing leaves it kept", () => {
  /** @param {string} type @param {Element} at */
  const key = (type, at) => at.dispatchEvent(new Event(type, { bubbles: true }));
  for (const [act, typed, kept] of [
    [
      "a scroll under way",
      false,
      (_, /** @type {Element} */ box) => box.dispatchEvent(new Event("scroll")),
      1100,
    ],
    ["a press", false, (/** @type {Element} */ box) => key("pointerdown", box), 1100],
    [
      "a key at a control",
      false,
      (/** @type {Element} */ box) => key("keydown", box),
      1100,
    ],
    [
      "a key typed into the field",
      true,
      (/** @type {Element} */ box) => key("keydown", box),
      1226,
    ],
    [
      "words typed into the field",
      true,
      (/** @type {Element} */ box) => key("input", box),
      1226,
    ],
  ].map(([name, typed, since, kept]) => [{ name, since }, typed, kept])) {
    const { scroller, item, at, scrolled, scrollTo } = laidOut();
    const read = item("read", 1150);
    scroller.append(read);
    scrollTo(1100);
    if (typed) read.contentEditable = "true";
    else read.tabIndex = 0;
    read.focus();
    const keep = holdUserPlace();
    at.set(read, 1276);
    act.since(read, scroller);
    keep();
    assert.equal(scrolled(), kept, act.name);
    scroller.remove();
  }
});

test("the keep yields to a choice in a box scrolling its place, not in another", () => {
  for (const [where, kept] of [
    ["another box", 1226],
    ["its own box", 1100],
  ]) {
    const page = laidOut();
    const other = laidOut();
    const read = page.item("read", 1150);
    page.scroller.append(read);
    page.scrollTo(1100);
    read.tabIndex = 0;
    read.focus();
    const keep = holdUserPlace();
    page.at.set(read, 1276);
    startScroll(where === "its own box" ? page.scroller : other.scroller);
    keep();
    assert.equal(page.scrolled(), kept, where);
    [page.scroller, other.scroller].forEach((node) => node.remove());
  }
});

test("a field the user types in comes before a resting pointer, which names a control", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [control, field] = [item("control", 1120), item("field", 1150)];
  control.setAttribute("role", "button");
  field.contentEditable = "true";
  scroller.append(control, field);
  scrollTo(1100);
  field.focus();
  // The pointer, moved last, rests on a control the answer joining between them leaves
  // still; the field being typed in is still the place kept.
  restOn(control);
  assert.equal(recentPlaceInput(), "pointer");
  const typing = holdUserPlace();
  at.set(field, 1276);
  typing();
  assert.equal(scrolled(), 1226);
  // Resting on the page's background, a pointer names nothing, and focus on a control
  // that types nothing is kept.
  const background = item("background", 1200);
  scroller.append(background);
  field.contentEditable = "false";
  field.tabIndex = 0;
  field.focus();
  restOn(background);
  const pointed = holdUserPlace();
  at.set(field, 1400);
  pointed();
  assert.equal(scrolled(), 1350);
  scroller.remove();
  restOn(null);
});

test("a block folded until found holds its stand-in, though it keeps a box", () => {
  const { scroller, item, scrolled, scrollTo } = laidOut();
  const [gist, folded] = [item("gist", 1000), item("folded", 1100)];
  scroller.append(gist, folded);
  scrollTo(1080);
  const hold = holdPlace(folded, (node) => (node === folded ? gist : null));
  // `hidden="until-found"` keeps the block's box and hides its contents.
  folded.setAttribute("hidden", "until-found");
  folded.style.display = "block";
  assert.ok(folded.checkVisibility());
  hold();
  assert.equal(scrolled(), 980);
  scroller.remove();
});
