/* This module owns how a binding is drawn: the steps a row's sequence or label breaks
 * into, which leading steps match presses the active interaction has accepted, and the
 * immutable key-sequence reading every keyboard surface renders through one Lit template. */
import { html, nothing, repeat } from "/runtime/framework.js";

import { bindings, spell, word } from "./bindings.js";

// A sequence row may name several presses, while an ordinary row still carries one compact
// label. Keep that distinction structured until the DOM is built: spaces in a label are
// words inside one step, never guessed back into a sequence. Each step holds the keys
// that take it, several where a row's bindings are alternatives, as `z` and `⌘z` both
// undo a stroke; its text joins them as `labelOf` does (bindings.js).
const rowKeySteps = (row, route = null) => {
  if (route) return [[spell(route.binding)]];
  const steps = word(row.sequenceSteps);
  if (steps) return steps.map((step) => [step]);
  const label = word(row.label);
  if (label !== undefined && label !== null) return label ? [[label]] : [];
  const keys = bindings(row).map(spell);
  return keys.length ? [keys] : [];
};

export const completeRowKeySteps = (row, route = null) => {
  const steps = route ? null : word(row.completeSequenceSteps);
  return steps ? steps.map((step) => [step]) : rowKeySteps(row, route);
};

export const stepText = (keys) => keys.join(" / ");

export const completeRowSteps = (row, route = null) =>
  completeRowKeySteps(row, route).map(stepText);

export const neutralStates = (steps) => steps.map(() => "neutral");

// A pressed face means this exact step was accepted on the way to this route. Counting
// accepted presses paints an unrelated continuation when routes branch: after `g n`, a
// static `g Tab` route has one matching step, not two. Stop at the first divergence because
// a sequence is ordered; a later coincidental letter is not part of the route taken.
export const progressStates = (steps, pressed) => {
  let matching = true;
  return steps.map((step, i) => {
    matching = matching && pressed[i] === step;
    return matching ? "pressed" : "neutral";
  });
};

export function keySequenceModel(
  steps,
  states = neutralStates(steps),
  spokenSteps = steps,
  keySteps = steps.map((text) => [text]),
) {
  if (
    !steps.length ||
    states.length !== steps.length ||
    spokenSteps.length !== steps.length ||
    keySteps.length !== steps.length
  )
    throw new Error(
      "leaf: a key sequence needs one state, spoken label and set of keys per step",
    );
  const reading = steps.map((text, index) => {
    const state = states[index];
    const spoken = spokenSteps[index];
    const keys = Object.freeze([...keySteps[index]]);
    return Object.freeze({ text, keys, spoken, state });
  });
  return Object.freeze({
    label: reading.map(({ spoken }) => spoken.replaceAll(" / ", " or ")).join(" then "),
    steps: Object.freeze(reading),
  });
}

export function keySequenceTemplate(model, { id = null, label = false } = {}) {
  return html`<span
    id=${id ?? nothing}
    class=${`lf-binding-sequence${label ? " lf-key-label" : ""}`}
    role="group"
    aria-label=${model.label}
    >${repeat(
      model.steps,
      (_step, index) => index,
      (step) =>
        step.keys.map(
          (key, index) =>
            html`<kbd
              class="lf-key-badge"
              data-lf-sequence-step-state=${step.state}
              ?data-lf-key-or=${index > 0}
              aria-hidden="true"
              >${key}</kbd
            >`,
        ),
    )}</span
  >`;
}
