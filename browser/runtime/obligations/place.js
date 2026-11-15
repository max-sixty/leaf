/* Mechanical placement of an obligation in the current document, and the one rule for which
   obligations a region of the page holds.

   A widget's source owns its answer; the context supplies its prompt. A unique context
   is also its current node. When several obligations share that context each stands at
   its own source, so focus, rings, markers and arrival all name the same request.
   A record unit stands at its projected datum, even when it is the widget's only
   obligation; the owning widget still supplies its commands and answer formatter.
   Frozen thread sources may have no node until the thread owner materializes them.
   A question answered in words and an update stand nowhere on the page; their thread
   or widget owner draws them. Nor does anything whose subject is the page as a whole:
   a to-do on the page stood at its first heading until 2 November 2026, when the user
   chose to give it no place, since that heading had nothing to do with it. Placement
   never changes the semantic inventory or its obligation identities.

   A region holds an obligation when the obligation's source element is the region or stands under
   it (`obligationsIn`), shadow trees included. A withdrawn obligation no longer asks anything, and
   an obligation with no source (a question answered in words, an update's, or a frozen
   source not drawn) stands in no region, so a region counts what its widgets
   ask. Membership reads the complete
   inventory, answered obligations included, and each consumer selects what it counts from
   the members: a tab row and `lf-tally` count every member, how many are answered, and
   whose turn the open ones are by next actor, so an obligation the user discussed and left
   with the agent counts as unanswered and on the agent; and a goal's
   interventions (work.js) are the members whose next actor is the user, since only those
   stop work on the user.
   Which obligation holds a node the user is in is the converse question, current location rather
   than membership (`obligationHolding`, current-target.js). It reads every placed
   obligation, and also falls back to an obligation's unique context. */
import { projectedDatum } from "../anchor-resolution.js";
import { elementById } from "../passages.js";
import { under } from "../shadow.js";
import { readObligations } from "./model.js";

const NOWHERE = Object.freeze({ source: null, context: null, node: null });

/** @param {import("../framework/application.js").ObligationRecord | null | undefined} item
 * @param {readonly import("../framework/application.js").ObligationRecord[]} items */
export function obligationPlace(item, items = readObligations().all) {
  if (item?.source.kind !== "widget") return NOWHERE;
  const owner = elementById(item.source.id);
  const source = item.source.unit ? projectedDatum(owner, item.source.unit) : owner;
  const context = elementById(item.prompt.target);
  const sharing = contextsOf(items).get(item.prompt.target);
  const shared = Boolean(
    sharing && (sharing.size > 1 || (sharing.size === 1 && !sharing.has(item.id))),
  );
  return { source, context, node: item.source.unit || shared ? source : context };
}

// The ids of the widget obligations each context holds, read once per inventory, so
// placing every obligation of an inventory costs one pass over it rather than one
// per obligation.
/** @type {WeakMap<readonly import("../framework/application.js").ObligationRecord[], Map<string | null, Set<string>>>} */
const contexts = new WeakMap();
/** @param {readonly import("../framework/application.js").ObligationRecord[]} items */
function contextsOf(items) {
  let held = contexts.get(items);
  if (held) return held;
  held = new Map();
  for (const { id, source, prompt } of items) {
    if (source.kind !== "widget") continue;
    const ids = held.get(prompt.target);
    if (ids) ids.add(id);
    else held.set(prompt.target, new Set([id]));
  }
  contexts.set(items, held);
  return held;
}

// Where a to-do's or an update's subject stands on the page: the element or widget it
// names, and nowhere for the page as a whole or a thread.
/** @param {import("../../types/contract.js").ServedSubject} subject */
export const subjectPlace = (subject) =>
  subject.kind === "page" || subject.kind === "thread" ? null : elementById(subject.id);

// The obligations `region` holds, in the order `obligations` lists them.
/** @param {Element} region
 * @param {readonly import("../framework/application.js").ObligationRecord[]} items */
export function obligationsIn(region, items = readObligations().all) {
  return items.filter((item) => {
    if (item.outcome === "dropped") return false;
    const { source } = obligationPlace(item, items);
    return Boolean(source && under(source, region));
  });
}
