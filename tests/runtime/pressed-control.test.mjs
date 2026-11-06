/* What a press at a point acts on (control-selectors.js, `pressedControl`), which the
 * page's click, the hand over a mark and the preview owner all ask: the element around
 * the point that takes the press as its own, or nothing where the press acts on the
 * page's words, at any point, marked words or not. */
import assert from "node:assert/strict";
import test from "node:test";
import { pressedControl } from "/runtime/control-selectors.js";

/** @param {string} markup */
const page = (markup) => {
  const holder = document.createElement("div");
  holder.innerHTML = markup;
  document.body.append(holder);
  return holder;
};
/** The first text node under `selector` in `holder`. */
const wordsIn = (holder, selector) => holder.querySelector(selector).firstChild;

test("a control, an editing region and a previewing card take a press; prose and a plain box don't", () => {
  const holder = page(
    '<a id="link" href="#x"><span id="in-link">link words</span></a>' +
      '<button id="titled" title="Inspect">button words</button>' +
      '<div id="editor" contenteditable><p id="in-editor">edited words</p></div>' +
      '<div id="card" tabindex="0"><p id="in-card">words around a chart</p><svg></svg></div>' +
      '<div id="box" tabindex="0"><p id="in-box">scrolling words</p></div>' +
      '<p id="prose">plain words</p>',
  );
  const card = holder.querySelector("#card");
  Reflect.set(card, "lfPreview", () => ({ name: "The card" }));
  try {
    assert.equal(
      pressedControl(wordsIn(holder, "#in-link")),
      holder.querySelector("#link"),
    );
    assert.equal(
      pressedControl(wordsIn(holder, "#titled")),
      holder.querySelector("#titled"),
    );
    assert.equal(
      pressedControl(wordsIn(holder, "#in-editor")),
      holder.querySelector("#editor"),
    );
    assert.equal(pressedControl(wordsIn(holder, "#in-card")), card);
    assert.equal(pressedControl(wordsIn(holder, "#in-box")), null);
    assert.equal(pressedControl(wordsIn(holder, "#prose")), null);
    // A previewing card inside a plain box is still the card's.
    holder.querySelector("#box").append(card);
    assert.equal(pressedControl(wordsIn(holder, "#in-card")), card);
  } finally {
    holder.remove();
  }
});
