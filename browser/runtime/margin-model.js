/* What each margin cluster shows, chosen from values the browser captured.

   `marginInventory` takes each target's margin contributions and the readings Leaf
   generated for it (threads, reactions, notices), in document order, and fixes the
   target's controls, reading choices and state once. `clusterProjection` then picks
   what its cluster shows. At rest that is a primary control and one more: the single
   peer, or More when there are several. Expanded, it is up to six controls, the last
   of them a route to the Page Map when more remain. A failure, work in flight or an
   open interaction keeps the cluster's controls open (`entryEngaged`). When the user
   expands one contribution, only its controls show, and an open thread card keeps its
   Thread control within the six.

   A pin with no room on the page may fold to its options toggle alone (`canFold`),
   whose options are then every control, the primary first. The folded toggle shows
   the icon of its primary contribution's declared `kind`; unfolded, it is More.
   Placement decides whether a pin folds, and the user's gesture opens it.

   A contributed control that represents a kind of generated reading replaces that
   reading. A target's workflow receipt goes on its primary control, and every other
   control carries its own (`controlReceipt`). Whether a cluster is expanded and
   whether a thread is open arrive as arguments. This module reads no DOM and no
   registrations; layout and the retained controls read its values.
 */
import {
  KINDS,
  spokenSubject,
  contributionItemKey,
  compareContributions,
  compareContributionEntryRecords,
  contributionState,
  contributionEntryStateRank,
} from "./contribution-model.js";
import { threadAttention } from "./thread/workflow.js";
import { leafSays, wordsText } from "./voice.js";

/** @typedef {import("./contribution-model.js").ContributionModel} Offer
 * @typedef {import("./contribution-model.js").OwnedEntry} RecordEntry
 * @typedef {import("./contribution-model.js").ContributionKind} Kind
 * @typedef {import("./contribution-model.js").ContributionState} State
 * @typedef {import("./contribution-model.js").KindFace} KindFace
 * @typedef {import("./framework/application.js").Workflow} Workflow
 * @typedef {{word: import("./voice.js").Words, reason: string}} UserAttention
 * @typedef {{id: string, text: string, owner?: string, marker?: boolean,
 * represents?: boolean, workflowFace?: KindFace & {state?: State}, workflowReceipt?: Workflow | null,
 * carriesWorkflow?: boolean, state?: State, label?: string | null,
 * userAttention?: UserAttention | null, unread?: number, context?: import("./voice.js").Words | null,
 * mapContext?: import("./voice.js").Words | null, words?: import("./voice.js").Words, atWork?: boolean}} AnnotationBase
 * @typedef {AnnotationBase & {kind: "comment", marker?: true, thread: import("./thread/workflow.js").ThreadRecord}} ThreadItem
 * @typedef {ThreadItem | (AnnotationBase & {kind: Exclude<Kind, "comment">, thread?: never}) | (AnnotationBase & {kind: "comment", marker: false, owner: string, thread?: never})} AnnotationItem
 */
/** @template {Offer} [O=Offer]
 * @typedef {{key: string, targetId: string, title: string, offers: readonly O[],
 * items: readonly AnnotationItem[], workflowReceipt?: Workflow | null, atWork?: boolean}} MarginGroup
 */
/** @typedef {{key: string, kind: "comment", items: readonly [ThreadItem, ...ThreadItem[]], text: string}} ThreadChoice
 * @typedef {ThreadChoice | {key: string, kind: Exclude<Kind, "comment">, items: readonly [AnnotationItem, ...AnnotationItem[]], text: string}} ReadingChoice
 * @typedef {{key: string, owner: string, receipt: Workflow}} WorkflowCarrier
 */
/** @template {Offer} [O=Offer]
 * @typedef {MarginGroup<O> & {controls: readonly Control<O>[], afterControls: readonly Control<O>[],
 * choices: readonly ReadingChoice[], state: State, hasMarginHost: boolean, workflowCarrier: WorkflowCarrier | null}} MarginEntry
 */
/** @template {Offer} [O=Offer]
 * @typedef {{cluster: MarginEntry<O> | null, kind: "contribution", offered: O,
 * record: RecordEntry, receipt: Workflow | null | undefined}} Control
 */
