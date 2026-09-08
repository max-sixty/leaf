/* This module owns how a binding is drawn: the steps a row's sequence or label breaks
 * into, which leading steps match presses the active mode has accepted, and the
 * key-sequence element every surface renders them as. */
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
