/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture supplies typed initial values; transport supplies complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { createApplicationPublisher, type Immutable } from "./snapshot.ts";
import {
  coordinateOf,
  foldProjection,
  foldedValue,
  foldWidgetStates,
  askValue,
  isProjectionEntry,
  stateCoordinate,
} from "../../skills/leaf/assets/runtime/projection/model.js";
import {
  stampedState,
  sameStateDefinition,
} from "../../skills/leaf/assets/runtime/registry-contract.js";
import {
  discussed,
  foldThreads,
  readThreadRecords,
  threadNames,
} from "../../skills/leaf/assets/runtime/thread/model.js";
import {
  threadForAttempt,
  editForAttempt,
  isThreadEvent,
  isTurnEvent,
  nameAdmitted,
  namesEvent,
  namesPending,
  turnMessage,
} from "../../skills/leaf/assets/runtime/pending/model.js";
import { PENDING } from "../../skills/leaf/assets/runtime/thread/identity.js";
import { queueOffers } from "../../skills/leaf/assets/runtime/queues.js";

import type {
  AuthoredMap,
  Thread,
  Event,
  Command,
  LocalMessage,
  LocalEdit,
  ThreadGesture,
  Message,
  WidgetEvent,
  LocalAction,
  ActionSpec,
  PendingProjection,
  ProjectionEntry,
  Coverage,
  ContentVersion,
} from "./domain.ts";

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
 * own event draws it. An entry leaves in exactly two ways. A refused one waits for
 * `release`, once the reading it restores is on the page. An accepted one leaves on
 * reaching `accepted:presented`, unless it is an action: an action's widget and the
 * projection chrome can hold a reading past the document pass (a drag, a deferred
 * widget), so an action waits there for `release`, which its owner calls once those
 * regions have committed. A signal a state has no edge for leaves it where it is. */
type GestureState =
  | "sending"
  | "sending:logged"
  | "sending:presented"
  | "accepted"
  | "accepted:logged"
  | "accepted:presented"
  | "refused";

type Signal = "accept" | "refuse" | "log" | "present";

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
const SENDING = new Set<GestureState>([
  "sending",
  "sending:logged",
  "sending:presented",
]);
// Drawn from the gesture, because no adopted reading holds its receipt.
const DRAWN_LOCALLY = new Set<GestureState>(["sending", "accepted"]);
// The states `release` retires.
const RELEASABLE = new Set<GestureState>(["accepted:presented", "refused"]);
// Gestures still waiting for a document pass: either locally drawn before their
// receipt is logged, or logged in an adopted reading the page has not presented.
const UNPRESENTED = new Set<GestureState>([
  "sending",
  "accepted",
  "sending:logged",
  "accepted:logged",
]);

/** One unresolved gesture. `admitted` is the log's event for it, known from the
 * POST's answer or from a reading, whichever came first. */
interface LedgerEntry {
  event: Command;
  localId: string;
  timestamp: string;
  order: number;
  projection: PendingProjection | null;
  /** What the gesture draws in a thread, as `foldThreads` reads it: its message, or
   * the user's rewrite of one of theirs. */
  thread: LocalMessage | LocalEdit | null;
  undoTarget: string | null;
  namedParent?: string;
  state: GestureState;
  admitted: Event | null;
}

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
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:presented" && entry.event.kind !== "action") return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}

interface WireProjection {
  entries: {
    event: WidgetEvent;
    coordinate: [string, string, string];
    restated: string[];
    absorbed: boolean;
    stands: boolean;
    scope: string;
    spec: Omit<ActionSpec, "writer">;
    value: unknown;
  }[];
  actions: string[];
  reports: string[];
  desired: string[];
}

/** A request and its contained answer. The source owns the canonical value;
 * identity includes its kind so authored ids and message ids cannot collide. */
interface AskRecord {
  id: string;
  source: { kind: "widget" | "reply"; id: string; tag?: string }
    | { kind: "approval"; version: number };
  thread: string | null;
  message: string | null;
  prompt: { text: string | null; target: string };
  answer: { value: unknown; event: Event | null } | null;
  /** `asks.py` owns the statuses; only a prose ask is `answered_elsewhere`. */
  status: "open" | "answered" | "answered_elsewhere" | "withdrawn";
  /** The agent's `leaf task end` that retired a prose ask: where the answer is, or why
   * the ask no longer applies. */
  end: { detail: string | null; event: Event } | null;
  next_actor: "user" | "agent" | null;
}

