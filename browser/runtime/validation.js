/* Internal render-check adaptation over the semantic publisher.

   Validation may temporarily paint authored, carried, and current projections to prove
   replay causality. It selects those snapshots from the publisher and adapts body
   records to the DOM. Package modules do not receive this validation-only reading. */
import { selectWidgets } from "./semantic-state.js";
import { domValue } from "./projection/authored.js";
import { elementById } from "./passages.js";

/** @param {readonly string[] | null} [eventIds] */
export function validationWidgetStates(eventIds = null) {
  return [...selectWidgets(eventIds)].map(([id, { state, specs }]) => ({
    id,
    get widget() {
      return elementById(id);
    },
    state,
    read: (/** @type {Element} */ widget) =>
      [...specs].flatMap(([verb, spec]) =>
        spec.record?.kind === "body" ? [[verb, domValue(widget, spec.record)]] : [],
      ),
  }));
}
