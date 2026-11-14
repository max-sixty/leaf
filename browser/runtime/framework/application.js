// @ts-check
/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture transfers typed initial values; transport transfers complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Internal producers transfer ownership on publication and retain no mutable borrow.
 * Public widget values are copied at their package boundary.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { hasObligationSource } from "../obligations/source.js";
import { VERB_WRITERS } from "../kernel-facts.js";
import { createApplicationPublisher, share, shareFold } from "./snapshot.js";
import {
  coordinateOf,
  foldProjection,
  foldedValue,
  widgetStateReader,
  obligationValue,
  isProjectionEntry,
  stateCoordinate,
} from "../projection/model.js";
import { stampedState, sameStateDefinition } from "../registry-contract.js";
import {
  discussed,
  foldThreads,
  threadRecordReader,
  threadNames,
  threadsBySection,
} from "../thread/model.js";
import {
  threadForAttempt,
  editForAttempt,
  isThreadEvent,
  isTurnEvent,
  nameAdmitted,
  namesEvent,
  namesPending,
  turnMessage,
} from "../pending/model.js";
import { PENDING } from "../thread/identity.js";
import { keptReadings } from "../kept.js";

/** @import {
 *   AuthoredMap, Thread, Event, Command, LocalMessage, LocalEdit, ThreadGesture,
 *   ActionSpec, PendingProjection, ProjectionEntry, ContentVersion
 * } from "../../types/domain.js" */
/** @import {
 *   ServedObligation, ServedQueueRow, ServedState, ServedSubject, ServedView,
 *   ServedWorkflow
 * } from "../../types/contract.js" */
/** @import { Immutable } from "./snapshot.js" */

/* The lifecycle of one unresolved gesture, from the turn that makes it to the
 * publication that retires it.
 *
 * Two things happen to a gesture independently, and either can come first: its POST
 * answers, accepting or refusing it, and readings of the log come to hold its receipt,
 * first adopted and then presented. A state therefore names both: `sending` or
 * `accepted`, then `:logged` once an adopted reading holds the receipt and
 * `:presented` once the document pass carrying one has run. A refusal ends the log's
 * part, since a refused attempt has no receipt to read.
 *
 * `sending` and `accepted` are drawn from the gesture; from `:logged` on, the log's
 * own event draws it. An entry leaves in one of three ways. A refused one waits for
 * `release`, once the reading it restores is on the page. An accepted one other than
 * an action leaves on reaching `accepted:logged`, in the same publication as the
 * reading that logs it, or as the acceptance where the reading came first. The log
 * draws it from then on, so the page draws that reading in one pass, and `settled`
 * keeps its thread gestured until that pass has run. An accepted action waits for that pass,
 * since its widget can hold a reading past it (a deferred widget): it goes on to
 * `accepted:presented` and waits there for `release`, which its owner calls once
 * those regions have committed. A signal a state has no edge for leaves it where it
 * is, and `present` moves only actions. */
/** @typedef {"sending"
 *   | "sending:logged"
 *   | "sending:presented"
 *   | "accepted"
 *   | "accepted:logged"
 *   | "accepted:presented"
 *   | "refused"} GestureState */

/** @typedef {"accept" | "refuse" | "log" | "present"} Signal */

/** @type {Record<GestureState, Partial<Record<Signal, GestureState>>>} */
const LIFECYCLE = {
  sending: {
    accept: "accepted",
    refuse: "refused",
    log: "sending:logged",
    present: "sending:presented",
  },
  "sending:logged": {
    accept: "accepted:logged",
    refuse: "refused",
    present: "sending:presented",
  },
  "sending:presented": { accept: "accepted:presented", refuse: "refused" },
  accepted: { log: "accepted:logged", present: "accepted:presented" },
  "accepted:logged": { present: "accepted:presented" },
  "accepted:presented": {},
  refused: {},
};

// Still waiting for its POST's answer: the delivery queue's and the traffic ledger's
// reading of the ledger.
/** @type {Set<GestureState>} */
const SENDING = new Set(["sending", "sending:logged", "sending:presented"]);
// Drawn from the gesture, because no adopted reading holds its receipt.
/** @type {Set<GestureState>} */
const DRAWN_LOCALLY = new Set(["sending", "accepted"]);
// The states `release` retires.
/** @type {Set<GestureState>} */
const RELEASABLE = new Set(["accepted:presented", "refused"]);
// Gestures still waiting for a document pass: either locally drawn before their
// receipt is logged, or logged in an adopted reading the page has not presented.
/** @type {Set<GestureState>} */
const UNPRESENTED = new Set([
  "sending",
  "accepted",
  "sending:logged",
  "accepted:logged",
]);

/** One unresolved gesture. `admitted` is the log's event for it, known from the
 * POST's answer or from a reading, whichever came first.
 *
 * @typedef {object} LedgerEntry
 * @property {Command} event
 * @property {string} localId
 * @property {string} timestamp
 * @property {number} order
 * @property {PendingProjection | null} projection
 * @property {LocalMessage | LocalEdit | null} thread
 *   What the gesture draws in a thread, as foldThreads reads it: its message,
 *   or the user's rewrite of one of theirs.
 * @property {string | null} undoTarget
 * @property {string} [namedParent]
 * @property {GestureState} state
 * @property {Event | null} admitted
 * @property {boolean} launching
 *   Whether the server had to launch the page's agent before it could take the
 *   gesture, as the tab read the server when it sent it.
 */

// The log's id for a gesture this tab sent: its ledger entry's while it stands, its
// receipt's, the logged event carrying its attempt, once released.
/**
 * @param {string | null | undefined} attempt
 * @param {readonly Immutable<LedgerEntry>[]} unresolved
 * @param {readonly Immutable<Event>[]} events
 */
function admittedId(attempt, unresolved, events) {
  if (!attempt) return null;
  return (
    unresolved.find((entry) => entry.event.attempt === attempt)?.admitted?.id ??
    events.findLast((event) => event.attempt === attempt)?.id ??
    null
  );
}

// `entry` after `signal`, or null once it leaves the ledger.
/**
 * @param {LedgerEntry} entry
 * @param {Signal} signal
 * @param {Event | null} [admitted]
 * @returns {LedgerEntry | null}
 */
