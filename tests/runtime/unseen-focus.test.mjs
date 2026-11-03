/* A key acts at the focused control only while the user sees it; focus scrolled out of
   sight leaves them on the page, apart from typing and Escape (dispatch.js, `stack`). */
import assert from "node:assert/strict";
import test from "node:test";
import { dispatchKey } from "../../browser/runtime/keyboard/dispatch.js";
import { keys } from "../../browser/runtime/keyboard/scopes.js";
import { inView } from "./dom.mjs";

/** @param {string} key */
const press = (key) =>
  dispatchKey(
    new window.KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
  );
// A scroll that settles, as the browser reports one.
const scrolled = () => {
  document.dispatchEvent(new window.Event("scroll"));
  document.dispatchEvent(new window.Event("scrollend"));
};
/** @param {Element} element */
const scrolledAway = (element) => {
  element.getBoundingClientRect = () => new DOMRect(0, innerHeight + 500, 100, 20);
  scrolled();
};

test("a key acts at a focused control only while the user sees it", () => {
  const widget = document.createElement("section");
  widget.tabIndex = 0;
  const field = document.createElement("input");
  widget.append(field);
  document.body.append(widget);
  /** @type {string[]} */
  const runs = [];
  keys(widget, "A widget", [
    { id: "probe.choose", keys: ["2"], title: "choose", run: () => runs.push("2") },
    {
      id: "probe.close",
      keys: ["Escape"],
      title: "close",
      run: () => runs.push("Esc"),
    },
  ]);
  keys(field, "A field", [
    { id: "probe.send", keys: ["Enter"], title: "send", run: () => runs.push("send") },
  ]);
  try {
    widget.focus();
    scrolledAway(widget);
    assert.equal(press("2"), false, "a choice reached a widget the user can't see");
    // Escape still takes its step, so letting go lands where the user is reading.
    assert.equal(press("Escape"), true);
    inView(widget);
    scrolled();
    assert.equal(press("2"), true);
    // A field keeps its keys out of sight, since typing brings its box back.
    field.focus();
    scrolledAway(field);
    assert.equal(press("Enter"), true);
    assert.deepEqual(runs, ["Esc", "2", "send"]);
  } finally {
    widget.remove();
  }
});
