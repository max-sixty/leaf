/* A widget's reading as Leaf hands it to the widget's element: the immutable `state`
   Leaf sets on it (`widgetState`), the Undo each of its units offers
   (`undoCandidates`), and what the widget says of its obligation as that state stands
   (`widgetAnswered`), which each gesture of it carries to the log. */
import { applicationState, readApplication } from "../state/semantic-state.js";
import { holdsState } from "../state/projection/model.js";
import { addressableAt } from "../records/thread/messages.js";

/** @typedef {ReturnType<ReturnType<typeof applicationState.selectWidget>["read"]>} WidgetReading */

/** @template T @param {T} value @returns {T} */
export const immutable = (value) => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
  }
  return value;
};

// Each unit of a verb whose action in force the user may take back, with the Undo
// candidate that takes it back.
/** @param {WidgetReading["actions"][string] | undefined} action */
export const undoCandidates = (action) => {
  const undo = new Map(action?.undo.map((event) => [event.id, event]));
  /** @type {Map<string, WidgetReading["actions"][string]["undo"][number]>} */
  const units = new Map();
  for (const { unit, event } of action?.inForce ?? []) {
    const candidate = undo.get(event.id);
    if (candidate) units.set(unit, candidate);
  }
  return units;
};

// A widget's reading as the immutable `state` property Leaf sets on an element it
// drives from outside (element-integration.js): each declared verb's folded state, with
// whether the user may act on it now (`available`), the reason they may not where Leaf
// has one to give (`unavailable`), and whether `lf-undo` would take back the action in
// force (`undoable`), which a verb holding a state for each unit says on each unit. A
// verb the agent writes reads as one the user may neither act on nor take back.
/** @param {WidgetReading} reading @returns {import("../../types/domain.js").WidgetState} */
export const widgetState = ({ state, actions }) =>
  immutable(
    Object.fromEntries(
      Object.entries(state).map(([verb, held]) => {
        const undoable = undoCandidates(actions[verb]);
        const offered = {
          available: actions[verb]?.available ?? false,
          unavailable: actions[verb]?.unavailable ?? null,
        };
        return [
          verb,
          "units" in held
            ? {
                ...held,
                units: Object.fromEntries(
                  Object.entries(held.units).map(([unit, at]) => [
                    unit,
                    { ...at, undoable: undoable.has(unit) },
                  ]),
                ),
                ...offered,
              }
            : { ...held, undoable: undoable.size > 0, ...offered },
        ];
      }),
    ),
  );

// What a widget that asks says of its obligation as its state now stands, which each
// of its actions and each undo of one carries (records/pending/dispatch.js): its
// class's static `answered(state, element)`, given the `state` Leaf sets
// (`widgetState`) and the widget's authored element, wherever it stands, so the word
// needs no drawing of the widget, as one in a thread nobody has open has none; or,
// where the class says nothing, whether the verb `awaits.value` names holds a state
// (`holdsState`). A widget that asks nothing says nothing.
/** @param {string} widget @returns {boolean | undefined} */
export function widgetAnswered(widget) {
  const root = readApplication();
  const descriptor = root.document.descriptors.get(widget);
  const verb = descriptor?.declaration.awaits?.value;
  if (!descriptor || !verb) return undefined;
  const decide = /** @type {{answered?: unknown} | undefined} */ (
    customElements.get(descriptor.tag)
  )?.answered;
  const element = addressableAt(widget);
  if (typeof decide === "function" && element)
    return Boolean(
      decide(widgetState(applicationState.selectWidget(descriptor).read()), element),
    );
  const folded = root.effective.widgets.get(widget);
  return folded ? holdsState(folded, verb) : false;
}
