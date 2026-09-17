/** One semantic root for accepted state, authored values, and ordered local attempts.
 *
 * DOM capture supplies typed initial values; transport supplies complete admitted
 * readings. The existing pure folds derive every published projection synchronously.
 * Promises, rendering instances, and proof of presentation stay outside this owner.
 */
import { createApplicationPublisher } from "./snapshot.ts";
import {
  foldProjection,
  foldedFacet,
  foldWidgetStates,
} from "../../skills/leaf/assets/runtime/projection/model.js";
import {
  conversational,
  foldThreads,
} from "../../skills/leaf/assets/runtime/conversation/model.js";
import {
  conversationForAttempt,
  isConversationEvent,
  isMessageEvent,
  pendingApprovals,
  pendingProjectionEntries,
  pendingReactions,
  pendingRequests,
  pendingSettlements,
  unreadMessages,
  unresolvedAttempts,
} from "../../skills/leaf/assets/runtime/pending/model.js";
import { PENDING } from "../../skills/leaf/assets/runtime/conversation/identity.js";

// The pure model's input types are inferred from its existing implementation. They
// remain one contract while those folds move to compiled source independently.
type AuthoredMap = Parameters<typeof foldWidgetStates>[0];
type Thread = Parameters<typeof conversational>[0];
type Event = Thread["root"];

interface ActionSpec {
  facet: string;
  unit: string;
  record?: { kind: string; value: string; attr?: string };
}

interface WireProjection {
  entries: {
    event: Event;
    coordinate: [string, string, string];
    restated?: string[];
    scope: string;
    spec: ActionSpec;
    value: unknown;
  }[];
  actions: string[];
  reports: string[];
  desired: string[];
}

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
      "x-report"?: Record<string, ActionSpec>;
      [name: string]: unknown;
    }
  >;
  authored: AuthoredMap;
  descriptors: ReadonlyMap<string, WidgetDescriptor>;
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
  retiredBy: readonly { ownerId: string; outcome: string }[];
  conversation?: {
    authored: Readonly<Record<string, string | null>>;
    when: Readonly<Record<string, readonly (string | boolean)[]>>;
  } | null;
  ask?: {
    authored?: Readonly<Record<string, string | null>>;
    when?: Readonly<Record<string, readonly (string | boolean)[]>>;
    answers: readonly string[];
    until?: {
      verb: string;
      when: Readonly<Record<string, readonly (string | boolean)[]>>;
    } | null;
    empty: Readonly<Record<string, string | null>>;
  } | null;
  bindings: Readonly<Record<string, string | null>>;
  offers: readonly { tag: string; attribute: string; verb: string }[];
}

export interface AuthoritativeState {
  taken: number;
  layer: { generation: string };
  active: { revision: number; version?: number | null; label?: string | null };
  versions?: { revision: number; version: number; label: string }[];
  events: Event[];
  browser: {
    basis: { through_seq: number };
    views: Record<
      string,
      {
        basis: { revision: number; through_seq: number };
        document: {
          projection: WireProjection;
          requests?: { seat: { widget: string }; phase: string }[];
        };
        undo?: { event: Event }[];
        coverage: object[];
        updates?: object[];
        published_at?: string | null;
      }
    >;
    conversation: {
      threads: Thread[];
      projection: WireProjection;
      requests?: { seat: { widget: string }; phase: string }[];
    };
    receipts: Event[];
  };
  activity: unknown;
  reading?: string;
  agent?: string;
}