interface WireAsks {
  all: AskRecord[];
  user: AskRecord[];
  unanswered: AskRecord[];
}

/** One served workflow, as `served_state.browser.served_workflows` serializes it;
 * `AuthoritativeState.workflows` lists them strongest first. */
interface WireWorkflow {
  id: string;
  seq: number;
  revision: number | null;
  input: string | null;
  /** The message a thread input shows on: its own, or the one an edit rewrote. */
  message: string | null;
  subject: { kind: "thread" | "widget"; id: string };
  thread: string | null;
  /** Whether the agent is at work on it (`served_state.work.at_work`). */
  at_work: boolean;
  holds_thread: boolean;
  coordinate: unknown;
  answer: { kind: "reply" | "turn" | "markup" } | null;
  stage: "sent" | "queued" | "picked_up" | "working" | "replying" | "answered";
  ts: string | null;
  detail: string | null;
  agent: string | null;
  session: string | null;
  delivery_seq: number | null;
  delivery_session: string | null;
  delivery_turn: string | null;
  response: object | null;
  activity: readonly {
    kind: string;
    detail: string;
    ts: string;
    session: string | null;
    turn: string | null;
  }[];
  condition: {
    kind: "ended" | "interrupted" | "stale" | "failed";
    operation: "delivery" | "work" | "response";
  } | null;
  next_actor: "user" | "agent";
  /** The starts that take the move in hand, which the Stop hook reads. */
  started_by: readonly {
    item: string;
    session: string | null;
    turn: string | null;
    seq: number;
  }[];
  quiet: boolean;
  dropped: boolean;
}

/** Published workflows include local sends, before the server can classify quietness. */
export type Workflow = Omit<WireWorkflow, "quiet" | "dropped" | "stage"> & {
  stage: WireWorkflow["stage"] | "sending";
  quiet?: boolean;
  dropped?: boolean;
};

/** One to-do, as `served_state.browser` serves it (`work_reading.WorkReading.page_todos`): `todos` holds
 * the open ones on either side and `ended_todos` the ones that ended, with their
 * outcome. Asks are separate records and never appear in this list. */
interface WireTodo {
  id: string;
  owner: "agent" | "user";
  subject: { kind: "thread" | "widget"; id: string } | { kind: "page" };
  thread: string | null;
  title: string | null;
  state: "open" | "done" | "failed" | "dropped";
  ts: string;
  revision: number | null;
  /** The start that holds the to-do, while one does; one gone quiet holds nothing
   * (`activity._canonical_todos`). */
  running: {
    id: string;
    text: string;
    seq: number;
    ts: string;
    agent: string | null;
    session: string | null;
    turn: string | null;
  } | null;
  agent: string | null;
  session: string | null;
  outcome: { id?: string; ts: string | null; detail?: string | null } | null;
}

/** One item on Questions or Tasks, as `served_state.queues` serves it. An ask item
 * keeps its record; a to-do item the fields a row draws. */
interface QueueItem {
  kind: "ask" | "todo" | "resend" | "answer" | "work";
  id: string;
  owner?: "user" | "agent";
  subject: { kind: "thread" | "widget"; id: string } | { kind: "page" };
  thread: string | null;
  /** Whether the agent has it in hand now. */
  live: boolean;
  ask?: AskRecord;
  [field: string]: unknown;
}

/** A finished item: how it ended, when, and the outcome's detail. */
type DoneItem = QueueItem & {
  state: "done" | "failed" | "dropped";
  ended: string | null;
  detail: string | null;
};

interface WireQueues {
  questions: QueueItem[];
  tasks: QueueItem[];
  done: DoneItem[];
}

export interface SemanticDocument {
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
    $reactions?: { tokens: Record<string, {glyph: string; settles?: boolean}> };
    $states: Record<string, Record<string, StampedState>>;
  };
  authored: AuthoredMap;
  descriptors: ReadonlyMap<string, WidgetDescriptor>;
  messageBodies?: ReadonlyMap<
    string,
    { text: string; document?: { thread: string; message: string } }
  >;
}

/** One verb's state as composition stamps it (`registry.contract.stamp_states`). */
interface StampedState {
  writer: "user" | "agent";
  definition: unknown;
}

export interface WidgetDescriptor {
  id: string;
  tag: string;
  document:
    | { kind: "page"; revision: number }
    | { kind: "thread"; thread?: string; message?: string };
  declaration: SemanticDocument["registry"][string];
  parent: { id: string; tag: string } | null;
  ancestors: readonly { id: string; tag: string }[];
  quoted: boolean;
}

