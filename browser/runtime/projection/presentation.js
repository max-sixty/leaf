/* The marks Leaf paints on every widget, whatever the widget's own module renders.

   Each widget's module renders its own state. This module's `projection:chrome` region
   paints the marks the layer derives for every widget: the restated mark, the
   user-override and reported origin marks (`paintStateOrigins`), and each widget's
   settlement (`paintSettlements`). It also stamps `document.body` with how many log
   events the projection covers, once every widget they touch has painted; a waiter
   outside the page reads that stamp to know the page has caught up. The region paints
   after native widget DOM commits (`PRESENTATION_DOM.widgets`); threads then
   resolve their passages over the words it writes into authored elements. */
import { authoredStates } from "./authored.js";
import { projectionOrigins } from "./model.js";
import {
  applicationPresenter,
  applicationState,
  projectionRegionsPresented,
  watchPresentation,
  PRESENTATION_DOM,
  readPart,
} from "../semantic-state.js";
import { decisionFor } from "../registry.js";
import { addressableAt } from "../thread/messages.js";
import { authored, elementById, renderRetired } from "../passages.js";
import { isPagePaint, sayQuietFacts } from "../declared-words.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { keeps } from "../lib/keeps.js";
import { inChrome } from "../ui-marks.js";

// Paint each unit's origin mark, and return every element that wears one or just lost
// one. `marked` holds the elements the last paint marked with each origin attribute.
// This region is the attribute's only writer, so a paint takes the mark off the
// elements it no longer wants from there rather than finding them by a query of the
// whole page.
/** @param {import("../../types/domain.js").Projection} projection
 * @param {Map<string, Set<Element>>} marked */
function paintStateOrigins(projection, marked) {
  /** @type {Set<Element>} */
  const userOverride = new Set();
  /** @type {Set<Element>} */
  const reported = new Set();
  const marks = new Map([
    [PAGE_PAINT_ATTRIBUTE.userOverride, userOverride],
    [PAGE_PAINT_ATTRIBUTE.reported, reported],
  ]);
  for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
    if (origin === "restated") continue;
    const target = elementById(unit);
    if (!target || inChrome(target)) continue;
    (origin === "user" ? userOverride : reported).add(target);
  }
  const touched = new Set();
  for (const [attr, wanted] of marks) {
    for (const target of marked.get(attr) ?? []) {
      touched.add(target);
      if (!wanted.has(target)) keeps(target, attr, null);
    }
    for (const target of wanted) {
      touched.add(target);
      keeps(target, attr, "1");
    }
    marked.set(attr, wanted);
  }
  return touched;
}

// A widget whose tag has a deciding verb (`decisionFor`) is settled when that verb's
// current outcome is one the registry says retires it. This marks every such widget,
// whether or not its module renders anything. A module that animates its own settling,
// as lf-suggestion does, has already run it in the publication before this writes the
// same mark. A widget in a message's markup is marked before the thread mounts
// it, so it joins the panel settled and the thread's passages skip what it retired.
/** @param {import("../framework/snapshot.js").Immutable<ReturnType<typeof import("./model.js").foldWidgetStates>>} widgets */
function paintSettlements(widgets) {
  for (const [widgetId, { state }] of widgets) {
    const owner = addressableAt(widgetId);
    const decision = owner && decisionFor(owner.localName);
    if (!decision) continue;
    const wanted = state[decision.verb]?.detail?.outcome;
    const outcome =
      Object.keys(decision.retires).find((candidate) => candidate === wanted) ?? null;
    keeps(owner, PAGE_PAINT_ATTRIBUTE.settlement, outcome);
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
  // stand for a new reading while thread widget markup is still joining the document;
  // the pass paints it afterwards. Before the server's first answer `reading` returns
  // null, and there is nothing to paint. The coverage stamp below follows presentation
  // (`watchPresentation`) rather than this region.
  applicationPresenter({
    region: "projection:chrome",
    after: PRESENTATION_DOM.widgets,
    reading: () => (answered() ? true : null),
    paint: paintReading,
  });

  // The stamp keeps the last complete coverage. It waits only for the widgets whose
  // events it covers to paint, so another widget's preparation cannot hold it back.
  // A live revision keeps that reading until its next projection completes. Current
  // document readiness belongs to the presentation coordinator, whose document:patch
  // region holds the installation, rather than to erasing and restoring this count.
  // The fold keeps the coverage records while no event joins the log (`kept.js`), so
  // once the stamp covers them a presentation that moves no widget event, such as a
  // thread's repaint, returns without walking the log again.
  /** @type {unknown} */
  let stamped = null;
  const coverage = () => {
    const root = applicationState.read();
    const records = root.effective.coverage;
    if (
      records === stamped ||
      root.phase === "waiting" ||
      root.authoritative === null ||
      !projectionRegionsPresented([])
    )
      return;
    const projection = root.effective.projection;
    const ready = records.every((record) => {
      if (record.coordinate === null) return true;
      const e = record.event;
      const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
      return (
        !target ||
        target.terminal ||
        projectionRegionsPresented(record.coordinate.slice(0, 1))
      );
    });
    if (!ready) return;
    keeps(document.body, PAGE_PAINT_ATTRIBUTE.applied, String(records.length));
    stamped = records;
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

  /** @type {Map<string, Set<Element>>} */
  const originMarked = new Map();
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
    // Every element this paint marks, or takes a mark off, says its marks again quietly.
    /** @type {Set<Element>} */
    const marked = new Set();
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? []) {
        const target = elementById(id);
        if (!target) continue;
        keeps(target, PAGE_PAINT_ATTRIBUTE.restated, "1");
        marked.add(target);
      }
    paintSettlements(widgetStates());
    for (const target of paintStateOrigins(projection, originMarked))
      marked.add(target);
    sayQuietFacts(marked);
    return projection;
  }

  // If painting throws, the region stays unpainted and the error reaches the
  // application's error boundary; the next claim tries the current state again.
  function paintReading() {
    return presentCurrent();
  }

  // `present` is not returned. The region repaints from its own subscription above, or
  // from `presentDocument` when a caller has changed the document. Handing one caller
  // a third way in can leave an owner, such as the obligation inventory, out of a
  // document-wide repaint.
}

/** @param {Element} root */
export function shallowSigs(root) {
  const sigs = new Map();
  /** @type {Map<Element | null, Map<Element, number>>} */
  const siblingPositions = new Map();
  /** @param {Element} node */
  const isAuthored = (node) => Boolean(node.id) && authored(node)(node);
  for (const node of [root, ...root.querySelectorAll("[id]")]) {
    if (!isAuthored(node)) continue;
    const attrs = Object.fromEntries(
      [...node.attributes]
        .filter((attribute) => !isPagePaint(attribute.name))
        .map((attribute) => ({ name: attribute.name, value: attribute.value }))
        .sort((left, right) => left.name.localeCompare(right.name))
        .map(({ name, value }) => [name, value]),
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
