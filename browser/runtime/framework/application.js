/* @noformat Generated TypeScript; edit the .ts owner. */
import { createApplicationPublisher, share } from "./snapshot.js";
import {
  coordinateOf,
  foldProjection,
  foldedValue,
  foldWidgetStates,
  obligationValue,
  isProjectionEntry,
  stateCoordinate
} from "../projection/model.js";
import { stampedState, sameStateDefinition } from "../registry-contract.js";
import {
  discussed,
  foldThreads,
  readThreadRecords,
  threadNames
} from "../thread/model.js";
import {
  threadForAttempt,
  editForAttempt,
  isThreadEvent,
  isTurnEvent,
  nameAdmitted,
  namesEvent,
  namesPending,
  turnMessage
} from "../pending/model.js";
import { PENDING } from "../thread/identity.js";
import { queueOffers } from "../queues.js";
const LIFECYCLE = {
  sending: {
    accept: "accepted",
    refuse: "refused",
    log: "sending:logged",
    present: "sending:presented"
  },
  "sending:logged": {
    accept: "accepted:logged",
    refuse: "refused",
    present: "sending:presented"
  },
  "sending:presented": { accept: "accepted:presented", refuse: "refused" },
  accepted: { log: "accepted:logged", present: "accepted:presented" },
  "accepted:logged": { present: "accepted:presented" },
  "accepted:presented": {},
  refused: {}
};
const SENDING = /* @__PURE__ */ new Set([
  "sending",
  "sending:logged",
  "sending:presented"
]);
const DRAWN_LOCALLY = /* @__PURE__ */ new Set(["sending", "accepted"]);
const RELEASABLE = /* @__PURE__ */ new Set(["accepted:presented", "refused"]);
const UNPRESENTED = /* @__PURE__ */ new Set([
  "sending",
  "accepted",
  "sending:logged",
  "accepted:logged"
]);
function admittedId(attempt, unresolved, receipts) {
  if (!attempt) return null;
  return unresolved.find((entry) => entry.event.attempt === attempt)?.admitted?.id ?? receipts.find((receipt) => receipt.attempt === attempt)?.id ?? null;
}
function advance(entry, signal, admitted = null) {
  const action = entry.event.kind === "action";
  if (signal === "present" && !action) return entry;
  const state = LIFECYCLE[entry.state][signal];
  if (!state) return entry;
  if (state === "accepted:logged" && !action) return null;
  return { ...entry, state, admitted: entry.admitted ?? admitted };
}
function normalizedProjection(view) {
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
        value: wire.value
      });
    }
    actionIds.push(...projection.actions);
    reportIds.push(...projection.reports);
    desiredIds.push(...projection.desired);
  }
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}
const NO_OBLIGATIONS = {
  all: [],
  user: [],
  unanswered: []
};
function normalizedObligations(view, widgets, document, projection, todos) {
  const todoRecords = new Map(
    [...todos.open, ...todos.ended].map((todo) => [todo.id, todo])
  );
  const all = (view?.obligations ?? []).map((item) => {
    if (item.source.kind === "todo") {
      const todo = todoRecords.get(item.source.id);
      if (todo.state === "open" && item.status !== "open")
        return {
          ...item,
          answer: null,
          status: "open",
          next_actor: "user",
          end: null
        };
      if (todo.state !== "open" && item.status === "open")
        return {
          ...item,
          answer: { value: todo.state, event: null },
          status: "answered",
          next_actor: null,
          end: null
        };
      return item;
    }
    if (item.source.kind !== "widget") return item;
    const sourceId = item.source.id;
    const sourceUnit = item.source.unit;
    const widget = widgets.get(sourceId);
    const declaration = document.descriptors.get(item.source.id)?.declaration["x-awaits"];
    const verb = declaration?.value;
    if (!verb || !widget) return item;
    const completed = item.status === "answered" && !(item.answer?.event && projection.pendingWithdrawals.has(item.answer.event.id));
    const { value, present } = obligationValue(widget, verb, completed, sourceUnit);
    const pendingValue = widget.entries.some(
      ({ e, unit }) => e.action === verb && (sourceUnit === void 0 || unit === sourceUnit) && !Number.isInteger(e.seq)
    ) || [...projection.pendingWithdrawals.values()].some(
      ({ e, unit }) => e.widget === sourceId && (sourceUnit === void 0 || unit === sourceUnit) && (e.action === verb || e.id === item.answer?.event?.id)
    );
    const answer = present ? { value, event: pendingValue ? null : item.answer?.event ?? null } : null;
    return { ...item, answer };
  });
  return {
    all,
    user: all.filter((item) => item.next_actor === "user"),
    unanswered: all.filter((item) => item.status === "open")
  };
}
function localTodos(state, local) {
  const ending = new Set(
    local.flatMap(({ event }) => event.kind === "todo_end" ? [event.todo] : [])
  );
  const undoing = new Set(
    local.flatMap(({ event }) => event.kind === "undo" ? [event.undoes] : [])
  );
  const all = state?.browser.todos ?? [];
  const served = all.filter((todo) => todo.state === "open");
  const ended = all.filter((todo) => todo.state !== "open");
  const reopened = (todo) => todo.outcome !== null && undoing.has(todo.outcome.id);
  const open = [
    ...served,
    ...ended.filter(reopened).map((todo) => ({
      ...todo,
      state: "open",
      outcome: null
    }))
  ];
  const locallyEnded = (todo) => ending.has(todo.id);
  return {
    open: open.filter((todo) => !locallyEnded(todo)),
    ended: [
      ...ended.filter((todo) => !reopened(todo)),
      ...open.filter(locallyEnded).map((todo) => ({
        ...todo,
        state: "done",
        running: null,
        outcome: { ts: null, detail: null }
      }))
    ]
  };
}
const NO_QUEUES = { on_user: [], on_agent: [], done: [] };
function currentWidgetRelations(document, widgets, projection) {
  const parents = new Map(
    [...document.descriptors].map(([id, descriptor]) => [id, descriptor.parent?.id])
  );
  const owners = /* @__PURE__ */ new Map();
  const memberships = /* @__PURE__ */ new Map();
  const members = (owner, attr) => memberships.get(owner)[attr];
  for (const [id, widget] of widgets) {
    for (const [verb, spec] of widget.specs) {
      const record = spec.record;
      if (record?.kind === "attribute") {
        const named = owners.get(record.attr) ?? /* @__PURE__ */ new Set();
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
      const seen = /* @__PURE__ */ new Set([id]);
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
function localQueues(served, workflows, todos, items, local) {
  const record = new Map(items.all.map((item) => [item.id, item]));
  const inventoryAt = new Map(items.all.map((item, at) => [item.id, at]));
  const open = new Set(todos.open.map((todo) => todo.id));
  const ended = new Set(todos.ended.map((todo) => todo.id));
  const todoRecord = new Map(
    [...todos.open, ...todos.ended].map((todo) => [todo.id, todo])
  );
  const sentIn = new Set(
    workflows.flatMap(
      (workflow) => workflow.stage === "sending" && workflow.condition === null && workflow.subject.kind === "thread" ? [workflow.thread] : []
    )
  );
  const obligationOf = (item) => {
    const current2 = record.get(item.id);
    if (!current2) throw new Error(`Queue item ${item.id} names no obligation`);
    return current2;
  };
  const standsOpen = (item) => {
    if (!namesRecord(item)) return open.has(item.id);
    const current2 = obligationOf(item);
    return current2.next_actor === item.owner && !(current2.source.kind === "update" && current2.thread !== null && sentIn.has(current2.thread));
  };
  const reopened = (item) => namesRecord(item) ? obligationOf(item).status === "open" && obligationOf(item).next_actor === item.owner : open.has(item.id);
  const endedHere = (item) => namesRecord(item) ? obligationOf(item).status !== "open" : ended.has(item.id);
  const todoOf = (item) => {
    const local2 = todoRecord.get(item.id);
    if (!local2) throw new Error(`Queue item ${item.id} names no to-do`);
    return local2;
  };
  const current = (item) => namesRecord(item) ? { ...item, obligation: obligationOf(item) } : { ...item, todo: todoOf(item) };
  const asOpen = ({
    state: _state,
    ended: _ended,
    detail: _detail,
    ...item
  }) => current(item);
  const asDone = (item) => ({
    ...current(item),
    live: false,
    state: namesRecord(item) && obligationOf(item).status === "withdrawn" ? "dropped" : "done",
    ended: null,
    detail: null
  });
  const reopenedFor = (owner) => served.done.filter((item) => item.owner === owner && reopened(item));
  const localRow = (item) => {
    const source = item.source;
    return current({
      kind: "update",
      id: item.id,
      owner: item.next_actor,
      subject: source.subject,
      thread: item.thread,
      also: [],
      live: false
    });
  };
  return {
    on_user: [
      ...served.on_user.filter(standsOpen).map(current),
      ...reopenedFor("user").map(asOpen),
      ...local.filter((item) => item.next_actor === "user").map(localRow)
    ].toSorted(
      (a, b) => onUserRank(a) - onUserRank(b) || (namesRecord(a) && namesRecord(b) ? inventoryAt.get(a.id) - inventoryAt.get(b.id) : 0)
    ),
    on_agent: [
      ...served.on_agent.filter((item) => item.kind !== "todo" && standsOpen(item)).map(current),
      ...local.filter((item) => item.next_actor === "agent").map(localRow),
      ...served.on_agent.filter((item) => item.kind === "todo" && standsOpen(item)).map(current),
      ...reopenedFor("agent").map(asOpen)
    ],
    // Newest first, as the server serves it: what ended in this tab has just ended.
    done: [
      ...[...served.on_user, ...served.on_agent].filter(endedHere).map(asDone),
      ...served.done.filter((item) => !reopened(item)).map(current)
    ]
  };
}
function localUpdates(workflows) {
  const newest = /* @__PURE__ */ new Map();
  for (const workflow of workflows)
    if (workflow.stage === "sending" && workflow.condition === null)
      newest.set(workflow.thread, workflow);
  const records = [];
  const named = workflows.map((workflow) => {
    if (workflow.stage !== "sending") return workflow;
    const refused = workflow.condition !== null;
    const owner = refused ? workflow : newest.get(workflow.thread);
    const id = `update:${owner.id}`;
    if (owner === workflow)
      records.push({
        id,
        source: { kind: "update", id: workflow.input, subject: workflow.subject },
        thread: workflow.thread,
        message: workflow.message,
        prompt: {
          text: null,
          target: "id" in workflow.subject ? workflow.subject.id : workflow.input
        },
        answer: null,
        status: "open",
        end: null,
        next_actor: refused ? "user" : "agent"
      });
    return { ...workflow, obligation: id };
  });
  return { workflows: named, records };
}
const onUserRank = (item) => item.kind === "todo" ? 1 : item.kind === "update" ? 2 : 0;
const namesRecord = (item) => item.kind !== "todo" || item.owner === "user";
function widgetIndex(root) {
  const projection = root.effective.projection;
  const byWidget = /* @__PURE__ */ new Map();
  const group = (widget) => {
    let entries = byWidget.get(widget);
    if (!entries)
      byWidget.set(widget, entries = { classified: [], desired: [], undo: [] });
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
  const heldBy = /* @__PURE__ */ new Map();
  for (const thread of root.effective.thread.all)
    if (!thread.resolved && !thread.root.pending && thread.root.holds && !heldBy.has(thread.root.holds))
      heldBy.set(thread.root.holds, thread.id);
  return { byWidget, heldBy };
}
const NO_ENTRIES = { classified: [], desired: [], undo: [] };
function widgetInputs(root, index, { id, tag }) {
  return {
    registered: root.document.descriptors.get(id),
    states: root.document.registry.$states[tag],
    current: root.effective.widgets.get(id),
    memberships: root.effective.memberships.get(id),
    authored: root.document.authored.get(id),
    hostAvailable: root.effective.hostAvailable,
    ready: root.phase === "ready",
    entries: index.byWidget.get(id) ?? NO_ENTRIES,
    heldBy: index.heldBy.get(id) ?? null
  };
}
function widgetReading(inputs, descriptor) {
  const currentDescriptor = JSON.stringify(inputs.registered) === JSON.stringify(descriptor);
  const current = currentDescriptor ? inputs.current : void 0;
  const authored = currentDescriptor ? inputs.authored?.state : void 0;
  const classified = inputs.entries.classified.toSorted(
    (left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0)
  );
  const actionSpecs = descriptor.declaration["x-state"] ?? {};
  const states = inputs.states ?? {};
  const desired = inputs.entries.desired;
  const durableUndo = inputs.entries.undo;
  const localUndo = desired.map(({ e }) => e).filter((event) => String(event.id).startsWith(PENDING));
  const actions = Object.fromEntries(
    Object.entries(actionSpecs).filter(([verb]) => states[verb]?.writer === "user").map(([verb]) => [
      verb,
      {
        available: currentDescriptor && inputs.hostAvailable && inputs.ready && !descriptor.quoted,
        unavailable: inputs.hostAvailable ? null : "no agent or server is available",
        history: classified.filter(({ e }) => e.action === verb).map(({ e }) => e),
        inForce: desired.filter(({ e }) => e.action === verb).map(({ e, unit, value }) => ({ event: e, unit, value })),
        undo: inputs.hostAvailable ? [...localUndo, ...durableUndo].filter((event) => event.action === verb) : []
      }
    ])
  );
  const provenanceEntries = current?.entries ?? [];
  const provenance = Object.fromEntries(
    provenanceEntries.map(({ e, unit, value }) => [
      `${e.action}:${unit}`,
      { event: e, unit, value }
    ])
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    memberships: currentDescriptor ? inputs.memberships ?? {} : {},
    thread: { heldBy: inputs.heldBy },
    provenance,
    actions
  };
}
function createSemanticApplication({
  presentation
} = {}) {
  const initial = {
    document: {
      revision: null,
      registry: { $states: {} },
      authored: /* @__PURE__ */ new Map(),
      descriptors: /* @__PURE__ */ new Map()
    },
    authoritative: null,
    unresolved: [],
    // The entries that left the ledger once a reading logged them. Each stays until the
    // first reading adopted after a document pass drew its receipt (`drawn`), so its
    // thread stays gestured through that pass, a failed one and its retry included, as
    // it was while the ledger held it.
    settled: [],
    // Content versions this tab has marked read and the log has not yet answered for.
    // Marking read is bookkeeping, not a gesture, so it has no place in the ordered
    // `unresolved` ledger; each leaves once the answer carrying it is applied.
    markingRead: [],
    phase: "waiting",
    // How the server answered the page's latest read: not yet (`waiting`), with a
    // reading the page adopted (`reached`), with nothing (`unreachable`, or `refused`
    // where it refused this tab's key), with an error of its own (`faulted`, whose
    // words `fault` keeps), or with one the page could not apply (`broken`). It is
    // what the page's status says about the server, and no semantic epoch.
    reach: "waiting",
    fault: null,
    hostAvailable: true,
    data: {
      version: null,
      sources: {}
    },
    // Ephemeral typed values derived by mounted widgets; no server run or revision.
    outputs: {},
    effective: derive(
      {
        revision: null,
        registry: { $states: {} },
        authored: /* @__PURE__ */ new Map(),
        descriptors: /* @__PURE__ */ new Map()
      },
      null,
      [],
      [],
      [],
      "waiting",
      true
    ),
    semanticEpoch: 0
  };
  const publisher = createApplicationPublisher(initial);
  const widgets = publisher.select(widgetIndex);
  let dataTaken = -Infinity;
  let order = 0;
  const drawn = /* @__PURE__ */ new Set();
  let publicationDepth = 0;
  let activePresentation = null;
  if (presentation) presentation.seal(presentation.begin());
  function derive(document, state, unresolved, settled, markingRead, phase, hostAvailable) {
    const receipts = state?.browser.receipts ?? [];
    const local = unresolved.filter((entry2) => DRAWN_LOCALLY.has(entry2.state));
    const refused = unresolved.filter((entry2) => entry2.state === "refused");
    const served = state?.browser.views[String(document.revision)];
    const view = served ? (({ basis: _basis, ...rest }) => rest)(served) : null;
    const admitted = normalizedProjection(view);
    const classifiedIds = new Set(admitted.entries.map(({ e }) => e.id));
    const drawsAction = (e) => {
      const descriptor = document.descriptors.get(e.widget);
      const state2 = descriptor && stampedState(document.registry, descriptor.tag, e);
      return Boolean(state2 && sameStateDefinition(e.meaning?.state, state2.definition));
    };
    const localProjections = local.flatMap((entry2) => {
      const projection2 = entry2.projection;
      if (!projection2) return [];
      if (projection2.kind !== "undo")
        return drawsAction(projection2.e) ? [projection2] : [];
      const { target } = projection2;
      const targetId = admittedId(entry2.undoTarget, unresolved, receipts);
      const pending = !Number.isInteger(target.e.seq);
      const draws = classifiedIds.has(targetId ?? target.e.id) || pending && drawsAction(target.e);
      return draws ? [{ ...projection2, targetId }] : [];
    });
    const projection = foldProjection({
      ...admitted,
      pendingEntries: localProjections
    });
    const ready = phase === "ready";
    const gestures = local.flatMap(
      ({ event, thread, namedParent }) => thread ? [thread] : event.kind === "resolve" || event.kind === "unresolve" ? [{ ...event, ...namedParent ? { localParent: namedParent } : {} }] : event.kind === "undo" ? [event] : []
    );
    const folded = foldThreads(view?.thread.threads ?? [], gestures);
    const widgets2 = foldWidgetStates(document.authored, projection);
    const { parents: widgetParents, memberships } = currentWidgetRelations(
      document,
      widgets2,
      projection
    );
    const todos = ready ? localTodos(state, local) : { open: [], ended: [] };
    const servedItems = ready ? normalizedObligations(view, widgets2, document, projection, todos) : NO_OBLIGATIONS;
    const named = threadNames(folded);
    const threadOfEntry = ({ event, thread: drawn2, namedParent }) => {
      const drawnIn = drawn2 && named.get(drawn2.id)?.id;
      if (drawnIn) return drawnIn;
      switch (event.kind) {
        case "comment":
          return drawn2?.id ?? null;
        case "reply":
          return named.get(event.parent)?.id ?? event.parent;
        case "edit":
          return named.get(event.message)?.id ?? null;
        case "resolve":
        case "unresolve":
          return named.get(event.parent)?.id ?? (namedParent ? named.get(namedParent)?.id : null) ?? null;
        case "action": {
          const held = document.descriptors.get(event.widget)?.document;
          return held?.kind === "thread" ? held.thread ?? null : null;
        }
        default:
          return null;
      }
    };
    const logged = state?.browser.thread_memberships ?? {};
    const threadsOfEntry = (entry2) => {
      const filed = entry2.admitted ? logged[entry2.admitted.id] : void 0;
      if (filed) return filed;
      const { event } = entry2;
      if (event.kind === "undo") {
        const target = unresolved.find(
          (each) => each.localId === event.undoes || each.admitted?.id === event.undoes
        );
        return target ? threadsOfEntry(target) : logged[event.undoes] ?? [];
      }
      const thread = threadOfEntry(entry2);
      return thread ? [thread] : [];
    };
    const recovery = /* @__PURE__ */ new Map();
    for (const entry2 of refused) {
      if (!isTurnEvent(entry2.event) && entry2.event.kind !== "action") continue;
      const thread = threadOfEntry(entry2);
      if (thread) recovery.set(thread, `rejected:${entry2.event.attempt}`);
    }
    const obligated = folded.map((thread) => {
      const retry = recovery.get(thread.id);
      return retry && thread.attention?.kind !== "needs_user" ? {
        ...thread,
        attention: { kind: "needs_user", reason: "resend", workflow: retry }
      } : thread;
    });
    const localWorkflow = (entry2, rejected) => {
      const turn = isTurnEvent(entry2.event) ? entry2.thread : null;
      const thread = threadOfEntry(entry2);
      const subject = turn ? thread === null ? null : { kind: "thread", id: thread } : entry2.event.kind === "action" ? { kind: "widget", id: entry2.event.widget } : null;
      if (!subject) return null;
      return {
        id: `${rejected ? "rejected" : "pending"}:${entry2.event.attempt}`,
        revision: entry2.event.revision ?? document.revision,
        seq: entry2.order,
        input: turn?.id ?? entry2.localId,
        message: turn ? turnMessage(turn) : null,
        subject,
        thread,
        at_work: false,
        // The server's tuple, where the local fold keys a coordinate.
        coordinate: turn ? ["thread", thread] : entry2.projection ? coordinateOf(entry2.projection.coordinate) : null,
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
        started_by: []
      };
    };
    const sends = localUpdates([
      ...state ? state.workflows : [],
      ...local.flatMap(
        (entry2) => isTurnEvent(entry2.event) ? localWorkflow(entry2, false) ?? [] : []
      ),
      // A refused message or widget move has a destination to send again.
      // Other gestures restore their own control or to-do when speculation ends.
      ...refused.flatMap((entry2) => localWorkflow(entry2, true) ?? [])
    ]);
    const workflows = sends.workflows;
    const localRecords = ready ? sends.records : [];
    const all = [...servedItems.all, ...localRecords];
    const items = {
      all,
      user: [
        ...servedItems.user,
        ...localRecords.filter((item) => item.next_actor === "user")
      ],
      unanswered: [...servedItems.unanswered, ...localRecords]
    };
    const threads = readThreadRecords(
      obligated,
      document,
      widgets2,
      workflows,
      todos.open,
      items.all,
      markingRead,
      ready
    );
    const selectedQueues = localQueues(
      ready ? view?.queues ?? NO_QUEUES : NO_QUEUES,
      workflows,
      todos,
      items,
      localRecords
    );
    const serving = /* @__PURE__ */ new Map();
    for (const workflow of workflows)
      if (workflow.obligation !== null && !serving.has(workflow.obligation))
        serving.set(workflow.obligation, workflow);
    const contextual = (items2, onUser = false) => items2.map((item) => ({
      ...item,
      workflow: serving.get(item.id) ?? null,
      offers: queueOffers(item, ready, onUser)
    }));
    return {
      hostAvailable,
      projection,
      widgets: widgets2,
      thread: {
        all: threads,
        collection: {
          phase,
          threads: threads.filter(discussed)
        },
        // The threads the gestures this tab's ledger still holds concern, refused ones
        // included until the reading they restore is drawn, and those the adopted
        // reading settled (held-news.js, `gesturedOn`).
        gestured: [...new Set([...unresolved, ...settled].flatMap(threadsOfEntry))]
      },
      obligations: { phase, ...items },
      // The agent's plan in force, as the server read it (`plans.plan_reading`).
      plan: ready ? state?.browser.plan ?? null : null,
      // On me (on the user), On <agent> (on the agent), and done: the served lists
      // with this tab's sends placed against them (`localQueues`).
      queues: {
        phase,
        on_user: contextual(selectedQueues.on_user, true),
        on_agent: contextual(selectedQueues.on_agent),
        done: contextual(selectedQueues.done)
      },
      // Part of the effective reading, so a read that changes only the view's
      // reports, publication time, or undo list opens an epoch and reaches its readers.
      view,
      memberships,
      widgetParents,
      // The attempts still waiting for their POST's answer, in ledger order.
      sending: unresolved.filter((entry2) => SENDING.has(entry2.state)).map((entry2) => entry2.event.attempt),
      workflows,
      activity: state?.activity ?? null
    };
  }
  function publish(changes) {
    const prior = publisher.peek();
    const next = { ...prior, ...changes };
    next.effective = share(
      prior.effective,
      derive(
        next.document,
        next.authoritative,
        next.unresolved,
        next.settled,
        next.markingRead,
        next.phase,
        next.hostAvailable
      )
    );
    next.data = share(prior.data, next.data);
    next.outputs = share(prior.outputs, next.outputs);
    next.semanticEpoch = prior.semanticEpoch + Number(
      next.effective !== prior.effective || next.data !== prior.data || next.outputs !== prior.outputs || next.phase !== prior.phase || next.document.revision !== prior.document.revision
    );
    if (presentation) activePresentation = presentation.begin();
    publicationDepth += 1;
    try {
      return publisher.publish(next);
    } finally {
      publicationDepth -= 1;
      if (presentation && publicationDepth === 0 && activePresentation) {
        const current = activePresentation;
        activePresentation = null;
        presentation.seal(current);
      }
    }
  }
  const overtaken = (state) => {
    const prior = publisher.peek().authoritative;
    return Boolean(
      prior && (state.taken < prior.taken || state.browser.basis.through_seq < prior.browser.basis.through_seq || state.active.revision < prior.active.revision)
    );
  };
  const adoptable = (state, candidate) => {
    const prior = publisher.peek();
    if (overtaken(state)) return false;
    const revision = typeof candidate === "number" ? candidate : candidate?.revision ?? prior.document.revision;
    const view = state.browser.views[String(revision)];
    return Boolean(
      view && view.basis.revision === revision && view.basis.through_seq === state.browser.basis.through_seq
    );
  };
  const unresolvedPart = publisher.select((root) => root.unresolved);
  const receiptsPart = publisher.select(
    (root) => root.authoritative?.browser.receipts ?? []
  );
  const widgetsPart = publisher.select((root) => root.effective.widgets);
  const entry = (attempt) => unresolvedPart.read().find((item) => item.event.attempt === attempt);
  const ledgerAndReceipts = () => [unresolvedPart.read(), receiptsPart.read()];
  const update = (attempt, change) => publish({
    unresolved: publisher.peek().unresolved.map(
      (item) => item.event.attempt === attempt ? change(item) : item
    )
  });
  const transition = (signal, admitted) => {
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
  const byAttempt = (receipts) => new Map(
    receipts.flatMap(
      (receipt) => receipt.attempt ? [[receipt.attempt, receipt]] : []
    )
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
    projectView(view) {
      return foldProjection({
        ...normalizedProjection(view),
        pendingEntries: []
      });
    },
    // Render checks compare authored, carried, and current states. The event filter is
    // a semantic selection of the same root, not a presentation-owned partial fold.
    selectWidgets(eventIds = null) {
      if (eventIds === null) return widgetsPart.read();
      const wanted = new Set(eventIds);
      return publisher.select(
        (root) => foldWidgetStates(root.document.authored, {
          ...root.effective.projection,
          desired: new Map(
            [...root.effective.projection.desired].filter(
              ([, entry2]) => wanted.has(entry2.e.id)
            )
          )
        })
      ).read();
    },
    // A widget's reading, recomputed only when one of the parts it draws moves, so a
    // publication about another widget or a thread costs each widget a comparison.
    selectWidget(descriptor) {
      let inputs = null;
      let reading;
      return publisher.select((root) => {
        const next = widgetInputs(root, widgets.read(), descriptor);
        const keys = Object.keys(next);
        const prior = inputs;
        if (prior && keys.every((key) => next[key] === prior[key])) return reading;
        inputs = next;
        return reading = widgetReading(next, descriptor);
      });
    },
    entry,
    identify(revision, stamp = null, live = false) {
      return publish({
        document: { ...publisher.peek().document, revision, stamp, live }
      });
    },
    setHostAvailable(hostAvailable) {
      return publish({ hostAvailable });
    },
    markRead(items) {
      return publish({
        markingRead: [...publisher.peek().markingRead, ...items]
      });
    },
    settleMarkRead(items) {
      const remaining = publisher.peek().markingRead.filter(
        (item) => !items.some(
          (done) => done.message === item.message && done.version === item.version
        )
      );
      return publish({ markingRead: remaining });
    },
    captureDocument(document) {
      if (publisher.peek().authoritative)
        throw new Error("an admitted document changes only through adopt");
      return publish({ document });
    },
    setPhase(phase) {
      return publish({ phase });
    },
    setReach(reach, fault = null) {
      const now = publisher.peek();
      if (now.reach === reach && now.fault === fault) return now;
      return publish({ reach, fault });
    },
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
    adopt(state, document = null) {
      const prior = publisher.peek();
      if (!adoptable(state, document)) return false;
      const authoritative = state;
      const { unresolved, left } = transition(
        "log",
        byAttempt(authoritative.browser.receipts)
      );
      const settled = [
        ...prior.settled.filter((item) => !drawn.has(item.event.attempt)),
        ...left
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
        fault: null
      });
      return true;
    },
    enqueue(event, timestamp, plainText = event.text ?? event.token ?? "") {
      if (entry(event.attempt)) return null;
      const before = publisher.peek();
      const localId = PENDING + event.attempt;
      const thread = isThreadEvent(event) ? { ...threadForAttempt(event, timestamp), plainText } : event.kind === "edit" ? editForAttempt(event, timestamp) : null;
      const undoTarget = event.kind === "undo" ? before.unresolved.find((item) => item.localId === event.undoes) : null;
      const localTarget = undoTarget?.projection;
      const target = event.kind === "undo" ? (localTarget?.kind !== "undo" ? localTarget : null) ?? before.effective.projection.classified.get(event.undoes) : null;
      const widget = event.kind === "action" ? before.document.authored.get(event.widget) : null;
      const declaration = event.kind === "action" ? before.document.descriptors.get(event.widget)?.declaration : null;
      const spec = event.kind === "action" && widget ? declaration?.["x-state"]?.[event.action] : null;
      const unit = event.kind === "action" && spec ? spec.unit === "widget" ? event.widget : event.detail[spec.unit] : null;
      const localOrder = ++order;
      const projection = event.kind === "undo" && target && isProjectionEntry(target) && target.e.kind === "action" ? {
        kind: "undo",
        target,
        coordinate: target.coordinate,
        localOrder
      } : event.kind === "action" && widget && spec && typeof unit === "string" ? {
        unit,
        spec,
        coordinate: stateCoordinate(event.widget, unit, event.action),
        localOrder,
        e: {
          ...event,
          id: localId,
          meaning: {
            state: before.document.registry.$states[widget.tag]?.[event.action]?.definition
          }
        },
        value: spec.record ? foldedValue(event, spec.record) : event.action
      } : null;
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
            admitted: null
          }
        ]
      });
      return entry(event.attempt);
    },
    // The POST accepted `attempt` as the log's `accepted`.
    accept(attempt, accepted) {
      if (!entry(attempt)) return;
      const { unresolved, left } = transition("accept", /* @__PURE__ */ new Map([[attempt, accepted]]));
      const settled = left.filter((item) => !drawn.delete(item.event.attempt));
      publish({
        unresolved,
        ...settled.length && { settled: [...publisher.peek().settled, ...settled] }
      });
    },
    // The POST refused `attempt`, or it can no longer be sent. What depends on it goes
    // with it: every gesture naming it by its pending id (`namesEvent`), such as an undo
    // of it, a reply to its message or a rewrite written over it, and so on down, since
    // a rewrite over that rewrite names only the one between. Returns those attempts.
    refuse(attempt) {
      const refused = entry(attempt);
      if (!refused) return [];
      const ledger = publisher.peek().unresolved;
      const gone = [refused.localId];
      const dependents = [];
      for (let grew = true; grew; ) {
        grew = false;
        for (const item of ledger)
          if (item.event.attempt !== attempt && !dependents.includes(item.event.attempt) && gone.some((id) => namesEvent(item.event, id))) {
            dependents.push(item.event.attempt);
            gone.push(item.localId);
            grew = true;
          }
      }
      const { unresolved } = transition("refuse", /* @__PURE__ */ new Map([[attempt, null]]));
      publish({
        unresolved: unresolved.filter(
          (item) => !dependents.includes(item.event.attempt)
        )
      });
      return dependents;
    },
    // A document pass carrying these receipts has run, which moves only the actions
    // among them, and publishes only where one moved.
    present(receipts) {
      const { unresolved, settled } = publisher.peek();
      const attempts = byAttempt(receipts);
      for (const item of [...settled, ...unresolved])
        if (attempts.has(item.event.attempt)) drawn.add(item.event.attempt);
      const { unresolved: next, moved } = transition("present", attempts);
      if (moved) publish({ unresolved: next });
    },
    // The entries no document pass has presented yet.
    unpresented: () => unresolvedPart.read().filter((item) => UNPRESENTED.has(item.state)),
    // The entries `release` would retire now, in ledger order.
    releasable: () => unresolvedPart.read().filter((item) => RELEASABLE.has(item.state)),
    // Retire those of `attempts` still in a releasable state.
    release(attempts) {
      return publish({
        unresolved: publisher.peek().unresolved.filter(
          (item) => !(attempts.has(item.event.attempt) && RELEASABLE.has(item.state))
        )
      });
    },
    // Just before a send, a gesture naming one this tab sent, by its pending id, names
    // it by the id the log gave it once the log has answered, in every field that names
    // an event (`nameAdmitted`): a reply's `parent`, the revision an edit is written over
    // (`base`), as a second rewrite over a first still sending is, an undo's target. A
    // renamed `parent` is kept as `namedParent`, which still finds the thread the reply
    // was drawn in. Returns false for a gesture that cannot be sent: an undo still naming
    // a gesture the log never took, since it would take back nothing the log knows.
    nameEvents(attempt) {
      const item = entry(attempt);
      if (!item) return true;
      const event = nameAdmitted(
        item.event,
        (pending) => admittedId(pending, ...ledgerAndReceipts())
      );
      if (event !== item.event)
        update(attempt, (item2) => ({
          ...item2,
          ...event.parent !== item2.event.parent && typeof item2.event.parent === "string" ? { namedParent: item2.event.parent } : {},
          event
        }));
      return !(event.kind === "undo" && namesPending(event));
    }
  });
}
export {
  createSemanticApplication
};
