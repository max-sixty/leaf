/* The marks Leaf paints on every widget, whatever the widget's own module renders.

   Each widget's module renders its own state. This module's `projection:chrome` region
   paints the marks the layer derives for every widget: the restated mark, the
   user-override and reported origin marks (`paintStateOrigins`), and each widget's
   settlement (`paintSettlements`). It also stamps `document.body` with how many log
   events the projection covers, once every widget they touch has painted; a waiter
   outside the page reads that stamp to know the page has caught up. The region paints
   first in each pass (`PRESENTATION_ORDER.projection`), because the thread then
   resolves its passages over the words it writes into authored elements. */
import { authoredStates } from "./authored.js";
import { projectionOrigins } from "./model.js";
import {
  applicationPresenter,
  applicationState,
  projectionRegionsPresented,
  watchPresentation,
  PRESENTATION_ORDER,
  readPart,
} from "../semantic-state.js";
import { decisionFor } from "../registry.js";
import { widgetElement } from "../widget-descriptors.js";
import {
  authored,
  elementById,
  inChrome,
  pageQueryAll,
  renderRetired,
} from "../passages.js";
import { isPagePaint, renderQuiet } from "../declared-words.js";
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

// A widget whose tag has a deciding verb (`decisionFor`) is settled when that verb's
// current outcome is one the registry says retires it. This marks every such widget,
// whether or not its module renders anything. A module that animates its own settling,
// as lf-suggestion does, has already run it in the publication before this writes the
// same mark. A widget in a message's frozen markup is marked before the thread mounts
// it, so it joins the panel settled and the thread's passages skip what it retired.
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

const answered = readPart((root) => root.authoritative !== null);
const phase = readPart((root) => root.phase);
const currentProjection = readPart((root) => root.effective.projection);
const widgetStates = readPart((root) => root.effective.widgets);

export function createProjectionPresentation() {
  // The region claims a paint synchronously as each publication is made, before the
  // coordinator seals which regions the pass must paint. So its previous paint cannot
  // stand for a new reading while frozen widget markup is still joining the document;
  // the pass paints it afterwards. Before the server's first answer `reading` returns
  // null, and there is nothing to paint. The coverage stamp below follows presentation
  // (`watchPresentation`) rather than this region.
  applicationPresenter({
    region: "projection:chrome",
    order: PRESENTATION_ORDER.projection,
    reading: () => (answered() ? true : null),
    paint: paintReading,
  });

  // The stamp keeps the last complete coverage. It waits only for the widgets whose
  // events it covers to paint, so another widget's preparation cannot hold it back.
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

  function presentCurrent() {
    const projection = currentProjection();
    // Until the server's first state or the offline fallback arrives, the page cannot
    // know which actions are available, so there is no projection to paint; widget
    // controllers already show each widget's authored state.
    if (phase() === "waiting" || !answered()) {
      // Returning here lets document installation finish and start the state feed. The
      // ready or offline publication that follows claims a new paint before any
      // widget's paint counts as current.
      return projection;
    }
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? [])
        keeps(elementById(id), PAGE_PAINT_ATTRIBUTE.restated, "1");
    paintSettlements(widgetStates());
    const originTargets = paintStateOrigins(projection);
    renderQuiet(document.body, originTargets);
    return projection;
  }

  // If painting throws, the region stays unpainted and the error reaches the
  // application's error boundary; the next claim tries the current state again.
  function paintReading() {
    return presentCurrent();
  }

  // `present` is not returned. The region repaints from its own subscription above, or
  // from `presentDocument` when a caller has changed the document. Handing one caller
  // a third way in is how the ask inventory once got left out of a document-wide
  // repaint.
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
