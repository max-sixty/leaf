/* Immutable margin inventory and cluster selection.
 * The browser captures target coordinates, contribution readings, and generated facts.
 * This fold owns representation, primary selection, thread aggregation, engagement,
 * ordering, and the compact/expanded budgets. Layout and retained controls consume
 * these values; neither DOM state nor registration capabilities enter this module.
 * A resting cluster has a primary and one peer, or More when multiple peers remain.
 * Expanded clusters have six seats including the route to the complete Page Map.
 * Failure, work in flight, and engagement keep completion controls exposed. An
 * explicitly focused contribution uses those seats alone; an open thread keeps its
 * aggregate control inside the budget. Thread membership retains conversation order.
 * A contributed representation suppresses the matching generated kind. Workflow
 * receipts use the surviving primary when available, before any control is painted.
 * Expansion and an open thread are explicit mechanical inputs, not application facts.
 */
import {
  compareMarginContributions,
  compareMarginEntryRecords,
  marginContributionState,
  marginEntryStateRank,
} from "./margin-entry-model.js";

export const KINDS = Object.freeze(
  Object.fromEntries(
    Object.entries({
      action: { label: "Action", icon: "dot", priority: -1 },
      change: { label: "Change", icon: "change", priority: 0 },
      restated: {
        label: "Rewritten",
        icon: "change",
        priority: 0,
        indication: true,
      },
      comment: { label: "Thread", icon: "comment", priority: 1 },
      ask: { label: "Ask", icon: "question", priority: 2 },
      sent: {
        label: "Sent",
        icon: "sent",
        priority: 3,
        indication: true,
      },
      pickup: {
        label: "Picked up",
        icon: "pickup",
        priority: 3,
        indication: true,
      },
      waiting: {
        label: "Waiting for pickup",
        icon: "waiting",
        priority: 3,
        indication: true,
      },
      reader: {
        label: "Your change",
        icon: "change",
        priority: 4,
        indication: true,
      },
      reported: {
        label: "Reported update",
        icon: "activity",
        priority: 4,
        indication: true,
      },
      activity: { label: "Working", icon: "activity", priority: 4 },
    }).map(([kind, face]) => [kind, Object.freeze(face)]),
  ),
);
const RESTING_MARGIN_ENTRY_BUDGET = 2;
const EXPANDED_MARGIN_ENTRY_BUDGET = 6;

export const trimmed = (value, limit = 110) => {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
};

const offerReadings = (offered) => offered.reading.readings;
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
export const entryState = (entry) => {
  const states = [
    ...entry.offers.map(marginContributionState),
    ...entry.items.map((item) => item.state ?? item.workflowFace?.state ?? "idle"),
  ];
  return (
    states.sort(
      (left, right) => marginEntryStateRank(left) - marginEntryStateRank(right),
    )[0] ?? "idle"
  );
};
// Every state but idle keeps the cluster open, so the reading is the absence of idle
// rather than a second list of states beside the grammar's.
export const entryEngaged = (entry) => entryState(entry) !== "idle";

const standingAfterOffers = (entry) =>
  entry.offers
    .filter(
      (offered) =>
        offered.reading.side === "after" && offerReadings(offered).length > 0,
    )
    .sort(compareMarginContributions);
const directOffers = (entry) => [
  ...entry.offers
    .filter((offered) => offered.reading.side === "before")
    .sort(compareMarginContributions),
  ...standingAfterOffers(entry),
];
export const contributionItem = (offered, record, surface = "margin", cluster = null) =>
  Object.freeze({
    cluster,
    kind: "contribution",
    offered,
    record,
    surface,
  });
const samePresentationItem = (left, right) => {
  if (left === right) return true;
  if (!left || !right || left.kind !== right.kind) return false;
  if (left.kind === "contribution")
    return (
      left.offered === right.offered &&
      left.record.key === right.record.key &&
      left.surface === right.surface
    );
  if (left.kind === "reading")
    return left.entry.key === right.entry.key && left.choice.key === right.choice.key;
  return left.offered === right.offered;
};
const directControlRecords = (entry) =>
  directOffers(entry)
    .flatMap((offered) =>
      offered.reading.entries
        .filter((record) => record.visible)
        .map((record) => ({
          offered,
          record,
          item: contributionItem(offered, record),
        })),
    )
    .sort(compareMarginEntryRecords);
