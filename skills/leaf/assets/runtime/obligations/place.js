/* Mechanical placement of an obligation in the current document, and the one rule for which
   obligations a region of the page holds.

   The source owns its answer; the context supplies its prompt. A unique context is
   also its standing node. When several obligations share that context each stands at
   its own source, so focus, rings, markers and arrival all name the same request.
   A record unit stands at its projected datum, even when it is the widget's only
   obligation; the owning widget still supplies its commands and answer formatter.
   Frozen thread sources may have no node until the thread owner materializes them.
   Placement never changes the semantic inventory or its obligation identities.

   A region holds an obligation when the obligation's source element is the region or stands under
   it (`obligationsIn`), shadow trees included. A withdrawn obligation no longer asks anything, and
   an obligation with no page node (a question answered in words, an approval obligation, an
   update's, or a frozen source not drawn) stands in no region. Membership reads the complete
   inventory, answered obligations included, and each consumer selects what it counts from
   the members: a tab row and `lf-tally` count every member, how many are answered, and
   whose turn the open ones are by next actor, so an obligation the user discussed and left
   with the agent counts as unanswered and on the agent; and a goal's
   interventions (work.js) are the members whose next actor is the user, since only those
   stop work on the user.
   Which obligation holds a node the user stands in is the converse question, standing rather
   than membership (`obligationHolding`, standing-target.js), and it also falls back to an
   obligation's unique context. */
import { projectedDatum } from "../anchor-resolution.js";
import { elementById } from "../passages.js";
import { under } from "../shadow.js";
import { readObligations } from "./model.js";

export function obligationPlace(item, items = readObligations().all) {
  if (!item || item.source.kind !== "widget")
    return { source: null, context: null, node: null };
  const owner = elementById(item.source.id);
  const source = item.source.unit ? projectedDatum(owner, item.source.unit) : owner;
  const context = elementById(item.prompt.target);
  const shared = items.some(
    (other) =>
      other.id !== item.id &&
      other.source.kind === "widget" &&
      other.prompt.target === item.prompt.target,
  );
  return { source, context, node: item.source.unit || shared ? source : context };
}

// The obligations `region` holds, in the order `obligations` lists them.
export function obligationsIn(region, items = readObligations().all) {
  return items.filter((item) => {
    if (item.source.kind !== "widget" || item.status === "withdrawn") return false;
    const { source } = obligationPlace(item, items);
    return Boolean(source && under(source, region));
  });
}
