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
  record?: { kind: string; value: string };
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

export interface SemanticDocument {
  revision: number | null;
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
  document: { kind: "page"; revision: number } | { kind: "thread" };
  declaration: Record<string, unknown>;
  parent: { id: string; tag: string } | null;
  ancestors: readonly { id: string; tag: string }[];
  quoted: boolean;
  bindings: Readonly<Record<string, string | null>>;
  offers: readonly { tag: string; attribute: string; verb: string }[];
}

export interface AuthoritativeState {
  taken: number;
  layer: { generation: string };
  active: { revision: number };
  events: Event[];
  browser: {
    basis: { through_seq: number };
    views: Record<
      string,
      {
        basis: { revision: number; through_seq: number };
        document: {
          projection: WireProjection;
          asks?: {
            awaiting?: Record<string, boolean>;
            unanswered_awaiting?: Record<string, boolean>;
          };
          requests?: { seat: { widget: string }; phase: string }[];
        };
        undo?: { event: Event }[];
        coverage: object[];
      }
    >;
    conversation: {
      threads: Thread[];
      projection: WireProjection;
      asks?: { awaiting?: Record<string, boolean> };
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

function awaitingValue(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
) {
  const page = root.effective.lifecycle.page;
  const conversation = root.effective.lifecycle.conversation;
  return Boolean(
    page?.asks?.unanswered_awaiting?.[descriptor.id] ??
      conversation?.asks?.awaiting?.[descriptor.id],
  );
}

function requirementMatches(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
  requirement: { target: "self" | "owner"; awaiting: boolean },
) {
  if (requirement.target === "self")
    return awaitingValue(root, descriptor) === requirement.awaiting;
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
      return awaitingValue(root, parent) === requirement.awaiting;
    child = parent;
  }
  return false;
}

function widgetReading(
  root: ReturnType<ReturnType<typeof createSemanticApplication>["read"]>,
  descriptor: WidgetDescriptor,
) {
  const registered = root.document.descriptors.get(descriptor.id);
  const current = root.effective.widgets.get(descriptor.id);
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
      ({ e, terminal }) =>
        !terminal && e.kind === "action" && appliesTo(descriptor, e),
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
          JSON.stringify(registered) === JSON.stringify(descriptor) &&
          root.phase !== "waiting" &&
          !descriptor.quoted &&
          (!spec.requires || requirementMatches(root, descriptor, spec.requires)),
        history: classified.filter(({ e }) => e.action === verb).map(({ e }) => e),
        standing: desired
          .filter(({ e }) => e.action === verb)
          .map(({ e, unit, value }) => ({ event: e, unit, value })),
        undo: [...localUndo, ...durableUndo].filter((event) => event.action === verb),
      },
    ]),
  );

  const request = (declaration["x-request"] ?? null) as
    | { verbs?: Record<string, unknown> }
    | null;
  const projectedRequest = pending.find((entry) => entry.event.kind === "request")
    ?.event;
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
          JSON.stringify(registered) === JSON.stringify(descriptor) &&
          root.phase !== "waiting" &&
          !descriptor.quoted &&
          offered.has(verb) &&
          lifecycle.phase === "ready",
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
  return {
    state: current?.state ?? {},
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
    data: { revision: -1, sources: {} },
    effective: derive(
      { revision: null, registry: {}, authored: new Map(), descriptors: new Map() },
      null,
      [],
      "waiting",
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
    const projection = foldProjection({
      ...normalizedProjection(
        state?.browser.views[String(document.revision)],
        state?.browser.conversation,
      ),
      pendingEntries: pendingProjectionEntries(pending, receipts),
    });
    const threads =
      phase === "ready"
        ? foldThreads(
            state?.browser.conversation.threads ?? [],
            unreadMessages(unresolved, receipts),
            pendingReactions(unresolved, receipts),
            pendingSettlements(unresolved, receipts),
          )
        : [];
    const active = state?.browser.views[String(document.revision)];
    return {
      projection,
      widgets: foldWidgetStates(document.authored, projection),
      conversation: { all: threads, listed: threads.filter(conversational) },
      pendingApprovals: pendingApprovals(unresolved, receipts),
      pendingRequests: pendingRequests(unresolved, receipts),
      delivery: unresolvedAttempts(unresolved),
      activity: state?.activity ?? null,
      lifecycle: {
        page: {
          asks: active?.document.asks ?? {},
          requests: active?.document.requests ?? [],
        },
        conversation: {
          asks: state?.browser.conversation.asks ?? {},
          requests: state?.browser.conversation.requests ?? [],
        },
        undo: active?.undo ?? [],
      },
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
    identify(revision: number | null) {
      return publish({ document: { ...publisher.read().document, revision } });
    },
    captureAuthored(values: AuthoredMap, registry: SemanticDocument["registry"]) {
      return publish({
        document: {
          ...publisher.read().document,
          registry: structuredClone(registry),
          authored: new Map([...publisher.read().document.authored, ...values]),
        },
      });
    },
    captureDescriptors(values: ReadonlyMap<string, WidgetDescriptor>) {
      return publish({
        document: {
          ...publisher.read().document,
          descriptors: new Map([
            ...publisher.read().document.descriptors,
            ...structuredClone(values),
          ]),
        },
      });
    },
    forgetAuthored(owners: Set<string>) {
      return publish({
        document: {
          ...publisher.read().document,
          authored: new Map(
            [...publisher.read().document.authored].filter(([id]) => !owners.has(id)),
          ),
          descriptors: new Map(
            [...publisher.read().document.descriptors].filter(
              ([id]) => !owners.has(id),
            ),
          ),
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
    adopt(state: AuthoritativeState) {
      const prior = publisher.read();
      if (
        prior.authoritative &&
        (state.taken < prior.authoritative.taken ||
          state.browser.basis.through_seq <
            prior.authoritative.browser.basis.through_seq ||
          state.active.revision < prior.authoritative.active.revision)
      )
        return false;
      if (!state.browser.views[String(prior.document.revision)]) return false;
      const basis = state.browser.views[String(prior.document.revision)]!.basis;
      if (
        basis.revision !== prior.document.revision ||
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
      publish({ authoritative, unresolved, phase: "ready" });
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
