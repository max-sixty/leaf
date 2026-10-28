/* A view of another widget's answer (x-shows), such as a board card standing in the
   column of the pick its section holds.

   The answer stays its widget's. Reading it here reads that widget's own published
   state, so a view drawing it in `render()` follows every pick, undo, refusal and
   revision the widget does; changing it here sends the widget's own `x-awaits.value`
   command through its controller, the same command its own control sends, so a view
   records no fact of its own. Python's `shown_answers.py` owns the contract and reads
   the same rule for `page check`: an answer names a value when it is one string, a
   `value` record's attribute or the picked members' `x-awaits.key` all naming the
   same one, and names none otherwise. */
import { declarationFor } from "./registry.js";
import { authoredScope, elementById } from "./passages.js";
import { widgetController } from "./widget-controller.js";
import { widgetDescriptor } from "./widget-descriptors.js";

// The value `answer` names, given the reading of the member key it is picked by.
const namedValue = (answer, keyOf) => {
  if (!keyOf) return typeof answer === "string" && answer ? answer : null;
  const values = new Set((Array.isArray(answer) ? answer : []).map(keyOf));
  return values.size === 1 && !values.has(null) ? [...values][0] : null;
};

/** The answer one view element shows, or null where it shows none: no `x-shows`, no
 * widget by that id in its own document, a widget whose answer no view can show, a
 * quoted one, or one whose state has not loaded.
 * `value` is the value the answer names now (null for none), `available` whether the
 * user can change it, `takes(value)` whether the widget can answer `value` (null
 * clears a pick), and `answer(value, says)` sends the widget's command, returning
 * what `dispatch` returns, or null where the widget can't take `value`. */
export function shownAnswer(view) {
  const shows = declarationFor(view, "x-shows");
  const id = shows && view.getAttribute(shows.attr);
  if (!id) return null;
  const owner = elementById(id, authoredScope(view));
  const awaits = owner && declarationFor(owner, "x-awaits");
  const verb = awaits?.value;
  const record = verb && declarationFor(owner, "x-state")?.[verb]?.record;
  if (record?.kind !== "value" && !(record?.kind === "attribute" && awaits.key))
    return null;
  // A quoted widget is a mention with no state to show.
  if (!widgetDescriptor(owner)) return null;
  const controller = widgetController(owner);
  const reading = controller.read();
  const state = reading.state?.[verb];
  if (!state) return null;
  const scope = authoredScope(owner);
  const keyOf =
    record.kind === "attribute"
      ? (member) => elementById(member, scope)?.getAttribute(awaits.key) ?? null
      : null;
  const detailFor = (value) => {
    if (!keyOf) return value === null ? null : { value };
    if (value === null) return { value: [] };
    const members = (reading.memberships?.[record.attr] ?? []).filter(
      (member) => keyOf(member) === value,
    );
    return members.length ? { value: members } : null;
  };
  return Object.freeze({
    owner,
    value: namedValue(state.value, keyOf),
    available: Boolean(reading.actions[verb]?.available),
    takes: (value) => detailFor(value) !== null,
    answer(value, says) {
      const detail = detailFor(value);
      return detail
        ? controller.dispatch({ kind: "action", verb, detail, ...(says && { says }) })
        : null;
    },
  });
}
