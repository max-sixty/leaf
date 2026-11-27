/* What a widget that asks says of its question (`awaits`): the default rule over the
   user's acts in force (`holdsState`), lf-options' own `static answered`, and the word
   the runtime reads for a gesture (`widgetAnswered`). Each counts only what the user's
   gestures hold, never a value the markup holds, so the browser and the server read
   one word. */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { adoptRegistry } from "/runtime/state/registry.js";
import { stageAuthoredStates } from "/runtime/records/projection/authored.js";
import { stageWidgetDescriptors } from "/runtime/records/widget-descriptors.js";
import { holdsState } from "/runtime/state/projection/model.js";
import { applicationState, readApplication } from "/runtime/state/semantic-state.js";
import { widgetAnswered } from "/runtime/host/widget-state.js";

const packaged = JSON.parse(
  readFileSync(
    new URL("../../packages/default/registry.json", import.meta.url),
    "utf8",
  ),
);
// Composition writes each verb's default `unit` (`complete_declarations`).
for (const tag of ["lf-options", "lf-draft"])
  for (const spec of Object.values(packaged[tag].verbs)) spec.unit ??= "widget";
// Two plain widgets that ask, one whose class says its own word and one that leaves it
// to the default rule, and one that asks nothing. Plain elements need no mounted
// application, so the runtime's reading of each can be asked here.
const asking = {
  attributes: {
    properties: { pick: { type: "string" }, ready: { type: "boolean" } },
    required: ["id"],
  },
  content: "markup",
  verbs: { pick: { unit: "widget", record: { kind: "value", attr: "pick" } } },
  awaits: { value: "pick" },
};
const { awaits: _awaits, ...quiet } = asking;
adoptRegistry({
  $layer: { generation: "widget-answers" },
  "lf-options": packaged["lf-options"],
  "lf-option": packaged["lf-option"],
  "lf-draft": packaged["lf-draft"],
  "lf-test-says": asking,
  "lf-test-plain": asking,
  "lf-test-quiet": quiet,
});
customElements.define(
  "lf-test-says",
  class extends HTMLElement {
    /** @param {unknown} _state @param {Element} element */
    static answered(_state, element) {
      return element.hasAttribute("ready");
    }
  },
);
await import("../../packages/default/widgets/lf-options.js");
const { answered } = /** @type {CustomElementConstructor & {answered: Function}} */ (
  customElements.get("lf-options")
);

const MARKUP =
  '<lf-options id="one"><lf-option id="a" selected>A</lf-option>' +
  '<lf-option id="b">B</lf-option></lf-options>' +
  '<lf-options id="several" multiple><lf-option id="c" selected>C</lf-option>' +
  '<lf-option id="d">D</lf-option></lf-options>' +
  '<lf-draft id="note" required><pre>Dear team,</pre></lf-draft>';

/** The page's markup, captured as Leaf captures it before upgrade, out of the
 * document so no group upgrades. */
function captured() {
  const template = document.createElement("template");
  template.innerHTML = `<main>${MARKUP}</main>`;
  const main = /** @type {Element} */ (template.content.firstElementChild);
  return { main, states: stageAuthoredStates(main) };
}

test("a pick only the markup holds answers nothing, by either rule", () => {
  try {
    const { main, states } = captured();
    const one = /** @type {NonNullable<ReturnType<typeof states.get>>} */ (
      states.get("one")
    );
    const several = /** @type {NonNullable<ReturnType<typeof states.get>>} */ (
      states.get("several")
    );
    const note = /** @type {NonNullable<ReturnType<typeof states.get>>} */ (
      states.get("note")
    );
    // The authored capture holds the markup's picks and words, as no action does.
    assert.deepEqual(one.state.choose, {
      action: null,
      value: ["a"],
      detail: { value: ["a"] },
    });
    const at = (/** @type {string} */ id) =>
      /** @type {Element} */ (main.querySelector(`#${id}`));
    assert.equal(answered(one.state, at("one")), false);
    assert.equal(answered(several.state, at("several")), false);
    assert.equal(holdsState(one, "choose"), false);
    assert.equal(holdsState(note, "edit"), false);
  } finally {
    document.body.replaceChildren();
  }
});