function advance(entry, signal, admitted = null) {
  const action = entry.event.kind === "action";
  if (signal === "present" && !action) return entry;
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:logged" && !action) return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}

/** @typedef {{reach: "waiting", fault?: never}
 * | {reach: "reached" | "unreachable" | "refused" | "broken", fault?: never}
 * | {reach: "faulted", fault: string}} Reach */
/** The state the server serves (`served_state/state.schema.json`), whose type the
 * build generates. The server answers `active` and `browser` null only before a page's
 * first revision, when it serves no document a runtime could run in
 * (`http._serve_root`), so every answer this runtime reads has both. The names below
 * select from it.
 *
 * @typedef {ServedState & {
 *   active: NonNullable<ServedState["active"]>;
 *   browser: NonNullable<ServedState["browser"]>;
 *   data: {version: string, sources: Record<string, import("../data.js").SourceReading>};
 * }} AuthoritativeState
 */
/** A server view with its basis, the transport identity, left off.
 * @typedef {Omit<ServedView, "basis">} PageView */
/** @typedef {ServedObligation} ObligationRecord */
/** The selections `readObligations` publishes from a view's one list of obligation
 * records.
 *
 * @typedef {{
 *   all: readonly ObligationRecord[];
 *   user: readonly ObligationRecord[];
 *   unanswered: readonly ObligationRecord[];
 * }} ObligationLists
 */
/** Published workflows include local sends, before the server can classify them: a
 * `local` send waits on the agent, or is blocked where the server refused it, and a
 * widget move has no coordinate the server has read. A send `launching` waits for the
 * server to launch the page's agent first.
 *
 * @template T
 * @typedef {T extends unknown ? Omit<T, "coordinate"> & {
 *   coordinate: readonly (string | null)[] | null;
 *   local?: boolean;
 *   launching?: boolean;
 * } : never} PublishedWorkflow
 */
/** @typedef {PublishedWorkflow<ServedWorkflow>} Workflow
 */

/** One row of On Me, On <agent> or Done, as `served_state.queues` serves it or this
 * tab places it: `owner` names the list. A row names its record by `id`, and `also`
 * the other records the user answers at its place. `localQueues` joins the current
 * obligation record before publication (`CurrentQueueItem`), which says where the item
 * stands: whether the agent has it in hand, and how a done one ended.
 *
 * @typedef {import("../../types/contract.js").CompleteUnion<ServedQueueRow>} QueueItem
 * @typedef {QueueItem & {obligation: ObligationRecord}} CurrentQueueItem
 */

/**
 * @typedef {{
 *   on_user: readonly QueueItem[];
 *   on_agent: readonly QueueItem[];
 *   done: readonly QueueItem[];
 * }} WireQueues
 */

/**
 * @typedef {{
 *   revision: number | null;
 *   stamp?: number | null;
 *   live?: boolean;
 *   registry: Record<
 *     string,
 *     {
 *       "x-state"?: Record<string, ActionSpec>;
 *       [name: string]: unknown;
 *     }
 *   > & {
 *     $reactions?: { tokens: Record<string, { glyph: string; settles?: boolean }> };
 *     $states: import("../registry-contract.js").StampedRegistry["$states"];
 *   };
 *   authored: AuthoredMap;
 *   descriptors: ReadonlyMap<string, WidgetDescriptor>;
 *   messageBodies?: ReadonlyMap<
 *     string,
 *     { text: string; markup: string; document?: { thread: string; message: string } }
 *   >;
 * }} SemanticDocument
 */

/**
 * @typedef {{
 *   id: string;
 *   tag: string;
 *   document:
 *     | { kind: "page"; revision: number | null }
 *     | { kind: "thread"; thread?: string; message?: string };
 *   declaration: SemanticDocument["registry"][string];
 *   parent: { id: string; tag: string } | null;
 *   ancestors: readonly { id: string; tag: string }[];
 *   quoted: boolean;
 * }} WidgetDescriptor
 */

// The server classifies a view's page and thread entries alike under that revision's
// registry, so every entry is one the view's widgets can draw.
/** @param {readonly (PageView["document"]["projection"] | undefined)[]} projections */
function normalizedProjection(projections) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of projections) {
    if (!projection) continue;
    for (const wire of projection.entries) {
      const e = wire.event;
      const coordinate = stateCoordinate(...wire.coordinate);
      entries.push({
        coordinate,
        e,
        restated: wire.restated,
        absorbed: wire.absorbed,
        stands: wire.stands,
        scope: wire.scope,
        spec: wire.spec,
        unit: wire.coordinate[1],
        value: wire.value,
      });
    }
    actionIds.push(...projection.actions);
    reportIds.push(...projection.reports);
    desiredIds.push(...projection.desired);
  }
  return { entries, actionIds, reportIds, desiredIds };
}

// Each widget event and undo in the log, with the coordinate the view's projections
// classify it at, an undo at its target's, or null where they classify none: what the
// page's applied stamp counts (`projection/presentation.js`), and what `foldProjection`
// keeps classified as terminal where the view draws nothing for it.
/**
 * @param {PageView["document"]["projection"] | undefined} pageProjection
 * @param {PageView["thread"]["projection"] | undefined} threadProjection
 * @param {readonly Event[]} events
 * @returns {import("../../types/domain.js").Coverage[]}
 */
function logCoverage(pageProjection, threadProjection, events) {
  if (!pageProjection || !threadProjection) return [];
  /** @type {Map<string, readonly string[]>} */
  const coordinates = new Map();
  for (const projection of [pageProjection, threadProjection])
    for (const entry of projection.entries)
      coordinates.set(entry.event.id, entry.coordinate);
  return events.flatMap((event) => {
    const target =
      event.kind === "undo"
        ? event.undoes
        : Object.hasOwn(VERB_WRITERS, event.kind)
          ? event.id
          : null;
    return target === null
      ? []
      : [{ event, coordinate: coordinates.get(target) ?? null }];
  });
}

const NO_OBLIGATIONS = {
  all: /** @type {ObligationRecord[]} */ ([]),
  user: /** @type {ObligationRecord[]} */ ([]),
  unanswered: /** @type {ObligationRecord[]} */ ([]),
};

/* The admitted inventory owns membership and widget completion. Widget values come from
 * the same local-inclusive fold used by their controls, so a partial answer is
 * visible before its POST settles the obligation. */
/**
 * @param {PageView["obligations"] | undefined} obligations
 * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets
 * @param {SemanticDocument["descriptors"]} descriptors
 * @param {ReturnType<typeof foldProjection>["pendingWithdrawals"]} pendingWithdrawals
 * @returns {ObligationLists}
 */
function normalizedObligations(obligations, widgets, descriptors, pendingWithdrawals) {
  const all = (obligations ?? []).map(
    /** @returns {ObligationRecord} */ (item) => {
      if (!hasObligationSource(item, "widget")) return item;
      const sourceId = item.source.id;
      const sourceUnit = item.source.unit;
      const widget = widgets.get(sourceId);
      const declaration = /** @type {{ value?: string } | undefined} */ (
        descriptors.get(item.source.id)?.declaration["x-awaits"]
      );
      const verb = declaration?.value;
      if (!verb || !widget) return item;
      const completed =
        answered(item) &&
        !(item.answer?.event && pendingWithdrawals.has(item.answer.event.id));
      const { value, present } = obligationValue(widget, verb, completed, sourceUnit);
      const pendingValue =
        /** @type {{ e: Event; unit: string }[]} */ (widget.entries).some(
          ({ e, unit }) =>
            e.action === verb &&
            (sourceUnit === undefined || unit === sourceUnit) &&
            !Number.isInteger(e.seq),
        ) ||
        [...pendingWithdrawals.values()].some(
          ({ e, unit }) =>
            e.widget === sourceId &&
            (sourceUnit === undefined || unit === sourceUnit) &&
            (e.action === verb || e.id === item.answer?.event?.id),
        );
      const answer = present
        ? { value, event: pendingValue ? null : (item.answer?.event ?? null) }
        : null;
      return { ...item, answer };
    },
  );
  // A widget's record keeps where the server says it stands and its next actor, which
  // only the log decides.
  return {
    all,
    user: all.filter((item) => item.next_actor === "user"),
    unanswered: all.filter((item) => item.state !== "done"),
  };
}

// Whether the answer a record's source takes stands on it (`standing.answered`): the
// user's own answer, where an end the agent recorded is none.
/** @param {ObligationRecord} item */
const answered = (item) =>
  item.state === "done" && item.outcome === "done" && item.end === null;

/** @type {WireQueues} */
const NO_QUEUES = { on_user: [], on_agent: [], done: [] };

// The steps of `derive` that read the whole page, each a function of the inputs `step`
// hands it and nothing else (`createSemanticApplication`, `step`).
/** @param {ServedView | undefined} served @returns {PageView | null} */
const shownView = (served) =>
  served ? (({ basis: _basis, ...rest }) => rest)(served) : null;
/**
 * @param {PageView["document"]["projection"] | undefined} pageProjection
 * @param {PageView["thread"]["projection"] | undefined} threadProjection
 */
const admittedProjection = (pageProjection, threadProjection) =>
  normalizedProjection([pageProjection, threadProjection]);
/** @param {ReturnType<typeof normalizedProjection>} admitted */
const classifiedIdsOf = (admitted) => new Set(admitted.entries.map(({ e }) => e.id));
/**
 * @param {ReturnType<typeof normalizedProjection>} admitted
 * @param {ReturnType<typeof logCoverage>} coverage
 * @param {PendingProjection[]} pendingEntries
 */
const projectionOf = (admitted, coverage, ...pendingEntries) =>
  foldProjection({ ...admitted, coverage, pendingEntries });
/** @param {readonly Thread[] | undefined} threads @param {ThreadGesture[]} gestures */
const threadsOf = (threads, ...gestures) => foldThreads(threads ?? [], gestures);