/** @typedef {{expandedKey?: string | null, expandedOwner?: string | null, forcedInlineKey?: string | null, folded?: boolean}} ProjectionOptions */

const RESTING_MARGIN_ENTRY_BUDGET = 2;
// The options toggle uses the shared kind face when folded; each face retains identity.
const TOGGLE = Object.freeze({ action: "more", label: "More options" });
const EXPANDED_MARGIN_ENTRY_BUDGET = 6;

// A contributed native control represents its owner's generated reading. Complete
// views retain owned readings only while that owner supplies no visible control.
/** @template {Offer} O @param {MarginEntry<O>} entry */
export function annotationItems(entry) {
  const represented = new Set(
    entry.offers.flatMap(({ reading }) =>
      reading.entries.filter((record) => record.visible).map((record) => record.owner),
    ),
  );
  return entry.items.filter((item) => !item.owner || !represented.has(item.owner));
}

/** @template {Offer} O @param {MarginEntry<O>} entry */
const noticeItems = (entry) =>
  entry.offers.flatMap((offered) => {
    const notice = offered.reading.notice;
    if (!notice) return [];
    return [Object.freeze({ kind: "notice", key: offered, notice, offered })];
  });
// One target has one lifecycle reading. Failure outranks work in flight, which
// outranks an open interaction; the ordinary idle state never forces peers open.
// Generated acknowledgment readings are settled server facts, so only a face that
// explicitly declares an interaction state joins this axis.
/** @template {Offer} O @param {Pick<MarginGroup, "offers" | "items">} entry */
const deriveEntryState = (entry) => {
  const states = [
    ...entry.offers.map(contributionState),
    ...entry.items.map((item) => item.state ?? item.workflowFace?.state ?? "idle"),
  ];
  return (
    states.sort(
      (left, right) =>
        contributionEntryStateRank(left) - contributionEntryStateRank(right),
    )[0] ?? "idle"
  );
};
// Every state but idle keeps the cluster open, so the reading is the absence of idle
// rather than a second list of states beside the grammar's.
/** @template {Offer} O @param {MarginEntry<O>} entry */
const entryState = (entry) => entry.state;
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const entryEngaged = (entry) => entry.state !== "idle";

// A target's agent work rides on its primary control (`workflowCarrier`); every other
// control shows the receipt its contribution gave it. Each control item carries the
// receipt this rule gives it, and every seat that shows the control paints that one.
/** @param {WorkflowCarrier | null} carrier @param {RecordEntry} record */
const controlReceipt = (carrier, record) =>
  carrier?.key === record.key && carrier.owner === record.owner
    ? carrier.receipt
    : record.workflowReceipt;
/** @template {Offer} O @param {O} offered @param {RecordEntry} record @param {WorkflowCarrier | null} carrier @param {MarginEntry<O> | null} [cluster] @returns {Readonly<Control<O>>} */
const contributionItem = (offered, record, carrier, cluster = null) =>
  Object.freeze({
    cluster,
    kind: "contribution",
    offered,
    record,
    receipt: controlReceipt(carrier, record),
  });
/** @template {Offer} O @param {readonly O[]} offers */
const visibleRecords = (offers) =>
  offers.flatMap((offered) =>
    offered.reading.entries
      .filter((record) => record.visible)
      .map((record) => ({ offered, record })),
  );