test("a pick the user made answers a single choice, and only Done a multiple one", () => {
  const pick = (/** @type {string[]} */ value) => ({
    action: "choose",
    value,
    detail: { value },
  });
  const done = { action: "answer", value: "answer", detail: {} };
  const one = document.createElement("lf-options");
  const several = document.createElement("lf-options");
  several.setAttribute("multiple", "");
  assert.equal(answered({ choose: pick(["a"]) }, one), true);
  // A pick the user emptied answers nothing.
  assert.equal(answered({ choose: pick([]) }, one), false);
  assert.equal(answered({ choose: pick(["c", "d"]) }, several), false);
  assert.equal(answered({ choose: pick(["c"]), answer: done }, several), true);
  assert.equal(answered({ choose: pick([]), answer: done }, several), true);
});

test("the default rule reads the user's acts in force at the verb the widget awaits", () => {
  const specs = new Map([
    ["edit", { unit: "widget", record: { kind: "body" } }],
    ["choose", { unit: "widget" }],
    ["move", { unit: "card", record: { kind: "position" } }],
  ]);
  const widget = (/** @type {Record<string, unknown>} */ state) =>
    /** @type {Parameters<typeof holdsState>[0]} */ ({ state, specs });
  const edited = (/** @type {string} */ value) => ({
    edit: { action: "edit", value, detail: { value } },
  });
  assert.equal(holdsState(widget(edited("Green room.")), "edit"), true);
  assert.equal(holdsState(widget(edited("")), "edit"), false);
  assert.equal(
    holdsState(
      widget({ choose: { action: "choose", value: "choose", detail: {} } }),
      "choose",
    ),
    true,
  );
  assert.equal(
    holdsState(widget({ choose: { action: null, value: null, detail: {} } }), "choose"),
    false,
  );
  const moved = { value: {}, ranks: {}, units: { "card-a": { action: "move" } } };
  assert.equal(holdsState(widget({ move: moved }), "move"), true);
  assert.equal(holdsState(widget({ move: { ...moved, units: {} } }), "move"), false);
  assert.equal(holdsState(widget({}), "edit"), false);
});

/** Capture `markup` in the page, as Leaf does before upgrade. */
function capturePage(/** @type {string} */ markup) {
  document.body.innerHTML = markup;
  const { descriptors } = stageWidgetDescriptors(document.body);
  applicationState.identify(1);
  applicationState.captureDocument({
    ...readApplication().document,
    authored: stageAuthoredStates(document.body),
    descriptors,
  });
}

test("the runtime asks a widget that asks for its word, and one that asks nothing for none", () => {
  try {
    capturePage(
      '<lf-test-says id="says" pick="x"></lf-test-says>' +
        '<lf-test-says id="ready" ready></lf-test-says>' +
        '<lf-test-plain id="plain" pick="x"></lf-test-plain>' +
        '<lf-test-quiet id="quiet" pick="x"></lf-test-quiet>',
    );
    // A class that says has its word read, whatever the default rule would say.
    assert.equal(widgetAnswered("says", null), false);
    assert.equal(widgetAnswered("ready", null), true);
    // The default rule speaks for a class that says nothing, and the markup's value
    // counts for nothing.
    assert.equal(widgetAnswered("plain", null), false);
    // A widget that asks nothing says nothing; one named by its tag where no
    // descriptor is captured still says.
    assert.equal(widgetAnswered("quiet", null), undefined);
    assert.equal(widgetAnswered("missing", null), undefined);
    assert.equal(widgetAnswered("missing", "lf-test-plain"), false);
  } finally {
    document.body.replaceChildren();
  }
});

test("an answered that throws is the widget's failure, and leaves its question open", () => {
  const Says = /** @type {CustomElementConstructor & {answered: Function}} */ (
    customElements.get("lf-test-says")
  );
  const own = Says.answered;
  /** @type {unknown[]} */
  const failures = [];
  const heard = (/** @type {Event} */ event) =>
    failures.push(/** @type {ErrorEvent} */ (event).error);
  try {
    capturePage('<lf-test-says id="says" ready></lf-test-says>');
    Says.answered = () => {
      throw new Error("no word");
    };
    document.addEventListener("error", heard);
    window.addEventListener("error", heard);
    // The class would say `ready` answers it; failing, it says nothing, and the
    // gesture says its question is open, so it stays on On Me.
    assert.equal(widgetAnswered("says", null), false);
    assert.equal(failures.length >= 1, true);
    assert.match(String(failures[0]), /no word/);
  } finally {
    Says.answered = own;
    document.removeEventListener("error", heard);
    window.removeEventListener("error", heard);
    document.body.replaceChildren();
  }
});
