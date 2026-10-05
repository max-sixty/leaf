/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture supplies typed initial values; transport supplies complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { createApplicationPublisher } from "./snapshot.ts";
import {
  foldProjection,
  foldedValue,
  foldWidgetStates,
} from "../../skills/leaf/assets/runtime/projection/model.js";
import {
  discussed,
  foldThreads,
  readThreadRecords,
  threadNames,
} from "../../skills/leaf/assets/runtime/thread/model.js";
import {
  threadForAttempt,
  isThreadEvent,
  isMessageEvent,
} from "../../skills/leaf/assets/runtime/pending/model.js";
import { PENDING } from "../../skills/leaf/assets/runtime/thread/identity.js";
import { selectDone, selectQueues } from "../../skills/leaf/assets/runtime/queues.js";

// The pure model's input types are inferred from its existing implementation. They
// remain one contract while those folds move to compiled source independently.
type AuthoredMap = Parameters<typeof foldWidgetStates>[0];
type Thread = Parameters<typeof discussed>[0];
type Event = Thread["root"];

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
// In an adopted reading that no document pass has presented yet: the semantic root
// already draws the log's event, and the page may still show what came before it.
const UNPRESENTED = new Set<GestureState>(["sending:logged", "accepted:logged"]);

/** One unresolved gesture. `admitted` is the log's event for it, known from the
 * POST's answer or from a reading, whichever came first. */
interface LedgerEntry {
  event: Event;
  localId: string;
  order: number;
  projection: any;
  thread: any;
  message: any;
  undoTarget: string | null;
  namedParent?: string;
  state: GestureState;
  admitted: Event | null;
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

interface ActionSpec {
  unit: string;
  record?: { kind: string; value: string; attr?: string };
  writer: "user" | "agent";
}

interface WireProjection {
  entries: {
    event: Event;
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

/** One wire Ask, as `served_state` serializes it. */
interface WireAsk {
  id: string;
  seq: number;
  tag: string;
  source: string;
  source_tag: string;
  thread: string | null;
}

/** One exact agent content version, as a Thread's `unread` names it. */
interface ContentVersion {
  message: string;
  version: string;
}

interface WireAsks {
  all: WireAsk[];
  user: WireAsk[];
  unanswered: WireAsk[];
}

/** One served workflow, as `served_state.browser.served_workflows` serializes it;
 * `AuthoritativeState.workflows` lists them strongest first. */
interface WireWorkflow {
  id: string;
  seq: number;
  revision: number | null;
  input: string | null;
  subject: { kind: "thread" | "widget"; id: string };
  thread: string | null;
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

/** One task, as `served_state.browser` serves it: `tasks` holds the open ones and
 * `ended_tasks` the ones a `task_end` ended, with its outcome. */
interface WireTask {
  id: string;
  subject: { kind: "thread" | "widget"; id: string } | { kind: "page" };
  thread: string | null;
  title: string;
  state: "open" | "done" | "failed" | "dropped";
  ts: string;
  revision: number | null;
  /** The start running on the task, while one does. */
  running: {
    id: string;
    text: string;
    seq: number;
    ts: string;
    agent: string | null;
    session: string | null;
    turn: string | null;
    condition: { kind: "stale"; operation: "work" } | null;
  } | null;
  agent: string | null;
  session: string | null;
  outcome: { ts: string; detail?: string | null } | null;
}

/** The public Ask record packages read. */
export interface AskRecord {
  id: string;
  tag: string;
  sourceId: string;
  sourceTag: string;
  thread: string | null;
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
  >;
  authored: AuthoredMap;
  descriptors: ReadonlyMap<string, WidgetDescriptor>;
  messageBodies?: ReadonlyMap<
    string,
    { text: string; document?: { thread: string; message: string } }
  >;
}

export interface WidgetDescriptor {
  id: string;
  tag: string;
  document:
    | { kind: "page"; revision: number }
    | { kind: "thread"; thread?: string; message?: string };
  declaration: Record<string, unknown>;
  parent: { id: string; tag: string } | null;
  ancestors: readonly { id: string; tag: string }[];
  quoted: boolean;
}

export interface AuthoritativeState {
  taken: number;
  layer: { generation: string };
  active: { revision: number; version?: number | null; label?: string | null };
  versions?: { revision: number; version: number; label: string }[];
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
          asks?: WireAsks;
        };
        undo?: { event: Event }[];
        coverage: object[];
        updates?: object[];
        published_at?: string | null;
      }
    >;
    thread: {
      threads: Thread[];
      projection: WireProjection;
      asks?: WireAsks;
      done?: Event[];
    };
    receipts: Event[];
    tasks?: WireTask[];
    ended_tasks?: WireTask[];
  };
  activity: unknown;
  reading?: string;
  agent?: string;
}

type ServerView = AuthoritativeState["browser"]["views"][string];
/** A server view with its basis, the transport identity, left off. */
type PageView = Omit<ServerView, "basis">;

function normalizedProjection(
  view: PageView | null | undefined,
  thread: AuthoritativeState["browser"]["thread"] | undefined,
) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, thread?.projection]) {
    if (!projection) continue;
    for (const wire of projection.entries ?? []) {
      const e = wire.event;
      const coordinate = JSON.stringify(wire.coordinate);
      entries.push({
        coordinate,
        e,
        restated: wire.restated,
        absorbed: wire.absorbed,
        stands: wire.stands,
        scope: wire.scope,
        spec: wire.spec,
        unit: wire.coordinate[1],
        value:
          wire.spec.record?.kind === "attribute"
            ? (wire.value as string[]).join(" ")
            : wire.value,
      });
    }
    actionIds.push(...(projection.actions ?? []));
    reportIds.push(...(projection.reports ?? []));
    desiredIds.push(...(projection.desired ?? []));
  }
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}

