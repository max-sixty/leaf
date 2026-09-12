/* DOM adaptation and commit for the semantic action/report projection.

   The desired record fold and the DOM commit checkpoint are separate readings. The
   former changes as soon as a local action is staged or an authoritative view arrives;
   the latter changes only after the current widget nodes accepted a complete render.
   One presentation instance owns the commit maps, optimistic staging, coordinate
   proof, release decisions, authored-page reset, and drag deferral observer. It adapts
   one complete publisher snapshot; only DOM signature/read adapters remain direct
   exports. */
import { authoredStates } from "./authored.js";
import { projectionOrigins } from "./model.js";
import { currentProjection, setProjectionDeferred } from "./state.js";
import { applicationState } from "../semantic-state.js";
import { stateSpecs } from "../registry.js";
import { runtime } from "../context.js";
import {
  authored,
  elementById,
  inChrome,
  pageQueryAll,
  renderRetired,
  settlementSlots,
} from "../passages.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  PAGE_PAINT_ATTRIBUTES,
  renderQuiet,
} from "../presentation.js";
import { reportPageError } from "../layer-client.js";
import { failSoft } from "../widget-upgrade.js";

const { registry } = runtime;

const committedEvent = (commit) => commit?.entry?.e.id ?? null;

function renderSettlement(widget, state) {
  const outcomes = settlementSlots()[widget.localName];
  if (!outcomes) return;
  const spec = registry[widget.localName]["x-state"][Object.keys(outcomes)[0]];
  const outcome = state[spec.facet].action;
  if (outcomes[outcome]) widget.setAttribute("data-lf-state", outcome);
  else widget.removeAttribute("data-lf-state");
  renderRetired(widget);
}

function paintStateOrigins(projection) {
  const marks = new Map(
    [PAGE_PAINT_ATTRIBUTE.readerOverride, PAGE_PAINT_ATTRIBUTE.reported].map((attr) => [
      attr,
      new Set(),
    ]),
  );
  for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
    if (origin === "restated") continue;
    const target = elementById(unit);
    if (!target || inChrome(target)) continue;
    const attr =
      origin === "reader"
        ? PAGE_PAINT_ATTRIBUTE.readerOverride
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
      if (target.getAttribute(attr) !== "1") target.setAttribute(attr, "1");
    }
  }
  return touched;
}