interface AuthoritativeState {
  taken: number;
  layer: { generation: string };
  active: { revision: number; version?: number | null; label?: string | null };
  versions?: { revision: number; version: number; url: string }[];
  revision_labels: Record<string, string>;
  events: Event[];
  workflows: WireWorkflow[];
  browser: {
    basis: { through_seq: number };
    views: Record<
      string,
      {
        basis: { revision: number; through_seq: number };
        document: {
          projection: WireProjection;
          asks: WireAsks;
        };
        /** The frozen threads as this revision reads them: its registry classifies
         * their widgets' decisions, and so the asks and attention those give. */
        thread: {
          threads: Thread[];
          projection: WireProjection;
          asks: WireAsks;
        };
        undo: { event: Event }[];
        coverage: Coverage[];
        reports: object[];
        published_at: string | null;
        queues: WireQueues;
        /** The asks approving this version waits on (`asks.approval_blocking`). */
        approval_blocking: string[];
      }
    >;
    /** Standing approvals across every stamp, for Threads' event timeline. */
    approval_history: Event[];
    receipts: Event[];
    /** Every thread whose history each logged event changes
     * (`thread_context.thread_memberships`). */
    thread_memberships: Record<string, string[]>;
    todos: WireTodo[];
    ended_todos: WireTodo[];
  };
  activity: unknown;
  reading?: string;
  agent?: string;
}

type ServerView = AuthoritativeState["browser"]["views"][string];
/** A server view with its basis, the transport identity, left off. */
type PageView = Omit<ServerView, "basis">;

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

// The selected server view already bounds page history to the captured revision and
// thread history to its frozen document. Widget ids are unique across both, so
// filtering again by the event's authored revision would incorrectly discard carried
// decisions from an earlier revision.
const appliesTo = (descriptor: WidgetDescriptor, event: WidgetEvent | LocalAction) =>
  event.widget === descriptor.id;

const NO_ASKS = {
  all: [] as AskRecord[],
  user: [] as AskRecord[],
  unanswered: [] as AskRecord[],
};

/* The admitted inventory owns membership and widget completion. Approval and its
 * undo draw their direct result immediately. Widget values come from
 * the same local-inclusive fold used by their controls, so a partial answer is
 * visible before its POST settles the ask. */
function normalizedAsks(
  view: PageView | null,
  widgets: ReturnType<typeof foldWidgetStates>,
  document: SemanticDocument,
  projection: ReturnType<typeof foldProjection>,
  local: readonly LedgerEntry[],
): WireAsks {
  const page = view?.document.asks;
  const thread = view?.thread.asks;
  const all = [...(page?.all ?? []), ...(thread?.all ?? [])].map(
    (ask): AskRecord => {
      if (ask.source.kind === "approval") {
        const version = ask.source.version;
        const undone = new Set(local.flatMap(({ event }) =>
          event.kind === "undo" ? [event.undoes] : []));
        const approving = local.some(({ event }) =>
          event.kind === "done" && event.version === version);
        if (approving) return { ...ask, answer: { value: true, event: null },
          status: "answered", next_actor: null };
        if (ask.answer?.event && undone.has(ask.answer.event.id))
          return { ...ask, answer: null, status: "open", next_actor: "user" };
        return ask;
      }
      if (ask.source.kind !== "widget") return ask;
      const sourceId = ask.source.id;
      const widget = widgets.get(sourceId);
      const declaration = document.descriptors.get(ask.source.id)?.declaration["x-awaits"] as
        { value?: string } | undefined;
      const verb = declaration?.value;
      if (!verb || !widget) return ask;
      const completed = ask.status === "answered" &&
        !(ask.answer?.event && projection.pendingWithdrawals.has(ask.answer.event.id));
      const { value, present } = askValue(widget, verb, completed);
      const pendingValue = (widget.entries as { e: Event }[]).some(({ e }) =>
        e.action === verb && !Number.isInteger(e.seq)) ||
        [...projection.pendingWithdrawals.values()].some(({ e }) =>
          e.widget === sourceId &&
          (e.action === verb || e.id === ask.answer?.event?.id));
      const answer = present
        ? { value, event: pendingValue ? null : ask.answer?.event ?? null }
        : null;
      return { ...ask, answer };
    },
  );
  const selection = (kind: "user" | "unanswered") => {
    const admitted = new Set([...(page?.[kind] ?? []), ...(thread?.[kind] ?? [])]
      .map((ask) => ask.id));
    return all.filter((ask) => ask.source.kind === "approval"
      ? kind === "user" ? ask.next_actor === "user" : ask.status === "open"
      : admitted.has(ask.id));
  };
  return { all, user: selection("user"), unanswered: selection("unanswered") };
}

