/** Browser domain values. Kernel records derive from the admission registry;
 * these types describe the projections and local gestures the browser owns.
 */
import type {
  Event,
  EventMap,
  BrowserCommand,
  CompleteUnion,
  MessageKind,
  ServedState,
  ServedVerb,
  ServedAttention,
  WidgetKind,
} from "./contract.js";
export type { Event, BrowserCommand };
import type { Immutable } from "../runtime/framework/snapshot.js";
export type StateRecord = NonNullable<ServedVerb["record"]>;
export interface ActionSpec {
  unit: string;
  record?: StateRecord;
  writer?: "user" | "agent";
  text?: boolean;
  creates?: { child: string; words: string };
  detail?: object | boolean;
}
export type Command = BrowserCommand & { attempt: string };
type OptionalAttempt<T> = T extends unknown
  ? Omit<T, "attempt"> & { attempt?: string }
  : never;
export type PendingCommand = OptionalAttempt<Command>;
export type Anchor = NonNullable<EventMap["comment"]["anchor"]>;
export interface ContentVersion {
  message: string;
  version: string;
}
export type LocalMessage = Extract<Command, { kind: MessageKind }> & {
  id: string;
  content_version: string;
  author: string;
  ts: string;
  pending: true;
  plainText: string;
};
/** The user's rewrite of one of their messages, as this tab draws it before the log
 * has it. */
export type LocalEdit = Extract<Command, { kind: "edit" }> & {
  id: string;
  author: "user";
  ts: string;
  pending: true;
};
/** A user's edit as a thread holds it, with the words it replaced. */
type Revision = (EventMap["edit"] | LocalEdit) & { was: string };
/** What the ledger hands `foldThreads`: each message or rewrite as the thread draws it,
 * each settlement, and each undo. */
export type ThreadGesture =
  LocalMessage | LocalEdit | Settlement | Extract<Command, { kind: "undo" }>;
/** A message as a served thread holds it (`Message` in `state.schema.json`): a logged
 * comment or reply naming its current content version, or a provisional reply. Its
 * `edited` joins a rewrite this tab has not sent yet, which has no `seq`. */
type ServedMessage = Without<
  NonNullable<
    ServedState["browser"]
  >["views"][string]["thread"]["threads"][number]["msgs"][number],
  "edited"
>;
type Without<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
export type Message = CompleteUnion<ServedMessage | LocalMessage> & {
  // The name it is drawn under where the server gives one (`thread.messageKey`).
  key?: string;
  agent?: string | null;
  pending?: boolean;
  edited?: { id: string; seq?: number; ts: string; was: string; pending?: true };
  addressable?: boolean;
  plainText?: string;
};
export type Attention = ServedAttention;
export interface Thread {
  id: string;
  root: Message;
  msgs: readonly Message[];
  title: string | null;
  anchor: Anchor | null;
  detached_from: Anchor | null;
  rewritten_from: Anchor | null;
  revisions: readonly Revision[];
  resolved: CompleteUnion<
    | NonNullable<
        ServedState["browser"]
      >["views"][string]["thread"]["threads"][number]["resolved"]
    | { author: "user"; pending: true }
  > | null;
  bare_reaction: boolean;
  seat: string | null;
  summaries: readonly (Pick<
    EventMap["summary"],
    "id" | "seq" | "from" | "through" | "text"
  > & {
    label: string;
    covers: readonly string[];
    protected: readonly string[];
  })[];
  unread: readonly ContentVersion[];
  attention: Attention;
}
export type Settlement = Extract<Command, { kind: "resolve" | "unresolve" }> & {
  localParent?: string;
};
type WidgetEvent = EventMap[WidgetKind];
type LocalAction = Extract<Command, { kind: "action" }> & {
  id: string;
  seq?: never;
  meaning: { state: unknown };
};
export interface ProjectionEntry {
  coordinate: string;
  kind?: never;
  e: WidgetEvent | LocalAction;
  unit: string;
  spec: ActionSpec;
  value: unknown;
  restated?: readonly string[];
  absorbed?: boolean;
  stands?: boolean;
  scope?: string;
  terminal?: boolean;
  localOrder?: number;
}
export type PendingProjection =
  | ProjectionEntry
  | {
      kind: "undo";
      target: ProjectionEntry;
      targetId?: string | null;
      coordinate: string;
      localOrder: number;
    };
interface Coverage {
  event: Event;
  coordinate: unknown;
}
export interface ProjectionInput {
  entries?: readonly ProjectionEntry[];
  actionIds?: string[];
  reportIds?: string[];
  desiredIds?: string[];
  coverage?: readonly Coverage[];
  pendingEntries?: readonly PendingProjection[];
}
export interface ActionValue {
  action: string | null;
  value: unknown;
  detail: Record<string, unknown>;
}
export interface UnitValue {
  detail?: never;
  value: Record<string, string[]>;
  units: Record<string, ActionValue>;
}
export interface PositionValue extends UnitValue {
  ranks: Record<string, string>;
}
export interface AuthoredWidget {
  tag: string;
  state: Record<string, ActionValue | UnitValue | PositionValue>;
  specs: ReadonlyMap<string, ActionSpec>;
}
export type AuthoredMap = ReadonlyMap<string, Immutable<AuthoredWidget>>;

export type ClassifiedEntry =
  | ProjectionEntry
  | {
      e: Event;
      terminal: boolean;
      coordinate?: never;
      stands?: never;
      localOrder?: never;
      unit?: never;
      spec?: never;
      value?: never;
      restated?: never;
    };
export interface Projection {
  actions: ReadonlyMap<string, ProjectionEntry>;
  reports: ReadonlyMap<string, readonly ProjectionEntry[]>;
  desired: ReadonlyMap<string, ProjectionEntry>;
  classified: ReadonlyMap<string, ClassifiedEntry>;
  pendingWithdrawals: ReadonlyMap<string, ClassifiedEntry>;
}
