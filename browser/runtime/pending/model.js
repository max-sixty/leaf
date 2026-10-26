// @ts-check
/* Pure readings of the events an unresolved browser gesture carries.

   The ledger holding each gesture, and the lifecycle that decides when it leaves, belong
   to the application publisher (`runtime/framework/application.js`). */
import { PENDING } from "../thread/identity.js";
import { MESSAGE_KINDS } from "../kernel-facts.js";

/** @param {import("../../types/domain.js").Command} event
 * @returns {event is Extract<import("../../types/domain.js").Command, {kind: import("../../types/contract.js").MessageKind}>}
 */
export const isThreadEvent = (event) => MESSAGE_KINDS.has(event.kind);

/** @param {import("../../types/domain.js").Command} event */
export const isMessageEvent = (event) => isThreadEvent(event) && !event.token;

// A gesture that speaks in a thread, so hands it to the agent: words, or the user
// rewriting words of theirs (`events.exchange`). `tests/turn_cases.json` holds this and
// `turnMessage` to the server's reading.
/** @param {import("../../types/domain.js").Command} event */
export const isTurnEvent = (event) => isMessageEvent(event) || event.kind === "edit";

// The message a turn shows on: a rewrite's message, else its own (`events.turn_message`).
/** @param {{kind: string, id: string, message?: string}} turn @returns {string} */
export const turnMessage = (turn) =>
  turn.kind === "edit" && turn.message ? turn.message : turn.id;

/** @param {Extract<import("../../types/domain.js").Command, {kind: import("../../types/contract.js").MessageKind}>} event
 * @param {string} timestamp
 */
export const threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  content_version: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: /** @type {const} */ (true),
});

// A rewrite as this tab draws it on its message before the log has it.
/** @param {Extract<import("../../types/domain.js").Command, {kind: "edit"}>} event
 * @param {string} timestamp
 * @returns {import("../../types/domain.js").LocalEdit}
 */
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
// log refused goes with it (`refuse`, framework/application.js). A new field naming an event
// joins this list, and nothing that reads or renames dependencies changes.
const NAMING_FIELDS = /** @type {const} */ (["parent", "message", "base", "undoes"]);

/** @param {unknown} value @returns {value is string} */
const pendingId = (value) => typeof value === "string" && value.startsWith(PENDING);

/** Whether `event` names the event `id` in any field that names an event.
 * @param {import("../../types/domain.js").Command} event @param {string} id
 */
export const namesEvent = (event, id) =>
  NAMING_FIELDS.some(
    (field) => /** @type {Record<string, unknown>} */ (event)[field] === id,
  );

/** Whether `event` still names a gesture of this tab's by its pending id.
 * @param {import("../../types/domain.js").Command} event
 */
export const namesPending = (event) =>
  NAMING_FIELDS.some((field) =>
    pendingId(/** @type {Record<string, unknown>} */ (event)[field]),
  );

/** `event` with each pending id it names replaced by the id `admitted` gives that
 * gesture's attempt, where the log has one; `event` itself where none changes.
 * @template {import("../../types/domain.js").Command} E
 * @param {E} event @param {(attempt: string) => string | null} admitted @returns {E}
 */
export const nameAdmitted = (event, admitted) => {
  let named = event;
  for (const field of NAMING_FIELDS) {
    const value = /** @type {Record<string, unknown>} */ (event)[field];
    const id = pendingId(value) ? admitted(value.slice(PENDING.length)) : null;
    if (id) named = { ...named, [field]: id };
  }
  return named;
};

/** @template {{event: import("../../types/domain.js").Command, namedParent?: string}} T
 * @param {readonly T[]} entries @param {string} id @param {string[] | null} kinds
 */
export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );

/** The widget dispatcher's command, before the ledger assigns its attempt.
 * @param {Pick<import("../framework/application.js").WidgetDescriptor, "id">} descriptor
 * @param {{verb: string, detail?: Record<string, unknown>, attempt?: string}} command
 * @param {number} revision
 * @returns {Extract<import("../../types/domain.js").BrowserCommand, {kind: "action"}>}
 */
export const actionForWidget = (descriptor, command, revision) => ({
  kind: "action",
  revision,
  widget: descriptor.id,
  action: command.verb,
  detail: structuredClone(command.detail ?? {}),
  ...(command.attempt && { attempt: command.attempt }),
});