// Every control a target offers, before and after it alike, in canonical order, each
// with its receipt. The Page Map and page annotation views list a target's controls so.
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const entryControls = (entry) =>
  [...entry.controls, ...entry.afterControls].sort(compareContributionEntryRecords);
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const choosePrimary = (entry) => entry.controls[0] ?? null;
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const entryHasMarginHost = (entry) => entry.hasMarginHost;
/** @param {Pick<MarginGroup, "key">} entry @param {ReadingChoice} choice */
export const readingKey = (entry, choice) => JSON.stringify([entry.key, choice.key]);
/** @param {readonly AnnotationItem[]} items @returns {readonly ReadingChoice[]} */
const deriveReadingChoices = (items) => {
  /** @type {ThreadItem[]} */
  const threadList = [];
  /** @type {ReadingChoice[]} */
  const choices = [];
  for (const item of items) {
    if (item.marker === false) continue;
    if (item.kind === "comment") threadList.push(item);
    else
      choices.push({
        key: contributionItemKey(item),
        kind: item.kind,
        items: [item],
        text: item.text,
      });
  }
  const [firstThread, ...otherThreads] = threadList;
  if (firstThread)
    choices.push({
      // One target owns one thread margin entry. Membership changes repaint its badge and
      // card without replacing the control that owns an open thread.
      key: "threadList",
      kind: "comment",
      items: [firstThread, ...otherThreads],
      text: firstThread.text,
    });
  return Object.freeze(
    choices
      .map((choice) => {
        Object.freeze(choice.items);
        return Object.freeze(choice);
      })
      .sort(
        (left, right) =>
          KINDS[left.kind].priority - KINDS[right.kind].priority ||
          left.items[0].id.localeCompare(right.items[0].id) ||
          left.key.localeCompare(right.key),
      ),
  );
};
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const readingChoices = (entry) => entry.choices;
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
/** @template {Offer} O @param {MarginEntry<O>} entry */
export const threadReading = (entry) =>
  readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
/** @template {Offer} O @param {MarginEntry<O>} entry @param {Control<O> | null} primaryControl */
const secondaryReadings = (entry, primaryControl) =>
  readingChoices(entry).slice(primaryControl ? 0 : 1);

/** @template {Offer} O @param {MarginEntry<O>} entry @param {Control<O> | null} primary */
export const secondaryCount = (entry, primary) =>
  secondaryReadings(entry, primary).length +
  entry.controls.length -
  Number(Boolean(primary)) +
  entry.afterControls.length;
// One peer is not overflow. It costs the same second entry as `…`, but the peer says
// what it does and is immediately usable. Ellipsis earns its place only from the third
// margin entry onward.
/** @template {Offer} O @param {MarginEntry<O>} entry @param {Control<O> | null} primary */
export const optionsOffered = (entry, primary) =>
  secondaryCount(entry, primary) > RESTING_MARGIN_ENTRY_BUDGET - 1;

// The words a reading's control shows: its kind's word, plural for several items, or
// the one item's own label where it has one (an item's question). Accessible names keep
// the kind's word and say the subject beside it.
/** @param {ReadingChoice | null | undefined} choice */
export function readingLabel(choice) {
  const face = readingFace(choice);
  const items = choice?.items ?? [];
  if (items.length > 1) return `${face.label}s`;
  return items[0]?.label || face.label;
}

/** @template {Offer} O @param {MarginEntry<O>} entry */
export function markerFace(entry) {
  const kinds = kindsIn(entry, { markerOnly: true });
  const choice = primaryReading(entry);
  const face = readingFace(choice);
  const faceCount = choice?.items.length ?? 0;
  return {
    kinds,
    face,
    label: readingLabel(choice),
    // The badge describes this margin entry's result. Other readings live behind `…`
    // and must not make a thread margin entry appear to open more threadList than it does.
    count: faceCount,
  };
}

/** @param {ReadingChoice | null | undefined} choice */
export function readingFace(choice) {
  return (
    (choice?.items.length === 1 && choice.items[0].workflowFace) ||
    (choice && KINDS[choice.kind]) ||
    KINDS.action
  );
}

/** @param {ReadingChoice | null | undefined} choice */
export function readingState(choice) {
  return (
    (choice?.items ?? [])
      .map((item) => item.state ?? item.workflowFace?.state ?? "idle")
      .sort(
        (left, right) =>
          contributionEntryStateRank(left) - contributionEntryStateRank(right),
      )[0] ?? "idle"
  );
}

/** @param {KindFace} face */
export const readingBehavior = (face) => (face.indication ? "status" : "disclosure");

