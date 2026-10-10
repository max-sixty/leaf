// @ts-check
/* Pure readings of the events an unresolved browser gesture carries.

   The ledger holding each gesture, and the lifecycle that decides when it leaves, belong
   to the application publisher (`build/browser/application.ts`). */
import { PENDING } from "../thread/identity.js";

/** @param {import("../../../../../build/browser/domain.ts").Command} event
 * @returns {event is Extract<import("../../../../../build/browser/domain.ts").Command, {kind: "comment" | "reply"}>}
 */
export const isThreadEvent = (event) =>
  event.kind === "comment" || event.kind === "reply";

/** @param {import("../../../../../build/browser/domain.ts").Command} event */
export const isMessageEvent = (event) => isThreadEvent(event) && !event.token;

/** @param {Extract<import("../../../../../build/browser/domain.ts").Command, {kind: "comment" | "reply"}>} event
 * @param {string} timestamp
 */
export const threadForAttempt = (event, timestamp) => ({
  ...event,
  id: `${PENDING}${event.attempt}`,
  author: "user",
  ts: timestamp,
  pending: /** @type {const} */ (true),
});

/** @template {{event: import("../../../../../build/browser/domain.ts").Command, namedParent?: string}} T
 * @param {readonly T[]} entries @param {string} id @param {string[] | null} kinds
 */
export const pendingForParent = (entries, id, kinds = null) =>
  entries.find(
    (entry) =>
      (entry.event.parent === id || entry.namedParent === id) &&
      (!kinds || kinds.includes(entry.event.kind)),
  );

/** The widget dispatcher's command, before the ledger assigns its attempt.
 * @param {Pick<import("../../../../../build/browser/application.ts").WidgetDescriptor, "id">} descriptor
 * @param {{verb: string, detail?: Record<string, unknown>, attempt?: string}} command
 * @param {number} revision
 * @returns {Extract<import("../../../../../build/browser/domain.ts").BrowserCommand, {kind: "action"}>}
 */
export const actionForWidget = (descriptor, command, revision) => ({
  kind: "action",
  revision,
  widget: descriptor.id,
  action: command.verb,
  detail: structuredClone(command.detail ?? {}),
  ...(command.attempt && { attempt: command.attempt }),
});
