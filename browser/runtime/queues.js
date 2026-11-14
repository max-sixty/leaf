// @ts-check
/* What an item on On Me or On <agent> offers and what a row calls it. The server selects
 * the queues (`served_state.queues`) and the application publisher places this tab's sends
 * against them. An obligation is answered only through its source, a widget's own
 * controls or a reply in its thread, so no row offers a control of Leaf's own to end
 * it. Every row names an obligation record and carries it (`obligation`), which says
 * where the item stands. */
import { agentSays, saidBy } from "./voice.js";

// An On list's name, for whoever it is on: the user's On Me, or On <agent>. A list's
// name is in title case, as On Claude is; a sentence about what waits on the user says
// `me` ("Nothing waiting on me").
/** @param {string} whom `me`, or the agent's name */
export const onList = (whom) => (whom === "me" ? "On Me" : `On ${whom}`);

// What an On list says while it lists nothing, by the reading's `phase`: that nothing
// waits on whoever it is on once the server's reading is in, else that the list can't
// be had while the server is offline or is still loading, as Threads says of its list.
// On Me's words are its empty view's, `m` pressed over it, and the notice of a reading
// that empties it (semantic-news.js).
/** @param {string} phase @param {string} whom `me`, or the agent's name */
export const emptyOnList = (phase, whom) =>
  phase === "ready"
    ? `Nothing waiting on ${whom}`
    : phase === "offline"
      ? `${onList(whom)} is unavailable while the server is offline`
      : `Loading ${onList(whom)}…`;
export const NOTHING_ON_ME = emptyOnList("ready", "me");

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
/** @param {import("./framework/snapshot.js").Immutable<import("./framework/application.js").CurrentQueueItem>} item */
export const itemOutcome = (item) =>
  item.kind === "update"
    ? agentSays("Answered")
    : saidBy(
        item.owner === "agent" ? "agent" : "leaf",
        OUTCOMES[item.obligation.outcome ?? "done"],
      );

// When a finished list item ended, and the detail its ending gave: the agent's end of
// a question or a to-do, or the answer's own time.
/** @param {import("./framework/snapshot.js").Immutable<import("./framework/application.js").CurrentQueueItem>} item */
export const itemEnding = ({ obligation }) =>
  Object.freeze({
    ended: (obligation.end ?? obligation.answer)?.event?.ts ?? null,
    detail: obligation.end?.detail ?? null,
  });
