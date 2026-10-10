/* Typed commands over the current Thread reading.

   A package names a stable Thread key and the meaning of its gesture; this owner
   resolves the current message target and constructs the event. Core controls call
   these same commands. The application ledger remains the one optimistic and
   admission path, so a stale or unavailable command returns null. */
import { readThreads } from "./state.js";

export function createThreadActions({
  post,
  withdraw,
  sendReaction,
  currentRevision,
  open,
}) {
  const create = (command) => {
    const {
      text,
      anchor,
      attempt = crypto.randomUUID(),
      holds,
      about,
      drawing,
      suggestion,
    } = command;
    if (text !== undefined && typeof text !== "string")
      throw new TypeError("A Thread comment needs text");
    if (typeof attempt !== "string" || !attempt)
      throw new TypeError("A Thread comment attempt must be a non-empty string");
    if (!text && !drawing) return null;
    const delivery = post({
      kind: "comment",
      revision: currentRevision(),
      ...(text !== undefined && { text }),
      ...(anchor !== undefined && { anchor: structuredClone(anchor) }),
      ...(attempt !== undefined && { attempt }),
      ...(holds !== undefined && { holds }),
      ...(about !== undefined && { about }),
      ...(drawing !== undefined && { drawing: structuredClone(drawing) }),
      ...(suggestion !== undefined && { suggestion }),
    });
    return delivery ? Object.freeze({ key: attempt, delivery }) : null;
  };
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
    if (!thread?.offers.reply) return null;
    return post({
      kind: "reply",
      revision: currentRevision(),
      parent: thread.root.id,
      text,
      ...(attempt && { attempt }),
    });
  };

  // A thread that already stands as asked, such as one resolved elsewhere while its
  // card still draws it open (held-news.js), sends nothing.
  const settle = (key, resolved, { attempt } = {}) => {
    const thread = find(key);
    if (!thread?.offers[resolved ? "resolve" : "reopen"]) return null;
    return post({
      kind: resolved ? "resolve" : "unresolve",
      parent: thread.root.id,
      ...(attempt && { attempt }),
    });
  };

  // An explicit desired state retains the meaning of a control drawn from a held
  // reading. A concurrent change that already achieved it sends nothing.
  const setReaction = (key, messageKey, token, active) => {
    if (typeof active !== "boolean")
      throw new TypeError("A reaction needs its desired standing state");
    const thread = find(key);
    const message = thread?.msgs.find((item) => item.key === messageKey);
    const choice =
      message && message.reactions?.choices.find((item) => item.name === token);
    if (!choice || active === Boolean(choice.standing)) return null;
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
    async open(key, { message = null, ...options } = {}) {
      const thread = find(key);
      if (!thread?.offers.open) return null;
      const target =
        message === null ? thread : thread.msgs.find((item) => item.key === message);
      if (!target) return null;
      return open(
        target.id,
        message === null ? options : { ...options, part: "message" },
      );
    },
    create,
    reply,
    resolve: (key, options) => settle(key, true, options),
    reopen: (key, options) => settle(key, false, options),
    setReaction,
  });
}
