/* Typed commands over the current Thread reading.

   A package names a stable Thread key and the meaning of its gesture; this owner
   resolves the current message target and constructs the event. Core controls call
   these same commands. The application ledger remains the one optimistic and
   admission path, so a stale or unavailable command returns null. */
import { readThreads } from "./state.js";
import { reactionReading } from "./reaction-model.js";

export function createThreadActions({ post, withdraw, sendReaction, currentRevision }) {
  const find = (key) => {
    const collection = readThreads();
    return collection.phase === "ready"
      ? collection.threads.find((thread) => thread.key === key)
      : null;
  };

  const reply = (key, text, { attempt } = {}) => {
    if (typeof text !== "string") throw new TypeError("A Thread reply needs text");
    if (!text) return null;
    if (attempt !== undefined && (typeof attempt !== "string" || !attempt))
      throw new TypeError("A Thread reply attempt must be a non-empty string");
    const thread = find(key);
    if (!thread || thread.resolved || thread.settling) return null;
    return post({
      kind: "reply",
      revision: currentRevision(),
      parent: thread.root.id,
      text,
      ...(attempt && { attempt }),
    });
  };

  const settle = (key, resolved) => {
    const thread = find(key);
    if (!thread || Boolean(thread.resolved) === resolved || thread.settling)
      return null;
    return post({
      kind: resolved ? "resolve" : "unresolve",
      parent: thread.root.id,
    });
  };

  const toggleReaction = (key, messageId, token) => {
    const thread = find(key);
    const message = thread?.msgs.find((item) => item.id === messageId);
    const choice =
      message &&
      reactionReading(thread, message, true)?.choices.find(
        (item) => item.name === token,
      );
    if (!choice) return null;
    if (choice.standing) return withdraw(choice.standing);
    return sendReaction(
      {
        kind: "reply",
        parent: message.id,
        revision: currentRevision(),
        token,
      },
      null,
      `${message.agent}'s reply`,
      post,
    );
  };

  return Object.freeze({
    reply,
    resolve: (key) => settle(key, true),
    reopen: (key) => settle(key, false),
    toggleReaction,
  });
}
