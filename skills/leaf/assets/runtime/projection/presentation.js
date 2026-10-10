/* Coordinate, provenance, settlement, and chrome commit for the semantic projection.

   Widget controllers run each module's own rendering of total state and own its
   presentation proof. This adapter paints what the layer derives for every widget,
   whether or not its module subscribed: the restated and origin marks and each
   holder's settlement. Coverage and update narration consume the same coordinator
   proof as widget rendering, asynchronous preparation, and pending release. It is an
   epoch presenter and paints first
   in the pass, because the words it materializes inside authored elements are nodes
   the thread then resolves its passages over. Its one document-wide drag gate
   withholds that global projection work while the gesture's own controller holds its
   local reading; the region stays open until the gesture ends and a fresh claim
   supersedes it. */
import { authoredStates } from "./authored.js";
import { projectionOrigins } from "./model.js";
import { projectionDeferred, setProjectionDeferred } from "./state.js";
import {
  applicationPresenter,
  applicationState,
  projectionRegionsPresented,
  watchPresentation,
  PRESENTATION_HELD,
  PRESENTATION_ORDER,
} from "../semantic-state.js";
import { runtime } from "../context.js";
import { decisionFor } from "../registry.js";
import { dragHeld, watchDragRelease } from "../widget-elements.js";
import { widgetElement } from "../widget-descriptors.js";
import {
  authored,
  elementById,
  inChrome,
  pageQueryAll,
  renderRetired,
} from "../passages.js";
import { isPagePaint, renderQuiet } from "../presentation.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { keeps } from "../keeps.js";

function paintStateOrigins(projection) {
  const marks = new Map(
    [PAGE_PAINT_ATTRIBUTE.userOverride, PAGE_PAINT_ATTRIBUTE.reported].map((attr) => [
      attr,
      new Set(),
    ]),
  );
  for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
    if (origin === "restated") continue;
    const target = elementById(unit);
    if (!target || inChrome(target)) continue;
    const attr =
      origin === "user"
        ? PAGE_PAINT_ATTRIBUTE.userOverride
        : PAGE_PAINT_ATTRIBUTE.reported;
    marks.get(attr).add(target);
  }
  const touched = new Set();
  for (const [attr, wanted] of marks) {
    for (const target of pageQueryAll(`[${attr}]`)) {
      touched.add(target);
      if (!wanted.has(target)) target.removeAttribute(attr);
    }
    for (const target of wanted) {
      touched.add(target);
      keeps(target, attr, "1");
    }
  }
  return touched;
}

// A holder's settlement is the registry's slot relation read against its deciding
// verb's standing outcome, so the layer paints it for every holder whether or not its
// module renders anything. A module with a choreography of its own (lf-suggestion's
// fold) has already run it in the publication, before this pass writes the same mark.
// A holder in a message's frozen markup is painted before the thread mounts it, so it
// joins the panel settled and the thread's passages skip what it retired.
function paintSettlements(widgets) {
  for (const [widgetId, { state }] of widgets) {
    const owner = widgetElement(widgetId);
    const decision = owner && decisionFor(owner.localName);
    if (!decision) continue;
    const outcome = state[decision.verb]?.detail?.outcome ?? null;
    keeps(
      owner,
      PAGE_PAINT_ATTRIBUTE.settlement,
      decision.retires[outcome] ? outcome : null,
    );
    renderRetired(owner, outcome);
  }
}