// The selected server view already bounds page history to the captured revision and
// thread history to its frozen document. Widget ids are unique across both, so
// filtering again by the event's authored revision would incorrectly discard carried
// decisions from an earlier revision.
const appliesTo = (descriptor: WidgetDescriptor, event: Event) =>
  event.widget === descriptor.id;

const NO_ASKS = {
  all: [] as AskRecord[],
  user: [] as AskRecord[],
  unanswered: [] as AskRecord[],
};

const askRecord = (ask: WireAsk): AskRecord => ({
  id: ask.id,
  tag: ask.tag,
  sourceId: ask.source,
  sourceTag: ask.source_tag,
  thread: ask.thread,
});

/* The admitted Ask reading, page asks before thread asks.
 *
 * Which Asks a document holds and which of them the user still owes are folded
 * by `leaf.asks` under the same page transaction as the rest of this state. Nothing here folds those declarations
 * again, so an answer reaches these lists when the state its POST returns is
 * adopted — one reading after the widget state the user sees change at once. */
function normalizedAsks(
  view: PageView | null,
  threadView: AuthoritativeState["browser"]["thread"] | undefined,
) {
  const page = view?.document.asks;
  const thread = threadView?.asks;
  const records = (kind: "all" | "user" | "unanswered") => [
    ...(page?.[kind] ?? []).map(askRecord),
    ...(thread?.[kind] ?? []).map(askRecord),
  ];
  return {
    all: records("all"),
    user: records("user"),
    unanswered: records("unanswered"),
  };
}

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
  const actionSpecs = (declaration["x-state"] ?? {}) as Record<string, ActionSpec>;
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
    .map((candidate: { event: Event }) => candidate.event)
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
      .filter(([, spec]) => spec.writer === "user")
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

  const provenanceEntries = (current?.entries ?? []) as unknown as {
    e: Event;
    unit: string;
    value: unknown;
  }[];
  const provenance = Object.fromEntries(
    provenanceEntries.map(({ e, unit, value }) => [
      `${e.action}:${unit}`,
      { event: e, unit, value },
    ]),
  );
  const holdingThread = root.effective.thread.all.find(
    (thread: any) =>
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
      registry: {},
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
        registry: {},
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
    // An undo withdraws its target by the log's id once the log has named it: the
    // target entry's while it stands in the ledger, its receipt's once released.
    const namedTarget = (attempt: string | null) => {
      const target = unresolved.find((entry) => entry.event.attempt === attempt);
      return target
        ? (target.admitted?.id ?? null)
        : (receipts.find((receipt) => receipt.attempt === attempt)?.id ?? null);
    };
    const localProjections = local
      .filter((entry) => entry.projection)
      .map((entry) =>
        entry.projection.kind === "undo"
          ? { ...entry.projection, targetId: namedTarget(entry.undoTarget) }
          : entry.projection,
      );
    // The shown revision's server view, resolved here once for every reader of this
    // document's page state. Its basis is transport identity, which the adoption
    // boundary has already matched to the log reading; left in, a read that only moved
    // the log's sequence would publish a new semantic epoch.
    const served = state?.browser.views[String(document.revision)];
    const view: PageView | null = served
      ? (({ basis: _basis, ...rest }) => rest)(served)
      : null;
    const admitted = normalizedProjection(view, state?.browser.thread);
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections,
    });
    // Threads and Asks both wait for an admitted reading. Authored markup names every
    // Ask the page could hold, but only the log says which of them it still holds and
    // whether they are answered, so before that reading there is no inventory to publish.
    const ready = phase === "ready";
    const messages = local.filter((entry) => entry.message);
    const folded = ready
      ? foldThreads(
          state?.browser.thread.threads ?? [],
          messages.map((entry) => entry.message),
          local.filter((entry) => entry.thread?.token).map((entry) => entry.thread),
          local
            .filter(
              ({ event }) => event.kind === "resolve" || event.kind === "unresolve",
            )
            .map((entry) => ({ ...entry.event, localParent: entry.namedParent })),
          new Set(
            local
              .filter(({ event }) => event.kind === "undo")
              .map(({ event }) => event.undoes),
          ),
        )
      : [];
    const widgets = foldWidgetStates(document.authored, projection);
    const asks = ready ? normalizedAsks(view, state?.browser.thread) : NO_ASKS;
    // Thread attention is the server's reading, and three local facts adjust it. A
    // pending send hands the thread to the agent, which `foldThreads` states. A
    // structural Ask survives prose sent beside it, so the admitted Ask inventory puts
    // back the independent obligation that still stands in that thread. A refused send
    // hands a thread the server left with the agent back to the user, whose
    // Retry it is.
    const owed = new Set(asks.user.map((ask) => ask.thread));
    // The thread a local message is in. A comment opens the thread its own id names. A
    // reply is in the thread holding its parent, which need not be that thread's id: a
    // thread that lost its opening message is answered at the reply that survived, and
    // a reply written against this tab's own comment names it by its pending id until
    // the log names it. A parent no thread holds is a comment of this tab's that the
    // log refused, and its pending id named its thread.
    const named = threadNames(folded);
    const threadOf = (message: any): string =>
      message.kind === "reply"
        ? (named.get(message.parent)?.id ?? message.parent)
        : message.id;
    // The thread a local gesture stands in: its message's, or the thread whose
    // markup froze the widget it moved; a page widget's stands in none.
    const threadOfEntry = (entry: any): string | null => {
      if (entry.message) return threadOf(entry.message);
      const held = document.descriptors.get(entry.event.widget)?.document;
      return held?.kind === "thread" ? (held.thread ?? null) : null;
    };
    const recovery = new Map<string, string>();
    for (const entry of refused) {
      const thread = threadOfEntry(entry);
      if (thread) recovery.set(thread, `rejected:${entry.event.attempt}`);
    }
    const obligated = folded.map((thread: any) => {
      if (owed.has(thread.id))
        return thread.attention?.reason === "ask"
          ? thread
          : {
              ...thread,
              attention: { kind: "needs_user", reason: "ask", workflow: null },
            };
      const retry = recovery.get(thread.id);
      return retry && thread.attention?.kind !== "needs_user"
        ? {
            ...thread,
            attention: { kind: "needs_user", reason: "recovery", workflow: retry },
          }
        : thread;
    });
    // A send this tab has not delivered, in the served workflow's shape. A message
    // holds its thread as every thread input does; a widget move owes no answer until
    // the server has read it, so it holds none.
    const localWorkflow = (entry: any, rejected: boolean) => {
      const message = entry.message;
      const thread = threadOfEntry(entry);
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
        revision: entry.event.revision ?? document.revision,
        seq: entry.order,
        input: message?.id ?? entry.localId,
        subject: message
          ? { kind: "thread", id: thread }
          : { kind: "widget", id: entry.event.widget },
        thread,
        holds_thread: Boolean(message),
        // The server's list, where the local fold keys a coordinate by its JSON.
        coordinate: message
          ? ["thread", thread]
          : entry.projection
            ? JSON.parse(entry.projection.coordinate)
            : null,
        answer: null,
        stage: "sending",
        ts: message?.ts ?? null,
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
    const workflows = [
      ...(state ? state.workflows : []),
      ...messages.map((entry) => localWorkflow(entry, false)),
      ...refused.map((entry) => localWorkflow(entry, true)),
    ];
    const threads = readThreadRecords(
      obligated,
      document,
      widgets,
      workflows,
      markingRead,
    );
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
      },
      asks,
      // What is on the user and what is on the agent, selected from the readings
      // above once this tab's sends are folded into them (`runtime/queues.js`).
      queues: selectQueues({
        asks: asks.user,
        threads,
        workflows,
        tasks: ready ? (state?.browser.tasks ?? []) : [],
      }),
      // What is finished, selected beside them from the same readings: the answered
      // Asks and the ended tasks.
      done: selectDone({
        asks,
        tasks: ready ? (state?.browser.ended_tasks ?? []) : [],
      }),
      // Inside the publication signature, so a read that changes only the view's
      // updates, publication time, or undo list still reaches its watchers.
      view,
      acceptedApprovals: state?.browser.thread.done ?? [],
      pendingApprovals: local
        .filter((entry) => entry.event.kind === "done")
        .map((entry) => entry.event),
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
  const byAttempt = (receipts: Event[]) =>
    new Map<string, Event | null>(
      receipts.map((receipt) => [receipt.attempt, receipt]),
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
    projectView(
      view: AuthoritativeState["browser"]["views"][string],
      thread: AuthoritativeState["browser"]["thread"],
    ) {
      return foldProjection({
        ...normalizedProjection(view, thread),
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
      event: Event,
      timestamp: string,
      plainText: string = event.text ?? event.token ?? "",
    ) {
      if (entry(event.attempt)) return null;
      const before = publisher.read();
      const localId = PENDING + event.attempt;
      const thread = isThreadEvent(event)
        ? { ...threadForAttempt(event, timestamp), plainText }
        : null;
      const undoTarget =
        event.kind === "undo"
          ? before.unresolved.find((item) => item.localId === event.undoes)
          : null;
      const target =
        undoTarget?.projection ??
        before.effective.projection.classified.get(event.undoes);
      const widget = before.document.authored.get(event.widget);
      const spec =
        widget && before.document.registry[widget.tag]?.["x-state"]?.[event.action];
      const unit =
        spec && (spec.unit === "widget" ? event.widget : event.detail[spec.unit]);
      const localOrder = ++order;
      const projection =
        event.kind === "undo" && target?.e.kind === "action"
          ? {
              kind: "undo",
              target,
              coordinate: target.coordinate,
              localOrder,
            }
          : event.kind === "action" && spec && typeof unit === "string"
            ? {
                unit,
                spec,
                coordinate: JSON.stringify([event.widget, unit, event.action]),
                localOrder,
                e: { ...event, id: localId },
                value: spec.record ? foldedValue(event, spec.record) : event.action,
              }
            : null;
      publish({
        unresolved: [
          ...before.unresolved,
          {
            event: structuredClone(event),
            localId,
            order: localOrder,
            projection,
            thread,
            message: isMessageEvent(event) ? thread : null,
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
    // with it: an undo of it, and a reply to its message. Returns those attempts.
    refuse(attempt: string) {
      const refused = entry(attempt);
      if (!refused) return [];
      const dependents = publisher
        .read()
        .unresolved.filter(
          (item) =>
            item.undoTarget === attempt ||
            (refused.message?.id && item.event.parent === refused.message.id),
        )
        .map((item) => item.event.attempt);
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
    // The entries an adopted reading logs that the page has not yet presented.
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
    nameParent(attempt: string, receipts: Event[]) {
      const item = entry(attempt);
      const parent = item?.event.parent;
      if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
      const parentAttempt = parent.slice(PENDING.length);
      const named =
        entry(parentAttempt)?.admitted?.id ??
        receipts.find((receipt) => receipt.attempt === parentAttempt)?.id;
      if (named)
        update(attempt, (item) => ({
          ...item,
          namedParent: parent,
          event: { ...item.event, parent: named },
        }));
    },
    nameUndo(attempt: string, receipts: Event[]) {
      const item = entry(attempt);
      if (item?.event.kind !== "undo" || !item.undoTarget) return true;
      const named =
        entry(item.undoTarget)?.admitted?.id ??
        receipts.find((receipt) => receipt.attempt === item.undoTarget)?.id;
      if (!named) return false;
      update(attempt, (item) => ({ ...item, event: { ...item.event, undoes: named } }));
      return true;
    },
  });
}
