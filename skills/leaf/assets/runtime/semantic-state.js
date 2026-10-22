/* The page's application state, `applicationState`: one immutable root that compiled
   pure folds publish synchronously, and the presenters that paint it. DOM nodes and
   network promises stay out of the root, in the modules that own them. Importing this
   module mounts no view and starts no delivery. */
import {
  createMemo,
  createSignal,
  flush,
  watchReaction,
  watchEffect,
  outsideReading,
  untracked,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
} from "/vendor/browser-runtime.js";

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
// paint follows it (projection-watch.js, `applicationPresenter`), so each reads again
// only when that part moves. An accessor that reads the whole root would make every
// reflection read again on every publication.
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
// Whether a session holds the page's claim, by the server's reading: false before one
// has arrived.
export const pageClaimed = readPart(
  (root) => root.authoritative?.claim_session != null,
);
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
export const attachApplicationPresentation = (region, renderer) =>
  presentation.attach(region, renderer);
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
const widgetRegions = (widget) =>
  ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
export const attachWidgetPresentation = (widget, kind, renderer) =>
  presentation.attach(widgetRegion(widget, kind), renderer);

// A parent renders moved members before their attribute-set owner reads the DOM.
// Authored parentage and projected moves supply the current depth; module arrival
// order supplies none. Widgets paint ahead of document projection at zero.
const currentWidgetParents = readPart((root) => root.effective.widgetParents);
const widgetOrder = (widget) => {
  const parents = currentWidgetParents();
  const seen = new Set();
  let depth = 0;
  for (let parent = parents.get(widget); parent; parent = parents.get(parent)) {
    if (seen.has(parent)) break;
    seen.add(parent);
    depth++;
  }
  return -1 / (depth + 1);
};
export const queueWidgetUpdate = (widget, update) =>
  schedule.enqueue(
    untracked(() => widgetOrder(widget)),
    update,
  );

// Where a document-wide renderer stands in one presentation pass. The projection
// materializes provenance words and coordinate chrome inside authored elements, the
// thread resolves its passages over the nodes that leaves, and the obligation view resolves
// the widget nodes those passages placed. Declaring the order here is what lets every
// publisher simply publish.
export const PRESENTATION_ORDER = Object.freeze({
  projection: 0,
  thread: 1,
  obligations: 2,
});

// The document-wide presenters, in registration order. `presentDocument` is what a
// caller reaches for when it has changed something every region may be showing and has
// no business knowing which those are.
const documentPresenters = [];
// `applicationPresenter` registers one region of the page, such as `projection:chrome`
// in projection/presentation.js, that repaints when the parts of the application state
// it reads change.
//
// `reading()` runs when its selected inputs move and returns the value to paint, or
// null when the region has nothing to paint (before the page has read the log, or while
// its renderer is not mounted). `paint(value, current, resume)` runs on the next
// presentation pass, after every region with a lower `order` has painted, and reads the
// state as it is then.
//
// No one lists a region's dependencies. Both functions read through `readPart`
// selectors; native Solid computed values and effects follow those reads. A publication
// that changes a part `paint` read schedules a paint. One that changes only parts
// `reading` read schedules a paint only if `reading` now returns a different value. One
// that changes neither carries the region's last paint into the new epoch
// (presentation.ts, `begin`). Reading the whole root subscribes to every publication,
// so renderers select the parts they draw.
//
// Recording sees only synchronous code. A paint that awaits wraps each continuation in
// `resume`, as a `.then` callback or a function it calls after an `await`; reads in a
// continuation it does not wrap are not followed. A paint's reads of values outside the
// state, such as the time it shows (`clockValue`), are followed too (`outsideReading`),
// and a change to one repaints the region. Anything else the paint takes from outside
// the state, such as a draft or the page's own nodes, is not followed: whoever changes
// it calls the returned `present()`, which paints what `reading` returns even if that
// has not changed.
/** @param {{
 *   region: string,
 *   renderer?: object,
 *   order?: number,
 *   reading: () => unknown,
 *   paint: (value: any, current: () => boolean, resume: <A extends unknown[], R>(run: (...args: A) => R) => (...args: A) => R) => unknown,
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
  // Reading identity decides whether a region needs new content. Solid owns its
  // dependencies, including subscriptions to values outside the application state.
  const [revision, setRevision] = createSignal(0, { ownedWrite: true });
  const selected = createMemo(
    () => {
      revision();
      const epoch = untracked(() => readApplication().semanticEpoch);
      const value = reading();
      if (epoch !== untracked(() => readApplication().semanticEpoch))
        throw new Error(`the ${region} region's reading moved a part it read`);
      return value;
    },
    { lazy: true },
  );
  // Surface a bad initial reading at registration. Eager memo construction captures
  // errors internally and can retry a self-invalidating read before a caller sees it.
  untracked(selected);
  let claimed;
  let owed = false;
  // A resumed asynchronous paint has one effect per synchronous stretch. A new paint
  // releases the whole generation; a superseded continuation keeps no subscriptions.
  let following = [];
  const forget = () => {
    for (const stop of following) stop();
    following = [];
  };
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region, renderer),
    order,
    paint: (value, current) => {
      owed = false;
      forget();
      const generation = following;
      const stretch = (run) => {
        let outcome;
        const stop = watchReaction(
          () => {
            try {
              outcome = { value: run() };
            } catch (error) {
              outcome = { error };
            }
          },
          () => {
            // Claim before the publication seals; painting belongs to the ordered pass.
            if (!owed && current())
              untracked(() => {
                const next = selected();
                if (next !== null) void claim(next);
              });
          },
        );
        if (current() && following === generation) generation.push(stop);
        else stop();
        if ("error" in outcome) throw outcome.error;
        return outcome.value;
      };
      /** @type {<A extends unknown[], R>(run: (...args: A) => R) => (...args: A) => R} */
      const resume =
        (run) =>
        (...args) =>
          stretch(() => run(...args));
      return stretch(() => paint(value, current, resume));
    },
    failSoft,
  });
  const claim = (value) => {
    claimed = value;
    if (value === null) return schedule.passed();
    owed = true;
    return presenter.sync(value);
  };
  // Mechanical inputs can change without publishing. Explicit presentation invalidates
  // the computed reading and claims it in one batch, so its observer cannot duplicate it.
  const present = () =>
    untracked(() =>
      flush(() => {
        setRevision((value) => value + 1);
        return claim(selected());
      }),
    );
  documentPresenters.push(present);
  // Registration records the initial value without drawing it. Future changed values
  // synchronously claim their region; present() can request the first paint earlier.
  let first = true;
  watchEffect(() => {
    const value = selected();
    if (first || value === null) {
      first = false;
      claimed = value;
    } else if (value !== claimed) untracked(() => claim(value));
  });
  // A document-wide region lives as long as the page; disconnect releases its renderer,
  // and a region that may mount again reads null while it is not mounted.
  const disconnect = () => {
    forget();
    presenter.disconnect();
  };
  return Object.freeze({ present, disconnect });
};

