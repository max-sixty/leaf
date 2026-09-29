/* Internal render-check adaptation over the semantic publisher.

   Validation may temporarily paint authored, carried, and current projections to prove
   replay causality. It selects those snapshots from the publisher and adapts body
   records to the DOM. Package modules do not receive this validation-only reading. */
import { selectWidgets } from "./semantic-state.js";
import { domValue } from "./projection/authored.js";
import { elementById } from "./passages.js";

export function validationWidgetStates(eventIds = null) {
  return [...selectWidgets(eventIds)].map(([id, { state, specs }]) => ({
    get widget() {
      return elementById(id);
    },
    state,
    read: () =>
      [...specs]
        .filter(([, spec]) => spec.record?.kind === "body")
        .map(([verb, spec]) => [verb, domValue(elementById(id), spec.record)]),
  }));
}
