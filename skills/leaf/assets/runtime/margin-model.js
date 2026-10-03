/* Immutable margin inventory and cluster selection.
 * The browser captures target coordinates, contribution readings, and generated facts.
 * The inventory derives control order, reading choices, and placement counts once.
 * This fold owns representation, primary selection, thread aggregation, engagement,
 * ordering, and the compact/expanded budgets. Layout and retained controls consume
 * these values; neither DOM state nor registration capabilities enter this module.
 * A resting cluster has a primary and one peer, or More when multiple peers remain.
 * Expanded clusters have six seats including the route to the complete Page Map.
 * A pin its placement found no room for stands folded where its resting face is a
 * primary and one more control: the options toggle alone, whose options are then every
 * control, the primary first. Folding is placement's input, opening it the gesture's.
 * The folded toggle wears a marker's face, the one its primary contribution's declared
 * `kind` gives, so it says what it folds; unfolded it is More.
 * Failure, work in flight, and engagement keep completion controls exposed. An
 * explicitly focused contribution uses those seats alone; an open thread keeps its
 * aggregate control inside the budget. Thread membership retains thread order.
 * A contributed representation suppresses the matching generated kind. Workflow
 * receipts use the surviving primary when available, before any control is painted.
 * Expansion and an open thread are explicit mechanical inputs, not application facts.
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

const RESTING_MARGIN_ENTRY_BUDGET = 2;
// The options toggle's faces: More, or folded, the kind it folds (`clusterProjection`),
// one each, so a view that painted a face knows it by identity.
const TOGGLE = Object.freeze({ icon: "more", label: "More options" });
const FOLDED = Object.freeze(
  Object.fromEntries(
    Object.entries(KINDS).map(([kind, { icon, label }]) => [
      kind,
      Object.freeze({ icon, label }),
    ]),
  ),
);
const EXPANDED_MARGIN_ENTRY_BUDGET = 6;

// A contributed native control represents its owner's generated reading. Complete
// views retain owned readings only while that owner supplies no visible control.
export function annotationItems(entry) {
  const represented = new Set(
    entry.offers.flatMap(({ reading }) =>
      reading.entries.filter((record) => record.visible).map((record) => record.owner),
    ),
  );
  return entry.items.filter((item) => !item.owner || !represented.has(item.owner));
}

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
const entryState = (entry) => entry.state;
export const entryEngaged = (entry) => entry.state !== "idle";

export const contributionItem = (offered, record, surface = "margin", cluster = null) =>
  Object.freeze({
    cluster,
    kind: "contribution",
    offered,
    record,
    surface,
  });
const controlItems = (offers) =>
  offers.flatMap((offered) =>
    offered.reading.entries
      .filter((record) => record.visible)
      .map((record) => contributionItem(offered, record)),
  );
export const choosePrimary = (entry) => entry.controls[0] ?? null;
export const entryHasMarginHost = (entry) => entry.hasMarginHost;
export const readingKey = (entry, choice) => JSON.stringify([entry.key, choice.key]);
const deriveReadingChoices = (items) => {
  const threadList = [];
  const choices = [];
  for (const item of items.filter((item) => item.marker !== false)) {
    if (item.kind === "comment") threadList.push(item);
    else
      choices.push({
        key: contributionItemKey(item),
        kind: item.kind,
        items: [item],
        text: item.text,
      });
  }
  if (threadList.length)
    choices.push({
      // One target owns one thread margin entry. Membership changes repaint its badge and
      // card without replacing the control that owns an open thread.
      key: "threadList",
      kind: "comment",
      items: threadList,
      text: threadList[0].text,
    });
  return Object.freeze(
    choices
      .map((choice) => Object.freeze({ ...choice, items: Object.freeze(choice.items) }))
      .sort(
        (left, right) =>
          KINDS[left.kind].priority - KINDS[right.kind].priority ||
          left.items[0].id.localeCompare(right.items[0].id) ||
          left.key.localeCompare(right.key),
      ),
  );
};
export const readingChoices = (entry) => entry.choices;
export const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
export const threadReading = (entry) =>
  readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
const secondaryReadings = (entry, primaryControl) =>
  readingChoices(entry).slice(primaryControl ? 0 : 1);

export const secondaryCount = (entry, primary) =>
  secondaryReadings(entry, primary).length +
  entry.controls.length -
  Number(Boolean(primary)) +
  entry.afterControls.length;
// One peer is not overflow. It costs the same second circle as `…`, but the peer says
// what it does and is immediately usable. Ellipsis earns its place only from the third
// margin entry onward.
export const optionsOffered = (entry, primary) =>
  secondaryCount(entry, primary) > RESTING_MARGIN_ENTRY_BUDGET - 1;

// The words a reading's control shows: its kind's word, plural for several items, or
// the one item's own label where it has one (an Ask's question). Accessible names keep
// the kind's word and say the subject beside it.
export function readingLabel(choice) {
  const face = readingFace(choice);
  const items = choice?.items ?? [];
  if (items.length > 1) return `${face.label}s`;
  return items[0]?.label || face.label;
}

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

export function readingFace(choice) {
  return (
    (choice?.items.length === 1 && choice.items[0].workflowFace) ||
    KINDS[choice?.kind] ||
    KINDS.action
  );
}

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

export const readingBehavior = (face) => (face.indication ? "status" : "disclosure");

// Each member already carries canonical Thread attention. An aggregate keeps a concrete
// Ask ahead of another user recovery; it never re-derives attention from turns or
// workflow stages.
const userAttention = (items) => {
  let first = null;
  for (const item of items) {
    const attention = item.userAttention;
    if (!attention) continue;
    if (attention.reason === "ask") return attention;
    first ??= attention;
  }
  return first;
};
export const awaitingUser = (items) => Boolean(userAttention(items));
// Agent messages the user has not taken in, across every thread a reading
// carries: each Thread's canonical `unread`, summed rather than re-derived.
export const unreadIn = (items) =>
  items.reduce((sum, item) => sum + (item.unread ?? 0), 0);

export function readingContext(choice) {
  const attention = userAttention(choice?.items ?? []);
  if (attention) return attention.label;
  const unread = unreadIn(choice?.items ?? []);
  if (unread) return `${unread} unread`;
  if (choice?.items.length !== 1) return null;
  return choice.items[0].context ?? null;
}

function kindsIn(entry, { markerOnly = false } = {}) {
  const counts = new Map();
  for (const item of entry.items) {
    if (!markerOnly || item.marker !== false)
      counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
  }
  return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
}

const readingItem = (entry, choice) =>
  Object.freeze({
    kind: "reading",
    key: `reading:${readingKey(entry, choice)}`,
    entry,
    choice,
  });

function optionItems(entry, primary, focusedOffer = null) {
  if (focusedOffer) {
    return focusedOffer.reading.entries
      .filter((record) => record.visible)
      .map((record) => contributionItem(focusedOffer, record, "margin", entry));
  }
  return [
    ...entry.controls
      .slice(primary ? 1 : 0)
      .map((item) => Object.freeze({ ...item, cluster: entry })),
    ...secondaryReadings(entry, primary).map((choice) => readingItem(entry, choice)),
    ...entry.afterControls.map((item) => Object.freeze({ ...item, cluster: entry })),
  ];
}

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
      ? items.find((item) => item.choice?.kind === "comment")
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

const focusedOfferOf = (entry, expandedKey, expandedOwner) =>
  expandedKey === entry.key && expandedOwner
    ? (entry.offers.find((offered) => offered.key === expandedOwner) ?? null)
    : null;

// Whether a cluster may stand folded: its resting face is a contributed primary and one
// more control, a peer or More, and nothing else, so folding it trades exactly one of
// them for the toggle. A cluster that shows a reading or a notice, or is engaged, keeps
// its face, since what it shows there is what the user returns to.
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
  const kind = folds ? (primary.offered.reading.kind ?? "action") : null;
  return Object.freeze({
    primary,
    hasOptions,
    optionsOpen,
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
    toggle: kind ? FOLDED[kind] : TOGGLE,
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
      const controls = Object.freeze(
        controlItems(direct).sort(compareContributionEntryRecords),
      );
      const afterControls = Object.freeze(
        after.flatMap((offered) =>
          controlItems([offered]).sort(compareContributionEntryRecords),
        ),
      );
      const primary = controls[0];
      const receipt = group.workflowReceipt;
      const workflowCarrier =
        primary && receipt
          ? Object.freeze({
              key: primary.record.key,
              owner: primary.record.owner,
              receipt,
            })
          : null;
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
