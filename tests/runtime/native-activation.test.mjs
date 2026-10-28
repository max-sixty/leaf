/* A link or button keeps its own Enter and Space from a container scope around it. */
import assert from "node:assert/strict";
import test from "node:test";
// Importing the page's own parts declares "On a link".
import "../../browser/runtime/keyboard/page.js";
import { dispatchKey } from "../../browser/runtime/keyboard/dispatch.js";
import { keys, reflectFirstScopes } from "../../browser/runtime/keyboard/scopes.js";

// One press from wherever focus stands: whether Leaf answered it, and whether the
// browser's own default survives.
function press(key) {
  const event = new window.KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
  });
  const handled = dispatchKey(event);
  return { handled, prevented: event.defaultPrevented };
}

test("Enter and Space on a link or button inside a container stay native", () => {
  const container = document.createElement("section");
  container.tabIndex = 0;
  const link = document.createElement("a");
  link.href = "#elsewhere";
  link.textContent = "elsewhere";
  const button = document.createElement("button");
  button.textContent = "Press";
  const disclosure = document.createElement("button");
  disclosure.setAttribute("aria-expanded", "false");
  disclosure.textContent = "More";
  let toggled = 0;
  disclosure.addEventListener("click", () => toggled++);
  container.append(link, button, disclosure);
  document.body.append(container);
  let acted = 0;
  keys(container, "In a container", [
    { id: "container.act", keys: ["Enter", " "], title: "act", run: () => acted++ },
  ]);
  try {
    // The container answers its own presses.
    container.focus();
    const own = { handled: true, prevented: true };
    assert.deepEqual(press("Enter"), own);
    assert.deepEqual(press(" "), own);
    assert.equal(acted, 2);

    // Enter follows a link, and the bar names that; Space is no link's press.
    link.focus();
    assert.deepEqual(press("Enter"), {
      handled: false,
      prevented: false,
    });
    assert.deepEqual(press(" "), own);
    assert.equal(acted, 3);

    // Both press a button, and the bar promises nothing the button won't do.
    button.focus();
    const native = { handled: false, prevented: false };
    assert.deepEqual(press("Enter"), native);
    assert.deepEqual(press(" "), native);
    assert.equal(acted, 3);

    // A disclosure's own scope speaks for the button: it keeps the press and its name.
    disclosure.focus();
    const toggle = { handled: true, prevented: true };
    assert.deepEqual(press("Enter"), toggle);
    assert.deepEqual(press(" "), toggle);
    assert.equal(toggled, 2);
    assert.equal(acted, 3);
  } finally {
    container.remove();
  }
});

test("a context alias on a button yields its Enter and Space, as dispatch and aria agree", () => {
  const button = document.createElement("button");
  button.textContent = "Act";
  document.body.append(button);
  let acted = 0;
  keys(button, "On a button", [
    {
      id: "button.act",
      keys: ["y"],
      contextKeys: ["Enter", " "],
      title: "act",
      run: () => acted++,
    },
  ]);
  try {
    reflectFirstScopes();
    button.focus();
    const native = { handled: false, prevented: false };
    assert.deepEqual(press("Enter"), native);
    assert.deepEqual(press(" "), native);
    assert.equal(acted, 0);
    assert.equal(button.getAttribute("aria-keyshortcuts"), "y");
  } finally {
    button.remove();
  }
});