function normalizedProjection(
  view: AuthoritativeState["browser"]["views"][string] | undefined,
  conversation: AuthoritativeState["browser"]["conversation"] | undefined,
) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  for (const projection of [view?.document.projection, conversation?.projection]) {
    if (!projection) continue;
    for (const wire of projection.entries ?? []) {
      const e = wire.event;
      const coordinate = JSON.stringify(wire.coordinate);
      entries.push({
        coordinate,
        e,
        restated: wire.restated ?? [],
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

const emptyLifecycle = (descriptor: WidgetDescriptor) => ({
  seat: { document: descriptor.document, widget: descriptor.id },
  attempts: [],
  latest: null,
  phase: "ready",
});

// The selected server view already bounds page history to the captured revision and
// conversation history to its frozen document. Widget ids are unique across both, so
// filtering again by the event's authored revision would incorrectly discard carried
// decisions from an earlier revision.
const appliesTo = (descriptor: WidgetDescriptor, event: Event) =>
  event.widget === descriptor.id;

const projectedPosition = (projection: any, id: string) =>
  [...projection.desired.values()].find(
    ({ unit, spec }: any) => unit === id && spec.record?.kind === "position",
  );

const projectedParent = (
  descriptors: ReadonlyMap<string, WidgetDescriptor>,
  projection: any,
  child: WidgetDescriptor,
) => {
  const moved = projectedPosition(projection, child.id);
  const parentId = moved ? moved.e.detail[moved.spec.record.value] : child.parent?.id;
  return typeof parentId === "string" ? descriptors.get(parentId) : undefined;
};

const localAsk = (descriptor: WidgetDescriptor) => {
  const awaits = descriptor.declaration["x-awaits"] as { rollup?: boolean } | undefined;
  return Boolean(
    (awaits && !awaits.rollup) ||
    (descriptor.declaration["x-request"] as { ask?: boolean } | undefined)?.ask,
  );
};

function surfaceFor(
  descriptors: ReadonlyMap<string, WidgetDescriptor>,
  projection: any,
  source: WidgetDescriptor,
) {
  let holder: WidgetDescriptor | undefined = source;
  const seen = new Set<string>();
  while (holder && !seen.has(holder.id)) {
    seen.add(holder.id);
    if (holder.declaration["x-ask-surface"]) return holder;
    holder = projectedParent(descriptors, projection, holder);
  }
  return source;
}

const nonempty = (value: unknown) =>
  Array.isArray(value)
    ? value.length > 0
    : value !== null && value !== undefined && value !== "";

function actionAskAnswered(
  document: SemanticDocument,
  projection: any,
  descriptor: WidgetDescriptor,
  reading: { answers: readonly string[]; explicit: boolean },
) {
  const ask = descriptor.ask;
  if (!ask) return false;
  return reading.answers.some((verb) => {
    const spec = (descriptor.declaration["x-state"] as Record<string, ActionSpec>)[
      verb
    ];
    if (!spec) return false;
    const held = [...projection.actions.values()].find(
      ({ e }: any) => e.widget === descriptor.id && e.action === verb,
    );
    // A frozen Ask's matching `until` verb is a completion gesture, not a value
    // declaration. Its action must stand even when authored state already carries a
    // nonempty value, and it completes even when the posted record clears that value.
    if (reading.explicit) return Boolean(held);
    if (
      spec.unit === "widget" &&
      ["attribute", "value"].includes(spec.record?.kind ?? "")
    )
      return nonempty(
        held?.value ?? document.authored.get(descriptor.id)?.state[spec.facet]?.value,
      );
    if (!held) return false;
    if (!(verb in ask.empty)) return true;
    const container = ask.empty[verb];
    return (
      container !== null &&
      ![...document.descriptors.values()].some(
        (child) =>
          projectedParent(document.descriptors, projection, child)?.id === container,
      )
    );
  });
}

const conditionMatches = (
  attributes: Readonly<Record<string, string | boolean | null>>,
  when: Readonly<Record<string, readonly (string | boolean)[]>> = {},
) =>
  Object.entries(when).every(([attribute, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? (attributes[attribute] !== null) === value
        : attributes[attribute] === value,
    ),
  );

function effectiveActionAsk(
  descriptor: WidgetDescriptor,
  widgets: ReturnType<typeof foldWidgetStates>,
) {
  const ask = descriptor.ask;
  if (!ask) return null;
  const attributes: Record<string, string | boolean | null> = {
    ...(ask.authored ?? {}),
  };
  const widget = widgets.get(descriptor.id) as
    | { entries?: { e: Event; spec: ActionSpec }[] }
    | undefined;
  for (const { e, spec } of widget?.entries ?? []) {
    const record = spec.record;
    if (record?.kind === "value" && record.attr && record.attr in attributes)
      attributes[record.attr] = foldedFacet(e, record) as string | boolean | null;
  }
  const until = descriptor.document.kind === "thread" ? ask.until : null;
  const explicit = Boolean(until && conditionMatches(attributes, until.when));
  return {
    local: conditionMatches(attributes, ask.when),
    answers: explicit ? [until!.verb] : ask.answers,
    explicit,
  };
}

function requestPhase(
  descriptor: WidgetDescriptor,
  lifecycle: { page: any; conversation: any },
  pendingRequestEvents: Event[],
) {
  if (pendingRequestEvents.some((event) => event.widget === descriptor.id))
    return "pending";
  const requests =
    descriptor.document.kind === "thread"
      ? lifecycle.conversation.requests
      : lifecycle.page.requests;
  return (
    requests?.find((item: any) => item.seat.widget === descriptor.id)?.phase ?? "ready"
  );
}

const retirementStands = (
  projection: any,
  relation: { ownerId: string; outcome: string },
) =>
  [...projection.actions.values()].some(
    ({ e }: any) => e.widget === relation.ownerId && e.action === relation.outcome,
  );

const retiredByAnother = (descriptor: WidgetDescriptor, projection: any) =>
  (descriptor.retiredBy ?? []).some(
    (relation) =>
      relation.ownerId !== descriptor.id && retirementStands(projection, relation),
  );

function deriveAsks(
  document: SemanticDocument,
  projection: any,
  widgets: ReturnType<typeof foldWidgetStates>,
  threads: Thread[],
  lifecycle: { page: any; conversation: any },
  pendingRequestEvents: Event[],
) {
  const descriptors = document.descriptors;
  const actionAsks = new Map(
    [...descriptors.values()].flatMap((descriptor) => {
      const reading = effectiveActionAsk(descriptor, widgets);
      return reading ? [[descriptor.id, reading] as const] : [];
    }),
  );
  const activeThreads = new Set(
    threads
      .filter((thread: any) => !thread.resolved)
      .map((thread: any) => thread.root.id),
  );
  const exists = (descriptor: WidgetDescriptor) =>
    !descriptor.quoted &&
    !retiredByAnother(descriptor, projection) &&
    (descriptor.document.kind === "page" ||
      (typeof descriptor.document.thread === "string" &&
        activeThreads.has(descriptor.document.thread)));

  // Authored descriptors are the complete Ask inventory. The effective projection
  // decides which captured retirement edges stand, and the effective thread fold
  // decides which frozen documents remain active. This one existence reading drives
  // both visible inventory and rollups; accepted and pending gestures take the same
  // path instead of patching deltas onto the server's previous list.
  const inventory: AskRecord[] = [];
  for (const descriptor of descriptors.values()) {
    const requestAsk = Boolean(
      (descriptor.declaration["x-request"] as { ask?: boolean } | undefined)?.ask,
    );
    const actionAsk = actionAsks.get(descriptor.id);
    if (
      !exists(descriptor) ||
      !localAsk(descriptor) ||
      (!actionAsk?.local && !requestAsk)
    )
      continue;
    const surface = surfaceFor(descriptors, projection, descriptor);
    inventory.push({
      id: surface.id,
      tag: surface.tag,
      sourceId: descriptor.id,
      sourceTag: descriptor.tag,
      thread:
        descriptor.document.kind === "thread"
          ? (descriptor.document.thread ?? null)
          : null,
    });
  }
  const documentOrder = new Map(
    [...descriptors.keys()].map((id, index) => [id, index]),
  );
  const all = [
    ...new Map(
      inventory
        .sort(
          (left, right) =>
            (documentOrder.get(left.id) ??
              documentOrder.get(left.sourceId) ??
              Infinity) -
            (documentOrder.get(right.id) ??
              documentOrder.get(right.sourceId) ??
              Infinity),
        )
        .map((record) => [`${record.thread ?? ""}:${record.id}`, record]),
    ).values(),
  ];
  const unansweredAwaiting: Record<string, boolean> = {};
  const awaiting: Record<string, boolean> = {};
  const unansweredBySource = new Map<string, boolean>();

  for (const descriptor of descriptors.values()) {
    const awaits = descriptor.declaration["x-awaits"] as
      | { rollup?: boolean }
      | undefined;
    if (awaits && !awaits.rollup) {
      const actionAsk = actionAsks.get(descriptor.id);
      const open =
        exists(descriptor) &&
        Boolean(actionAsk?.local) &&
        !actionAskAnswered(
          document,
          projection,
          descriptor,
          actionAsk ?? { answers: [], explicit: false },
        );
      unansweredBySource.set(descriptor.id, open);
      unansweredAwaiting[descriptor.id] = open;
      awaiting[descriptor.id] =
        open &&
        !(
          descriptor.document.kind === "page" &&
          descriptor.conversation !== null &&
          descriptor.conversation !== undefined &&
          conditionMatches(
            descriptor.conversation.authored,
            descriptor.conversation.when,
          ) &&
          threads.some(
            (thread: any) =>
              thread.seat === descriptor.id && thread.awaits_agent && !thread.resolved,
          )
        );
    } else if (
      (descriptor.declaration["x-request"] as { ask?: boolean } | undefined)?.ask
    ) {
      const open =
        exists(descriptor) &&
        requestPhase(descriptor, lifecycle, pendingRequestEvents) === "ready";
      unansweredBySource.set(descriptor.id, open);
      unansweredAwaiting[descriptor.id] = open;
      awaiting[descriptor.id] = open;
    }
  }

  const direct = new Map<string, WidgetDescriptor[]>();
  for (const candidate of descriptors.values()) {
    const candidateAwaits = candidate.declaration["x-awaits"] as
      | { rollup?: boolean }
      | undefined;
    if (!localAsk(candidate) && !candidateAwaits?.rollup) continue;
    let holder = projectedParent(descriptors, projection, candidate);
    const seen = new Set([candidate.id]);
    while (holder && !seen.has(holder.id)) {
      seen.add(holder.id);
      const holderAwaits = holder.declaration["x-awaits"] as
        | { rollup?: boolean }
        | undefined;
      if (holderAwaits?.rollup) {
        const children = direct.get(holder.id) ?? [];
        children.push(candidate);
        direct.set(holder.id, children);
        break;
      }
      holder = projectedParent(descriptors, projection, holder);
    }
  }

  const rollup = new Map<string, boolean>();
  const rollupValue = (owner: WidgetDescriptor, stack = new Set<string>()): boolean => {
    if (rollup.has(owner.id)) return rollup.get(owner.id)!;
    if (stack.has(owner.id) || !exists(owner)) return false;
    const nextStack = new Set(stack).add(owner.id);
    const value = (direct.get(owner.id) ?? []).some((candidate) => {
      if (!exists(candidate)) return false;
      const candidateAwaits = candidate.declaration["x-awaits"] as
        | { rollup?: boolean }
        | undefined;
      return candidateAwaits?.rollup
        ? rollupValue(candidate, nextStack)
        : Boolean(unansweredBySource.get(candidate.id));
    });
    rollup.set(owner.id, value);
    return value;
  };
  for (const descriptor of descriptors.values())
    if (
      (descriptor.declaration["x-awaits"] as { rollup?: boolean } | undefined)?.rollup
    ) {
      const open = rollupValue(descriptor);
      unansweredAwaiting[descriptor.id] = open;
      awaiting[descriptor.id] = open;
    }

  const unanswered = all.filter((ask) => unansweredBySource.get(ask.sourceId) ?? false);
  const reader = all.filter((ask) => awaiting[ask.sourceId] ?? false);
  return { all, reader, unanswered, awaiting, unansweredAwaiting };
}

const NO_ASKS: ReturnType<typeof deriveAsks> = {
  all: [],
  reader: [],
  unanswered: [],
  awaiting: {},
  unansweredAwaiting: {},
};

const isReaction = (message: any) => Boolean(message.token);

function deriveThreadReaderObligations(
  document: SemanticDocument,
  threads: Thread[],
  asks: ReturnType<typeof deriveAsks>,
) {
  const openAskThreads = new Set(
    asks.reader
      .map((ask) => ask.thread)
      .filter((thread): thread is string => Boolean(thread)),
  );
  const asksByMessage = new Map<string, WidgetDescriptor[]>();
  for (const descriptor of document.descriptors.values()) {
    if (descriptor.document.kind !== "thread" || !localAsk(descriptor)) continue;
    const message = descriptor.document.message;
    if (typeof message !== "string") continue;
    const existing = asksByMessage.get(message) ?? [];
    existing.push(descriptor);
    asksByMessage.set(message, existing);
  }
  const settlingTokens = (document.registry["$reactions"]?.tokens ?? {}) as Record<
    string,
    { settles?: boolean }
  >;
  return threads.map((thread: any) => {
    let awaitsReader = false;
    if (!thread.resolved) {
      if (openAskThreads.has(thread.root.id)) awaitsReader = true;
      else {
        const turns = thread.msgs.filter((message: any) => !isReaction(message));
        const last = turns.at(-1);
        if (last?.author === "claude") {
          const declared =
            last.kind === "reply" ? (asksByMessage.get(last.id) ?? []) : [];
          const structuralAnswered =
            declared.length > 0 &&
            !declared.some((descriptor) => asks.awaiting[descriptor.id]);
          const expectsReply =
            last.kind !== "reply" || declared.length > 0 || Boolean(last.awaits);
          const settledByReaction = thread.msgs.some(
            (message: any) =>
              isReaction(message) &&
              message.author === "user" &&
              message.parent === last.id &&
              settlingTokens[message.token]?.settles,
          );
          awaitsReader = expectsReply && !structuralAnswered && !settledByReaction;
        }
      }
    }
    return thread.awaits_reader === awaitsReader
      ? thread
      : { ...thread, awaits_reader: awaitsReader };
  });
}

function requirementMatches(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
  requirement: { target: "self" | "owner"; awaiting: boolean },
) {
  if (requirement.target === "self")
    return (
      Boolean(root.effective.asks.unansweredAwaiting[descriptor.id]) ===
      requirement.awaiting
    );
  const declaredOwners = (descriptor.declaration["x-owners"] ?? []) as string[];
  let child: WidgetDescriptor | undefined = descriptor;
  const visited = new Set([descriptor.id]);
  while (child) {
    const positioned = [...root.effective.projection.desired.values()].find(
      ({ unit, spec }) => unit === child?.id && spec.record?.kind === "position",
    );
    const parentId = positioned
      ? positioned.e.detail[positioned.spec.record.value]
      : child.parent?.id;
    if (typeof parentId !== "string" || visited.has(parentId)) return false;
    visited.add(parentId);
    const parent = root.document.descriptors.get(parentId) as
      | WidgetDescriptor
      | undefined;
    if (!parent) return false;
    if (declaredOwners.includes(parent.tag))
      return (
        Boolean(root.effective.asks.unansweredAwaiting[parent.id]) ===
        requirement.awaiting
      );
    child = parent;
  }
  return false;
}

function widgetReading(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
) {
  const registered = root.document.descriptors.get(descriptor.id);
  const currentDescriptor = JSON.stringify(registered) === JSON.stringify(descriptor);
  // A live revision connects and prepares replacement nodes before their complete
  // document capture is adopted. An id shared with the outgoing node must not lend the
  // replacement its old semantic facets during that preparation window.
  const current = currentDescriptor
    ? root.effective.widgets.get(descriptor.id)
    : undefined;
  const authored = currentDescriptor
    ? root.document.authored.get(descriptor.id)?.state
    : undefined;
  const declaration = descriptor.declaration;
  const actionSpecs = (declaration["x-state"] ?? {}) as Record<
    string,
    ActionSpec & {
      requires?: { target: "self" | "owner"; awaiting: boolean };
    }
  >;
  const projection = root.effective.projection;
  const classified = [...projection.classified.values()]
    .filter(
      ({ e, terminal }) => !terminal && e.kind === "action" && appliesTo(descriptor, e),
    )
    .sort((left, right) => (left.e.seq ?? 0) - (right.e.seq ?? 0));
  const desired = [...projection.actions.values()].filter(({ e }) =>
    appliesTo(descriptor, e),
  );
  const pending = root.unresolved.filter((entry) => appliesTo(descriptor, entry.event));
  const durableUndo = root.effective.lifecycle.undo
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
  const actions = Object.fromEntries(
    Object.entries(actionSpecs).map(([verb, spec]) => [
      verb,
      {
        available:
          currentDescriptor &&
          root.effective.hostAvailable &&
          root.phase !== "waiting" &&
          !descriptor.quoted &&
          (!spec.requires || requirementMatches(root, descriptor, spec.requires)),
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

  const request = (declaration["x-request"] ?? null) as {
    verbs?: Record<string, unknown>;
  } | null;
  const projectedRequest = pending.find(
    (entry) => entry.event.kind === "request",
  )?.event;
  const lifecycles =
    descriptor.document.kind === "thread"
      ? root.effective.lifecycle.conversation.requests
      : root.effective.lifecycle.page.requests;
  const lifecycle = projectedRequest
    ? {
        seat: { document: descriptor.document, widget: descriptor.id },
        attempts: [{ request: projectedRequest, receipt: null }],
        latest: { request: projectedRequest, receipt: null },
        phase: "pending",
      }
    : (lifecycles?.find((item) => item.seat.widget === descriptor.id) ??
      emptyLifecycle(descriptor));
  const offered = new Set(descriptor.offers.map(({ verb }) => verb));
  const requests = Object.fromEntries(
    Object.keys(request?.verbs ?? {}).map((verb) => [
      verb,
      {
        available:
          currentDescriptor &&
          root.effective.hostAvailable &&
          root.phase !== "waiting" &&
          !descriptor.quoted &&
          offered.has(verb) &&
          lifecycle.phase === "ready",
        unavailable: root.effective.hostAvailable
          ? null
          : "no agent or server is available",
      },
    ]),
  );
  const provenanceEntries = (current?.entries ?? []) as unknown as {
    e: Event;
    spec: ActionSpec;
    unit: string;
    value: unknown;
  }[];
  const provenance = Object.fromEntries(
    provenanceEntries.map(({ e, spec, unit, value }) => [
      `${spec.facet}:${unit}`,
      { event: e, unit, value },
    ]),
  );
  const holdingThread = root.effective.conversation.all.find(
    (thread: any) =>
      !thread.resolved &&
      !thread.root.pending &&
      thread.root.holds === descriptor.id,
  );
  return {
    authored: authored ?? {},
    state: current?.state ?? {},
    conversation: { heldBy: holdingThread?.root.id ?? null },
    provenance,
    actions,
    requests,
    request: lifecycle,
    delivery: pending.map((entry) => ({
      attempt: entry.event.attempt,
      kind: entry.event.kind,
      verb: entry.event.action,
      answered: entry.answered,
      rejected: entry.rejected,
    })),
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
    unresolved: [] as Event[],
    phase: "waiting",
    hostAvailable: true,
    data: { revision: -1, sources: {} },
    effective: derive(
      {
        revision: null,
        registry: {},
        authored: new Map(),
        descriptors: new Map(),
      },
      null,
      [],
      "waiting",
      true,
    ),
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  let order = 0;
  let signature = semanticSignature([initial.effective, initial.data, initial.phase]);
  let publicationDepth = 0;
  let activePresentation: SemanticPresentationPublication | null = null;

  if (presentation) presentation.seal(presentation.begin(initial.semanticEpoch));

  function derive(
    document: SemanticDocument,
    state: AuthoritativeState | null,
    unresolved: Event[],
    phase: string,
    hostAvailable: boolean,
  ) {
    const receipts = state?.browser.receipts ?? [];
    const pending = unresolved.map((entry) =>
      entry.projection?.kind === "undo"
        ? {
            ...entry,
            projection: {
              ...entry.projection,
              targetEntry: unresolved.find(
                (target) => target.event.attempt === entry.undoTarget,
              ) ?? {
                readEvent: receipts.find(
                  (receipt) => receipt.attempt === entry.undoTarget,
                ),
              },
            },
          }
        : entry,
    );
    const admitted = normalizedProjection(
      state?.browser.views[String(document.revision)],
      state?.browser.conversation,
    );
    const projection = foldProjection({
      ...admitted,
      pendingEntries: pendingProjectionEntries(pending, receipts),
    });
    const active = state?.browser.views[String(document.revision)];
    const lifecycle = {
      page: {
        requests: active?.document.requests ?? [],
      },
      conversation: {
        requests: state?.browser.conversation.requests ?? [],
      },
      undo: active?.undo ?? [],
    };
    // Threads and Asks both wait for an admitted reading. Authored markup names every
    // Ask the page could hold, but only the log says which of them it still holds and
    // whether they are answered, so before that reading there is no inventory to publish.
    const ready = phase === "ready";
    let threads = ready
      ? foldThreads(
          state?.browser.conversation.threads ?? [],
          unreadMessages(unresolved, receipts),
          pendingReactions(unresolved, receipts),
          pendingSettlements(unresolved, receipts),
        )
      : [];
    const widgets = foldWidgetStates(document.authored, projection);
    const projectedRequests = pendingRequests(unresolved, receipts);
    const asks = ready
      ? deriveAsks(document, projection, widgets, threads, lifecycle, projectedRequests)
      : NO_ASKS;
    let admittedUnansweredAsks = asks.unanswered;
    if (ready && unresolved.length) {
      const admittedProjection = foldProjection(admitted);
      admittedUnansweredAsks = deriveAsks(
        document,
        admittedProjection,
        foldWidgetStates(document.authored, admittedProjection),
        foldThreads(state?.browser.conversation.threads ?? [], [], [], []),
        lifecycle,
        [],
      ).unanswered;
    }
    threads = deriveThreadReaderObligations(document, threads, asks);
    return {
      hostAvailable,
      projection,
      widgets,
      conversation: { all: threads, listed: threads.filter(conversational) },
      asks,
      // Approval is irreversible. While projection paint is deferred, its gate uses
      // this admitted selection instead of an optimistic answer the reader cannot yet
      // see committed to the document.
      admittedUnansweredAsks,
      // These are semantic inputs to package rendering, not transport metadata.
      // A worker row with no report dates its claim from the active revision, while
      // report-backed rows render the accepted update sequence. Keep both inside the
      // publication signature so their public watchers cannot miss a state read whose
      // projection and widget facets happen to be unchanged.
      updates: active?.updates ?? [],
      publishedAt: active?.published_at ?? null,
      pendingApprovals: pendingApprovals(unresolved, receipts),
      pendingRequests: projectedRequests,
      delivery: unresolvedAttempts(unresolved),
      activity: state?.activity ?? null,
      lifecycle,
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

  // An answer this document can take on with `revision` showing: not overtaken by one
  // already adopted, and holding a view of the revision that would be current.
  const adoptable = (
    state: AuthoritativeState,
    candidate: SemanticDocument | number | null,
  ) => {
    const prior = publisher.read();
    if (
      prior.authoritative &&
      (state.taken < prior.authoritative.taken ||
        state.browser.basis.through_seq <
          prior.authoritative.browser.basis.through_seq ||
        state.active.revision < prior.authoritative.active.revision)
    )
      return false;
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
  const update = (attempt: string, change: (entry: Event) => Event) =>
    publish({
      unresolved: publisher
        .read()
        .unresolved.map((item) =>
          item.event.attempt === attempt ? change(item) : item,
        ),
    });

  return Object.freeze({
    read: publisher.read,
    select: publisher.select,
    // Version comparison receives a server projection already interpreted through the
    // requested revision's registry. Keep that admitted spec on the wire; the current
    // document contract must not reinterpret historical events.
    projectView(
      view: AuthoritativeState["browser"]["views"][string],
      conversation: AuthoritativeState["browser"]["conversation"],
    ) {
      return foldProjection({
        ...normalizedProjection(view, conversation),
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
    acceptData(data: typeof initial.data) {
      if (data.revision <= publisher.read().data.revision) return false;
      publish({ data: structuredClone(data) });
      return true;
    },
    // Whether this answer could be adopted with `revision` showing, asked without
    // adopting it. A live activation patches the document before it adopts, and a patch
    // is not something to undo, so the candidate is judged before the reader's page is
    // touched. One definition read from two places, because two would be one edit away
    // from a document patched to a revision the answer it was patched for declines to
    // speak for.
    canAdopt(
      state: AuthoritativeState,
      document: SemanticDocument | number | null = null,
    ) {
      return adoptable(state, document);
    },
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
      const shown = document?.revision ?? prior.document.revision;
      const basis = state.browser.views[String(shown)]!.basis;
      if (
        basis.revision !== shown ||
        basis.through_seq !== state.browser.basis.through_seq
      )
        throw new TypeError("state browser has no matching revision view");
      const authoritative = structuredClone(state);
      const unresolved = prior.unresolved.map((item) => {
        const receipt = authoritative.browser.receipts.find(
          (receipt) => receipt.attempt === item.event.attempt,
        );
        return receipt ? { ...item, readEvent: receipt } : item;
      });
      publish({
        document: document
          ? {
              ...structuredClone(document),
              stamp: document.stamp ?? state.active.version ?? null,
              authored: new Map(structuredClone(document.authored)),
              descriptors: new Map(structuredClone(document.descriptors)),
            }
          : prior.document,
        authoritative,
        unresolved,
        phase: "ready",
      });
      return true;
    },
    enqueue(event: Event, timestamp: string) {
      if (entry(event.attempt)) return null;
      const before = publisher.read();
      const localId = PENDING + event.attempt;
      const conversation = isConversationEvent(event)
        ? conversationForAttempt(event, timestamp)
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
                coordinate: JSON.stringify([event.widget, unit, spec.facet]),
                localOrder,
                e: { ...event, id: localId },
                value: spec.record ? foldedFacet(event, spec.record) : event.action,
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
            conversation,
            message: isMessageEvent(event) ? conversation : null,
            undoTarget: undoTarget?.event.attempt ?? null,
            answered: false,
            rejected: false,
            readEvent: null,
            presented: false,
          },
        ],
      });
      return entry(event.attempt);
    },
    remove(attempts: Set<string>) {
      return publish({
        unresolved: publisher
          .read()
          .unresolved.filter((item) => !attempts.has(item.event.attempt)),
      });
    },
    accept(attempt: string, accepted: Event) {
      const item = entry(attempt);
      if (!item) return;
      if (item.presented && item.event.kind !== "action") {
        this.remove(new Set([attempt]));
        return;
      }
      update(attempt, (item) => ({
        ...item,
        answered: true,
        acceptedId: accepted?.id ?? null,
      }));
    },
    reject(attempt: string) {
      const rejected = entry(attempt);
      if (!rejected) return [];
      const removed = new Set<string>();
      if (rejected.event.kind !== "action") removed.add(attempt);
      for (const item of publisher.read().unresolved)
        if (
          item.undoTarget === attempt ||
          (rejected.message?.id && item.event.parent === rejected.message.id)
        )
          removed.add(item.event.attempt);
      publish({
        unresolved: publisher
          .read()
          .unresolved.filter((item) => !removed.has(item.event.attempt))
          .map((item) =>
            item.event.attempt === attempt
              ? { ...item, answered: true, acceptedId: null, rejected: true }
              : item,
          ),
      });
      return [...removed];
    },
    accountPresented(receipts: Event[]) {
      const byAttempt = new Map(receipts.map((receipt) => [receipt.attempt, receipt]));
      const removed: string[] = [];
      const unresolved = publisher.read().unresolved.flatMap((item) => {
        const receipt = byAttempt.get(item.event.attempt);
        if (!receipt) return [item];
        if (item.answered && item.event.kind !== "action") {
          removed.push(item.event.attempt);
          return [];
        }
        return [{ ...item, readEvent: receipt, presented: true }];
      });
      publish({ unresolved });
      return removed;
    },
    nameParent(attempt: string, receipts: Event[]) {
      const item = entry(attempt);
      const parent = item?.event.parent;
      if (typeof parent !== "string" || !parent.startsWith(PENDING)) return;
      const parentAttempt = parent.slice(PENDING.length);
      const named =
        entry(parentAttempt)?.acceptedId ??
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
        entry(item.undoTarget)?.acceptedId ??
        receipts.find((receipt) => receipt.attempt === item.undoTarget)?.id;
      if (!named) return false;
      update(attempt, (item) => ({ ...item, event: { ...item.event, undoes: named } }));
      return true;
    },
  });
}
