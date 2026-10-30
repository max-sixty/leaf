/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture transfers typed initial values; transport transfers complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Internal producers transfer ownership on publication and retain no mutable borrow.
 * Public widget values are copied at their package boundary.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { createApplicationPublisher, share } from "./snapshot.js";
import {
  coordinateOf,
  foldProjection,
  foldedValue,
  foldWidgetStates,
  obligationValue,
  isProjectionEntry,
  stateCoordinate,
} from "../projection/model.js";
import { stampedState, sameStateDefinition } from "../registry-contract.js";
import {
  discussed,
  foldThreads,
  readThreadRecords,
  threadNames,
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
import { queueOffers } from "../queues.js";
import type {
  AuthoredMap,
  Thread,
  Event,
  Command,
  LocalMessage,
  LocalEdit,
  ThreadGesture,
  ActionSpec,
  PendingProjection,
  ProjectionEntry,
  ContentVersion,
} from "../../types/domain.js";
import type {
  ServedObligation,
  ServedQueueRow,
  ServedState,
  ServedSubject,
  ServedTodo,
  ServedView,
  ServedWorkflow,
} from "../../types/contract.js";
import type { Immutable } from "./snapshot.js";
type GestureState =
  | "sending"
  | "sending:logged"
  | "sending:presented"
  | "accepted"
  | "accepted:logged"
  | "accepted:presented"
  | "refused";
type Signal = "accept" | "refuse" | "log" | "present";

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

const LIFECYCLE: Record<GestureState, Partial<Record<Signal, GestureState>>> = {
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
const SENDING: Set<GestureState> = new Set([
  "sending",
  "sending:logged",
  "sending:presented",
]);
// Drawn from the gesture, because no adopted reading holds its receipt.
const DRAWN_LOCALLY: Set<GestureState> = new Set(["sending", "accepted"]);
// The states `release` retires.
const RELEASABLE: Set<GestureState> = new Set(["accepted:presented", "refused"]);
// Gestures still waiting for a document pass: either locally drawn before their
// receipt is logged, or logged in an adopted reading the page has not presented.
const UNPRESENTED: Set<GestureState> = new Set([
  "sending",
  "accepted",
  "sending:logged",
  "accepted:logged",
]);
/** One unresolved gesture. `admitted` is the log's event for it, known from the
 * POST's answer or from a reading, whichever came first.
 */
type LedgerEntry = {
  event: Command;
  localId: string;
  timestamp: string;
  order: number;
  projection: PendingProjection | null;
  // What the gesture draws in a thread, as foldThreads reads it: its message,
  // or the user's rewrite of one of theirs.
  thread: LocalMessage | LocalEdit | null;
  undoTarget: string | null;
  namedParent?: string;
  state: GestureState;
  admitted: Event | null;
};
// The log's id for a gesture this tab sent: its ledger entry's while it stands, its
// receipt's once released.
function admittedId(
  attempt: string | null | undefined,
  unresolved: readonly Immutable<LedgerEntry>[],
  receipts: readonly Immutable<Event>[],
) {
  if (!attempt) return null;
  return (
    unresolved.find((entry) => entry.event.attempt === attempt)?.admitted?.id ??
    receipts.find((receipt) => receipt.attempt === attempt)?.id ??
    null
  );
}
// `entry` after `signal`, or null once it leaves the ledger.
function advance(
  entry: LedgerEntry,
  signal: Signal,
  admitted: Event | null = null,
): LedgerEntry | null {
  const action = entry.event.kind === "action";
  if (signal === "present" && !action) return entry;
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:logged" && !action) return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}
/** The state the server serves (`served_state/state.schema.json`), whose type the
 * build generates. The server answers `active` and `browser` null only before a page's
 * first revision, when it serves no document a runtime could run in
 * (`http._serve_root`), so every answer this runtime reads has both. The names below
 * select from it.
 */
type AuthoritativeState = ServedState & {
  active: NonNullable<ServedState["active"]>;
  browser: NonNullable<ServedState["browser"]>;
};
/** A server view with its basis, the transport identity, left off.
 */
type PageView = Omit<ServedView, "basis">;
export type ObligationRecord = ServedObligation;
/** The selections `readObligations` publishes from a view's one list of obligation
 * records.
 */
type ObligationLists = {
  all: readonly ObligationRecord[];
  user: readonly ObligationRecord[];
  unanswered: readonly ObligationRecord[];
};
/** Published workflows include local sends, before the server can classify them: a
 * send has no stage the server knows yet, and a widget move no coordinate the server
 * has read.
 */
export type Workflow = Omit<ServedWorkflow, "stage" | "coordinate"> & {
  stage: ServedWorkflow["stage"] | "sending";
  coordinate: readonly (string | null)[] | null;
};
/** One to-do as the browser publishes it: as the server serves it, or ended by this
 * tab's Done, which the server has not dated yet.
 */
export type WireTodo = Omit<ServedTodo, "outcome"> & {
  outcome:
    | ServedTodo["outcome"]
    | {
        ts: null;
        detail: null;
      };
};
/** One row of On me or On <agent>, as `served_state.queues` serves it or this tab
 * places it: `owner` names the list. A widget or to-do row names its record
 * by `id`. `also`, on a record's row, names the other records the user answers at
 * its place; `live` says whether the agent has it in hand now; `obligation` and
 * `todo` are a widget row's and a to-do row's current record, which `localQueues`
 * joins on.
 */
type QueueItem = {
  kind: ServedQueueRow["kind"];
  id: string;
  owner: "user" | "agent";
  subject: ServedSubject;
  thread: string | null;
  also?: readonly string[];
  live: boolean;
  obligation?: ObligationRecord;
  todo?: WireTodo;
  [field: string]: unknown;
};
/** A finished item, in the Done of the list `owner` names: how it ended, when, and the
 * outcome's detail.
 */
type DoneItem = QueueItem & {
  state: "done" | "failed" | "dropped";
  ended: string | null;
  detail: string | null;
};
type WireQueues = {
  on_user: readonly QueueItem[];
  on_agent: readonly QueueItem[];
  done: readonly DoneItem[];
};
export type SemanticDocument = {
  revision: number | null;
  stamp?: number | null;
  live?: boolean;
  registry: Record<
    string,
    {
      "x-state"?: Record<string, ActionSpec>;
      [name: string]: unknown;
    }
  > & {
    $reactions?: {
      tokens: Record<
        string,
        {
          glyph: string;
          settles?: boolean;
        }
      >;
    };
    $states: Record<string, Record<string, StampedState>>;
  };
  authored: AuthoredMap;
  descriptors: ReadonlyMap<string, WidgetDescriptor>;
  messageBodies?: ReadonlyMap<
    string,
    {
      text: string;
      document?: {
        thread: string;
        message: string;
      };
    }
  >;
};
/** One verb's state as composition stamps it (`registry.contract.stamp_states`).
 */
type StampedState = {
  writer: "user" | "agent";
  definition: unknown;
};
export type WidgetDescriptor = {
  id: string;
  tag: string;
  document:
    | {
        kind: "page";
        revision: number;
      }
    | {
        kind: "thread";
        thread?: string;
        message?: string;
      };
  declaration: SemanticDocument["registry"][string];
  parent: {
    id: string;
    tag: string;
  } | null;
  ancestors: readonly {
    id: string;
    tag: string;
  }[];
  quoted: boolean;
};

// The server classifies a view's page and thread entries alike under that revision's
// registry, so every entry is one the view's widgets can draw.
function normalizedProjection(view: PageView | null | undefined) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, view?.thread.projection]) {
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
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}
const NO_OBLIGATIONS = {
  all: [] as ObligationRecord[],
  user: [] as ObligationRecord[],
  unanswered: [] as ObligationRecord[],
};
/* The admitted inventory owns membership and widget completion. Widget values come from
 * the same local-inclusive fold used by their controls, so a partial answer is
 * visible before its POST settles the obligation. */

function normalizedObligations(
  view: PageView | null,
  widgets: ReturnType<typeof foldWidgetStates>,
  document: SemanticDocument,
  projection: ReturnType<typeof foldProjection>,
  todos: ReturnType<typeof localTodos>,
): ObligationLists {
  const todoRecords = new Map(
    [...todos.open, ...todos.ended].map((todo) => [todo.id, todo]),
  );
  const all = (view?.obligations ?? []).map((item): ObligationRecord => {
    // Done and its Undo decide the user's task directly. Reuse the pending to-do
    // reading so the canonical inventory and its queue row show the same gesture.
    if (item.source.kind === "todo") {
      const todo = todoRecords.get(item.source.id) as NonNullable<
        ReturnType<typeof todoRecords.get>
      >;
      if (todo.state === "open" && item.status !== "open")
        return {
          ...item,
          answer: null,
          status: "open",
          next_actor: "user",
          end: null,
        };
      if (todo.state !== "open" && item.status === "open")
        return {
          ...item,
          answer: { value: todo.state, event: null },
          status: "answered",
          next_actor: null,
          end: null,
        };
      return item;
    }
    if (item.source.kind !== "widget") return item;
    const sourceId = item.source.id;
    const sourceUnit = item.source.unit;
    const widget = widgets.get(sourceId);
    const declaration = document.descriptors.get(item.source.id)?.declaration[
      "x-awaits"
    ] as
      | {
          value?: string;
        }
      | undefined;
    const verb = declaration?.value;
    if (!verb || !widget) return item;
    const completed =
      item.status === "answered" &&
      !(item.answer?.event && projection.pendingWithdrawals.has(item.answer.event.id));
    const { value, present } = obligationValue(widget, verb, completed, sourceUnit);
    const pendingValue =
      (
        widget.entries as {
          e: Event;
          unit: string;
        }[]
      ).some(
        ({ e, unit }) =>
          e.action === verb &&
          (sourceUnit === undefined || unit === sourceUnit) &&
          !Number.isInteger(e.seq),
      ) ||
      [...projection.pendingWithdrawals.values()].some(
        ({ e, unit }) =>
          e.widget === sourceId &&
          (sourceUnit === undefined || unit === sourceUnit) &&
          (e.action === verb || e.id === item.answer?.event?.id),
      );
    const answer = present
      ? { value, event: pendingValue ? null : (item.answer?.event ?? null) }
      : null;
    return { ...item, answer };
  });
  // A widget's record keeps the server's status and next actor, which only the log
  // decides.
  return {
    all,
    user: all.filter((item) => item.next_actor === "user"),
    unanswered: all.filter((item) => item.status === "open"),
  };
}
/* To-dos, open and ended, including Done this tab is sending or undoing. A to-do the
 * user is ending stands ended in the gesture's own turn, and one whose Done they are
 * undoing stands open again; a refused gesture leaves the ledger and so puts the to-do
 * back as the log has it. */

function localTodos(state: AuthoritativeState | null, local: readonly LedgerEntry[]) {
  const ending = new Set(
    local.flatMap(({ event }) => (event.kind === "todo_end" ? [event.todo] : [])),
  );
  const undoing = new Set(
    local.flatMap(({ event }) => (event.kind === "undo" ? [event.undoes] : [])),
  );
  const all = state?.browser.todos ?? [];
  const served = all.filter((todo) => todo.state === "open");
  const ended = all.filter((todo) => todo.state !== "open");

  const reopened = (todo: ServedTodo) =>
    todo.outcome !== null && undoing.has(todo.outcome.id);
  const open = [
    ...served,
    ...ended.filter(reopened).map((todo) => ({
      ...todo,
      state: "open" as const,
      outcome: null,
    })),
  ];

  const locallyEnded = (todo: WireTodo) => ending.has(todo.id);
  return {
    open: open.filter((todo) => !locallyEnded(todo)),
    ended: [
      ...ended.filter((todo) => !reopened(todo)),
      ...open.filter(locallyEnded).map((todo) => ({
        ...todo,
        state: "done" as const,
        running: null,
        outcome: { ts: null, detail: null },
      })),
    ],
  };
}

const NO_QUEUES: WireQueues = { on_user: [], on_agent: [], done: [] };
/** Attribute-set owners depend on the members their total render paints, as well
 * as on the selected ids. Capture supplies authored parentage; the complete
 * position fold supplies current parentage for declared descendants. Flat creates
 * supply additional members to their creator without becoming widget owners. */

function currentWidgetRelations(
  document: SemanticDocument,
  widgets: ReturnType<typeof foldWidgetStates>,
  projection: ReturnType<typeof foldProjection>,
) {
  const parents = new Map(
    [...document.descriptors].map(([id, descriptor]) => [id, descriptor.parent?.id]),
  );

  const owners: Map<string, Set<string>> = new Map();

  const memberships: Map<string, Record<string, string[]>> = new Map();
  // An owner's members under one attribute, which the first pass gave every owner.
  const members = (owner: string, attr: string) =>
    (memberships.get(owner) as Record<string, string[]>)[attr] as string[];
  for (const [id, widget] of widgets) {
    for (const [verb, spec] of widget.specs) {
      const record = spec.record;
      if (record?.kind === "attribute") {
        const named = owners.get(record.attr) ?? (new Set() as Set<string>);
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
    for (const id of document.descriptors.keys()) {
      const seen = new Set([id]);
      for (let parent = parents.get(id); parent; parent = parents.get(parent)) {
        if (seen.has(parent)) break;
        seen.add(parent);
        if (!named.has(parent)) continue;
        members(parent, attr).push(id);
        break;
      }
    }
    for (const { e, unit, spec } of projection.desired.values())
      if (spec.creates && named.has(e.widget) && !document.descriptors.has(unit))
        members(e.widget, attr).push(unit);
    for (const owner of named) members(owner, attr).sort();
  }
  return { parents, memberships };
}
/* What is on the user (On me), what is on the agent (On <agent>), and what is done:
 * the view's served lists (`served_state.queues`), with this tab's unresolved sends
 * placed against them. Every row but a to-do names an obligation record, so a send moves
 * an item the server listed only where the record is its own subject: a Done or its
 * undo moves a to-do between its list and done. What a send leaves anything else, such
 * as which obligations in its thread it answers, waits for the server's reading of it. This adds only the
 * records a send alone publishes (`localUpdates`): the answer it is owed, which stands
 * for every update the server listed open in its thread, and the resend a refused one
 * leaves. Nothing here selects a list again. */

function localQueues(
  served: WireQueues,
  workflows: readonly Workflow[],
  todos: ReturnType<typeof localTodos>,
  items: ObligationLists,
  local: readonly ObligationRecord[],
) {
  const record = new Map(items.all.map((item) => [item.id, item]));
  const inventoryAt = new Map(items.all.map((item, at) => [item.id, at]));
  const open = new Set(todos.open.map((todo) => todo.id));
  const ended = new Set(todos.ended.map((todo) => todo.id));
  const todoRecord = new Map(
    [...todos.open, ...todos.ended].map((todo) => [todo.id, todo]),
  );
  // The threads holding a send this tab has in flight.
  const sentIn = new Set(
    workflows.flatMap((workflow) =>
      workflow.stage === "sending" &&
      workflow.condition === null &&
      workflow.subject.kind === "thread"
        ? [workflow.thread]
        : [],
    ),
  );

  const obligationOf = (item: QueueItem) => {
    const current = record.get(item.id);
    if (!current) throw new Error(`Queue item ${item.id} names no obligation`);
    return current;
  };
  // Whether an item the server listed as open still stands open in this tab: a
  // record still on the list's side, unless it is an update in a thread this tab has
  // sent to since, whose own record stands for it.
  const standsOpen = (item: QueueItem) => {
    if (!namesRecord(item)) return open.has(item.id);
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
  const reopened = (item: DoneItem) =>
    namesRecord(item)
      ? obligationOf(item).status === "open" &&
        obligationOf(item).next_actor === item.owner
      : open.has(item.id);
  // Whether an item the server listed as open has ended in this tab.
  const endedHere = (item: QueueItem) =>
    namesRecord(item) ? obligationOf(item).status !== "open" : ended.has(item.id);

  const todoOf = (item: QueueItem) => {
    const local = todoRecord.get(item.id);
    if (!local) throw new Error(`Queue item ${item.id} names no to-do`);
    return local;
  };
  // A record's row carries this tab's record of its obligation, and a to-do's row
  // this tab's record of the to-do.
  const current = <T extends QueueItem>(item: T): T =>
    namesRecord(item)
      ? { ...item, obligation: obligationOf(item) }
      : { ...item, todo: todoOf(item) };

  const asOpen = ({
    state: _state,
    ended: _ended,
    detail: _detail,
    ...item
  }: DoneItem) => current(item as QueueItem);

  const asDone = (item: QueueItem): DoneItem => ({
    ...current(item),
    live: false,
    state:
      namesRecord(item) && obligationOf(item).status === "withdrawn"
        ? "dropped"
        : "done",
    ended: null,
    detail: null,
  });

  const reopenedFor = (owner: "user" | "agent") =>
    served.done.filter((item) => item.owner === owner && reopened(item));
  // A record this tab published, as the row the server would list it under.
  const localRow = (item: ObligationRecord): QueueItem => {
    const source = item.source as {
      kind: "update";
      subject: ServedSubject;
    };
    return current({
      kind: "update",
      id: item.id,
      owner: item.next_actor as "user" | "agent",
      subject: source.subject,
      thread: item.thread,
      also: [],
      live: false,
    });
  };
  return {
    on_user: [
      ...served.on_user.filter(standsOpen).map(current),
      ...reopenedFor("user").map(asOpen),
      ...local.filter((item) => item.next_actor === "user").map(localRow),
    ].toSorted(
      (a, b) =>
        onUserRank(a) - onUserRank(b) ||
        (namesRecord(a) && namesRecord(b)
          ? (inventoryAt.get(a.id) as number) - (inventoryAt.get(b.id) as number)
          : 0),
    ),
    on_agent: [
      ...served.on_agent
        .filter((item) => item.kind !== "todo" && standsOpen(item))
        .map(current),
      ...local.filter((item) => item.next_actor === "agent").map(localRow),
      ...served.on_agent
        .filter((item) => item.kind === "todo" && standsOpen(item))
        .map(current),
      ...reopenedFor("agent").map(asOpen),
    ],
    // Newest first, as the server serves it: what ended in this tab has just ended.
    done: [
      ...[...served.on_user, ...served.on_agent].filter(endedHere).map(asDone),
      ...served.done.filter((item) => !reopened(item)).map(current),
    ],
  };
}
/* The records this tab's sends publish before the server has read them, in the served
 * record's shape (`obligations.update_obligation`): the answer a message it is sending
 * is owed, one per thread for the newest, as the server's reply to the newest answers
 * every message before it; and the resend each refused message or widget move leaves.
 * Each local workflow names the record it serves. */

function localUpdates(workflows: readonly Workflow[]) {
  const newest: Map<string | null, Workflow> = new Map();
  for (const workflow of workflows)
    if (workflow.stage === "sending" && workflow.condition === null)
      newest.set(workflow.thread, workflow);

  const records: ObligationRecord[] = [];
  const named = workflows.map((workflow): Workflow => {
    if (workflow.stage !== "sending") return workflow;
    const refused = workflow.condition !== null;
    const owner = refused ? workflow : (newest.get(workflow.thread) as Workflow);
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
        status: "open",
        end: null,
        next_actor: refused ? "user" : "agent",
      });
    return { ...workflow, obligation: id };
  });
  return { workflows: named, records };
}
// The order the server lists On me in: widget obligations, to-dos, then updates to
// send again; records of a kind among
// themselves in the order the view's inventory holds them.
const onUserRank = (item: QueueItem) =>
  item.kind === "todo" ? 1 : item.kind === "update" ? 2 : 0;
// Every row but an agent-owned to-do names the canonical obligation inventory.
const namesRecord = (item: QueueItem) => item.kind !== "todo" || item.owner === "user";
type SemanticRoot = ReturnType<ReturnType<typeof createSemanticApplication>["read"]>;
type RootProjection = SemanticRoot["effective"]["projection"];
type MapValue<M> = M extends ReadonlyMap<unknown, infer V> ? V : never;
type WidgetEntries = {
  readonly classified: readonly MapValue<RootProjection["classified"]>[];
  readonly desired: readonly MapValue<RootProjection["actions"]>[];
  readonly undo: readonly NonNullable<
    SemanticRoot["effective"]["view"]
  >["undo"][number]["event"][];
};
type WidgetIndex = {
  readonly byWidget: ReadonlyMap<string, WidgetEntries>;
  readonly heldBy: ReadonlyMap<string, string>;
};
type WidgetGroup = {
  -readonly [K in keyof WidgetEntries]: WidgetEntries[K][number][];
};

// Every widget's share of the root's action entries and threads, grouped once per
// publication rather than filtered from the whole projection by each widget. The
// publisher shares each widget's group across publications, so a widget whose entries
// did not move reads the group it read before. Entries group by widget id alone: the
// selected server view already bounds page history to the captured revision and thread
// history to its frozen document, and widget ids are unique across both, so filtering
// again by the event's authored revision would discard carried decisions from an
// earlier revision.
function widgetIndex(root: SemanticRoot): WidgetIndex {
  const projection = root.effective.projection;

  const byWidget: Map<string, WidgetGroup> = new Map();

  const group = (widget: string) => {
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

  const heldBy: Map<string, string> = new Map();
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

const NO_ENTRIES: WidgetEntries = { classified: [], desired: [], undo: [] };
// Everything one widget's reading draws from the root, each part by identity.
function widgetInputs(
  root: SemanticRoot,
  index: WidgetIndex,
  { id, tag }: WidgetDescriptor,
) {
  return {
    registered: root.document.descriptors.get(id),
    states: root.document.registry.$states[tag],
    current: root.effective.widgets.get(id),
    memberships: root.effective.memberships.get(id),
    authored: root.document.authored.get(id),
    hostAvailable: root.effective.hostAvailable,
    ready: root.phase === "ready",
    entries: index.byWidget.get(id) ?? NO_ENTRIES,
    heldBy: index.heldBy.get(id) ?? null,
  };
}

function widgetReading(
  inputs: ReturnType<typeof widgetInputs>,
  descriptor: WidgetDescriptor,
) {
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
type SemanticPresentationPublication = object;
type PresentationLifecycle = {
  begin(): SemanticPresentationPublication;
  seal(publication: SemanticPresentationPublication): unknown;
};

export function createSemanticApplication({
  presentation,
}: {
  presentation?: PresentationLifecycle;
} = {}) {
  const initial = {
    document: {
      revision: null,
      registry: { $states: {} },
      authored: new Map(),
      descriptors: new Map(),
    } as SemanticDocument,
    authoritative: null as AuthoritativeState | null,
    unresolved: [] as LedgerEntry[],
    // The entries that left the ledger once a reading logged them. Each stays until the
    // first reading adopted after a document pass drew its receipt (`drawn`), so its
    // thread stays gestured through that pass, a failed one and its retry included, as
    // it was while the ledger held it.
    settled: [] as LedgerEntry[],
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: [] as ContentVersion[],
    phase: "waiting",
    // How the server answered the page's latest read: not yet (`waiting`), with a
    // reading the page adopted (`reached`), with nothing (`unreachable`, or `refused`
    // where it refused this tab's key), with an error of its own (`faulted`, whose
    // words `fault` keeps), or with one the page could not apply (`broken`). It is
    // what the page's status says about the server, and no semantic epoch.
    reach: "waiting" as
      "waiting" | "reached" | "unreachable" | "refused" | "faulted" | "broken",
    fault: null as string | null,
    hostAvailable: true,
    data: {
      version: null as string | null,
      sources: {} as Record<string, unknown>,
    },
    // Ephemeral typed values derived by mounted widgets; no server run or revision.
    outputs: {} as Record<
      string,
      Record<
        string,
        {
          contract: string;
          value: unknown;
        }
      >
    >,
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
  let dataTaken = -Infinity;
  let order = 0;
  // The attempts of `settled` and of the ledger whose receipts a document pass has drawn
  // (`present`). A settled entry among them leaves `settled` with the next adoption,
  // since a publication of its own would repaint the threads to show nothing new.
  const drawn: Set<string> = new Set();
  let publicationDepth = 0;

  let activePresentation: SemanticPresentationPublication | null = null;
  if (presentation) presentation.seal(presentation.begin());

  function derive(
    document: SemanticDocument,
    state: AuthoritativeState | null,
    unresolved: LedgerEntry[],
    settled: LedgerEntry[],
    markingRead: ContentVersion[],
    phase: string,
    hostAvailable: boolean,
  ) {
    const receipts = state?.browser.receipts ?? [];
    const local = unresolved.filter((entry) => DRAWN_LOCALLY.has(entry.state));
    const refused = unresolved.filter((entry) => entry.state === "refused");
    // The shown revision's server view, resolved here once for every reader of this
    // document's page state. Its basis is transport identity, which the adoption
    // boundary has already matched to the log reading; left in, a read that only moved
    // the log's sequence would publish a new semantic epoch.
    const served = state?.browser.views[String(document.revision)];

    const view: PageView | null = served
      ? (({ basis: _basis, ...rest }) => rest)(served)
      : null;
    const admitted = normalizedProjection(view);
    const classifiedIds = new Set(admitted.entries.map(({ e }) => e.id));
    // A revision may reuse a widget/verb with a different operation. Keep its pending
    // delivery, but stop drawing it against that new declaration. This tab wrote a
    // pending action's definition itself, so it draws while the shown declaration
    // still defines the same one; the server validates the durable payload. An undo
    // draws while its target draws: in the server's reading of this document, under
    // the id the log gave it, or as a pending action by the rule above.
    const drawsAction = (e: ProjectionEntry["e"]) => {
      const descriptor = document.descriptors.get(e.widget);
      const state = descriptor && stampedState(document.registry, descriptor.tag, e);
      return Boolean(state && sameStateDefinition(e.meaning?.state, state.definition));
    };
    const localProjections = local.flatMap((entry): PendingProjection[] => {
      const projection = entry.projection;
      if (!projection) return [];
      if (projection.kind !== "undo")
        return drawsAction(projection.e) ? [projection] : [];
      const { target } = projection;
      const targetId = admittedId(entry.undoTarget, unresolved, receipts);
      const pending = !Number.isInteger(target.e.seq);
      const draws =
        classifiedIds.has(targetId ?? target.e.id) ||
        (pending && drawsAction(target.e));
      return draws ? [{ ...projection, targetId }] : [];
    });
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections,
    });
    // A local comment belongs to the shown document even before saved history arrives.
    // Fold it through the same ledger and receipt path in every phase; collection.phase
    // still says whether this is a complete reading. The obligations need the log to say which
    // of them the page still holds, so their inventory waits for that reading.
    const ready = phase === "ready";
    // The ledger's thread gestures, in the order the user made them.
    const gestures = local.flatMap(({ event, thread, namedParent }): ThreadGesture[] =>
      thread
        ? [thread]
        : event.kind === "resolve" || event.kind === "unresolve"
          ? [{ ...event, ...(namedParent ? { localParent: namedParent } : {}) }]
          : event.kind === "undo"
            ? [event]
            : [],
    );
    const folded = foldThreads(view?.thread.threads ?? [], gestures);
    const widgets = foldWidgetStates(document.authored, projection);
    const { parents: widgetParents, memberships } = currentWidgetRelations(
      document,
      widgets,
      projection,
    );
    const todos = ready ? localTodos(state, local) : { open: [], ended: [] };
    const servedItems = ready
      ? normalizedObligations(view, widgets, document, projection, todos)
      : NO_OBLIGATIONS;
    // Thread attention is the server's reading, and one local fact adjusts it: a
    // refused send hands a thread the server left with the agent back to the user,
    // whose Retry it is.
    // The thread a gesture stands in. A message stands in the thread that draws it,
    // under its pending id or, once the log has it, its attempt. Until one does, a
    // comment opens the thread its own id names, and a reply joins the thread holding
    // its parent, or, where no thread holds it, the thread its parent names: a comment
    // of this tab's that the log refused, whose pending id named its thread. A rewrite
    // stands in its message's thread, a settlement in the thread it settles, and an
    // action in the thread whose markup froze its widget; a page widget's action stands
    // in none.
    const named = threadNames(folded);

    const threadOfEntry = ({ event, thread: drawn, namedParent }: LedgerEntry) => {
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

    const threadsOfEntry = (entry: LedgerEntry): readonly string[] => {
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
    const recovery: Map<string, string> = new Map();
    for (const entry of refused) {
      if (!isTurnEvent(entry.event) && entry.event.kind !== "action") continue;
      const thread = threadOfEntry(entry);
      if (thread) recovery.set(thread, `rejected:${entry.event.attempt}`);
    }
    const obligated = folded.map((thread): Thread => {
      const retry = recovery.get(thread.id);
      return retry && thread.attention?.kind !== "needs_user"
        ? {
            ...thread,
            attention: { kind: "needs_user", reason: "resend", workflow: retry },
          }
        : thread;
    });
    // A send this tab has not delivered, in the served workflow's shape, naming the
    // record it serves once `localUpdates` publishes it. A widget move owes no answer
    // until the server has read it, so only a refused one publishes a record: the
    // resend it leaves.
    const localWorkflow = (entry: LedgerEntry, rejected: boolean): Workflow | null => {
      const turn = isTurnEvent(entry.event) ? entry.thread : null;
      const thread = threadOfEntry(entry);

      const subject: Workflow["subject"] | null = turn
        ? thread === null
          ? null
          : { kind: "thread", id: thread }
        : entry.event.kind === "action"
          ? { kind: "widget", id: entry.event.widget }
          : null;
      if (!subject) return null;
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
        revision: entry.event.revision ?? document.revision,
        seq: entry.order,
        input: turn?.id ?? entry.localId,
        message: turn ? turnMessage(turn) : null,
        subject,
        thread,
        at_work: false,
        // The server's tuple, where the local fold keys a coordinate.
        coordinate: turn
          ? ["thread", thread]
          : entry.projection
            ? coordinateOf(entry.projection.coordinate)
            : null,
        obligation: null,
        stage: "sending",
        ts: turn?.ts ?? null,
        detail: null,
        detail_seq: null,
        agent: null,
        session: null,
        delivery_seq: null,
        delivery_session: null,
        delivery_turn: null,
        response: null,
        activity: [],
        condition: rejected ? { kind: "failed", operation: "delivery" } : null,
        started_by: [],
      };
    };
    const sends = localUpdates([
      ...(state ? state.workflows : []),
      ...local.flatMap((entry) =>
        isTurnEvent(entry.event) ? (localWorkflow(entry, false) ?? []) : [],
      ),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control or to-do when speculation ends.
      ...refused.flatMap((entry) => localWorkflow(entry, true) ?? []),
    ]);
    const workflows = sends.workflows;
    // The records this tab's sends publish join the served inventory once it is read.
    const localRecords = ready ? sends.records : [];
    const all = [...servedItems.all, ...localRecords];

    const items: ObligationLists = {
      all,
      user: [
        ...servedItems.user,
        ...localRecords.filter((item) => item.next_actor === "user"),
      ],
      unanswered: [...servedItems.unanswered, ...localRecords],
    };
    const threads = readThreadRecords(
      obligated,
      document,
      widgets,
      workflows,
      todos.open,
      items.all,
      markingRead,
      ready,
    );
    const selectedQueues = localQueues(
      ready ? (view?.queues ?? NO_QUEUES) : NO_QUEUES,
      workflows,
      todos,
      items,
      localRecords,
    );
    // A record's row reads the strongest workflow serving it, the first in the
    // published order.
    const serving: Map<string, Workflow> = new Map();
    for (const workflow of workflows)
      if (workflow.obligation !== null && !serving.has(workflow.obligation))
        serving.set(workflow.obligation, workflow);

    const contextual = <
      T extends {
        id: string;
        kind: string;
      },
    >(
      items: T[],
      onUser = false,
    ) =>
      items.map((item) => ({
        ...item,
        workflow: serving.get(item.id) ?? null,
        offers: queueOffers(item, ready, onUser),
      }));
    return {
      hostAvailable,
      projection,
      widgets,
      thread: {
        all: threads,
        collection: {
          phase,
          threads: threads.filter(discussed),
        },
        // The threads the gestures this tab's ledger still holds concern, refused ones
        // included until the reading they restore is drawn, and those the adopted
        // reading settled (held-news.js, `gesturedOn`).
        gestured: [...new Set([...unresolved, ...settled].flatMap(threadsOfEntry))],
      },
      obligations: { phase, ...items },
      // The agent's plan in force, as the server read it (`plans.plan_reading`).
      plan: ready ? (state?.browser.plan ?? null) : null,
      // On me (on the user), On <agent> (on the agent), and done: the served lists
      // with this tab's sends placed against them (`localQueues`).
      queues: {
        phase,
        on_user: contextual(selectedQueues.on_user, true),
        on_agent: contextual(selectedQueues.on_agent),
        done: contextual(selectedQueues.done),
      },
      // Part of the effective reading, so a read that changes only the view's
      // reports, publication time, or undo list opens an epoch and reaches its readers.
      view,
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

  function publish(changes: Partial<typeof initial>) {
    const prior = publisher.peek();
    const next = { ...prior, ...changes } as typeof initial;
    // Shared against the current reading, so a part whose contents did not move keeps
    // its identity: that is what an epoch and every selection compare.
    next.effective = share(
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
  const overtaken = (state: AuthoritativeState) => {
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
  const adoptable = (
    state: AuthoritativeState,
    candidate: SemanticDocument | number | null,
  ) => {
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
  // the ledger and the receipts rather than every publication.
  const unresolvedPart = publisher.select((root) => root.unresolved);
  const receiptsPart = publisher.select(
    (root) => root.authoritative?.browser.receipts ?? [],
  );
  const widgetsPart = publisher.select((root) => root.effective.widgets);

  const entry = (attempt: string) =>
    unresolvedPart.read().find((item) => item.event.attempt === attempt);
  const ledgerAndReceipts = () => [unresolvedPart.read(), receiptsPart.read()] as const;

  const update = (attempt: string, change: (entry: LedgerEntry) => LedgerEntry) =>
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
  const transition = (signal: Signal, admitted: Map<string, Event | null>) => {
    const left: LedgerEntry[] = [];
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

  const byAttempt = (receipts: readonly Event[]): Map<string, Event | null> =>
    new Map(
      receipts.flatMap((receipt) =>
        receipt.attempt ? [[receipt.attempt, receipt] as const] : [],
      ),
    );
  return Object.freeze({
    read: publisher.read,
    select: publisher.select,
    // Whether a publication is still running its synchronous subscribers. A renderer
    // driven by one paints after it, so every region has claimed this epoch before any
    // of them touches the document.
    publishing: () => publicationDepth > 0,
    // Version comparison receives a server projection already interpreted through the
    // requested revision's registry. Keep that admitted spec on the wire; the current
    // document contract must not reinterpret historical events.
    projectView(view: ServedView) {
      return foldProjection({
        ...normalizedProjection(view),
        pendingEntries: [],
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds: string[] | null = null) {
      if (eventIds === null) return widgetsPart.read();
      const wanted = new Set(eventIds);
      return publisher
        .select((root) =>
          foldWidgetStates(root.document.authored, {
            ...root.effective.projection,
            desired: new Map(
              [...root.effective.projection.desired].filter(([, entry]) =>
                wanted.has(entry.e.id),
              ),
            ),
          }),
        )
        .read();
    },
    // A widget's reading, recomputed only when one of the parts it draws moves, so a
    // publication about another widget or a thread costs each widget a comparison.
    selectWidget(descriptor: WidgetDescriptor) {
      let inputs: ReturnType<typeof widgetInputs> | null = null;

      let reading: ReturnType<typeof widgetReading>;
      return publisher.select((root) => {
        const next = widgetInputs(root, widgets.read(), descriptor);
        const keys = Object.keys(next) as (keyof typeof next)[];
        const prior = inputs;
        if (prior && keys.every((key) => next[key] === prior[key])) return reading;
        inputs = next;
        return (reading = widgetReading(next, descriptor));
      });
    },
    entry,

    identify(revision: number | null, stamp: number | null = null, live = false) {
      return publish({
        document: { ...publisher.peek().document, revision, stamp, live },
      });
    },

    setHostAvailable(hostAvailable: boolean) {
      return publish({ hostAvailable });
    },

    markRead(items: ContentVersion[]) {
      return publish({
        markingRead: [...publisher.peek().markingRead, ...items],
      });
    },

    settleMarkRead(items: ContentVersion[]) {
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

    captureDocument(document: SemanticDocument) {
      if (publisher.peek().authoritative)
        throw new Error("an admitted document changes only through adopt");
      return publish({ document });
    },

    setPhase(phase: string) {
      return publish({ phase });
    },

    setReach(reach: typeof initial.reach, fault: string | null = null) {
      const now = publisher.peek();
      if (now.reach === reach && now.fault === fault) return now;
      return publish({ reach, fault });
    },

    publishOutput(
      widget: string,
      output: string,
      reading: {
        contract: string;
        value: unknown;
      } | null,
    ) {
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
    acceptData(data: typeof initial.data, taken: number) {
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
    canAdopt(
      state: AuthoritativeState,
      document: SemanticDocument | number | null = null,
    ) {
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
    adopt(state: AuthoritativeState, document: SemanticDocument | null = null) {
      const prior = publisher.peek();
      if (!adoptable(state, document)) return false;
      const authoritative = state;
      // The reading and what it logs are one publication: the entries whose receipts
      // it holds stop drawing from the gesture as the log starts drawing them, and an
      // accepted one other than an action leaves with it.
      const { unresolved, left } = transition(
        "log",
        byAttempt(authoritative.browser.receipts),
      );
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
        reach: "reached",
        fault: null,
      });
      return true;
    },
    enqueue(
      event: Command,
      timestamp: string,
      plainText: string = event.text ?? event.token ?? "",
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
      const projection: PendingProjection | null =
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
          },
        ],
      });
      return entry(event.attempt);
    },

    // The POST accepted `attempt` as the log's `accepted`.
    accept(attempt: string, accepted: Event) {
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
    refuse(attempt: string) {
      const refused = entry(attempt);
      if (!refused) return [];
      const ledger = publisher.peek().unresolved;
      const gone = [refused.localId];
      const dependents: string[] = [];
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

    // A document pass carrying these receipts has run, which moves only the actions
    // among them, and publishes only where one moved.
    present(receipts: Event[]) {
      const { unresolved, settled } = publisher.peek();
      const attempts = byAttempt(receipts);
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
    release(attempts: Set<string>) {
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
    nameEvents(attempt: string) {
      const item = entry(attempt);
      if (!item) return true;
      const event = nameAdmitted(item.event, (pending) =>
        admittedId(pending, ...ledgerAndReceipts()),
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