export function createProjectionPresentation({ onDeferredReady, onDomIntroduced }) {
  const committedProjection = new Map();

  const committedWidgets = new Map();

  let projectionDragObserver = null;

  function coordinateProjectionCommitted(projection, entry) {
    const desired = projection.desired.get(entry.coordinate);
    const commit = committedProjection.get(entry.coordinate);
    return (
      commit?.widget === elementById(entry.e.widget) &&
      commit.unit === elementById(entry.unit) &&
      committedEvent(commit) === (desired?.e.id ?? null)
    );
  }

  function projectionCommitted(projection, event) {
    const entry = projection.classified.get(event.id);
    return Boolean(
      entry && (entry.terminal || coordinateProjectionCommitted(projection, entry)),
    );
  }

  function localCoordinateCommitted(projection, entry) {
    const local = entry.projection;
    if (!local) return true;
    const widget = elementById(local.e.widget);
    if (!widget) return true;
    const desired = projection.desired.get(local.coordinate) ?? null;
    const commit = committedProjection.get(local.coordinate);
    return (
      commit?.widget === widget &&
      commit.unit === elementById(local.unit) &&
      committedEvent(commit) === (desired?.e.id ?? null)
    );
  }

  function releasableEntries(entries, projection = currentProjection()) {
    return entries.filter((entry) => {
      if (!entry.answered || entry.event.kind !== "action") return false;
      return entry.rejected
        ? localCoordinateCommitted(projection, entry)
        : Boolean(
            entry.presented &&
            entry.readEvent &&
            projectionCommitted(projection, entry.readEvent),
          );
    });
  }

  // Every action reaches the send door after its widget has painted the semantic
  // outcome. Give recorded and recordless actions the same local coordinate so later
  // gestures and all projection consumers read that outcome before delivery settles.
  // An exact undo uses the target's same entry rather than a reverse action or DOM
  // snapshot; the pure fold derives whichever prior value still stands.
  function stageOptimistic(entry) {
    const e = entry.event;
    const local = entry.projection;
    if (!local) return false;
    if (e.kind === "undo") {
      committedWidgets.delete(local.target.e.widget);
      return true;
    }
    const widget = elementById(e.widget);
    committedWidgets.delete(e.widget);
    committedProjection.set(local.coordinate, {
      widgetId: e.widget,
      widget,
      unit: elementById(local.unit),
      entry: local,
    });
    return true;
  }

  function projectionCoverage(projection, coverage) {
    let covered = 0;
    for (const record of coverage ?? []) {
      if (record.coordinate === null) {
        covered += 1;
        continue;
      }
      const e = record.event;
      const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
      if (!target || target.terminal || projectionCommitted(projection, target.e))
        covered += 1;
    }
    return covered;
  }

  function resetAuthoredPage() {
    const pageOwners = new Set();
    for (const { tag } of stateSpecs())
      for (const widget of pageQueryAll(tag))
        if (widget.id && !inChrome(widget)) pageOwners.add(widget.id);
    const dropCoordinates = (records) => {
      for (const coordinate of records.keys()) {
        const [owner] = JSON.parse(coordinate);
        if (pageOwners.has(owner)) records.delete(coordinate);
      }
    };
    dropCoordinates(committedProjection);
    applicationState.forgetAuthored(pageOwners);
    for (const owner of pageOwners) {
      committedWidgets.delete(owner);
    }
    document.body.removeAttribute(PAGE_PAINT_ATTRIBUTE.applied);
  }

  function watchProjectionDrag() {
    if (projectionDragObserver) return;
    projectionDragObserver = new MutationObserver(() => {
      if (document.querySelector(".lf-dragging")) return;
      projectionDragObserver.disconnect();
      projectionDragObserver = null;
      onDeferredReady();
    });
    projectionDragObserver.observe(document.body, {
      attributes: true,
      subtree: true,
      attributeFilter: ["class"],
    });
  }

  function presentCurrent(snapshot) {
    const projection = snapshot.effective.projection;
    // Before the first state or the offline fallback, authored capture has completed
    // but the application still cannot know whether an action is available. Surface
    // registration may invalidate the DOM in that interval. Publish the desired record
    // for readers, but leave the widget uncommitted so ready/offline presentation must
    // render it instead of treating this provisional authored state as current.
    if (snapshot.phase === "waiting") {
      setProjectionDeferred(true);
      return projection;
    }
    if (document.querySelector(".lf-dragging")) {
      setProjectionDeferred(true);
      watchProjectionDrag();
      return projection;
    }
    projectionDragObserver?.disconnect();
    projectionDragObserver = null;
    setProjectionDeferred(false);
    let painted = false;
    const started = new Set(document.getAnimations());
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? [])
        elementById(id)?.setAttribute(PAGE_PAINT_ATTRIBUTE.restated, "1");
    for (const [widgetId, { state, entries }] of snapshot.effective.widgets) {
      const widget = elementById(widgetId);
      if (!widget) continue;
      const key = JSON.stringify(state);
      const commit = committedWidgets.get(widgetId);
      const unitsChanged = entries.some(
        ({ coordinate, unit }) =>
          committedProjection.get(coordinate)?.unit !== elementById(unit),
      );
      if (commit?.widget !== widget || commit.key !== key || unitsChanged) {
        try {
          if (widget.renderState?.(state) === false) {
            setProjectionDeferred(true);
            continue;
          }
          renderSettlement(widget, state);
        } catch (error) {
          reportPageError(
            `<${widget.localName}> renderState threw: ${error?.message ?? error}`,
          );
          failSoft(widget, error);
          renderSettlement(widget, state);
        }
        committedWidgets.set(widgetId, { widget, key });
        painted = true;
      }
      const coordinates = new Map();
      for (const entry of projection.classified.values())
        if (!entry.terminal && entry.e.widget === widgetId)
          coordinates.set(entry.coordinate, entry);
      for (const entry of entries) coordinates.set(entry.coordinate, entry);
      for (const [coordinate, commitEntry] of committedProjection)
        if (commitEntry.widgetId === widgetId && commitEntry.entry)
          coordinates.set(coordinate, commitEntry.entry);
      for (const [coordinate, sample] of coordinates)
        committedProjection.set(coordinate, {
          widgetId,
          widget,
          unit: elementById(sample.unit),
          entry: projection.desired.get(coordinate) ?? null,
        });
    }
    for (const [coordinate, commit] of committedProjection)
      if (!elementById(commit.widgetId)) committedProjection.delete(coordinate);
    const originTargets = paintStateOrigins(projection);
    renderQuiet(document.body, originTargets);
    document.body.setAttribute(
      PAGE_PAINT_ATTRIBUTE.applied,
      String(
        projectionCoverage(
          projection,
          snapshot.authoritative?.browser.views[String(snapshot.document.revision)]
            ?.coverage,
        ),
      ),
    );
    if (painted)
      Promise.allSettled(
        document
          .getAnimations()
          .filter((animation) => !started.has(animation))
          .map((animation) => animation.finished),
      ).then(onDomIntroduced);
    return projection;
  }

  function present(snapshot) {
    const prior = runtime.restoringState;
    if (snapshot.unresolved.some((entry) => entry.rejected && entry.projection))
      runtime.restoringState = true;
    try {
      return presentCurrent(snapshot);
    } finally {
      runtime.restoringState = prior;
    }
  }

  return {
    present,
    stageOptimistic,
    releasableEntries,
    resetAuthoredPage,
    projectionCommitted,
    coordinateProjectionCommitted,
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
        .filter((attribute) => !PAGE_PAINT_ATTRIBUTES.has(attribute.name))
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
