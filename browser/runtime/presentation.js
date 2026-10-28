/* The page's readiness: the stamps written on body, the work an owner finishes after
   presentation (`deferredArrival`), and the events startup dispatches to present the
   page (`PRESENTATION`, `PAGE_INTERFACE`). The words and marks the runtime paints onto
   page-owned elements live in declared-words.js.

   The page has three readiness facts, all three written on `body` rather than on the
   root element. A reader waiting on the root sees an empty `dataset` forever, with every
   module loaded, nothing logged and nothing failed — which reads exactly like a page
   that never started, and sends the search to the server, the page key and the page's
   layer in turn:

   - `data-lf-upgraded` means widget imports, asynchronous upgrades, geometry, and
     drawings have finished.
   - `data-lf-applied` is the event coverage of the last complete semantic projection
     committed to the DOM.
   - `data-lf-presented` means the initial authoritative projection, or the deliberate
     offline authored fallback, has crossed the semantic-interaction boundary.

   Beside them, `data-lf-reading` names the `/api/state` answer the page last applied
   (`markStateApplied`): its log, data, status, versions and presence adopted, its
   document's presentation pass finished, and every data subscriber told. A drag may
   still hold a region that pass reached; the coordinator, not this stamp, says so.

   Do not merge these stamps. A document can finish upgrading while its first state read
   is pending, or the answer can wait unapplied while upgrades finish. A later semantic
   publication or same-epoch renderer replacement leaves `data-lf-presented` set while
   the presentation coordinator reopens. A reader outside the page does not combine
   them itself: `pageReadiness` names the first of these facts, and of those below,
   still outstanding, and the entry script hands it to every such reader as
   `lfReadiness`.

   Presentation is not the end of the page's arrival. An owner may deliberately keep work
   off the presentation path, such as a widget's progressive upgrade, and that work
   still moves boxes when it lands. Where that landing would move what the reader sees,
   its owner holds the growth until it would not (thread/held-news.js, `heldGrowth`). `deferredArrival` is where such an owner says so,
   and the `arrived` stage of `pageReadiness` answers whether any of it is still
   outstanding. Startup waits for these arrivals before
   its final retained fragment landing, so late geometry keeps the requested place.
   A reader outside the page waits on the
   page rather than on a widget it had to know about. Without it the only thing outside
   the page that knows a deferred upgrade exists is whoever remembered to name it, which
   is a reader repeating what the page should settle.

   A widget reaches this through two routes, and each declares what it defers, so no
   widget keeps work off the presentation path without the page counting it.
   `afterPresentation` is the wait and the declaration together, for work the widget
   earns the right to start only once the user has the page. `deferredArrival` is the
   declaration alone, for work already running that presentation need not wait for,
   such as a live sample's child page starting below the window: the work starts
   now, the page presents without it, and `arrived` waits for it. Neither hands a
   package the bare `presented` wait. */

import { whileConnected } from "./arrivals.js";
import { applicationPresented } from "./semantic-state.js";
import { reportPageError } from "./layer-client.js";
import { activityTransitionAt } from "./presence.js";
import { renderingState } from "./rendering.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { PAGE_PAINT_ATTRIBUTE, pagePresented } from "./page-paint.js";

export const UPGRADE = "lf-upgraded";
export function markPageUpgraded() {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  document.dispatchEvent(new Event(UPGRADE));
}
// The stamp is written here and nowhere else, and never taken back, so the promise it
// resolves answers every later waiter too.
/** @type {PromiseWithResolvers<void>} */
const { promise: presented, resolve: resolvePresented } = Promise.withResolvers();
export function markPagePresented() {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.presented, "1");
  resolvePresented();
}

// The arrivals their owners placed after presentation and that have not landed yet.
// Registration is synchronous at the point the owner decides to defer — before
// presentation for anything a page starts with — so the page never reads as arrived in
// the window between presenting and its first deferred upgrade taking hold. A
// rejection lands the arrival like a resolution; its owner draws the failure.
const arriving = new Set();
// Those waiting for the page to start arriving again (`whenArriving`).
const restarts = new Set();

/** Declare work this page finishes after presenting, and hand back its promise. */
export function deferredArrival(work) {
  arriving.add(work);
  const landed = () => arriving.delete(work);
  work.then(landed, landed);
  for (const restart of restarts) restart();
  restarts.clear();
  return work;
}

/** Wait for declared arrivals, including any they introduce while settling. */
export async function whenArrived() {
  while (arriving.size) await Promise.allSettled(arriving);
}

/** Wait until some arrival is outstanding: at once if one is, else at the next one
    declared, as when a sample this page holds is Reset. */
export const whenArriving = () =>
  arriving.size ? Promise.resolve() : new Promise((restart) => restarts.add(restart));

/** Run `work` once the page has presented, as an arrival the page answers for. */
export const afterPresentation = (work) => deferredArrival(presented.then(work));

// The `/api/state` answer this page last applied: the reading that names it, the moment
// the server took it, and the moment its activity could next change with no file
// moving (`activityTransitionAt`), all on the server's clock. The `state` stage below
// compares these with the answer a reader holds.
let appliedState = null;

