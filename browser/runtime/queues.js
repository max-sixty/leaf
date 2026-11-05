// @ts-check
/* What an item on On me or On <agent> offers and what a row calls it. The server selects
 * the queues (`served_state.queues`) and the application publisher places this tab's sends
 * against them. An obligation is answered only through its source, a widget's own
 * controls or a reply in its thread, so no row offers a control of Leaf's own to end
 * it. Every row but a to-do's names an obligation record and carries it
 * (`obligation`). */
import { agentSays, saidBy } from "./voice.js";

// Whether a list item asks something of the user, whose row draws its record's
// prompt and the controls that answer or complete it. An
// update's record is answered by a reply or a version, or by the user sending again.
/** @template {import("./framework/snapshot.js").Immutable<import("./framework/application.js").CurrentQueueItem>} T
 * @param {T} item
 * @returns {item is T & {obligation: import("./obligations/answer.js").AnswerableObligation}} */
export const carriesObligation = (item) =>
  item.kind === "widget" || item.kind === "message";

// What a row names its item as: an update handed back to the user is one to send
// again; one the agent owes is a reply when it stands in a thread, else an answer the
// agent writes into the page.
/** @param {Pick<import("./framework/application.js").QueueItem, "kind" | "owner" | "thread">} item */
export const itemNoun = (item) =>
  item.kind !== "update"
    ? item.kind
    : item.owner === "user"
      ? "resend"
      : item.thread !== null
        ? "reply"
        : "answer";

// How a finished list item other than an obligation the page asked ended, in the words its
// row says: a reply the agent sent, or a to-do's outcome. A widget's
// obligation says its own ending (obligations/answer.js). The agent's own reply and
// the end it gave its own to-do are its acts, in its voice; Leaf says how anything
// else on the user's list ended (voice.js).
const OUTCOMES = Object.freeze({ done: "Done", failed: "Failed", dropped: "Dropped" });
/** @param {import("./framework/application.js").DoneItem} item */
export const itemOutcome = (item) =>
  item.kind === "update"
    ? agentSays("Answered")
    : saidBy(
        item.owner === "agent" ? "agent" : "leaf",
        OUTCOMES[item.state] ?? item.state,
      );