// Each member already carries canonical Thread attention. An aggregate keeps a concrete
// obligation ahead of a resend; it never re-derives attention from turns or
// workflow stages.
/** @param {readonly AnnotationItem[]} items */
const userAttention = (items) => {
  let first = null;
  for (const item of items) {
    const attention = item.userAttention;
    if (!attention) continue;
    if (attention.reason === "obligation") return attention;
    first ??= attention;
  }
  return first;
};
/** @param {readonly AnnotationItem[]} items */
export const awaitingUser = (items) => Boolean(userAttention(items));
// Agent messages the user has not taken in, across every thread a reading
// carries: each Thread's canonical `unread`, summed rather than re-derived.
/** @param {readonly AnnotationItem[]} items */
export const unreadIn = (items) =>
  items.reduce((sum, item) => sum + (item.unread ?? 0), 0);

// What a thread's margin item and its Page Map row carry of it beside its name and
// place, from the one reading of the thread's state (`threadAttention`) that Threads
// paints as its status: whose turn it is; the workflow its progress decoration paints
// while the thread waits on the agent, saying that workflow's word (`workflowWord`);
// and its line, the thread's word wherever no such receipt says it, else how many of
// its messages the user has not read. A receipt under a condition, such as a response
// that failed, paints no progress (`progressFace`), so the line says its word.
/** @param {import("./thread/workflow.js").ThreadRecord} thread @param {string} agent */
export function threadMarks(thread, agent) {
  const attention = threadAttention(thread, agent);
  const onUser = attention?.kind === "needs_user";
  const receipt = attention?.kind === "waiting" ? attention.workflow : null;
  const unread = thread.unread.length;
  // The thread's word, said by whoever says it (`threadAttention`), or Leaf's count of
  // what it holds unread.
  const line =
    (attention && (!receipt || receipt.condition) && attention.word) ||
    (unread ? leafSays(`${unread} unread`) : null);
  return {
    userAttention: onUser
      ? { word: attention.word, reason: thread.attention?.reason ?? "workflow" }
      : null,
    unread,
    context: line,
    mapContext: line,
    workflowReceipt: receipt,
  };
}

// A reading of one item says that item's own line, as a thread's says its word or its
// unread count (`threadMarks`); an aggregate says the turn it owes the user, else what
// its threads hold unread. Each line is said by whoever says it (voice.js).
/** @param {ReadingChoice | null | undefined} choice */
export function readingContext(choice) {
  const items = choice?.items ?? [];
  const attention = userAttention(items);
  if (attention) return attention.word;
  if (items.length === 1) return items[0].context ?? null;
  const unread = unreadIn(items);
  return unread ? leafSays(`${unread} unread`) : null;
}

// The line a reading's name says too: a thread's, which is its word or what it holds
// unread (`threadMarks`), and an aggregate's turn or unread count. Another reading's
// line, such as a change's offer, is said by its control.
/** @param {ReadingChoice | null | undefined} choice */
export const spokenContext = (choice) => {
  const items = choice?.items ?? [];
  return choice?.kind === "comment" || awaitingUser(items) || unreadIn(items)
    ? wordsText(readingContext(choice) ?? "") || null
    : null;
};

/** @param {MarginGroup} entry @param {{markerOnly?: boolean}} [options] */
function kindsIn(entry, { markerOnly = false } = {}) {
  /** @type {Map<Kind, number>} */
  const counts = new Map();
  for (const item of entry.items) {
    if (!markerOnly || item.marker !== false)
      counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
  }
  return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
}

/** @template {Offer} O @param {MarginEntry<O>} entry @param {ReadingChoice} choice */
const readingItem = (entry, choice) =>
  Object.freeze({
    kind: "reading",
    key: `reading:${readingKey(entry, choice)}`,
    entry,
    choice,
  });

/** @template {Offer} O @param {MarginEntry<O>} entry @param {Control<O> | null} primary @param {O | null} [focusedOffer]
 * @returns {(Control<O> | {kind: "reading", key: string, entry: MarginEntry<O>, choice: ReadingChoice})[]} */
function optionItems(entry, primary, focusedOffer = null) {
  if (focusedOffer) {
    return focusedOffer.reading.entries
      .filter((record) => record.visible)
      .map((record) =>
        contributionItem(focusedOffer, record, entry.workflowCarrier, entry),
      );
  }
  return [
    ...entry.controls
      .slice(primary ? 1 : 0)
      .map((item) => Object.freeze({ ...item, cluster: entry })),
    ...secondaryReadings(entry, primary).map((choice) => readingItem(entry, choice)),
    ...entry.afterControls.map((item) => Object.freeze({ ...item, cluster: entry })),
  ];
}

