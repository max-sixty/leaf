// Compiled from model.ts by build/typescript.mjs; edit that file.
/* Pure readings of the events an unresolved browser gesture carries.

   The ledger holding each gesture, and the lifecycle that decides when it leaves, belong
   to the application publisher (`runtime/state/semantic-application.js`). */
import { PENDING } from "../thread/identity.js";
import { MESSAGE_KINDS } from "../kernel-facts.js";

export const isThreadEvent = (event) => MESSAGE_KINDS.has(event.kind);

// The widget an action concerns, or an undo of one: the only gestures that carry what
// the widget works out of its state (`facts`), its word on whether its obligation is
// answered among them (`awaits`).
export const gestureWidget = ({ event, projection }) =>
  event.kind === "action"
    ? event.widget
    : projection?.kind === "undo"
      ? projection.target.e.widget
      : null;

// A gesture that speaks in a thread, so hands it to the agent: a message, in words or
// an emoji, or the user rewriting words of theirs (`events.exchange`).
// `tests/turn_cases.json` holds this and `turnMessage` to the server's reading.
export const isTurnEvent = (event) => isThreadEvent(event) || event.kind === "edit";

// The message a turn shows on: a rewrite's message, else its own (`events.turn_message`).
export const turnMessage = (turn) =>
  turn.kind === "edit" && turn.message ? turn.message : turn.id;

export const threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  content_version: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true,
});

// A rewrite as this tab draws it on its message before the log has it.
export const editForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: true,
});

// The fields through which a command names another event: a reply's or settlement's
// `parent`, a rewrite's `message` and the revision it was written over (`base`), an
// undo's `undoes`. A gesture of this tab's still sending is named there by its pending
// id, so these are the gesture's dependencies on the ledger. Each is renamed to the id
// the log gave once the log has answered (`nameAdmitted`), and a gesture naming one the
// log refused goes with it (`refuse`, state/semantic-application.js). A new field naming an event
// joins this list, and nothing that reads or renames dependencies changes.
const NAMING_FIELDS = ["parent", "message", "base", "undoes"];

const pendingId = (value) => typeof value === "string" && value.startsWith(PENDING);

/** Whether `event` names the event `id` in any field that names an event. */
export const namesEvent = (event, id) =>
  NAMING_FIELDS.some((field) => event[field] === id);

/** Whether `event` still names a gesture of this tab's by its pending id. */
export const namesPending = (event) =>
  NAMING_FIELDS.some((field) => pendingId(event[field]));

/** `event` with each pending id it names replaced by the id `admitted` gives that
 * gesture's attempt, where the log has one; `event` itself where none changes. */
export const nameAdmitted = (event, admitted) => {
  let named = event;
  for (const field of NAMING_FIELDS) {
    const value = event[field];
    const id = pendingId(value) ? admitted(value.slice(PENDING.length)) : null;
    if (id) named = { ...named, [field]: id };
  }
  return named;
};

/** The widget dispatcher's command, before the ledger assigns its attempt. */
export const actionForWidget = (descriptor, command, revision) => ({
  kind: "action",
  revision,
  widget: descriptor.id,
  action: command.verb,
  detail: structuredClone(command.detail ?? {}),
  ...(command.attempt && { attempt: command.attempt }),
});
