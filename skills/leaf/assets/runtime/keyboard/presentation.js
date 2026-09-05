/* This module owns how a binding is drawn: the steps a row's chord or label breaks
 * into, their pressed states, and the key-sequence element every surface renders them
 * as. */
import { labelOf, spell, word } from "./bindings.js";

const STATES = new Set(["neutral", "pressed"]);

// A chord row may name several presses, while an ordinary row still carries one compact
// label. Keep that distinction structured until the DOM is built: spaces in a label are
// words inside one step, never guessed back into a sequence.
export const rowSteps = (row, route = null) => {
  if (route) return [spell(route.binding)];
  return word(row.chordSteps) ?? [labelOf(row)];
};

export const completeRowSteps = (row, route = null) => {
  if (route) return rowSteps(row, route);
  return word(row.completeChordSteps) ?? rowSteps(row);
};

export const neutralStates = (steps) => steps.map(() => "neutral");

export const progressStates = (steps, pressed) =>
  steps.map((_, i) => (i < pressed ? "pressed" : "neutral"));

export function keySequence(steps, states = neutralStates(steps), spokenSteps = steps) {
  if (
    !steps.length ||
    states.length !== steps.length ||
    spokenSteps.length !== steps.length
  )
    throw new Error("leaf: a key sequence needs one state and spoken label per step");

  const sequence = document.createElement("span");
  sequence.className = "lf-key-sequence";
  sequence.setAttribute("role", "group");
  sequence.setAttribute(
    "aria-label",
    spokenSteps.map((step) => step.replaceAll(" / ", " or ")).join(" then "),
  );
  steps.forEach((step, i) => {
    const state = states[i];
    if (!STATES.has(state)) throw new Error(`leaf: unknown key state ${String(state)}`);
    const key = document.createElement("kbd");
    key.dataset.lfKeyState = state;
    key.setAttribute("aria-hidden", "true");
    key.textContent = step;
    sequence.append(key);
  });
  return sequence;
}
