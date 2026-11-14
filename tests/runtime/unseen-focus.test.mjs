/* A key pressed at a control the user has scrolled out of sight lets go of it first and
   acts from the page; typing and Escape keep the control (keyboard/controller.js). */
import assert from "node:assert/strict";
import test from "node:test";
import { mountKeyboard } from "../../browser/runtime/keyboard/controller.js";
import { keys } from "../../browser/runtime/keyboard/scopes.js";
import { focused } from "../../browser/runtime/focus.js";

mountKeyboard({
  goToSequenceActive: () => false,
  setGoToSequence: () => {},
  reactArmed: () => false,
  setReact: () => {},
});
// Whether the key's default survived, as `dispatchEvent` reports it.
/** @param {Element} target @param {string} key */
const press = (target, key) =>
  target.dispatchEvent(
    new window.KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
  );
/** @param {Element} element @param {number} top */
const standAt = (element, top) => {
  element.getBoundingClientRect = () => new DOMRect(0, top, 100, 20);
};
const away = innerHeight + 500;

test("a key at a control the user scrolled away from lets go of it first", () => {
  const widget = document.createElement("section");
  widget.tabIndex = 0;
  const radio = Object.assign(document.createElement("input"), { type: "radio" });
  const field = document.createElement("input");
  document.body.append(widget, radio, field);
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
  keys(document.body, "The page", [
    { id: "probe.page", keys: ["Enter"], title: "page", run: () => runs.push("page") },
  ]);
  // What a widget's own listener on its control, and a page's on the document, hear.
  /** @type {string[]} */
  const heard = [];
  widget.addEventListener("keydown", (ev) => heard.push(`widget ${ev.key}`));
  /** @param {KeyboardEvent} ev */
  const pageHears = (ev) => heard.push(`page ${ev.key}`);
  document.addEventListener("keydown", pageHears);
  try {
    widget.focus();
    standAt(widget, 0);
    press(widget, "2");
    assert.equal(focused(), widget);
    standAt(widget, away);
    // Escape takes its own step at the control.
    press(widget, "Escape");
    assert.equal(focused(), widget);
    press(widget, "2");
    assert.notEqual(focused(), widget, "a key acted at a control out of sight");
    // The key that lets go reaches no listener past the document's capture, and Leaf's
    // own command for a key that is not a character still runs.
    widget.focus();
    press(widget, "Enter");
    assert.deepEqual(heard, ["widget Escape", "page Escape"]);
    // Back in view, the control is no longer where the user is.
    standAt(widget, 0);
    press(document.body, "2");
    // Focused there again, the same key reaches the widget's listener and the page's
    // before Leaf's command.
    widget.focus();
    press(widget, "Enter");
    assert.deepEqual(heard.slice(-2), ["widget Enter", "page Enter"]);
    // The browser moves a radio's choice at the control the key was aimed at, wherever
    // focus has gone, so the let-go withholds it.
    radio.focus();
    standAt(radio, away);
    assert.equal(press(radio, "ArrowDown"), false, "an unseen radio took its arrow");
    assert.notEqual(focused(), radio);
    // A field keeps its keys out of sight, since typing brings its box back.
    field.focus();
    standAt(field, away);
    press(field, "Enter");
    assert.equal(focused(), field);
    assert.deepEqual(runs, ["2", "Esc", "page", "page", "send"]);
  } finally {
    document.removeEventListener("keydown", pageHears);
    widget.remove();
    radio.remove();
    field.remove();
  }
});
