/* This module owns how a binding is drawn: the steps a row's sequence or label breaks
 * into, which leading steps match presses the active interaction has accepted, and the
 * immutable key-sequence reading every keyboard surface renders through one Lit template. */
import { html, nothing, repeat } from "../../vendor/browser-runtime.js";

import { labelOf, spell, word } from "./bindings.js";

const STATES = new Set(["neutral", "pressed"]);

// A sequence row may name several presses, while an ordinary row still carries one compact
// label. Keep that distinction structured until the DOM is built: spaces in a label are
// words inside one step, never guessed back into a sequence.
export const rowSteps = (row, route = null) => {
  if (route) return [spell(route.binding)];
  return word(row.sequenceSteps) ?? [labelOf(row)];
};

export const completeRowSteps = (row, route = null) => {
  if (route) return rowSteps(row, route);
  return word(row.completeSequenceSteps) ?? rowSteps(row);
};

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
) {
  if (
    !steps.length ||
    states.length !== steps.length ||
    spokenSteps.length !== steps.length
  )
    throw new Error("leaf: a key sequence needs one state and spoken label per step");
  const reading = steps.map((text, index) => {
    const state = states[index];
    const spoken = spokenSteps[index];
    if (!STATES.has(state)) throw new Error(`leaf: unknown key state ${String(state)}`);
    return Object.freeze({ text, spoken, state });
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
        html`<kbd data-lf-sequence-step-state=${step.state} aria-hidden="true"
          >${step.text}</kbd
        >`,
    )}</span
  >`;
}