const directControlItems = (entry) =>
  directControlRecords(entry).map(({ item }) => item);
export const choosePrimary = (entry) => directControlRecords(entry)[0]?.item ?? null;
const markerItems = (entry) => entry.items.filter((item) => item.marker !== false);
export const entryHasMarginHost = (entry) =>
  entry.offers.some((offered) =>
    offered.reading.entries.some((candidate) => candidate.visible),
  ) || markerItems(entry).length > 0;
export const readingKey = (entry, choice) => JSON.stringify([entry.key, choice.key]);
export const readingChoices = (entry) => {
  const threadList = [];
  const choices = [];
  for (const item of markerItems(entry)) {
    if (item.kind === "comment") threadList.push(item);
    else
      choices.push({
        key: item.id,
        kind: item.kind,
        items: [item],
        text: item.text,
      });
  }
  if (threadList.length)
    choices.push({
      // One target owns one thread margin entry. Membership changes repaint its badge and
      // card without replacing the control that owns an open conversation.
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
          left.key.localeCompare(right.key),
      ),
  );
};
export const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
export const threadReading = (entry) =>
  readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
const secondaryReadings = (entry, primaryControl) =>
  readingChoices(entry).slice(primaryControl ? 0 : 1);

const secondaryControls = (entry, primary) =>
  directControlItems(entry).filter((item) => !samePresentationItem(item, primary));
const afterOffers = (entry, { claimedOnly = false } = {}) =>
  entry.offers
    .filter(
      (offered) =>
        offered.reading.side === "after" &&
        offerReadings(offered).length === 0 &&
        offered.reading.entries.some((entry) => entry.visible) &&
        (!claimedOnly || offered.reading.claim),
    )
    .sort(compareMarginContributions);
export const secondaryCount = (entry, primary, { claimedOnly = false } = {}) => {
  const generated = secondaryReadings(entry, primary).length;
  const contributed = secondaryControls(entry, primary).length;
  const after = afterOffers(entry, { claimedOnly }).reduce(
    (count, offered) =>
      count + offered.reading.entries.filter((record) => record.visible).length,
    0,
  );
  if (claimedOnly && !entry.offers.some((offered) => offered.reading.claim))
    return generated;
  return generated + contributed + after;
};
// One peer is not overflow. It costs the same second circle as `…`, but the peer says
// what it does and is immediately usable. Ellipsis earns its place only from the third
// margin entry onward.
export const optionsOffered = (entry, primary, options = {}) =>
  secondaryCount(entry, primary, options) > RESTING_MARGIN_ENTRY_BUDGET - 1;

export function markerFace(entry) {
  const kinds = kindsIn(entry, { markerOnly: true });
  const choice = primaryReading(entry);
  const face = readingFace(choice);
  const faceCount = choice?.items.length ?? 0;
  return {
    kinds,
    face,
    label: faceCount > 1 ? `${face.label}s` : face.label,
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
        (left, right) => marginEntryStateRank(left) - marginEntryStateRank(right),
      )[0] ?? "idle"
  );
}

export const readingBehavior = (face) => (face.indication ? "status" : "disclosure");

// An aggregated reading takes its most urgent member's turn, as it already takes the
// most urgent member's workflow stage: one seat cannot say two things, and the reading
// a cluster is compact enough to hide is the one the reader most needs to see.
export const awaitingReader = (items) => items.some((item) => item.awaitsReader);
// The word beside the colour. Colour alone cannot carry a state, and the panel already
// calls this one "On you", so the margin says it the same way.
export const TURN_WORD = "On you";

export function readingContext(choice) {
  if (awaitingReader(choice?.items ?? [])) return TURN_WORD;
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
    ...secondaryControls(entry, primary).map((item) =>
      Object.freeze({ ...item, cluster: entry }),
    ),
    ...secondaryReadings(entry, primary).map((choice) => readingItem(entry, choice)),
    ...afterOffers(entry).flatMap((offered) =>
      offered.reading.entries
        .filter((record) => record.visible)
        .map((record) => ({
          offered,
          record,
        }))
        .sort(compareMarginEntryRecords)
        .map(({ record }) => contributionItem(offered, record, "margin", entry)),
    ),
  ];
}

