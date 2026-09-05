/* Server-projected decision state, resolved onto the browser's live DOM: which decisions
   are open, answered, or waiting on the agent, and the three lists the banner, the tray,
   and the walks read.

   The banner's Asks count is durable progress: `Asks 3/7` means three of the seven active
   Decisions are answered. `allDecisions` supplies the denominator and
   `unansweredDecisions` supplies what remains outside the numerator, so moving focus or
   walking the page changes neither number. At 7/7 the same button stays available and
   takes the positive treatment; it is both the completion signal and the route back
   through the answers.

   A request decision is answered at acceptance rather than by replayable widget state.
   Its pending lifecycle therefore leaves the reader's list immediately and hands the next
   word to the host; a terminal failure returns it, while success keeps it closed. Page
   holders scope that reading to their authored revision and frozen thread holders scope
   it to the conversation document's lifetime, exactly as the request seat does.

   A decision is answered by a verb listed in `x-awaits.answers`; do not infer that every
   state change is an answer. Two things take a decision off the reader's list, and only
   that one is an answer. The other is a conversation standing in the widget's own
   declared seat (`x-conversation`) while it waits on the agent: `seatRoot` finds a root
   anchored on the widget and nothing else, which is the anchor `renderConversations`
   collects into that seat, and `awaitsAgent` says the next word there is the agent's. So
   the banner's count and the panel's reading of the same thread cannot disagree about
   whose turn it is. Whose thread it is does not enter into it — the agent may open one in
   the seat too, and once the reader has answered there the question is with the agent
   either way. An ordinary agent reply hands the conversation back. A `response: {kind:
   version, verb: <answer>}` conversation accepts no agent reply; the agent incorporates
   it into a version or opens a separate thread for clarification. While that thread waits
   on the reader in the same seat, it carries the original response through the stop gate;
   their answer hands both threads back to the agent.

   That combined reading is what `openDecisions` returns, so the `a`/`A` walk follows the
   reader's worklist and a request the agent owes the next word on does not belong on it.
   The banner and tray instead use `allDecisions`, the current page-and-thread inventory
   that retains an answered action Decision and a request throughout its lifecycle.

   Three readings ask the other question — whether the request is *answered* — and all say
   so by emptying the seats (`answeredContext`, stated beside the shape rather than by a
   caller reaching into it, so a member derived from those conversations later cannot
   escape the emptying). An action's `requires` is one: a conversation does not answer a
   question the widget holds no state for, and refusing a pick over the reader's own
   remark would refuse them the answer they were asked for. The version-response resolve
   gate is another. Where the reader is standing preserves that reading first, then widens
   through `allDecisions` for answered-review routes; `decisions/view.js` owns that
   reading (`standingIn`). Frozen
   thread markup seats no conversation of its own, so only an action answers there. A
   `rollup` instance is an aggregate-only owner: it awaits when any nearest local decision
   or child roll-up awaits, but it never enters the visible list. The standing projection
   keeps every open local member; an enclosing `x-decision` replaces that member only on
   the visible/navigation surface. `actionAvailable` still queries whether the source or
   an ancestor's aggregate is open. A module reading `openDecisions()` calls
   `decisionSource()` when it needs the actionable widget rather than the reader-facing
   region. */

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

/* Server-projected decision state, resolved onto the browser's live DOM. */
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