export function createProjectionPresentation({ onDeferredReady }) {
  let stopWatchingDrag = null;

  const presenter = applicationPresenter({
    region: "projection:chrome",
    order: PRESENTATION_ORDER.projection,
    current: () => {
      const root = applicationState.read();
      return root.authoritative === null ? null : root.effective.projection;
    },
    paint: () => paintReading(applicationState.read()),
  });

  // A semantic publication precedes the imperative adapter that paints it. The claim
  // happens in the publisher's synchronous subscription phase, before it seals
  // presentation membership, so an inherited commit cannot acknowledge the new reading
  // while frozen widget markup is still joining the document; the pass paints it after.
  // Every epoch owes one: the coverage stamp reads the server's view of the log beside
  // the fold, so an unchanged fold is not an unchanged chrome reading.
  applicationState.select((snapshot) => snapshot.semanticEpoch).subscribe(present);

  // The stamp retains the last complete coverage. Only the widgets whose events
  // it covers owe proof, so unrelated preparation cannot hold this log reading.
  const coverage = () => {
    const root = applicationState.read();
    if (
      root.phase === "waiting" ||
      root.authoritative === null ||
      !projectionRegionsPresented([])
    )
      return;
    const projection = root.effective.projection;
    const records = root.effective.view?.coverage ?? [];
    const ready = records.every((record) => {
      if (record.coordinate === null) return true;
      const e = record.event;
      const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
      return (
        !target || target.terminal || projectionRegionsPresented([target.e.widget])
      );
    });
    if (ready)
      keeps(document.body, PAGE_PAINT_ATTRIBUTE.applied, String(records.length));
  };
  let coverageQueued = false;
  const updateCoverage = () => {
    if (coverageQueued) return;
    coverageQueued = true;
    queueMicrotask(() => {
      coverageQueued = false;
      coverage();
    });
  };
  watchPresentation(updateCoverage);

  // The coverage stamp says how much of the log the last complete projection covered,
  // and it is what a waiter outside the page reads to know the page has caught up. A
  // revision arriving in this document has not been projected at all yet, so the stamp
  // describes a reading nobody can still be looking at.
  const retireProjectionCoverage = () =>
    document.body.removeAttribute(PAGE_PAINT_ATTRIBUTE.applied);

  // A drag holds the projection until the last one ends (widget-elements.js).
  function watchProjectionDrag() {
    stopWatchingDrag ??= watchDragRelease(() => {
      unwatchProjectionDrag();
      onDeferredReady();
    });
  }

  function unwatchProjectionDrag() {
    stopWatchingDrag?.();
    stopWatchingDrag = null;
  }

  function presentCurrent(snapshot) {
    const projection = snapshot.effective.projection;
    // Before the first state or the offline fallback, authored capture has completed
    // but the application still cannot know whether an action is available. Controllers
    // independently present any complete authored widget state; this adapter has no
    // authoritative projection coordinates or chrome to commit yet.
    if (snapshot.phase === "waiting" || snapshot.authoritative === null) {
      // This provisional epoch has no authoritative projection to withhold. Settling
      // its chrome ticket lets document installation finish and start the state feed;
      // adoption publishes a ready/offline epoch and claims a fresh ticket before any
      // semantic or widget commit can become current.
      setProjectionDeferred(false);
      return projection;
    }
    if (dragHeld()) {
      setProjectionDeferred(true);
      watchProjectionDrag();
      return projection;
    }
    unwatchProjectionDrag();
    setProjectionDeferred(false);
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? [])
        keeps(elementById(id), PAGE_PAINT_ATTRIBUTE.restated, "1");
    paintSettlements(snapshot.effective.widgets);
    const originTargets = paintStateOrigins(projection);
    renderQuiet(document.body, originTargets);
    return projection;
  }

  // A throw leaves this region pending and preserves the application error boundary;
  // the next claim supersedes the hold and tries the current semantic root again.
  function paintReading(snapshot) {
    const prior = runtime.restoringState;
    if (
      snapshot.unresolved.some((entry) => entry.state === "refused" && entry.projection)
    )
      runtime.restoringState = true;
    try {
      const projection = presentCurrent(snapshot);
      // A drag holds this region open at the user's own gesture rather than
      // committing a document-wide reading their own controller has not taken yet.
      return projectionDeferred() ? PRESENTATION_HELD : projection;
    } finally {
      runtime.restoringState = prior;
    }
  }

  function present() {
    return presenter.present();
  }

  // `present` stays in here. The region has two ways in — its own subscription above,
  // and `presentDocument` for a caller that changed the document and has no business
  // knowing which regions are alive. A third, handed to one caller, is how the Question
  // inventory came to be left out of a document-wide repaint.
  return {
    retireProjectionCoverage,
  };
}

export function shallowSigs(root) {
  const sigs = new Map();
  const siblingPositions = new Map();
  const isAuthored = (node) => Boolean(node.id) && authored(node)(node);
  for (const node of [root, ...root.querySelectorAll("[id]")]) {
    if (!isAuthored(node)) continue;
    const attrs = Object.fromEntries(
      [...node.attributes]
        .filter((attribute) => !isPagePaint(attribute.name))
        .map((attribute) => [attribute.name, attribute.value])
        .sort(([left], [right]) => left.localeCompare(right)),
    );
    const parent = node.parentElement;
    let positions = siblingPositions.get(parent);
    if (!positions) {
      positions = new Map();
      for (const sibling of parent?.children ?? [])
        if (isAuthored(sibling)) positions.set(sibling, positions.size);
      siblingPositions.set(parent, positions);
    }
    sigs.set(
      node.id,
      JSON.stringify({
        tag: node.tagName,
        attrs,
        parent: parent && isAuthored(parent) ? parent.id : "",
        index: positions.get(node) ?? -1,
      }),
    );
  }
  return sigs;
}
