/* The document's single semantic owner. Its compiled pure folds publish a complete
   immutable reading synchronously; renderer nodes and transport promises stay in
   their adapters. Importing this module does not mount any view or start delivery. */
import {
  collectReads,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
  PRESENTATION_HELD,
} from "../vendor/browser-runtime.js";

import { bindQueuedWork } from "./queued-work.js";

const documentToken = Object.freeze({});
// The semantic epoch the application last began presenting, which is the epoch of the
// root it publishes next. Presentation proof compares against it; a paint that waits on
// proof reads no part of the root for it, so the wait subscribes the paint to nothing.
let begunEpoch;
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
    begin: (semanticEpoch) =>
      presentation.begin(documentToken, (begunEpoch = semanticEpoch)),
    // The application seals each publication as `begin` returned it.
    seal: (publication) =>
      presentation.seal(
        /** @type {ReturnType<typeof presentation.begin>} */ (publication),
      ),
  },
});
export const readApplication = applicationState.read;
// A reader of one part of the root, through its own selection. A key or button
// reflection tracks what it reads (keyboard/scopes.js), and a watcher's or a region's
// paint collects it (projection-watch.js, `applicationPresenter`), so each reads again
// only when that part moves. An accessor that reads the whole root would make every
// reflection read again on every publication, and inside a paint it throws.
/**
 * @template T
 * @param {(root: ReturnType<typeof readApplication>) => T} derive
 */
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
// the widget nodes those passages placed, and the On panel formats the canonical
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

// One region's epoch presenter. `reading` decides, synchronously, whether the region
// owes a paint and with what value: it returns null where the region owes nothing,
// before the page has read the log or where this renderer was never mounted, and
// otherwise the value `paint` receives. The paint runs on the pass after the claim,
// once every region ranked before it has painted, and reads the root as it stands then.
// Each of them reads through readers that select their parts (`readPart`): the reading's
// reads and those the paint makes before its first `await` are collected
// (`collectReads`), and the region follows them, so nobody lists what a region depends
// on. A publication that moves a part either read claims a presentation inside that
// publication, with the value the reading gives then; one that moves none of them is no
// claim, so the region carries its last commit into the new epoch (presentation.ts,
// `begin`). A move of the reading's own parts that leaves its value as it was claimed
// is no claim either, so a region that reads one unchanging value through a phase keeps
// it. A read of the whole root in either throws, since every publication moves it. What
// the paint takes from beyond the root — the clock, a draft, the document's own nodes —
// is a mechanical change, and its owner claims through `present`, which claims whatever
// the reading gives, so a reading that stands still is still painted when asked for. A
// renderer withholds a value it does owe by returning `PRESENTATION_HELD`, which keeps
// its region pending until a later claim supersedes it.
/** @param {{
 *   region: string,
 *   renderer?: object,
 *   order?: number,
 *   reading: () => unknown,
 *   paint: (value: any, current: () => boolean) => unknown,
 *   failSoft?: (reason: unknown) => unknown,
 * }} presenter */
export const applicationPresenter = ({
  region,
  renderer = document,
  order,
  reading,
  paint,
  failSoft,
}) => {
  // The parts the last reading and the last paint read, each with the value it read.
  let readingReads = new Map();
  let paintReads = new Map();
  // The value last claimed, and whether its paint has yet to start.
  let claimed;
  let owed = false;
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region, renderer),
    order,
    paint: (value, current) => {
      owed = false;
      const outcome = collectReads(() => paint(value, current));
      paintReads = outcome.reads;
      if ("error" in outcome) throw outcome.error;
      return outcome.value;
    },
    failSoft,
  });
  const read = () => {
    const outcome = collectReads(reading);
    readingReads = outcome.reads;
    if ("error" in outcome) throw outcome.error;
    return outcome.value;
  };
  const claim = (value) => {
    claimed = value;
    if (value === null) return schedule.passed();
    owed = true;
    return presenter.sync(value);
  };
  const moved = (reads) => [...reads].some(([part, seen]) => part.read() !== seen);
  const present = () => claim(read());
  documentPresenters.push(present);
  // A region claims on the publications after this first reading; a renderer that owes
  // its first value earlier asks with `present`. One subscription, made here, hears
  // every publication, so each region claims at the same point in a publication as it
  // always has, before anything that publication starts waits on presentation.
  claimed = read();
  applicationState
    .select((root) => root)
    .subscribe(() => {
      // A paint's part moved, which owes a paint unless one is already owed, or the
      // reading's part moved, which owes one only where the value changed.
      const painted = !owed && moved(paintReads);
      if (!painted && !moved(readingReads)) return;
      const value = read();
      if (value === null) claimed = null;
      else if (painted || value !== claimed) void claim(value);
    });
  // A document-wide region lives as long as the page; `disconnect` releases its renderer,
  // and a region that may mount again reads null while it is not mounted.
  const disconnect = () => {
    paintReads = new Map();
    presenter.disconnect();
  };
  return Object.freeze({ present, disconnect });
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
  semanticEpoch: begunEpoch,
});
export const whenApplicationPresented = () =>
  presentation.whenCurrentPresented(currentApplicationPresentation);
export const applicationPresented = () =>
  presentation.currentPresented(currentApplicationPresentation);
export const whenWidgetsPresented = (widgets) =>
  presentation.whenCurrentRegionsPresented(
    () => ({
      document: documentToken,
      semanticEpoch: begunEpoch,
    }),
    widgets.flatMap(widgetRegions),
  );
export const whenApplicationRegionsPresented = (regions, current) =>
  presentation.whenCurrentRegionsPresented(
    () =>
      current()
        ? {
            document: documentToken,
            semanticEpoch: begunEpoch,
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
