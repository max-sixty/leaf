/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture supplies typed initial values; transport supplies complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { createApplicationPublisher } from "./snapshot.js";
import {
  foldProjection,
  foldedValue,
  foldWidgetStates,
  questionValue,
  isProjectionEntry,
} from "../../runtime/projection/model.js";
import {
  stateDefinition,
  eventSpec,
  sameStateDefinition,
  sameStateOperation,
} from "../../runtime/registry-contract.js";
import {
  discussed,
  foldThreads,
  readThreadRecords,
  threadNames,
} from "../../runtime/thread/model.js";
import {
  threadForAttempt,
  isThreadEvent,
  isMessageEvent,
} from "../../runtime/pending/model.js";
import { PENDING } from "../../runtime/thread/identity.js";
import {
  queueOffers,
  selectDone,
  selectQueues,
} from "../../runtime/queues.js";

















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











const LIFECYCLE                                                              = {
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
const SENDING = new Set              ([
  "sending",
  "sending:logged",
  "sending:presented",
]);
// Drawn from the gesture, because no adopted reading holds its receipt.
const DRAWN_LOCALLY = new Set              (["sending", "accepted"]);
// The states `release` retires.
const RELEASABLE = new Set              (["accepted:presented", "refused"]);
// In an adopted reading that no document pass has presented yet: the semantic root
// already draws the log's event, and the page may still show what came before it.
const UNPRESENTED = new Set              (["sending:logged", "accepted:logged"]);

/** One unresolved gesture. `admitted` is the log's event for it, known from the
 * POST's answer or from a reading, whichever came first. */














// `entry` after `signal`, or null once it leaves the ledger.
function advance(
  entry             ,
  signal        ,
  admitted               = null,
)                     {
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:presented" && entry.event.kind !== "action") return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}

















/** A request and its contained answer. The source owns the canonical value;
 * identity includes its kind so authored ids and message ids cannot collide. */


















/** One served workflow, as `served_state.browser.served_workflows` serializes it;
 * `AuthoritativeState.workflows` lists them strongest first. */










































/** Published workflows include local sends, before the server can classify quietness. */






/** One task, as `served_state.browser` serves it (`tasks.page_tasks`): `tasks` holds
 * the open ones on either side and `ended_tasks` the ones that ended, with their
 * outcome. Questions are separate records and never appear in this task list. */




































































































/** A server view with its basis, the transport identity, left off. */


function normalizedProjection(
  view                             ,
  thread                                                     ,
  descriptors                                  ,
) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, thread?.projection]) {
    if (!projection) continue;
    for (const wire of projection.entries ?? []) {
      const e = wire.event;
      const descriptor = descriptors?.get(e.widget);
      const currentSpec = descriptor && eventSpec(descriptor.declaration, e);
      if (
        descriptor &&
        (!currentSpec ||
          !sameStateOperation(
            e.meaning?.state,
            stateDefinition(descriptor.tag, descriptor.declaration, currentSpec),
          ))
      )
        continue;
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
            ? foldedValue(e, wire.spec.record)
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
const appliesTo = (descriptor                  , event                           ) =>
  event.widget === descriptor.id;

const NO_QUESTIONS = {
  all: []                    ,
  user: []                    ,
  unanswered: []                    ,
};

/* The admitted inventory owns membership and widget completion. Approval and its
 * undo draw their direct result immediately. Widget values come from
 * the same local-inclusive fold used by their controls, so a partial answer is
 * visible before its POST settles the Question. */
function normalizedQuestions(
  view                 ,
  threadView                                                     ,
  widgets                                     ,
  document                  ,
  projection                                   ,
  local                        ,
)                {
  const page = view?.document.questions;
  const thread = threadView?.questions;
  const all = [...(page?.all ?? []), ...(thread?.all ?? [])].map(
    (question)                 => {
      if (question.source.kind === "approval") {
        const version = question.source.version;
        const undone = new Set(local.flatMap(({ event }) =>
          event.kind === "undo" ? [event.undoes] : []));
        const approving = local.some(({ event }) =>
          event.kind === "done" && event.version === version);
        if (approving) return { ...question, answer: { value: true, event: null },
          status: "answered", next_actor: null };
        if (question.answer?.event && undone.has(question.answer.event.id))
          return { ...question, answer: null, status: "open", next_actor: "user" };
        return question;
      }
      if (question.source.kind !== "widget") return question;
      const sourceId = question.source.id;
      const widget = widgets.get(sourceId);
      const declaration = document.descriptors.get(question.source.id)?.declaration["x-awaits"]
                                      ;
      const verb = declaration?.value;
      if (!verb || !widget) return question;
      const completed = question.status === "answered" &&
        !(question.answer?.event && projection.pendingWithdrawals.has(question.answer.event.id));
      const { value, present } = questionValue(widget, verb, completed);
      const pendingValue = (widget.entries                  ).some(({ e }) =>
        e.action === verb && !Number.isInteger(e.seq)) ||
        [...projection.pendingWithdrawals.values()].some(({ e }) =>
          e.widget === sourceId &&
          (e.action === verb || e.id === question.answer?.event?.id));
      const answer = present
        ? { value, event: pendingValue ? null : question.answer?.event ?? null }
        : null;
      return { ...question, answer };
    },
  );
  const selection = (kind                       ) => {
    const admitted = new Set([...(page?.[kind] ?? []), ...(thread?.[kind] ?? [])]
      .map((question) => question.id));
    return all.filter((question) => question.source.kind === "approval"
      ? kind === "user" ? question.next_actor === "user" : question.status === "open"
      : admitted.has(question.id));
  };
  return { all, user: selection("user"), unanswered: selection("unanswered") };
}

/* Prose sends hand attention to the agent immediately; settlement remains the
 * server's. Earlier suppressed prompts stay in the complete inventory. */
function questionAttention(questions               , threads                                                 )                {
  const byThread = new Map(threads.map((thread) => [thread.id, thread]));
  const user = new Set(questions.user.map((question) => question.id));
  const all = questions.all.map((question)                 => {
    if (question.source.kind !== "reply" || !user.has(question.id)) return question;
    const thread = question.thread === null ? undefined : byThread.get(question.thread);
    return thread?.resolved || thread?.attention?.kind === "waiting"
      ? { ...question, next_actor: thread?.resolved ? null : "agent" }
      : question;
  });
  const byId = new Map(all.map((question) => [question.id, question]));
  return {
    all,
    user: questions.user.map((question) => byId.get(question.id) )
      .filter((question) => question.next_actor === "user"),
    unanswered: questions.unanswered.map((question) => byId.get(question.id) ),
  };
}

/* Explicit work, open and ended, including Done this tab is sending or undoing. A task the user is ending stands ended in the
 * gesture's own turn, and one whose Done they are undoing stands open again; a refused
 * gesture leaves the ledger and so puts the task back as the log has it. */
function localTasks(
  state                           ,
  local                        ,
) {
  const ending = new Set(
    local.flatMap(({ event }) => (event.kind === "task_end" ? [event.task] : [])),
  );
  const undoing = new Set(
    local.flatMap(({ event }) => (event.kind === "undo" ? [event.undoes] : [])),
  );
  const served = state?.browser.tasks ?? [];
  const ended = state?.browser.ended_tasks ?? [];
  const reopened = (task          ) =>
    task.outcome !== null && undoing.has(task.outcome.id ?? "");
  const open = [
    ...served,
    ...ended
      .filter(reopened)
      .map((task) => ({ ...task, state: "open"         , outcome: null })),
  ];
  const locallyEnded = (task          ) => ending.has(task.id);
  return {
    open: open.filter((task) => !locallyEnded(task)),
    ended: [
      ...ended.filter((task) => !reopened(task)),
      ...open.filter(locallyEnded).map((task) => ({
        ...task,
        state: "done"         ,
        running: null,
        outcome: { ts: null, detail: null },
      })),
    ],
  };
}

function widgetReading(
  root                                                                  ,
  descriptor                  ,
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
      (event       ) =>
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










export function createSemanticApplication({
  presentation,
}                                           = {}) {
  const initial = {
    document: {
      revision: null,
      registry: {},
      authored: new Map(),
      descriptors: new Map(),
    }                    ,
    authoritative: null                             ,
    unresolved: []                 ,
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: []                    ,
    phase: "waiting",
    hostAvailable: true,
    data: { version: null                 , sources: {}                            },
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
  let activePresentation                                         = null;

  if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));

  function derive(
    document                  ,
    state                           ,
    unresolved               ,
    markingRead                  ,
    phase        ,
    hostAvailable         ,
  ) {
    const receipts = state?.browser.receipts ?? [];
    const local = unresolved.filter((entry) => DRAWN_LOCALLY.has(entry.state));
    const refused = unresolved.filter((entry) => entry.state === "refused");
    // An undo withdraws its target by the log's id once the log has named it: the
    // target entry's while it stands in the ledger, its receipt's once released.
    const namedTarget = (attempt               ) => {
      const target = unresolved.find((entry) => entry.event.attempt === attempt);
      return target
        ? (target.admitted?.id ?? null)
        : (receipts.find((receipt) => receipt.attempt === attempt)?.id ?? null);
    };
    // A revision may reuse a widget/verb with a different operation. Keep its
    // pending delivery, but stop drawing it against that new declaration. The
    // server validates durable payloads; speculative state waits for its receipt
    // when a revised payload schema cannot be compared directly.
    const compatiblePending = (projection                                        ) => {
      const operation = projection.kind === "undo" ? projection.target : projection;
      const descriptor = document.descriptors.get(operation.e.widget);
      if (!descriptor) return false;
      const currentSpec = eventSpec(descriptor.declaration, operation.e);
      return (
        currentSpec &&
        sameStateDefinition(
          operation.e.meaning?.state,
          stateDefinition(descriptor.tag, descriptor.declaration, currentSpec),
        )
      );
    };
    const localProjections = local.flatMap((entry) => {
      const projection = entry.projection;
      if (!projection || !compatiblePending(projection)) return [];
      return [
        projection.kind === "undo"
          ? { ...projection, targetId: namedTarget(entry.undoTarget) }
          : projection,
      ];
    });
    // The shown revision's server view, resolved here once for every reader of this
    // document's page state. Its basis is transport identity, which the adoption
    // boundary has already matched to the log reading; left in, a read that only moved
    // the log's sequence would publish a new semantic epoch.
    const served = state?.browser.views[String(document.revision)];
    const view                  = served
      ? (({ basis: _basis, ...rest }) => rest)(served)
      : null;
    const admitted = normalizedProjection(
      view,
      state?.browser.thread,
      document.descriptors,
    );
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections,
    });
    // A local comment belongs to the shown document even before saved history arrives.
    // Fold it through the same ledger and receipt path in every phase; collection.phase
    // still says whether this is a complete reading. Questions need the log to say which
    // authored questions the page still holds, so their inventory waits for that reading.
    const ready = phase === "ready";
    const messages = local.filter((entry) => entry.message);
    const folded = foldThreads(
      state?.browser.thread.threads ?? [],
      messages.flatMap((entry) => (entry.message ? [entry.message] : [])),
      local.flatMap((entry) => (entry.thread?.token ? [entry.thread] : [])),
      local.flatMap(({ event, namedParent }) =>
        event.kind === "resolve" || event.kind === "unresolve"
          ? [{ ...event, ...(namedParent ? { localParent: namedParent } : {}) }]
          : [],
      ),
      new Set(
        local.flatMap(({ event }) => (event.kind === "undo" ? [event.undoes] : [])),
      ),
    );
    const widgets = foldWidgetStates(document.authored, projection);
    const admittedQuestions = ready
      ? normalizedQuestions(view, state?.browser.thread, widgets, document, projection, local)
      : NO_QUESTIONS;
    const tasks = ready ? localTasks(state, local) : { open: [], ended: [] };
    // Thread attention is the server's reading, and three local facts adjust it. A
    // pending send hands the thread to the agent, which `foldThreads` states. A
    // structural Question survives prose sent beside it, so the admitted Question inventory puts
    // back the independent obligation that still stands in that thread. A refused send
    // hands a thread the server left with the agent back to the user, whose
    // Retry it is.
    const owed = new Set(admittedQuestions.user
      .filter((question) => question.source.kind === "widget")
      .map((question) => question.thread));
    // The thread a local message is in. A comment opens the thread its own id names. A
    // reply is in the thread holding its parent, which need not be that thread's id: a
    // thread that lost its opening message is answered at the reply that survived, and
    // a reply written against this tab's own comment names it by its pending id until
    // the log names it. A parent no thread holds is a comment of this tab's that the
    // log refused, and its pending id named its thread.
    const named = threadNames(folded);
    const threadOf = (message         )         =>
      message.kind === "reply"
        ? (named.get(message.parent)?.id ?? message.parent)
        : message.id;
    // The thread a local gesture stands in: its message's, or the thread whose
    // markup froze the widget it moved; a page widget's stands in none.
    const threadOfEntry = (entry             )                => {
      if (entry.message) return threadOf(entry.message);
      const held = entry.event.widget
        ? document.descriptors.get(entry.event.widget)?.document
        : null;
      return held?.kind === "thread" ? (held.thread ?? null) : null;
    };
    const recovery = new Map                ();
    for (const entry of refused) {
      const thread = threadOfEntry(entry);
      if (thread) recovery.set(thread, `rejected:${entry.event.attempt}`);
    }
    const obligated = folded.map((thread)         => {
      if (owed.has(thread.id))
        return thread.attention?.reason === "question"
          ? thread
          : {
              ...thread,
              attention: { kind: "needs_user", reason: "question", workflow: null },
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
    const localWorkflow = (entry             , rejected         )                  => {
      const message = entry.message;
      const thread = threadOfEntry(entry);
      const subject                             = message
        ? { kind: "thread", id: threadOf(message) }
        : entry.event.kind === "action"
          ? { kind: "widget", id: entry.event.widget }
          : null;
      if (!subject) return null;
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry.event.attempt}`,
        revision: entry.event.revision ?? document.revision,
        seq: entry.order,
        input: message?.id ?? entry.localId,
        subject,
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
    const workflows             = [
      ...(state ? state.workflows : []),
      ...messages.flatMap((entry) => localWorkflow(entry, false) ?? []),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control or task when speculation ends.
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
    const questions = questionAttention(admittedQuestions, threads);
    const selectedQueues = selectQueues({ threads, workflows, tasks: tasks.open, questions });
    const workflowById = new Map(workflows.map((workflow) => [workflow.id, workflow]));
    const contextual =                                         (
      items     ,
      onYou = false,
    ) =>
      items.map((item) => ({
        ...item,
        workflow: workflowById.get(item.id) ?? null,
        offers: queueOffers(item, ready, onYou),
      }));
    return {
      hostAvailable,
      projection,
      widgets,
      thread: {
        all: threads,
        // Historical system rows are event narration, never current approval state.
        approvalHistory: [
          ...(state?.browser.thread.approval_history ?? []),
          ...local.flatMap(({ event, localId, timestamp }) => event.kind === "done"
            ? [{ ...event, id: localId, ts: timestamp }] : []),
        ].filter((event) => !local.some(({ event: gesture }) =>
          gesture.kind === "undo" && gesture.undoes === event.id)),
        collection: {
          phase,
          threads: threads.filter(discussed),
        },
      },
      questions: { phase, ...questions },
      // What is on the user and what is on the agent, selected from the readings
      // above once this tab's sends are folded into them (`runtime/queues.js`).
      queues: {
        phase,
        onYou: contextual(selectedQueues.onYou, true),
        onAgent: contextual(selectedQueues.onAgent),
        done: contextual(selectDone({ tasks: tasks.ended, questions })),
      },
      // Inside the publication signature, so a read that changes only the view's
      // updates, publication time, or undo list still reaches its watchers.
      view,
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved
        .filter((entry) => SENDING.has(entry.state))
        .map((entry) => entry.event.attempt),
      workflows,
      activity: state?.activity ?? null,
    };
  }

  function semanticSignature(value         ) {
    return JSON.stringify(value, (_key, child) =>
      child instanceof Map ? [...child] : child,
    );
  }

  function publish(changes                         ) {
    const prior = publisher.read();
    const next = { ...prior, ...changes }                  ;
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
  const overtaken = (state                    ) => {
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
    state                    ,
    candidate                                  ,
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

  const entry = (attempt        ) =>
    publisher.read().unresolved.find((item) => item.event.attempt === attempt);
  const update = (attempt        , change                                     ) =>
    publish({
      unresolved: publisher
        .read()
        .unresolved.map((item) =>
          item.event.attempt === attempt ? change(item) : item,
        ),
    });
  // The ledger after `signal` reaches each attempt `admitted` names, with the log's
  // event for it (or null), and the attempts that left. The caller publishes it.
  const transition = (signal        , admitted                           ) => {
    const left           = [];
    const unresolved = publisher.read().unresolved.flatMap((item) => {
      if (!admitted.has(item.event.attempt)) return [item];
      const next = advance(item, signal, admitted.get(item.event.attempt) ?? null);
      if (!next) left.push(item.event.attempt);
      return next ? [next] : [];
    });
    return { unresolved, left };
  };
  const byAttempt = (receipts                  ) =>
    new Map                      (
      receipts.flatMap((receipt) =>
        receipt.attempt ? [[receipt.attempt, receipt]         ] : [],
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
    projectView(
      view                                                ,
      thread                                         ,
    ) {
      return foldProjection({
        ...normalizedProjection(view, thread),
        pendingEntries: [],
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds                  = null) {
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
    selectWidget(descriptor                  ) {
      let prior                                              ;
      let priorSignature                    ;
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
    identify(revision               , stamp                = null, live = false) {
      return publish({
        document: { ...publisher.read().document, revision, stamp, live },
      });
    },
    setHostAvailable(hostAvailable         ) {
      return publish({ hostAvailable });
    },
    markRead(items                  ) {
      return publish({
        markingRead: [...publisher.read().markingRead, ...structuredClone(items)],
      });
    },
    settleMarkRead(items                  ) {
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
    captureDocument(document                  ) {
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
    setPhase(phase        ) {
      return publish({ phase });
    },
    // Source revisions are digests with no order, so a reading's data is ordered by
    // the moment the server took it: an answer taken before the one already accepted
    // is older, whichever order the two arrive in.
    acceptData(data                     , taken        ) {
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
      state                    ,
      document                                   = null,
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
    adopt(state                    , document                          = null) {
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
      const capture =    (value   , standing         )    =>
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
      event         ,
      timestamp        ,
      plainText         = event.text ?? event.token ?? "",
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
      const localTarget = undoTarget?.projection;
      const target =
        event.kind === "undo"
          ? ((localTarget?.kind !== "undo" ? localTarget : null) ??
            before.effective.projection.classified.get(event.undoes))
          : null;
      const widget =
        event.kind === "action" ? before.document.authored.get(event.widget) : null;
      const spec =
        event.kind === "action" && widget
          ? before.document.registry[widget.tag]?.["x-state"]?.[event.action]
          : null;
      const unit =
        event.kind === "action" && spec
          ? spec.unit === "widget"
            ? event.widget
            : event.detail[spec.unit]
          : null;
      const localOrder = ++order;
      const projection                           =
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
                coordinate: JSON.stringify([event.widget, unit, event.action]),
                localOrder,
                e: {
                  ...event,
                  id: localId,
                  meaning: {
                    state: stateDefinition(
                      widget.tag,
                      before.document.registry[widget.tag],
                      spec,
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
    accept(attempt        , accepted       ) {
      if (!entry(attempt)) return;
      const { unresolved } = transition("accept", new Map([[attempt, accepted]]));
      publish({ unresolved });
    },
    // The POST refused `attempt`, or it can no longer be sent. What depends on it goes
    // with it: an undo of it, and a reply to its message. Returns those attempts.
    refuse(attempt        ) {
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
    present(receipts         ) {
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
    release(attempts             ) {
      return publish({
        unresolved: publisher
          .read()
          .unresolved.filter(
            (item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state)),
          ),
      });
    },
    nameParent(attempt        , receipts         ) {
      const item = entry(attempt);
      const parent = item?.event.parent;
      if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
      const parentAttempt = parent.slice(PENDING.length);
      const named =
        entry(parentAttempt)?.admitted?.id ??
        receipts.find((receipt) => receipt.attempt === parentAttempt)?.id;
      if (named)
        update(attempt, (item) =>
          item.event.parent
            ? {
                ...item,
                namedParent: parent,
                event: { ...item.event, parent: named },
              }
            : item,
        );
    },
    nameUndo(attempt        , receipts         ) {
      const item = entry(attempt);
      if (item?.event.kind !== "undo" || !item.undoTarget) return true;
      const named =
        entry(item.undoTarget)?.admitted?.id ??
        receipts.find((receipt) => receipt.attempt === item.undoTarget)?.id;
      if (!named) return false;
      update(attempt, (item) =>
        item.event.kind === "undo"
          ? { ...item, event: { ...item.event, undoes: named } }
          : item,
      );
      return true;
    },
  });
}
// Generated from build/browser/application.ts by npm run build:browser.
