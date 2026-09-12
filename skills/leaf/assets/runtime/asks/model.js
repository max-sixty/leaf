/* Server-projected ask state plus the canonical action projection, resolved onto the
   browser's live DOM: which asks
   are open, answered, or waiting on the agent, and the three lists the banner, the tray,
   and the walks read.

   The banner's Asks count is effective progress: `Asks 3/7` means three of the seven active
   Asks are answered, including a pending answer or withdrawal the reader can already
   see.
   `allAsks` supplies the denominator and
   `unansweredAsks` supplies what remains outside the numerator, so moving focus or
   walking the page changes neither number. At 7/7 the same button stays available and
   takes the positive treatment; it is both the completion signal and the route back
   through the answers.

   A request ask is answered at acceptance rather than by replayable widget state.
   Its pending lifecycle therefore leaves the reader's list immediately and hands the next
   word to the host; a terminal failure returns it, while success keeps it closed. Page
   holders scope that reading to their authored revision and frozen thread holders scope
   it to the conversation document's lifetime, exactly as the request seat does.

   An Ask is answered by a verb listed in `x-awaits.answers`; do not infer that every
   state change is an answer. Two things take an ask off the reader's list, and only
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

   That combined reading is what `openAsks` returns, so the `a`/`A` walk follows the
   reader's worklist and a request the agent owes the next word on does not belong on it.
   The banner and tray instead use `allAsks`, the current page-and-thread inventory
   that retains an answered action Ask and a request throughout its lifecycle.

   The counter, tray, walk, action availability, and approval gate all read the same
   effective projection. Request Asks retain their durable lifecycle. An action Ask
   reflects the pending result the page has already drawn; refusal removes that winner
   and restores the authoritative reading.

   Three readings ask the other question — whether the request is *answered* — and all say
   so by emptying the seats (`answeredContext`, stated beside the shape rather than by a
   caller reaching into it, so a member derived from those conversations later cannot
   escape the emptying). An action's `requires` is one: a conversation does not answer a
   question the widget holds no state for, and refusing a pick over the reader's own
   remark would refuse them the answer they were asked for. The version-response resolve
   gate is another. Where the reader is standing preserves that reading first, then widens
   through `allAsks` for answered-review routes; `asks/view.js` owns that
   reading (`standingIn`). Frozen
   thread markup seats no conversation of its own, so only an action answers there. A
   `rollup` instance is an aggregate-only owner: it awaits when any nearest local ask
   or child roll-up awaits, but it never enters the visible list. The standing projection
   keeps every open local member; an enclosing `x-ask-surface` replaces that member only on
   the visible/navigation surface. A controller command entry still queries whether the
   source or an ancestor's aggregate is open. A module reading `openAsks()` calls
   `askSource()` when it needs the actionable widget rather than the reader-facing
   region. A pending gesture re-folds its owner's declared answer and completion
   predicate locally; refusal removes that overlay and restores the authoritative Ask. */

import { watchProjection } from "../projection-watch.js";
import { registry, tagsDeclaring } from "../registry.js";
import { closestAcross, elementById, inChrome } from "../passages.js";
import { runtime } from "../context.js";
import { pagePresented } from "../presentation.js";
import {
  authoredFacet,
  authoredParents,
  stateCoordinate,
} from "../projection/authored.js";
import { currentProjection, projectionDeferred } from "../projection/state.js";

/* Effective ask state, resolved onto the browser's live DOM. */
const authoredParentOf = (node) => authoredParents.get(node);

export const askEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
const requestAskEntry = (el) => {
  const request = registry[el.tagName.toLowerCase()]?.["x-request"];
  return request?.ask ? request : null;
};
const askSourceEntry = (el) => askEntry(el) ?? requestAskEntry(el);
const askTags = () =>
  tagsDeclaring((entry) => entry["x-awaits"] || entry["x-request"]?.ask);
const askSurfaceTags = () => tagsDeclaring((entry) => entry["x-ask-surface"]);

function askSurface(el) {
  const tags = askSurfaceTags();
  return (tags.length && closestAcross(el, tags.join(","))) || el;
}

export function askSource(el) {
  if (askSourceEntry(el)) return el;
  const tags = askTags();
  if (!tags.length || !registry[el.localName]?.["x-ask-surface"]) return el;
  return (
    [...el.querySelectorAll(tags.join(","))].find(
      (candidate) => askSurface(candidate) === el,
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
      (registry[moved.localName]?.["x-owners"] ?? []).includes(holder.localName)
    )
      parents.set(unit, parent);
  }
  return parents;
}

const awaitingValues = (answered) => ({
  ...(answered
    ? runtime.view?.document?.asks?.unanswered_awaiting
    : runtime.view?.document?.asks?.awaiting),
  ...(runtime.browser?.conversation?.asks?.awaiting ?? {}),
});