/* To-dos, open and ended, including Done this tab is sending or undoing. A to-do the
 * user is ending stands ended in the gesture's own turn, and one whose Done they are
 * undoing stands open again; a refused gesture leaves the ledger and so puts the to-do
 * back as the log has it. */
function localTodos(
  state: AuthoritativeState | null,
  local: readonly LedgerEntry[],
) {
  const ending = new Set(
    local.flatMap(({ event }) => (event.kind === "todo_end" ? [event.todo] : [])),
  );
  const undoing = new Set(
    local.flatMap(({ event }) => (event.kind === "undo" ? [event.undoes] : [])),
  );
  const served = state?.browser.todos ?? [];
  const ended = state?.browser.ended_todos ?? [];
  const reopened = (todo: WireTodo) =>
    todo.outcome !== null && undoing.has(todo.outcome.id ?? "");
  const open = [
    ...served,
    ...ended
      .filter(reopened)
      .map((todo) => ({ ...todo, state: "open" as const, outcome: null })),
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

const NO_QUEUES: WireQueues = { questions: [], tasks: [], done: [] };

/* What is on the user (Questions), what is on the agent (Tasks), and what is done:
 * the view's served lists (`served_state.queues`), with this tab's unresolved sends
 * placed against them. A send moves an item the server listed only where the item is
 * its own subject: a Done or its undo moves a to-do between its list and done, and an
 * approval or its undo moves the approval ask. What a send leaves anything else, such
 * as which asks in its thread it answers, waits for the server's reading of it. This
 * adds only the items a send alone implies: its own answer owed, which stands for the
 * response its thread was already owed, and the resend a refused one leaves. Nothing
 * here selects a list again. */
function localQueues(
  served: WireQueues,
  threads: readonly Pick<Thread, "id" | "resolved" | "attention">[],
  workflows: readonly Workflow[],
  todos: ReturnType<typeof localTodos>,
  asks: WireAsks,
) {
  const record = new Map(asks.all.map((ask) => [ask.id, ask]));
  const asked = new Map(asks.all.map((ask, at) => [ask.id, at]));
  const open = new Set(todos.open.map((todo) => todo.id));
  const ended = new Set(todos.ended.map((todo) => todo.id));
  const byThread = new Map(threads.map((thread) => [thread.id, thread]));
  // The forward sends still in flight; a refused one is the user's resend, below.
  const sending = workflows.filter(
    (workflow) =>
      workflow.stage === "sending" &&
      workflow.next_actor === "agent" &&
      workflow.subject.kind === "thread",
  );
  const resent = new Set(sending.map((workflow) => workflow.thread));
  const retrying = (thread: string) => {
    const reading = byThread.get(thread);
    return Boolean(
      reading &&
      !reading.resolved &&
      reading.attention?.kind === "needs_user" &&
      reading.attention.reason === "resend",
    );
  };
  const askOf = (item: QueueItem) => {
    const local = record.get(item.id);
    if (!local) throw new Error(`Queue item ${item.id} names no ask`);
    return local;
  };
  // Whether an item the server listed as open still stands open in this tab.
  const standsOpen = (item: QueueItem) => {
    switch (item.kind) {
      case "ask":
        return askOf(item).next_actor === "user";
      case "todo":
        return open.has(item.id);
      case "resend":
        return item.thread === null || retrying(item.thread);
      case "answer":
        return !resent.has(item.thread);
      default:
        return true;
    }
  };
  // Whether an item the server listed as done stands open again in this tab.
  const reopened = (item: DoneItem) =>
    item.kind === "ask"
      ? askOf(item).status === "open" && askOf(item).next_actor === "user"
      : open.has(item.id);
  // Whether an item the server listed as open has ended in this tab.
  const endedHere = (item: QueueItem) =>
    item.kind === "ask"
      ? askOf(item).status !== "open"
      : item.kind === "todo" && ended.has(item.id);
  // An ask item carries this tab's record of its ask.
  const current = <T extends QueueItem>(item: T): T =>
    item.kind === "ask" ? { ...item, ask: askOf(item) } : item;
  const asOpen = ({ state: _state, ended: _ended, detail: _detail, ...item }: DoneItem) =>
    current(item as QueueItem);
  const asDone = (item: QueueItem): DoneItem => ({
    ...current(item),
    live: false,
    state:
      item.kind === "ask" && askOf(item).status === "withdrawn"
        ? "dropped"
        : "done",
    ended: null,
    detail: null,
  });
  const listed = new Set(
    [...served.questions, ...served.tasks].map((item) => `${item.kind}:${item.id}`),
  );
  const resend = (id: string, subject: QueueItem["subject"], thread: string | null) =>
    listed.has(`resend:${id}`)
      ? []
      : [{ kind: "resend" as const, id, subject, thread, live: false }];
  const reopenedFor = (owner: "user" | "agent") =>
    served.done.filter((item) => (item.owner ?? "user") === owner && reopened(item));
  return {
    questions: [
      ...served.questions.filter(standsOpen).map(current),
      ...reopenedFor("user").map(asOpen),
      ...threads.flatMap((thread) =>
        retrying(thread.id)
          ? resend(thread.id, { kind: "thread", id: thread.id }, thread.id)
          : [],
      ),
      ...workflows.flatMap((workflow) =>
        workflow.next_actor === "user" && workflow.thread === null
          ? resend(workflow.id, workflow.subject, null)
          : [],
      ),
    ].toSorted(
      (a, b) =>
        questionsRank(a) - questionsRank(b) ||
        (a.kind === "ask" && b.kind === "ask" ? asked.get(a.id)! - asked.get(b.id)! : 0),
    ),
    tasks: [
      ...served.tasks.filter((item) => item.kind !== "todo" && standsOpen(item)),
      // One answer per thread, as the server lists one for the newest turn owed.
      ...sending
        .filter((workflow, at) =>
          sending.slice(at + 1).every((later) => later.thread !== workflow.thread),
        )
        .map((workflow) => ({
          kind: "answer" as const,
          id: workflow.id,
          subject: workflow.subject,
          thread: workflow.thread,
          live: false,
          answer: workflow.answer,
          stage: workflow.stage,
        })),
      ...served.tasks.filter((item) => item.kind === "todo" && standsOpen(item)),
      ...reopenedFor("agent").map(asOpen),
    ],
    done: [
      ...served.done.filter((item) => !reopened(item)).map(current),
      ...[...served.questions, ...served.tasks].filter(endedHere).map(asDone),
    ].toSorted((a, b) => Number(a.kind === "todo") - Number(b.kind === "todo")),
  };
}

// The order the server lists Questions in: asks, to-dos, then resends; asks among
// themselves in the order the view's ask inventory holds them.
const questionsRank = (item: QueueItem) =>
  item.kind === "ask" ? 0 : item.kind === "todo" ? 1 : 2;

function widgetReading(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
) {
  const registered = root.document.descriptors.get(descriptor.id);
  const currentDescriptor = JSON.stringify(registered) === JSON.stringify(descriptor);
  // A live revision connects and prepares replacement nodes before their complete
  // document capture is adopted. An id shared with the outgoing node must not lend the
  // replacement its old semantic state during that preparation window.
  const current = currentDescriptor
    ? root.effective.widgets.get(descriptor.id)
    : undefined;
  const authored = currentDescriptor
    ? root.document.authored.get(descriptor.id)?.state
    : undefined;
  const declaration = descriptor.declaration;
  const actionSpecs = declaration["x-state"] ?? {};
  const states = root.document.registry.$states[descriptor.tag] ?? {};
  const projection = root.effective.projection;
  const classified = [...projection.classified.values()]
    .filter(
      ({ e, terminal }) => !terminal && e.kind === "action" && appliesTo(descriptor, e),
    )
    .sort((left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0));
  const desired = [...projection.actions.values()].filter(({ e }) =>
    appliesTo(descriptor, e),
  );
  const durableUndo = (root.effective.view?.undo ?? [])
    .map((candidate) => candidate.event)
    .filter(
      (event: Event) =>
        event.kind === "action" &&
        appliesTo(descriptor, event) &&
        !projection.pendingWithdrawals.has(event.id),
    );
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
            root.effective.hostAvailable &&
            root.phase !== "waiting" &&
            !descriptor.quoted,
          unavailable: root.effective.hostAvailable
            ? null
            : "no agent or server is available",
          history: classified.filter(({ e }) => e.action === verb).map(({ e }) => e),
          standing: desired
            .filter(({ e }) => e.action === verb)
            .map(({ e, unit, value }) => ({ event: e, unit, value })),
          undo: root.effective.hostAvailable
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
  const holdingThread = root.effective.thread.all.find(
    (thread) =>
      !thread.resolved && !thread.root.pending && thread.root.holds === descriptor.id,
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    thread: { heldBy: holdingThread?.id ?? null },
    provenance,
    actions,
  };
}

interface SemanticPresentationPublication {
  readonly semanticEpoch: number;
}

interface PresentationLifecycle {
  begin(semanticEpoch: number): SemanticPresentationPublication;
  seal(publication: SemanticPresentationPublication): unknown;
}

export function createSemanticApplication({
  presentation,
}: { presentation?: PresentationLifecycle } = {}) {
  const initial = {
    document: {
      revision: null,
      registry: { $states: {} },
      authored: new Map(),
      descriptors: new Map(),
    } as SemanticDocument,
    authoritative: null as AuthoritativeState | null,
    unresolved: [] as LedgerEntry[],
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: [] as ContentVersion[],
    phase: "waiting",
    hostAvailable: true,
    data: { version: null as string | null, sources: {} as Record<string, unknown> },
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
      "waiting",
      true,
    ),
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  let dataTaken = -Infinity;
  let order = 0;
  let signature = semanticSignature([initial.effective, initial.data, initial.phase]);
  let publicationDepth = 0;
  let activePresentation: SemanticPresentationPublication | null = null;

  if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));

  function derive(
    document: SemanticDocument,
    state: AuthoritativeState | null,
    unresolved: LedgerEntry[],
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
      if (projection.kind !== "undo") return drawsAction(projection.e) ? [projection] : [];
      const { target } = projection;
      const targetId = admittedId(entry.undoTarget, unresolved, receipts);
      const pending = !Number.isInteger(target.e.seq);
      const draws =
        classifiedIds.has(targetId ?? target.e.id) || (pending && drawsAction(target.e));
      return draws ? [{ ...projection, targetId }] : [];
    });
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections,
    });
    // Threads and Questions both wait for an admitted reading. Authored markup names every
    // ask the page could hold, but only the log says which of them it still holds and
    // whether they are answered, so before that reading there is no inventory to publish.
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
    const folded = ready
      ? foldThreads(view?.thread.threads ?? [], gestures)
      : [];
    const widgets = foldWidgetStates(document.authored, projection);
    const asks = ready
      ? normalizedAsks(view, widgets, document, projection, local)
      : NO_ASKS;
    const todos = ready ? localTodos(state, local) : { open: [], ended: [] };
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
    const threadsOfEntry = (entry: LedgerEntry): string[] => {
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
    const recovery = new Map<string, string>();
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
    // A send this tab has not delivered, in the served workflow's shape. A turn holds
    // its thread as every thread input does; a widget move owes no answer until the
    // server has read it, so it holds none.
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
        holds_thread: Boolean(turn),
        // The server's tuple, where the local fold keys a coordinate.
        coordinate: turn
          ? ["thread", thread]
          : entry.projection
            ? coordinateOf(entry.projection.coordinate)
            : null,
        answer: null,
        stage: "sending",
        ts: turn?.ts ?? null,
        detail: null,
        agent: null,
        session: null,
        delivery_seq: null,
        delivery_session: null,
        delivery_turn: null,
        response: null,
        activity: [],
        condition: rejected ? { kind: "failed", operation: "delivery" } : null,
        next_actor: rejected ? "user" : "agent",
        started_by: [],
      };
    };
    const workflows: Workflow[] = [
      ...(state ? state.workflows : []),
      ...local.flatMap((entry) =>
        isTurnEvent(entry.event) ? (localWorkflow(entry, false) ?? []) : [],
      ),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control or to-do when speculation ends.
      ...refused.flatMap((entry) => localWorkflow(entry, true) ?? []),
    ];
    const threads = readThreadRecords(
      obligated,
      document,
      widgets,
      workflows,
      markingRead,
      ready,
    );
    const selectedQueues = localQueues(
      ready ? (view?.queues ?? NO_QUEUES) : NO_QUEUES,
      threads,
      workflows,
      todos,
      asks,
    );
    const workflowById = new Map(workflows.map((workflow) => [workflow.id, workflow]));
    const contextual = <T extends { id: string; kind: string }>(
      items: T[],
      onUser = false,
    ) =>
      items.map((item) => ({
        ...item,
        workflow: workflowById.get(item.id) ?? null,
        offers: queueOffers(item, ready, onUser),
      }));
    return {
      hostAvailable,
      projection,
      widgets,
      thread: {
        all: threads,
        // Historical system rows are event narration, never current approval state.
        approvalHistory: [
          ...(state?.browser.approval_history ?? []),
          ...local.flatMap(({ event, localId, timestamp }) => event.kind === "done"
            ? [{ ...event, id: localId, ts: timestamp }] : []),
        ].filter((event) => !local.some(({ event: gesture }) =>
          gesture.kind === "undo" && gesture.undoes === event.id)),
        collection: {
          phase,
          threads: threads.filter(discussed),
        },
        // The threads the gestures this tab's ledger still holds concern, refused ones
        // included until the reading they restore is drawn (held-news.js, `gesturedOn`).
        gestured: [...new Set(unresolved.flatMap(threadsOfEntry))],
      },
      asks: { phase, ...asks },
      // Questions (on the user), Tasks (on the agent), and done: the served lists
      // with this tab's sends placed against them (`localQueues`).
      queues: {
        phase,
        questions: contextual(selectedQueues.questions, true),
        tasks: contextual(selectedQueues.tasks),
        done: contextual(selectedQueues.done),
      },
      // Inside the publication signature, so a read that changes only the view's
      // reports, publication time, or undo list still reaches its watchers.
      view,
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved
        .filter((entry) => SENDING.has(entry.state))
        .map((entry) => entry.event.attempt),
      workflows,
      activity: state?.activity ?? null,
    };
  }

  function semanticSignature(value: unknown) {
    return JSON.stringify(value, (_key, child) =>
      child instanceof Map ? [...child] : child,
    );
  }

  function publish(changes: Partial<typeof initial>) {
    const prior = publisher.read();
    const next = { ...prior, ...changes } as typeof initial;
    next.effective = derive(
      next.document,
      next.authoritative,
      next.unresolved,
      next.markingRead,
      next.phase,
      next.hostAvailable,
    );
    const nextSignature = semanticSignature([next.effective, next.data, next.phase]);
    next.semanticEpoch =
      prior.semanticEpoch +
      Number(
        nextSignature !== signature ||
          next.document.revision !== prior.document.revision,
      );
    signature = nextSignature;
    if (presentation) activePresentation = presentation.begin(next.semanticEpoch);
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
    const prior = publisher.read().authoritative;
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
    const prior = publisher.read();
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

  const entry = (attempt: string) =>
    publisher.read().unresolved.find((item) => item.event.attempt === attempt);
  const ledgerAndReceipts = () => {
    const { unresolved, authoritative } = publisher.read();
    return [unresolved, authoritative?.browser.receipts ?? []] as const;
  };
  const update = (attempt: string, change: (entry: LedgerEntry) => LedgerEntry) =>
    publish({
      unresolved: publisher
        .read()
        .unresolved.map((item) =>
          item.event.attempt === attempt ? change(item) : item,
        ),
    });
  // The ledger after `signal` reaches each attempt `admitted` names, with the log's
  // event for it (or null), and the attempts that left. The caller publishes it.
  const transition = (signal: Signal, admitted: Map<string, Event | null>) => {
    const left: string[] = [];
    const unresolved = publisher.read().unresolved.flatMap((item) => {
      if (!admitted.has(item.event.attempt)) return [item];
      const next = advance(item, signal, admitted.get(item.event.attempt) ?? null);
      if (!next) left.push(item.event.attempt);
      return next ? [next] : [];
    });
    return { unresolved, left };
  };
  const byAttempt = (receipts: readonly Event[]) =>
    new Map<string, Event | null>(
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
    projectView(view: AuthoritativeState["browser"]["views"][string]) {
      return foldProjection({
        ...normalizedProjection(view),
        pendingEntries: [],
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds: string[] | null = null) {
      if (eventIds === null) return publisher.read().effective.widgets;
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
    selectWidget(descriptor: WidgetDescriptor) {
      let prior: ReturnType<typeof widgetReading> | undefined;
      let priorSignature: string | undefined;
      return publisher.select((root) => {
        const reading = widgetReading(root, descriptor);
        const readingSignature = semanticSignature(reading);
        if (readingSignature === priorSignature && prior) return prior;
        prior = reading;
        priorSignature = readingSignature;
        return reading;
      });
    },
    entry,
    identify(revision: number | null, stamp: number | null = null, live = false) {
      return publish({
        document: { ...publisher.read().document, revision, stamp, live },
      });
    },
    setHostAvailable(hostAvailable: boolean) {
      return publish({ hostAvailable });
    },
    markRead(items: ContentVersion[]) {
      return publish({
        markingRead: [...publisher.read().markingRead, ...structuredClone(items)],
      });
    },
    settleMarkRead(items: ContentVersion[]) {
      const remaining = publisher
        .read()
        .markingRead.filter(
          (item) =>
            !items.some(
              (done) => done.message === item.message && done.version === item.version,
            ),
        );
      return publish({ markingRead: remaining });
    },
    captureDocument(document: SemanticDocument) {
      if (publisher.read().authoritative)
        throw new Error("an admitted document changes only through adopt");
      return publish({
        document: {
          ...structuredClone(document),
          authored: new Map(structuredClone(document.authored)),
          descriptors: new Map(structuredClone(document.descriptors)),
        },
      });
    },
    setPhase(phase: string) {
      return publish({ phase });
    },
    // Source revisions are digests with no order, so a reading's data is ordered by
    // the moment the server took it: an answer taken before the one already accepted
    // is older, whichever order the two arrive in.
    acceptData(data: typeof initial.data, taken: number) {
      if (taken < dataTaken) return false;
      dataTaken = taken;
      if (data.version === publisher.read().data.version) return false;
      publish({ data: structuredClone(data) });
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
      const prior = publisher.read();
      if (!adoptable(state, document)) return false;
      const authoritative = structuredClone(state);
      // The reading and what it logs are one publication: the entries whose receipts
      // it holds stop drawing from the gesture as the log starts drawing them.
      const { unresolved } = transition(
        "log",
        byAttempt(authoritative.browser.receipts),
      );
      // A capture can add message bodies without changing the shown document.
      // Retain its explicit identity and share fields the publisher already owns.
      const capture = <T>(value: T, standing: unknown): T =>
        value === standing ? value : structuredClone(value);
      publish({
        document: document
          ? {
              ...document,
              registry: capture(document.registry, prior.document.registry),
              authored: capture(document.authored, prior.document.authored),
              descriptors: capture(document.descriptors, prior.document.descriptors),
              ...(document.messageBodies
                ? {
                    messageBodies: capture(
                      document.messageBodies,
                      prior.document.messageBodies,
                    ),
                  }
                : {}),
            }
          : prior.document,
        authoritative,
        unresolved,
        phase: "ready",
      });
      return true;
    },
    enqueue(
      event: Command,
      timestamp: string,
      plainText: string = event.text ?? event.token ?? "",
    ) {
      if (entry(event.attempt)) return null;
      const before = publisher.read();
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
                    state: structuredClone(
                      before.document.registry.$states[widget.tag]?.[event.action]
                        ?.definition,
                    ),
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
      const { unresolved } = transition("accept", new Map([[attempt, accepted]]));
      publish({ unresolved });
    },
    // The POST refused `attempt`, or it can no longer be sent. What depends on it goes
    // with it: every gesture naming it by its pending id (`namesEvent`), such as an undo
    // of it, a reply to its message or a rewrite written over it, and so on down, since
    // a rewrite over that rewrite names only the one between. Returns those attempts.
    refuse(attempt: string) {
      const refused = entry(attempt);
      if (!refused) return [];
      const ledger = publisher.read().unresolved;
      const gone = [refused.localId];
      const dependents: string[] = [];
      for (let grew = true; grew; ) {
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
    // A document pass carrying these receipts has run. Returns the attempts that left.
    present(receipts: Event[]) {
      const { unresolved, left } = transition("present", byAttempt(receipts));
      publish({ unresolved });
      return left;
    },
    // The entries no document pass has presented yet.
    unpresented: () =>
      publisher.read().unresolved.filter((item) => UNPRESENTED.has(item.state)),
    // The entries `release` would retire now, in ledger order.
    releasable: () =>
      publisher.read().unresolved.filter((item) => RELEASABLE.has(item.state)),
    // Retire those of `attempts` still in a releasable state.
    release(attempts: Set<string>) {
      return publish({
        unresolved: publisher
          .read()
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
          ...(event.parent !== item.event.parent && typeof item.event.parent === "string"
            ? { namedParent: item.event.parent }
            : {}),
          event,
        }));
      return !(event.kind === "undo" && namesPending(event));
    },
  });
}
