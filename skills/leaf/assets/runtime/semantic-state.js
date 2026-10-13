/* The document's single semantic owner. Its compiled pure folds publish a complete
   immutable reading synchronously; renderer nodes and transport promises stay in
   their adapters. Importing this module does not mount any view or start delivery. */
import {
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
  PRESENTATION_HELD,
} from "../vendor/browser-runtime.js";

import { bindQueuedWork } from "./queued-work.js";

const documentToken = Object.freeze({});
let reportPresentationFailure = (reason) =>
  console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason),
});
// A publication paints on the pass after it, so every subscriber has claimed its region
// before any renderer touches the document.
const schedule = createPresentationSchedule(bindQueuedWork);

/** The compiled factory is generated from this checked source contract. */
/** @type {ReturnType<typeof import("../../../../build/browser/application.ts").createSemanticApplication>} */
export const applicationState = createSemanticApplication({
  presentation: {
    begin: (semanticEpoch) => presentation.begin(documentToken, semanticEpoch),
    seal: (publication) => presentation.seal(publication),
  },
});
export const readApplication = applicationState.read;
// A reader of one part of the root, through its own selection. A key or button
// reflection tracks what it reads (keyboard/scopes.js), so an accessor that reads the
// whole root makes every reflection that calls it read again on every publication;
// one that reads its part makes them read again only when that part moves.
export const readPart = (derive) => applicationState.select(derive).read;
// What the page calls its agent: the name the server's answer gives, or "the agent"
// before one has arrived. Every surface naming the agent's side reads it here.
const agent = readPart((root) => root.authoritative?.agent ?? null);
export const agentName = () => agent() || "the agent";
// The same name where it opens a sentence or stands alone as a label.
export const agentLabel = () =>
  agentName().replace(/^./, (first) => first.toUpperCase());
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
export const attachApplicationPresentation = (region, renderer) =>
  presentation.attach(region, renderer);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) =>
  ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
export const attachWidgetPresentation = (widget, kind, renderer) =>
  presentation.attach(widgetRegion(widget, kind), renderer);

// Where a document-wide renderer stands in one presentation pass. The projection
// materializes provenance words and coordinate chrome inside authored elements, the
// thread resolves its passages over the nodes that leaves, the ask view resolves
// the widget nodes those passages placed, and the Questions panel formats the canonical
// answers against those source nodes. Declaring the order here is what lets
// every publisher simply publish.
export const PRESENTATION_ORDER = Object.freeze({
  projection: 0,
  thread: 1,
  asks: 2,
  queue: 3,
});

// The document-wide presenters, in registration order. `presentDocument` is what a
// caller reaches for when it has changed something every region may be showing and has
// no business knowing which those are.
const documentPresenters = [];

// One region's epoch presenter. `reading` selects, from the semantic root, everything
// the region's paint draws from it, and returns null where the region owes nothing:
// before the page has read the log, or where this renderer was never mounted. The
// region claims a presentation inside each publication that changes that selection,
// and the paint runs on the pass that follows; a publication that leaves it unchanged
// is no claim, so the region carries its last commit into the new epoch
// (presentation.ts, `begin`). A selection shares unchanged parts across publications
// (snapshot.ts), so a reading that names the parts it draws claims only when one of
// them moves. What the paint reads beyond the root — the clock, a draft, the document's
// own nodes — is a mechanical change, and its owner claims through `present`, which
// selects the root as it stands. `reading` is the region's one decision of whether it
// owes anything, for a publication's claim and `present` alike, and a claim always
// paints, so a reading that stands still is still painted when asked for. A renderer
// withholds a reading it does owe by returning `PRESENTATION_HELD`, which keeps its
// region pending until a later claim supersedes it.
export const applicationPresenter = ({
  region,
  renderer = document,
  order,
  reading,
  paint,
  failSoft,
}) => {
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region, renderer),
    order,
    paint,
    failSoft,
  });
  const claim = (value) => (value === null ? schedule.passed() : presenter.sync(value));
  const present = () => claim(reading(readApplication()));
  documentPresenters.push(present);
  // A document-wide region lives as long as the page; `disconnect` releases its renderer,
  // and a region that may mount again reads null while it is not mounted.
  // A selection's subscriber hears its value at once; a region claims on the changes
  // after it, and a renderer that owes its first reading earlier asks with `present`.
  let subscribed = false;
  applicationState.select(reading).subscribe((value) => {
    if (subscribed) void claim(value);
    subscribed = true;
  });
  return Object.freeze({ present, disconnect: presenter.disconnect });
};

// How many times a caller has said the document changed under every region. A reading
// derived from the page's own nodes, rather than from the root, keys on it.
let documentChanges = 0;
export const documentChanged = () => documentChanges;

/** Claim every document-wide region for the root as it stands now. */
export const presentDocument = () => {
  documentChanges += 1;
  for (const present of documentPresenters) void present();
  return schedule.passed();
};

// The page has caught up with the root it is reading: every presenter the current
// publications collected has painted, including the ones their painting collected. This
// is what a caller awaits instead of naming renderers, and it carries the first paint
// failure of the pass so an accepted reading that could not be shown stays unrecorded.
export const whenDocumentPresented = () => schedule.passed();
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
    widgets.flatMap(widgetRegions),
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
const applicationRegionsPresented = (regions) =>
  presentation.currentRegionsPresented(currentApplicationPresentation, regions);
export const projectionRegionsPresented = (widgets) =>
  applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
export const watchPresentation = presentation.subscribe;
export const readApplicationPresentation = presentation.read;
export function setPresentationFailureReporter(report) {
  reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
export const watchSemantic = (callback) =>
  applicationState
    .select((root) => root.semanticEpoch)
    .subscribe(() => callback(readApplication()));