const attributeConditionHolds = (element, when = {}) =>
  Object.entries(when).every(([attribute, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? element.hasAttribute(attribute) === value
        : element.getAttribute(attribute) === value,
    ),
  );

function projectedHolder(element, reading) {
  let holder = projectedParent(element, reading);
  while (holder && !registry[holder.localName])
    holder = projectedParent(holder, reading);
  return holder;
}

function completionMet(source, spec, reading) {
  const completion = spec.completion;
  if (!completion) return true;
  const empty = completion.empty;
  const containers = [...source.querySelectorAll(empty.within)].filter((element) =>
    attributeConditionHolds(element, empty.when),
  );
  if (containers.length !== 1) return false;
  const container = containers[0];
  return ![source, ...source.querySelectorAll("*")]
    .filter((element) => registry[element.localName])
    .some(
      (element) =>
        element !== container && projectedHolder(element, reading) === container,
    );
}

function answerStands(source, verb, reading) {
  const spec = registry[source.localName]?.["x-state"]?.[verb];
  if (!spec) return false;
  const held = [...reading.projection.actions.values()].find(
    ({ e }) => e.widget === source.id && e.action === verb,
  );
  const record = spec.record;
  if (spec.unit === "widget" && ["attribute", "value"].includes(record?.kind)) {
    const value =
      held?.value ?? authoredFacet(stateCoordinate(source.id, source.id, spec));
    return (
      value !== undefined &&
      value !== null &&
      value !== "" &&
      (!Array.isArray(value) || value.length > 0)
    );
  }
  return Boolean(held && completionMet(source, spec, reading));
}

function projectionAnswered(source, reading) {
  const awaits = askEntry(source);
  if (!awaits) return false;
  const until = inChrome(source) && awaits.until;
  const answers =
    until && attributeConditionHolds(source, until.when)
      ? [until.verb]
      : (awaits.answers ?? []);
  return answers.some((verb) => answerStands(source, verb, reading));
}

function optimisticallyReopened(reading) {
  const owners = new Set(
    [...(reading.projection.pendingWithdrawals?.values() ?? [])]
      .map(({ e }) => elementById(e.widget))
      .filter(Boolean),
  );
  return [...owners].filter(
    (owner) => askEntry(owner) && !projectionAnswered(owner, reading),
  );
}

function context(answered = false) {
  const projection = currentProjection();
  const reading = {
    awaiting: awaitingValues(answered),
    positionedParents: positionedParents(projection),
    projection,
  };
  if (!projectionDeferred())
    for (const owner of optimisticallyReopened(reading))
      reading.awaiting[owner.id] = true;
  return reading;
}

export const answeredContext = () => context(true);
export const isAwaiting = (el, reading) => Boolean(reading.awaiting[el.id]);
export const projectedParent = (el, reading) =>
  (el.id && reading.positionedParents.get(el.id)) ??
  authoredParentOf(el) ??
  el.parentElement;

function serverAsks(kind, pendingRequestEvents = []) {
  if (!pagePresented()) return [];
  const requested = new Set(
    kind === "all" ? [] : pendingRequestEvents.map((event) => event.widget),
  );
  const documentAsks = runtime.view?.document?.asks?.[kind] ?? [];
  const conversationAsks = runtime.browser?.conversation?.asks?.[kind] ?? [];
  const elements = [...documentAsks, ...conversationAsks]
    .map((ask) => elementById(ask.id))
    .filter(
      (element) => element && (kind === "all" || !requested.has(askSource(element).id)),
    );
  return [...new Set(elements)].sort((left, right) => {
    if (left === right) return 0;
    return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING
      ? -1
      : 1;
  });
}

function effectiveAsks(kind, pendingRequestEvents) {
  const durable = serverAsks(kind, pendingRequestEvents);
  const durableSet = new Set(durable);
  const reading = answeredContext();
  const reopened = optimisticallyReopened(reading).map(askSurface);
  const candidates =
    kind === "unanswered" ? allAsks() : [...new Set([...durable, ...reopened])];
  return candidates.filter((ask) => {
    const source = askSource(ask);
    return askEntry(source)
      ? !projectionAnswered(source, reading)
      : durableSet.has(ask);
  });
}

export const allAsks = () => serverAsks("all");
export const openAsks = (pendingRequestEvents) =>
  effectiveAsks("reader", pendingRequestEvents);
export const unansweredAsks = (pendingRequestEvents) =>
  effectiveAsks("unanswered", pendingRequestEvents);

// A failed or deferred document transaction can leave the public action projection
// ahead of the DOM it was meant to describe. Approval is irreversible enough to wait
// for that transaction boundary; ordinary Ask surfaces continue to narrate a local
// gesture immediately.
export function approvalBlockingAsks(pendingRequestEvents) {
  if (projectionDeferred()) return serverAsks("unanswered", pendingRequestEvents);
  return effectiveAsks("unanswered", pendingRequestEvents);
}

// A package subscribes to the semantic projection, never to the transport's broad
// invalidation event. The first reading is synchronous, which lets a connected
// widget paint one complete state without a separate setup path. The owner exists
// only to bind lifetime; the reading stays page-wide because a command hub observes
// asks elsewhere in the document.
export function watchAsks(owner, pendingRequests, callback) {
  if (typeof pendingRequests !== "function")
    throw new TypeError("An Ask watcher needs a pending-request reading");
  if (typeof callback !== "function")
    throw new TypeError("An Ask watcher needs a callback");
  return watchProjection(owner, () => callback(openAsks(pendingRequests())));
}
