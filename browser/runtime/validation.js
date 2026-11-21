/* Internal render-check adaptation over the semantic publisher.

   The replay render check reads each widget's current state from the publisher
   with a reader of the values its body records hold in the DOM. Package modules do
   not receive this validation-only reading. */
import { selectWidgets } from "./semantic-state.js";
import { domValue } from "./projection/authored.js";
import { elementById } from "./passages.js";

export function validationWidgetStates() {
  return [...selectWidgets()].map(([id, { state, specs }]) => ({
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