/** Attribute-set owners depend on the members their total render paints, as well
 * as on the selected ids. Capture supplies authored parentage; the complete
 * position fold supplies current parentage for declared descendants. Flat creates
 * supply additional members to their creator without becoming widget owners. */
/**
 * @param {SemanticDocument["descriptors"]} descriptors
 * @param {ReturnType<typeof import("../projection/model.js").foldWidgetStates>} widgets
 * @param {ReturnType<typeof foldProjection>["desired"]} desired
 */
function currentWidgetRelations(descriptors, widgets, desired) {
  const parents = new Map(
    [...descriptors].map(([id, descriptor]) => [id, descriptor.parent?.id]),
  );
  /** @type {Map<string, Set<string>>} */
  const owners = new Map();
  /** @type {Map<string, Record<string, string[]>>} */
  const memberships = new Map();
  // An owner's members under one attribute, which the first pass gave every owner.
  /** @param {string} owner @param {string} attr */
  const members = (owner, attr) =>
    /** @type {string[]} */ (
      /** @type {Record<string, string[]>} */ (memberships.get(owner))[attr]
    );
  for (const [id, widget] of widgets) {
    for (const [verb, spec] of widget.specs) {
      const record = spec.record;
      if (record?.kind === "attribute") {
        const named = owners.get(record.attr) ?? /** @type {Set<string>} */ (new Set());
        named.add(id);
        owners.set(record.attr, named);
        const slots = memberships.get(id) ?? {};
        slots[record.attr] = [];
        memberships.set(id, slots);
      } else if (record?.kind === "position") {
        const state = widget.state[verb];
        if (state && "ranks" in state)
          for (const [container, units] of Object.entries(state.value))
            for (const unit of units) parents.set(unit, container);
      }
    }
  }
  for (const [attr, named] of owners) {
    for (const id of descriptors.keys()) {
      const seen = new Set([id]);
      for (let parent = parents.get(id); parent; parent = parents.get(parent)) {
        if (seen.has(parent)) break;
        seen.add(parent);
        if (!named.has(parent)) continue;
        members(parent, attr).push(id);
        break;
      }
    }
    for (const { e, unit, spec } of desired.values())
      if (spec.creates && named.has(e.widget) && !descriptors.has(unit))
        members(e.widget, attr).push(unit);
    for (const owner of named) members(owner, attr).sort();
  }
  return { parents, memberships };
}

/* What is on the user (On Me), what is on the agent (On <agent>), and what is done:
 * the view's served lists (`served_state.queues`), with this tab's unresolved sends
 * placed against them. Every row names an obligation record, and only the
 * agent ends a to-do, so a send moves an item the server listed only where the record
 * is its own subject. What a send leaves anything else, such as which obligations in
 * its thread it answers, waits for the server's reading of it. This adds only the
 * records a send alone publishes (`localUpdates`): the answer it is owed, which stands
 * for every update the server listed open in its thread, and the resend a refused one
 * leaves. Nothing here selects a list again. */
/**
 * @param {WireQueues} served
 * @param {readonly Workflow[]} workflows
 * @param {ObligationLists} items
 * @param {readonly ObligationRecord[]} local
 * @param {ReadonlyMap<string, ObligationRecord>} record each of `items` by its id
 */
function localQueues(served, workflows, items, local, record) {
  const inventoryAt = new Map(items.all.map((item, at) => [item.id, at]));
  // The threads holding a send this tab has in flight.
  const sentIn = new Set(
    workflows.flatMap((workflow) =>
      workflow.local &&
      workflow.state !== "blocked" &&
      workflow.subject.kind === "thread"
        ? [workflow.thread]
        : [],
    ),
  );
  /** @param {QueueItem} item */
  const obligationOf = (item) => {
    const current = record.get(item.id);
    if (!current) throw new Error(`Queue item ${item.id} names no obligation`);
    return current;
  };
  // Whether an item the server listed as open still stands open in this tab: a
  // record still on the list's side, unless it is an update in a thread this tab has
  // sent to since, whose own record stands for it.
  /** @param {QueueItem} item */
  const standsOpen = (item) => {
    const current = obligationOf(item);
    return (
      current.next_actor === item.owner &&
      !(
        current.source.kind === "update" &&
        current.thread !== null &&
        sentIn.has(current.thread)
      )
    );
  };
  // Whether an item the server listed as done stands open again in this tab.
  /** @param {QueueItem} item */
  const reopened = (item) =>
    obligationOf(item).state !== "done" && obligationOf(item).next_actor === item.owner;
  // Whether an item the server listed as open has ended in this tab.
  /** @param {QueueItem} item */
  const endedHere = (item) => obligationOf(item).state === "done";
  // A row carries this tab's record of its obligation.
  /** @param {QueueItem} item @returns {CurrentQueueItem} */
  const current = (item) => ({ ...item, obligation: obligationOf(item) });
  /** @param {"user" | "agent"} owner */
  const reopenedFor = (owner) =>
    served.done.filter((item) => item.owner === owner && reopened(item));
  // A record this tab published, as the row the server would list it under.
  /** @param {ObligationRecord} item @returns {CurrentQueueItem} */
  const localRow = (item) => {
    const source = /** @type {{ kind: "update"; subject: ServedSubject }} */ (
      item.source
    );
    return current({
      kind: "update",
      id: item.id,
      owner: /** @type {"user" | "agent"} */ (item.next_actor),
      subject: source.subject,
      thread: item.thread,
      also: [],
    });
  };
  return {
    on_user: [
      ...served.on_user.filter(standsOpen).map(current),
      ...reopenedFor("user").map(current),
      ...local.filter((item) => item.next_actor === "user").map(localRow),
    ].toSorted(
      (a, b) =>
        onUserRank(a) - onUserRank(b) ||
        /** @type {number} */ (inventoryAt.get(a.id)) -
          /** @type {number} */ (inventoryAt.get(b.id)),
    ),
    on_agent: [
      ...served.on_agent
        .filter((item) => item.kind !== "todo" && standsOpen(item))
        .map(current),
      ...local.filter((item) => item.next_actor === "agent").map(localRow),
      ...served.on_agent
        .filter((item) => item.kind === "todo" && standsOpen(item))
        .map(current),
      ...reopenedFor("agent").map(current),
    ],
    // Newest first, as the server serves it: what ended in this tab has just ended.
    done: [
      ...[...served.on_user, ...served.on_agent].filter(endedHere).map(current),
      ...served.done.filter((item) => !reopened(item)).map(current),
    ],
  };
}

/* The records this tab's sends publish before the server has read them, in the served
 * record's shape (`obligations.update_obligation`): the answer a message it is sending
 * is owed, one per thread for the newest, as the server's reply to the newest answers
 * every message before it; and the resend each refused message or widget move leaves.
 * Each local workflow names the record it serves. */
/** @param {readonly Workflow[]} workflows */
function localUpdates(workflows) {
  /** @type {Map<string | null, Workflow>} */
  const newest = new Map();
  for (const workflow of workflows)
    if (workflow.local && workflow.state !== "blocked")
      newest.set(workflow.thread, workflow);
  /** @type {ObligationRecord[]} */
  const records = [];
  const named = workflows.map(
    /** @returns {Workflow} */ (workflow) => {
      if (!workflow.local) return workflow;
      const refused = workflow.state === "blocked";
      const owner = refused
        ? workflow
        : /** @type {Workflow} */ (newest.get(workflow.thread));
      const id = `update:${owner.id}`;
      if (owner === workflow)
        records.push({
          id,
          source: { kind: "update", id: workflow.input, subject: workflow.subject },
          thread: workflow.thread,
          message: workflow.message,
          prompt: {
            text: null,
            target: "id" in workflow.subject ? workflow.subject.id : workflow.input,
          },
          answer: null,
          end: null,
          next_actor: refused ? "user" : "agent",
          state: workflow.state,
          reason: workflow.reason,
          outcome: null,
          seen: false,
          workflow: workflow.id,
        });
      return { ...workflow, obligation: id };
    },
  );
  return { workflows: named, records };
}

