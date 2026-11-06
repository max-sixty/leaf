/* What a press at a point acts on (widget-elements.js, `pressedControl`), which the
 * page's click, the hand over a mark and the preview owner all ask: the element around
 * the point that takes the press as its own, or nothing where the press acts on the
 * page's words, at any point, marked words or not; and what else the user could aim at
 * there (`aimedAt`): that, or else an element that declares its own preview. */
import assert from "node:assert/strict";
import test from "node:test";
import { aimedAt, pressedControl } from "/runtime/widget-elements.js";
import { registry } from "/runtime/registry.js";
import playwright from "../../packages/playwright/registry.json" with { type: "json" };

/** @param {string} markup */
const page = (markup) => {
  const holder = document.createElement("div");
  holder.innerHTML = markup;
  document.body.append(holder);
  return holder;
};
/** The first text node under `selector` in `holder`. */
const wordsIn = (holder, selector) => holder.querySelector(selector).firstChild;

test("a control and an editing region take a press; prose, a plain box and a card that only previews don't", () => {
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
    for (const [words, owner] of [
      ["#in-link", "#link"],
      ["#titled", "#titled"],
      ["#in-editor", "#editor"],
    ]) {
      assert.equal(pressedControl(wordsIn(holder, words)), holder.querySelector(owner));
      assert.equal(aimedAt(wordsIn(holder, words)), holder.querySelector(owner));
    }
    // A card that says what it holds takes no press, but the user can aim at it.
    assert.equal(pressedControl(wordsIn(holder, "#in-card")), null);
    assert.equal(aimedAt(wordsIn(holder, "#in-card")), card);
    for (const words of ["#in-box", "#prose"]) {
      assert.equal(pressedControl(wordsIn(holder, words)), null);
      assert.equal(aimedAt(wordsIn(holder, words)), null);
    }
  } finally {
    holder.remove();
  }
});

test("a widget takes a press on the parts its entry declares, in the state it names", () => {
  Object.assign(registry, {
    "lf-pressed": { "x-content": "markup", "x-upgrade": true, "x-press": true },
    "lf-parted": {
      "x-content": "markup",
      "x-upgrade": true,
      "x-press": { region: ".part", when: { live: [true] } },
    },
    "lf-unpressed": { "x-content": "markup", "x-upgrade": true },
  });
  const holder = page(
    '<p><lf-pressed id="pressed"><span id="in-pressed">phrase</span>' +
      '<span id="said" data-lf-said="tip">its explanation</span>' +
      '<button id="inner">More</button></lf-pressed></p>' +
      '<lf-parted id="parted" live><span class="part" id="part">a part</span>' +
      '<span id="outside">words between</span></lf-parted>' +
      '<lf-unpressed id="unpressed"><span id="in-unpressed">words</span></lf-unpressed>',
  );
  try {
    const pressed = holder.querySelector("#pressed");
    assert.equal(pressedControl(wordsIn(holder, "#in-pressed")), pressed);
    // What it says isn't its own, and a control inside keeps its press.
    assert.equal(pressedControl(wordsIn(holder, "#said")), null);
    assert.equal(
      pressedControl(wordsIn(holder, "#inner")),
      holder.querySelector("#inner"),
    );
    const parted = holder.querySelector("#parted");
    assert.equal(
      pressedControl(wordsIn(holder, "#part")),
      holder.querySelector("#part"),
    );
    assert.equal(pressedControl(wordsIn(holder, "#outside")), null);
    parted.removeAttribute("live");
    assert.equal(pressedControl(wordsIn(holder, "#part")), null);
    assert.equal(pressedControl(wordsIn(holder, "#in-unpressed")), null);
  } finally {
    holder.remove();
    delete registry["lf-pressed"];
    delete registry["lf-parted"];
    delete registry["lf-unpressed"];
  }
});

test("the trace takes a press on its image tools, whose click it inspects", () => {
  Object.assign(registry, { "lf-trace": playwright["lf-trace"] });
  const holder = page(
    '<lf-trace id="trace"><div class="lf-trace-image-tools">' +
      '<span class="lf-trace-tools-status" id="status">x</span>' +
      '<button id="tool">Tool</button></div></lf-trace>',
  );
  try {
    const tools = holder.querySelector(".lf-trace-image-tools");
    assert.equal(pressedControl(wordsIn(holder, "#status")), tools);
    assert.equal(
      pressedControl(wordsIn(holder, "#tool")),
      holder.querySelector("#tool"),
    );
  } finally {
    holder.remove();
    delete registry["lf-trace"];
  }
});
