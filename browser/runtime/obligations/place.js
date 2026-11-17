/* Mechanical placement of an obligation in the current document, and the one rule for which
   obligations a region of the page holds.

   A widget's source owns its answer; the context supplies its prompt. The context is
   the part of the page the author assigned to the question: the innermost group the
   author declares round the widget, `role="group"` or a `<fieldset>`, which its name
   words (`prompt.target`, `obligations.framed_widgets` in Python), or else the widget
   itself. A unique context is also its current node, so `m` lands on the whole
   question, its premise and evidence included, and focus anywhere in it is being at the
   question, where digits answer it.
   When several obligations share that context each stands at its own source, so focus,
   rings, markers and arrival all name the same request. A record unit stands at its
   projected datum, even when it is the widget's only obligation; the owning widget
   still supplies its commands and answer formatter.
   Frozen thread sources may have no node until the thread owner materializes them.
   A question answered in words and an update stand nowhere on the page; their thread
   or widget owner draws them. Nor does anything whose subject is the page as a whole:
   the user chose to give a to-do on the page no place, over standing it at its first
   heading, which has nothing to do with it. Placement
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
   obligation, and also falls back to an obligation's unique context. */
import { projectedDatum } from "../anchor-resolution.js";
import { elementById } from "../passages.js";
import { readPart } from "../semantic-state.js";
import { composedParentNode } from "../shadow.js";
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
    const { source } = obligationPlace(item, items);
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

// The regions among `regions` that hold a widget declaring `state.awaits`, one whose markup
// asks the user something, in the page or in a message's markup. A region holds it
// whatever the inventory says of its obligation: before the first reading the
// obligation isn't listed yet, and once it is withdrawn the inventory lists it as
// withdrawn, which `obligationsByRegion` leaves out. A queue's row keeps room for the
// answer through both. The widgets are the documents' captured ones
// (widget-descriptors.js), which change with each revision and each message whose
// markup is captured, and each climbs once from its element, as an obligation's source
// does in `obligationsByRegion`. So the cost grows with the widgets and not with the
// elements the regions hold, of which a panel holding a 96,000-line text document has
// about 97,000.
const authoredWidgets = readPart((root) => root.document.descriptors);
/** @type {WeakMap<ReadonlyMap<string, import("../framework/application.js").WidgetDescriptor>, string[]>} */
const awaitingIds = new WeakMap();
/** @param {readonly Node[]} regions */
export function regionsAwaiting(regions) {
  const widgets = authoredWidgets();
  let ids = awaitingIds.get(widgets);
  if (!ids) {
    ids = [...widgets.values()]
      .filter(({ declaration }) => declaration.state?.awaits !== undefined)
      .map(({ id }) => id);
    awaitingIds.set(widgets, ids);
  }
  const wanted = new Set(regions);
  /** @type {Set<Node>} */
  const awaiting = new Set();
  for (const id of ids)
    for (
      let at = /** @type {Node | null} */ (elementById(id));
      at;
      at = composedParentNode(at)
    )
      if (wanted.has(at)) awaiting.add(at);
  return awaiting;
}