// The order the server lists On Me in: obligations, then updates to send again;
// records of a kind among themselves in the order the view's inventory holds them.
/** @param {QueueItem} item */
const onUserRank = (item) => (item.kind === "update" ? 1 : 0);

/** @typedef {ReturnType<ReturnType<typeof createSemanticApplication>["read"]>} SemanticRoot */
/** @typedef {SemanticRoot["effective"]["projection"]} RootProjection */
/** @template M @typedef {M extends ReadonlyMap<unknown, infer V> ? V : never} MapValue */
/**
 * @typedef {{
 *   readonly classified: readonly MapValue<RootProjection["classified"]>[];
 *   readonly desired: readonly MapValue<RootProjection["actions"]>[];
 *   readonly undo: readonly NonNullable<
 *     SemanticRoot["effective"]["view"]
 *   >["undo"][number]["event"][];
 * }} WidgetEntries
 */
/**
 * @typedef {{
 *   readonly byWidget: ReadonlyMap<string, WidgetEntries>;
 *   readonly heldBy: ReadonlyMap<string, string>;
 * }} WidgetIndex
 */
/** @typedef {{ -readonly [K in keyof WidgetEntries]: WidgetEntries[K][number][] }} WidgetGroup */

// Every widget's share of the root's action entries and threads, grouped once per
// publication rather than filtered from the whole projection by each widget. The
// publisher shares each widget's group across publications, so a widget whose entries
// did not move reads the group it read before. Entries group by widget id alone: the
// selected server view already bounds page history to the captured revision and thread
// history to its frozen document, and widget ids are unique across both, so filtering
// again by the event's authored revision would discard carried decisions from an
// earlier revision.
/** @param {SemanticRoot} root @returns {WidgetIndex} */
function widgetIndex(root) {
  const projection = root.effective.projection;
  /** @type {Map<string, WidgetGroup>} */
  const byWidget = new Map();
  /** @param {string} widget */
  const group = (widget) => {
    let entries = byWidget.get(widget);
    if (!entries)
      byWidget.set(widget, (entries = { classified: [], desired: [], undo: [] }));
    return entries;
  };
  for (const entry of projection.classified.values())
    if (!entry.terminal && entry.e.kind === "action")
      group(entry.e.widget).classified.push(entry);
  for (const entry of projection.actions.values())
    group(entry.e.widget).desired.push(entry);
  for (const { event } of root.effective.view?.undo ?? [])
    if (event.kind === "action" && !projection.pendingWithdrawals.has(event.id))
      group(event.widget).undo.push(event);
  /** @type {Map<string, string>} */
  const heldBy = new Map();
  for (const thread of root.effective.thread.all)
    if (
      !thread.resolved &&
      !thread.root.pending &&
      thread.root.holds &&
      !heldBy.has(thread.root.holds)
    )
      heldBy.set(thread.root.holds, thread.id);
  return { byWidget, heldBy };
}

/** @type {WidgetEntries} */
const NO_ENTRIES = { classified: [], desired: [], undo: [] };

// The parts of the root any widget's reading draws from (`widgetInputs`).
/** @param {SemanticRoot} root @param {WidgetIndex} index */
const widgetParts = (root, index) => ({
  descriptors: root.document.descriptors,
  states: root.document.registry.$states,
  widgets: root.effective.widgets,
  memberships: root.effective.memberships,
  authored: root.document.authored,
  hostAvailable: root.effective.hostAvailable,
  ready: root.phase === "ready",
  index,
});

// Everything one widget's reading draws from those parts, each by identity.
/**
 * @param {ReturnType<typeof widgetParts>} parts
 * @param {WidgetDescriptor} descriptor
 */
function widgetInputs(parts, { id, tag }) {
  return {
    registered: parts.descriptors.get(id),
    states: parts.states[tag],
    current: parts.widgets.get(id),
    memberships: parts.memberships.get(id),
    authored: parts.authored.get(id),
    hostAvailable: parts.hostAvailable,
    ready: parts.ready,
    entries: parts.index.byWidget.get(id) ?? NO_ENTRIES,
    heldBy: parts.index.heldBy.get(id) ?? null,
  };
}

/**
 * @param {ReturnType<typeof widgetInputs>} inputs
 * @param {WidgetDescriptor} descriptor
 */
function widgetReading(inputs, descriptor) {
  const currentDescriptor =
    JSON.stringify(inputs.registered) === JSON.stringify(descriptor);
  // A live revision connects and prepares replacement nodes before their complete
  // document capture is adopted. An id shared with the outgoing node must not lend the
  // replacement its old semantic state during that preparation window.
  const current = currentDescriptor ? inputs.current : undefined;
  const authored = currentDescriptor ? inputs.authored?.state : undefined;
  const classified = inputs.entries.classified.toSorted(
    (left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0),
  );
  const actionSpecs = descriptor.declaration["x-state"] ?? {};
  const states = inputs.states ?? {};
  const desired = inputs.entries.desired;
  const durableUndo = inputs.entries.undo;
  const localUndo = desired
    .map(({ e }) => e)
    .filter((event) => String(event.id).startsWith(PENDING));
  // The user acts only on the verbs they write; an agent's verb reaches this widget as
  // state and never as a control.
  const actions = Object.fromEntries(
    Object.entries(actionSpecs)
      .filter(([verb]) => states[verb]?.writer === "user")
      .map(([verb]) => [
        verb,
        {
          available:
            currentDescriptor &&
            inputs.hostAvailable &&
            inputs.ready &&
            !descriptor.quoted,
          unavailable: inputs.hostAvailable ? null : "no agent or server is available",
          history: classified.filter(({ e }) => e.action === verb).map(({ e }) => e),
          inForce: desired
            .filter(({ e }) => e.action === verb)
            .map(({ e, unit, value }) => ({ event: e, unit, value })),
          undo: inputs.hostAvailable
            ? [...localUndo, ...durableUndo].filter((event) => event.action === verb)
            : [],
        },
      ]),
  );

  const provenanceEntries = current?.entries ?? [];
  const provenance = Object.fromEntries(
    provenanceEntries.map(({ e, unit, value }) => [
      `${e.action}:${unit}`,
      { event: e, unit, value },
    ]),
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    memberships: currentDescriptor ? (inputs.memberships ?? {}) : {},
    thread: { heldBy: inputs.heldBy },
    provenance,
    actions,
  };
}

/** @typedef {object} SemanticPresentationPublication */

/**
 * @typedef {{
 *   begin(): SemanticPresentationPublication;
 *   seal(publication: SemanticPresentationPublication): unknown;
 * }} PresentationLifecycle
 */