/** Record `state` as applied. Called once per answer, after its document's presentation
    pass and every data subscriber it told have finished. */
export function markStateApplied(state) {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.reading, state.reading);
  appliedState = {
    reading: state.reading,
    taken: state.taken,
    lapses: activityTransitionAt(state),
  };
}

const stamp = (name) => document.body.getAttribute(PAGE_PAINT_ATTRIBUTE[name]);
// In the order a page reaches them. `held` is the `/api/state` answer a reader holds
// (`{reading, taken}`), or null for a reader holding none, which skips `state`.
/** @type {[string, (held?: {taken: number, reading: string} | null) => boolean][]} */
const READINESS = [
  ["upgraded", () => stamp("upgraded") === "1"],
  ["log", () => stamp("applied") !== null],
  [
    "state",
    (held) =>
      !held ||
      appliedState?.taken >= held.taken ||
      (appliedState?.reading === held.reading &&
        held.taken * 1000 < appliedState.lapses),
  ],
  ["presented", () => pagePresented() && applicationPresented()],
  ["arrived", () => arriving.size === 0],
  ["rendering", () => Object.values(renderingState()).every(Boolean)],
];
const READINESS_STAGES = new Set(READINESS.map(([stage]) => stage));

/** The first readiness fact this page has yet to state, or null once a reader outside
    it may read its final boxes and press its keys.

    The stages: `upgraded`; `log`, some log coverage applied; `state`, the answer the
    reader holds applied; `presented`, the initial milestone and the coordinator's
    current reading; `arrived`, nothing deferred past presentation still outstanding;
    `rendering`, no finite preparation or queued rendering update remains. A reading is a digest with no
    order, and the server may move past the answer held — a source rewritten, a claim
    aged, a neighbour started — so a page that applied an answer the server took later
    has caught up with it too. A reading names files and presence, not the activity the
    server folds from them against its clock, so an applied answer with the held
    reading has caught up only if the held one was taken before that activity could
    change; after it, the page asks again at that moment and catches up by `taken`.

    `through` names the last stage the reader needs. A test that writes behind a page
    in the middle of a gesture — a drag holding a revision back, a fold still animating
    — asks only that the page has taken the write in, which is `state`.

    Finite animation is not a stage: the render gate's `pageSettled` asks that
    separately. */
export function pageReadiness(held = null, through = "rendering") {
  if (!READINESS_STAGES.has(through))
    throw new TypeError(`no readiness stage named ${through}`);
  for (const [stage, met] of READINESS) {
    if (!met(held)) return stage;
    if (stage === through) return null;
  }
}

// The one initial turn in which box-derived page apparatus can read the complete
// authoritative layout before semantic interaction opens. Widget upgrade gives
// components enough geometry to build and paint from authored state, while presentation
// adds replay, restored chrome, and fragment reveal. Components keep observing later
// real layout changes through their ordinary ResizeObserver or layout signal; this event
// exists only to replace a provisional startup reading synchronously.
export const PRESENTATION = "lf-presentation";

// Interface derived from authored structure joins the same settlement boundary as the
// widget modules that compose it. Initial startup and an in-place version activation
// both pass here, so such a surface cannot appear after either page is already in
// front of the user.
export const PAGE_INTERFACE = "lf-page-interface";
// Prepare interface owners over the current DOM. This joins their reconciliation,
// separately from the semantic document's canonical presentation proof.
export async function settlePageInterface() {
  const pending = [];
  const present = (promise) => {
    if (!promise?.then)
      throw new TypeError("Page interface presentation must be a promise");
    pending.push(promise);
    return promise;
  };
  document.dispatchEvent(new CustomEvent(PAGE_INTERFACE, { detail: { present } }));
  // Owners can report and recover locally. An unhandled preparation failure is still
  // visible, but must not keep every generated control behind the upgrade boundary.
  for (const result of await Promise.allSettled(pending)) {
    if (result.status === "rejected")
      reportPageError(result.reason, "Page interface failed");
  }
}

// A page script's view of a widget, such as a playground's preview, which can reach the
// widget only once it has upgraded. The first connection waits for PAGE_INTERFACE and
// holds the page's presentation until `connect` has run; a reconnection runs it at once.
// `declare` runs once, before the first `connect`, for what the widget accepts once per
// lifetime; `connect(signal)` runs on each connection, and its returned cleanup runs as
// the element leaves. A later PAGE_INTERFACE, from a revision applied in place, finds
// the view already connected.
export function whileInterfaceConnected(element, { declare, connect }) {
  let declared = false;
  return whileConnected(element, (signal) => {
    let connected = false;
    let cleanup;
    const start = () => {
      if (signal.aborted || connected) return;
      if (!declared) {
        declare?.();
        declared = true;
      }
      connected = true;
      cleanup = connect(signal);
    };
    document.addEventListener(
      PAGE_INTERFACE,
      (event) =>
        /** @type {CustomEvent} */ (event).detail.present(
          Promise.resolve().then(start),
        ),
      { signal },
    );
    if (declared) start();
    return () => cleanup?.();
  });
}
