/* This module owns request discovery, decision folding, and the semantic Decision
 * subscription: server-projected decision state resolved onto the live DOM. */
import { watchProjection } from "../projection-watch.js";

let publishedDecisionModel;
export const answeredContext = (...args) =>
  publishedDecisionModel.answeredContext(...args);
export const decisionSource = (...args) =>
  publishedDecisionModel.decisionSource(...args);
export const allDecisions = (...args) => publishedDecisionModel.allDecisions(...args);
export const openDecisions = (...args) => publishedDecisionModel.openDecisions(...args);
export const watchDecisions = (...args) =>
  publishedDecisionModel.watchDecisions(...args);

export function createDecisionModel({
  authoredParentOf,
  closestAcross,
  elementById,
  pagePresented,
  registry,
  runtime,
  stateProjection,
  tagsDeclaring,
}) {
  const decisionEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
  const requestDecisionEntry = (el) => {
    const request = registry[el.tagName.toLowerCase()]?.["x-request"];
    return request?.decision ? request : null;
  };
  const decisionSourceEntry = (el) => decisionEntry(el) ?? requestDecisionEntry(el);
  const decisionTags = () =>
    tagsDeclaring((entry) => entry["x-awaits"] || entry["x-request"]?.decision);
  const decisionSurfaceTags = () => tagsDeclaring((entry) => entry["x-decision"]);

  function decisionSurface(el) {
    const tags = decisionSurfaceTags();
    return (tags.length && closestAcross(el, tags.join(","))) || el;
  }

  function decisionSource(el) {
    if (decisionSourceEntry(el)) return el;
    const tags = decisionTags();
    if (!tags.length || !registry[el.localName]?.["x-decision"]) return el;
    return (
      [...el.querySelectorAll(tags.join(","))].find(
        (candidate) => decisionSurface(candidate) === el,
      ) ?? el
    );
  }

  function positionedParents(projection) {
    const parents = new Map();
    for (const { unit, e, spec } of projection.desired.values()) {
      if (spec.record?.kind !== "position") continue;
      const parent = elementById(e.detail[spec.record.value]);
      const moved = elementById(unit);
      let holder = parent;
      while (holder && !registry[holder.localName])
        holder = authoredParentOf(holder) ?? holder.parentElement;
      if (
        parent &&
        moved &&
        holder &&
        (registry[moved.localName]?.["x-parent"] ?? []).includes(holder.localName)
      )
        parents.set(unit, parent);
    }
    return parents;
  }

  const awaitingValues = (answered) => ({
    ...(answered
      ? runtime.view?.document?.decisions?.unanswered_awaiting
      : runtime.view?.document?.decisions?.awaiting),
    ...(runtime.browser?.conversation?.decisions?.awaiting ?? {}),
  });

  function context(answered = false) {
    const projection = stateProjection();
    return {
      awaiting: awaitingValues(answered),
      positionedParents: positionedParents(projection),
      projection,
    };
  }

  const answeredContext = () => context(true);
  const isAwaiting = (el, reading) => Boolean(reading.awaiting[el.id]);
  const projectedParent = (el, reading) =>
    (el.id && reading.positionedParents.get(el.id)) ??
    authoredParentOf(el) ??
    el.parentElement;

  function decisions(kind) {
    if (!pagePresented()) return [];
    const documentDecisions = runtime.view?.document?.decisions?.[kind] ?? [];
    const conversationDecisions =
      runtime.browser?.conversation?.decisions?.[kind] ?? [];
    const elements = [...documentDecisions, ...conversationDecisions]
      .map((decision) => elementById(decision.id))
      .filter(Boolean);
    return [...new Set(elements)].sort((left, right) => {
      if (left === right) return 0;
      return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING
        ? -1
        : 1;
    });
  }

  const allDecisions = () => decisions("all");
  const openDecisions = () => decisions("reader");
  const unansweredDecisions = () => decisions("unanswered");

  // A package subscribes to the semantic projection, never to the transport's broad
  // invalidation event. The first reading is synchronous, which lets a connected
  // widget paint one complete state without a separate setup path. The owner exists
  // only to bind lifetime; the reading stays page-wide because a command hub observes
  // decisions elsewhere in the document.
  function watchDecisions(owner, callback) {
    if (typeof callback !== "function")
      throw new TypeError("A decision watcher needs a callback");
    return watchProjection(owner, () => callback(openDecisions()));
  }

  const model = {
    allDecisions,
    answeredContext,
    decisionEntry,
    decisionSource,
    isAwaiting,
    openDecisions,
    projectedParent,
    unansweredDecisions,
    watchDecisions,
  };
  publishedDecisionModel = model;
  return model;
}
