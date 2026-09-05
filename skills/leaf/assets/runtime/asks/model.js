/* Server-projected ask state, resolved onto the browser's live DOM: which asks
   are open, answered, or waiting on the agent, and the three lists the banner, the tray,
   and the walks read.

   The banner's Asks count is durable progress: `Asks 3/7` means three of the seven active
   Asks are answered. `allAsks` supplies the denominator and
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
   the visible/navigation surface. `actionAvailable` still queries whether the source or
   an ancestor's aggregate is open. A module reading `openAsks()` calls
   `askSource()` when it needs the actionable widget rather than the reader-facing
   region. */

import { watchProjection } from "../projection-watch.js";
import { registry, tagsDeclaring } from "../registry.js";
import { closestAcross, elementById } from "../passages.js";
import { runtime } from "../context.js";
import { pagePresented } from "../presentation.js";
import { authoredParents } from "../projection/authored.js";
import { stateProjection } from "../projection/fold.js";

/* Server-projected ask state, resolved onto the browser's live DOM. */
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
      (registry[moved.localName]?.["x-parent"] ?? []).includes(holder.localName)
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

function context(answered = false) {
  const projection = stateProjection();
  return {
    awaiting: awaitingValues(answered),
    positionedParents: positionedParents(projection),
    projection,
  };
}

export const answeredContext = () => context(true);
export const isAwaiting = (el, reading) => Boolean(reading.awaiting[el.id]);
export const projectedParent = (el, reading) =>
  (el.id && reading.positionedParents.get(el.id)) ??
  authoredParentOf(el) ??
  el.parentElement;

function asks(kind) {
  if (!pagePresented()) return [];
  const documentAsks = runtime.view?.document?.asks?.[kind] ?? [];
  const conversationAsks = runtime.browser?.conversation?.asks?.[kind] ?? [];
  const elements = [...documentAsks, ...conversationAsks]
    .map((ask) => elementById(ask.id))
    .filter(Boolean);
  return [...new Set(elements)].sort((left, right) => {
    if (left === right) return 0;
    return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING
      ? -1
      : 1;
  });
}

export const allAsks = () => asks("all");
export const openAsks = () => asks("reader");
export const unansweredAsks = () => asks("unanswered");

// A package subscribes to the semantic projection, never to the transport's broad
// invalidation event. The first reading is synchronous, which lets a connected
// widget paint one complete state without a separate setup path. The owner exists
// only to bind lifetime; the reading stays page-wide because a command hub observes
// asks elsewhere in the document.
export function watchAsks(owner, callback) {
  if (typeof callback !== "function")
    throw new TypeError("An Ask watcher needs a callback");
  return watchProjection(owner, () => callback(openAsks()));
}
