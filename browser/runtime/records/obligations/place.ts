/* The obligations the page holds or a region of it holds, the mechanical placement of an
   obligation in the current document, and the one rule for which obligations a region
   holds.

   The page's reading is the application publisher's. Python folds the page's and thread
   markup's obligation readings under the page transaction that answers each state read,
   and the publisher carries them; nothing here folds those declarations again, and
   placement never changes which obligations exist, whether they await the user, or their
   identities.

   A widget's source owns its answer; the context supplies its prompt. The context is
   the part of the page the author assigned to the question: the innermost named group
   round the widget, such as an `lf-group`, whose label words it (`prompt.target`,
   `obligation_sources.widget_groups` in Python), or else the widget itself. A unique context
   is also its current node, so `m` lands on the whole question, its premise and
   evidence included, and focus anywhere in it is being at the question, where digits
   answer it.
   When several obligations share that context each stands at its own source, so focus,
   rings, markers and arrival all name the same request.
   Thread sources may have no node until the thread owner materializes them.
   A question answered in words and an update stand nowhere on the page; their thread
   or widget owner draws them. Nor does anything whose subject is the page as a whole:
   the user chose to give a to-do on the page no place, over standing it at its first
   heading, which has nothing to do with it.

   A region holds an obligation when the obligation's source element is the region or
   stands under it, shadow trees included: `readObligations(region)` reads the page's
   inventory so, and `obligationsByRegion` a list of the runtime's own. A withdrawn
   obligation no longer asks anything, and an obligation with no source (a question
   answered in words, an update's, or a thread source not drawn) stands in no region, so
   a region counts what its widgets ask. Membership reads the complete inventory,
   answered obligations included, and each consumer selects what it counts from the
   members: a tab row and `lf-tally` count every member, how many are answered, and whose
   turn the open ones are by next actor, so an obligation the user discussed and left
   with the agent counts as unanswered and on the agent; and a goal's interventions
   (host/work.js) are the members whose next actor is the user, since only those stop work on
   the user.
   A region's reading also says whether its markup asks the user something (`asks`): it
   holds a widget declaring `awaits`, in the page or in a message's markup, whatever the
   inventory says of its obligation. Before the first reading the obligation isn't listed
   yet, and once withdrawn it stands in no region; a side list's row keeps room for the
   answer through both.
   Every obligation and every asking widget of the page's markup is filed under each node
   above it once for the inventory, the captured widgets and the page's reading
   (state/kept.js), so a widget that reads every panel or card of its own pays one climb per
   obligation for the page, a region's reading costs a lookup, and no region's elements
   are searched: a panel holding a 96,000-line text document has about 97,000. A
   message's markup is a document of its own, drawn and moved by Leaf's surfaces and
   package readers, and nothing versions where it stands (readings/passages.js,
   `pageReadingVersion`, versions only the page's), so each widget in a message's
   markup is looked up and climbs on every read: reading every panel of a side list
   costs the panels times those widgets. Keeping that too would take a version every
   drawing of a message moves.
   Which obligation holds a node the user is in is the converse question, current location rather
   than membership (`obligationHolding`, records/current-target.js). It reads every placed
   obligation, and also falls back to an obligation's unique context. */
import { elementById } from "../../readings/passages.js";
import { readPart } from "../../state/semantic-state.js";
import { composedParentNode, under } from "../../lib/shadow-tree.js";
import { kept, keptEach } from "../../state/kept.js";
import type {
  ObligationRecord,
  WidgetDescriptor,
} from "../../state/semantic-application.js";
import type { ServedSubject } from "../../../types/contract.js";

const pageObligations = readPart((root) => root.effective.obligations);
/** The page's reading less its index, holding what one region holds, and whether the
 * region's markup asks the user something. */
type RegionObligations = Omit<ReturnType<typeof pageObligations>, "byId"> & {
  asks: boolean;
};

export function readObligations(): ReturnType<typeof pageObligations>;
export function readObligations(region: Node): RegionObligations;
/** The page's obligations, or those `region` holds. */
export function readObligations(
  region?: Node,
): ReturnType<typeof pageObligations> | RegionObligations {
  const page = pageObligations();
  if (region === undefined) return page;
  const all = heldBy(region, page.all);
  return {
    phase: page.phase,
    all,
    user: all.filter((item) => item.next_actor === "user"),
    unanswered: all.filter((item) => item.state !== "done"),
    // Read when asked, so a widget that doesn't ask doesn't draw again as the captured
    // widgets change.
    get asks() {
      return asks(region);
    },
  };
}

const NOWHERE = Object.freeze({ source: null, context: null, node: null });