/** @param {{ presentation?: PresentationLifecycle }} [options] */
export function createSemanticApplication({ presentation } = {}) {
  // Each publication's widget states and thread records, read again only where what
  // one reads changed (`kept.js`).
  const widgetStates = widgetStateReader();
  const threadRecords = threadRecordReader();
  // Each step of `derive` that reads the whole page, run again only where one of the
  // parts it reads changed (`kept.js`). A step left alone hands back what it made last
  // time, which the publisher has shared before and so need not compare again
  // (snapshot.js, `shareFold`): a publication about one thing costs what it changed.
  // A step is called with exactly the inputs it is kept by, so it can read nothing
  // they leave out.
  /** @type {ReturnType<typeof keptReadings<any>>} */
  const steps = keptReadings();
  /**
   * @template {unknown[]} A
   * @template R
   * @param {string} key
   * @param {(...inputs: A) => R} make
   * @param {A} inputs
   * @returns {R}
   */
  const step = (key, make, ...inputs) => steps.read(key, inputs, () => make(...inputs));
  const initial = {
    document: /** @type {SemanticDocument} */ ({
      revision: null,
      registry: { $states: {} },
      authored: new Map(),
      descriptors: new Map(),
    }),
    authoritative: /** @type {AuthoritativeState | null} */ (null),
    unresolved: /** @type {LedgerEntry[]} */ ([]),
    // The entries that left the ledger once a reading logged them. Each stays until the
    // first reading adopted after a document pass drew its receipt (`drawn`), so its
    // thread stays gestured through that pass, a failed one and its retry included, as
    // it was while the ledger held it.
    settled: /** @type {LedgerEntry[]} */ ([]),
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: /** @type {ContentVersion[]} */ ([]),
    phase: "waiting",
    // How the server answered the page's latest read: not yet (`waiting`), with a
    // reading the page adopted (`reached`), with nothing (`unreachable`, or `refused`
    // where it refused this tab's key), with an error of its own (`faulted`, whose
    // words `fault` keeps), or with one the page could not apply (`broken`). It is
    // what the page's status says about the server, and no semantic epoch.
    /** @type {Reach} */
    reach: { reach: "waiting" },
    hostAvailable: true,
    data: {
      version: /** @type {string | null} */ (null),
      /** @type {Record<string, import("../data.js").SourceReading>} */
      sources: {},
    },
    // Ephemeral typed values derived by mounted widgets; no server run or revision.
    outputs:
      /** @type {Record<string, Record<string, { contract: string; value: unknown }>>} */ ({}),
    effective: derive(
      {
        revision: null,
        registry: { $states: {} },
        authored: new Map(),
        descriptors: new Map(),
      },
      null,
      [],
      [],
      [],
      "waiting",
      true,
    ),
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  const widgets = publisher.select(widgetIndex);
  // Read by every widget's selection in place of the root, so a publication that moves
  // none of these parts, such as a comment's, reads no widget again.
  const parts = publisher.select((root) => widgetParts(root, widgets.read()));
  let dataTaken = -Infinity;
  let order = 0;
  // The attempts of `settled` and of the ledger whose receipts a document pass has drawn
  // (`present`). A settled entry among them leaves `settled` with the next adoption,
  // since a publication of its own would repaint the threads to show nothing new.
  /** @type {Set<string>} */
  const drawn = new Set();
  let publicationDepth = 0;
  /** @type {SemanticPresentationPublication | null} */
  let activePresentation = null;

  if (presentation) presentation.seal(presentation.begin());

  /**
   * @param {SemanticDocument} document
   * @param {AuthoritativeState | null} state
   * @param {LedgerEntry[]} unresolved
   * @param {LedgerEntry[]} settled
   * @param {ContentVersion[]} markingRead
   * @param {string} phase
   * @param {boolean} hostAvailable
   */
  function derive(
    document,
    state,
    unresolved,
    settled,
    markingRead,
    phase,
    hostAvailable,
  ) {
    const events = state?.events ?? [];
    const local = unresolved.filter((entry) => DRAWN_LOCALLY.has(entry.state));
    const refused = unresolved.filter((entry) => entry.state === "refused");
    // The shown revision's server view, resolved here once for every reader of this
    // document's page state. Its basis is transport identity, which the adoption
    // boundary has already matched to the log reading; left in, a read that only moved
    // the log's sequence would publish a new semantic epoch.
    const served = state?.browser.views[String(document.revision)];
    const view = step("view", shownView, served);
    const pageProjection = view?.document.projection;
    const threadProjection = view?.thread.projection;
    const admitted = step(
      "admitted",
      admittedProjection,
      pageProjection,
      threadProjection,
    );
    const coverage = step(
      "coverage",
      logCoverage,
      pageProjection,
      threadProjection,
      events,
    );
    const classifiedIds = step("classified", classifiedIdsOf, admitted);
    // A revision may reuse a widget/verb with a different operation. Keep its pending
    // delivery, but stop drawing it against that new declaration. This tab wrote a
    // pending action's definition itself, so it draws while the shown declaration
    // still defines the same one; the server validates the durable payload. An undo
    // draws while its target draws: in the server's reading of this document, under
    // the id the log gave it, or as a pending action by the rule above.
    /** @param {ProjectionEntry["e"]} e */
    const drawsAction = (e) => {
      const descriptor = document.descriptors.get(e.widget);
      const state = descriptor && stampedState(document.registry, descriptor.tag, e);
      return Boolean(state && sameStateDefinition(e.meaning?.state, state.definition));
    };
    const localProjections = local.flatMap(
      /** @returns {PendingProjection[]} */ (entry) => {
        const projection = entry.projection;
        if (!projection) return [];
        if (projection.kind !== "undo")
          return drawsAction(projection.e) ? [projection] : [];
        const { target } = projection;
        const targetId = admittedId(entry.undoTarget, unresolved, events);
        const pending = !Number.isInteger(target.e.seq);
        const draws =
          classifiedIds.has(targetId ?? target.e.id) ||
          (pending && drawsAction(target.e));
        return draws ? [{ ...projection, targetId }] : [];
      },
    );
    const projection = step(
      "projection",
      projectionOf,
      admitted,
      coverage,
      ...localProjections,
    );
    // A local comment belongs to the shown document even before saved history arrives.
    // Fold it through the same ledger and receipt path in every phase; collection.phase
    // still says whether this is a complete reading. The obligations need the log to say which
    // of them the page still holds, so their inventory waits for that reading.
    const ready = phase === "ready";
    // The ledger's thread gestures, in the order the user made them.
    const gestures = local.flatMap(
      /** @returns {ThreadGesture[]} */ ({ event, thread, namedParent }) =>
        thread
          ? [thread]
          : event.kind === "resolve" || event.kind === "unresolve"
            ? [{ ...event, ...(namedParent ? { localParent: namedParent } : {}) }]
            : event.kind === "undo"
              ? [event]
              : [],
    );
    const folded = step("threads", threadsOf, view?.thread.threads, ...gestures);
    const widgets = step("widgets", widgetStates, document.authored, projection);
    const { parents: widgetParents, memberships } = step(
      "relations",
      currentWidgetRelations,
      document.descriptors,
      widgets,
      projection.desired,
    );
    const servedItems = ready
      ? step(
          "obligations",
          normalizedObligations,
          view?.obligations,
          widgets,
          document.descriptors,
          projection.pendingWithdrawals,
        )
      : NO_OBLIGATIONS;
    // The thread a gesture stands in. A message stands in the thread that draws it,
    // under its pending id or, once the log has it, its attempt. Until one does, a
    // comment opens the thread its own id names, and a reply joins the thread holding
    // its parent, or, where no thread holds it, the thread its parent names: a comment
    // of this tab's that the log refused, whose pending id named its thread. A rewrite
    // stands in its message's thread, a settlement in the thread it settles, and an
    // action in the thread whose markup froze its widget; a page widget's action stands
    // in none.
    const named = threadNames(folded);
    /** @param {LedgerEntry} entry */
    const threadOfEntry = ({ event, thread: drawn, namedParent }) => {
      const drawnIn = drawn && named.get(drawn.id)?.id;
      if (drawnIn) return drawnIn;
      switch (event.kind) {
        case "comment":
          return drawn?.id ?? null;
        case "reply":
          return named.get(event.parent)?.id ?? event.parent;
        case "edit":
          return named.get(event.message)?.id ?? null;
        case "resolve":
        case "unresolve":
          return (
            named.get(event.parent)?.id ??
            (namedParent ? named.get(namedParent)?.id : null) ??
            null
          );
        case "action": {
          const held = document.descriptors.get(event.widget)?.document;
          return held?.kind === "thread" ? (held.thread ?? null) : null;
        }
        default:
          return null;
      }
    };
    // Every thread a gesture concerns. Once a reading logs it, that is the log's own
    // filing (the browser state's `thread_memberships`): every thread whose history it
    // changes, the one an answer closes and the one an earlier answer it replaces or
    // takes back had closed among them. Until then it is only what the page draws from
    // the gesture itself: the thread it stands in, or, for an undo, the threads of the
    // gesture it takes back, this tab's own entry or the log's. A thread an answer
    // closes changes in the reading that logs the answer, and the gesture concerns it
    // from that reading on.
    const logged = state?.browser.thread_memberships ?? {};
    /** @param {LedgerEntry} entry @returns {readonly string[]} */
    const threadsOfEntry = (entry) => {
      const filed = entry.admitted ? logged[entry.admitted.id] : undefined;
      if (filed) return filed;
      const { event } = entry;
      if (event.kind === "undo") {
        const target = unresolved.find(
          (each) => each.localId === event.undoes || each.admitted?.id === event.undoes,
        );
        return target ? threadsOfEntry(target) : (logged[event.undoes] ?? []);
      }
      const thread = threadOfEntry(entry);
      return thread ? [thread] : [];
    };
    // A refused send or move is the user's to retry from the thread it stood in.
    /** @type {Map<string, string>} */
    const recovery = new Map();
    for (const entry of refused) {
      if (!isTurnEvent(entry.event) && entry.event.kind !== "action") continue;
      const thread = threadOfEntry(entry);
      if (thread) recovery.set(thread, `rejected:${entry.event.attempt}`);
    }
    // A send this tab has not delivered, in the served workflow's shape, naming the
    // record it serves once `localUpdates` publishes it. A widget move owes no answer
    // until the server has read it, so only a refused one publishes a record: the
    // resend it leaves.
    /** @param {LedgerEntry} entry @param {boolean} rejected @returns {Workflow | null} */
    const localWorkflow = (entry, rejected) => {
      const turn = isTurnEvent(entry.event) ? entry.thread : null;
      const thread = threadOfEntry(entry);
      const subject =
        turn && thread !== null
          ? { kind: "thread", id: thread }
          : entry.event.kind === "action"
            ? { kind: "widget", id: entry.event.widget }
            : null;
      if (!subject) return null;
      /** @type {Omit<Workflow, "subject" | "revision" | "detail" | "detail_seq"> & {detail: null, detail_seq: null}} */
      const common = {
        id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
        seq: entry.order,
        input: turn?.id ?? entry.localId,
        message: turn ? turnMessage(turn) : null,
        thread,
        local: true,
        // The server's tuple, where the local fold keys a coordinate.
        coordinate: turn
          ? ["thread", thread]
          : entry.projection
            ? coordinateOf(entry.projection.coordinate)
            : null,
        obligation: null,
        state: rejected ? "blocked" : "waiting",
        reason: rejected ? "failed" : null,
        seen: false,
        ts: turn?.ts ?? null,
        detail: null,
        detail_seq: null,
        agent: null,
        session: null,
        delivery_seq: null,
        delivery_session: null,
        delivery_turn: null,
        response: null,
        started_by: [],
        launching: entry.launching,
      };
      if (entry.event.kind === "action")
        return {
          ...common,
          subject: { kind: "widget", id: entry.event.widget },
          revision: entry.event.revision,
        };
      return {
        ...common,
        subject: { kind: "thread", id: subject.id },
        revision: entry.event.revision ?? document.revision,
      };
    };
    const sends = localUpdates([
      ...(state ? state.workflows : []),
      ...local.flatMap((entry) =>
        isTurnEvent(entry.event) ? (localWorkflow(entry, false) ?? []) : [],
      ),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control when speculation ends.
      ...refused.flatMap((entry) => localWorkflow(entry, true) ?? []),
    ]);
    const workflows = sends.workflows;
    // Thread attention is the server's reading, and two local facts adjust it. A
    // refused send hands a thread the server left with the agent back to the user,
    // whose Retry it is. And a thread this tab opened, which the server has yet to
    // read, stands by the record its newest send in flight publishes.
    const servedIds = new Set(servedItems.all.map((item) => item.id));
    const servedUsers = new Set(servedItems.user.map((item) => item.id));
    const sendingIn = new Map(
      sends.records.flatMap((item) =>
        item.next_actor === "agent" && item.thread !== null
          ? [[item.thread, item.id]]
          : [],
      ),
    );
    const obligated = folded.map(
      /** @returns {Thread} */ (thread) => {
        const retry = recovery.get(thread.id);
        if (retry && !(thread.attention && servedUsers.has(thread.attention)))
          return { ...thread, attention: `update:${retry}` };
        const sent = sendingIn.get(thread.id);
        return sent &&
          thread.attention !== null &&
          thread.attention !== sent &&
          !servedIds.has(thread.attention)
          ? { ...thread, attention: sent }
          : thread;
      },
    );
    // The records this tab's sends publish join the served inventory once it is read.
    const localRecords = ready ? sends.records : [];
    const all = [...servedItems.all, ...localRecords];
    /** @type {ObligationLists} */
    const items = {
      all,
      user: [
        ...servedItems.user,
        ...localRecords.filter((item) => item.next_actor === "user"),
      ],
      unanswered: [...servedItems.unanswered, ...localRecords],
    };
    // Each obligation by its id, indexed as the reading arrives, so a reader asking for
    // one does no walk of its own.
    const obligationsById = new Map(all.map((item) => [item.id, item]));
    const threads = threadRecords(
      obligated,
      document,
      widgets,
      workflows,
      items.all,
      markingRead,
      ready,
    );
    // The thread each name names and the threads about each element, indexed as the
    // threads arrive, so a reader asking either does no walk of its own. Each index holds
    // a thread's place in `threads` rather than the record, so a record has one home
    // and sharing an index against the last reading compares numbers.
    const placeOf = new Map(threads.map((thread, index) => [thread, index]));
    const threadsNamed = new Map(
      [...threadNames(threads)].map(([name, thread]) => [
        name,
        /** @type {number} */ (placeOf.get(thread)),
      ]),
    );
    const selectedQueues = localQueues(
      ready ? (view?.queues ?? NO_QUEUES) : NO_QUEUES,
      workflows,
      items,
      localRecords,
      obligationsById,
    );
    // A record's row reads the strongest workflow serving it, the first in the
    // published order.
    /** @type {Map<string, Workflow>} */
    const serving = new Map();
    for (const workflow of workflows)
      if (workflow.obligation !== null && !serving.has(workflow.obligation))
        serving.set(workflow.obligation, workflow);
    /** @template {{ id: string; kind: QueueItem["kind"] }} T @param {T[]} items */
    const contextual = (items) =>
      items.map((item) => ({
        ...item,
        workflow: serving.get(item.id) ?? null,
      }));
    steps.done();
    return {
      hostAvailable,
      projection,
      widgets,
      thread: {
        all: threads,
        named: threadsNamed,
        bySection: threadsBySection(threads),
        collection: {
          phase,
          threads: threads.filter(discussed),
        },
        // The threads the gestures this tab's ledger still holds concern, refused ones
        // included until the reading they restore is drawn, and those the adopted
        // reading settled (held-news.js, `gesturedOn`).
        gestured: [...new Set([...unresolved, ...settled].flatMap(threadsOfEntry))],
      },
      obligations: { phase, ...items, byId: obligationsById },
      // The agent's plan in force, as the server read it (`plans.plan_reading`).
      plan: ready ? (state?.browser.plan ?? null) : null,
      // On Me (on the user), On <agent> (on the agent), and done: the served lists
      // with this tab's sends placed against them (`localQueues`).
      queues: {
        phase,
        on_user: contextual(selectedQueues.on_user),
        on_agent: contextual(selectedQueues.on_agent),
        done: contextual(selectedQueues.done),
      },
      // Part of the effective reading, so a read that changes only the view's
      // reports, publication time, or undo list opens an epoch and reaches its readers.
      view,
      coverage,
      memberships,
      widgetParents,
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved
        .filter((entry) => SENDING.has(entry.state))
        .map((entry) => entry.event.attempt),
      workflows,
      activity: state?.activity ?? null,
    };
  }

  /** @param {Partial<typeof initial>} changes */
  function publish(changes) {
    const prior = publisher.peek();
    const next = /** @type {typeof initial} */ ({ ...prior, ...changes });
    // The folds read the server's reading as the root holds it, so each record the new
    // answer left alone is the very object they read last time, and the record readers
    // that keep what they read (`threadRecordReader`) keep it too.
    next.authoritative = share(prior.authoritative, next.authoritative);
    // Shared against the current reading, so a part whose contents did not move keeps
    // its identity: that is what an epoch and every selection compare.
    next.effective = shareFold(
      prior.effective,
      derive(
        next.document,
        next.authoritative,
        next.unresolved,
        next.settled,
        next.markingRead,
        next.phase,
        next.hostAvailable,
      ),
    );
    next.data = share(prior.data, next.data);
    next.outputs = share(prior.outputs, next.outputs);
    next.semanticEpoch =
      prior.semanticEpoch +
      Number(
        next.effective !== prior.effective ||
          next.data !== prior.data ||
          next.outputs !== prior.outputs ||
          next.phase !== prior.phase ||
          next.document.revision !== prior.document.revision,
      );
    if (presentation) activePresentation = presentation.begin();
    publicationDepth += 1;
    try {
      return publisher.publish(next);
    } finally {
      publicationDepth -= 1;
      // Signals subscribers run synchronously. A subscriber may publish again in the
      // same stack, so only the outermost return seals the newest barrier opened by
      // that stack; sealing the older publication cannot acknowledge its replacement.
      if (presentation && publicationDepth === 0 && activePresentation) {
        const current = activePresentation;
        activePresentation = null;
        presentation.seal(current);
      }
    }
  }

  // An answer taken, read through, or activated before the one already adopted.
  /** @param {AuthoritativeState} state */
  const overtaken = (state) => {
    const prior = publisher.peek().authoritative;
    return Boolean(
      prior &&
      (state.taken < prior.taken ||
        state.browser.basis.through_seq < prior.browser.basis.through_seq ||
        state.active.revision < prior.active.revision),
    );
  };

  // An answer this document can take on with `revision` showing: not overtaken, and
  // holding a view of the revision that would be current.
  /**
   * @param {AuthoritativeState} state
   * @param {SemanticDocument | number | null} candidate
   */
  const adoptable = (state, candidate) => {
    const prior = publisher.peek();
    if (overtaken(state)) return false;
    const revision =
      typeof candidate === "number"
        ? candidate
        : (candidate?.revision ?? prior.document.revision);
    const view = state.browser.views[String(revision)];
    return Boolean(
      view &&
      view.basis.revision === revision &&
      view.basis.through_seq === state.browser.basis.through_seq,
    );
  };

  // The ledger's own readings select their parts, so a paint that reads one follows
  // the ledger and the log, whose events carrying an attempt are receipts, rather than
  // every publication.
  const unresolvedPart = publisher.select((root) => root.unresolved);
  const eventsPart = publisher.select((root) => root.authoritative?.events ?? []);
  const widgetsPart = publisher.select((root) => root.effective.widgets);
  /** @param {string} attempt */
  const entry = (attempt) =>
    unresolvedPart.read().find((item) => item.event.attempt === attempt);
  const ledgerAndLog = () =>
    /** @type {const} */ ([unresolvedPart.read(), eventsPart.read()]);
  /** @param {string} attempt @param {(entry: LedgerEntry) => LedgerEntry} change */
  const update = (attempt, change) =>
    publish({
      unresolved: publisher
        .peek()
        .unresolved.map((item) =>
          item.event.attempt === attempt ? change(item) : item,
        ),
    });
  // The ledger after `signal` reaches each attempt `admitted` names, with the log's
  // event for it (or null), the entries that left, with that event, and whether any
  // entry moved. The caller publishes it.
  /** @param {Signal} signal @param {Map<string, Event | null>} admitted */
  const transition = (signal, admitted) => {
    /** @type {LedgerEntry[]} */
    const left = [];
    let moved = false;
    const unresolved = publisher.peek().unresolved.flatMap((item) => {
      if (!admitted.has(item.event.attempt)) return [item];
      const event = admitted.get(item.event.attempt) ?? null;
      const next = advance(item, signal, event);
      if (next !== item) moved = true;
      if (!next) left.push({ ...item, admitted: item.admitted ?? event });
      return next ? [next] : [];
    });
    return { unresolved, left, moved };
  };
  // Each receipt among `events`, by the attempt it carries.
  /** @param {readonly Event[]} events @returns {Map<string, Event | null>} */
  const byAttempt = (events) =>
    new Map(
      events.flatMap((receipt) =>
        receipt.attempt ? [/** @type {const} */ ([receipt.attempt, receipt])] : [],
      ),
    );

  return Object.freeze({
    read: publisher.read,
    select: publisher.select,
    // Version comparison receives a server projection already interpreted through the
    // requested revision's registry. Keep that admitted spec on the wire; the current
    // document contract must not reinterpret historical events.
    /** @param {ServedView["document"]["projection"]} projection */
    projectDocument(projection) {
      return foldProjection({
        ...normalizedProjection([projection]),
        pendingEntries: [],
      });
    },
    // Every widget's current state, which the replay render check reads.
    selectWidgets() {
      return widgetsPart.read();
    },
    // A widget's reading, recomputed only when one of the parts it draws moves. A
    // publication that moves none of the parts any widget draws reads no widget, and
    // one about another widget costs each widget a comparison.
    /** @param {WidgetDescriptor} descriptor */
    selectWidget(descriptor) {
      /** @type {ReturnType<typeof widgetInputs> | null} */
      let inputs = null;
      /** @type {ReturnType<typeof widgetReading>} */
      let reading;
      return publisher.select((from) => {
        const next = widgetInputs(from, descriptor);
        const keys = /** @type {(keyof typeof next)[]} */ (Object.keys(next));
        const prior = inputs;
        if (prior && keys.every((key) => next[key] === prior[key])) return reading;
        inputs = next;
        return (reading = widgetReading(next, descriptor));
      }, parts);
    },
    entry,
    /** @param {number | null} revision @param {number | null} [stamp] */
    identify(revision, stamp = null, live = false) {
      return publish({
        document: { ...publisher.peek().document, revision, stamp, live },
      });
    },
    /** @param {boolean} hostAvailable */
    setHostAvailable(hostAvailable) {
      return publish({ hostAvailable });
    },
    /** @param {ContentVersion[]} items */
    markRead(items) {
      return publish({
        markingRead: [...publisher.peek().markingRead, ...items],
      });
    },
    /** @param {ContentVersion[]} items */
    settleMarkRead(items) {
      const remaining = publisher
        .peek()
        .markingRead.filter(
          (item) =>
            !items.some(
              (done) => done.message === item.message && done.version === item.version,
            ),
        );
      return publish({ markingRead: remaining });
    },
    /** @param {SemanticDocument} document */
    captureDocument(document) {
      if (publisher.peek().authoritative)
        throw new Error("an admitted document changes only through adopt");
      return publish({ document });
    },
    /** @param {string} phase */
    setPhase(phase) {
      return publish({ phase });
    },
    /** @param {Reach} reach */
    setReach(reach) {
      const now = publisher.peek();
      if (now.reach.reach === reach.reach && now.reach.fault === reach.fault)
        return now;
      return publish({ reach });
    },
    /**
     * @param {string} widget
     * @param {string} output
     * @param {{ contract: string; value: unknown } | null} reading
     */
    publishOutput(widget, output, reading) {
      const prior = publisher.peek();
      const values = { ...prior.outputs[widget] };
      if (reading === null) delete values[output];
      else values[output] = reading;
      const outputs = { ...prior.outputs };
      if (Object.keys(values).length) outputs[widget] = values;
      else delete outputs[widget];
      if (share(prior.outputs, outputs) === prior.outputs) return prior;
      return publish({ outputs });
    },
    // Source revisions are digests with no order, so a reading's data is ordered by
    // the moment the server took it: an answer taken before the one already accepted
    // is older, whichever order the two arrive in.
    /** @param {typeof initial.data} data @param {number} taken */
    acceptData(data, taken) {
      if (taken < dataTaken) return false;
      dataTaken = taken;
      if (data.version === publisher.peek().data.version) return false;
      publish({ data });
      return true;
    },
    // Whether this answer could be adopted with `revision` showing, asked without
    // adopting it. A live activation patches the document before it adopts, and a patch
    // is not something to undo, so the candidate is judged before the user's page is
    // touched. One definition read from two places, because two would be one edit away
    // from a document patched to a revision the answer it was patched for declines to
    // speak for.
    /**
     * @param {AuthoritativeState} state
     * @param {SemanticDocument | number | null} [document]
     */
    canAdopt(state, document = null) {
      return adoptable(state, document);
    },
    // Whether an answer is older than the one adopted, whichever revision it would
    // show. Transport drops such an answer before preparing anything for it.
    overtaken,
    // `revision` is the revision a live activation has just installed into this
    // document, and adopting the answer that named it is where its revision and stamp
    // become current.
    // The two are one reading: published apart, every widget renders once against a
    // state holding no view of the revision the document now shows — an empty
    // projection, indistinguishable for many widgets from their authored condition,
    // so the second publication changes nothing and never reaches them.
    /** @param {AuthoritativeState} state @param {SemanticDocument | null} [document] */
    adopt(state, document = null) {
      const prior = publisher.peek();
      if (!adoptable(state, document)) return false;
      const authoritative = state;
      // The reading and what it logs are one publication: the entries whose receipts
      // it holds stop drawing from the gesture as the log starts drawing them, and an
      // accepted one other than an action leaves with it.
      const { unresolved, left } = transition("log", byAttempt(authoritative.events));
      const settled = [
        ...prior.settled.filter((item) => !drawn.has(item.event.attempt)),
        ...left,
      ];
      for (const attempt of drawn)
        if (!unresolved.some((item) => item.event.attempt === attempt))
          drawn.delete(attempt);
      publish({
        document: document ?? prior.document,
        authoritative,
        unresolved,
        settled,
        phase: "ready",
        reach: { reach: "reached" },
      });
      return true;
    },
    /** @param {Command} event @param {string} timestamp @param {string} [plainText]
     * @param {boolean} [launching] */
    enqueue(
      event,
      timestamp,
      plainText = event.text ?? event.token ?? "",
      launching = false,
    ) {
      if (entry(event.attempt)) return null;
      const before = publisher.peek();
      const localId = PENDING + event.attempt;
      const thread = isThreadEvent(event)
        ? { ...threadForAttempt(event, timestamp), plainText }
        : event.kind === "edit"
          ? editForAttempt(event, timestamp)
          : null;
      const undoTarget =
        event.kind === "undo"
          ? before.unresolved.find((item) => item.localId === event.undoes)
          : null;
      const localTarget = undoTarget?.projection;
      const target =
        event.kind === "undo"
          ? ((localTarget?.kind !== "undo" ? localTarget : null) ??
            before.effective.projection.classified.get(event.undoes))
          : null;
      const widget =
        event.kind === "action" ? before.document.authored.get(event.widget) : null;
      // The widget's own captured declaration, as its reading (`widgetReading`) and the
      // projection's meaning check read it.
      const declaration =
        event.kind === "action"
          ? before.document.descriptors.get(event.widget)?.declaration
          : null;
      const spec =
        event.kind === "action" && widget
          ? declaration?.["x-state"]?.[event.action]
          : null;
      const unit =
        event.kind === "action" && spec
          ? spec.unit === "widget"
            ? event.widget
            : event.detail[spec.unit]
          : null;
      const localOrder = ++order;
      /** @type {PendingProjection | null} */
      const projection =
        event.kind === "undo" &&
        target &&
        isProjectionEntry(target) &&
        target.e.kind === "action"
          ? {
              kind: "undo",
              target,
              coordinate: target.coordinate,
              localOrder,
            }
          : event.kind === "action" && widget && spec && typeof unit === "string"
            ? {
                unit,
                spec,
                coordinate: stateCoordinate(event.widget, unit, event.action),
                localOrder,
                e: {
                  ...event,
                  id: localId,
                  meaning: {
                    state:
                      before.document.registry.$states[widget.tag]?.[event.action]
                        ?.definition,
                  },
                },
                value: spec.record ? foldedValue(event, spec.record) : event.action,
              }
            : null;
      publish({
        unresolved: [
          ...before.unresolved,
          {
            event: structuredClone(event),
            localId,
            timestamp,
            order: localOrder,
            projection,
            thread,
            undoTarget: undoTarget?.event.attempt ?? null,
            state: "sending",
            admitted: null,
            launching,
          },
        ],
      });
      return entry(event.attempt);
    },
    // The POST accepted `attempt` as the log's `accepted`.
    /** @param {string} attempt @param {Event} accepted */
    accept(attempt, accepted) {
      if (!entry(attempt)) return;
      const { unresolved, left } = transition("accept", new Map([[attempt, accepted]]));
      // A reading logged it first; it stays gestured unless a pass has drawn that.
      const settled = left.filter((item) => !drawn.delete(item.event.attempt));
      publish({
        unresolved,
        ...(settled.length && { settled: [...publisher.peek().settled, ...settled] }),
      });
    },
    // The POST refused `attempt`, or it can no longer be sent. What depends on it goes
    // with it: every gesture naming it by its pending id (`namesEvent`), such as an undo
    // of it, a reply to its message or a rewrite written over it, and so on down, since
    // a rewrite over that rewrite names only the one between. Returns those attempts.
    /** @param {string} attempt */
    refuse(attempt) {
      const refused = entry(attempt);
      if (!refused) return [];
      const ledger = publisher.peek().unresolved;
      const gone = [refused.localId];
      /** @type {string[]} */
      const dependents = [];
      for (let grew = true; grew;) {
        grew = false;
        for (const item of ledger)
          if (
            item.event.attempt !== attempt &&
            !dependents.includes(item.event.attempt) &&
            gone.some((id) => namesEvent(item.event, id))
          ) {
            dependents.push(item.event.attempt);
            gone.push(item.localId);
            grew = true;
          }
      }
      const { unresolved } = transition("refuse", new Map([[attempt, null]]));
      publish({
        unresolved: unresolved.filter(
          (item) => !dependents.includes(item.event.attempt),
        ),
      });
      return dependents;
    },
    // A document pass drawing these logged events has run, which moves only the actions
    // whose receipts are among them, and publishes only where one moved.
    /** @param {readonly Event[]} events */
    present(events) {
      const { unresolved, settled } = publisher.peek();
      const attempts = byAttempt(events);
      for (const item of [...settled, ...unresolved])
        if (attempts.has(item.event.attempt)) drawn.add(item.event.attempt);
      const { unresolved: next, moved } = transition("present", attempts);
      if (moved) publish({ unresolved: next });
    },
    // The entries no document pass has presented yet.
    unpresented: () =>
      unresolvedPart.read().filter((item) => UNPRESENTED.has(item.state)),
    // The entries `release` would retire now, in ledger order.
    releasable: () =>
      unresolvedPart.read().filter((item) => RELEASABLE.has(item.state)),
    // Retire those of `attempts` still in a releasable state.
    /** @param {Set<string>} attempts */
    release(attempts) {
      return publish({
        unresolved: publisher
          .peek()
          .unresolved.filter(
            (item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state)),
          ),
      });
    },
    // Just before a send, a gesture naming one this tab sent, by its pending id, names
    // it by the id the log gave it once the log has answered, in every field that names
    // an event (`nameAdmitted`): a reply's `parent`, the revision an edit is written over
    // (`base`), as a second rewrite over a first still sending is, an undo's target. A
    // renamed `parent` is kept as `namedParent`, which still finds the thread the reply
    // was drawn in. Returns false for a gesture that cannot be sent: an undo still naming
    // a gesture the log never took, since it would take back nothing the log knows.
    /** @param {string} attempt */
    nameEvents(attempt) {
      const item = entry(attempt);
      if (!item) return true;
      const event = nameAdmitted(item.event, (pending) =>
        admittedId(pending, ...ledgerAndLog()),
      );
      if (event !== item.event)
        update(attempt, (item) => ({
          ...item,
          ...(event.parent !== item.event.parent &&
          typeof item.event.parent === "string"
            ? { namedParent: item.event.parent }
            : {}),
          event,
        }));
      return !(event.kind === "undo" && namesPending(event));
    },
  });
}
