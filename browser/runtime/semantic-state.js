// @ts-check
/* The page's application state, `applicationState`: one immutable root that compiled
   pure folds publish synchronously, and the presenters that paint it. DOM nodes and
   network promises stay out of the root, in the modules that own them. Importing this
   module mounts no view and starts no delivery. */
import {
  batch,
  computed,
  effect,
  signal,
  untracked,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
} from "/runtime/framework.js";

import { bindQueuedWork } from "./queued-work.js";
import { tick } from "./version-signal.js";

/** @param {unknown} reason */
let reportPresentationFailure = (reason) =>
  console.error("leaf: presentation failed", reason);
const presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason),
});
// A publication paints on the pass after it, so every subscriber has claimed its region
// before any renderer touches the document.
const schedule = createPresentationSchedule(bindQueuedWork);

export const applicationState = createSemanticApplication({ presentation });
export const readApplication = applicationState.read;
// A reader of one part of the root, through its own selection. A key or button
// reflection tracks what it reads (keyboard/scopes.js), and a watcher's or a region's
// paint follows it (`LeafElement`, `applicationPresenter`), so each reads again
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
// Whether a session holds the page's claim, by the server's reading: false before one
// has arrived.
export const pageClaimed = readPart(
  (root) => root.authoritative?.claim_session != null,
);
export const projectView = applicationState.projectView;
export const selectWidgets = applicationState.selectWidgets;
/** @param {string} region */
export const attachApplicationPresentation = (region) => presentation.attach(region);
/**
 * @param {string} widget
 * @param {string} kind
 */
const widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
/** @param {string} widget */
const widgetRegions = (widget) =>
  ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
/**
 * @param {string} widget
 * @param {string} kind
 */
export const attachWidgetPresentation = (widget, kind) =>
  presentation.attach(widgetRegion(widget, kind));

// These promises describe committed DOM, never semantic presentation completion. A
// widget's native updateComplete includes Lit's updated callback; its preparation
// and gesture holds belong only to its presentation tickets.
/** @type {Map<string, Promise<void>>} */
const widgetCommits = new Map();
/** @type {Map<string, () => readonly PromiseLike<unknown>[]>} */
const documentCommits = new Map();
const currentWidgetParents = readPart((root) => root.effective.widgetParents);
/**
 * @param {string} widget
 * @param {() => unknown} update
 * @param {() => PromiseLike<unknown>} committed
 */
export const queueWidgetUpdate = (widget, update, committed) => {
  const { ready, committed: dom } = schedule.enqueue(
    () => {
      const parents = untracked(currentWidgetParents);
      const pending = [];
      const seen = new Set([widget]);
      for (let parent = parents.get(widget); parent; parent = parents.get(parent)) {
        // Optimistic moves precede server admission. A cyclic move has no DOM
        // order; leave rendering and refusal free to report it instead of waiting
        // on ourselves or another member of that cycle.
        if (seen.has(parent)) return [];
        seen.add(parent);
        const dom = widgetCommits.get(parent);
        if (dom) pending.push(dom);
      }
      return pending;
    },
    update,
    committed,
  );
  widgetCommits.set(widget, dom);
  const retire = () => {
    if (widgetCommits.get(widget) === dom) widgetCommits.delete(widget);
  };
  void dom.then(retire, retire);
  return ready;
};

// The DOM each document owner reads: projection decorates widget output, threads
// resolve passages over that decoration, obligations locate controls in threads,
// and annotations measure those targets. Imperative Lit render commits in its call;
// what the thread pass decides later, where it places and seats each thread, reaches
// the margin as readings its paint follows (anchor-placement.js `placedAt`,
// thread/surfaces.js `claimed`), not as DOM it waits for. An obligation's control is a
// widget, so one a seat mounts after this commit presents the whole document as it
// connects (widget-controller.js, `widgetMounted`), and obligations locate it on the
// pass that follows. Each entry is transitive: it settles once its region and
// everything upstream of it have committed.
export const PRESENTATION_DOM = Object.freeze({
  widgets: () => [...widgetCommits.values()],
  projection: () => documentCommits.get("projection:chrome")?.() ?? [],
  thread: () => documentCommits.get("thread")?.() ?? [],
  obligations: () => documentCommits.get("obligations")?.() ?? [],
});

// The document-wide presenters, in registration order. `presentDocument` is what a
// caller reaches for when it has changed something every region may be showing and has
// no business knowing which those are.
/** @type {Array<() => Promise<void>>} */
const documentPresenters = [];
// `applicationPresenter` registers one region of the page, such as `projection:chrome`
// in projection/presentation.js, that repaints when the parts of the application state
// it reads change.
//
// `reading()` runs when its selected inputs move and returns the value to paint, or
// null when the region has nothing to paint (before the page has read the log, or while
// its renderer is not mounted). `paint(value, current, resume)` runs on the next
// presentation pass, after the DOM named by `after` has committed, and reads the
// state as it is then.
//
// Semantic dependencies are implicit. Both functions read through `readPart`
// selectors; native Preact computed values and effects follow those reads. A publication
// that changes a part `paint` read schedules a paint. One that changes only parts
// `reading` read schedules a paint only if `reading` now returns a different value. One
// that changes neither carries the region's last paint into the new epoch
// (framework/presentation.js, `begin`). Reading the whole root subscribes to every publication,
// so renderers select the parts they draw.
//
// Recording sees only synchronous code. A paint that awaits wraps each continuation in
// `resume`, as a `.then` callback or a function it calls after an `await`; reads in a
// continuation it does not wrap are not followed. A paint's reads of values outside the
// state, such as the time it shows (`clockValue`), are followed too,
// and a change to one repaints the region. Anything else the paint takes from outside
// the state, such as a draft or the page's own nodes, is not followed: whoever changes
// it calls the returned `present()`, which paints what `reading` returns even if that
// has not changed.
//
// The returned `committed()` is the region's own DOM commit. It settles at once when the
// region owes no paint; a claimed paint commits only after the DOM `after` names, so its
// commit waits for everything upstream as well.
/** @typedef {<A extends unknown[], R>(run: (...args: A) => R) => (...args: A) => R} Resume */

