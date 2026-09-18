/* The document's single semantic owner. Its compiled pure folds publish a complete
   immutable reading synchronously; renderer nodes and transport promises stay in
   their adapters. Importing this module does not mount any view or start delivery. */
import {
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
  describeFailure,
  PRESENTATION_HELD,
} from "../vendor/browser-runtime.js";

const documentToken = Object.freeze({});
let reportPresentationFailure = (reason) =>
  console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason),
});
// A publication paints on the pass after it, so every subscriber has claimed its region
// before any renderer touches the document.
const schedule = createPresentationSchedule();

export const applicationState = createSemanticApplication({
  presentation: {
    begin: (semanticEpoch) => presentation.begin(documentToken, semanticEpoch),
    seal: (publication) => presentation.seal(publication),
  },
});
export const readApplication = applicationState.read;
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
export const attachApplicationPresentation = (region, renderer) =>
  presentation.attach(region, renderer);
export const attachWidgetPresentation = (widget, kind, renderer) =>
  presentation.attach(`widget:${widget}:${kind}`, renderer);

// Where a document-wide renderer stands in one presentation pass. The projection
// materializes provenance words and coordinate chrome inside authored elements, the
// conversation resolves its passages over the nodes that leaves, and the Ask inventory
// reads the conversation those passages placed. Declaring the order here is what lets
// every publisher simply publish.
export const PRESENTATION_ORDER = Object.freeze({
  projection: 0,
  conversation: 1,
  asks: 2,
});

// The document-wide presenters, in registration order. `presentDocument` is what a
// caller reaches for when it has changed something every region may be showing and has
// no business knowing which those are.
const documentPresenters = [];

// One region's epoch presenter: the claim is synchronous, inside the publication that
// opened the epoch, and the paint runs on the pass that follows it. `current` reads the
// value this region owes now, so claiming never needs the caller to carry one, and
// returns null where the region owes nothing yet — before the page has read the log,
// or on a copy where this renderer was never mounted. That answer belongs to the
// presenter rather than to whoever asks it to paint: a region claimed for a renderer
// that cannot paint stays pending, and the page never presents at all. A renderer
// withholds a reading it does owe by returning `PRESENTATION_HELD`, which keeps its
// region pending until a later claim supersedes it.
export const applicationPresenter = ({
  region,
  renderer = document,
  order,
  current,
  paint,
  failSoft,
}) => {
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region, renderer),
    order,
    paint,
    failSoft,
  });
  const present = () => {
    const value = current();
    return value === null ? schedule.passed() : presenter.sync(value);
  };
  documentPresenters.push(present);
  return Object.freeze({ present, disconnect: presenter.disconnect });
};

/** Claim every document-wide region for the root as it stands now. */
export const presentDocument = () => {
  for (const present of documentPresenters) void present();
  return schedule.passed();
};

// The page has caught up with the root it is reading: every presenter the current
// publications collected has painted, including the ones their painting collected. This
// is what a caller awaits instead of naming renderers, and it carries the first paint
// failure of the pass so an accepted reading that could not be shown stays unrecorded.
export const documentPresented = () => schedule.passed();
export { PRESENTATION_HELD };

export class PresentationRetentionError extends AggregateError {}

export const failSoftAfterRetention = (proof) => (reason) => {
  if (reason instanceof PresentationRetentionError) throw reason;
  return proof;
};
const currentApplicationPresentation = () => ({
  document: documentToken,
  semanticEpoch: readApplication().semanticEpoch,
});
export const whenApplicationPresented = () =>
  presentation.whenCurrentPresented(currentApplicationPresentation);
export const applicationPresented = () =>
  presentation.currentPresented(currentApplicationPresentation);
export const whenWidgetsPresented = (widgets) =>
  presentation.whenCurrentRegionsPresented(
    () => ({
      document: documentToken,
      semanticEpoch: readApplication().semanticEpoch,
    }),
    widgets.flatMap((widget) => [
      `widget:${widget}:render`,
      `widget:${widget}:preparation`,
    ]),
  );
export const whenApplicationRegionsPresented = (regions, current) =>
  presentation.whenCurrentRegionsPresented(
    () =>
      current()
        ? {
            document: documentToken,
            semanticEpoch: readApplication().semanticEpoch,
          }
        : null,
    regions,
  );
export const readApplicationPresentation = presentation.read;
export function setPresentationFailureReporter(report) {
  if (typeof report !== "function")
    throw new TypeError("Presentation failure reporting needs a callback");
  reportPresentationFailure = (reason) =>
    report(`Presentation failed: ${describeFailure(reason)}`);
}
export const watchSemantic = (callback) =>
  applicationState
    .select((root) => root.semanticEpoch)
    .subscribe(() => callback(readApplication()));
