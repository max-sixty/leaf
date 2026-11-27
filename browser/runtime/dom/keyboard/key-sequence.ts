/* This module owns how a binding is drawn: the steps a row's sequence or label breaks
 * into, which leading steps match presses the active interaction has accepted, and the
 * immutable key-sequence reading every keyboard surface renders through one Lit template. */
import { html, nothing, repeat } from "/vendor/lit.js";

import { bindings, spell, word } from "./bindings.js";
import type { Command, CommandRoute } from "./bindings.js";

// A sequence row may name several presses, while an ordinary row still carries one compact
// label. Keep that distinction structured until the DOM is built: spaces in a label are
// words inside one step, never guessed back into a sequence. Each step holds the keys
// that take it, several where a row's bindings are alternatives, as `z` and `⌘z` both
// undo a stroke; its text joins them as `labelOf` does (bindings.js).
const rowKeySteps = (row: Command, route: CommandRoute | null = null) => {
  if (route?.binding !== undefined) return [[spell(route.binding)]];
  const steps = word(row.sequenceSteps);
  if (steps) return steps.map((step) => [step]);
  const label = word(row.label);
  if (label !== undefined && label !== null) return label ? [[label]] : [];
  const keys = bindings(row).map(spell);
  return keys.length ? [keys] : [];
};

export const completeRowKeySteps = (
  row: Command,
  route: CommandRoute | null = null,
) => {
  const steps = route ? null : word(row.completeSequenceSteps);
  return steps ? steps.map((step) => [step]) : rowKeySteps(row, route);
};

export const stepText = (keys: readonly string[]) => keys.join(" / ");

export const completeRowSteps = (row: Command, route: CommandRoute | null = null) =>
  completeRowKeySteps(row, route).map(stepText);

/** One complete step, kept together through every presentation. */
export type KeySequenceStep = {
  text: string;
  keys: readonly string[];
  spoken: string;
  state: "neutral" | "pressed";
};
export const neutralSteps = (steps: readonly string[]): KeySequenceStep[] =>
  steps.map((text) => ({
    text,
    keys: [text],
    spoken: text,
    state: "neutral",
  }));

// A pressed face means this exact step was accepted on the way to this route.
// Stop at the first divergence because a sequence is ordered.
export const progressSteps = (
  steps: readonly string[],
  pressed: readonly string[],
): KeySequenceStep[] => {
  let matching = true;
  return steps.map((text, i) => {
    matching = matching && pressed[i] === text;
    return {
      text,
      keys: [text],
      spoken: text,
      state: matching ? "pressed" : "neutral",
    };
  });
};

export function keySequenceModel(steps: readonly KeySequenceStep[]) {
  if (!steps.length) throw new Error("leaf: a key sequence needs a step");
  const reading = steps.map(({ text, keys, spoken, state }) =>
    Object.freeze({ text, keys: Object.freeze([...keys]), spoken, state }),
  );
  return Object.freeze({
    label: reading.map(({ spoken }) => spoken.replaceAll(" / ", " or ")).join(" then "),
    steps: Object.freeze(reading),
  });
}

export function keySequenceTemplate(
  model: ReturnType<typeof keySequenceModel>,
  { id = null, label = false }: { id?: string | null; label?: boolean } = {},
) {
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
