// Compiled from validation.ts by build/typescript.mjs; edit that file.
/* Internal render-check adaptation over the semantic publisher.

   The replay render check reads each widget's current state from the publisher
   with a reader of the values its body records hold in the DOM. Package modules do
   not receive this validation-only reading. */
import { selectWidgets } from "./state/semantic-state.js";
import { domValue } from "./records/projection/authored.js";
import { elementById } from "./readings/passages.js";

export function validationWidgetStates() {
  return [...selectWidgets()].map(([id, { state, specs }]) => ({
    id,
    get widget() {
      return elementById(id);
    },
    state,
    read: (widget) =>
      [...specs].flatMap(([verb, spec]) =>
        spec.record?.kind === "body" ? [[verb, domValue(widget, spec.record)]] : [],
      ),
  }));
}