/** @template {Offer} O @param {MarginEntry<O>} entry @param {Control<O> | null} primary @param {boolean} optionsOpen @param {O | null} [focusedOffer] @param {string | null} [forcedInlineKey] @param {boolean} [folded] */
function optionGroupProjection(
  entry,
  primary,
  optionsOpen,
  focusedOffer = null,
  forcedInlineKey = null,
  folded = false,
) {
  const items = optionItems(entry, primary, focusedOffer);
  // Peers may use the whole cluster budget only when no margin entry stands outside this
  // group. Reaction mode is the common case: it has neither a primary nor a reading
  // marker, so its six declared choices fit exactly. A reading-only target keeps its
  // marker visible, and that margin entry counts just as a contributed primary would.
  const peerCapacity = Math.max(
    0,
    EXPANDED_MARGIN_ENTRY_BUDGET -
      (!focusedOffer && (primary || entry.choices.length) ? 1 : 0),
  );
  const needsSpill = items.length > peerCapacity;
  // The spill route consumes the last visible margin entry; it does not increase the
  // cluster beyond its budget. A fully expanded cluster is therefore either one
  // primary plus five peers, or one primary plus four peers plus the Page Map route.
  const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
  const hidden = Math.max(0, items.length - visibleCapacity);
  const direct = items.slice(0, visibleCapacity);
  const forcedThread =
    forcedInlineKey === entry.key
      ? items.find((item) => item.kind === "reading" && item.choice.kind === "comment")
      : null;
  // An open thread card keeps its owning Thread control on the page edge. When the
  // ordinary order would put it beyond the six-control budget, spill the last unrelated
  // peer in its place; the Page Map still retains every action in canonical order.
  if (forcedThread && direct.length && !direct.includes(forcedThread))
    direct[direct.length - 1] = forcedThread;
  const firstSpilled = items.find((item) => !direct.includes(item));
  return Object.freeze({
    entry,
    entryKey: entry.key,
    label: `${entryEngaged(entry) || folded ? "Actions" : "More options"} for ${spokenSubject(entry.title)}`,
    hidden: !optionsOpen || direct.length === 0,
    items: Object.freeze(items),
    spill: needsSpill
      ? Object.freeze({
          count: hidden,
          first: firstSpilled,
          label: `Show ${hidden} more in Page Map`,
        })
      : null,
    visible: Object.freeze(direct),
  });
}

/** @template {Offer} O @param {MarginEntry<O>} entry @param {string | null | undefined} expandedKey @param {string | null | undefined} expandedOwner */
export const focusedOfferOf = (entry, expandedKey, expandedOwner) =>
  expandedKey === entry.key && expandedOwner
    ? (entry.offers.find((offered) => offered.key === expandedOwner) ?? null)
    : null;

// Whether a cluster may stand folded: its resting face is a contributed primary and one
// more control, a peer or More, and nothing else, so folding it trades exactly one of
// them for the toggle. A cluster that shows a reading or a notice, or is engaged, keeps
// its face, since what it shows there is what the user returns to.
/** @template {Offer} O @param {MarginEntry<O>} entry @param {ProjectionOptions} [options] */
export function canFold(entry, { expandedKey = null, expandedOwner = null } = {}) {
  if (focusedOfferOf(entry, expandedKey, expandedOwner)) return false;
  const primary = choosePrimary(entry);
  return (
    Boolean(primary) &&
    secondaryCount(entry, primary) > 0 &&
    entry.choices.length === 0 &&
    noticeItems(entry).length === 0 &&
    !entryEngaged(entry)
  );
}

