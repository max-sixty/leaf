/* Internal render-check adaptation over the semantic publisher.

   Validation may temporarily paint authored, carried, and current projections to prove
   replay causality. It selects those snapshots from the publisher and adapts body
   facets to the DOM; package modules never receive this historical selector. */
import { selectWidgets } from "./semantic-state.js";
import { domFacet } from "./projection/authored.js";
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
        .map(([facet, spec]) => [facet, domFacet(elementById(id), spec.record)]),
  }));
}
