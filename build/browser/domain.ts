/** Browser domain values. Kernel records derive from the admission registry;
 * these types describe the projections and local gestures the browser owns.
 */
import type {
  Event,
  EventMap,
  BrowserCommand,
  CompleteUnion,
} from "./event-contract.js";
export type { Event, EventMap, BrowserCommand };
import type { Immutable } from "./snapshot.ts";
export type StateRecord =
  | { kind: "body" }
  | { kind: "attribute" | "value"; attr: string }
  | { kind: "position"; within: string };
export interface ActionSpec {
  unit: string;
  record?: StateRecord;
  writer?: "user" | "agent";
  update?: boolean;
  creates?: { child: string; [key: string]: unknown };
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
export type MessageEvent = CompleteUnion<EventMap["comment"] | EventMap["reply"]>;
export type LocalMessage = Extract<Command, { kind: "comment" | "reply" }> & {
  id: string;
  author: string;
  ts: string;
  pending: true;
  plainText: string;
};
export type StreamingMessage = {
  id: string;
  attempt: string;
  kind: "reply";
  addressable: false;
  author: "agent";
  agent: string | null;
  parent: string;
  text: string;
  ts: string;
  pending: boolean;
};
export type Message = CompleteUnion<MessageEvent | LocalMessage | StreamingMessage> & {
  agent?: string | null;
  pending?: boolean;
  edited?: { id: string; seq: number; ts: string };
  addressable?: boolean;
  plainText?: string;
};
export type Attention = {
  kind: "waiting" | "needs_user";
  reason: string;
  workflow: string | null;
} | null;
export interface Thread {
  id: string;
  root: Message;
  msgs: Message[];
  title: string | null;
  anchor: Anchor | null;
  detached_from: Anchor | null;
  rewritten_from: Anchor | null;
  resolved:
    EventMap["resolve"] | EventMap["action"] | { author: string; pending: true } | null;
  user_prompt: { message: string; [key: string]: unknown } | null;
  bare_reaction: boolean;
  seat: string | null;
  summaries: readonly (Pick<
    EventMap["summary"],
    "id" | "seq" | "from" | "through" | "text"
  > & {
    label: string;
    covers: readonly string[];
    protected: readonly string[];
    trigger?: string;
  })[];
  unread: readonly ContentVersion[];
  attention: Attention;
  settling?: "resolve" | "unresolve";
}
export type Settlement = Extract<Command, { kind: "resolve" | "unresolve" }> & {
  localParent?: string;
};
export type WidgetEvent = EventMap["action"] | EventMap["report"];
export type LocalAction = Extract<Command, { kind: "action" }> & {
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
export interface Coverage {
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
export interface StandingValue {
  action: string | null;
  value: unknown;
  detail: Record<string, unknown>;
}
export interface UnitValue {
  value: Record<string, string[]>;
  units: Record<string, StandingValue>;
}
export interface PositionValue extends UnitValue {
  ranks: Record<string, string>;
}
export interface AuthoredWidget {
  tag: string;
  state: Record<string, StandingValue | UnitValue | PositionValue>;
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
