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
        document: { projection: WireProjection };
        coverage: object[];
      }
    >;
    conversation: { threads: Thread[]; projection: WireProjection };
    receipts: Event[];
  };
  activity: unknown;
  reading?: string;
  agent?: string;
}

function normalizedProjection(
  document: SemanticDocument,
  state: AuthoritativeState | null,
) {
  const entries = [];
  const actionIds = [];
  const reportIds = [];
  const desiredIds = [];
  const view = state?.browser.views[String(document.revision)];
  for (const projection of [
    view?.document.projection,
    state?.browser.conversation.projection,
  ]) {
    if (!projection) continue;
    for (const wire of projection.entries ?? []) {
      const e = wire.event;
      const widget = document.authored.get(e.widget);
      const spec =
        widget &&
        document.registry[widget.tag]?.[e.kind === "action" ? "x-state" : "x-report"]?.[
          e.action
        ];
      const coordinate = JSON.stringify(wire.coordinate);
      entries.push(
        spec
          ? {
              coordinate,
              e,
              restated: wire.restated ?? [],
              scope: wire.scope,
              spec,
              unit: wire.coordinate[1],
              value:
                spec.record?.kind === "attribute"
                  ? (wire.value as string[]).join(" ")
                  : wire.value,
            }
          : { coordinate, e, scope: wire.scope, terminal: true },
      );
    }
    actionIds.push(...(projection.actions ?? []));
    reportIds.push(...(projection.reports ?? []));
    desiredIds.push(...(projection.desired ?? []));
  }
  return { entries, actionIds, reportIds, desiredIds, coverage: view?.coverage ?? [] };
}

export function createSemanticApplication() {
  const initial = {
    document: { revision: null, registry: {}, authored: new Map() } as SemanticDocument,
    authoritative: null as AuthoritativeState | null,
    unresolved: [] as Event[],
    phase: "waiting",
    data: { revision: -1, sources: {} },
    effective: derive(
      { revision: null, registry: {}, authored: new Map() },
      null,
      [],
      "waiting",
    ),
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  let order = 0;
  let signature = semanticSignature([initial.effective, initial.data, initial.phase]);

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
      ...normalizedProjection(document, state),
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
    return {
      projection,
      widgets: foldWidgetStates(document.authored, projection),
      conversation: { all: threads, listed: threads.filter(conversational) },
      pendingApprovals: pendingApprovals(unresolved, receipts),
      pendingRequests: pendingRequests(unresolved, receipts),
      delivery: unresolvedAttempts(unresolved),
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
    return publisher.publish(next);
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
    forgetAuthored(owners: Set<string>) {
      return publish({
        document: {
          ...publisher.read().document,
          authored: new Map(
            [...publisher.read().document.authored].filter(([id]) => !owners.has(id)),
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
