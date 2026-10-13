/* Which command a letter reaches while the Go-to sequence is armed (go-to-sequence.js,
   dispatched through dispatch.js). Every letter of the hint alphabet is the sequence's
   while it stands, so a letter no hint names now, such as one a scene refresh retired,
   is reported as a miss and never falls through to the page command it names when the
   sequence is not armed. The hint session's own handling of the letter is
   hint-session.test.mjs's. */

import assert from "node:assert/strict";
import test from "node:test";

import { createGoToSequence } from "/runtime/keyboard/go-to-sequence.js";
import { dispatchKey } from "/runtime/keyboard/dispatch.js";
import {
  pageCommand,
  registerCoveringAuxiliarySurface,
} from "/runtime/keyboard/register.js";
import { liveEl } from "/runtime/notifications.js";
import { applicationState } from "/runtime/semantic-state.js";

applicationState.setPhase("ready");
registerCoveringAuxiliarySurface(() => null);

// A page command on a letter of the hint alphabet, as `e` opens reactions on a page.
const reacted = [];
pageCommand({
  id: "reaction.open",
  keys: ["e"],
  touch: false,
  title: "react",
  description: "React to what you stand on",
  run: () => reacted.push("e"),
});

const goTo = createGoToSequence({
  panelIsOpen: () => false,
  elements: {
    banner: document.createElement("header"),
    toggleBtn: document.createElement("button"),
  },
  hintChrome: { barriers: () => [], lineBox: () => null, viewportTop: () => 0 },
  directDestinations: () => [],
  scrollToElement: () => {},
  leavesOffered: () => false,
  glideTo: () => {},
  placeThreadEdge: () => {},
  seenScroller: () => document.scrollingElement,
  stopGlide: () => {},
  coveringAuxiliarySurface: () => null,
});

const press = (key) =>
  dispatchKey(new window.KeyboardEvent("keydown", { key, cancelable: true }), {});

test("unarmed, the letter is the page command's", () => {
  assert.equal(goTo.goToSequenceActive(), false);
  assert.equal(press("e"), true);
  assert.deepEqual(reacted, ["e"]);
  reacted.length = 0;
});

test("armed, a letter no hint names is reported as a miss, and the sequence stands", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  assert.equal(press("g"), true);
  assert.equal(goTo.goToSequenceActive(), true);
  t.after(() => goTo.setGoToSequence(false));

  assert.equal(press("e"), true);
  t.mock.timers.tick(30);
  assert.equal(liveEl.textContent, "No hint e. The current hints are unchanged.");
  assert.deepEqual(reacted, []);
  assert.equal(goTo.goToSequenceActive(), true);
});