/** @template {Offer} O @param {MarginEntry<O>} entry @param {ProjectionOptions} [options] */
export function clusterProjection(
  entry,
  {
    expandedKey = null,
    expandedOwner = null,
    forcedInlineKey = null,
    folded = false,
  } = {},
) {
  const focusedOffer = focusedOfferOf(entry, expandedKey, expandedOwner);
  const primary = focusedOffer ? null : choosePrimary(entry);
  const folds = folded && canFold(entry, { expandedKey, expandedOwner });
  // Folded, the primary stands among the options, first, behind the toggle.
  const shown = folds ? null : primary;
  const subject = spokenSubject(entry.title);
  const secondaries = focusedOffer
    ? focusedOffer.reading.entries.filter((record) => record.visible).length
    : secondaryCount(entry, primary);
  const hasOptions =
    folds || secondaries > (focusedOffer ? 0 : RESTING_MARGIN_ENTRY_BUDGET - 1);
  const optionsOpen =
    secondaries > 0 &&
    (!hasOptions || expandedKey === entry.key || entryEngaged(entry));
  // A contribution that declares no kind is an action, as a reading with none is.
  const kind = folds && primary ? (primary.offered.reading.kind ?? "action") : null;
  return Object.freeze({
    primary,
    hasOptions,
    optionsOpen,
    optionsExpanded: optionsOpen && expandedKey === entry.key,
    folded: folds,
    options: optionGroupProjection(
      entry,
      shown,
      optionsOpen,
      focusedOffer,
      forcedInlineKey,
      folds,
    ),
    direct: Object.freeze([...(shown ? [shown] : []), ...noticeItems(entry)]),
    entry,
    kind: "page",
    label: `Page actions for ${subject}`,
    toggle: kind ? KINDS[kind] : TOGGLE,
    moreLabel: kind
      ? `${KINDS[kind].label}, ${subject}`
      : `More options for ${subject}`,
    offers: entry.offers,
    hasPrimary: Boolean(shown),
    state: entryState(entry),
    target: entry.targetId || entry.key,
  });
}

// Inputs are captured in composed document order by the browser adapter. DOM targets,
// registrations, and activation callbacks stay there; this inventory owns only values.
/** @template {Offer} O @param {readonly MarginGroup<O>[]} groups @returns {readonly Readonly<MarginEntry<O>>[]} */
export function marginInventory(groups) {
  return Object.freeze(
    groups.map((group) => {
      const represented = new Set(
        group.items
          .filter((item) => item.marker === false && item.represents)
          .map((item) => item.kind),
      );
      let items = group.items
        .filter(
          (item) =>
            item.marker === false || item.workflowFace || !represented.has(item.kind),
        )
        .sort(
          (left, right) =>
            KINDS[left.kind].priority - KINDS[right.kind].priority ||
            (left.kind === "comment" ? 0 : left.id.localeCompare(right.id)),
        );
      const direct = group.offers.filter(
        (offered) => offered.reading.side === "before" || offered.reading.hasReadings,
      );
      const after = group.offers
        .filter(
          (offered) => offered.reading.side === "after" && !offered.reading.hasReadings,
        )
        .sort(compareContributions);
      const directRecords = visibleRecords(direct).sort(
        compareContributionEntryRecords,
      );
      const primary = directRecords[0];
      const receipt = group.workflowReceipt;
      const workflowCarrier =
        primary && receipt
          ? Object.freeze({
              key: primary.record.key,
              owner: primary.record.owner,
              receipt,
            })
          : null;
      /** @param {{offered: O, record: RecordEntry}[]} records */
      const controlsFrom = (records) =>
        records.map(({ offered, record }) =>
          contributionItem(offered, record, workflowCarrier),
        );
      const controls = Object.freeze(controlsFrom(directRecords));
      const afterControls = Object.freeze(
        after.flatMap((offered) =>
          controlsFrom(visibleRecords([offered]).sort(compareContributionEntryRecords)),
        ),
      );
      if (workflowCarrier)
        items = items.filter((item) => !(item.workflowFace && item.carriesWorkflow));
      return Object.freeze({
        ...group,
        items: Object.freeze(items),
        controls,
        afterControls,
        choices: deriveReadingChoices(items),
        state: deriveEntryState({ offers: group.offers, items }),
        hasMarginHost:
          controls.length > 0 ||
          afterControls.length > 0 ||
          items.some((item) => item.marker !== false),
        workflowCarrier,
      });
    }),
  );
}
