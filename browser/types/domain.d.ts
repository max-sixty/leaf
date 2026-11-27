/** Browser domain values. Kernel records derive from the admission registry;
 * these types describe the projections and local gestures the browser owns.
 */
import type {
  Event,
  EventMap,
  BrowserCommand,
  CompleteUnion,
  MessageKind,
  ServedReading,
  ServedState,
  ServedVerb,
  ServedWorkflow,
  WidgetKind,
} from "./contract.js";
export type { Event, BrowserCommand };
import type { Immutable } from "../runtime/base/snapshot.js";
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
/** One piece of news a reading carries (host/semantic-news.js), as the announcer queues
 * it (transport/notifications.js). */
export type SemanticNews = ContentNews | FailureNews | ObligationNews | EmptiedNews;
type ContentNews = {
  kind: "agent_content";
  key: string;
  thread: string;
  message: Message;
  version: string;
};
type FailureNews = {
  kind: "response_failure";
  key: string;
  condition: "failed" | "interrupted";
  input: string;
  thread: string | null;
  seq: number;
};
export type ObligationNews = {
  kind: "user_obligation";
  key: string;
  sourceKey: string;
  episode: number;
  source: string;
  thread: string | null;
  message: string | null;
};
type EmptiedNews = {
  kind: "on_me_empty";
  key: string;
};
/** A publication as `leaf.source.data.read_source` serves it, before widget delivery. */
export type SourceReading = NonNullable<ServedReading["data"]["sources"]>[string];
/** A workflow as the application state publishes it, local sends included before the
 * server can classify them: a `local` send waits on the agent, or is blocked where the
 * server refused it, and a widget move has no coordinate the server has read. A send
 * `launching` waits for the server to launch the page's agent first. */
export type Workflow = Published<ServedWorkflow>;
type Published<T> = T extends unknown
  ? Omit<T, "coordinate"> & {
      coordinate: readonly (string | null)[] | null;
      local?: boolean;
      launching?: boolean;
    }
  : never;
export type Anchor = NonNullable<EventMap["comment"]["anchor"]>;
/** A comment's drawing as its draft holds it, with `at`, the matrix from its local frame
 * into its anchor's section when last drawn on (annotations/composing/drawing-record.js). */
export type DraftDrawing = NonNullable<EventMap["comment"]["drawing"]> & {
  at?: readonly [number, number, number, number, number, number];
};
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
  | LocalMessage
  | LocalEdit
  | Settlement
  | Extract<Command, { kind: "undo" }>;
/** A message as a served thread holds it (`Message` in `state.schema.json`): a logged
 * comment or reply naming its current content version, or a provisional reply. Its
 * `edited` joins a rewrite this tab has not sent yet, which has no `seq`, and its
 * `withdrawn` an undo this tab has not sent yet, which has no id or time. */
type ServedMessage = Without<
  NonNullable<
    ServedState["browser"]
  >["views"][string]["thread"]["threads"][number]["msgs"][number],
  "edited" | "withdrawn"
>;
type Without<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;
export type Message = CompleteUnion<ServedMessage | LocalMessage> & {
  // The name it is drawn under where the server gives one (`thread.messageKey`).
  key?: string;
  agent?: string | null;
  pending?: boolean;
  edited?: { id: string; seq?: number; ts: string; was: string; pending?: true };
  withdrawn?: { id: string; ts: string; was: string } | { was: string; pending: true };
  addressable?: boolean;
  plainText?: string;
};
/** The id of the obligation record that speaks for a thread (`standing.leading`), or
 * null where nobody owes a move there. */
export type Attention = string | null;
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
    "id" | "seq" | "from" | "through" | "text" | "label"
  > & {
    covers: readonly string[];
  })[];
  unread: Readonly<Record<string, string>>;
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
// A widget event or undo in the log, at the coordinate its view classifies it at, an
// undo at its target's, or null (`logCoverage` in `state/semantic-application.js`).
export interface Coverage {
  event: Event;
  coordinate: readonly string[] | null;
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
/** A widget's reading as the `state` property Leaf sets on an element it drives
 * (host/widget-controller.js, `widgetState`): each declared verb's folded state, whether
 * the user may act on it now and the reason they may not, and whether Undo would take
 * back the action in force, on each unit of a verb that holds a state for each. */
export type WidgetState = Immutable<
  Record<
    string,
    | (UndoableAction & OfferedVerb)
    | (Omit<UnitValue, "units"> & {
        units: Record<string, UndoableAction>;
      } & OfferedVerb)
    | (Omit<PositionValue, "units"> & {
        units: Record<string, UndoableAction>;
      } & OfferedVerb)
  >
>;
type UndoableAction = ActionValue & { undoable: boolean };
type OfferedVerb = { available: boolean; unavailable: string | null };

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
