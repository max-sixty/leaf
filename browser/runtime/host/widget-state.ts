/* A widget's reading as Leaf hands it to the widget's element: the immutable `state`
   Leaf sets on it (`widgetState`), the Undo each of its units offers
   (`undoCandidates`), and what the widget works out of that state for the page to keep
   (`widgetFacts`), which each gesture of it carries to the log. */
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

// What a widget works out of its state and markup for the page to keep (`facts`), as
// that state now stands: each fact its declaration lists, by name. Each of its actions
// and each undo of one carries them (records/pending/dispatch.js), and a tab sends them
// again where the state or markup moves without a gesture of its own
// (host/widget-facts.js). Each is the class's static of the fact's name, given the
// `state` Leaf sets (`widgetState`) and the widget's authored markup as `answerWords`
// is (`widgetStatic`), so a fact needs no drawing of the widget, as one in a thread
// nobody has open has none. Where the class says nothing of `answered`, Leaf says
// whether the user's acts hold a state at the verb `awaits.value` names
// (`holdsState`). A static that throws, a fact with no static, and a widget with no
// markup to work from are the widget's failure, reported as one, and the fact goes
// unsaid, apart from `answered`, which says the question is open rather than waiting
// on a widget that can't say, so a failing widget leaves its question on On Me rather
// than closing it. `tag` names the widget's kind where no captured descriptor does, as
// for an undo of an action in a message nobody has drawn. A widget that declares no
// facts says none.
export function widgetFacts(
  widget: string,
  tag: string | null,
): Record<string, unknown> | undefined {
  const root = readApplication();
  const descriptor = root.document.descriptors.get(widget);
  const kind = descriptor?.tag ?? tag;
  const entry = kind ? registry[kind] : undefined;
  if (!kind || !entry?.facts) return undefined;
  const folded = root.effective.widgets.get(widget);
  // A widget no page has captured has no reading: its folded state, or none, is all
  // there is to work from.
  const state = descriptor
    ? widgetState(applicationState.selectWidget(descriptor).read())
    : ((folded?.state ?? {}) as WidgetState);
  const facts: Record<string, unknown> = {};
  for (const name of Object.keys(entry.facts)) {
    const own = widgetStatic(kind, widget, name);
    const verb = entry.awaits?.value;
    if (!own && name === "answered" && verb) {
      facts.answered = Boolean(folded && holdsState(folded, verb));
      continue;
    }
    const value = workedOut(own, `<${kind} id="${widget}">`, name, state);
    if (name === "answered") facts.answered = Boolean(value);
    else if (value !== undefined) facts[name] = value;
  }
  return facts;
}

/** One fact as `own` works it out of `state`, or undefined where it can't. */
function workedOut(
  own: ReturnType<typeof widgetStatic>,
  widget: string,
  name: string,
  state: WidgetState,
) {
  if (!own?.element) {
    console.error(
      own
        ? `leaf: ${widget} has no markup to work its ${name} out from`
        : `leaf: ${widget} lists the fact ${name}, but its class has no static ${name}`,
    );
    return undefined;
  }
  try {
    const value = own.call(state, own.element);
    // A value the event can't carry fails here, where the widget's failure is named.
    JSON.stringify(value);
    return value;
  } catch (error) {
    reportFailure(own.element, error);
    return undefined;
  }
}