// How many times a caller has said the document changed under every region. A reading
// derived from the page's own nodes, rather than from the root, keys on it. It is an
// outside reading, so a paint that reads one follows it: a watched paint
// (`watchProjection`), which `presentDocument` does not call, repaints when the nodes it
// drew from change, as the floating panel's quote does when a datum's label does. The
// regions it calls hear it after they have claimed, which owes them nothing more.
let documentChanges = 0;
const documentListeners = new Set();
const documentReading = outsideReading(
  () => documentChanges,
  (moved) => {
    documentListeners.add(moved);
    return () => documentListeners.delete(moved);
  },
);
export const documentChanged = () => documentReading.read();

/** Claim every document-wide region for the root as it stands now. */
export const presentDocument = () => {
  documentChanges += 1;
  for (const present of documentPresenters) void present();
  const round = {};
  for (const moved of [...documentListeners]) moved(round);
  return schedule.passed();
};

// The page has caught up with the root it is reading: every presenter the current
// publications collected has painted, including the ones their painting collected. This
// is what a caller awaits instead of naming renderers, and it carries the first paint
// failure of the pass so an accepted reading that could not be shown stays unrecorded.
export const whenDocumentPresented = () => schedule.passed();

// The epoch presentation proof compares against. A paint that waits on proof reads it
// outside its collection, so waiting subscribes the paint to nothing.
const currentEpoch = () => untracked(() => readApplication().semanticEpoch);
const currentApplicationPresentation = () => ({
  document: documentToken,
  semanticEpoch: currentEpoch(),
});
export const whenApplicationPresented = () =>
  presentation.whenCurrentPresented(currentApplicationPresentation);
export const applicationPresented = () =>
  presentation.currentPresented(currentApplicationPresentation);
export const whenWidgetsPresented = (widgets) =>
  presentation.whenCurrentRegionsPresented(
    () => ({
      document: documentToken,
      semanticEpoch: currentEpoch(),
    }),
    widgets.flatMap(widgetRegions),
  );
export const whenApplicationRegionsPresented = (regions, current) =>
  presentation.whenCurrentRegionsPresented(
    () =>
      current()
        ? {
            document: documentToken,
            semanticEpoch: currentEpoch(),
          }
        : null,
    regions,
  );
export const applicationRegionsPresented = (regions) =>
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