function optionGroupProjection(
  entry,
  primary,
  optionsOpen,
  focusedOffer = null,
  forcedInlineKey = null,
) {
  const items = optionItems(entry, primary, focusedOffer);
  const unique = items.filter(
    (item, index) =>
      items.findIndex((candidate) => samePresentationItem(candidate, item)) === index,
  );
  // Peers may use the whole cluster budget only when no margin entry stands outside this
  // group. Reaction mode is the common case: it has neither a primary nor a reading
  // marker, so its six declared choices fit exactly. A reading-only target keeps its
  // marker visible, and that margin entry counts just as a contributed primary would.
  const peerCapacity = Math.max(
    0,
    EXPANDED_MARGIN_ENTRY_BUDGET -
      (!focusedOffer && (primary || markerFace(entry).kinds.length) ? 1 : 0),
  );
  const needsSpill = unique.length > peerCapacity;
  // The spill route consumes the last visible margin entry; it does not increase the
  // cluster beyond its budget. A fully expanded cluster is therefore either one
  // primary plus five peers, or one primary plus four peers plus the Page Map route.
  const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
  const hidden = Math.max(0, unique.length - visibleCapacity);
  const direct = unique.slice(0, visibleCapacity);
  const forcedThread =
    forcedInlineKey === entry.key
      ? unique.find((item) => item.choice?.kind === "comment")
      : null;
  // An open thread card keeps its owning Thread control on the page edge. When the
  // ordinary order would put it beyond the six-control budget, spill the last unrelated
  // peer in its place; the Page Map still retains every action in canonical order.
  if (forcedThread && direct.length && !direct.includes(forcedThread))
    direct[direct.length - 1] = forcedThread;
  const firstSpilled = unique.find((item) => !direct.includes(item));
  return Object.freeze({
    entry,
    entryKey: entry.key,
    label: `${entryEngaged(entry) ? "Actions" : "More options"} for ${entry.title}`,
    hidden: !optionsOpen || direct.length === 0,
    items: Object.freeze(unique),
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

export function clusterProjection(
  entry,
  { expandedKey = null, expandedOwner = null, forcedInlineKey = null } = {},
) {
  const focusedOffer =
    expandedKey === entry.key && expandedOwner
      ? (entry.offers.find((offered) => offered.key === expandedOwner) ?? null)
      : null;
  const primary = focusedOffer ? null : choosePrimary(entry);
  const secondaries = focusedOffer
    ? focusedOffer.reading.entries.filter((record) => record.visible).length
    : secondaryCount(entry, primary);
  const hasOptions = focusedOffer ? secondaries > 0 : optionsOffered(entry, primary);
  const optionsOpen =
    secondaries > 0 &&
    (!hasOptions || expandedKey === entry.key || entryEngaged(entry));
  return Object.freeze({
    primary,
    hasOptions,
    optionsOpen,
    options: optionGroupProjection(
      entry,
      primary,
      optionsOpen,
      focusedOffer,
      forcedInlineKey,
    ),
    direct: Object.freeze([...(primary ? [primary] : []), ...noticeItems(entry)]),
    entry,
    kind: "page",
    label: `Page actions for ${entry.title}`,
    moreLabel: `More options for ${entry.title}`,
    offers: entry.offers,
    hasPrimary: Boolean(primary),
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
      const items = group.items
        .filter(
          (item) =>
            item.marker === false || item.workflowFace || !represented.has(item.kind),
        )
        .sort(
          (left, right) =>
            KINDS[left.kind].priority - KINDS[right.kind].priority ||
            (left.kind === "comment" ? 0 : left.id.localeCompare(right.id)),
        );
      const entry = { ...group, items: Object.freeze(items) };
      const primary = choosePrimary(entry);
      const receipt = group.workflowReceipt;
      const workflowCarrier =
        primary && receipt
          ? Object.freeze({
              key: primary.record.key,
              owner: primary.record.owner,
              receipt,
            })
          : null;
      return Object.freeze({
        ...entry,
        workflowCarrier,
        items: Object.freeze(
          workflowCarrier
            ? items.filter((item) => !(item.workflowFace && item.carriesWorkflow))
            : items,
        ),
      });
    }),
  );
}