/**
 * @template T
 * @param {{
 *   region: string,
 *   after?: () => readonly PromiseLike<unknown>[],
 *   reading: () => T | null,
 *   paint: (value: T, current: () => boolean, resume: Resume) => unknown,
 *   failSoft?: (reason: unknown) => unknown,
 * }} options
 */
export const applicationPresenter = ({ region, after, reading, paint, failSoft }) => {
  // Reading identity decides whether a region needs new content. Preact owns its
  // dependencies, including subscriptions to values outside the application state.
  const revision = signal(0);
  const selected = computed(() => {
    revision.value;
    const epoch = untracked(() => readApplication().semanticEpoch);
    const value = reading();
    if (epoch !== untracked(() => readApplication().semanticEpoch))
      throw new Error(`the ${region} region's reading moved a part it read`);
    return value;
  });
  /** @type {T | null | undefined} */
  let claimed;
  let owed = false;
  // A resumed asynchronous paint has one effect per synchronous stretch. A new paint
  // releases the whole generation; a superseded continuation keeps no subscriptions.
  /** @type {Array<() => void>} */
  let following = [];
  const forget = () => {
    for (const stop of following) stop();
    following = [];
  };
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region),
    after,
    paint: (/** @type {T} */ value, current) => {
      owed = false;
      forget();
      const generation = following;
      /**
       * @template R
       * @param {() => R} run
       * @returns {R}
       */
      const stretch = (run) => {
        let first = true;
        /** @type {{value: R} | {error: unknown} | undefined} */
        let outcome;
        const stop = effect(() => {
          if (!first) {
            // Claim in the publication's own task, before its presentation is sealed.
            // The actual paint still belongs to the shared presentation pass.
            if (!owed && current()) {
              untracked(() => {
                const next = selected.value;
                if (next !== null) void claim(next);
              });
            }
            return;
          }
          first = false;
          try {
            outcome = { value: run() };
          } catch (error) {
            outcome = { error };
          }
        });
        if (current() && following === generation) generation.push(stop);
        else stop();
        if ("error" in /** @type {{value: R} | {error: unknown}} */ (outcome))
          throw /** @type {{error: unknown}} */ (outcome).error;
        return /** @type {{value: R}} */ (outcome).value;
      };
      /** @type {Resume} */
      const resume =
        (run) =>
        (...args) =>
          stretch(() => run(...args));
      return stretch(() => paint(value, current, resume));
    },
    failSoft,
  });
  // An unchanged intermediary may owe no paint while an upstream owner does.
  // Keep the dependency transitive even then; its last DOM commit cannot certify
  // the new upstream DOM. Each owner still declares only the edges it reads.
  documentCommits.set(region, () => [...(after?.() ?? []), presenter.committed()]);
  /** @param {T | null} value */
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
      batch(() => {
        tick(revision);
        return claim(selected.value);
      }),
    );
  documentPresenters.push(present);
  // Registration records the initial value without drawing it. Future changed values
  // synchronously claim their region; present() can request the first paint earlier.
  let first = true;
  effect(() => {
    const value = selected.value;
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
  return Object.freeze({ present, disconnect, committed: presenter.committed });
};

// How many times a caller has said the document changed under every region. A reading
// derived from the page's own nodes, rather than from the root, keys on it. It is an
// outside reading, so a Lit render that reads one follows it and repaints when the nodes it
// drew from change, as the floating panel's quote does when a datum's label does. The
// regions it calls hear it after they have claimed, which owes them nothing more.
const documentChanges = signal(0);
export const documentChanged = () => documentChanges.value;

/** Claim every document-wide region before native signal notifications run. */
export const presentDocument = () =>
  batch(() => {
    tick(documentChanges);
    for (const present of documentPresenters) void present();
    return schedule.passed();
  });

// The page has caught up with the root it is reading: every presenter the current
// publications collected has painted, including the ones their painting collected. This
// is what a caller awaits instead of naming renderers, and it carries the first paint
// failure of the pass so an accepted reading that could not be shown stays unrecorded.
export const whenDocumentPresented = () => schedule.passed();

export const whenApplicationPresented = () => presentation.whenCurrentPresented();
export const applicationPresented = () => presentation.currentPresented();
/** @param {readonly string[]} widgets */
export const whenWidgetsPresented = (widgets) =>
  presentation.whenCurrentRegionsPresented(widgets.flatMap(widgetRegions));
/**
 * @param {readonly string[]} regions
 * @param {() => boolean} [current]
 */
export const whenApplicationRegionsPresented = (regions, current) =>
  presentation.whenCurrentRegionsPresented(regions, current);
/** @param {readonly string[]} regions */
export const applicationRegionsPresented = (regions) =>
  presentation.currentRegionsPresented(regions);
/** @param {readonly string[]} widgets */
export const projectionRegionsPresented = (widgets) =>
  applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
export const watchPresentation = presentation.subscribe;
export const readApplicationPresentation = presentation.read;
/** @param {(reason: unknown, title: string) => unknown} report */
export function setPresentationFailureReporter(report) {
  reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
/** @param {(root: ReturnType<typeof readApplication>) => unknown} callback */
export const watchSemantic = (callback) =>
  applicationState
    .select((root) => root.semanticEpoch)
    .subscribe(() => callback(readApplication()));