// The element a widget's obligation answers at, and nothing for any other kind's.
const sourceOf = (item: ObligationRecord) =>
  item.source.kind === "widget" ? elementById(item.source.id) : null;

export function obligationPlace(
  item: ObligationRecord | null | undefined,
  items: readonly ObligationRecord[] = readObligations().all,
) {
  if (item?.source.kind !== "widget") return NOWHERE;
  const source = sourceOf(item);
  const context = elementById(item.prompt.target);
  const sharing = contextsOf(items).get(item.prompt.target);
  const shared = Boolean(
    sharing && (sharing.size > 1 || (sharing.size === 1 && !sharing.has(item.id))),
  );
  return { source, context, node: shared ? source : context };
}

// The ids of the widget obligations each context holds, read once per inventory
// (state/kept.js), so placing every obligation of an inventory costs one pass over it rather
// than one per obligation.
const contextsOf = keptEach((items: readonly ObligationRecord[]) => {
  const held = new Map<string | null, Set<string>>();
  for (const { id, source, prompt } of items) {
    if (source.kind !== "widget") continue;
    const ids = held.get(prompt.target);
    if (ids) ids.add(id);
    else held.set(prompt.target, new Set([id]));
  }
  return held;
});

// Where a to-do's or an update's subject stands on the page: the element or widget it
// names, and nowhere for the page as a whole or a thread.
export const subjectPlace = (subject: ServedSubject) =>
  subject.kind === "page" || subject.kind === "thread" ? null : elementById(subject.id);

// Whether an obligation still asks anything: a withdrawn one stands in no region.
const live = (item: ObligationRecord) => item.outcome !== "dropped";

// The obligations each of `regions` holds, in the order `items` lists them, filed in
// one pass over the list rather than one per region.
export function obligationsByRegion(
  regions: readonly Node[],
  items: readonly ObligationRecord[],
) {
  const filed = filedAbove(items.filter(live), sourceOf);
  return new Map(regions.map((region) => [region, filed.get(region) ?? []]));
}

// `items` filed under each node above where each stands (`at`), in their order: each
// climbs once to the top of the page, shadow trees included.
function filedAbove<T>(items: readonly T[], at: (item: T) => Node | null) {
  const filed = new Map<Node, T[]>();
  for (const item of items)
    for (let node = at(item); node; node = composedParentNode(node)) {
      const held = filed.get(node);
      if (held) held.push(item);
      else filed.set(node, [item]);
    }
  return filed;
}

// The inventory's live widget obligations, those of the page's markup and those of a
// message's, read once per inventory.
const placed = keptEach((all: readonly ObligationRecord[]) => {
  const widgets = all.filter((item) => item.source.kind === "widget" && live(item));
  return {
    onPage: widgets.filter((item) => item.thread === null),
    inMessages: widgets.filter((item) => item.thread !== null),
  };
});
// Each region's list is handed to every reader of the region, so it is frozen, as the
// page's reading is.
const filedOnPage = keptEach((all: readonly ObligationRecord[]) => {
  const filed = filedAbove(placed(all).onPage, sourceOf);
  for (const held of filed.values()) Object.freeze(held);
  return filed;
});
const NONE: readonly ObligationRecord[] = [];

// The obligations of `all` that `region` holds, in its order.
function heldBy(region: Node, all: readonly ObligationRecord[]) {
  const onPage = filedOnPage(all).get(region) ?? NONE;
  const inMessages = placed(all).inMessages.filter((item) =>
    under(sourceOf(item), region),
  );
  if (!inMessages.length) return onPage;
  const held = new Set([...onPage, ...inMessages]);
  return all.filter((item) => held.has(item));
}

// The ids of the captured widgets declaring `awaits`, of the page's markup and of
// messages' (records/widget-descriptors.js), which change with each revision and each message
// whose markup is captured.
const captured = readPart((root) => root.document.descriptors);
const asking = keptEach((widgets: ReadonlyMap<string, WidgetDescriptor>) => {
  const declaring = [...widgets.values()].filter(
    ({ declaration }) => declaration.awaits !== undefined,
  );
  return {
    onPage: declaring
      .filter(({ document }) => document.kind === "page")
      .map(({ id }) => id),
    inMessages: declaring
      .filter(({ document }) => document.kind !== "page")
      .map(({ id }) => id),
  };
});
const askingOnPage = kept(() => filedAbove(asking(captured()).onPage, elementById));

// Whether `region`'s markup holds a widget that asks the user something.
const asks = (region: Node) =>
  askingOnPage().has(region) ||
  asking(captured()).inMessages.some((id) => under(elementById(id), region));
