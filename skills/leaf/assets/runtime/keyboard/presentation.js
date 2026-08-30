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

export const pressedStates = (steps) => steps.map(() => "pressed");

export const neutralStates = (steps) => steps.map(() => "neutral");

export function keySequence(steps, states = neutralStates(steps)) {
  if (!steps.length || states.length !== steps.length)
    throw new Error("leaf: a key sequence needs one state per step");

  const sequence = document.createElement("span");
  sequence.className = "lf-key-sequence";
  sequence.setAttribute("role", "group");
  sequence.setAttribute(
    "aria-label",
    steps.map((step) => step.replaceAll(" / ", " or ")).join(" then "),
  );
  steps.forEach((step, i) => {
    const state = states[i];
    if (!STATES.has(state)) throw new Error(`leaf: unknown key state ${String(state)}`);
    if (i) {
      const then = document.createElement("span");
      then.className = "lf-key-then";
      then.setAttribute("aria-hidden", "true");
      then.textContent = "›";
      sequence.append(then);
    }
    const key = document.createElement("kbd");
    key.dataset.lfKeyState = state;
    key.setAttribute("aria-hidden", "true");
    key.textContent = step;
    sequence.append(key);
  });
  return sequence;
}
