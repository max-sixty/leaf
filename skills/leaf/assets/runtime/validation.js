/* Internal render-check adaptation over the semantic and presentation publishers.

   Validation may temporarily paint authored, carried, and current projections to prove
   replay causality. It selects those snapshots from the publisher and adapts body
   facets to the DOM. It also exposes the coordinator's synchronous current-readiness
   fact. Package modules receive neither validation-only reading. */
import { applicationPresented, selectWidgets } from "./semantic-state.js";
import { domFacet } from "./projection/authored.js";
import { elementById } from "./passages.js";

export const validationPresentationReady = applicationPresented;

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
