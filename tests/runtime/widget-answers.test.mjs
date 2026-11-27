/* What a widget works out of its state for the page to keep (`facts`), and what one
   that asks says of its question (`awaits`): the default rule over the user's acts in
   force (`holdsState`), lf-options' own `static answered`, and the facts the runtime
   reads for a gesture (`widgetFacts`). A word on a question counts only what the
   user's gestures hold, never a value the markup holds, so the browser and the server
   read one word. */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { adoptRegistry } from "/runtime/state/registry.js";
import { stageAuthoredStates } from "/runtime/records/projection/authored.js";
import { stageWidgetDescriptors } from "/runtime/records/widget-descriptors.js";
import { holdsState } from "/runtime/state/projection/model.js";
import { applicationState, readApplication } from "/runtime/state/semantic-state.js";
import { widgetFacts } from "/runtime/host/widget-state.js";

const packaged = JSON.parse(
  readFileSync(
    new URL("../../packages/default/registry.json", import.meta.url),
    "utf8",
  ),
);
// Composition writes each verb's default `unit` (`complete_declarations`).
for (const tag of ["lf-options", "lf-draft"])
  for (const spec of Object.values(packaged[tag].verbs)) spec.unit ??= "widget";
// Two plain widgets that ask, one whose class works out its own word and a count
// beside it and one that leaves its word to the default rule, and one that declares no
// facts. Plain elements need no mounted application, so the runtime's reading of each
// can be asked here.
const asking = {
  attributes: {
    properties: { pick: { type: "string" }, ready: { type: "boolean" } },
    required: ["id"],
  },
  content: "markup",
  verbs: { pick: { unit: "widget", record: { kind: "value", attr: "pick" } } },
  awaits: { value: "pick" },
  facts: { answered: { type: "boolean" } },
};
const { awaits: _awaits, facts: _facts, ...quiet } = asking;
adoptRegistry({
  $layer: { generation: "widget-answers" },
  "lf-options": packaged["lf-options"],
  "lf-option": packaged["lf-option"],
  "lf-draft": packaged["lf-draft"],
  "lf-test-says": {
    ...asking,
    facts: { ...asking.facts, count: { type: "integer" } },
  },
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
    /** @param {unknown} _state @param {Element} element */
    static count(_state, element) {
      return Number(element.getAttribute("count") ?? 0);
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

const pick = (/** @type {string[]} */ value) => ({
  action: "choose",
  value,
  detail: { value },
});
// The Done of a checklist pressed on `options`, with `picked` among them.
const done = (/** @type {string[]} */ options, /** @type {string[]} */ picked) => ({
  action: "answer",
  value: "answer",
  detail: { options, picked },
});
/** A checklist of `options`, as its authored markup stands, out of the document. */
function checklist(/** @type {string[]} */ options) {
  const template = document.createElement("template");
  template.innerHTML = `<lf-options id="several" multiple>${options
    .map((id) => `<lf-option id="${id}">${id}</lf-option>`)
    .join("")}</lf-options>`;
  return /** @type {Element} */ (template.content.firstElementChild);
}

test("a pick the user made answers a single choice, and only Done a multiple one", () => {
  const one = document.createElement("lf-options");
  const several = checklist(["c", "d"]);
  assert.equal(answered({ choose: pick(["a"]) }, one), true);
  // A pick the user emptied answers nothing.
  assert.equal(answered({ choose: pick([]) }, one), false);
  assert.equal(answered({ choose: pick(["c", "d"]) }, several), false);
  assert.equal(
    answered({ choose: pick(["c"]), answer: done(["c", "d"], ["c"]) }, several),
    true,
  );
  assert.equal(
    answered({ choose: pick([]), answer: done(["c", "d"], []) }, several),
    true,
  );
});

test("Done answers the set it was pressed on, and a version that changes the set asks again", () => {
  const pressed = done(["c", "d"], ["c"]);
  const state = { choose: pick(["c"]), answer: pressed };
  assert.equal(answered(state, checklist(["c", "d"])), true);
  // A step the version adds is one Done never covered: the question asks again, and
  // the step the user picked stays picked.
  assert.equal(answered(state, checklist(["c", "d", "e"])), false);
  assert.equal(state.choose.value.join(), "c");
  // A version that restates the picked step takes the pick back, which Done no longer
  // stands on, and so does a pick the user changes after it; picking it again answers.
  assert.equal(answered({ ...state, choose: pick([]) }, checklist(["c", "d"])), false);
  assert.equal(
    answered({ ...state, choose: pick(["c", "d"]) }, checklist(["c", "d"])),
    false,
  );
  // A step the version removes changes nothing Done answered.
  assert.equal(answered(state, checklist(["c"])), true);
});

test("an option whose add the user undid answers as gone while it is still drawn", () => {
  // Done covers c and d with c picked; the user added x, then undid its pick and its
  // add. The gesture's facts are worked out before the group redraws, so x is still
  // drawn, and Done still stands on the set the group shows.
  const group = checklist(["c", "d"]);
  const drawn = document.createElement("lf-option");
  drawn.id = "x";
  drawn.toggleAttribute("data-lf-added", true);
  group.append(drawn);
  const state = { choose: pick(["c"]), answer: done(["c", "d"], ["c"]) };
  assert.equal(answered(state, group), true);
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

test("the runtime asks a widget for each fact it declares, and one that declares none for none", () => {
  try {
    capturePage(
      '<lf-test-says id="says" pick="x" count="2"></lf-test-says>' +
        '<lf-test-says id="ready" ready></lf-test-says>' +
        '<lf-test-plain id="plain" pick="x"></lf-test-plain>' +
        '<lf-test-quiet id="quiet" pick="x"></lf-test-quiet>',
    );
    // A class that works its facts out has each read, its word whatever the default
    // rule would say.
    assert.deepEqual(widgetFacts("says", null), { answered: false, count: 2 });
    assert.deepEqual(widgetFacts("ready", null), { answered: true, count: 0 });
    // The default rule speaks for a class that says nothing of its question, and the
    // markup's value counts for nothing.
    assert.deepEqual(widgetFacts("plain", null), { answered: false });
    // A widget that declares no facts says none; one named by its tag where no
    // descriptor is captured still says.
    assert.equal(widgetFacts("quiet", null), undefined);
    assert.equal(widgetFacts("missing", null), undefined);
    assert.deepEqual(widgetFacts("missing", "lf-test-plain"), { answered: false });
  } finally {
    document.body.replaceChildren();
  }
});

test("a fact that throws is the widget's failure, and leaves its question open", () => {
  const Says =
    /** @type {CustomElementConstructor & {answered: Function, count: Function}} */ (
      customElements.get("lf-test-says")
    );
  const own = Says.answered;
  const counted = Says.count;
  /** @type {unknown[]} */
  const failures = [];
  const heard = (/** @type {Event} */ event) =>
    failures.push(/** @type {ErrorEvent} */ (event).error);
  try {
    capturePage('<lf-test-says id="says" ready></lf-test-says>');
    Says.answered = () => {
      throw new Error("no word");
    };
    Says.count = () => {
      throw new Error("no count");
    };
    document.addEventListener("error", heard);
    window.addEventListener("error", heard);
    // The class would say `ready` answers it; failing, it says nothing, and the
    // gesture says its question is open, so it stays on On Me. The count it can't
    // work out goes unsaid.
    assert.deepEqual(widgetFacts("says", null), { answered: false });
    assert.ok(failures.some((failure) => /no word/.test(String(failure))));
    assert.ok(failures.some((failure) => /no count/.test(String(failure))));
  } finally {
    Says.answered = own;
    Says.count = counted;
    document.removeEventListener("error", heard);
    window.removeEventListener("error", heard);
    document.body.replaceChildren();
  }
});
