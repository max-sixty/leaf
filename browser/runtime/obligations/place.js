/* Mechanical placement of an obligation in the current document, and the one rule for which
   obligations a region of the page holds.

   A widget's source owns its answer and is where the obligation stands, so focus, rings,
   markers and arrival all name the same request. Its context, the element whose heading
   names it (`prompt.target`, `obligations.framed_widgets` in Python) where that is not
   the widget itself, supplies its prompt and where an arrival starts reading
   (obligations/view.js). The context is
   plain HTML, such as a section holding the question with its premise or a whole part
   of a report, so no obligation stands at it, and being in it is not being at one; until
   16 November 2026 an `lf-ask` was the context, and the one obligation it held stood at
   it whole. A record unit stands at its projected datum, even when it is the widget's
   only obligation; the owning widget still supplies its commands and answer formatter.
   Frozen thread sources may have no node until the thread owner materializes them.
   A question answered in words and an update stand nowhere on the page; their thread
   or widget owner draws them. Nor does anything whose subject is the page as a whole:
   a to-do on the page stood at its first heading until 2 November 2026, when the user
   chose to give it no place, since that heading had nothing to do with it. Placement
   never changes the semantic inventory or its obligation identities.

   A region holds an obligation when the obligation's source element is the region or stands under
   it (`obligationsIn`, or `obligationsByRegion` for many regions at once), shadow trees included. A withdrawn obligation no longer asks anything, and
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
   obligation. */
import { projectedDatum } from "../anchor-resolution.js";
import { elementById } from "../passages.js";
import { composedParentNode } from "../shadow.js";
import { readObligations } from "./model.js";

const NOWHERE = Object.freeze({ source: null, context: null });

/** @param {import("../framework/application.js").ObligationRecord | null | undefined} item */
export function obligationPlace(item) {
  if (item?.source.kind !== "widget") return NOWHERE;
  const owner = elementById(item.source.id);
  const source = item.source.unit ? projectedDatum(owner, item.source.unit) : owner;
  const framed = item.prompt.target !== item.source.id;
  return { source, context: framed ? elementById(item.prompt.target) : null };
}

// Where a to-do's or an update's subject stands on the page: the element or widget it
// names, and nowhere for the page as a whole or a thread.
/** @param {import("../../types/contract.js").ServedSubject} subject */
export const subjectPlace = (subject) =>
  subject.kind === "page" || subject.kind === "thread" ? null : elementById(subject.id);

// The obligations each of `regions` holds, in the order `items` lists them. Each
// obligation's source climbs once to the top of the page, past each region above it, so
// a widget that counts for every panel or card makes one pass over the inventory rather
// than one per region.
/** @param {readonly Node[]} regions
 * @param {readonly import("../framework/application.js").ObligationRecord[]} items */
export function obligationsByRegion(regions, items = readObligations().all) {
  /** @type {Map<Node, import("../framework/application.js").ObligationRecord[]>} */
  const held = new Map(regions.map((region) => [region, []]));
  for (const item of items) {
    if (item.status === "withdrawn") continue;
    const { source } = obligationPlace(item);
    for (let at = /** @type {Node | null} */ (source); at; at = composedParentNode(at))
      held.get(at)?.push(item);
  }
  return held;
}

// The obligations `region` holds, in the order `items` lists them.
/** @param {Element} region
 * @param {readonly import("../framework/application.js").ObligationRecord[]} items */
export const obligationsIn = (region, items = readObligations().all) =>
  /** @type {import("../framework/application.js").ObligationRecord[]} */ (
    obligationsByRegion([region], items).get(region)
  );
