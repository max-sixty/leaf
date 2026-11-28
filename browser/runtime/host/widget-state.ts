/* A widget's reading as Leaf hands it to the widget's element: the immutable `state`
   Leaf sets on it (`widgetState`), the Undo each of its units offers
   (`undoCandidates`), and what the widget says of its obligation as that state stands
   (`widgetAnswered`), which each gesture of it carries to the log. */
import { applicationState, readApplication } from "../state/semantic-state.js";
import { holdsState } from "../state/projection/model.js";
import { registry } from "../state/registry.js";
import { widgetStatic } from "../records/obligations/answer.js";
import { reportFailure } from "../lib/failure.js";
import type { WidgetState } from "../../types/domain.js";

export type WidgetReading = ReturnType<
  ReturnType<typeof applicationState.selectWidget>["read"]
>;

export const immutable = <T>(value: T): T => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
  }
  return value;
};

// Each unit of a verb whose action in force the user may take back, with the Undo
// candidate that takes it back.
export const undoCandidates = (
  action: WidgetReading["actions"][string] | undefined,
) => {
  const undo = new Map(action?.undo.map((event) => [event.id, event]));
  const units: Map<string, WidgetReading["actions"][string]["undo"][number]> =
    new Map();
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
export const widgetState = ({ state, actions }: WidgetReading): WidgetState =>
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
// (`widgetState`) and the widget's authored markup as `answerWords` is
// (`widgetStatic`), so the word needs no drawing of the widget, as one in a thread
// nobody has open has none; or, where the class says nothing, whether the user's acts
// hold a state at the verb `awaits.value` names (`holdsState`). A class's `answered`
// that throws is the widget's failure, reported as one, and the gesture goes saying
// the question is open rather than waiting on a widget that can't say, so a failing
// widget leaves its question on On Me rather than closing it; a class that says never
// has the default rule speak for it. `tag` names the widget's
// kind where no captured descriptor does, as for an undo of an action in a message
// nobody has drawn. A widget that asks always says, and one that asks nothing says
// nothing.
export function widgetAnswered(
  widget: string,
  tag: string | null,
): boolean | undefined {
  const root = readApplication();
  const descriptor = root.document.descriptors.get(widget);
  const kind = descriptor?.tag ?? tag;
  const verb = kind ? registry[kind]?.awaits?.value : undefined;
  if (!kind || !verb) return undefined;
  const folded = root.effective.widgets.get(widget);
  const byDefault = () => Boolean(folded && holdsState(folded, verb));
  const own = widgetStatic(kind, widget, "answered");
  if (!own) return byDefault();
  // A widget no page has captured has no reading: its folded state, or none, is all
  // there is to say from.
  const state = descriptor
    ? widgetState(applicationState.selectWidget(descriptor).read())
    : ((folded?.state ?? {}) as WidgetState);
  if (!own.element) {
    console.error(
      `leaf: <${kind} id="${widget}"> has no markup to say its answer from`,
    );
    return false;
  }
  try {
    return Boolean(own.call(state, own.element));
  } catch (error) {
    reportFailure(own.element, error);
    return false;
  }
}
